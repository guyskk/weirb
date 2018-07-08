import inspect
import logging
import itertools
from functools import partial

from validr import T, Invalid

from .response import Response
from .helper import HTTP_METHODS
from .tagger import tagger
from .error import ServiceError, ServiceInvalidParams

LOG = logging.getLogger(__name__)


class Route:
    def __init__(self, path, methods):
        self.path = path
        self.methods = methods


def route(path, *, methods):
    path = '/' + path.lstrip('/')
    methods = _normalize_methods(methods)
    return tagger.stackable_tag("routes", Route(path, methods))


def _normalize_methods(methods):
    methods = set(x.upper() for x in methods)
    unknown = set(methods) - set(HTTP_METHODS)
    if unknown:
        raise ValueError(f"unknown methods {unknown!r}")
    return methods


def _build_route():
    for m in HTTP_METHODS:
        setattr(route, m.lower(), partial(route, methods=[m]))


_build_route()
del _build_route


get_routes = tagger.get("routes")


def raises(*errors):
    for e in errors:
        if not issubclass(e, ServiceError):
            raise TypeError("Can only raises subtypes of ServiceError")
    return tagger.stackable_tag("raises", errors)


get_raises = tagger.get("raises", default=None)


class Service:
    def __init__(self, app, cls):
        self.app = app
        self.cls = cls
        self.scope = app.create_scope(cls)
        self.name = cls.__name__[: -len("Service")]
        self.doc = cls.__doc__
        self._load_handlers()

    def __repr__(self):
        handlers = ", ".join(h.name for h in self.handlers)
        return f"<Service {self.name}: {handlers}>"

    def _load_handlers(self):
        self.handlers = []
        for name, f in vars(self.cls).items():
            if not callable(f):
                continue
            if self._is_view(name, f):
                self._load_handler(name, f, is_method=False)
            if self._is_method(name, f):
                self._load_handler(name, f, is_method=True)

    def _is_view(self, name, f):
        return bool(get_routes(f))

    def _is_method(self, name, f):
        return name.startswith("do_") and name != "do_"

    def _load_handler(self, name, f, is_method):
        self._check_handler_func(name, f)
        handler = Handler(self, name, f, is_method)
        self.handlers.append(handler)

    def _check_handler_func(self, name, f):
        class_name = self.cls.__name__
        if not inspect.iscoroutinefunction(f):
            msg = f"{class_name}.{name} is not coroutine function"
            raise TypeError(msg)


class Handler:
    def __init__(self, service, name, f, is_method):
        self.service = service
        self.name = name
        self.f = f
        self.is_method = is_method
        self.scope = service.scope
        self.service_name = service.name
        self.decorators = service.app.decorators
        self.schema_compiler = service.app.schema_compiler
        self.root_path = service.app.config.root_path
        self.tags = tagger.get_tags(f)
        self.doc = f.__doc__
        self.routes = self._load_routes()
        self.params = None
        if self.is_method:
            self.params = self._get_params(f)
        self.returns = self._get_returns(f)
        self.raises = self._get_raises(f)
        self.params_validator = None
        if self.params is not None:
            self.params_validator = self._compile_schema(self.params)
        self.returns_validator = None
        if self.returns is not None:
            self.returns_validator = self._compile_schema(self.returns)
        self.handler = self._decorate(f)

    def _load_routes(self):
        if self.is_method:
            name = self.name[len('do_'):]
            path = f"{self.service_name}/{name}"
            r = Route(path=self._fix_path(path), methods=["POST"])
            return [r]
        else:
            routes = []
            for route in get_routes(self.f):
                path = self._fix_path(route.path)
                routes.append(Route(path, route.methods))
            return routes

    def _fix_path(self, path):
        return (self.root_path + path.lstrip("/")).lower()

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
        raises = set(itertools.chain.from_iterable(raises))
        return raises

    def _compile_schema(self, schema):
        return self.schema_compiler.compile(schema)

    def _decorate(self, f):
        origin = f
        for d in reversed(self.decorators):
            f = d(f, self)
        f.__name__ = origin.__name__
        f.__qualname__ = origin.__qualname__
        f.__module__ = origin.__module__
        f.__doc__ = origin.__doc__
        return f

    async def _get_request_params(self, request):
        if not self.is_method:
            return request.path_params
        if self.params_validator is None:
            return {}
        params = await request.json()
        try:
            params = self.params_validator(params)
        except Invalid as ex:
            raise ServiceInvalidParams(str(ex)) from None
        return params

    def _set_response_error(self, response, ex):
        response.status = ex.status
        response.headers["Service-Error"] = ex.code
        response.json(dict(message=ex.message, data=ex.data))

    def _set_response_result(self, response, returns):
        if self.returns_validator is None:
            if returns is not None:
                LOG.info('Service return a value but no schema provided: %r', returns)
            return
        try:
            returns = self.returns_validator(returns)
        except Invalid as ex:
            LOG.error(f"Service return a invalid result: {ex}")
            raise
        response.json(returns)

    async def __call__(self, context, request):
        service = self.scope.instance(context)
        service.request = request
        service.response = Response(context)
        try:
            params = await self._get_request_params(request)
            returns = await self.handler(service, **params)
            self._set_response_result(service.response, returns)
        except ServiceError as ex:
            self._set_response_error(service.response, ex)
        return service.response
