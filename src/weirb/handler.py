import inspect
import logging
from functools import partial

from validr import T, Invalid

from .response import Response
from .helper import HTTP_METHODS
from .tagger import tagger
from .error import (
    HrpcError,
    HrpcServerError,
    HrpcInvalidParams,
    BadRequest,
    HrpcInvalidRequest,
)

LOG = logging.getLogger(__name__)


def route(path, *, methods, host=None):
    return tagger.stackable_tag('routes', dict(
        path=path,
        methods=methods,
        host=host,
    ))


def _build_route():
    for m in HTTP_METHODS:
        setattr(route, m.lower(), partial(route, methods=[m]))


_build_route()
del _build_route


get_routes = tagger.get('routes')


def raises(error):
    return tagger.stackable_tag('raises', error)


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


class Component:
    def __init__(self, origin_class, provides, decorators, schema_compiler):
        self.origin_class = origin_class
        self.provides = provides
        self.decorators = decorators
        self.schema_compiler = schema_compiler
        self.__load_fields()
        self.__load_cls()

    def __load_fields(self):
        self.fields = {}
        for cls in reversed(self.origin_class.__mro__):
            for k, v in vars(cls).items():
                if not isinstance(v, Dependency):
                    continue
                if v.key not in self.provides:
                    raise ValueError(f'dependency {v.key!r} not exists')
                self.fields[k] = v

    def __load_cls(self):
        base = self.origin_class
        cls = type(base.__name__, (base,), self.fields)
        cls.__module__ = base.__module__
        cls.__name__ = base.__name__
        cls.__qualname__ = base.__qualname__
        cls.__doc__ = base.__doc__
        self.cls = cls

    def __load_views(self):
        views = []
        for k, v in vars(self.origin_class).items():
            if not callable(v):
                continue
            routes = get_routes(v)
            if not routes:
                continue
            view = View(self.cls, k, v, routes, self.decorators)
            views.append(view)
        return views

    def __load_methods(self):
        methods = []
        prefix = 'method_'
        for k, v in vars(self.origin_class).items():
            if not callable(v):
                continue
            if not (k.startswith(prefix) and k != prefix):
                continue
            name = k[len(prefix)]
            method = Method(self.cls, name, v, self.decorators,
                            self.schema_compiler)
            methods.append(method)
        return methods


def _decorate(f, handler, decorators):
    origin = f
    for d in decorators:
        f = d(f, handler)
    f.__name__ = origin.__name__
    f.__qualname__ = origin.__qualname__
    f.__module__ = origin.__module__
    f.__doc__ = origin.__doc__
    return f


class View:

    def __init__(self, cls, name, f, routes, decorators):
        self.cls = cls
        self.name = name
        self.routes = routes
        self.tags = tagger.get_tags(f)
        self.doc = f.__doc__
        self.f = _decorate(f, self, decorators)

    async def __call__(self, context, request):
        obj = self.cls()
        obj.context = context
        obj.request = request
        obj.response = Response(context)
        await self.f(obj, context, request)
        return obj.response


class Method:

    def __init__(self, cls, name, f, decorators, schema_compiler):
        self.cls = cls
        self.service_name = cls.__name__
        self.name = name
        self.schema_compiler = schema_compiler
        self.tags = tagger.get_tags(f)
        self.doc = f.__doc__
        self.params = self._get_params(f)
        self.returns = self._get_returns(f)
        self.raises = self._get_raises(f)
        self.f = _decorate(f, self, decorators)
        self._params_validator = None
        if self.params is not None:
            self._params_validator = self._compile_schema(self.params)
        self._returns_validator = None
        if self.returns is not None:
            self._returns_validator = self._compile_schema(self.returns)

    def _get_params(self, f):
        sig = inspect.signature(f)
        params_schema = {}
        for name, p in sig.parameters.items():
            if p.annotation is not inspect.Parameter.empty:
                params_schema[name] = p.annotation
        if params_schema:
            return T.dict(params_schema).__schema__
        return None

    def _get_returns(self, f):
        sig = inspect.signature(f)
        if sig.return_annotation is not inspect.Signature.empty:
            schema = sig.return_annotation
            return T(schema).__schema__
        return None

    def _get_raises(self, f):
        raises = get_raises(f) or []
        for error in raises:
            if not isinstance(error, HrpcError):
                raise TypeError('Can only raises subtypes of HrpcError')
        return raises

    def _compile_schema(self, schema):
        return self.schema_compiler.compile(schema)

    def __repr__(self):
        return f'<Method {self.service_name}.{self.name}>'

    def _set_error(self, response, ex):
        response.status = ex.status
        response.headers['Hrpc-Error'] = ex.code
        response.json(dict(message=ex.message, data=ex.data))

    async def __call__(self, context, request):
        service = self.service_class()
        try:
            return await self._call(service, context, request)
        except HrpcError as ex:
            self._set_error(service.response, ex)
        except Exception as ex:
            LOG.error('Error raised when handle request:', exc_info=ex)
            self._set_error(service.response, HrpcServerError())
        return service.response

    async def _call(self, obj, context, request):
        obj.context = context
        obj.request = request
        obj.response = Response(context)
        # prepare request
        if self._params_validator is not None:
            params = await self._parse_request(request)
            try:
                params = self._params_validator(params)
            except Invalid as ex:
                raise HrpcInvalidParams(str(ex)) from None
            returns = await self._handler(obj, **params)
        else:
            returns = await self._handler(obj)
        # process response
        if self._returns_validator is not None:
            try:
                returns = self._returns_validator(returns)
            except Invalid as ex:
                msg = f'Service return a invalid result: {ex}'
                raise HrpcServerError(msg)
            obj.response.json(returns)
        return obj.response

    async def _parse_request(self, request):
        try:
            params = await request.json()
        except BadRequest as ex:
            raise HrpcInvalidRequest(ex.message) from ex
        return params
