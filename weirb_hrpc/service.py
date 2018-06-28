import inspect
import logging
from validr import T, Invalid
from weirb.error import BadRequest
from .request import Request
from .response import Response
from .error import HrpcError, InvalidRequest, InvalidParams, InvalidResult
from .tagger import tagger

http_request = tagger.tag('http_request', True)
is_http_request = tagger.get('http_request', default=False)
http_response = tagger.tag('http_response', True)
is_http_response = tagger.get('http_response', default=False)


def raises(error):
    return tagger.stackable_tag('raises', error)


get_raises = tagger.get('raises', default=None)


LOG = logging.getLogger(__name__)


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


class MethodInfo:
    def __init__(self, service_name, name, f):
        self.service_name = service_name
        self.name = name
        self.f = f
        self.tags = tagger.get_tags(f)
        self.doc = f.__doc__
        self.is_http_request = is_http_request(f)
        self.is_http_response = is_http_response(f)
        if not self.is_http_request:
            self.params = self._get_params(f)
        else:
            self.params = None
        if not self.is_http_response:
            self.returns = self._get_returns(f)
        else:
            self.returns = None
        self.raises = self._get_raises(f)

    def __repr__(self):
        return f'<MethodInfo {self.service_name}.{self.name}>'

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


class Service:

    def __init__(self, service_class, provides, decorators, schema_compiler):
        self.name = service_class.__name__[:-len('Service')]
        self.doc = service_class.__doc__ or ''
        self.decorators = decorators
        self.schema_compiler = schema_compiler
        methods, fields = self._parse_service(service_class, provides)
        self._load_fields(fields)
        self._make_service_class(service_class)
        self._load_methods(methods)

    def __repr__(self):
        methods = ','.join(m.name for m in self.methods)
        return f'<Service {self.name}: {methods}>'

    def _load_fields(self, fields):
        self.fields = {
            k: DependencyField(k, v.key)
            for k, v in fields.items()
        }

    def _make_service_class(self, base):
        cls = type(base.__name__, (base,), self.fields)
        cls.__module__ = base.__module__
        cls.__name__ = base.__name__
        cls.__qualname__ = base.__qualname__
        cls.__doc__ = base.__doc__
        self.service_class = cls

    def _load_methods(self, methods):
        self.methods = []
        for name, f in methods.items():
            method_info = MethodInfo(self.name, name, f)
            method_info.f = self._decorate(method_info)
            m = Method(
                service_name=self.name,
                service_class=self.service_class,
                method_info=method_info,
            )
            self.methods.append(m)

    def _parse_service(self, service_class, provides):
        prefix = 'method_'
        methods = {}
        fields = {}
        for cls in reversed(service_class.__mro__):
            for k, v in vars(cls).items():
                if callable(v) and k.startswith(prefix) and k != prefix:
                    name = k[len(prefix):]
                    if not inspect.iscoroutinefunction(v):
                        msg = (f'{self.name}Service.{k} '
                               f'is not coroutine function')
                        raise TypeError(msg)
                    methods[name] = v
                if isinstance(v, Dependency):
                    if v.key not in provides:
                        raise ValueError(f'dependency {v.key!r} not exists')
                    fields[k] = v
        return methods, fields

    def _decorate(self, method_info):
        origin = method_info.f
        f = self._hrpc_decorator(origin, method_info)
        for d in self.decorators:
            f = d(f, method_info)
        f.__name__ = origin.__name__
        f.__qualname__ = origin.__qualname__
        f.__module__ = origin.__module__
        f.__doc__ = origin.__doc__
        return f

    def _compile_schema(self, schema):
        return self.schema_compiler.compile(schema)

    def _hrpc_decorator(self, f, method_info):
        _is_http_request = method_info.is_http_request
        _is_http_response = method_info.is_http_response
        method = method_info.name

        if _is_http_request and _is_http_response:
            return f

        if method_info.params is None:
            params_validator = None
        else:
            params_validator = self._compile_schema(method_info.params)
        if method_info.returns is None:
            returns_validator = None
        else:
            returns_validator = self._compile_schema(method_info.returns)

        async def wrapper(service, http_request):
            # prepare request
            if _is_http_request:
                service.request = None
            else:
                headers, params = await self._parse_request(http_request)
                if params_validator is not None:
                    try:
                        params = params_validator(params)
                    except Invalid as ex:
                        raise InvalidParams(str(ex)) from None
                request = Request(method, headers, params)
                service.request = request

            # prepare response
            if _is_http_response:
                service.response = None
            else:
                service.response = Response()

            # call method
            if _is_http_request:
                returns = await f(service, http_request)
            else:
                returns = await f(service, **params)

            # process response
            if _is_http_response:
                return returns
            else:
                if returns_validator is not None:
                    try:
                        returns = returns_validator(returns)
                    except Invalid as ex:
                        raise InvalidResult(str(ex))
                service.response.result = returns
                return service.response.to_http()

        return wrapper

    async def _parse_request(self, http_request):
        prefix = 'hrpc-'
        headers = {}
        for k, v in http_request.headers.items():
            k = k.lower()
            if k.startswith(prefix):
                headers[k[len(prefix):]] = v
        try:
            params = await http_request.json()
        except BadRequest as ex:
            raise InvalidRequest(ex.message) from ex
        LOG.debug(params)
        return headers, params


class Method:

    def __init__(
        self, *,
        service_name,
        service_class,
        method_info,
    ):
        self.service_name = service_name
        self.service_class = service_class
        self.name = method_info.name
        self.handler = method_info.f
        self.tags = method_info.tags
        self.doc = method_info.doc
        self.is_http_request = method_info.is_http_request
        self.is_http_response = method_info.is_http_response
        self.params = method_info.params
        self.returns = method_info.returns
        self.raises = method_info.raises

    def __repr__(self):
        return f'<Method {self.service_name}.{self.name}>'

    async def __call__(self, context, http_request):
        service = self.service_class()
        service.context = context
        return await self.handler(service, http_request)
