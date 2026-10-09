# RepoHub golden-rule release gate

This is our executable product contract. It checks backup safety, diagnostic evidence, privacy, scoped APIs, restore behavior and source/package consistency. It is not a claim of mathematical correctness or an exhaustive end-to-end test.

Read [the failure-mode register](FAILURE_MODES.md) and its machine-readable [rule definitions](golden-rules.json). Each rule specifies its most susceptible boundary, diagnostic trail, required response, exact regression IDs and remaining exposure. Fixes add counterexamples to that register rather than replacing its history with a new test count.

## Run for a new version

From a clean macOS source checkout:

```sh
python3 tools/release_gate.py --require-clean
```

The command prints a path to a new private JSON receipt. Its sibling logs hold the full Python results and each JavaScript/Swift build or test result. It does not touch installed apps, login items, iCloud, personal repos or existing backup archives. Native app/cloud binaries are compiled but not launched; only the synthetic Swift test executables run.

For development, omit `--require-clean` to check uncommitted work. The receipt records dirty source; it is not evidence for a clean committed release. `--output /new/path/result.json` chooses a new receipt location without overwriting earlier evidence. Keep the receipt and its referenced log directory together; do not commit logs or personal incident data.

A passed macOS gate means:

- All discovered Python tests passed, without skipped or expected-failure tests.
- Every test named by every golden rule actually executed and passed. Missing/renamed/skipped tests fail their rule.
- Installer packages all local runtime imports, and HTML dependencies have existing served routes.
- Every web JavaScript file parses; status-policy and diagnostic-delivery suites pass.
- The app and cloud helper compile for the host architecture/macOS 13 target; notification and native-bridge tests compile and run successfully.
- The source fingerprint remains unchanged during execution. The receipt identifies the Git revision, dirty state, profile, test outcomes, command logs and known manual gaps.

The optional `--profile portable` is deliberately marked **partial**, even when its Python/JavaScript checks pass. It cannot satisfy the macOS release requirement. Running the default profile on a non-Mac fails rather than silently skipping native checks.

## What still needs live evidence

An automated pass never means a complete release approval. `manual_release_approval` stays false and pending manual checks are explicit in every receipt.

For an application release, verify installed file hashes/helper build identity, unchanged settings and served UI on the target Macs. For changed UI, record rendered states and the corresponding observation receipts. For archive/verification/restore changes, use small isolated fixtures and independent two-device reception/restore. For scheduling or recovery changes, exercise the relevant power, login, sleep or fault boundary. Record which checks ran, which did not, and why; a missing receipt cannot become a pass.

The existing Air pilot demonstrates particular supported paths. It does not close the gaps for databases, unusual Git layouts, sustained network/storage failures, hardware power transitions or rendered progress percentages.

## Continuous integration

[The workflow](../../.github/workflows/golden-rules.yml) runs the macOS gate on main/work-branch pushes, pull requests and manual dispatch. It uses synthetic inputs only, read-only repository permission and no persisted checkout credentials. The checkout action is pinned to a verified commit; see its [official documentation](https://github.com/actions/checkout).

GitHub protects `main`: changes require a pull request and the `automated-contract` check from GitHub Actions (app ID 15368), with the branch up to date before merging. Protection applies to administrators too; force pushes and branch deletion are disabled. No extra approving review is required for this single-maintainer workflow. Repository administrators can change protection settings, so this is an enforced merge policy, not an immutable security boundary. Do not promote or deploy a version with a failed/missing gate receipt. Do not enable `pull_request_target` or upload private diagnostic receipts as part of this workflow.

## Maintaining the contract

When a failure is found, preserve private incident evidence, distinguish the observed cause from a hypothesis, reproduce with a controlled fixture, and add a regression plus diagnostic assertions. Update the rule’s causal explanation and remaining gap. When an intentional behavior changes, review the invariant itself; do not merely weaken the test until it passes. A future export field requires explicit typed policy and adversarial privacy tests even if the local logger already permits it.
