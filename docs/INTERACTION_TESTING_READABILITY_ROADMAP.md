# RepoHub interaction testing and readability roadmap

Initially approved for documentation by Leo on 2026-10-13. Leo subsequently authorized **Step 1 only**, establishing readability standards and their documentation/instruction pointer. **Steps 2-9 are not authorized yet.** Obtain Leo's explicit go-ahead before starting another stage, installing/configuring tools, changing application code or tests, making broader agent-configuration changes, or deploying. This is the agreed local plan for Leo and the development agent to follow.

## Purpose

Make RepoHub easier to understand and safer to change by defining visible interaction expectations, testing them repeatedly, and then using those tests while improving code readability. The menu bar remains the primary product surface. A browser test and a check of the installed Mac app supply different evidence for the same requirement.

This roadmap adds interaction coverage to the existing [Golden Gate](quality/RELEASE_GATE.md) and [two-Mac reliability acceptance](RELIABILITY_TWO_MAC_ACCEPTANCE.md). It does not replace their permission, freshness, access, volume-identity, backup-preservation, protected-merge or rollback requirements. Destination selection and other new product features remain outside this pass.

## Recorded starting point

At roadmap approval, the inspected task branch was `codex/workspace-setup`, clean at `40c39baf4b19eda635cb4658dc3541c9d19059ea`. The application candidate was `71998b0`; subsequent commits through that baseline changed acceptance documentation only. The recorded clean macOS Golden Gate passed 204 Python tests plus JavaScript/native checks, and both GitHub automated-contract checks passed for that baseline. PR #6 remained draft and unmerged. These historical results do not prove future revisions or every visible interaction.

The current stack is HTML, plain CSS and JavaScript, a Python helper, native Swift/WebKit integration and JSON persistence. React, TypeScript, TSX and Tailwind are not currently used. The user reported that Show me does not work on the installed Pro; reproduce it before assigning a cause. Previous Air acceptance had demonstrated permission grant and restart recovery, but the complete final-candidate matrix on both Macs remained unfinished. Daily services were restored before the authentication blocker. Revalidate current installations, service ownership, source revisions and protected state at resumption rather than treating this recorded baseline as live evidence.

## Ordered work and completion criteria

Step 1 is documented under its separate authorization; Steps 2-9 remain open. Tick a stage only after its criteria are evidenced; planned tests and previous-version results are not completion.

### 1. Agree on readability standards

- [x] Establish clear names, sensible formatting, small functions with recognizable responsibilities, and selective comments explaining decisions.

The [initial readability standard](READABILITY_STANDARDS.md) defines conventions, representative JavaScript/CSS examples and separate formatting/cleanup/fix verification. Existing application code is unchanged. Teacher review before broad cleanup remains Step 7.

**Why:** New work should follow understandable conventions from the beginning. Separate mechanical formatting, structural cleanup and behavior changes. Do not start a broad rewrite before stronger browser coverage exists.

**Complete when:** Leo and the agent have a documented, concrete standard with representative examples. This stage defines conventions; it does not claim the existing code has been refactored.

### 2. Record the baseline

- [ ] Identify the installed Pro version, development candidate, runtime assets and current automated checks. Reproduce the reported Show me issue and record the exact surface, selected repo and circumstances.

**Why:** A failure can originate in code, styling, packaging or a different installed version. Diagnose the actual version rather than an assumed one.

**Complete when:** The relevant versions and asset identities are recorded, existing checks have known results, and the observed problem is reproducible or explicitly unresolved. Preserve personal configuration, sources, credentials, schedules and backups.

### 3. Define the interaction checklist

- [ ] Inventory controls and agree on their visible results, important failure states and required browser/native checks.

Start with the menu bar: repo selection and navigation, status explanations, Show me, Finder shortcuts, default and per-repo settings, manual backup/retry, readiness and reporting. Each checklist entry records its preconditions, user action, expected visible result, permitted side effects, relevant diagnostic evidence, verification method and pass/fail/blocked status.

