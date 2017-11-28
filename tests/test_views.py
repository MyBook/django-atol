import pytest
from django.test import override_settings
from atol.models import Receipt, ReceiptStatus


@pytest.mark.django_db(transaction=True)
def test_receipt_302_normal_redirect(web_client):
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

    resp = web_client.get(receipt.ofd_link)
    assert resp.status_code == 302
    assert resp['Location'].startswith('https://lk.platformaofd')
    assert receipt.content['payload']['fn_number'] in resp['Location']

    with override_settings(RECEIPTS_OFD_URL_TEMPLATE=u'fake?t={t}&s={s}&fn={fn}&i={fd}&fp={fp}&n={n}'):
        resp = web_client.get(receipt.ofd_link)
        assert resp.status_code == 302
        assert '20170726T103200' in resp['Location']


@pytest.mark.django_db(transaction=True)
def test_receipt_404_missing_receipt(web_client):
    receipt = Receipt.objects.create(content=['Dummy'])
    response = web_client.get(receipt.ofd_link, expect_errors=True)
    assert response.status_code == 404


@pytest.mark.django_db(transaction=True)
def test_receipt_404_malformed_receipt(web_client):
    receipt = Receipt.objects.create(content={'a': 'b'})
    response = web_client.get(receipt.ofd_link, expect_errors=True)
    assert response.status_code == 404
