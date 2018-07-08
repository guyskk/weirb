import json
import datetime
from pathlib import Path
from mako.template import Template

_here = Path(__file__).parent

INTRO_MD = _here / 'intro.md.mako'
SERVICE_MD = _here / 'service.md.mako'
CONTENT_DIR = Path('docs') / 'content'


class DocumentGenerator:

    def __init__(self, app):
        self.app = app
        self.name = self.app.import_name
        if self.app.intro:
            self.intro = self.app.intro
        else:
            self.intro = (
                f'# {self.app.import_name} #\n\n'
                f'No Doc\n\n'
            )
        self.date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.builtin_errors = self._format_errors(app.raises)
        self.services = []
        for s in self.app.services:
            handlers = []
            for h in s.handlers:
                routes = []
                for r in h.routes:
                    methods = ' '.join(r.methods)
                    routes.append(dict(path=r.path, methods=methods))
                params = None if h.params is None else str(h.params)
                returns = None if h.returns is None else str(h.returns)
                handler = {
                    'is_method': h.is_method,
                    'name': h.name,
                    'doc': h.doc,
                    'routes': routes,
                    'raises': self._format_errors(h.raises),
                    'params': params,
                    'returns': returns,
                }
                handlers.append(handler)
            self.services.append({
                'name': s.name,
                'doc': s.doc,
                'handlers': handlers,
            })

    def _format_errors(self, errors):
        return [{
            'status': e.status,
            'code': e.code,
            'doc': e.__doc__ or ''
        } for e in errors]

    def _get_meta(self):
        meta = {
            'name': self.name,
            'intro': self.intro,
            'date': self.date,
            'services': self.services,
            'builtin_errors': self.builtin_errors,
        }
        return meta

    def _write(self, path, text):
        if not CONTENT_DIR.exists():
            raise FileNotFoundError(f"Directory '{CONTENT_DIR}' not exists")
        Path(path).parent.mkdir(exist_ok=True)
        with open(path, 'w') as f:
            f.write(text)

    def gen(self):
        meta = self._get_meta()
        # meta
        text = json.dumps(meta, ensure_ascii=False, indent=4)
        self._write(CONTENT_DIR / 'meta.json', text)
        # intro
        intro_tmpl = Template(filename=str(INTRO_MD))
        text = intro_tmpl.render(**meta)
        self._write(CONTENT_DIR / 'intro' / 'intro.md', text)
        # services
        service_tmpl = Template(filename=str(SERVICE_MD))
        for service in self.services:
            name = service['name']
            text = service_tmpl.render(date=self.date, **service)
            self._write(CONTENT_DIR / 'services' / f'{name}.md', text)
