import sys

from .error import DependencyError
from .compat.contextlib import AsyncExitStack


class Context:
    def __init__(self, app):
        self.config = app.config
        self.request = None
        self.response = None
        self._config = app._config_dict
        self._scopes = app._scopes
        self._contexts = [c(self) for c in app.contexts]
        self._handler = app._handler
        self._container = {}
        self._providers = {}

    def require(self, key):
        if key in self._config:
            return self._config[key]
        if key in self._container:
            return self._container[key]
        if key in self._providers:
            value = self._providers[key](self)
        elif key in self._scopes:
            value = self._scopes[key].instance(self)
        else:
            raise DependencyError(f"dependency {key!r} not exists")
        self._container[key] = value
        return value

    def provide(self, key, value, *, lazy=False):
        if lazy:
            self._providers[key] = value
        else:
            self._container[key] = value

    async def __call__(self, raw_request):
        return await self._handler(self, raw_request)

    async def __aenter__(self):
        self._stack = await AsyncExitStack().__aenter__()
        try:
            for ctx in self._contexts:
                await self._stack.enter_async_context(ctx)
        except BaseException:
            await self._stack.__aexit__(*sys.exc_info())
            raise
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return await self._stack.__aexit__(exc_type, exc, tb)