**Why:** Expected behavior determines the saved tests. Tool installation alone does not define success.

**Complete when:** Each agreed interaction has understandable acceptance criteria and an assigned browser or native verification method. Cover important combinations without claiming that a finite suite exhausts every possible UI sequence.

### 4. Set up Playwright

- [ ] Configure Playwright MCP for agent exploration and a reproducible saved Playwright test environment for repeatable checks.

Use synthetic repo/status data, isolated settings and pinned/reproducible dependencies. Browser tests must not bind to the daily helper, start real backups, submit public reports, access personal credentials or relax loopback/request guards. Document how another agent installs the dependencies and runs the same tests. Determine the appropriate project versus personal MCP configuration before changing it.

**Why:** MCP lets an agent investigate browser behavior; saved tests encode agreed expectations and repeat them on future versions. They are complementary, not interchangeable.

**Complete when:** A fresh documented setup runs a known browser check against isolated inputs and the MCP connection is verified. Neither replaces actual native Mac acceptance.

### 5. Dogfood with Show me

- [ ] Write a saved test that demonstrates the reproduced issue, make the smallest necessary fix, then verify the browser result and the installed native menu.

The initial contract is:

1. Highlight the folder button on the selected repo card.
2. Make the visual effect apparent and reset it afterward.
3. Support repeated activation and changing the selected repo.
4. Support keyboard activation.
5. Provide a clear visual indication with reduced motion enabled.
6. Do not open Finder or change backup settings as a side effect of the demonstration.

**Why:** A real counterexample establishes whether the testing approach catches useful failures. Checking for a handler or CSS class alone does not establish a visible effect.

**Complete when:** The controlled regression fails for the demonstrated problem, passes after the narrow fix, and actual computer-use evidence confirms the changed behavior in the installed menu. If the original failure cannot be reproduced, record the limit; do not fabricate a failing baseline or claim a fix.

### 6. Expand coverage and strengthen the Golden Gate

- [ ] Add the agreed saved interaction checks to the automated release contract while preserving explicitly required native checks.

**Why:** Future changes must meet the same expectations. The new testing system should protect the later readability work as well as behavior fixes.

**Complete when:** The saved checks actually run, failures make the release check fail, and coverage/evidence limits are documented. Keep diagnostics correlated with displayed states. Browser checks do not close native permission, Finder, menu-window or actual provider obligations. Store raw/private logs outside Git; any CI evidence uses synthetic data and an explicit bounded retention policy rather than uploading installers or personal diagnostics.

### 7. Review readability with Leo's AI teacher

- [ ] Prepare a representative function, its purpose, current behavior and proposed readable version for Leo's AI teacher. Obtain that review before applying the approach broadly.

After agreement, improve readability in small separate commits and rerun the new saved tests and relevant Golden Gate checks. Do not deliberately change behavior during cleanup. If tests expose a real behavior defect, separate its fix from the readability commit rather than altering the expectations to accept it.

**Why:** Leo can follow how functions contribute like paragraphs, and the project dogfoods its new testing system during code cleanup.

**Complete when:** Teacher feedback is recorded, the agreed readability changes are reviewable, behavior remains consistent and required checks pass. If the teacher is unavailable, keep that review open rather than inventing approval. Leo supplies the review or explicitly authorizes contact with the chosen teacher; the agent does not send code elsewhere by default.

### 8. Audit documentation and agent configuration

- [ ] Reconcile the roadmap, testing guides, failure register, product thesis, AGENTS.md and relevant .toml configuration with the implemented system.

Distinguish repository-owned settings from personal Codex configuration. TOML is a file format, not inherently a sandbox; inspect the actual MCP and access settings. Make only justified changes, preserve necessary safety boundaries, and keep credentials and personal configuration dumps out of Git. Clearly distinguish planned, implemented, browser-tested and native-accepted states.

**Why:** Future agents need accurate instructions and appropriate access boundaries before final release acceptance.

