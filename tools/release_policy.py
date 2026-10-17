"""Pure release decisions; no credentials, network calls or installation."""
import re

REPOSITORY = 'yogoldy/RepoHub'
FEED_URL = f'https://github.com/{REPOSITORY}/releases/latest/download/appcast.xml'
RETAIN_PACKAGES = 4  # Current plus three historical packages; Git tags remain.
TAG = re.compile(r'repohub-v(0\.[0-9]+\.[0-9])-b([1-9][0-9]*)')
SHA = re.compile(r'[0-9a-f]{40}')


def require_accepted_run(run, jobs, revision, main_revision):
    """Only an exact, successful main push from this repository may publish."""
    expected = (
        run.get('event') == 'push',
        run.get('head_branch') == 'main',
        run.get('status') == 'completed',
        run.get('conclusion') == 'success',
        run.get('path') == '.github/workflows/golden-rules.yml',
        run.get('repository', {}).get('full_name') == REPOSITORY,
        run.get('head_repository', {}).get('full_name') == REPOSITORY,
        run.get('head_sha') == revision == main_revision,
        bool(SHA.fullmatch(revision)),
    )
    contracts = [job for job in jobs if job.get('name') == 'automated-contract']
    if not all(expected) or len(contracts) != 1:
        raise ValueError('accepted_main_gate_required')
    if contracts[0].get('status') != 'completed' or contracts[0].get('conclusion') != 'success':
        raise ValueError('accepted_main_gate_required')


def release_number(release):
    match = TAG.fullmatch(release.get('tag_name', ''))
    return int(match[2]) if match else None


def release_plan(releases, revision):
    # Failed drafts reserve their number, avoiding accidental overwrite on retry.
    build = max((release_number(item) or 0 for item in releases), default=0) + 1
    return plan_for_build(build, revision)


def plan_for_build(build, revision):
    if type(build) is not int or build < 1 or not SHA.fullmatch(revision):
        raise ValueError('exact_source_and_positive_build_required')
    version = f'0.{build // 10}.{build % 10}'
    tag = f'repohub-v{version}-b{build}'
    archive = f'RepoHub-{version}-arm64.zip'
    return {
        'schema': 1, 'publisher': 'repohub-release', 'source_revision': revision,
        'version': version, 'build': str(build), 'tag': tag,
        'archive': archive, 'archive_url': f'https://github.com/{REPOSITORY}/releases/download/{tag}/{archive}',
        'feed_url': FEED_URL,
    }


def validate_receipt(release, receipt):
    build = release_number(release)
    if build is None:
        raise ValueError('managed_release_required')
    expected = plan_for_build(build, receipt.get('source_revision', ''))
    for field in ('schema', 'publisher', 'version', 'build', 'tag', 'archive', 'archive_url', 'feed_url'):
        if receipt.get(field) != expected[field]:
            raise ValueError('release_receipt_mismatch')
    if (receipt.get('test_only') is not False
            or not re.fullmatch(r'[0-9a-f]{64}', receipt.get('archive_sha256', ''))
            or type(receipt.get('archive_bytes')) is not int or receipt['archive_bytes'] <= 0):
        raise ValueError('production_archive_evidence_required')


def expired_releases(releases, current_tag):
    published = [item for item in releases if release_number(item) is not None
                 and not item.get('draft') and not item.get('prerelease')]
    published.sort(key=release_number, reverse=True)
    if not published or published[0]['tag_name'] != current_tag:
        raise ValueError('current_release_must_be_newest')
    return published[RETAIN_PACKAGES:]
