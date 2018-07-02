from .error import DependencyError


class Context:

    def __init__(self, app):
        self.config = app.config
        self._config = app._config_dict
        self._contexts = [c(self) for c in app.contexts]
        self._handler = app._handler
        self._container = {'config': app.config}
        self._providers = {}

    def require(self, key):
        if key.startswith('config.'):
            config_key = key[7:]
            if config_key not in self._config:
                raise DependencyError(f'dependency {key!r} not exists')
            return self._config[config_key]
        if key not in self._container:
            if key not in self._providers:
                raise DependencyError(f'dependency {key!r} not exists')
            self._container[key] = self._providers[key]()
        return self._container[key]

    def provide(self, key, value, *, lazy=False):
        if lazy:
            self._providers[key] = value
        else:
            self._container[key] = value

    async def __call__(self, raw_request):
        return await self._handler(self, raw_request)

    async def __aenter__(self):
        error = None
        for i, ctx in enumerate(self._contexts):
            try:
                ret = await ctx.asend(None)
            except StopAsyncIteration:
                error = RuntimeError(f'context {ctx} not yield')
            except BaseException as ex:
                error = ex
            else:
                if ret is not None:
                    msg = f'context {ctx} must not yield non-None value'
                    error = RuntimeError(msg)
            if error is not None:
                break
        if error is not None:
            current_error = error
            for ctx in reversed(self._contexts[:i]):
                try:
                    ret = await ctx.athrow(current_error)
                except StopAsyncIteration as stop:
                    pass  # ignore
                except BaseException as ex:
                    error = ex
                else:
                    error = RuntimeError(f'context {ctx} not stop after throw')
                if error is not current_error:
                    error.__cause__ = current_error
                    current_error = error
            raise current_error
        return self

    async def __aexit__(self, exc_type, exc, tb):
        current_error = error = exc
        for ctx in reversed(self._contexts):
            try:
                if current_error is not None:
                    await ctx.athrow(current_error)
                else:
                    await ctx.asend(None)
            except StopAsyncIteration as stop:
                pass  # ignore
            except BaseException as ex:
                error = ex
            else:
                error = RuntimeError(f'context {ctx} not stop after throw')
            if error is None:
                current_error = None
            else:
                if current_error is None:
                    current_error = error
                elif error is not current_error:
                    error.__cause__ = current_error
                    current_error = error
        if current_error is not exc:
            raise current_error
