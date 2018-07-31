import inspect
import json
try:
    import ujson
except ModuleNotFoundError:
    ujson = None
from http import HTTPStatus
from werkzeug.http import dump_cookie
from werkzeug.datastructures import Headers

from .server import AbstractResponse, ErrorResponse
from .helper import stream, HTTP_REDIRECT_STATUS

__all__ = ('AbstractResponse', 'ErrorResponse', 'Response',)


class ResponseCookieMixin:

    def set_cookie(self, key, value='', max_age=None, expires=None,
                   path='/', domain=None, secure=False, httponly=False):
        """Sets a cookie. The parameters are the same as in the cookie `Morsel`
        object in the Python standard library but it accepts unicode data, too.

        :param key: the key (name) of the cookie to be set.
        :param value: the value of the cookie.
        :param max_age: should be a number of seconds, or `None` (default) if
                        the cookie should last only as long as the client's
                        browser session.
        :param expires: should be a `datetime` object or UNIX timestamp.
        :param path: limits the cookie to a given path, per default it will
                     span the whole domain.
        :param domain: if you want to set a cross-domain cookie.  For example,
                       ``domain=".example.com"`` will set a cookie that is
                       readable by the domain ``www.example.com``,
                       ``foo.example.com`` etc.  Otherwise, a cookie will only
                       be readable by the domain that set it.
        :param secure: If `True`, the cookie will only be available via HTTPS
        :param httponly: disallow JavaScript to access the cookie.  This is an
                         extension to the cookie standard and probably not
                         supported by all browsers.
        """
        cookie = dump_cookie(key,
                             value=value,
                             max_age=max_age,
                             expires=expires,
                             path=path,
                             domain=domain,
                             secure=secure,
                             httponly=httponly,
                             charset='utf-8')
        self.headers.add('Set-Cookie', cookie)

    def delete_cookie(self, key, path='/', domain=None):
        """Delete a cookie.  Fails silently if key doesn't exist.

        :param key: the key (name) of the cookie to be deleted.
        :param path: if the cookie that should be deleted was limited to a
                     path, the path has to be defined here.
        :param domain: if the cookie that should be deleted was limited to a
                       domain, that domain has to be defined here.
        """
        self.set_cookie(key, expires=0, max_age=0, path=path, domain=domain)


class ResponseRedirectMixin:

    def redirect(self, location, status=302):
        if status not in HTTP_REDIRECT_STATUS:
            raise ValueError(f'{status} is not redirect status')
        self.headers['Location'] = location
        self.status = status

    @property
    def is_redirect(self):
        return self.status in HTTP_REDIRECT_STATUS


class Response(AbstractResponse, ResponseCookieMixin, ResponseRedirectMixin):
    def __init__(self, context, *, status=200, version=None, headers=None, body=None):
        super().__init__()
        self.context = context
        context.response = self
        self._status = HTTPStatus(status)
        self.version = version or 'HTTP/1.1'
        if headers is None:
            self.headers = Headers()
        else:
            self.headers = Headers(headers)
        self.body = body

    @property
    def status(self):
        return int(self._status)

    @status.setter
    def status(self, value):
        self._status = HTTPStatus(value)

    @property
    def status_text(self):
        return self._status.phrase

    @property
    def body(self):
        return self._body

    @body.setter
    def body(self, value):
        if value is None:
            self._body = stream(b'')
            self.content_length = 0
        elif isinstance(value, bytes):
            self._body = stream(value)
            self.content_length = len(value)
        elif isinstance(value, str):
            value = value.encode('utf-8')
            self._body = stream(value)
            self.content_length = len(value)
        elif inspect.isasyncgen(value):
            self._body = value
        else:
            msg = (f'response body should be bytes, str or async generator, '
                   f'type {type(value).__name__} is not supported')
            raise ValueError(msg)

    def json(self, value):
        sort_keys = self.context.config.json_sort_keys
        indent = None
        if self.context.config.json_pretty:
            indent = 4
        if self.context.config.json_ujson_enable:
            dumps = ujson.dumps
        else:
            dumps = json.dumps
        text = dumps(
            value, ensure_ascii=False, indent=indent, sort_keys=sort_keys)
        self.body = text.encode('utf-8')
        self.headers['Content-Type'] = 'application/json;charset=utf-8'

    @property
    def chunked(self):
        return self.headers.get('Transfer-Encoding', '').lower() == 'chunked'

    @chunked.setter
    def chunked(self, value):
        if value:
            self.headers['Transfer-Encoding'] = 'chunked'
        else:
            self.headers.pop('Transfer-Encoding', None)

    @property
    def content_length(self):
        length = self.headers.get('Content-Length', '')
        if not length:
            return None
        return int(length)

    @content_length.setter
    def content_length(self, value):
        if value is None:
            self.headers.pop('Content-Length', None)
        else:
            self.headers['Content-Length'] = value

    @property
    def keep_alive(self):
        connection = self.headers.get('Connection', '').lower()
        if connection == 'keep-alive':
            return True
        elif connection == 'close':
            return False
        return None

    @keep_alive.setter
    def keep_alive(self, value):
        if value is None:
            self.headers.pop('Connection', None)
        elif value:
            self.headers['Connection'] = 'keep-alive'
        else:
            self.headers['Connection'] = 'close'

    def __repr__(self):
        return f'<{type(self).__name__} {self.status} {self.status_text}>'
