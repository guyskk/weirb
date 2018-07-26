import json
import inspect
import logging
from urllib.parse import urlencode

from werkzeug.utils import cached_property
from werkzeug.http import parse_authorization_header, parse_options_header, parse_cookie
from werkzeug.datastructures import Headers
from newio import run

from .helper import shorten_text, stream
from .request import RawRequest
from .error import HttpError, InternalServerError
from .response import ErrorResponse

LOG = logging.getLogger(__name__)


def _format_headers(headers):
    headers = [f"{k}: {v}" for k, v in headers.items()]
    return "\n".join(headers)


class ClientRequest(RawRequest):
    def __init__(self, path, *, method, query=None, body=None, headers=None):
        if query:
            path = path + "?" + urlencode(query)
        headers = ClientHeaders(headers or {})
        if not inspect.isasyncgen(body):
            if body is None:
                body = b""
            elif isinstance(body, bytes):
                body = body
            elif isinstance(body, str):
                body = body.encode("utf-8")
            else:
                msg = (
                    f"request body should be bytes, str or async generator, "
                    f"type {type(body).__name__} is not supported"
                )
                raise ValueError(msg)
            headers["Content-Length"] = str(len(body))
            body = stream(body)
        super().__init__(
            method=method,
            url=path,
            version="HTTP/1.1",
            headers=headers,
            body=body,
            protocol="http",
            remote_ip="127.0.0.1",
            keep_alive=False,
        )


class ClientResponse:
    def __init__(self, status, status_text, headers, content):
        self.status = status
        self.status_text = status_text
        self.headers = ClientHeaders(headers or {})
        self.content = content
        self.__repr_text = self.__repr()

    @cached_property
    def ok(self):
        return 200 <= self.status <= 399

    @cached_property
    def error(self):
        e = self.headers.get("Service-Error", None)
        if e is None and not self.ok:
            e = self.status
        return e

    @cached_property
    def content_type(self):
        return self.headers.get("Content-Type", "")

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
    def is_json(self):
        mt = self.mimetype
        if mt == "application/json":
            return True
        if mt.startswith("application/") and mt.endswith("+json"):
            return True
        return False

    @cached_property
    def cookies(self):
        """A :class:`dict` with the contents of all cookies transmitted with
        the request."""
        return parse_cookie(self.headers.get("Cookie", ""))

    @cached_property
    def authorization(self):
        """The `Authorization` object in parsed form."""
        header = self.headers.get("Authorization", "")
        return parse_authorization_header(header)

    @cached_property
    def text(self):
        return self.content.decode("utf-8")

    @cached_property
    def json(self):
        if not self.is_json:
            msg = ('The response has no JSON data, or missing JSON '
                   'content-type header, eg: application/json')
            raise ValueError(msg)
        return json.loads(self.text)

    def __repr(self):
        status_line = f"{self.status} {self.status_text}"
        headers = _format_headers(self.headers)
        if self.is_json:
            try:
                data = self.json
            except (json.JSONDecodeError, UnicodeDecodeError) as ex:
                text = f"Failed to decode JSON content: {ex}"
            else:
                text = json.dumps(data, ensure_ascii=False, indent=4)
        else:
            try:
                text = self.text
            except UnicodeDecodeError as ex:
                text = f"Failed to decode response content: {ex}"
            text = shorten_text(text, 80 * 3)
        text = text.strip()
        ret = "\n" + status_line
        if headers:
            ret += "\n" + headers + "\n"
        if text:
            ret += "\n" + text + "\n"
        return ret

    def __repr__(self):
        return self.__repr_text


class ClientHeaders(Headers):
    def __repr__(self):
        if not self:
            return "\n    No Headers\n"
        headers = [f"    {k}: {v}" for k, v in self.items()]
        headers = "\n".join(headers)
        return f"\n{headers}\n"


class Client:
    def __init__(self, app, headers=None):
        self.app = app
        self.headers = ClientHeaders(headers or {})

    async def __request(self, path, *, method, query=None, body=None, headers=None):
        path = "/" + path.lstrip("/")
        request_headers = self.headers.copy()
        if headers:
            for k, v in Headers(headers).items():
                request_headers[k] = v
        raw_request = ClientRequest(
            path, method=method, query=query, body=body, headers=request_headers
        )
        async with self.app.context() as ctx:
            try:
                response = await ctx(raw_request)
            except HttpError as ex:
                response = ErrorResponse(ex)
            except Exception as ex:
                LOG.error("Error raised when handle request:", exc_info=ex)
                response = ErrorResponse(InternalServerError(str(ex)))
            return await self.__read_response(response)

    def __request_body(self, body):
        if body is None:
            return stream(b"")
        return stream(body)

    async def __read_response(self, response):
        content = []
        async for chunk in response.body:
            content.append(chunk)
        content = b"".join(content)
        return ClientResponse(
            response.status, response.status_text, response.headers, content
        )

    def request(self, path, *, method, query=None, body=None, headers=None):
        return run(
            self.__request(path, method=method, query=query, body=body, headers=headers)
        )

    def __data_request(self, path, *, method, query=None, data=None, headers=None):
        if headers:
            headers = Headers(headers)
        else:
            headers = Headers()
        if data is not None:
            headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
            body = urlencode(data).encode("utf-8")
        else:
            body = None
        return self.request(
            path, method="POST", query=query, body=body, headers=headers
        )

    def post(self, path, **kwargs):
        return self.__data_request(path, method="POST", **kwargs)

    def put(self, path, **kwargs):
        return self.__data_request(path, method="PUT", **kwargs)

    def patch(self, path, **kwargs):
        return self.__data_request(path, method="PATCH", **kwargs)

    def get(self, path, *, query=None, headers=None):
        return self.request(path, method="GET", query=query, headers=headers)

    def delete(self, path, *, query=None, headers=None):
        return self.request(path, method="DELETE", query=query, headers=headers)

    def head(self, path, *, query=None, headers=None):
        return self.request(path, method="HEAD", query=query, headers=headers)

    def options(self, path, *, query=None, headers=None):
        return self.request(path, method="OPTIONS", query=query, headers=headers)

    def call(self, path, **params):
        headers = {"Content-Type": "application/json;charset=utf-8"}
        text = json.dumps(params, ensure_ascii=False, indent=4)
        return self.request(path, method="POST", body=text, headers=headers)
