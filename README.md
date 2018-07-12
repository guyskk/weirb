# Weirb

[![travis-ci](https://api.travis-ci.org/guyskk/weirb.svg)](https://travis-ci.org/guyskk/weirb) [![codecov](https://codecov.io/gh/guyskk/weirb/branch/master/graph/badge.svg)](https://codecov.io/gh/guyskk/weirb)

Weird async web framework based on Newio!

## Overview

```python
from validr import T

class HelloService:
    async def do_say(
        self, name: T.str.maxlen(10).default("world")
    ) -> T.dict(message=T.str):
        return {"message": f"hello {name}!"}
```

Save as `hello.py`!

Run it `weirb serve --name hello --debug`!

Play in shell `weirb shell --name hello --debug`:

```
Wb> call('/hello/say', name='guyskk')

200 OK
Content-Length: 34
Content-Type: application/json;charset=utf-8

{
    "message": "hello guyskk!"
}
```

## Install

Note: Python 3.6+

```
pip install weirb
```

## Document

https://github.com/guyskk/weirb/wiki
