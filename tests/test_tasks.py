from uuid import uuid4
from freezegun import freeze_time
import responses
import datetime
import mock
import pytest

from django.utils import timezone

from atol.core import AtolAPI, NewReceipt
from atol.models import Receipt, ReceiptStatus
from atol.tasks import (atol_create_receipt, atol_receive_receipt_report,
                        atol_retry_created_receipts, atol_retry_initiated_receipts)
from tests import ATOL_BASE_URL

pytestmark = pytest.mark.django_db(transaction=True)


@responses.activate
def test_created_receipt_ok():
    now = timezone.now()
    responses.add(responses.POST, ATOL_BASE_URL + '/getToken', status=200,
                  json={'code': 0, 'token': 'foobar'})

    receipt = Receipt.objects.create(user_email='foo@bar.com', purchase_price=707.1)

    with mock.patch.object(AtolAPI, 'sell', wraps=AtolAPI.sell) as sell_mock:
        with mock.patch.object(atol_receive_receipt_report, 'apply_async') as task_mock:
            sell_mock.return_value = NewReceipt(uuid='5869a6d9-1540-4ebb-a2a2-f1d11501f213', data=None)
            atol_create_receipt(receipt.id)
            assert len(task_mock.mock_calls) == 1

    receipt.refresh_from_db()
    assert receipt.uuid == '5869a6d9-1540-4ebb-a2a2-f1d11501f213'
    assert receipt.status == ReceiptStatus.initiated
    assert receipt.initiated_at > now


@responses.activate
def test_atol_create_failing_receipt_progressive_countdown():
    responses.add(responses.POST, ATOL_BASE_URL + '/getToken', status=200,
                  json={'code': 0, 'token': 'foobar'})
    responses.add(responses.POST, ATOL_BASE_URL + '/ATOL-ProdTest-1/sell', status=500)

    receipt = Receipt.objects.create(user_email='foo@bar.com', purchase_price=999)

    with mock.patch.object(atol_create_receipt, 'retry', wraps=atol_create_receipt.retry) as task_mock:
        atol_create_receipt.delay(receipt.id)
        assert len(task_mock.mock_calls) == 5
        assert [call[1]['countdown'] for call in task_mock.call_args_list] == [60, 120, 420, 1200, 3240]

    receipt.refresh_from_db()
    assert receipt.status == 'failed'


@responses.activate
def test_atol_create_receipt_stopped_on_unrecoverable_error():
    responses.add(responses.POST, ATOL_BASE_URL + '/getToken',
                  status=200, json={'code': 0, 'token': 'foobar'})
    responses.add(responses.POST, ATOL_BASE_URL + '/ATOL-ProdTest-1/sell',
                  status=400, json={'error': {'code': 3}})

    receipt = Receipt.objects.create(user_email='foo@bar.com', purchase_price=999)
    atol_create_receipt(receipt.id)
    receipt.refresh_from_db()
    assert receipt.status == 'failed'


@pytest.mark.parametrize(['receipt_data', 'status'], [
    ({'status': 'failed', 'purchase_price': 299, 'user_email': 'foo@bar.com'}, ReceiptStatus.failed),
    ({'purchase_price': 299}, ReceiptStatus.no_email_phone),
])
def test_atol_create_receipt_fail(receipt_data, status):
    receipt = Receipt.objects.create(**receipt_data)

    with mock.patch.object(AtolAPI, 'sell') as sell_mock:
        atol_create_receipt(receipt.id)
        assert len(sell_mock.mock_calls) == 0

    receipt.refresh_from_db()
    assert receipt.status == status


@responses.activate
def test_atol_failing_receive_report_progressive_countdown():
    uuid = str(uuid4())
    receipt = Receipt.objects.create(status='initiated', uuid=uuid)

    responses.add(responses.POST, ATOL_BASE_URL + '/getToken',
                  status=200, json={'code': 0, 'token': 'foobar'})
    responses.add(responses.GET, ATOL_BASE_URL + '/ATOL-ProdTest-1/report/%s' % uuid,
                  status=500)

    with mock.patch.object(atol_receive_receipt_report, 'retry', wraps=atol_receive_receipt_report.retry) as task_mock:
        atol_receive_receipt_report.delay(receipt.id)
        assert len(task_mock.mock_calls) == 9
        countdown_prognosis = [60, 120, 420, 1200, 3240, 8880, 24180, 65760, 178800]
        assert [call[1]['countdown'] for call in task_mock.call_args_list] == countdown_prognosis

    receipt.refresh_from_db()
    assert receipt.status == 'failed'


