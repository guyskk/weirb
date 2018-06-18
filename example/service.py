import os.path
from validr import T
from weirb_hrpc.error import HrpcError
from weirb import HttpResponse


class LoginFailed(HrpcError):
    error = 'User.LoginFailed'


class AuthPlugin:

    def __init__(self, database):
        self._database = database

    @property
    def provides(self):
        return ['user']

    @property
    def requires(self):
        return [self._database]

    def decorate(self, f):
        async def wrapper(service, *args, **kwargs):
            token = service.request.headers['auth_token']
            db = service.context.require(self._database)
            current_user = await db.query(token)
            service.context.provide('current_user', current_user)
            return f(service, *args, **kwargs)
        return wrapper


class MysqlPlugin:

    async def context(self, ctx):
        def connect():
            return 'connection'
        ctx.provide('mysql.connection', connect, lazy=True)
        try:
            yield
        finally:
            connection.close()


class UserService:

    db = require('database')
    timeit = require('timeit')
    auth = require('auth')
    user = require('auth.user')

    @raises(LoginFailed)
    @permission(None)
    async def method_login(
        self,
        username: T.str.maxlen(16),
        password: T.str.maxlen(16),
    ) -> T.dict(user_id=T.int, message=T.str):
        user = await self.db.query(username)
        if user is None:
            raise LoginFailed('incorrect username or password')
        if password != user.password:
            raise LoginFailed('incorrect username or password')
        auth_token = self.auth.generate_token(user)
        self.response.headers['auth_token'] = auth_token
        return dict(
            user_id=user.user_id,
            message='OK',
        )

    @raw_http_response
    @permission('login')
    async def method_download_avatar(self):
        avatar_path = self.user.avatar_path
        http_response = HttpResponse()
        http_response.headers['Content-Type'] = 'application/png'
        content_length = os.path.getsize(avatar_path)
        http_response.content_length = content_length

        async def _body_stream(self):
            with open(avatar_path, 'rb') as f:
                while True:
                    chunk = f.read(1024)
                    if not chunk:
                        break
                    yield chunk

        http_response.body = _body_stream()
        return http_response

    @raw_http_request
    @permission('login')
    async def method_upload_avatar(self, http_request):
        avatar = http_request.files[0]
        with open(avatar.path, 'wb') as f:
            async for chunk in avatar:
                f.write(chunk)
        self.user.avatar_path = avatar.path
        await self.db.save(self.user)
        return dict(message='OK')
