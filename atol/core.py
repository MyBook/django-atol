import logging
import requests
from collections import namedtuple
from dateutil.parser import parse as parse_date

from django.conf import settings
from django.core.cache import cache

from atol import exceptions

logger = logging.getLogger(__name__)

NewReceipt = namedtuple('NewReceipt', ['uuid', 'data'])
ReceiptReport = namedtuple('ReceiptReport', ['uuid', 'data'])


class AtolAPI(object):
    request_timeout = 5

    def __init__(self):
        self.base_url = getattr(settings, 'RECEIPTS_ATOL_BASE_URL', None) or 'https://online.atol.ru/possystem/v3'

    def _obtain_new_token(self):
        """
        Obtain new access token using the login-password credentials pair.
        If failed to obtain token, raise an exception.
        """
        response_data = self._request('post', 'getToken', json={
            'login': settings.RECEIPTS_ATOL_LOGIN,
            'pass': settings.RECEIPTS_ATOL_PASSWORD,
        })
        # all codes other than 0 (new token) and 1 (existing token) are considered errors
        if response_data.get('code') not in (0, 1):
            raise exceptions.AtolAuthTokenException()

        auth_token = response_data['token']
        logger.info('successfully obtained fresh auth token "%s" for login "%s"',
                    auth_token, settings.RECEIPTS_ATOL_LOGIN)
        return auth_token

    def _get_auth_token(self, force_renew=False):
        """
        Obtain the authentication token obtained earlier and put in cache.
        In case the cache yields nothing, or the token has expired (401),
        obtain a new token then put in cache.
        """
        cache_key = 'atol_auth_token:{login}'.format(login=settings.RECEIPTS_ATOL_LOGIN)
        auth_token = cache.get(cache_key)

        # obtain and store fresh auth token
        if not auth_token or force_renew:
            auth_token = self._obtain_new_token()
            # cache the key forever without a ttl
            cache.set(cache_key, auth_token)
        else:
            logger.debug('successfully obtained auth token "%s" for login "%s" from cache',
                         auth_token, settings.RECEIPTS_ATOL_LOGIN)

        return auth_token

    def request(self, method, endpoint, json=None):
        """
        Make a request to atol api endpoint using cached access token.

        If endpoint yields a 401 error, obtain a new token then try the request again.

        :param method: HTTP method
        :param endpoint: Name of atol endpoint (e.g. sell, report, you name it)
        :param json: json-ready request data (normally this would be a dict)

        The final url will assume the following form:
            https://online.atol.ru/possystem/v3/MyCompany_MyShop/sell?tokenid=d8c7021934fg4f2384ebf6b72624bbbf
        """
        auth_token = self._get_auth_token()

        params = {
            'tokenid': auth_token
        }

        # signed requests contain group codes in front of the endpoint name
        endpoint = '{group_code}/{endpoint}'.format(group_code=settings.RECEIPTS_ATOL_GROUP_CODE,
                                                    endpoint=endpoint)

        try:
            return self._request(method, endpoint, params=params, json=json)
        except exceptions.AtolAuthTokenException:
            # token must have expired, try new one
            logger.info('trying new token for request "%s" to endpoint %s with params=%s json=%s token=%s',
                        method, endpoint, params, json, auth_token)
            params.update({'tokenid': self._get_auth_token(force_renew=True)})
            return self._request(method, endpoint, params=params, json=json)

    def _request(self, method, endpoint, params=None, headers=None, json=None):
        params = params or {}
        headers = headers or {}
        headers.setdefault('Content-Type', 'application/json')

        url = '{base_url}/{endpoint}'.format(base_url=self.base_url.rstrip('/'),
                                             endpoint=endpoint)

        logger.info('about to %s %s with headers=%s, params=%s json=%s', method, url, headers, params, json)

        try:
            response = requests.request(method, url, params=params, json=json,
                                        headers=headers, timeout=self.request_timeout)
        except Exception as exc:
            logger.warning('failed to request %s %s with headers=%s, params=%s json=%s due to %s',
                           method, url, headers, params, json, exc,
                           exc_info=True,
                           extra={'data': {'json': json, 'params': params}})
            raise exceptions.AtolRequestException()

        # error codes other than 2xx, 400, 401 are considered unexpected and yield an exception
        if response.status_code not in (200, 201, 400, 401):
            try:
                json_response = response.json()
            except Exception:
                json_response = None
            logger.warning('request %s %s with headers=%s, params=%s json=%s failed with status code %s: %s',
                           method, url, headers, params, json, response.status_code, json_response,
                           extra={'data': {'json_request': json,
                                           'content': response.content,
                                           'json_response': json_response}})
            raise exceptions.AtolRequestException()

        # 401 should be handled separately by the calling code
        if response.status_code == 401:
            logger.info('authentication failed for request %s %s with headers=%s, params=%s json=%s',
                        method, url, headers, params, json, extra={'data': {'content': response.content}})
            raise exceptions.AtolAuthTokenException()

        try:
            response_data = response.json()
        except Exception as exc:
            logger.warning('unable to parse json response due to %s', exc, exc_info=True,
                           extra={'data': {'content': response.content}})
            raise exceptions.AtolRequestException()

        if response_data.get('error'):
            logger.warning('received error response from atol url %s: %s',
                           url, response_data['error'],
                           extra={'data': {'json': json, 'params': params}})
            raise exceptions.AtolClientRequestException(response=response,
                                                        response_data=response_data,
                                                        error_data=response_data['error'])

        return response_data

    def sell(self, **params):
        """
        Register a new receipt for given payment details on the atol side.
        Receive receipt uuid for the created receipt.

        :param timestamp: Payment datetime
        :param transaction_uuid: Unique payment id (potentically across all organization projects' payments.
                                 uuid4 should do fine.
        :param purchase_name: Human readable name of the purchased product
        :param purchase_price: The amount in roubles the user was billed with
        :param user_email: User supplied email
        :param user_phone: User supplied phone (may or may not start with +7)
        """
        user_email = params.get('user_email')
        user_phone = params.get('user_phone')
        # receipt must contain either of the two
        if not (user_email or user_phone):
            raise exceptions.AtolPrepRequestException()

        purchase_price = params['purchase_price']
        # convert decimals and strings to float, because atol does not accept those types
        if not isinstance(purchase_price, int):
            purchase_price = float(purchase_price)

        timestamp = params['timestamp']
        if isinstance(timestamp, str):
            timestamp = parse_date(timestamp)

        request_data = {
            'external_id': params['transaction_uuid'],
            'timestamp': timestamp.strftime('%d.%m.%Y %H:%M:%S'),
            'receipt': {
                # user supplied details
                'attributes': {
                    'email': user_email or u'',
                    'phone': user_phone or u'',
                },
                'items': [{
                    'name': params['purchase_name'],
                    'price': purchase_price,
                    'quantity': 1,
                    'sum': purchase_price,
                    'tax': settings.RECEIPTS_ATOL_TAX_NAME,
                }],
                'payments': [{
                    'sum': purchase_price,
                    'type': 1,
                }],
                'total': purchase_price,
            },
            'service': {
                'inn': settings.RECEIPTS_ATOL_INN,
                'callback_url': settings.RECEIPTS_ATOL_CALLBACK_URL or u'',
                'payment_address': settings.RECEIPTS_ATOL_PAYMENT_ADDRESS,
            }
        }

        try:
            response_data = self.request('post', 'sell', json=request_data)
        # check for recoverable errors
        except exceptions.AtolClientRequestException as exc:
            logger.info('sell request with json %s failed with code %s', request_data, exc.error_data['code'])
            if exc.error_data['code'] in (1, 4, 5, 6):
                raise exceptions.AtolRecoverableError()
            if exc.error_data['code'] == 10:
                logger.info('sell request with json %s already accepted; uuid: %s',
                            request_data, exc.response_data['uuid'])
                return NewReceipt(uuid=exc.response_data['uuid'], data=exc.response_data)
            # the rest of the errors are not recoverable
            raise exceptions.AtolUnrecoverableError()
        except Exception as exc:
            logger.warning('sell request with json %s failed due to %s', request_data, exc, exc_info=True)
            raise exceptions.AtolRecoverableError()

        return NewReceipt(uuid=response_data['uuid'], data=response_data)

    def report(self, receipt_uuid):
        """
        The receipt may not yet be processed by the time of the request,
        the calling code should try this method again later.

        :param receipt_uuid: Receipt identifier previously returned by atol
        """
        try:
            response_data = self.request('get', 'report/{uuid}'.format(uuid=receipt_uuid))
        # check for recoverable errors
        except exceptions.AtolClientRequestException as exc:
            logger.info('report request for receipt %s failed with code %s', receipt_uuid, exc.error_data['code'])
            if exc.error_data['code'] in (7, 9, 12, 13, 14, 16):
                raise exceptions.AtolRecoverableError()
            if exc.error_data['code'] == 1:
                logger.info('report request for receipt %s was not processed: %s; '
                            'Must repeat the request with a new unique value <external_id>',
                            receipt_uuid, exc.response_data.get('text'))
                raise exceptions.AtolReceiptNotProcessed(exc.response_data.get('text'))
            # the rest of the errors are not recoverable
            raise exceptions.AtolUnrecoverableError()
        except Exception as exc:
            logger.info('report request for receipt %s failed due to %s', receipt_uuid, exc)
            raise exceptions.AtolRecoverableError()

        return ReceiptReport(uuid=receipt_uuid, data=response_data)
