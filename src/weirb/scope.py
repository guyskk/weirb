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


class Scope:
    def __init__(self, app, cls):
        self.name = cls.__module__ + "." + cls.__name__
        self.cls = cls
        self.app = app
        self._load_fields()
        self._load_scope_class()

    def __repr__(self):
        return f"<{type(self).__name__} {self.name}>"

    def instance(self, context):
        obj = self.scope_class()
        obj.context = context
        return obj

    def _load_fields(self):
        fields = {}
        requires = set()
        for cls in reversed(self.cls.__mro__):
            for k, v in vars(cls).items():
                if not isinstance(v, Dependency):
                    continue
                if inspect.isclass(v.key):
                    scope = self.app.create_scope(v.key)
                    fields[k] = DependencyField(k, v.key)
                    requires.update(scope.requires)
                else:
                    if v.key not in self.app.provides:
                        raise DependencyError(f"dependency {v.key!r} not exists")
                    fields[k] = DependencyField(k, v.key)
                    requires.add(v.key)
        self.requires = frozenset(requires)
        self.fields = fields

    def _load_scope_class(self):
        scope_class = type(self.cls.__name__, (self.cls,), self.fields)
        scope_class.__module__ = self.cls.__module__
        scope_class.__name__ = self.cls.__name__
        scope_class.__qualname__ = self.cls.__qualname__
        scope_class.__doc__ = self.cls.__doc__
        self.scope_class = scope_class
