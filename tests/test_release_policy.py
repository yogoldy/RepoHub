import copy
import unittest
from tools.release_policy import (
    REPOSITORY, expired_releases, release_plan, require_accepted_run, validate_receipt,
)

SHA = 'a' * 40


class ReleasePolicyTests(unittest.TestCase):
    def accepted(self):
        run = {
            'event': 'push', 'head_branch': 'main', 'status': 'completed',
            'conclusion': 'success', 'path': '.github/workflows/golden-rules.yml',
            'repository': {'full_name': REPOSITORY}, 'head_repository': {'full_name': REPOSITORY},
            'head_sha': SHA,
        }
        jobs = [{'name': 'automated-contract', 'status': 'completed', 'conclusion': 'success'}]
        return run, jobs

    def test_only_exact_successful_main_push_can_release(self):
        run, jobs = self.accepted()
        require_accepted_run(run, jobs, SHA, SHA)
        changes = {
            'event': 'pull_request', 'head_branch': 'codex/untrusted', 'status': 'in_progress',
            'conclusion': 'failure', 'path': '.github/workflows/other.yml',
            'repository': {'full_name': 'foreign/RepoHub'},
            'head_repository': {'full_name': 'foreign/RepoHub'}, 'head_sha': 'b' * 40,
        }
        for field, value in changes.items():
            with self.subTest(field=field), self.assertRaises(ValueError):
                require_accepted_run(dict(run, **{field: value}), jobs, SHA, SHA)
        for invalid_jobs in ([], jobs * 2, [dict(jobs[0], conclusion='skipped')]):
            with self.assertRaises(ValueError):
                require_accepted_run(run, invalid_jobs, SHA, SHA)
        with self.assertRaises(ValueError):
            require_accepted_run(run, jobs, SHA, 'b' * 40)

    def test_versions_increase_and_failed_drafts_reserve_numbers(self):
        self.assertEqual(release_plan([], SHA)['version'], '0.0.1')
        previous = [{'tag_name': 'repohub-v0.0.9-b9', 'draft': True}]
        self.assertEqual(release_plan(previous, SHA)['version'], '0.1.0')
        self.assertEqual(release_plan(previous, SHA)['build'], '10')
        previous.append({'tag_name': 'unrelated-v999'})
        self.assertEqual(release_plan(previous, SHA)['build'], '10')

    def test_retention_keeps_current_plus_three_without_deleting_tags_or_unrelated_releases(self):
        releases = [dict(release_plan([{'tag_name': f'repohub-v0.0.0-b{number - 1}'}]
                                    if number > 1 else [], SHA), draft=False)
                    for number in range(1, 7)]
        releases = [dict(item, tag_name=item['tag']) for item in releases]
        releases += [{'tag_name': 'other-app-v1'}, {'tag_name': 'repohub-v0.0.7-b7', 'draft': True}]
        original = copy.deepcopy(releases)
        expired = expired_releases(releases, 'repohub-v0.0.6-b6')
        self.assertEqual([item['tag_name'] for item in expired], ['repohub-v0.0.2-b2', 'repohub-v0.0.1-b1'])
        self.assertEqual(releases, original)
        with self.assertRaises(ValueError):
            expired_releases(releases, 'repohub-v0.0.5-b5')

    def test_retention_requires_a_matching_production_receipt(self):
        receipt = dict(release_plan([], SHA), test_only=False, archive_sha256='b' * 64, archive_bytes=10)
        release = {'tag_name': receipt['tag']}
        validate_receipt(release, receipt)
        for field, value in {'source_revision': 'unknown', 'tag': 'foreign', 'build': '9',
                             'archive_url': 'https://foreign/update.zip', 'test_only': True,
                             'archive_sha256': '', 'archive_bytes': 0}.items():
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_receipt(release, dict(receipt, **{field: value}))
