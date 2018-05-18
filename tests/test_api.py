from datetime import datetime
from uuid import uuid4
import responses
import pytest
from django.test import override_settings

from atol.core import AtolAPI
from atol.exceptions import AtolRecoverableError, AtolUnrecoverableError
from tests import ATOL_BASE_URL

ATOL_AUTH_CACHE_KEY = 'atol_auth_token:login'


@pytest.fixture
def caches():
    from django.core.cache import caches
    yield caches


@pytest.fixture
def set_atol_token(caches):
    def setter(token=None):
        token = token or str(uuid4().hex)[:12]
        caches['default'].set(ATOL_AUTH_CACHE_KEY, token)
        return token
    return setter


@responses.activate
def test_atol_create_receipt_workflow():
    uid = '973f3bef-1c39-40c9-abd0-33a91ab005ca'
    # get Token
    data = {
        'code': 1,
        'text': None,
        'token': '84a50b3a6207421aba46834d650b42a0'
    }
    url = ATOL_BASE_URL + '/getToken'
    responses.add(responses.POST, url, status=200, json=data)

    # sell
    data = {
        'uuid': uid,
        'timestamp': '13.07.2017 18:32:49',
        'status': 'wait',
        'error': None
    }
    url = ATOL_BASE_URL + '/ATOL-ProdTest-1/sell'
    responses.add(responses.POST, url, status=200, json=data)

    # report error
    data = {
        'uuid': uid,
        'timestamp': '13.07.2017 18:32:49',
        'status': 'wait',
        'error': {
            'code': 16,
            'text': 'Нет информации, попробуйте позднее',
            'type': 'system'
        },
        'payload': None
    }
    url = ATOL_BASE_URL + '/ATOL-ProdTest-1/report/' + uid
    responses.add(responses.GET, url, status=200, json=data)

    # report ok
    data = {
        'uuid': uid,
        'error': None,
        'status': 'done',
        'payload': {
            'total': 199.99,
            'fns_site': 'www.nalog.ru',
            'fn_number': '9999078900003780',
            'shift_number': 114,
            'receipt_datetime': '13.07.2017 18:32:00',
            'fiscal_receipt_number': 1412,
            'fiscal_document_number': 50066,
            'ecr_registration_number': '1029384756033729',
            'fiscal_document_attribute': 2649836604
        },
        'timestamp': '13.07.2017 18:32:50',
        'group_code': 'ATOL-ProdTest-1',
        'daemon_code': 'prod-agent-1',
        'device_code': 'KSR13.11-3-1',
        'callback_url': ''
    }
    url = ATOL_BASE_URL + '/ATOL-ProdTest-1/report/' + uid
    responses.add(responses.GET, url, status=200, json=data)

    # sell error
    data = {
        'uuid': uid,
        'timestamp': '13.07.2017 18:32:50',
        'status': 'fail',
        'error': {
            'code': 10,
            'text': 'В системе существует чек с external_id : ec0ce0c6-7a31-4f45-b94f-a1442be3bb9c '
                    'и group_code: ATOL-ProdTest-1',
            'type': 'system'
        }
    }
    url = ATOL_BASE_URL + '/ATOL-ProdTest-1/sell'
    responses.add(responses.POST, url, status=200, json=data)

    atol = AtolAPI()

    now = datetime(2017, 11, 22, 10, 47, 32)
    payment_uuid = str(uuid4())

    sell_params = dict(timestamp=now, transaction_uuid=payment_uuid,
                       purchase_name=u'Стандартная подписка на 1 месяц', purchase_price='199.99',
                       user_email='user@example.com', user_phone='+75551234567')

    receipt = atol.sell(**sell_params)

    assert receipt.uuid == '973f3bef-1c39-40c9-abd0-33a91ab005ca'
    assert receipt.data['status'] == 'wait'

    # report is not ready yet
    with pytest.raises(AtolRecoverableError):
        atol.report(receipt.uuid)

    report = atol.report(receipt.uuid)
    assert report.data['group_code'] == 'ATOL-ProdTest-1'
    assert report.data['status'] == 'done'
    assert report.data['payload']['total'] == 199.99

    # another celery worker somehow requested the same payment receipt
    double_receipt = atol.sell(**sell_params)
    assert double_receipt.uuid == '973f3bef-1c39-40c9-abd0-33a91ab005ca'
    assert double_receipt.data['status'] == 'fail'


@pytest.mark.parametrize('status,params', [
    (500, {'body': b''}),
    (302, {'body': b''}),
    (400, {'json': {'error': {'code': 1}}}),
    (400, {'json': {'error': {'code': 6}}}),
])
@responses.activate
def test_atol_sell_recoverable_errors(status, params, set_atol_token):
    atol = AtolAPI()
    set_atol_token('12345')

    sell_params = dict(timestamp=datetime.now(), transaction_uuid=str(uuid4()),
                       purchase_name=u'Стандартная подписка на 1 месяц', purchase_price='199.99',
                       user_email='user@example.com', user_phone='+75551234567')

    responses.add(responses.POST, ATOL_BASE_URL + '/ATOL-ProdTest-1/sell', status=status, **params)

    with pytest.raises(AtolRecoverableError):
        atol.sell(**sell_params)


