from uuid import uuid4
from freezegun import freeze_time
import responses
import datetime
import mock
import pytest

from django.utils import timezone

from atol.core import AtolAPI
from atol.models import Receipt
from atol.tasks import (atol_create_receipt, atol_receive_receipt_report,
                        atol_retry_created_receipts, atol_retry_initiated_receipts)
from tests import ATOL_BASE_URL

pytestmark = pytest.mark.django_db(transaction=True)


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

    with mock.patch.object(atol_create_receipt, 'retry', wraps=atol_create_receipt.retry) as task_mock:
        atol_create_receipt.delay(receipt.id)
        assert len(task_mock.mock_calls) == 0

    receipt.refresh_from_db()
    assert receipt.status == 'failed'


@responses.activate
def test_atol_create_receipt_check_receipt_status():
    receipt = Receipt.objects.create(status='failed')

    with mock.patch.object(AtolAPI, 'sell', wraps=AtolAPI.sell) as sell_mock:
        atol_create_receipt.delay(receipt.id)
        assert len(sell_mock.mock_calls) == 0


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
        assert len(task_mock.mock_calls) == 5
        assert [call[1]['countdown'] for call in task_mock.call_args_list] == [60, 120, 420, 1200, 3240]

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

    with mock.patch.object(atol_receive_receipt_report, 'retry', wraps=atol_receive_receipt_report.retry) as task_mock:
        atol_receive_receipt_report.delay(receipt.id)
        assert len(task_mock.mock_calls) == 0

    receipt.refresh_from_db()
    assert receipt.status == 'failed'


@responses.activate
def test_atol_fetch_receipt_report_check_receipt_status():
    receipt = Receipt.objects.create()

    with mock.patch.object(AtolAPI, 'report', wraps=AtolAPI.sell) as report_mock:
        atol_receive_receipt_report.delay(receipt.id)
        assert len(report_mock.mock_calls) == 0


def test_retry_created_receipt_payments():
    now = timezone.now()

    with freeze_time(now - datetime.timedelta(hours=3)):
        receipt1 = Receipt.objects.create(status='created')
    with freeze_time(now - datetime.timedelta(hours=18)):
        receipt2 = Receipt.objects.create(status='created')
    with freeze_time(now - datetime.timedelta(hours=28)):
        Receipt.objects.create(status='created')
    with freeze_time(now - datetime.timedelta(hours=3)):
        Receipt.objects.create(status='failed')
    Receipt.objects.create(status='received')

    with mock.patch.object(atol_create_receipt, 'delay', wraps=atol_create_receipt.delay) as task_mock:
        atol_retry_created_receipts()
        assert len(task_mock.mock_calls) == 2
        assert {call[0][0] for call in task_mock.call_args_list} == {receipt1.id, receipt2.id}


def test_retry_initiated_receipt_payments():
    now = timezone.now()

    receipt1 = Receipt.objects.create(status='initiated', initiated_at=now - datetime.timedelta(hours=1))
    receipt2 = Receipt.objects.create(status='initiated', initiated_at=now - datetime.timedelta(hours=18))
    Receipt.objects.create(status='initiated', initiated_at=now - datetime.timedelta(hours=28))
    Receipt.objects.create(status='failed', initiated_at=now - datetime.timedelta(hours=3))
    Receipt.objects.create(status='received')

    with mock.patch.object(atol_receive_receipt_report, 'delay', wraps=atol_receive_receipt_report.delay) as task_mock:
        atol_retry_initiated_receipts()

    assert len(task_mock.mock_calls) == 2
    assert {call[0][0] for call in task_mock.call_args_list} == {receipt1.id, receipt2.id}
