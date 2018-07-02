import inspect
import logging
import itertools
from functools import partial

from validr import T, Invalid

from .response import Response
from .helper import HTTP_METHODS
from .tagger import tagger
from .error import (
    DependencyError,
    HrpcError,
    HrpcServerError,
    HrpcInvalidParams,
    BadRequest,
    HrpcInvalidRequest,
)

LOG = logging.getLogger(__name__)


class Route:
    def __init__(self, path, methods):
        self.path = path
        self.methods = methods


def route(path, *, methods):
    methods = _normalize_methods(methods)
    return tagger.stackable_tag('routes', Route(path, methods))


def _normalize_methods(methods):
    methods = set(x.upper() for x in methods)
    unknown = set(methods) - set(HTTP_METHODS)
    if unknown:
        raise ValueError(f'unknown methods {unknown!r}')
    return methods


def _build_route():
    for m in HTTP_METHODS:
        setattr(route, m.lower(), partial(route, methods=[m]))


_build_route()
del _build_route


get_routes = tagger.get('routes')


def raises(*errors):
    for e in errors:
        if not issubclass(e, HrpcError):
            raise TypeError('Can only raises subtypes of HrpcError')
    return tagger.stackable_tag('raises', errors)


get_raises = tagger.get('raises', default=None)


class Dependency:
    def __init__(self, key):
        self.key = key


def require(key):
    return Dependency(key)


class DependencyField:

    def __init__(self, name, key):
        self.name = name
        self.key = key

    def __get__(self, obj, obj_type):
        if obj is None:
            return self
        if self.name in obj.__dict__:
            return obj.__dict__[self.name]
        value = obj.context.require(self.key)
        obj.__dict__[self.name] = value
        return value


class Service:

    @staticmethod
    def is_service(name):
        return name.endswith('Service') and name != 'Service'

    def __init__(self, app, cls):
        self.app = app
        self.raw_cls = cls
        self.name = cls.__name__[:-len('Service')]
        self.doc = cls.__doc__
        self.__load_fields()
        self.__load_cls()
        self.__load_handlers()

    def __repr__(self):
        handlers = ', '.join(m.name for m in self.handlers)
        return f'<Service {self.name}: {handlers}>'

    def __load_fields(self):
        self.fields = {}
        for cls in reversed(self.raw_cls.__mro__):
            for k, v in vars(cls).items():
                if not isinstance(v, Dependency):
                    continue
                if v.key not in self.app.provides:
                    raise DependencyError(f'dependency {v.key!r} not exists')
                self.fields[k] = DependencyField(k, v.key)

    def __load_cls(self):
        base = self.raw_cls
        cls = type(base.__name__, (base,), self.fields)
        cls.__module__ = base.__module__
        cls.__name__ = base.__name__
        cls.__qualname__ = base.__qualname__
        cls.__doc__ = base.__doc__
        self.cls = cls

    def __load_handlers(self):
        self.handlers = []
        for name, f in vars(self.raw_cls).items():
            if not callable(f):
                continue
            if self.__is_view(name, f):
                handler = self.__load_view(name, f)
            elif self.__is_method(name, f):
                handler = self.__load_method(name, f)
            else:
                continue
            self.__decorate(handler)
            self.handlers.append(handler)

    def __is_view(self, name, f):
        return bool(get_routes(f))

    def __load_view(self, name, f):
        self.__check_handler_func(name, f)
        return View(self, name, f)

    def __is_method(self, name, f):
        return name.startswith('method_') and name != 'method_'

    def __load_method(self, name, f):
        self.__check_handler_func(name, f)
        return Method(self, name, f)

    def __check_handler_func(self, name, f):
        class_name = self.raw_cls.__name__
        if not inspect.iscoroutinefunction(f):
            raise TypeError(f'{class_name}.{name} is not coroutine function')

    def __decorate(self, handler):
        origin = f = handler.f
        for d in self.app.decorators:
            f = d(f, handler)
        f.__name__ = origin.__name__
        f.__qualname__ = origin.__qualname__
        f.__module__ = origin.__module__
        f.__doc__ = origin.__doc__
        handler.f = f


