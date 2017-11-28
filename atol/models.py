import logging
import shortuuid
from uuid import uuid4

from django.contrib.postgres.fields import JSONField
from django.core.urlresolvers import reverse
from django.db import models, transaction
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from model_utils import Choices

from atol.signals import receipt_failed, receipt_initiated, receipt_received

logger = logging.getLogger('atol')


ReceiptStatus = Choices(
    ('created', 'Ожидает инициации в системе оператора'),
    ('initiated', 'Иницирован в системе оператора'),
    ('received', 'Получен от оператора'),
    ('no_email_phone', 'Отсутствует email/phone'),
    ('failed', 'Ошибка'),
)


class Receipt(models.Model):
    internal_uuid = models.UUIDField(default=uuid4, unique=True, editable=False)

    created_at = models.DateTimeField(_('Дата создания чека'), auto_now_add=True, editable=False)
    initiated_at = models.DateTimeField(_('Дата инициализации чека в системе оператора'), blank=True, null=True)
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
        self.status = ReceiptStatus.initiated
        self.initiated_at = timezone.now()
        self.save(update_fields=list(kwargs.keys()) + ['status', 'initiated_at'])
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
        if self.user_phone:
            params['user_phone'] = self.user_phone  # don't strip leading plus nor non-russian country code
        return params
