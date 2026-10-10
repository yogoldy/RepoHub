"""User-initiated public issue delivery; credentials stay behind the native boundary."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import urllib.error
import urllib.request

REPOSITORY = 'yogoldy/RepoHub'
KEYCHAIN_SERVICE = 'com.leogoldberg.repohub.github'
MAX_BODY = 60000


class DeliveryError(Exception):
    def __init__(self, code, uncertain=False):
        self.code, self.uncertain = code, uncertain
        super().__init__(code)


def keychain_token():
    try:
        result = subprocess.run(['/usr/bin/security', 'find-generic-password', '-s', KEYCHAIN_SERVICE,
                                 '-a', 'github.com', '-w'], capture_output=True, text=True, timeout=10)
        token = result.stdout.strip() if result.returncode == 0 else ''
    except (OSError, subprocess.TimeoutExpired):
        token = ''
    if not token:
        raise DeliveryError('connection_required')
    return token


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class GitHubClient:
    def __init__(self, token_reader=keychain_token, repository=REPOSITORY):
        # The application always uses the fixed product tracker. Tests inject a
        # client, rather than letting HTTP callers redirect reports elsewhere.
        self.token_reader = token_reader
        self.repository = repository

    def request(self, method, endpoint, payload=None):
        token = self.token_reader()
        request = urllib.request.Request('https://api.github.com/' + endpoint,
            json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None,
            {'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json',
             'X-GitHub-Api-Version': '2022-11-28', 'Content-Type': 'application/json',
             'User-Agent': 'RepoHub-reports'}, method=method)
        try:
            with urllib.request.build_opener(NoRedirect).open(request, timeout=20) as response:
                data = response.read(8 * 1024 * 1024 + 1)
                if len(data) > 8 * 1024 * 1024:
                    raise DeliveryError('invalid_response', method == 'POST')
                return json.loads(data)
        except urllib.error.HTTPError as error:
            if error.code in (401, 403):
                raise DeliveryError('github_access_denied') from None
            if 400 <= error.code < 500 and error.code != 408:
                raise DeliveryError('github_rejected') from None
            raise DeliveryError('network_unavailable', method == 'POST') from None
        except (OSError, ValueError):
            raise DeliveryError('network_unavailable', method == 'POST') from None

    def account(self):
        value = self.request('GET', 'user')
        login = value.get('login') if isinstance(value, dict) else None
        if not isinstance(login, str) or not re.fullmatch(r'[A-Za-z0-9-]{1,39}', login):
            raise DeliveryError('invalid_response')
        return login

    def create(self, payload):
        return self.request('POST', 'repos/' + self.repository + '/issues', payload)

    def find(self, account, payload, marker):
        # Use the issue list, not eventually indexed search. If not found, an
        # ambiguous prior POST remains uncertain: absence is not retry permission.
        for page in range(1, 21):
            rows = self.request('GET', 'repos/' + self.repository + '/issues?state=all&creator=' +
                                account + '&sort=created&direction=desc&per_page=100&page=' + str(page))
            if not isinstance(rows, list):
                raise DeliveryError('invalid_response')
            for row in rows:
                if not isinstance(row, dict) or not isinstance(row.get('body') or '', str):
                    raise DeliveryError('invalid_response')
                if 'pull_request' not in row and marker in (row.get('body') or ''):
                    if row.get('title') != payload['title'] or row.get('body') != payload['body']:
                        raise DeliveryError('report_identity_conflict', True)
                    return row
            if len(rows) < 100:
                return None
        return None


def public_payload(draft):
    kind = draft['type']
    if kind not in ('bug', 'feature'):
        raise ValueError('Invalid report type')
    files = draft['files']
    if not isinstance(files, list) or len(files) > 2 or any(f['name'] not in ('schema.json','events.jsonl') for f in files):
        raise ValueError('Invalid diagnostic files')
    body = draft['body'] + '\n\nReport type: ' + kind
    for file in files:
        # JSON encoding prevents diagnostic strings from introducing markup.
        content = file['content']
        fence = '`' * (max([len(x) for x in re.findall(r'`+', content)] or [2]) + 1)
        body += '\n\n### ' + file['name'] + '\n' + fence + 'json\n' + content + '\n' + fence
    if len(body.encode('utf-8')) > MAX_BODY:
        raise ValueError('Report exceeds GitHub size limit; remove diagnostics and preview again')
    return {'title': ('[Bug] ' if kind == 'bug' else '[Feature] ') + draft['title'],
            'body': body, 'labels': ['bug' if kind == 'bug' else 'enhancement', 'from-app']}


def digest(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def private_write(path, value):
    tmp = path.with_name(path.name + '-' + secrets.token_hex(8))
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'w') as target:
            json.dump(value, target, ensure_ascii=False)
            target.flush(); os.fsync(target.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def read_private(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd) as source:
        raw = source.read(2 * 1024 * 1024 + 1)
    if len(raw) > 2 * 1024 * 1024:
        raise ValueError('Report too large')
    return json.loads(raw)


def case_path(state, report_id):
    if not isinstance(report_id, str) or not re.fullmatch(r'[a-f0-9]{24}', report_id):
        raise ValueError('Invalid report ID')
    parent = Path(state) / 'reports'
    case = parent / report_id
    if parent.is_symlink() or case.is_symlink() or not case.is_dir():
        raise ValueError('Report unavailable')
    return case


def receipt(row, payload, account, repository=REPOSITORY):
    if not isinstance(row, dict) or not isinstance(row.get('user'), dict):
        raise DeliveryError('invalid_receipt', True)
    number = row.get('number')
    expected_url = 'https://github.com/' + repository + '/issues/' + str(number)
    if type(number) is not int or number < 1 or row.get('html_url') != expected_url or \
       row.get('title') != payload['title'] or row.get('body') != payload['body'] or \
       str(row.get('user', {}).get('login', '')).lower() != account.lower() or 'pull_request' in row:
        raise DeliveryError('invalid_receipt', True)
    return {'state':'sent', 'issue_url':expected_url, 'issue_number':number, 'account':account,
            'payload_digest':digest(payload), 'error_code':None}


def delivery_status(state, report_id):
    case = case_path(state, report_id)
    draft = read_private(case / 'draft.json')
    value = read_private(case / 'delivery.json') if (case / 'delivery.json').exists() else {'state':'draft'}
    # Persisted sending is an uncertain outcome after a crash/restart.
    if value['state'] == 'sending': value['state'] = 'uncertain'
    return {'report_id':report_id, 'type':draft['type'], **value}


def connection_status(client=None):
    try:
        account = (client or GitHubClient()).account()
        return {'ready':True, 'account':account}
    except DeliveryError as error:
        return {'ready':False, 'error_code':error.code}


def send_report(state, payload, client=None, logger=None):
    def log(state, reason):
        if logger is None: return
        from diagnostics import diagnostic_ref
        try: logger.emit("report_delivery", report_ref=diagnostic_ref(payload.get("report_id")), state=state, reason=reason)
        except Exception: pass
    if set(payload) != {'report_id','preview_digest','account','confirm'} or payload['confirm'] is not True:
        raise ValueError('Send requires confirmation of the displayed preview')
    if not isinstance(payload['account'], str) or not re.fullmatch(r'[A-Za-z0-9-]{1,39}', payload['account']):
        raise ValueError('Invalid account')
    if not isinstance(payload['preview_digest'], str) or not re.fullmatch(r'[a-f0-9]{64}', payload['preview_digest']):
        raise ValueError('Invalid preview identity')
    case = case_path(state, payload['report_id'])
    client = client or GitHubClient()
    lock_fd = os.open(case / 'delivery.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        try: fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: return {'state':'sending','report_id':payload['report_id']}
        draft = read_private(case / 'draft.json')
        issue = public_payload(draft)
        identity = digest(issue)
        if draft.get('report_id') != payload['report_id'] or identity != payload['preview_digest']:
            raise ValueError('Preview changed; review the report again')
        path = case / 'delivery.json'
        previous = read_private(path) if path.exists() else {'state':'draft'}
        if previous.get('payload_digest', identity) != identity:
            raise ValueError('Delivery identity changed')
        if previous['state'] == 'sent': return delivery_status(state, payload['report_id'])
        attempted = previous['state'] in ('sending','uncertain')
        if attempted and previous.get('account') != payload['account']:
            raise ValueError('Check delivery using the original GitHub account')
        result = {'state':'uncertain' if attempted else 'failed', 'account':payload['account'],
                  'payload_digest':identity, 'error_code':None}
        try:
            account = client.account()
            if account != payload['account']:
                raise DeliveryError('account_changed', attempted)
            if attempted:
                row = client.find(account, issue, 'Report ID: ' + payload['report_id'])
                if row:
                    result = receipt(row, issue, account, client.repository)
                else:
                    result['error_code'] = 'delivery_unconfirmed'
            else:
                private_write(path, {**result, 'state':'sending'})
                log('sending', 'manual')
                try: row = client.create(issue)
                except DeliveryError as error:
                    result.update(state='uncertain' if error.uncertain else 'failed', error_code=error.code)
                else:
                    result = receipt(row, issue, account, client.repository)
        except DeliveryError as error:
            result.update(state='uncertain' if attempted or error.uncertain else 'failed', error_code=error.code)
        private_write(path, result)
        log(result['state'], result['error_code'] or 'report_confirmed')
        return delivery_status(state, payload['report_id'])
    finally:
        os.close(lock_fd)
