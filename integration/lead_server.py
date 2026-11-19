"""Receiving adapter. Python 3.9+, no third-party dependencies.
Deploy behind HTTPS on the client-approved Russian server; see README.md.
"""
import hashlib
import hmac
import json
import os
import re
import sqlite3
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def normalize_email(value):
    parts = value.split('@')
    if len(parts) != 2 or len(parts[0]) > 64:
        raise ValueError('Invalid email')
    local, domain = parts
    labels = domain.split('.')
    if (not re.fullmatch(r"[a-zA-Z0-9!#$%&'*+/=?^_`{|}~.-]+", local)
            or local.startswith('.') or local.endswith('.') or '..' in local
            or len(labels) < 2
            or any(not re.fullmatch(r'[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?', label) for label in labels)
            or not re.fullmatch(r'(?:[a-zA-Z]{2,63}|xn--[a-zA-Z0-9-]{2,59})', labels[-1])
            or labels[-1].lower() in ('invalid', 'test', 'localhost')):
        raise ValueError('Invalid email')
    return local + '@' + domain.lower()


def normalize_phone(value):
    digits = re.sub(r'[^0-9]', '', value)
    if len(digits) == 10 and digits.startswith('9'):
        digits = '7' + digits
    if len(digits) == 11 and digits.startswith('8') and not value.startswith('+'):
        digits = '7' + digits[1:]
    russian = digits.startswith('7')
    length_valid = len(digits) == 11 if russian else value.startswith('+') and bool(re.fullmatch(r'[1-9][0-9]{7,14}', digits))
    if (not re.fullmatch(r'[+]?[0-9 ()-]+', value) or not length_valid
            or re.fullmatch(r'([0-9])\1+', digits[1:])
            or digits in ('1234567890', '12345678901', '9876543210')):
        raise ValueError('Invalid phone')
    return '+' + digits


