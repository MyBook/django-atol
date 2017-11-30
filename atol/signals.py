"""
Signals:

receipt_initiated:
    Called at the time of successful receipt registration in Atol

receipt_failed:
    Called if an error occurred:
    - There is not enough data to register a receipt in Atol
    - Error registering receipt
    - Error of receipt processing

receipt_received:
    Called at the moment of Atol's response on successful processing of the receipt

"""
from django.dispatch import Signal

receipt_initiated = Signal(providing_args=['receipt'])
receipt_failed = Signal(providing_args=['receipt'])
receipt_received = Signal(providing_args=['receipt'])
