from datetime import datetime
from atol.utils import parse_receipt_datetime


def test_parse_receipt_datetime():
    assert parse_receipt_datetime('13.12.2017 18:55:19') == datetime(2017, 12, 13, 18, 55, 19)
    assert parse_receipt_datetime('2017.12.13') == datetime(2017, 12, 13, 0, 0)
