from django.dispatch import Signal

receipt_initiated = Signal(providing_args=['receipt'])
receipt_failed = Signal(providing_args=['receipt'])
receipt_received = Signal(providing_args=['receipt'])
