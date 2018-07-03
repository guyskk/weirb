import inspect

from .error import DependencyError


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


class ScopeField:
    def __init__(self, name, scope):
        self.name = name
        self.scope = scope

    def __get__(self, obj, obj_type):
        if obj is None:
            return self
        if self.name in obj.__dict__:
            return obj.__dict__[self.name]
        value = self.scope.instance(obj.context)
        obj.__dict__[self.name] = value
        return value


class Scope:
    def __init__(self, base, provides):
        self.name = base.__module__ + "." + base.__name__
        self.base = base
        self.provides = provides
        self._load_fields()
        self._load_cls()

    def __repr__(self):
        return f"<{type(self).__name__} {self.name}>"

    def instance(self, context):
        obj = self.cls()
        obj.context = context
        return obj

    def _load_fields(self):
        self.fields = {}
        for cls in reversed(self.base.__mro__):
            for k, v in vars(cls).items():
                if not isinstance(v, Dependency):
                    continue
                if inspect.isclass(v.key):
                    scope = Scope(v.key, self.provides)
                    self.fields[k] = ScopeField(k, scope)
                else:
                    if v.key not in self.provides:
                        raise DependencyError(f"dependency {v.key!r} not exists")
                    self.fields[k] = DependencyField(k, v.key)

    def _load_cls(self):
        cls = type(self.base.__name__, (self.base,), self.fields)
        cls.__module__ = self.base.__module__
        cls.__name__ = self.base.__name__
        cls.__qualname__ = self.base.__qualname__
        cls.__doc__ = self.base.__doc__
        self.cls = cls
