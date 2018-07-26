import logging
from urllib.parse import unquote

import httptools
from newio import timeout_after

from ..error import (
    BadRequest,
    RequestHeaderFieldsTooLarge,
    RequestEntityTooLarge,
    LengthRequired,
    RequestTimeout,
)
from .request import RawRequest

LOG = logging.getLogger(__name__)


class RequestParser:

    def __init__(self,
                 cli_sock, cli_addr,
                 header_timeout,
                 body_timeout,
                 keep_alive_timeout,
                 max_header_size,
                 max_body_size,
                 header_buffer_size,
                 body_buffer_size,
                 ):
        self.cli_sock = cli_sock
        self.cli_addr = cli_addr
        self.header_timeout = header_timeout
        self.body_timeout = body_timeout
        self.keep_alive_timeout = keep_alive_timeout
        self.max_header_size = max_header_size
        self.max_body_size = max_body_size
        self.max_request_size = max_header_size + max_body_size
        self.header_buffer_size = header_buffer_size
        self.body_buffer_size = body_buffer_size

        # public attrs
        self.method = None
        self.url = None
        self.version = None
        self.headers = []
        self.remote_ip = None
        self.protocol = None
        self.keep_alive = False

        # helper attrs
        self._address = '{}:{}'.format(*self.cli_addr)

        # temp attrs
        self._parser = httptools.HttpRequestParser(self)
        self._buffer_size = self.header_buffer_size
        self._started = False
        self._headers_completed = False
        self._completed = False
        self._url = b''
        self._header_name = b''
        self._body_chunks = []
        self._readed_size = 0

    # ========= httptools callbacks ========
    def on_message_begin(self):
        self._started = True

    def on_url(self, url: bytes):
        self._url += url

    def on_header(self, name: bytes, value: bytes or None):
        self._header_name += name
        if value is not None:
            self.headers.append((self._header_name.decode(), value.decode()))
            self._header_name = b''

    def on_headers_complete(self):
        self.method = self._parser.get_method().decode().upper()
        self.url = unquote(self._url.decode())
        self.version = self._parser.get_http_version()
        self.keep_alive = self._parser.should_keep_alive()
        if 'Content-Length' in self.headers:
            self._content_length = int(self.headers['Content-Length'])
        self.protocol = 'http'
        self.remote_ip = self.cli_addr[0]
        self._headers_completed = True

    def on_body(self, body: bytes):
        self._body_chunks.append(body)

    def on_message_complete(self):
        self._completed = True
    # ========= end httptools callbacks ========

    def _get_content_length(self):
        for name, value in self.headers:
            if name.lower() == 'content-length':
                return int(value)
        raise LengthRequired()

    def _feed(self, data: bytes):
        self._readed_size += len(data)
        return self._parser.feed_data(data)

    async def _recv(self):
        return await self.cli_sock.recv(self._buffer_size)

    def _take_body_chunks(self):
        ret = b''.join(self._body_chunks)
        self._body_chunks.clear()
        return ret

    async def _body_stream(self):
        """
        Read request body

        Raises:
            BadRequest: request body invalid or incomplete
            RequestTimeout: read request body timeout
        """
        self._buffer_size = self.body_buffer_size
        if self._body_chunks:
            yield self._take_body_chunks()
        if self._completed:
            return
        async with timeout_after(self.body_timeout) as is_timeout:
            try:
                while not self._completed:
                    chunk = await self._recv()
                    self._feed(chunk)
                    if self._body_chunks:
                        yield self._take_body_chunks()
                    if not chunk:
                        break
            except httptools.HttpParserError as ex:
                msg = 'Invalid request body from %s'
                LOG.debug(msg, self._address, exc_info=True)
                raise BadRequest('Invalid request body') from ex
        if is_timeout:
            raise RequestTimeout()
        if not self._completed:
            LOG.debug('Incomplete request body from %s', self._address)
            raise BadRequest('Incomplete request body')

    async def parse(self):
        """Parse http request

        Returns:
            Request object, or None if no data received
        Raises:
            BadRequest: request headers invalid or incomplete
            RequestHeaderFieldsTooLarge: request headers too large
            RequestTimeout: read request headers timeout
            RequestEntityTooLarge: request content-length too large
        """
        # browsers may preconnect but didn't send request immediately
        # keep-alive connection has similar behaviors
        first_chunk = b''
        async with timeout_after(self.keep_alive_timeout):
            first_chunk = await self._recv()
        if not first_chunk:
            return None

        # read request headers
        try:
            self._feed(first_chunk)
            async with timeout_after(self.header_timeout) as is_timeout:
                while not self._headers_completed:
                    if self._readed_size > self.max_header_size:
                        raise RequestHeaderFieldsTooLarge()
                    chunk = await self._recv()
                    self._feed(chunk)
                    if not chunk:
                        break
        except httptools.HttpParserError as ex:
            msg = 'Invalid request headers from %s'
            LOG.debug(msg, self._address, exc_info=True)
            raise BadRequest('Invalid request headers') from ex
        if is_timeout:
            raise RequestTimeout()
        if not self._headers_completed:
            LOG.debug('Incomplete request headers from %s', self._address)
            raise BadRequest('Incomplete request headers')

        # check content-length
        if self.method in ['POST', 'PUT', 'PATCH']:
            content_length = self._get_content_length()
            if content_length > self.max_body_size:
                raise RequestEntityTooLarge()

        return RawRequest(
            method=self.method,
            url=self.url,
            version=self.version,
            headers=self.headers,
            body=self._body_stream(),
            remote_ip=self.remote_ip,
            protocol=self.protocol,
            keep_alive=self.keep_alive,
        )
