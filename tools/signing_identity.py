"""Check the code identities that macOS uses to recognize RepoHub updates.

These requirements match the first Developer ID package (build 9). Changing a
Team ID, designated requirement or helper identity needs an explicit migration;
notarization alone does not prove that existing privacy grants will match.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

TEAM_ID = 'LJM5FKB7DY'
COMPONENTS = (
    ('app', '.', 'com.leogoldberg.repohub'),
    ('helper', 'Contents/Resources/python/bin/python3.14', 'python3'),
    ('cloud', 'Contents/Resources/runtime/cloud-status', 'cloud-status'),
)


def designated_requirement(identifier):
    return (f'identifier "{identifier}" and anchor apple generic '
            'and certificate 1[field.1.2.840.113635.100.6.2.6] '
            'and certificate leaf[field.1.2.840.113635.100.6.1.13] '
            f'and certificate leaf[subject.OU] = {TEAM_ID}')


def normalized_requirement(value):
    # codesign quotes identifiers only when necessary and adds /* exists */.
    value = re.sub(r'/\*.*?\*/', '', value)
    return ' '.join(value.replace('"', '').split())


def check_metadata(text, identifier):
    fields = {}
    for line in text.splitlines():
        for name in ('Identifier', 'TeamIdentifier'):
            if line.startswith(name + '='):
                fields[name] = line.split('=', 1)[1]
        if line.startswith('designated => '):
            fields['requirement'] = line.removeprefix('designated => ')
    expected = normalized_requirement(designated_requirement(identifier))
    if (fields.get('Identifier') != identifier or fields.get('TeamIdentifier') != TEAM_ID
            or normalized_requirement(fields.get('requirement', '')) != expected):
        raise ValueError('permission_signing_identity_changed')
    return {'identifier': identifier, 'team': TEAM_ID,
            'requirement_sha256': hashlib.sha256(expected.encode()).hexdigest()}


def verify_identity(app):
    root = app.resolve(strict=True)
    results = {}
    for role, relative, identifier in COMPONENTS:
        path = (app / relative).resolve(strict=True)
        if not path.is_relative_to(root):
            raise ValueError('signing_component_outside_app')
        result = subprocess.run(['/usr/bin/codesign', '-d', '-r-', '--verbose=2', str(path)],
                                capture_output=True, text=True)
        if result.returncode:
            raise ValueError('permission_signing_identity_unavailable')
        results[role] = check_metadata(result.stdout + '\n' + result.stderr, identifier)
    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', type=Path, required=True)
    print(json.dumps(verify_identity(parser.parse_args().app), sort_keys=True))