@responses.activate
def test_atol_fetch_receipt_report_stopped_on_unrecoverable_error():
    uuid = str(uuid4())
    receipt = Receipt.objects.create(status='initiated', uuid=uuid)

    responses.add(responses.POST, ATOL_BASE_URL + '/getToken',
                  status=200, json={'code': 0, 'token': 'foobar'})
    responses.add(responses.GET, ATOL_BASE_URL + '/ATOL-ProdTest-1/report/%s' % uuid,
                  status=400, json={'error': {'code': 3}})

    atol_receive_receipt_report(receipt.id)
    receipt.refresh_from_db()
    assert receipt.status == 'failed'


@responses.activate
def test_atol_fetch_receipt_report_check_receipt_status():
    uuid = str(uuid4())
    receipt = Receipt.objects.create(uuid=uuid)

    with mock.patch.object(AtolAPI, 'report') as report_mock:
        atol_receive_receipt_report(receipt.id)
        assert len(report_mock.mock_calls) == 0


@responses.activate
def test_retry_created_receipt_for_not_processed_receipt():
    uuid = str(uuid4())
    now = timezone.now()
    receipt = Receipt.objects.create(status='initiated', uuid=uuid, purchase_price=1234.5,
                                     user_phone='+79991234567')

    responses.add(responses.POST, ATOL_BASE_URL + '/getToken',
                  status=200, json={'code': 0, 'token': 'foobar'})
    responses.add(responses.GET, ATOL_BASE_URL + '/ATOL-ProdTest-1/report/%s' % uuid,
                  status=400, json={'error': {'code': 1}})

    with mock.patch.object(AtolAPI, 'sell', wraps=AtolAPI.sell) as sell_mock:
        sell_mock.return_value = NewReceipt(uuid='42ee0a7a-2b30-42f1-951f-1c131e2ab322', data=None)

        with mock.patch.object(atol_receive_receipt_report, 'apply_async'):
            atol_receive_receipt_report(receipt.id)
        assert len(sell_mock.mock_calls) == 1

    receipt.refresh_from_db()
    assert receipt.uuid == '42ee0a7a-2b30-42f1-951f-1c131e2ab322'
    assert receipt.status == ReceiptStatus.retried
    assert receipt.retried_at > now


def test_retry_created_receipt_payments():
    now = timezone.now()

    with freeze_time(now - datetime.timedelta(hours=3)):
        Receipt.objects.create()
    with freeze_time(now - datetime.timedelta(hours=25)):
        receipt1 = Receipt.objects.create()
    with freeze_time(now - datetime.timedelta(hours=31)):
        receipt2 = Receipt.objects.create()
    with freeze_time(now - datetime.timedelta(hours=49)):
        Receipt.objects.create()
    with freeze_time(now - datetime.timedelta(hours=31)):
        Receipt.objects.create(status='failed')
    Receipt.objects.create(status='received')

    with mock.patch.object(atol_create_receipt, 'delay') as task_mock:
        atol_retry_created_receipts()
        assert len(task_mock.mock_calls) == 2
        assert {call[0][0] for call in task_mock.call_args_list} == {receipt1.id, receipt2.id}


def test_retry_initiated_receipt_payments():
    now = timezone.now()

    receipt1 = Receipt.objects.create(status='initiated', initiated_at=now - datetime.timedelta(hours=25))
    receipt2 = Receipt.objects.create(status='initiated', initiated_at=now - datetime.timedelta(hours=31))
    Receipt.objects.create(status='initiated', initiated_at=now - datetime.timedelta(hours=1))
    Receipt.objects.create(status='initiated', initiated_at=now - datetime.timedelta(hours=49))
    Receipt.objects.create(status='failed', initiated_at=now - datetime.timedelta(hours=25))
    Receipt.objects.create(status='received')

    with mock.patch.object(atol_receive_receipt_report, 'delay') as task_mock:
        atol_retry_initiated_receipts()

    assert len(task_mock.mock_calls) == 2
    assert {call[0][0] for call in task_mock.call_args_list} == {receipt1.id, receipt2.id}
