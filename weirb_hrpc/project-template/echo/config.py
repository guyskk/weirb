from validr import T


class Config:
    echo_times = T.int.min(1).default(1)


plugins = []
validators = {}
