import re
import textwrap
from validr import T

from .app import App
from .service import Method, route


class _DocumentSampleService:
    """A Simple Hello

    Creates a channel from a multiprocessing Connection. Note: The
    multiprocessing connection is detached by having its handle set to None.
    """

    @route.get('/document/sample/a')
    async def view_a(self):
        """A simple view"""

    async def method_a(self):
        """A Simple Hello"""

    async def method_b(
        self,
        name: T.str.maxlen(10).optional.desc('姓名'),
        language: T.str.default('CN').desc('语言'),
    ):
        """
        A Simple Hello

        Creates a channel from a multiprocessing Connection. Note: The
        multiprocessing connection is detached by having its handle set to None.
        """

    async def method_c(self) -> T.str.maxlen(100).desc('欢迎消息'):
        """
        Creates a channel from a multiprocessing Connection. Note: The
        multiprocessing connection is detached by having its handle set to None.
        """

    async def method_d(
        self,
        name: T.str.maxlen(10).optional.desc('姓名'),
        language: T.str.default('CN').desc('语言'),
    ) -> T.dict(
        name=T.str.maxlen(10).optional.desc('姓名'),
        email=T.email.optional.desc('邮箱'),
        sex=T.bool.desc('性别'),
        message=T.str.maxlen(100).desc('欢迎消息'),
    ):
        """A Simple Hello

        Creates a channel from a multiprocessing Connection. Note: The
        multiprocessing connection is detached by having its handle set to None.

        This method can be used to make curio talk over Pipes as created by
        multiprocessing.  For example:

            p1, p2 = multiprocessing.Pipe()
            p1 = Connection.from_Connection(p1)
            p2 = Connection.from_Connection(p2)

        """


NEW_LINE = re.compile('\r?\n\r?\n')


def _format_head(doc):
    parts = NEW_LINE.split(doc, maxsplit=1)
    first_line = textwrap.dedent(parts[0]).strip()
    last = ''
    if len(parts) >= 2:
        last = textwrap.dedent(parts[1]).strip()
    if not first_line:
        return f''
    if not last:
        return f'\n{first_line}\n'
    else:
        return f'\n{first_line}\n\n{last}\n'


def format_service_doc(service):
    head = _format_head(service.doc)
    if service.handlers:
        handlers = ', '.join(m.name for m in service.handlers)
        handlers = f'Handlers: {handlers}\n'
    else:
        handlers = f'Handlers: No Handlers\n'
    return f'{head}\n{handlers}'


def format_handler_doc(handler):
    ret = [
        _format_head(handler.doc),
    ]
    if isinstance(handler, Method):

        if handler.params is None:
            params = ['Params: No Params\n']
        else:
            params = ['Params:\n']
            for k, v in handler.params.items.items():
                params.append(f'    {k}: {v.repr()}\n')
        ret.append(''.join(params))

        if handler.returns is None:
            returns = ['Returns: No Returns\n']
        else:
            if handler.returns.validator == 'dict':
                returns = ['Returns:\n']
                for k, v in handler.returns.items.items():
                    returns.append(f'    {k}: {v.repr()}\n')
            else:
                returns = [f'Returns: {handler.returns.repr()}\n']
        ret.append(''.join(returns))

    if not handler.raises:
        raises = ['Raises: No Raises\n']
    else:
        raises = ['Raises:\n']
        for error in handler.raises:
            raises.append(f'    {error.code}\n')
    ret.append(''.join(raises))

    return '\n'.join(ret)


def main():
    app = App(__name__)
    service = app.services[0]
    print(format_service_doc(service))
    for handler in service.handlers:
        print('-' * 60)
        print(format_handler_doc(handler))


if __name__ == '__main__':
    main()
