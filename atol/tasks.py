import math
import logging
from uuid import uuid4
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from django.apps import apps
from celery.exceptions import MaxRetriesExceededError
from celery import shared_task

from atol.core import AtolAPI
from atol.models import ReceiptStatus
from atol.exceptions import AtolUnrecoverableError, NoEmailAndPhoneError, AtolReceiptNotProcessed

logger = logging.getLogger(__name__)


@shared_task(name='atol_create_receipt', bind=True, max_retries=4, time_limit=60, soft_time_limit=45)
def atol_create_receipt(self, receipt_id):
    """
    Change receipt status and the change date accordingly
    If received an unrecoverable error, stop any further attempts to init a receipt and mark its status as failed
    """
    atol = AtolAPI()
    Receipt = apps.get_model('atol', 'Receipt')
    receipt = Receipt.objects.get(id=receipt_id)

    try:
        params = receipt.get_params()
    except NoEmailAndPhoneError:
        # this email should have been sent, but we got neither email
        logger.warning('unable to init receipt %s due to missing email/phone', receipt.id)
        receipt.declare_failed(status=ReceiptStatus.no_email_phone)
        return

    if receipt.status not in [ReceiptStatus.created, ReceiptStatus.retried]:
        logger.error('receipt %s has invalid status: %s', receipt.uuid, receipt.status)
        return

    try:
        receipt_data = atol.sell(**params)
    except AtolUnrecoverableError as exc:
        logger.error('unable to init receipt %s with params %s due to %s', receipt.id, params, exc,
                     exc_info=True, extra={'data': {'payment_params': params}})
        receipt.declare_failed()
    except Exception as exc:
        logger.warning('failed to init receipt %s with params %s due to %s', receipt.id, params, exc,
                       exc_info=True, extra={'data': {'payment_params': params}})
        try:
            countdown = 60 * int(math.exp(self.request.retries))
            logger.info('retrying to create receipt %s with params %s countdown %s due to %s',
                        receipt.id, params, countdown, exc)
            self.retry(countdown=countdown)
        except MaxRetriesExceededError:
            logger.error('run out of attempts to create receipt %s with params %s due to %s',
                         receipt.id, params, exc)
            receipt.declare_failed()
    else:
        with transaction.atomic():
            receipt.initiate(uuid=receipt_data.uuid)
            transaction.on_commit(
                lambda: atol_receive_receipt_report.apply_async(args=(receipt.id,), countdown=60)
            )


@shared_task(name='atol_receive_receipt_report', bind=True, max_retries=4, time_limit=60, soft_time_limit=45)
def atol_receive_receipt_report(self, receipt_id):
    """
    Attempt to retrieve a receipt report for given receipt_id
    If received an unrecoverable error, then stop any further attempts to receive the report
    """
    atol = AtolAPI()
    Receipt = apps.get_model('atol', 'Receipt')
    receipt = Receipt.objects.get(id=receipt_id)

    if not receipt.uuid:
        logger.error('receipt %s does not have a uuid', receipt.id)
        return

    if receipt.status not in [ReceiptStatus.initiated, ReceiptStatus.retried]:
        logger.error('receipt %s has invalid status: %s', receipt.uuid, receipt.status)
        return

    try:
        report = atol.report(receipt.uuid)
    except AtolUnrecoverableError as exc:
        logger.error('unable to fetch report for receipt %s due to %s',
                     receipt.id, exc, exc_info=True)
        receipt.declare_failed()
    except AtolReceiptNotProcessed as exc:
        logger.warning('unable to fetch report for receipt %s due to %s',
                       receipt.id, exc, exc_info=True)
        logger.info('repeat receipt registration: id %s; old internal_uuid %s',
                    receipt.id, receipt.internal_uuid)
        with transaction.atomic():
            receipt.internal_uuid = uuid4()
            receipt.status = ReceiptStatus.retried
            receipt.save(update_fields=['internal_uuid', 'status'])
            transaction.on_commit(
                lambda: atol_create_receipt.apply_async(args=(receipt.id,), countdown=60)
            )
    except Exception as exc:
        logger.warning('failed to fetch report for receipt %s due to %s',
                       receipt.id, exc, exc_info=True)
        try:
            countdown = 60 * int(math.exp(self.request.retries))
            logger.info('retrying to receive receipt %s with countdown %s due to %s',
                        receipt.id, countdown, exc)
            self.retry(countdown=countdown)
        except MaxRetriesExceededError:
            logger.error('run out of attempts to create receipt %s due to %s',
                         receipt.id, exc)
            receipt.declare_failed()
    else:
        with transaction.atomic():
            receipt.receive(content=report.data)


@shared_task(name='atol_retry_created_receipts', time_limit=3600)
def atol_retry_created_receipts():
    """
    Retry older receipt that have not been initiated by this time for some reason
    """
    Receipt = apps.get_model('atol', 'Receipt')
    now = timezone.now()

    created_receipts = (Receipt.objects
                        .filter(status=ReceiptStatus.created,
                                created_at__range=(now - timedelta(days=1), now)))

    logger.info('there are %s receipts waiting to be initiated', created_receipts.count())

    for receipt in created_receipts.only('pk').iterator():
        logger.info('retrying created receipt %s', receipt.id)
        atol_create_receipt.delay(receipt.id)


@shared_task(name='atol_retry_initiated_receipts', time_limit=3600)
def atol_retry_initiated_receipts():
    """
    Retry older receipts that have been initiated but have not been received receipt report from atol
    """
    Receipt = apps.get_model('atol', 'Receipt')
    now = timezone.now()

    initiated_receipts = (Receipt.objects
                          .filter(status=ReceiptStatus.initiated,
                                  initiated_at__range=(now - timedelta(days=1), now)))

    logger.info('there are %s initiated receipts waiting for report', initiated_receipts.count())

    for receipt in initiated_receipts.only('pk').iterator():
        logger.info('retrying initiated payment %s', receipt.id)
        atol_receive_receipt_report.delay(receipt.id)
