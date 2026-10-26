"""Pure staged-update contracts. These functions never publish or install."""
import re
from tools.release_policy import REPOSITORY, FEED_URL, plan_for_build, SHA

CHANNELS = ('stable', 'dev')
DEV_CHECKS = (
    'test_hub.py', 'test_scoped_backups.py', 'test_setup_api.py',
    'test_setup_service.py', 'test_setup_ui.py', 'test_update_channels.py',
    'test_channel_release.py', 'test_update_feed.py',
    'test_signing_identity.py',
    'test_local_dev.py',
)
ACCEPTANCE_CASES = {'permissions', 'configuration', 'install_update', 'backup', 'channels'}


def require_channel(channel):
    if channel not in CHANNELS:
        raise ValueError('unsupported_update_channel')
    return channel


def feed_url(channel):
    require_channel(channel)
    if channel == 'stable':
        return FEED_URL
    return f'https://github.com/{REPOSITORY}/releases/download/repohub-channel-{channel}/appcast.xml'


def channel_plan(build, revision, channel):
    require_channel(channel)
    if channel == 'stable':
        raise ValueError('stable_is_promotion_only')
    return dict(plan_for_build(build, revision), schema=2, channel=channel)


def validate_channel_receipt(receipt):
    if not isinstance(receipt, dict) or receipt.get('schema') != 2:
        raise ValueError('channel_receipt_required')
    raw = receipt.get('build')
    if not isinstance(raw, str) or not re.fullmatch('[1-9][0-9]*', raw):
        raise ValueError('positive_build_required')
    revision = receipt.get('source_revision')
    if not isinstance(revision, str) or not SHA.fullmatch(revision):
        raise ValueError('exact_source_revision_required')
    expected = channel_plan(int(raw), revision, receipt.get('channel'))
    if any(receipt.get(key) != value for key, value in expected.items()):
        raise ValueError('channel_receipt_mismatch')
    if (receipt.get('test_only') is not False
            or receipt.get('distribution') not in ('personal_adhoc', 'developer_id')
            or receipt.get('notarized') is not (receipt.get('distribution') == 'developer_id')
            or not re.fullmatch('[a-f0-9]{64}', str(receipt.get('archive_sha256', '')))
            or type(receipt.get('archive_bytes')) is not int or receipt['archive_bytes'] <= 0):
        raise ValueError('verified_channel_archive_required')
    return receipt


def require_github_run(run, jobs, revision):
    branch = run.get('head_branch', '')
    if (not isinstance(branch, str) or not (branch == 'main' or branch.startswith('codex/'))
            or run.get('event') != 'push' or run.get('status') != 'completed'
            or run.get('conclusion') != 'success'
            or run.get('path') != '.github/workflows/golden-rules.yml'
            or run.get('repository', {}).get('full_name') != REPOSITORY
            or run.get('head_repository', {}).get('full_name') != REPOSITORY
            or run.get('head_sha') != revision or not SHA.fullmatch(revision)):
        raise ValueError('exact_successful_github_run_required')
    contracts = [job for job in jobs if job.get('name') == 'automated-contract']
    if (len(contracts) != 1 or contracts[0].get('conclusion') != 'success'
            or contracts[0].get('status') != 'completed'):
        raise ValueError('exact_successful_github_run_required')


def require_focused_gate(gate, revision):
    if (gate.get('profile') != 'dev' or gate.get('result') != 'passed'
            or gate.get('source_commit') != revision or gate.get('dirty_source') is not False
            or gate.get('source_unchanged') is not True
            or gate.get('patterns') != list(DEV_CHECKS)
            or gate.get('skipped') != 0 or not gate.get('tests_run', 0)
            or gate.get('native_build') is not True
            or not re.fullmatch('[a-f0-9]{64}', str(gate.get('source_digest', '')))):
        raise ValueError('exact_focused_dev_gate_required')


def require_full_gate(gate, revision):
    from tools.publish_release import require_gate
    from tools.release_gate import REGISTER, validate_register
    import json
    require_gate(gate, revision)
    registered = validate_register(json.loads(REGISTER.read_text()))
    python = gate.get('python', {})
    commands = {row.get('check'): row.get('result') for row in gate.get('commands', [])}
    rules = {row.get('id'): row.get('result') for row in gate.get('rules', [])}
    required_commands = {'native-app-build', 'coordinated-sparkle-package',
                         'github-workflow-syntax', 'bridge-checks', 'updater-settings-checks'}
    if (python.get('successful') is not True or python.get('skipped') != 0
            or not python.get('tests_run', 0)
            or any(commands.get(name) != 'passed' for name in required_commands)
            or any(row.get('result') != 'passed' for row in gate.get('commands', []))
            or any(rules.get(rule['id']) != 'passed' for rule in registered)
            or any(python.get('outcomes', {}).get(name) != 'passed'
                   for rule in registered for name in rule['test_ids'])):
        raise ValueError('complete_executed_macos_gate_required')


def require_acceptance(value, receipt, pro_only_exception=None):
    validate_channel_receipt(receipt)
    if (not isinstance(value, dict) or value.get('schema') != 1
            or value.get('source_revision') != receipt['source_revision']
            or value.get('build') != receipt['build']
            or value.get('archive_sha256') != receipt['archive_sha256']):
        raise ValueError('exact_package_native_acceptance_required')
    scope = 'pro_and_air'
    required_hosts = ('pro', 'air')
    if pro_only_exception is not None:
        expected = {'kind': 'pro_only_once', 'tag': receipt['tag']}
        if pro_only_exception != receipt['tag'] or value.get('exception') != expected:
            raise ValueError('explicit_exact_release_pro_only_exception_required')
        scope = 'pro_only_exception'
        required_hosts = ('pro',)
    for host in required_hosts:
        hosts = value.get('hosts')
        if not isinstance(hosts, dict):
            raise ValueError('both_macs_native_acceptance_required')
        results = hosts.get(host, {})
        required = ACCEPTANCE_CASES | ({'onboarding'} if host == 'air' else set())
        if (not isinstance(results, dict) or not required.issubset(results)
                or any(results[key] != 'passed' for key in required)):
            raise ValueError('both_macs_native_acceptance_required')
    if receipt['distribution'] != 'developer_id' or receipt['notarized'] is not True:
        raise ValueError('stable_requires_notarized_developer_id')
    return scope


def require_promotion(current, target):
    require_channel(current)
    require_channel(target)
    if (current, target) != ('dev', 'stable'):
        raise ValueError('sequential_channel_promotion_required')


def validation_record(github_passed=False, installed_passed=False):
    if installed_passed and not github_passed:
        raise ValueError('github_checks_required_before_installed_acceptance')
    return {'local_checks': 'passed',
            'github_checks': 'passed' if github_passed else 'pending',
            'installed_acceptance': 'passed' if installed_passed else 'pending'}


def require_qualification(proof):
    if (proof.get('validation') != validation_record(True)
            or type(proof.get('github_run_id')) is not int or proof['github_run_id'] <= 0):
        raise ValueError('exact_candidate_github_qualification_required')
    return proof['github_run_id']
