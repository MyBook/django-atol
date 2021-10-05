Changelog
---------

1.3.4 (2021-10-05)
------------------
* Fix bug with payment_method parameter

1.3.3 (2021-06-28)
------------------
* Add task for sell_refund request

1.3.2 (2020-08-17)
------------------
* Upgrade shortuuid 0.5.0 -> 1.0.1

1.3.1 (2018-12-19)
------------------
* Sell method: do not insert empty email or phone

1.3.0 (2018-12-19)
------------------
* Support Atol protocol v4 (FFD 1.05)

1.2.2 (2018-10-08)
------------------
* Change maximum retry counts for task `atol_receive_receipt_report`. Now its awaiting report for 29 hours.

* Changed `atol_retry_created_receipts` and `atol_retry_initiated_receipts` tasks retry period.
  Now it will retry receipts from day before yesterday

1.2.1 (2018-05-22)
------------------
* AtolAPI.base_url specifying in settings

1.2.0 (2017-12-14)
------------------
* Support retried not processed receipt

1.1.0 (2017-12-13)
------------------
* Django 2.0 support

1.0.0 (2017-12-01)
------------------
* Initial release
