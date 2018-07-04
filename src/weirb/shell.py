import sys
import code
import json
import atexit
import logging
import os.path

from validr import Compiler, T, Invalid

from .client import Client
from .helper import HTTP_METHODS

HISTORY_PATH = os.path.expanduser("~/.weirb-history")
HEADERS_PATH = os.path.abspath(".weirb-shell.json")

LOG = logging.getLogger(__name__)


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


HeadersSchema = T.list(T.dict(name=T.str, value=T.str))
validate_headers = Compiler().compile(HeadersSchema)


class Shell:
    def __init__(self, app):
        self.app = app
        headers = self._load_headers()
        self._client = Client(app, headers=headers)

    def _load_headers(self):
        if not os.path.exists(HEADERS_PATH):
            return None
        LOG.info(f"Load headers from {HEADERS_PATH!r}")
        try:
            with open(HEADERS_PATH) as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as ex:
            LOG.warning(f"Failed to load headers: {ex}")
            return None
        try:
            data = validate_headers(data)
        except Invalid as ex:
            LOG.warning(f"Invalid headers file: {ex}")
            return None
        headers = [(x["name"], x["value"]) for x in data]
        return headers

    def _save_headers(self):
        if not self.headers:
            return
        LOG.info(f"Save headers to {HEADERS_PATH!r}")
        data = [{"name": name, "value": value} for name, value in self.headers.items()]
        try:
            with open(HEADERS_PATH, "w") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except (OSError, TypeError) as ex:
            LOG.warning(f"Failed to save headers: {ex}")

    @property
    def headers(self):
        return self._client.headers

    @headers.setter
    def headers(self, value):
        self._client.headers = value

    def _context_locals(self):
        ctx = {
            "app": self.app,
            "config": self.app.config,
            "headers": self.headers,
            "call": self._client.call,
        }
        for method in HTTP_METHODS:
            ctx[method.lower()] = getattr(self._client, method.lower())
        return ctx

    def _format_banner(self):
        python_version = "{}.{}.{}".format(*sys.version_info)
        banner = [
            f"Python {python_version} Weirb Shell\n",
            "Locals: " + ", ".join(self._context_locals()),
        ]
        return "".join(banner)

    def start(self):
        context = self._context_locals()
        banner = self._format_banner()
        _enable_completer(context)
        sys.ps1 = "Wb> "
        try:
            code.interact(banner=banner, local=context, exitmsg="")
        finally:
            self._save_headers()
