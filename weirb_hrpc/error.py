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

    error = None

    def __init__(self, message=None, data=None):
        if self.error is None:
            raise RuntimeError(f'{type(self).__name__} can not instantiated')
        self.message = message or self.error
        self.data = data


class MethodNotFound(HrpcError):
    error = 'Hrpc.Client.MethodNotFound'


class InvalidRequest(HrpcError):
    error = 'Hrpc.Client.InvalidRequest'


class InvalidParams(HrpcError):
    error = 'Hrpc.Client.InvalidParams'


class InternalError(HrpcError):
    error = 'Hrpc.Server.InternalError'


class InvalidResult(HrpcError):
    error = 'Hrpc.Server.InvalidResult'