**Complete when:** Commands, links, coverage claims and configuration agree with the actual implementation. Remaining gaps are explicit, and an agent can follow the release process without relying on chat history.

### 9. Finalize release acceptance

- [ ] Complete the required final-candidate Air/Pro acceptance, protected merge and sequential deployment with rollback.

Follow the existing numbered two-Mac reliability matrix, incorporating the changed interaction checks. Every application-code change creates a new candidate: run the clean committed macOS Golden Gate, rebuild on Pro, transfer the same payload and complete both host matrices for that candidate. Documentation-only changes require current clean checks and verification that the accepted application payload is unchanged. Do not substitute simulation or browser evidence for required actual macOS permission evidence.

**Why:** Only a verified release becomes the daily installation.

**Complete when:** The required browser and native checks pass on both Macs for the accepted payload; protected data/configuration remain intact; exact-head GitHub checks pass; PR #6 follows the protected merge process; and Pro then Air deployment passes with rollback available and documented installed assets. Preserve the Air's own monitoring setup. Report release/PR/commit, installed versions, tests, diagnostics, rollback locations, limitations and the next feature.

## Verification responsibilities

| Responsibility | Owner/tool |
|---|---|
| Intended behavior and acceptance expectations | Leo, with the agent making them concrete |
| Exploration, saved-test authoring, execution and diagnosis | Agent; Playwright MCP and saved Playwright tests where appropriate |
| Actual installed menu, Finder and OS permission checks | Agent through approved computer use on the Macs |
| Password entry and required macOS authentication | Leo directly, never through chat |
| Readability teaching review | Leo's selected AI teacher before broad cleanup |

For example, a browser test can establish the visible Show me effect; native checking establishes that it works inside the installed menu. A browser bridge test can establish the requested folder identity; actual Finder evidence establishes which directory opened. Simulated denial can establish UI behavior; real macOS denial/restoration establishes helper access and preservation. Each supplies only the evidence it actually observed.

## Branches, commits and operating agreement

- Keep the testing foundation and any narrow interaction fix with the current reliability work on `codex/workspace-setup`, in separate logical commits, subject to implementation approval.
- Substantial readability work uses a separately approved branch from a tested baseline. Confirm its starting revision and how it returns to the release branch before creating it; never create a branch merely because this roadmap mentions one.
- Do not mix behavior fixes, mechanical formatting and structural cleanup into one commit. Commit completed work before reporting it and preserve unrelated worktree changes.
- Never claim checks passed without running them. Distinguish exploration, automated browser checks, native evidence, implementation and deployment.
- Report where we are, what changes next, why, how it will be verified, required user actions and remaining gaps. For user-run commands, provide the exact command, where it runs and the expected result; authentication stays direct on the Mac.
- A failed test stops promotion and starts diagnosis; it does not justify weakening the expected behavior to obtain a green check.
- Restore paused daily services before waiting for user action or reporting a blocker. Retain the stopping points in the two-Mac protocol for unavailable native controls, missing permission evidence, protected-state changes, broader access or failed deployment.
- Tailwind and TestSprite evaluation remain deferred. Vercel, Workers, cloud connectors, destination selection and unrelated new features are outside this roadmap.

## Approval and evidence record

| Date | Record |
|---|---|
| 2026-10-13 | Leo approved formalizing this nine-stage local roadmap and linking it from the product thesis. Implementation remains unapproved; no setup, application/test/configuration edits or deployment are implied. |
| 2026-10-13 | Leo explicitly authorized Step 1. Established the initial readability standard with representative examples and a narrow AGENTS.md pointer. No application/test code, tools, .toml settings or installed apps were changed. Steps 2-9 remain unstarted and require authorization. Evidence: local links checked, three JavaScript examples syntax-checked, and the formatting example matched the current function for six representative inputs. Commit reference: `docs: establish readable coding conventions`. |

At implementation start, append the explicitly approved scope here. For completed stages, record the stage number, commit, test/evidence references and unresolved limitations. Do not copy personal logs, paths, credentials or course material into the public repository.
