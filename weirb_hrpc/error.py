class WeirbHrpcError(Exception):
    """Base class of WeirbHrpc Errors"""


class DependencyError(WeirbHrpcError):
    """Dependency Error"""


class ConfigError(WeirbHrpcError):
    """Config Error"""


class AppNotFound(WeirbHrpcError):
    """App Not Fount"""


class HrpcError(WeirbHrpcError):
    """Base class for HRPC Errors"""

    code = None

    def __init__(self, message=None, data=None):
        if self.code is None:
            raise RuntimeError(f'{type(self).__name__} can not instantiated')
        self.message = message or self.code
        self.data = data

    def __repr__(self):
        return f'<{type(self).__name__} {self.code}>'


class MethodNotFound(HrpcError):
    """Method not found in relevant service"""
    code = 'Hrpc.Client.MethodNotFound'


class InvalidRequest(HrpcError):
    """Request format invalid"""
    code = 'Hrpc.Client.InvalidRequest'


class InvalidParams(HrpcError):
    """Request params invalid"""
    code = 'Hrpc.Client.InvalidParams'


class InternalError(HrpcError):
    """Service internal error"""
    code = 'Hrpc.Server.InternalError'


class InvalidResult(HrpcError):
    """Service response an invalid result"""
    code = 'Hrpc.Server.InvalidResult'


BUILTIN_HRPC_ERRORS = [
    MethodNotFound,
    InvalidRequest,
    InvalidParams,
    InternalError,
    InvalidResult,
]
