import inspect
import logging
from validr import T, Invalid
from weirb.error import BadRequest
from .response import Response
from .error import HrpcError, HrpcInvalidRequest, HrpcInvalidParams, HrpcServerError
from .tagger import tagger


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
        self.params = self._get_params(f)
        self.returns = self._get_returns(f)
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
            m = Method(self, method_info)
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
        origin = f = method_info.f
        for d in self.decorators:
            f = d(f, method_info)
        f.__name__ = origin.__name__
        f.__qualname__ = origin.__qualname__
        f.__module__ = origin.__module__
        f.__doc__ = origin.__doc__
        return f


class Method:

    def __init__(self, service, method_info):
        self.service = service
        self.service_name = service.name
        self.service_class = service.service_class
        self.name = method_info.name
        self.tags = method_info.tags
        self.doc = method_info.doc
        self.params = method_info.params
        self.returns = method_info.returns
        self.raises = method_info.raises
        self._handler = method_info.f
        self._params_validator = None
        if self.params is not None:
            self._params_validator = self._compile_schema(self.params)
        self._returns_validator = None
        if self.returns is not None:
            self._returns_validator = self._compile_schema(self.returns)

    def _compile_schema(self, schema):
        return self.service.schema_compiler.compile(schema)

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

    async def _call(self, service, context, request):
        service.context = context
        service.request = request
        service.response = Response(context)
        # prepare request
        if self._params_validator is not None:
            params = await self._parse_request(request)
            try:
                params = self._params_validator(params)
            except Invalid as ex:
                raise HrpcInvalidParams(str(ex)) from None
            returns = await self._handler(service, **params)
        else:
            returns = await self._handler(service)
        # process response
        if self._returns_validator is not None:
            try:
                returns = self._returns_validator(returns)
            except Invalid as ex:
                msg = f'Service return a invalid result: {ex}'
                raise HrpcServerError(msg)
            service.response.json(returns)
        return service.response

    async def _parse_request(self, request):
        try:
            params = await request.json()
        except BadRequest as ex:
            raise HrpcInvalidRequest(ex.message) from ex
        return params
