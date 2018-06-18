from validr import T
from weirb_hrpc import App, require


class DemoService:

    debug = require('config.debug')

    async def method_echo(self, text: T.str) -> T.dict(text=T.str):
        """A echo method"""
        if self.debug:
            print(f'> {text}')
        self.response.headers['echo'] = 123
        return dict(text=text)


app = App(__name__, debug=True)


if __name__ == '__main__':
    app.run()
