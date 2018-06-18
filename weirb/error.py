from http import HTTPStatus

__all__ = ('WeirbError', 'ConfigError', 'HttpError',)


class WeirbError(Exception):
    """Base exception of weirb"""


class ConfigError(WeirbError):
    """Config Error"""


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
        return f'{type(self).__name__}({self.status}, {self.message!r})'

    def __str__(self):
        return f'{self.status} {self.phrase}: {self.message}'


HTTP_ERRORS = {}


def _init_http_errors():
    g = globals()
    _all = list(g['__all__'])
    for s in HTTPStatus.__members__.values():
        if s < 400:
            continue
        classname = s.phrase.replace(' ', '')
        error_class = type(classname, (HttpError,), {
            'status': int(s),
            'phrase': s.phrase,
            '__doc__': s.description,
        })
        HTTP_ERRORS[int(s)] = error_class
        g[classname] = error_class
        _all.append(classname)
    g['__all__'] = tuple(_all)


_init_http_errors()
del _init_http_errors
