from http import HTTPStatus

__all__ = ("WeirbError", "ConfigError", "HttpError")


class WeirbError(Exception):
    """Base exception of weirb"""


class ConfigError(WeirbError):
    """Config Error"""


class DependencyError(WeirbError):
    """Dependency Error"""


class AppNotFound(WeirbError):
    """App Not Fount"""


class HttpError(WeirbError):
    """Base class of http errors"""

    status = phrase = message = None

    def __init__(self, message=None):
        if self.status is None or self.phrase is None:
            msg = f"{type(self).__name__} can not be instantiated"
            raise RuntimeError(msg)
        s = HTTPStatus(self.status)
        self.message = message or s.description

    def __repr__(self):
        return f"{type(self).__name__}({self.status}, {self.message!r})"

    def __str__(self):
        return f"{self.status} {self.phrase}: {self.message}"


class HttpRedirect(HttpError):
    """Http Redirect, it's not real HttpError"""

    def __init__(self, location, status):
        self.location = location
        self.status = status
        s = HTTPStatus(self.status)
        self.phrase = s.phrase
        self.message = s.description


HTTP_ERRORS = {}


def _init_http_errors():
    g = globals()
    _all = list(g["__all__"])
    for s in HTTPStatus.__members__.values():
        if s < 400:
            continue
        classname = s.phrase.replace(" ", "")
        error_class = type(
            classname,
            (HttpError,),
            {"status": int(s), "phrase": s.phrase, "__doc__": s.description},
        )
        HTTP_ERRORS[int(s)] = error_class
        g[classname] = error_class
        _all.append(classname)
    g["__all__"] = tuple(_all)


_init_http_errors()
del _init_http_errors


class ServiceError(HttpError):
    """Base class for Service Errors"""

    status = code = None

    def __init__(self, message=None, data=None):
        if self.status is None or self.code is None:
            raise RuntimeError(f"{type(self).__name__} can not instantiated")
        s = HTTPStatus(self.status)
        self.phrase = s.phrase
        self.message = message or type(self).__doc__
        self.data = data

    def __repr__(self):
        return f"<{type(self).__name__} {self.status}:{self.code}>"


class ServiceInvalidParams(ServiceError):
    """Request params invalid"""

    status = 400
    code = "Service.InvalidParams"


BUILTIN_SERVICE_ERRORS = frozenset([ServiceInvalidParams])
