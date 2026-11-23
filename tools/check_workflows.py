#!/usr/bin/env python3
"""Check GitHub workflows with a pinned actionlint binary on ARM64 macOS."""
import argparse
from pathlib import Path
import platform
import subprocess
import tempfile
try:
    from tools.package_app import dependency, extract
except ModuleNotFoundError:
    from package_app import dependency, extract


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, required=True)
    args = parser.parse_args()
    if platform.system() != 'Darwin' or platform.machine() != 'arm64':
        raise SystemExit('ARM64 macOS required; workflow validation was not run')
    with tempfile.TemporaryDirectory(prefix='repohub-workflow-check-') as folder:
        target = Path(folder)
        extract(dependency('actionlint-arm64', args.cache), target)
        # Workflow shell commands are simple fixed invocations; shellcheck is
        # deliberately not a separate unpinned dependency of this syntax check.
        subprocess.run([str(target / 'actionlint'), '-shellcheck='], check=True,
                       cwd=Path(__file__).resolve().parents[1])


if __name__ == '__main__':
    main()