@pytest.mark.parametrize('status,params', [
    (400, {'json': {'error': {'code': 3}}}),
    (400, {'json': {'error': {'code': 22}}}),
])
@responses.activate
def test_atol_sell_unrecoverable_errors(status, params, set_atol_token):
    atol = AtolAPI()
    set_atol_token('12345')

    sell_params = dict(timestamp=datetime.now(), transaction_uuid=str(uuid4()),
                       purchase_name=u'Стандартная подписка на 1 месяц', purchase_price='199.99',
                       user_email='user@example.com', user_phone='+75551234567')

    responses.add(responses.POST, ATOL_BASE_URL + '/ATOL-ProdTest-1/sell', status=status, **params)

    with pytest.raises(AtolUnrecoverableError):
        atol.sell(**sell_params)


def test_atol_sell_expired_token_is_renewed(set_atol_token, caches):
    atol = AtolAPI()
    set_atol_token('12345')

    assert caches['default'].get(ATOL_AUTH_CACHE_KEY) == '12345'

    receipt_uuid = str(uuid4())

    with responses.RequestsMock(assert_all_requests_are_fired=True) as resp_mock:
        resp_mock.add(responses.POST, ATOL_BASE_URL + '/ATOL-ProdTest-1/sell', status=401)
        resp_mock.add(responses.POST, ATOL_BASE_URL + '/getToken', status=200,
                      json={'code': 0, 'token': 'foobar'})
        resp_mock.add(responses.POST, ATOL_BASE_URL + '/ATOL-ProdTest-1/sell', status=200,
                      json={'uuid': receipt_uuid})

        sell_params = dict(timestamp=datetime.now(), transaction_uuid=str(uuid4()),
                           purchase_name=u'Стандартная подписка на 1 месяц', purchase_price='199.99',
                           user_email='user@example.com', user_phone='+75551234567')

        receipt = atol.sell(**sell_params)
        assert receipt.uuid == receipt_uuid
        assert resp_mock.calls[0].request.url.endswith('?tokenid=12345')

    # token is updated
    assert caches['default'].get(ATOL_AUTH_CACHE_KEY) == 'foobar'

    with responses.RequestsMock(assert_all_requests_are_fired=True) as resp_mock:
        anoher_receipt_uuid = str(uuid4())
        resp_mock.add(responses.POST, ATOL_BASE_URL + '/ATOL-ProdTest-1/sell', status=200,
                      json={'uuid': anoher_receipt_uuid})

        sell_params = dict(timestamp=datetime.now(), transaction_uuid=str(uuid4()),
                           purchase_name=u'Стандартная подписка на 1 месяц', purchase_price='199.99',
                           user_email='user@example.com', user_phone='+75551234567')

        receipt = atol.sell(**sell_params)
        assert receipt.uuid == anoher_receipt_uuid
        assert resp_mock.calls[0].request.url.endswith('?tokenid=foobar')


def test_atol_sell_expired_token_is_failed_to_renew(set_atol_token):
    atol = AtolAPI()
    set_atol_token()

    with responses.RequestsMock(assert_all_requests_are_fired=True) as resp_mock:
        resp_mock.add(responses.POST, ATOL_BASE_URL + '/ATOL-ProdTest-1/sell', status=401)
        resp_mock.add(responses.POST, ATOL_BASE_URL + '/getToken', status=400, json={'code': 19})

        sell_params = dict(timestamp=datetime.now(), transaction_uuid=str(uuid4()),
                           purchase_name=u'Стандартная подписка на 1 месяц', purchase_price='199.99',
                           user_email='user@example.com', user_phone='+75551234567')

        with pytest.raises(AtolRecoverableError):
            atol.sell(**sell_params)


@pytest.mark.parametrize('status,params', [
    (500, {'body': b''}),
    (302, {'body': b''}),
    (400, {'json': {'error': {'code': 7}}}),
    (400, {'json': {'error': {'code': 12}}}),
    (400, {'json': {'error': {'code': 16}}}),
])
@responses.activate
def test_atol_report_recoverable_errors(status, params, set_atol_token):
    atol = AtolAPI()
    set_atol_token('12345')
    payment_uuid = str(uuid4())

    responses.add(responses.POST, ATOL_BASE_URL + '/ATOL-ProdTest-1/report/%s' % payment_uuid,
                  status=status, **params)

    with pytest.raises(AtolRecoverableError):
        atol.report(payment_uuid)


@pytest.mark.parametrize('status,params', [
    (400, {'json': {'error': {'code': 3}}}),
    (400, {'json': {'error': {'code': 15}}}),
])
@responses.activate
def test_atol_report_unrecoverable_errors(status, params, set_atol_token):
    atol = AtolAPI()
    set_atol_token('12345')
    payment_uuid = str(uuid4())

    responses.add(responses.GET, ATOL_BASE_URL + '/ATOL-ProdTest-1/report/%s' % payment_uuid,
                  status=status, **params)

    with pytest.raises(AtolUnrecoverableError):
        atol.report(payment_uuid)


def test_atol_api_base_url():
    """
    We Check base_url in case that RECEIPTS_ATOL_BASE_URL is not specified in settings
    """
    assert AtolAPI().base_url == 'https://online.atol.ru/possystem/v3'


@pytest.mark.parametrize('settings_url, api_base_url', [
    ('test_url', 'test_url'),
    ('', 'https://online.atol.ru/possystem/v3'),
    (None, 'https://online.atol.ru/possystem/v3')
])
def test_atol_api_base_url_customizing(settings_url, api_base_url):
    """
    We check base_url in case of specifying RECEIPTS_ATOL_BASE_URL as different values in settings
    :param settings_url: url in settings
    :param api_base_url: url, which must be in AtolAPI
    """
    with override_settings(RECEIPTS_ATOL_BASE_URL=settings_url):
        assert AtolAPI().base_url == api_base_url
