import os
import logging
import inspect
from importlib import import_module
from pathlib import Path

import toml
from terminaltables import AsciiTable, SingleTable
from validr import modelclass, Invalid, Compiler, asdict

from .server import serve
from .logger import config_logging
from .request import Request
from .response import Response
from .error import ConfigError, DependencyError, HttpRedirect
from .error import BUILTIN_SERVICE_ERRORS
from .context import Context
from .helper import import_all_classes, shorten_text, concat_words, is_terminal
from .config import InternalConfig, INTERNAL_VALIDATORS
from .service import Service
from .router import Router
from .scope import Scope
from .compat.contextlib import asynccontextmanager

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
        config_logging(self.import_name, self.config)
        self._scopes = {}
        self._active_plugins()
        self._load_services()
        self.router = Router(self.services, self.config.server_name)
        self._print_info()

    def __repr__(self):
        return f"<App {self.import_name}>"

    def create_scope(self, cls):
        if cls not in self._scopes:
            self._scopes[cls] = Scope(self, cls)
        return self._scopes[cls]

    def _load_config_module(self):
        self.config_module = None
        name = f"{self.import_name}.config"
        try:
            self.config_module = import_module(name)
        except ModuleNotFoundError as ex:
            if ex.name != name:
                raise
            self.config_module = import_module(self.import_name)

    def _load_intro(self):
        if hasattr(self.config_module, "intro"):
            self.intro = self.config_module.intro or ""
        else:
            self.intro = ""

    def _load_plugins(self):
        if hasattr(self.config_module, "plugins"):
            self.plugins = list(self.config_module.plugins)
        else:
            self.plugins = []

    def _load_schema_compiler(self):
        self.validators = INTERNAL_VALIDATORS.copy()
        if hasattr(self.config_module, "validators"):
            self.validators.update(self.config_module.validators)
        self.schema_compiler = Compiler(self.validators)

    def _load_config_class(self):
        """
        user_config > internal_config > plugin_config
        """
        configs = []
        if hasattr(self.config_module, "Config"):
            configs.append(self.config_module.Config)
        configs.append(InternalConfig)
        for plugin in self.plugins:
            if hasattr(plugin, "Config"):
                configs.append(plugin.Config)
        config_class = type("Config", tuple(configs), {})
        self.config_class = modelclass(
            config_class, compiler=self.schema_compiler, immutable=True
        )

    def _normalize_config_path(self, config_path):
        config_path = Path(config_path).expanduser()
        return str(config_path.absolute())

    def _load_config(self, cli_config):
        name = self.import_name.replace(".", "_")
        key = f"{name}_config".upper()
        config_path = os.getenv(key, None)
        if config_path:
            config_path = self._normalize_config_path(config_path)
            print(f"[INFO] Load config file {config_path!r}")
            try:
                with open(config_path) as f:
                    content = f.read()
            except FileNotFoundError:
                msg = f"config file {config_path!r} not found"
                raise ConfigError(msg) from None
            try:
                config = toml.loads(content)
            except toml.TomlDecodeError:
                msg = f"config file {config_path!r} is not valid TOML file"
                raise ConfigError(msg) from None
            config.update(cli_config)
        else:
            print(f"[INFO] No config file provided " f"by {key} environment variable")
            config = cli_config
        self.config_path = config_path
        try:
            self.config = self.config_class(**config)
        except Invalid as ex:
            raise ConfigError(ex.message) from None
        self._config_dict = {"config": self.config}
        for k, v in asdict(self.config).items():
            self._config_dict[f"config.{k}"] = v

    def _active_plugins(self):
        self.contexts = []
        self.decorators = []
        self.raises = set(BUILTIN_SERVICE_ERRORS)
        self.provides = set(self._config_dict)
        for plugin in self.plugins:
            plugin.active(self)
            if hasattr(plugin, "context"):
                context = plugin.context
                if inspect.isasyncgenfunction(plugin.context):
                    context = asynccontextmanager(plugin.context)
                self.contexts.append(context)
            if hasattr(plugin, "decorator"):
                self.decorators.append(plugin.decorator)
            if hasattr(plugin, "raises"):
                self.raises.update(plugin.raises)
            if hasattr(plugin, "provides"):
                self.provides.update(plugin.provides)
            if not hasattr(plugin, "requires"):
                continue
            requires = set()
            for r in plugin.requires:
                if inspect.isclass(r):
                    scope = self.create_scope(r)
                    requires.update(scope.requires)
                else:
                    requires.add(r)
            missing = ", ".join(requires - self.provides)
            if missing:
                msg = f"the requires {missing} of plugin {plugin} is missing"
                raise DependencyError(msg)

    def _load_services(self):
        self.services = []
        for obj in import_all_classes(self.import_name, ".+Service"):
            s = Service(self, obj)
            if s.handlers:
                self.services.append(s)

    def context(self):
        return Context(self)

    async def _handler(self, context, raw_request):
        request = Request(context, raw_request)
        try:
            handler, path_params = self.router.lookup(request.path, request.method)
            request.path_params = path_params
        except HttpRedirect as redirect:
            response = Response(context)
            response.redirect(redirect.location, redirect.status)
            return response
        return await handler(context, request)

    def serve(self):
        serve(self, self.config)

    def _print_info(self):
        if self.config.print_config:
            self.print_config()
        if self.config.print_plugins:
            self.print_plugins()
        if self.config.print_services:
            self.print_services()
        if self.config.print_handlers:
            self.print_handlers()

    def _print_table(self, table, title, inner_row_border=False):
        if is_terminal():
            table = SingleTable(table, title=title)
        else:
            table = AsciiTable(table, title=title)
        table.inner_row_border = inner_row_border
        print(table.table)

    def print_config(self):
        table = [("Key", "Value", "Schema")]
        config_schema = self.config.__schema__.items
        for key, value in sorted(asdict(self.config).items()):
            schema = shorten_text(config_schema[key].repr())
            value = shorten_text(str(value), 20)
            table.append((key, value, schema))
        self._print_table(table, title="Configs")

    def print_plugins(self):
        title = "Plugins" if self.plugins else "No Plugins"
        table = [("Name", "Provides", "Requires", "Contributes")]
        for plugin in self.plugins:
            name = type(plugin).__name__
            contributes = []
            provides = ""
            requires = ""
            if hasattr(plugin, "context"):
                contributes.append("context")
            if hasattr(plugin, "decorator"):
                contributes.append("decorator")
            contributes = ", ".join(contributes)
            if hasattr(plugin, "provides"):
                provides = "\n".join(plugin.provides)
            if hasattr(plugin, "requires"):
                requires = "\n".join(plugin.requires)
            table.append((name, provides, requires, contributes))
        self._print_table(table, title=title, inner_row_border=True)

    def print_services(self):
        title = "Services" if self.services else "No Services"
        table = [("Name", "Handlers", "Requires")]
        for service in self.services:
            handlers = [m.name for m in service.handlers]
            handlers = concat_words(handlers, 30)
            requires = "\n".join(sorted(service.scope.requires))
            table.append((service.name, handlers, requires))
        self._print_table(table, title=title, inner_row_border=True)

    def print_handlers(self):
        title = "Handlers" if self.services else "No Handlers"
        table = [("Methods", "Path", "Handler")]
        for service in self.services:
            for handler in service.handlers:
                for route in handler.routes:
                    if handler.is_method:
                        methods = "*POST"
                    else:
                        methods = " " + concat_words(route.methods, sep=" ")
                    handler_name = service.name + "." + handler.name
                    table.append((methods, route.path, handler_name))
        self._print_table(table, title=title)
