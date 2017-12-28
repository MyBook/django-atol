====
ATOL
====

Application for integrating Django and  https://online.atol.ru/

.. image:: https://img.shields.io/badge/python-3.5,%203.6-blue.svg
    :target: https://pypi.python.org/pypi/django-atol/
.. image:: https://travis-ci.org/MyBook/django-atol.svg?branch=master
    :target: https://travis-ci.org/MyBook/django-atol
.. image:: https://codecov.io/gh/MyBook/django-atol/branch/master/graph/badge.svg
    :target: https://codecov.io/gh/MyBook/django-atol
.. image:: https://img.shields.io/badge/docs-v3-yellow.svg
    :target: https://t.me/atolonline
    
    

Important limitations:

    * Python 3.5+
    * Support Django 1.11+
    * PostgreSQL ≥ 9.4 (JSONB field)
    * only 1 purchase is supported in receipt (1 product)
    * only v3 protocol version is supported

Quick start
-----------

1. Add ``atol`` to your INSTALLED_APPS setting like this::

    INSTALLED_APPS = [
        ...
        'atol',
    ]

2. Add ``atol`` settings like this::

    RECEIPTS_ATOL_LOGIN = 'login'
    RECEIPTS_ATOL_PASSWORD = 'secret'
    RECEIPTS_ATOL_GROUP_CODE = 'ATOL-ProdTest-1'
    RECEIPTS_ATOL_TAX_NAME = 'vat18'
    RECEIPTS_ATOL_INN = '112233445573'
    RECEIPTS_ATOL_CALLBACK_URL = None
    RECEIPTS_ATOL_PAYMENT_ADDRESS = 'г. Москва, ул. Оранжевая, д.22 к.11'
    RECEIPTS_OFD_URL_TEMPLATE = u'https://lk.platformaofd.ru/web/noauth/cheque?fn={fn}&fp={fp}'

3. Add celery-beat tasks to CELERYBEAT_SCHEDULE settings like this::

    CELERYBEAT_SCHEDULE = {
        ...
        'atol_retry_created_receipts': {
            'task': 'atol_retry_created_receipts',
            'schedule': crontab(minute=25)
        },
        'atol_retry_initiated_receipts': {
            'task': 'atol_retry_initiated_receipts',
            'schedule': crontab(minute=35)
        }
    }

4. Include the ``atol`` URLconf in your project urls.py like this::

    from atol.views import ReceiptView

    url(r'^r/(?P<short_uuid>[\w]+)/$', ReceiptView.as_view(), name='receipt')

5. Run ``python manage.py migrate atol`` to create the receipt model.

6. Add receipt field to your payment model::

    from atol.models import Receipt

    receipt = models.OneToOneField(Receipt, verbose_name=_('Чек'), blank=True, null=True, on_delete=models.SET_NULL)

7. Add the mechanics of calling a receipt creation after a successful payment. For example, this can be done through a signal that will be called upon successful payment::

    # <your_app>/signals.py

    payment_accepted = Signal(providing_args=['payment'])

    # <your_app>/providers/googleplay.py

    def process_payment(payment)

        ...

        payment_accepted.send(sender='google-play', payment=payment)

    # <your_app>/receivers.py

    @receiver(payment_accepted)
    @transaction.atomic
    def init_payment_receipt(sender, payment, **kwargs):

        ...

        receipt = Receipt.objects.create(
            user_email=payment.user.email,
            purchase_price=payment.amount
        )
        payment.receipt = receipt
        payment.save(update_fields=['receipt'])
        transaction.on_commit(
            lambda: atol_create_receipt.apply_async(args=(receipt.id,), fallback_sync=True)
        )

Run tests
---------

    python setup.py test
