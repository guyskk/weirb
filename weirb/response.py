from http import HTTPStatus
from typing import List, Tuple, AsyncIterable, Any
from zope.interface import Interface, Attribute, implementer
from werkzeug.http import dump_cookie
from werkzeug.datastructures import Headers

from .error import HttpError
from .helper import stream
from .const import HTTP_REDIRECT_STATUS


class IResponse(Interface):
    status: int = Attribute('Status code')
    status_text: str = Attribute('Status text')
    version: str = Attribute('HTTP version')
    headers: List[Tuple[str, Any]] = Attribute('Response headers')
    body: AsyncIterable = Attribute('Response body')
    chunked: bool = Attribute('Is chunked or not')
    keep_alive: bool = Attribute('Is keep alive or not')


@implementer(IResponse)
class AbstractResponse:
    """Abstract Response"""


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
    def __init__(self, status=200, *, version=None, headers=None, body=None):
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
        else:
            self._body = value

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
