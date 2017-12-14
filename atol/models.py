import logging
from uuid import uuid4

import shortuuid
from django.contrib.postgres.fields import JSONField
from django.db import models, transaction
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _

try:
    from django.urls import reverse
except ImportError:
    from django.core.urlresolvers import reverse
from model_utils import Choices

from atol.signals import receipt_failed, receipt_initiated, receipt_received
from atol.exceptions import NoEmailAndPhoneError

logger = logging.getLogger(__name__)


ReceiptStatus = Choices(
    ('created', _('Ожидает инициации в системе оператора')),
    ('initiated', _('Иницирован в системе оператора')),
    ('retried', _('Повторно иницирован в системе оператора')),
    ('received', _('Получен от оператора')),
    ('no_email_phone', _('Отсутствует email/phone')),
    ('failed', _('Ошибка')),
)


class Receipt(models.Model):
    internal_uuid = models.UUIDField(default=uuid4, unique=True, editable=False)

    created_at = models.DateTimeField(_('Дата создания чека'), auto_now_add=True, editable=False)
    initiated_at = models.DateTimeField(_('Дата инициализации чека в системе оператора'), blank=True, null=True)
    retried_at = models.DateTimeField(_('Дата повторной инициализации чека в системе оператора'),
                                      blank=True, null=True)
    received_at = models.DateTimeField(_('Дата получения чека от оператора'), blank=True, null=True)
    failed_at = models.DateTimeField(_('Дата ошибки'), blank=True, null=True)

    status = models.CharField(_('Статус чека'), max_length=16, choices=ReceiptStatus,
                              default=ReceiptStatus.created)
    uuid = models.TextField(_('Идентификатор чека'), null=True, editable=False,
                            help_text=_('Идентификатор чека платежа в системе оператора'))
    content = JSONField(_('Содержимое чека'), null=True, editable=False)

    user_email = models.CharField(_('Email пользователя'), max_length=254, null=True)
    user_phone = models.CharField(_('Телефон пользователя'), max_length=32, null=True)
    purchase_price = models.DecimalField(_('Цена покупки'), max_digits=8, decimal_places=2, null=True)
    purchase_name = models.TextField(_('Наименование покупки'), null=True)

    class Meta:
        verbose_name = _('Чек Атола')
        verbose_name_plural = _('Чеки Атола')
        ordering = ['id']

    @cached_property
    def ofd_link(self):
        """Return the receipt url"""
        return reverse('receipt', kwargs={'short_uuid': shortuuid.encode(self.internal_uuid)})

    @transaction.atomic()
    def declare_failed(self, status=None):
        logger.warning('declaring receipt %s as failed', self.id)
        self.status = status or ReceiptStatus.failed
        self.failed_at = timezone.now()
        self.save(update_fields=['status', 'failed_at'])
        receipt_failed.send(sender=None, receipt=self)

    def initiate(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
        update_fields = list(kwargs.keys())

        now = timezone.now()
        if self.status == ReceiptStatus.retried:
            self.retried_at = now
            update_fields += ['retried_at']
        else:
            self.initiated_at = now
            self.status = ReceiptStatus.initiated
            update_fields += ['initiated_at', 'status']

        self.save(update_fields=update_fields)
        receipt_initiated.send(sender=None, receipt=self)

    def receive(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
        self.status = ReceiptStatus.received
        self.received_at = timezone.now()
        self.save(update_fields=list(kwargs.keys()) + ['status', 'received_at'])
        receipt_received.send(sender=None, receipt=self)

    def get_params(self):
        params = {
            'timestamp': self.created_at.isoformat(),
            'transaction_uuid': str(self.internal_uuid),
            'purchase_price': float(self.purchase_price),
            'purchase_name': self.purchase_name or 'Оплата подписки'
        }
        if self.user_email:
            params['user_email'] = self.user_email
        elif self.user_phone:
            params['user_phone'] = self.user_phone  # don't strip leading plus nor non-russian country code
        else:
            raise NoEmailAndPhoneError

        return params
