import logging
import shortuuid

from django.conf import settings
from django.http import HttpResponseNotFound
from django.shortcuts import get_object_or_404
from django.utils.encoding import force_bytes
from django.views.generic import RedirectView
from django.utils.translation import ugettext_lazy as _

from atol.models import Receipt
from atol.exceptions import MissingReceipt
from atol.utils import parse_receipt_datetime

logger = logging.getLogger(__name__)


class ReceiptView(RedirectView):
    """
    Anonymous view as a proxy to OFD provider.
    - link is shorter for sms usage (use internal uuid, so that we have stable link for our payments)
    - ability to change ofd at any point
    - links will not break even if ofd-1 changes URL scheme
    - easy way to monitor feature usage via logs

    Swallows missing receipts and malformed data to show only 404 (user-friendly)
    """

    def get(self, request, *args, **kwargs):
        try:
            return super(ReceiptView, self).get(request, *args, **kwargs)
        except MissingReceipt:
            return HttpResponseNotFound(content=force_bytes(_('Чек не найден')))
        except (KeyError, TypeError, ValueError) as exc:
            logger.error('invalid receipt format: %s', exc, exc_info=True)
            return HttpResponseNotFound(content=force_bytes(_('Чек не найден')))  # do not face 500 to user

    def get_redirect_url(self, *args, **kwargs):
        uuid = shortuuid.decode(kwargs['short_uuid'])
        receipt = get_object_or_404(Receipt, internal_uuid=uuid)

        if not receipt.content:
            logger.warning('access receipt before backend processed receipt, suspicious')
            raise MissingReceipt()

        payload = receipt.content['payload']
        receipt_dt = parse_receipt_datetime(payload['receipt_datetime'])

        return settings.RECEIPTS_OFD_URL_TEMPLATE.format(
            t='{:%Y%m%dT%H%M%S}'.format(receipt_dt),
            s=payload['total'],
            fn=payload['fn_number'],
            fd=payload['fiscal_document_number'],
            fp=payload['fiscal_document_attribute'],
            n=payload['fiscal_receipt_number'],
        )
