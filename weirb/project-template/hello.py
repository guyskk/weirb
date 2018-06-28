from validr import T


class HelloService:
    """A Simple Hello"""
    async def method_say(
        self,
        name: T.str.maxlen(10).default('world')
    ) -> T.dict(message=T.str):
        """Say Hello"""
        return dict(message=f'hello {name}!')
