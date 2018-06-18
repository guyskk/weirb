import os
import logging
from importlib import import_module

import toml
from validr import Invalid, Compiler, fields, asdict
from weirb import Request as HttpRequest, run
from weirb.error import HttpError

from .error import ConfigError, DependencyError, HrpcError, InternalError
from .response import ErrorResponse
from .context import Context
from .helper import import_services
from .config import InternalConfig
from .service import Service
from .router import Router

LOG = logging.getLogger(__name__)


class App:
    def __init__(self, import_name, **config):
        self.import_name = import_name
        self._load_config_module()
        self._load_plugins()
        self._load_config_class()
        self._load_config(config)
        self._config_dict = asdict(self.config)
        self._active_plugins()
        self._load_schema_compiler()
        self._load_services()
        self.router = Router(self.services, self.config.url_prefix)

    def _load_config_module(self):
        self.config_module = None
        try:
            self.config_module = import_module(f'{self.import_name}.config')
        except ImportError:
            try:
                self.config_module = import_module(self.import_name)
            except ImportError:
                pass

    def _load_config_class(self):
        """
        user_config > internal_config > plugin_config
        """
        configs = []
        if hasattr(self.config_module, 'Config'):
            configs.append(self.config_module.Config)
        configs.append(InternalConfig)
        for plugin in self.plugins:
            if hasattr(plugin, 'Config'):
                configs.append(plugin.Config)
        self.config_class = type('Config', tuple(configs), {})

    def _load_config(self, config):
        key = f'{self.import_name}_config'.upper()
        config_path = os.getenv(key, None)
        if not config_path:
            try:
                self.config = self.config_class(**config)
            except Invalid as ex:
                raise ConfigError(ex.message) from None
            return
        try:
            with open(config_path) as f:
                content = f.read()
        except FileNotFoundError:
            msg = f'config file {config_path!r} not found'
            raise ConfigError(msg) from None
        try:
            file_config = toml.loads(content)
        except toml.TomlDecodeError:
            msg = f'config file {config_path!r} is not valid TOML file'
            raise ConfigError(msg) from None
        file_config.update(config)
        try:
            self.config = self.config_class(**file_config)
        except Invalid as ex:
            raise ConfigError(ex.message) from None

    def _load_plugins(self):
        if hasattr(self.config_module, 'plugins'):
            self.plugins = list(self.config_module.plugins)
        else:
            self.plugins = []

    def _active_plugins(self):
        self.contexts = []
        self.decorators = []
        self.provides = {f'config.{key}' for key in fields(self.config)}
        for plugin in self.plugins:
            plugin.active(self)
            if hasattr(plugin, 'context'):
                self.contexts.append(plugin.context)
            if hasattr(plugin, 'decorator'):
                self.decorators.append(plugin.decorator)
            if hasattr(plugin, 'provides'):
                self.provides.update(plugin.provides)
        for plugin in self.plugins:
            if not hasattr(plugin, 'requires'):
                continue
            requires = set(plugin.requires)
            missing = ', '.join(requires - self.provides)
            if missing:
                msg = f'the requires {missing} of plugin {plugin} is missing'
                raise DependencyError(msg)

    def _load_schema_compiler(self):
        if hasattr(self.config_module, 'validators'):
            self.validators.update(self.config_module.validators)
        else:
            self.validators = {}
        self.schema_compiler = Compiler(self.validators)

    def _load_services(self):
        self.services = []
        for cls in import_services(self.import_name):
            s = Service(
                cls, self.provides, self.decorators, self.schema_compiler)
            self.services.append(s)

    def context(self):
        return Context(self._config_dict, self.contexts, self._handler)

    async def _handler(self, context, raw_request):
        http_request = HttpRequest(raw_request)
        try:
            method = self.router.lookup(http_request.method, http_request.path)
            http_response = await method(context, http_request)
        except HrpcError as ex:
            http_response = ErrorResponse(ex).to_http()
        except HttpError:
            raise
        except Exception as ex:
            LOG.error('Error raised when handle request:', exc_info=ex)
            http_response = ErrorResponse(InternalError()).to_http()
        return http_response

    def run(self):
        run(self, debug=self.config.debug)
