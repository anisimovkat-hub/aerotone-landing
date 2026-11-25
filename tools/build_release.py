#!/usr/bin/env python3
"""Build a client handoff with a deliberately small public allowlist. No dependencies."""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import zipfile
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_FILES = ('index.html', 'privacy.html', 'styles.css', 'preview.js', 'lead-form.js', 'robots.txt')


def site_origin(value):
    parsed = urlsplit(value)
    if (parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port
            or parsed.query or parsed.fragment or parsed.path not in ('', '/')
            or not parsed.hostname or not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', parsed.hostname)
            or '..' in parsed.hostname or '.' not in parsed.hostname):
        raise ValueError('Use an HTTPS origin, e.g. https://b2b.aerotone.ru, without a path')
    return 'https://' + parsed.hostname


def lead_endpoint(value):
    if value == '' or value == '/api/leads':
        return value
    parsed = urlsplit(value)
    if (parsed.scheme != 'https' or parsed.username or parsed.password or not parsed.hostname
            or parsed.query or parsed.fragment or parsed.path != '/api/leads'):
        raise ValueError('Endpoint must be /api/leads or an HTTPS URL ending in /api/leads')
    return value


def copy_file(source, destination):
    if source.is_symlink():
        raise ValueError('Symlinks are not allowed in release inputs: ' + str(source))
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def build(output, url, endpoint='', forms_approved=False, revision=None):
    origin, endpoint = site_origin(url), lead_endpoint(endpoint)
    if endpoint and not forms_approved:
        raise ValueError('Enable the endpoint only with --forms-approved after CRM/legal acceptance')
    output = Path(output).resolve()
    if output.exists():
        raise ValueError('Output already exists; choose a new empty release directory')
    if output == ROOT or ROOT in output.parents and output.parts[len(ROOT.parts)] != 'dist':
        raise ValueError('Inside the repository, releases belong under dist/')
    output.mkdir(parents=True)
    public = output / 'public'
    public.mkdir()
    for name in PUBLIC_FILES:
        copy_file(ROOT / name, public / name)
    for file in sorted((ROOT / 'assets').rglob('*')):
        if file.is_symlink():
            raise ValueError('Symlink in assets')
        if file.is_file() and file.suffix.lower() in ('.jpg', '.jpeg', '.png', '.svg', '.woff2', '.txt') and not file.name.startswith('.'):
            copy_file(file, public / file.relative_to(ROOT))
    copy_file(ROOT / 'deployment/apache.htaccess', public / '.htaccess')
    original = (ROOT / 'lead-config.js').read_text(encoding='utf-8')
    consent = re.search(r"consentVersion:\s*['\"]([^'\"]+)['\"]", original).group(1)
    settings = {'endpoint': endpoint, 'consentVersion': consent, 'metrikaId': ''}
    (public / 'lead-config.js').write_text('// Public settings only. Never place CRM tokens here.\nwindow.AEROTONE_LEADS = Object.freeze(' + json.dumps(settings, ensure_ascii=False, indent=2) + ');\n', encoding='utf-8')
    for name in ('index.html', 'privacy.html'):
        path = public / name
        html = path.read_text(encoding='utf-8')
        if '<meta name="robots" content="noindex, nofollow">' not in html:
            raise ValueError('Missing noindex in ' + name)
        canonical = origin + ('/' if name == 'index.html' else '/privacy.html')
        html = html.replace('</head>', '  <link rel="canonical" href="' + canonical + '">\n  <meta property="og:url" content="' + canonical + '">\n</head>')
        path.write_text(html, encoding='utf-8')
    for name in ('lead_server.py', 'test_leads.py', '.env.example', 'README.md'):
        copy_file(ROOT / 'integration' / name, output / 'backend' / name)
    for name in ('nginx-landing.conf.example', 'aerotone-leads.service', 'HANDOFF.md'):
        copy_file(ROOT / 'deployment' / name, output / name)
    if revision is None:
        revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    manifest = {'source_repository': 'https://github.com/anisimovkat-hub/aerotone-landing',
                'source_revision': revision, 'site_url': origin + '/', 'endpoint_enabled': bool(endpoint),
                'forms_approved': forms_approved, 'indexing': 'noindex, nofollow', 'files': {}}
    for path in sorted(output.rglob('*')):
        if path.is_file():
            manifest['files'][path.relative_to(output).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    archive = output.with_suffix('.zip')
    if archive.exists():
        raise ValueError('Archive already exists: ' + str(archive))
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(output.rglob('*')):
            if path.is_file():
                bundle.write(path, path.relative_to(output))
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.zip.sha256').write_text(checksum + '  ' + archive.name + '\n', encoding='utf-8')
    return archive


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site-url', required=True)
    parser.add_argument('--output', default='dist/client-handoff')
    parser.add_argument('--endpoint', default='')
    parser.add_argument('--forms-approved', action='store_true')
    args = parser.parse_args()
    try:
        print(build(args.output, args.site_url, args.endpoint, args.forms_approved))
    except (ValueError, OSError) as error:
        parser.error(str(error))
