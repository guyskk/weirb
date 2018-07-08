from copy import deepcopy


class Tagger:

    def __init__(self, namespace):
        self.namespace = namespace

    def get(self, key, default=None):
        def getter(f):
            if isinstance(f, dict):
                tags = f
            else:
                tags = getattr(f, self.namespace, {})
            return tags.get(key, default)
        return getter

    def tag(self, key, value):
        def decorator(f):
            if not hasattr(f, self.namespace):
                setattr(f, self.namespace, {})
            getattr(f, self.namespace)[key] = value
            return f
        return decorator

    def stackable_tag(self, key, value):
        def decorator(f):
            if not hasattr(f, self.namespace):
                setattr(f, self.namespace, {})
            getattr(f, self.namespace).setdefault(key, []).append(value)
            return f
        return decorator

    def is_tagged(self, f):
        if not callable(f):
            return False
        if not hasattr(f, '__dict__'):
            return False
        # check __dict__ other than use hasattr can skip objects with __getattr__
        return self.namespace in f.__dict__

    def get_tags(self, f):
        return deepcopy(getattr(f, self.namespace, {}))

    def set_tags(self, f, tags):
        setattr(f, self.namespace, tags)


tagger = Tagger('__weirb_tags__')
