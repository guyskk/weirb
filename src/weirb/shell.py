import sys
import code
import atexit
import os.path

from .client import Client
from .helper import HTTP_METHODS

HISTORY_PATH = os.path.expanduser('~/.weirb-history')


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
    readline.parse_and_bind('tab:complete')
    # command history
    if os.path.exists(HISTORY_PATH):
        readline.read_history_file(HISTORY_PATH)
    atexit.register(_save_history)


class Shell:

    def __init__(self, app):
        self.app = app
        self._client = Client(app)

    @property
    def headers(self):
        return self._client.headers

    @headers.setter
    def headers(self, value):
        self._client.headers = value

    def _context_locals(self):
        ctx = {
            'app': self.app,
            'config': self.app.config,
            'headers': self.headers,
            'call': self._client.call,
        }
        for method in HTTP_METHODS:
            ctx[method.lower()] = getattr(self._client, method.lower())
        return ctx

    def _format_banner(self):
        python_version = '{}.{}.{}'.format(*sys.version_info)
        banner = [
            f'Python {python_version} Weirb Shell\n\n',
            'Locals: ' + ', '.join(self._context_locals()) + '\n',
        ]
        return ''.join(banner)

    def start(self):
        context = self._context_locals()
        banner = self._format_banner()
        _enable_completer(context)
        sys.ps1 = 'Wb> '
        code.interact(banner=banner, local=context, exitmsg='')
