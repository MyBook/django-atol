import pytest
from django.test import override_settings
from atol.models import Receipt, ReceiptStatus

pytestmark = pytest.mark.django_db(transaction=True)


def test_receipt_302_normal_redirect(client):
    data = {
        'callback_url': '',
        'daemon_code': 'prod-agent-3',
        'device_code': 'KSR13.11-8-18',
        'error': None,
        'group_code': 'mybook-ru_1815',
        'payload': {
            'ecr_registration_number': '0000932756018558',
            'fiscal_document_attribute': 4146968358,
            'fiscal_document_number': 40,
            'fiscal_receipt_number': 1,
            'fn_number': '8710000100942521',
            'fns_site': 'www.nalog.ru',
            'receipt_datetime': '26.07.2017 10:32:00',
            'shift_number': 19,
            'total': 12
        },
        'status': 'done',
        'timestamp': '26.07.2017 10:32:21',
        'uuid': 'd407f2bf-edb8-43c9-aac4-468c05f1a8d8'
    }
    receipt = Receipt.objects.create(content=data, status=ReceiptStatus.received)

    resp = client.get(receipt.ofd_link)
    assert resp.status_code == 302
    assert resp['Location'].startswith('https://lk.platformaofd')
    assert receipt.content['payload']['fn_number'] in resp['Location']

    with override_settings(RECEIPTS_OFD_URL_TEMPLATE=u'fake?t={t}&s={s}&fn={fn}&i={fd}&fp={fp}&n={n}'):
        resp = client.get(receipt.ofd_link)
        assert resp.status_code == 302
        assert '20170726T103200' in resp['Location']


@pytest.mark.parametrize('content', [
    ['Dummy'],
    {'a': 'b'},
    None,
])
def test_receipt_404(content, client):
    receipt = Receipt.objects.create(content=content)
    response = client.get(receipt.ofd_link, expect_errors=True)
    assert response.status_code == 404
