class NoEmailAndPhoneError(Exception):
    pass


class MissingReceipt(Exception):
    pass


class AtolException(Exception):
    pass


class AtolPrepRequestException(AtolException):
    """Raised client side due to various validation errors prior to a request"""
    pass


class AtolRequestException(AtolException):
    """Raised when atol request fails in the middle, or the endpoint returns unexpected response"""
    pass


class AtolClientRequestException(AtolException):
    """Raised when received an expected error code from atol"""

    def __init__(self, *args, **kwargs):
        self.response = kwargs.pop('response', None)
        self.response_data = kwargs.pop('response_data')
        self.error_data = kwargs.pop('error_data')
        super(AtolClientRequestException, self).__init__(*args, **kwargs)


class AtolAuthTokenException(AtolException):
    """Raised when atol api endpoint returns 401"""
    pass


class AtolUnrecoverableError(AtolException):
    """Raised when atol responds with an error
       that is generally unrecoverable and requires manual maintenance"""
    pass


class AtolRecoverableError(AtolException):
    """Raised when atol responds with an error
       that is normally recoverable and can be retried with an extra request"""
    pass


class AtolReceiptNotProcessed(AtolException):
    """Raised when atol responds with an error
        that is requires a repeated request to register a check

        Call if:
        1. The number of KKT in the group does not correspond to the speed of receipt of checks.
            It is necessary to connect additional KKT or reduce the speed of receipt of checks.
        2. All cash desks of the group are off or inactive. Please contact your administrator.
    """
    pass
