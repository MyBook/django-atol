Changelog
---------

1.3.0 (2018-11-28)
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