class Handler:

    def __init__(self, service, name, f):
        self.service = service
        self.service_class = service.cls
        self.service_name = service.name
        self.root_path = self.service.app.config.root_path
        self.tags = tagger.get_tags(f)
        self.doc = f.__doc__
        self.f = f

    def __repr__(self):
        return f'<{type(self).__name__} {self.service_name}.{self.name}>'

    def fix_path(self, path):
        return (self.root_path + path.lstrip('/')).lower()


class View(Handler):

    def __init__(self, service, name, f):
        super().__init__(service, name, f)
        self.is_method = False
        self.name = name
        self.routes = []
        for route in get_routes(f):
            path = self.fix_path(route.path)
            self.routes.append(Route(path, route.methods))

    async def __call__(self, context, request):
        service = self.service_class()
        service.context = context
        service.request = request
        service.response = Response(context)
        await self.f(service, **request.path_params)
        return service.response


class Method(Handler):

    def __init__(self, service, name, f):
        super().__init__(service, name, f)
        self.is_method = True
        self.name = name[len('method_'):]
        self.schema_compiler = service.app.schema_compiler
        self.routes = [Route(
            path=self.fix_path(f'{self.service_name}/{self.name}'),
            methods=['POST'],
        )]
        self.params = self.__get_params(f)
        self.returns = self.__get_returns(f)
        self.raises = self.__get_raises(f)
        self.__params_validator = None
        if self.params is not None:
            self.__params_validator = self.__compile_schema(self.params)
        self.__returns_validator = None
        if self.returns is not None:
            self.__returns_validator = self.__compile_schema(self.returns)

    def __get_params(self, f):
        sig = inspect.signature(f)
        params_schema = {}
        for name, p in sig.parameters.items():
            if p.annotation is not inspect.Parameter.empty:
                params_schema[name] = p.annotation
        if params_schema:
            return T.dict(params_schema).__schema__
        return None

    def __get_returns(self, f):
        sig = inspect.signature(f)
        if sig.return_annotation is not inspect.Signature.empty:
            schema = sig.return_annotation
            return T(schema).__schema__
        return None

    def __get_raises(self, f):
        raises = get_raises(f) or []
        raises = set(itertools.chain.from_iterable(raises))
        return raises

    def __compile_schema(self, schema):
        return self.schema_compiler.compile(schema)

    def __set_error(self, response, ex):
        response.status = ex.status
        response.headers['Hrpc-Error'] = ex.code
        response.json(dict(message=ex.message, data=ex.data))

    async def __call__(self, context, request):
        service = self.service_class()
        try:
            return await self.__call(service, context, request)
        except HrpcError as ex:
            self.__set_error(service.response, ex)
        except Exception as ex:
            LOG.error('Error raised when handle request:', exc_info=ex)
            self.__set_error(service.response, HrpcServerError())
        return service.response

    async def __call(self, service, context, request):
        service.context = context
        service.request = request
        service.response = Response(context)
        # prepare request
        if self.__params_validator is not None:
            params = await self.__parse_request(request)
            try:
                params = self.__params_validator(params)
            except Invalid as ex:
                raise HrpcInvalidParams(str(ex)) from None
            returns = await self.f(service, **params)
        else:
            returns = await self.f(service)
        # process response
        if self.__returns_validator is not None:
            try:
                returns = self.__returns_validator(returns)
            except Invalid as ex:
                msg = f'Service return a invalid result: {ex}'
                raise HrpcServerError(msg)
            service.response.json(returns)
        return service.response

    async def __parse_request(self, request):
        try:
            params = await request.json()
        except BadRequest as ex:
            raise HrpcInvalidRequest(ex.message) from ex
        return params
