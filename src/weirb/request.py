import json
from io import BytesIO
from urllib.parse import parse_qsl, urlparse

from werkzeug.utils import cached_property
from werkzeug.formparser import parse_form_data
from werkzeug.useragents import UserAgent
from werkzeug.http import (
    parse_accept_header,
    parse_authorization_header,
    parse_options_header,
    parse_cookie,
)
from werkzeug.datastructures import (
    Headers,
    ImmutableMultiDict,
    MIMEAccept,
    CharsetAccept,
    LanguageAccept,
)

from .server import RawRequest
from .error import BadRequest


class RequestUrlMixin:

    @cached_property
    def _parsed_url(self):
        return urlparse(self.url)

    @cached_property
    def path(self):
        return self._parsed_url.path

    @cached_property
    def query_string(self):
        return self._parsed_url.query

    @cached_property
    def query(self):
        return ImmutableMultiDict(parse_qsl(self.query_string))


class RequestHeadersMixin:

    @cached_property
    def content_type(self):
        return self.headers.get('Content-Type', '')

    @cached_property
    def _parsed_mimetype(self):
        name, options = parse_options_header(self.content_type)
        return name, options

    @cached_property
    def mimetype(self):
        """Like content_type but without parameters (eg, without charset, type etc.).

        For example if the content type is text/html; charset=utf-8
        the mimetype would be 'text/html'.
        """
        return self._parsed_mimetype[0].lower()

    @cached_property
    def mimetype_params(self):
        return self._parsed_mimetype[1]

    @cached_property
    def is_xhr(self):
        """True if the request was triggered via a JavaScript XMLHttpRequest.

        This only works with libraries that support the `X-Requested-With`
        header and set it to "XMLHttpRequest".  Libraries that do that are
        prototype, jQuery and Mochikit and probably some more.
        """
        return self.headers.get('X-Requested-With', '').lower() == 'xmlhttprequest'

    @cached_property
    def is_json(self):
        """Indicates if this request is JSON or not.  By default a request
        is considered to include JSON data if the mimetype is
        :mimetype:`application/json` or :mimetype:`application/*+json`.

        .. versionadded:: 0.11
        """
        mt = self.mimetype
        if mt == 'application/json':
            return True
        if mt.startswith('application/') and mt.endswith('+json'):
            return True
        return False

    @cached_property
    def is_form(self):
        """Indicates if this request is Form or not."""
        mt = self.mimetype
        if mt == 'application/x-www-form-urlencoded':
            return True
        if mt == 'multipart/form-data':
            return True
        return False

    @cached_property
    def cookies(self):
        """A :class:`dict` with the contents of all cookies transmitted with
        the request."""
        return parse_cookie(self.headers.get('Cookie', ''))

    @cached_property
    def user_agent(self):
        return UserAgent(self.headers.get('User-Agent', ''))

    @cached_property
    def authorization(self):
        """The `Authorization` object in parsed form."""
        header = self.headers.get('Authorization', '')
        return parse_authorization_header(header)

    def _parse_accept(self, key, cls):
        return parse_accept_header(self.headers.get(key, ''), MIMEAccept)

    @cached_property
    def accept_mimetypes(self):
        """List of mimetypes this client supports as
        :class:`~werkzeug.datastructures.MIMEAccept` object.
        """
        return self._parse_accept('Accept', MIMEAccept)

    @cached_property
    def accept_charsets(self):
        """List of charsets this client supports as
        :class:`~werkzeug.datastructures.CharsetAccept` object.
        """
        return self._parse_accept('Accept-Charset', CharsetAccept)

    @cached_property
    def accept_encodings(self):
        """List of encodings this client accepts.  Encodings in a HTTP term
        are compression encodings such as gzip.  For charsets have a look at
        :attr:`accept_charset`.
        """
        return self._parse_accept('Accept-Encoding')

    @cached_property
    def accept_languages(self):
        """List of languages this client accepts as
        :class:`~werkzeug.datastructures.LanguageAccept` object.

        .. versionchanged 0.5
           In previous versions this was a regular
           :class:`~werkzeug.datastructures.Accept` object.
        """
        return self._parse_accept('Accept-Language', LanguageAccept)


_NOT_READ = object()


class RequestBodyMixin:

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._content = _NOT_READ
        self._text = _NOT_READ
        self._json = _NOT_READ
        self._form = _NOT_READ
        self._files = _NOT_READ

    async def content(self):
        if self._content is _NOT_READ:
            chunks = []
            async for chunk in self.body:
                chunks.append(chunk)
            self._content = b''.join(chunks)
        return self._content

    async def text(self):
        if self._text is _NOT_READ:
            charset = self.mimetype_params.get('charset', 'UTF-8')
            content = await self.content()
            try:
                self._text = content.decode(charset)
            except UnicodeDecodeError as ex:
                msg = 'Bad request body encoding or incorrect charset'
                raise BadRequest(msg) from ex
        return self._text

    async def json(self):
        if self._json is _NOT_READ:
            if not self.is_json:
                msg = ('The request has no JSON data, or missing JSON '
                       'content-type header, eg: application/json')
                raise BadRequest(msg)
            content = await self.content()
            try:
                self._json = json.loads(content)
            except json.JSONDecodeError as ex:
                raise BadRequest('Invalid JSON') from ex
        return self._json

    async def form(self):
        if self._form is _NOT_READ:
            await self._parse_form_data()
        return self._form

    async def files(self):
        if self._files is _NOT_READ:
            await self._parse_form_data()
        return self._files

    async def _parse_form_data(self):
        if not self.is_form:
            msg = ('The request no form data, or missing form '
                   'content-type header, eg: application/x-www-form-urlencoded')
            raise BadRequest(msg)
        if not self.body or self.method not in {'POST', 'PUT', 'PATCH'}:
            self._form = self._files = None
            return
        content = await self.content()
        environ = {
            'wsgi.input': BytesIO(content),
            'CONTENT_LENGTH': str(len(content)),
            'CONTENT_TYPE': self.content_type,
            'REQUEST_METHOD': self.method
        }
        __, self._form, self._files = parse_form_data(environ)


class Request(RequestUrlMixin, RequestHeadersMixin, RequestBodyMixin):
    """HTTP Request"""

    def __init__(self, context, raw: RawRequest):
        super().__init__()
        self.context = context
        context.request = self
        self.raw = raw
        self.path_params = {}
        self._xheaders = context.config.xheaders
        self._body_readed = False

    @property
    def method(self):
        return self.raw.method

    @property
    def url(self):
        return self.raw.url

    @property
    def version(self):
        return self.raw.version

    @cached_property
    def headers(self):
        return Headers(self.raw.headers)

    @property
    def body(self):
        return self.raw.body

    @cached_property
    def remote_ip(self):
        if not self._xheaders:
            return self.raw.remote_ip
        return (
            self.headers.get('X-Real-Ip') or
            self.headers.get('X-Forwarded-For') or
            self.raw.remote_ip
        )

    @cached_property
    def protocol(self):
        if not self._xheaders:
            return self.raw.protocol
        return self.headers.get('X-Scheme') or self.raw.protocol

    @property
    def keep_alive(self):
        return self.raw.keep_alive

    @cached_property
    def host(self):
        return self.headers.get('Host', '')

    @cached_property
    def is_secure(self):
        return self.protocol == 'https'

    def __repr__(self):
        return f'<{type(self).__name__} {self.method} {self.path}>'
