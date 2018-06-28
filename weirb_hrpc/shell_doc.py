import re
import textwrap
from validr import T, Compiler

from .service import Service


class _DocumentSampleService:
    """A Simple Hello

    Creates a channel from a multiprocessing Connection. Note: The
    multiprocessing connection is detached by having its handle set to None.
    """

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
    if service.methods:
        methods = ', '.join(m.name for m in service.methods)
        methods = f'Methods: {methods}\n'
    else:
        methods = f'Methods: No Methods\n'
    return f'{head}\n{methods}'


def format_method_doc(method):
    head = _format_head(method.doc)

    if method.is_http_request:
        params = ['Params: HttpRequest\n']
    elif method.params is None:
        params = ['Params: No Params\n']
    else:
        params = ['Params:\n']
        for k, v in method.params.items.items():
            params.append(f'    {k}: {v.repr()}\n')
    params = ''.join(params)

    if method.is_http_response:
        returns = ['Returns: HttpResponse\n']
    elif method.returns is None:
        returns = ['Returns: No Returns\n']
    else:
        if method.returns.validator == 'dict':
            returns = ['Returns:\n']
            for k, v in method.returns.items.items():
                returns.append(f'    {k}: {v.repr()}\n')
        else:
            returns = [f'Returns: {method.returns.repr()}\n']
    returns = ''.join(returns)

    if not method.raises:
        raises = ['Raises: No Raises\n']
    else:
        raises = ['Raises:\n']
        for error in method.raises:
            raises.append(f'    {error.code}\n')
    raises = ''.join(raises)

    return f'{head}\n{params}\n{returns}\n{raises}'


def main():
    service = Service(_DocumentSampleService, {}, [], Compiler())
    print(format_service_doc(service))
    for method in service.methods:
        print('-' * 60)
        print(format_method_doc(method))


if __name__ == '__main__':
    main()
