====
ATOL
====

Description

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

3. Include the ``atol`` URLconf in your project urls.py like this::

    from atol.views import ReceiptView

    url(r'^r/(?P<short_uuid>[\w]+)/$', ReceiptView.as_view(), name='receipt')

4. Run ``python manage.py migrate atol`` to create the receipt model.

5. Add ``payment_accept`` signal and ``init_receipt`` receiver::

    payment_accepted = Signal(providing_args=['payment'])

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
