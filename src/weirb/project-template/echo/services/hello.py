from validr import T


class HelloService:
    """Hello World"""

    async def do_say(
        self, name: T.str.maxlen(10).default("world")
    ) -> T.dict(message=T.str):
        """Say Hello"""
        return {"message": f"hello {name}!"}
