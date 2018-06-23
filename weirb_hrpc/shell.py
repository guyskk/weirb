import sys
import json
import code
import atexit
import os.path
from terminaltables import AsciiTable
from newio_kernel import run
from weirb import RawRequest
from weirb.error import HttpError


HISTORY_PATH = os.path.expanduser('~/.weirb-hrpc-history')


def _save_history():
    import readline
    readline.write_history_file(HISTORY_PATH)


def _enable_completer(context):
    try:
        import readline
    except ImportError:
        return
    try:
        import rlcompleter
    except ImportError:
        return
    readline.set_completer(rlcompleter.Completer(context).complete)
    readline.parse_and_bind("tab:complete")
    # command history
    if os.path.exists(HISTORY_PATH):
        readline.read_history_file(HISTORY_PATH)
    atexit.register(_save_history)


def _format_headers(headers):
    headers = [f'{k}: {v}' for k, v in headers.items()]
    return'\n'.join(headers)


class ApiError(Exception):
    """Api Error"""

    def __init__(self, message, headers=None, data=None):
        self.message = message
        self.headers = headers or {}
        self.error = headers.pop('error', None) or 'Hrpc.HttpError'
        self.data = data
        super().__init__(repr(self))

    def __repr__(self):
        headers = _format_headers(self.headers)
        if self.error == self.message:
            msg = self.error
        else:
            msg = f'{self.error}: {self.message}'
        if headers:
            return f'\n{headers}\n    {msg}\n'
        else:
            return f'\n    {msg}\n'


class ApiResult:
    def __init__(self, result, headers):
        self.result = result
        self.headers = headers

    def __repr__(self):
        headers = _format_headers(self.headers)
        text = json.dumps(self.result, ensure_ascii=False, indent=4).strip()
        if headers:
            return f'\n{headers}\n{text}\n'
        else:
            return f'\n{text}\n'


class Headers(dict):

    def __getitem__(self, k):
        return super().__getitem__(k.lower())

    def __setitem__(self, k, v):
        super().__setitem__(k.lower(), v)

    def __delitem__(self, k):
        super().__delitem__(k.lower())

    def __repr__(self):
        if not self:
            return '\n    No Headers\n'
        headers = [f'    {k}: {v}' for k, v in self.items()]
        headers = '\n'.join(headers)
        return f'\n{headers}\n'


class Service:
    def __init__(self, service, methods):
        self.__dict__.update(methods)
        self._service = service
        self._methods = ','.join(methods)

    def __repr__(self):
        return f'<{self._service}: {self._methods}>'


class Method:
    def __init__(self, shell, service, method):
        self._shell = shell
        self._service = service
        self._method = method

    def __call__(self, **params):
        try:
            return self._shell.call(self._service, self._method, params)
        except ApiError as ex:
            return ex

    def __repr__(self):
        return f'{self._service}.{self._method}'


class HrpcShell:
    def __init__(self, app):
        self.app = app
        self.url_prefix = app.config.url_prefix
        self.headers = Headers()
        self.services = {}
        for s in app.services:
            methods = {}
            for m in s.methods:
                methods[m.name] = Method(self, s.name, m.name)
            self.services[s.name] = Service(s.name, methods)

    def _get_endpoint(self, service, method):
        return f'{self.url_prefix}/{service}/{method}'

    async def _read_response(self, response):
        content = []
        async for chunk in response.body:
            content.append(chunk)
        content = b''.join(content)
        text = content.decode('utf-8')
        result = json.loads(text)
        headers = {}
        for k, v in response.headers.items():
            k = k.lower()
            if k.startswith('hrpc-'):
                headers[k[5:]] = v
        if 'error' in headers:
            raise ApiError(headers=headers, **result)
        return ApiResult(result, headers)

    async def _request_body(self, params):
        text = json.dumps(params, ensure_ascii=False, indent=4)
        yield text.encode('utf-8')

    async def _call(self, service, method, headers, params):
        path = self._get_endpoint(service, method)
        headers = [(f'Hrpc-{k}', v) for k, v in headers.items()]
        headers.append(('Content-Type', 'application/json;charset=utf-8'))
        raw_request = RawRequest(
            method='POST',
            url=path,
            version='HTTP/1.1',
            headers=headers,
            body=self._request_body(params),
            protocol='http',
            remote_ip='127.0.0.1',
            keep_alive=True,
        )
        async with self.app.context() as ctx:
            try:
                response = await ctx(raw_request)
            except HttpError as ex:
                raise ApiError(str(ex))
            return await self._read_response(response)

    def call(self, service, method, params):
        return run(self._call(service, method, self.headers, params))

    def _context_locals(self):
        return {
            'app': self.app,
            'config': self.app.config,
            'headers': self.headers,
        }

    def _format_banner(self):
        python_version = '{}.{}.{}'.format(*sys.version_info)
        banner = [
            f'Python {python_version} Hrpc Shell\n',
            'Locals: ' + ', '.join(self._context_locals()) + '\n',
        ]
        services = [('Service', 'Methods')]
        for s in self.app.services:
            methods = ', '.join([m.name for m in s.methods])
            services.append((s.name, methods))
        table = AsciiTable(services).table.strip()
        banner.append(table)
        return ''.join(banner)

    def start(self):
        context = self._context_locals()
        context.update(self.services)
        banner = self._format_banner()
        _enable_completer(context)
        sys.ps1 = 'Hrpc> '
        code.interact(banner=banner, local=context, exitmsg='')
