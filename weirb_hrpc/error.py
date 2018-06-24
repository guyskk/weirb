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
    code = 'Hrpc.Client.MethodNotFound'


class InvalidRequest(HrpcError):
    code = 'Hrpc.Client.InvalidRequest'


class InvalidParams(HrpcError):
    code = 'Hrpc.Client.InvalidParams'


class InternalError(HrpcError):
    code = 'Hrpc.Server.InternalError'


class InvalidResult(HrpcError):
    code = 'Hrpc.Server.InvalidResult'