class LeadService:
    def __init__(self, database, domain, token, pipeline, origin, page, consent, context_field):
        if not re.fullmatch(r'[a-z0-9-]+\.amocrm\.ru', domain):
            raise ValueError('AMO_DOMAIN must be the client account host')
        if not token or not pipeline or not origin.startswith('https://'):
            raise ValueError('Configure token, pipeline and HTTPS origin')
        self.database, self.domain, self.token = database, domain, token
        self.pipeline, self.origin, self.page, self.consent = int(pipeline), origin, page, consent
        self.context_field = int(context_field)
        if self.context_field <= 0:
            raise ValueError('Configure AMO_CONTEXT_FIELD_ID')
        Path(database).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS requests (
                id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, state TEXT NOT NULL,
                created INTEGER NOT NULL, consent TEXT NOT NULL, receipt TEXT)''')
            db.execute('CREATE TABLE IF NOT EXISTS limits (key TEXT PRIMARY KEY, bucket INTEGER, count INTEGER)')
        os.chmod(database, 0o600)

    def connect(self):
        return sqlite3.connect(self.database, timeout=10)

    def validate(self, data):
        if not isinstance(data, dict) or data.get('website'):
            raise ValueError('Invalid submission')
        data = dict(data)
        data['request_id'] = str(uuid.UUID(data.get('request_id', '')))
        for key, maximum in [('name', 100), ('company', 160), ('email', 254), ('phone', 30)]:
            value = data.get(key, '')
            if not isinstance(value, str) or len(value) > maximum:
                raise ValueError('Invalid field')
            data[key] = value.strip()
        form_type = data.get('form_type', 'main')
        if form_type not in ('main', 'quiz'):
            raise ValueError('Invalid form type')
        if form_type == 'main' and (not data['name'] or not data['company']):
            raise ValueError('Required name and company')
        data['email'] = normalize_email(data['email'])
        data['phone'] = normalize_phone(data['phone'])
        if data.get('consent') is not True or data.get('consent_version') != self.consent:
            raise ValueError('Consent required')
        if data.get('page') != self.page:
            raise ValueError('Invalid page')
        if data.get('trips', '') not in ('', 'q1', 'q2', 'q3', 'q4'):
            raise ValueError('Invalid trip count')
        allowed = {'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term', 'yclid'}
        attribution = data.get('attribution', {})
        if not isinstance(attribution, dict) or any(k not in allowed or not isinstance(v, str) or len(v) > 300 for k, v in attribution.items()):
            raise ValueError('Invalid attribution')
        quiz = data.get('quiz', {})
        options = {'1': ['2', '7', '20', '40'], '2': ['ru', 'cis', 'world', 'mix'], '3': ['short', 'mid', 'long'],
                   '4': ['self', 'office', 'agency', 'platform'], '5': ['manual', 'part', 'edo'], '6': ['none', 'manual', 'auto']}
        if not isinstance(quiz, dict) or any(k not in options or v not in options[k] for k, v in quiz.items()):
            raise ValueError('Invalid quiz')
        if form_type == 'quiz' and set(quiz) != set(options):
            raise ValueError('Quiz must be complete')
        return data

    def rate_allowed(self, ip):
        # A short-lived hash is sufficient for per-address rate limiting.
        bucket = int(time.time() // 3600)
        key = hashlib.sha256((str(bucket) + ip).encode()).hexdigest()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM limits WHERE bucket < ?', (bucket,))
            db.execute('INSERT OR IGNORE INTO limits VALUES (?, ?, 0)', (key, bucket))
            db.execute('UPDATE limits SET count = count + 1 WHERE key = ?', (key,))
            return db.execute('SELECT count FROM limits WHERE key = ?', (key,)).fetchone()[0] <= 20

    def deliver(self, data):
        contact_fields = [{'field_code': 'EMAIL', 'values': [{'value': data['email'], 'enum_code': 'WORK'}]}]
        if data['phone']:
            contact_fields.append({'field_code': 'PHONE', 'values': [{'value': data['phone'], 'enum_code': 'WORK'}]})
        # A client-configured text area keeps the complete approved submission context.
        context = json.dumps({'trips': data.get('trips'), 'quiz': data.get('quiz'),
                              'attribution': data.get('attribution'), 'consent_version': self.consent, 'form_type': data.get('form_type', 'main')}, ensure_ascii=False)
        payload = [{
            'source_name': 'Аэротон — лендинг', 'source_uid': data['request_id'],
            'request_id': data['request_id'], 'pipeline_id': self.pipeline,
            'metadata': {'form_id': 'aerotone-landing', 'form_name': 'Демо Аэротона',
                         'form_page': self.page, 'form_sent_at': int(time.time())},
            '_embedded': {
                'leads': [{'name': 'Аэротон — ' + (data['company'] or 'Предложение по опросу') + ' — ' + data['request_id'],
                           'custom_fields_values': [{'field_id': self.context_field, 'values': [{'value': context}]}]}],
                'contacts': [{'name': data['name'] or 'Заявка с лендинга', 'custom_fields_values': contact_fields}],
                'companies': [{'name': data['company']}] if data['company'] else [],
            },
        }]
        req = Request('https://' + self.domain + '/api/v4/leads/unsorted/forms',
                      data=json.dumps(payload).encode(), method='POST',
                      headers={'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json'})
        with urlopen(req, timeout=12) as response:
            result = json.load(response)['_embedded']['unsorted'][0]
            if result.get('request_id') != data['request_id'] or not result.get('uid'):
                raise ValueError('Unconfirmed CRM response')
            return result['uid']

    def submit(self, raw):
        try:
            data = self.validate(raw)
        except (ValueError, TypeError, AttributeError):
            return 400, {'status': 'invalid'}
        request_id = data['request_id']
        fingerprint = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT fingerprint, state FROM requests WHERE id=?', (request_id,)).fetchone()
            if row:
                if not hmac.compare_digest(row[0], fingerprint):
                    return 409, {'status': 'conflict'}
                if row[1] == 'created':
                    return 200, {'status': 'created', 'request_id': request_id}
                if row[1] == 'rejected':
                    return 503, {'status': 'unavailable', 'request_id': request_id}
                return 202, {'status': 'pending', 'request_id': request_id}
            db.execute('INSERT INTO requests VALUES (?, ?, ?, ?, ?, NULL)',
                       (request_id, fingerprint, 'pending', int(time.time()), self.consent))
        # No automatic resending after an uncertain outcome. A timeout can follow CRM creation.
        state, receipt = 'uncertain', None
        try:
            receipt = self.deliver(data)
            state = 'created'
        except HTTPError as error:
            if error.code in (400, 401, 403, 422, 429):
                state = 'rejected'
        except Exception:
            pass  # Deliberately exclude personal data and tokens from server logs.
        with self.connect() as db:
            db.execute('UPDATE requests SET state=?, receipt=? WHERE id=?', (state, receipt, request_id))
        if state == 'created':
            return 200, {'status': state, 'request_id': request_id}
        return 503, {'status': 'pending' if state == 'uncertain' else 'unavailable', 'request_id': request_id}


def make_handler(service):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def reply(self, code, body):
            self.send_response(code)
            if self.headers.get('Origin') == service.origin:
                self.send_header('Access-Control-Allow-Origin', service.origin)
            self.send_header('Vary', 'Origin')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps(body).encode())

        def do_OPTIONS(self):
            if self.path != '/api/leads' or self.headers.get('Origin') != service.origin:
                self.reply(403, {'status': 'forbidden'})
                return
            self.send_response(204)
            self.send_header('Access-Control-Allow-Origin', service.origin)
            self.send_header('Access-Control-Allow-Methods', 'POST')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            self.send_header('Vary', 'Origin')
            self.end_headers()

        def do_POST(self):
            self.connection.settimeout(10)
            if self.path != '/api/leads' or self.headers.get('Origin') != service.origin:
                self.reply(403, {'status': 'forbidden'})
                return
            if not service.rate_allowed(self.client_address[0]):
                self.reply(429, {'status': 'limited'})
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 12000 or self.headers.get_content_type() != 'application/json':
                    raise ValueError('Invalid request')
                payload = json.loads(self.rfile.read(length))
            except (ValueError, TimeoutError):
                self.reply(400, {'status': 'invalid'})
                return
            code, result = service.submit(payload)
            self.reply(code, result)
    return Handler


if __name__ == '__main__':
    service = LeadService(os.environ['LEADS_DB'], os.environ['AMO_DOMAIN'], os.environ['AMO_ACCESS_TOKEN'],
                          os.environ['AMO_PIPELINE_ID'], os.environ['ALLOWED_ORIGIN'],
                          os.environ['LANDING_URL'], os.environ['CONSENT_VERSION'], os.environ['AMO_CONTEXT_FIELD_ID'])
    ThreadingHTTPServer(('127.0.0.1', int(os.environ.get('PORT', '8787'))), make_handler(service)).serve_forever()
