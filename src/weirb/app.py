import os
import inspect
import logging
from importlib import import_module

import toml
from terminaltables import SingleTable
from validr import modelclass, Invalid, Compiler, fields, asdict

from .server import serve
from .logger import config_logging
from .request import Request
from .response import Response
from .error import ConfigError, DependencyError, HttpRedirect
from .context import Context
from .helper import import_all_modules, shorten_text
from .config import InternalConfig, INTERNAL_VALIDATORS
from .service import Service, Method
from .router import Router

LOG = logging.getLogger(__name__)


class App:
    def __init__(self, import_name, **cli_config):
        self.import_name = import_name
        self._load_config_module()
        self._load_intro()
        self._load_plugins()
        self._load_schema_compiler()
        self._load_config_class()
        self._load_config(cli_config)
        config_logging(self.config)
        self._config_dict = asdict(self.config)
        self._active_plugins()
        self._load_services()
        self.router = Router(self.services, self.config.server_name)

    def __repr__(self):
        return f'<App {self.import_name}>'

    def _load_config_module(self):
        self.config_module = None
        try:
            self.config_module = import_module(f'{self.import_name}.config')
        except ImportError:
            try:
                self.config_module = import_module(self.import_name)
            except ImportError:
                pass

    def _load_intro(self):
        if hasattr(self.config_module, 'intro'):
            self.intro = self.config_module.intro or ''
        else:
            self.intro = ''

    def _load_plugins(self):
        if hasattr(self.config_module, 'plugins'):
            self.plugins = list(self.config_module.plugins)
        else:
            self.plugins = []

    def _load_schema_compiler(self):
        self.validators = INTERNAL_VALIDATORS.copy()
        if hasattr(self.config_module, 'validators'):
            self.validators.update(self.config_module.validators)
        self.schema_compiler = Compiler(self.validators)

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
        config_class = type('Config', tuple(configs), {})
        self.config_class = modelclass(
            config_class, compiler=self.schema_compiler, immutable=True)

    def _load_config(self, cli_config):
        name = self.import_name.replace('.', '_')
        key = f'{name}_config'.upper()
        config_path = os.getenv(key, None)
        if config_path:
            print(f'[INFO] Load config file {config_path!r}')
            try:
                with open(config_path) as f:
                    content = f.read()
            except FileNotFoundError:
                msg = f'config file {config_path!r} not found'
                raise ConfigError(msg) from None
            try:
                config = toml.loads(content)
            except toml.TomlDecodeError:
                msg = f'config file {config_path!r} is not valid TOML file'
                raise ConfigError(msg) from None
            config.update(cli_config)
        else:
            print(f'[INFO] No config file provided '
                  f'by {key} environment variable')
            config = cli_config
        try:
            self.config = self.config_class(**config)
        except Invalid as ex:
            raise ConfigError(ex.message) from None

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

    def _load_services(self):
        visited = set()
        self.services = []
        for module in import_all_modules(self.import_name):
            for name, obj in vars(module).items():
                if not inspect.isclass(obj):
                    continue
                if obj in visited:
                    continue
                if not Service.is_service(name):
                    continue
                visited.add(obj)
                service = Service(self, obj)
                self.services.append(service)

    def context(self):
        return Context(self)

    async def _handler(self, context, raw_request):
        request = Request(context, raw_request)
        try:
            handler, path_params = self.router.lookup(
                request.path, request.method)
            request.path_params = path_params
        except HttpRedirect as redirect:
            response = Response(context)
            response.redirect(redirect.location, redirect.status)
            return response
        return await handler(context, request)

    def serve(self):
        if self.config.print_config:
            self.print_config()
        if self.config.print_plugin:
            self.print_plugin()
        if self.config.print_service:
            self.print_service()
        if self.config.print_handler:
            self.print_handler()
        serve(self, self.config)

    def print_config(self):
        table = [('Key', 'Value', 'Schema')]
        config_schema = self.config.__schema__.items
        for key, value in sorted(asdict(self.config).items()):
            schema = config_schema[key]
            table.append(
                (key, shorten_text(str(value)), shorten_text(schema.repr()))
            )
        table = SingleTable(table, title='Configs')
        print(table.table)

    def print_plugin(self):
        title = 'Plugins' if self.plugins else 'No Plugins'
        table = [('#', 'Name', 'Provides', 'Requires', 'Contributes')]
        for idx, plugin in enumerate(self.plugins, 1):
            name = type(plugin).__name__
            contributes = []
            provides = ''
            requires = ''
            if hasattr(plugin, 'context'):
                contributes.append('context')
            if hasattr(plugin, 'decorator'):
                contributes.append('decorator')
            contributes = ', '.join(contributes)
            if hasattr(plugin, 'provides'):
                provides = ', '.join(plugin.provides)
            if hasattr(plugin, 'requires'):
                requires = ', '.join(plugin.requires)
            table.append((idx, name, provides, requires, contributes))
        table = SingleTable(table, title=title)
        print(table.table)

    def print_service(self):
        title = 'Services' if self.services else 'No Services'
        table = [('#', 'Name', 'Handlers', 'Requires')]
        for idx, service in enumerate(self.services, 1):
            handlers = [m.name for m in service.handlers]
            handlers = ', '.join(handlers)
            requires = [field.key for field in service.fields.values()]
            requires = ', '.join(requires)
            table.append((idx, service.name, handlers, requires))
        table = SingleTable(table, title=title)
        print(table.table)

    def print_handler(self):
        title = 'Handlers' if self.services else 'No Handlers'
        table = [
            ['Service', 'Handler', 'Methods', 'Path'],
        ]
        for service in self.services:
            for handler in service.handlers:
                for route in handler.routes:
                    if isinstance(handler, Method):
                        methods = '*POST'
                    else:
                        methods = ' '.join(route.methods)
                    table.append((
                        service.name,
                        handler.name,
                        methods,
                        route.path,
                    ))
        table = SingleTable(table, title=title)
        print(table.table)
