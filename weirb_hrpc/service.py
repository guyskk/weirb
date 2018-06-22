import inspect
import logging
from validr import T, Invalid
from weirb.error import BadRequest
from .request import Request
from .response import Response
from .error import InvalidRequest, InvalidParams, InvalidResult
from .tagger import tagger

http_request = tagger.tag('http_request', True)
is_http_request = tagger.get('http_request', default=False)
http_response = tagger.tag('http_response', True)
is_http_response = tagger.get('http_response', default=False)

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


def _make_service_class(base, fields):
    cls = type(base.__name__, (base,), fields)
    cls.__module__ = base.__module__
    cls.__name__ = base.__name__
    cls.__qualname__ = base.__qualname__
    cls.__doc__ = base.__doc__
    return cls


class Service:

    def __init__(self, service_class, provides, decorators, schema_compiler):
        self.name = service_class.__name__[:-len('Service')]
        self.decorators = decorators
        self.schema_compiler = schema_compiler
        methods, fields = self._parse_service(service_class, provides)
        self.fields = fields
        self.service_class = _make_service_class(service_class, fields)
        self.methods = []
        for name, f in methods.items():
            tags = tagger.get_tags(f)
            f = self._decorate(name, f)
            m = Method(self.name, self.service_class, name, f, tags)
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
                    fields[k] = DependencyField(k, v.key)
        return methods, fields

    def _decorate(self, method, f):
        origin = f
        tags = tagger.get_tags(f)
        f = self._hrpc_decorator(method, f)
        for d in self.decorators:
            f = d(f, tags)
        f.__name__ = origin.__name__
        f.__qualname__ = origin.__qualname__
        f.__module__ = origin.__module__
        f.__doc__ = origin.__doc__
        return f

    def _hrpc_decorator(self, method, f):
        _is_http_request = is_http_request(f)
        _is_http_response = is_http_response(f)
        if _is_http_request and _is_http_response:
            return f

        if _is_http_request:
            params_validator = None
        else:
            params_validator = self._get_params_validator(f)
        if _is_http_response:
            result_validator = None
        else:
            result_validator = self._get_result_validator(f)

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
                result = await f(service, http_request)
            else:
                result = await f(service, **params)

            # process response
            if _is_http_response:
                return result
            else:
                if result_validator is not None:
                    try:
                        result = result_validator(result)
                    except Invalid as ex:
                        raise InvalidResult(str(ex))
                service.response.result = result
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

    def _get_params_validator(self, f):
        sig = inspect.signature(f)
        params_schema = {}
        for name, p in sig.parameters.items():
            if p.annotation is not inspect.Parameter.empty:
                params_schema[name] = p.annotation
        if params_schema:
            return self.schema_compiler.compile(T.dict(params_schema))
        return None

    def _get_result_validator(self, f):
        sig = inspect.signature(f)
        if sig.return_annotation is not inspect.Signature.empty:
            schema = sig.return_annotation
            return self.schema_compiler.compile(schema)
        return None


class Method:

    def __init__(self, service_name, service_class, name, handler, tags):
        self.service_name = service_name
        self.service_class = service_class
        self.name = name
        self.handler = handler
        self.tags = tags
        self.is_http_request = is_http_request(tags)
        self.is_http_response = is_http_response(tags)

    def __repr__(self):
        return f'<Method {self.service_name}.{self.name}>'

    async def __call__(self, context, http_request):
        service = self.service_class()
        service.context = context
        return await self.handler(service, http_request)
