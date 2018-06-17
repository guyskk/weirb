import logging
from newio import spawn

from .error import HttpError, InternalServerError
from .response import ErrorResponse

LOG = logging.getLogger(__name__)


def _is_keep_alive(request, response):
    keep_alive = response.keep_alive
    if keep_alive is None:
        keep_alive = request.keep_alive
    return keep_alive


def _format_headers(response):
    headers = [f'HTTP/1.1 {response.status} {response.status_text}']
    for k, v in response.headers:
        headers.append(f'{k}: {v}')
    return '\r\n'.join(headers).encode() + b'\r\n\r\n'


def _format_chunk(chunk: bytes):
    length = hex(len(chunk))[2:].encode()
    return length + b'\r\n' + chunk + b'\r\n'


class Worker:

    def __init__(self, app, parse_request, cli_sock, cli_addr):
        self.app = app
        self.parse_request = parse_request
        self.cli_sock = cli_sock
        self.cli_addr = cli_addr
        self.address = '{}:{}'.format(*cli_addr)

    async def main(self):
        try:
            keep_alive = await self._worker_impl()
            if not keep_alive:
                await self._close()
            else:
                await spawn(self.main())
        except Exception as ex:
            LOG.exception(ex)
            await self._close()
        except BaseException:
            await self._close()
            raise

    async def _send_response(self, response):
        headers = _format_headers(response)
        await self.cli_sock.sendall(headers)
        if response.chunked:
            async for chunk in response.body:
                chunk = _format_chunk(chunk)
                await self.cli_sock.sendall(chunk)
            await self.cli_sock.sendall(b'0\r\n\r\n')
        else:
            async for chunk in response.body:
                await self.cli_sock.sendall(chunk)

    async def _send_error(self, error: HttpError):
        response = ErrorResponse(error)
        async with response:
            await self._send_response(response)
        LOG.debug('Request finished: %s', response)

    async def _drain_request(self, request):
        # drain request data
        return
        async for _ in request.body:  # noqa: F841
            pass

    async def _close(self):
        LOG.debug('Close connection %s', self.address)
        await self.cli_sock.close()

    async def _worker_impl(self):
        # parse request
        try:
            request = await self.parse_request(self.cli_sock, self.cli_addr)
        except HttpError as ex:
            LOG.info('Failed to parse request from %s', self.address)
            await self._send_error(ex)
            return False
        if request is None:
            return False
        LOG.debug('Request parsed: %s', request)

        # get response with headers
        try:
            response = await self.app(request)
        except HttpError as ex:
            await self._send_error(ex)
            await self._drain_request(request)
            return request.keep_alive
        except Exception as ex:
            LOG.error('Error raised when handle request:', exc_info=ex)
            await self._send_error(InternalServerError())
            await self._drain_request(request)
            return request.keep_alive

        # send response
        async with response:
            await self._send_response(response)
        await self._drain_request(request)
        LOG.debug('Request finished: %s', response)
        return _is_keep_alive(request, response)
