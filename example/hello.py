from validr import T


class HelloService:

    def method_say(
        self,
        name: T.str.maxlen(10).default('world')
    ) -> T.dict(message=T.str):
        """Say Hello"""
        return dict(message=f'hello {name}!')
