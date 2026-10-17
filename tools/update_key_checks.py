#!/usr/bin/env python3
"""Exercise the compiled key matcher using public RFC 8032 test material."""
import argparse
import base64
from pathlib import Path
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checker', required=True)
    args = parser.parse_args()
    # RFC 8032 section 7.1, test 1. This published vector is not a signing secret.
    seed = bytes.fromhex('9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60')
    public = bytes.fromhex('d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a')
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / 'public-test-vector.key'
        path.write_bytes(base64.b64encode(seed))
        path.chmod(0o600)
        def result(expected):
            return subprocess.run([args.checker, str(path), expected], check=False).returncode
        if result(base64.b64encode(public).decode()) != 0:
            raise ValueError('matching_update_key_rejected')
        if result(base64.b64encode(b'x' * 32).decode()) != 78:
            raise ValueError('foreign_update_key_accepted')
        path.write_text('not base64')
        if result(base64.b64encode(public).decode()) != 78:
            raise ValueError('malformed_update_key_accepted')
    print('Matching, foreign and malformed update key checks passed')


if __name__ == '__main__':
    main()
