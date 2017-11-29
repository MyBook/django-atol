import logging
import datetime
from dateutil.parser import parse as parse_date

logger = logging.getLogger(__name__)


def parse_receipt_datetime(date_str):
    try:
        return datetime.datetime.strptime(date_str, '%d.%m.%Y %H:%M:%S')
    except Exception:
        logger.warning('unexpected date format in receipt, %s', date_str)
        return parse_date(date_str)
