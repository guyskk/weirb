import json
import datetime
from pathlib import Path
from mako.template import Template

from ..error import BUILTIN_HRPC_ERRORS

_here = Path(__file__).parent

INTRO_MD = _here / 'intro.md.mako'
SERVICE_MD = _here / 'service.md.mako'
ERRORS_MD = _here / 'errors.md.mako'

CONTENT_DIR = Path('docs') / 'content'


class HrpcGenerator:

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
        self.services = []
        builtin_errors = set(BUILTIN_HRPC_ERRORS)
        service_errors = set()
        for s in self.app.services:
            methods = []
            for m in s.methods:
                service_errors.update(m.raises)
                methods.append({
                    'name': m.name,
                    'doc': m.doc,
                    'params': None if m.params is None else str(m.params),
                    'returns': None if m.returns is None else str(m.returns),
                    'raises': self._format_errors(m.raises),
                })
            self.services.append({
                'name': s.name,
                'doc': s.doc,
                'methods': methods,
            })
        service_errors -= builtin_errors
        self.builtin_errors = self._format_errors(builtin_errors)
        self.service_errors = self._format_errors(service_errors)

    def _format_errors(self, errors):
        return [{'code': e.code, 'doc': e.__doc__ or ''} for e in errors]

    def _get_meta(self):
        meta = {
            'name': self.name,
            'intro': self.intro,
            'date': self.date,
            'services': self.services,
            'builtin_errors': self.builtin_errors,
            'service_errors': self.service_errors,
        }
        return meta

    def _write(self, path, text):
        if not CONTENT_DIR.exists():
            raise FileNotFoundError(f"Directory '{CONTENT_DIR}' not exists")
        Path(path).parent.mkdir(exist_ok=True)
        with open(path, 'w') as f:
            f.write(text)

    def gen_meta(self):
        meta = self._get_meta()
        text = json.dumps(meta, ensure_ascii=False, indent=4)
        self._write(CONTENT_DIR / 'meta.json', text)

    def gen_docs(self):
        meta = self._get_meta()
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
        # errors
        errors_tmpl = Template(filename=str(ERRORS_MD))
        text = errors_tmpl.render(**meta)
        self._write(CONTENT_DIR / 'errors' / 'errors.md', text)
