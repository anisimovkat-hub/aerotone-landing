import hashlib
import json
import re
import tempfile
import unittest
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

from build_release import build, site_origin


class References(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.noindex = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'meta' and attrs.get('name') == 'robots':
            self.noindex = 'noindex' in attrs.get('content', '').split(', ')
        for key in ('src', 'href'):
            if key in attrs:
                self.links.append(attrs[key])


class ReleaseTests(unittest.TestCase):
    def test_public_payload_complete_and_private_files_separate(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'handoff'
            archive = build(output, 'https://b2b.aerotone.ru', revision='test-version')
            public = output / 'public'
            for name in ('index.html', 'privacy.html'):
                parser = References()
                parser.feed((public / name).read_text())
                self.assertTrue(parser.noindex)
                for href in parser.links:
                    parsed = urlsplit(href)
                    if not parsed.scheme and not parsed.netloc and parsed.path:
                        self.assertTrue((public / parsed.path).is_file(), href)
            for href in re.findall(r'url\([\"\x27]?([^\)\"\x27]+)', (public / 'styles.css').read_text()):
                if not href.startswith(('data:', 'https:', 'http:')):
                    self.assertTrue((public / href.split('?')[0]).is_file(), href)
            self.assertNotIn('Disallow: /', (public / 'robots.txt').read_text())
            self.assertIn('X-Robots-Tag', (public / '.htaccess').read_text())
            self.assertIn('"endpoint": ""', (public / 'lead-config.js').read_text())
            manifest = json.loads((output / 'manifest.json').read_text())
            self.assertFalse(manifest['endpoint_enabled'])
            self.assertEqual(manifest['source_revision'], 'test-version')
            for name, digest in manifest['files'].items():
                self.assertEqual(hashlib.sha256((output / name).read_bytes()).hexdigest(), digest)
            with zipfile.ZipFile(archive) as bundle:
                self.assertIsNone(bundle.testzip())
                files = bundle.namelist()
                self.assertIn('backend/lead_server.py', files)
                self.assertFalse(any(n.startswith('public/') and (n.endswith('.py') or '.env' in n or '.sqlite' in n or '/.git/' in n) for n in files))
            self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(), archive.with_suffix('.zip.sha256').read_text().split()[0])

    def test_endpoint_requires_explicit_acceptance(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                build(Path(temp) / 'disabled', 'https://b2b.aerotone.ru', '/api/leads')
            output = Path(temp) / 'connected'
            build(output, 'https://b2b.aerotone.ru', '/api/leads', True, revision='test-version')
            self.assertIn('"endpoint": "/api/leads"', (output / 'public/lead-config.js').read_text())

    def test_existing_release_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'existing'
            output.mkdir()
            marker = output / 'keep'
            marker.write_text('keep')
            with self.assertRaises(ValueError):
                build(output, 'https://b2b.aerotone.ru')
            self.assertEqual(marker.read_text(), 'keep')

    def test_site_url_rejects_paths_secrets_insecure_scheme(self):
        for value in ('http://b2b.aerotone.ru', 'https://b2b.aerotone.ru/path',
                      'https://user:password@b2b.aerotone.ru', 'https://b2b.aerotone.ru?x=1'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                site_origin(value)


if __name__ == '__main__':
    unittest.main()
