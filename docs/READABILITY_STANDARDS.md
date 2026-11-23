# RepoHub readability standards

These conventions apply to new and modified code. Use a separate proposal for broad rewrites, new formatters or frameworks, and behavior changes. For project priorities, see the [roadmap](../ROADMAP.md).

## Purpose: each function should contribute like a paragraph

A reader should be able to answer:

1. What is this function trying to accomplish?
2. What information does it receive, and what does it return or change?
3. Which other function or user action uses it?
4. What happens when it cannot complete its job?

Readable code must retain the same backup, verification, privacy and request guards. More lines are acceptable when they make the responsibilities visible. More abstraction is useful only when it makes the actual behavior easier to follow.

## Formatting

- JavaScript, HTML and CSS: two spaces for indentation. Python and Swift: four spaces, consistent with their surrounding code. Do not reindent untouched modules just to enforce this convention.
- Put unrelated statements and variable declarations on separate lines. Use braces and multiline blocks for conditions, loops and error handling. Use semicolons consistently in JavaScript.
- Separate logical sections with a blank line. Wrap long argument lists, objects and conditions at a natural boundary; aim for roughly 100 characters, not a hard limit requiring distorted strings or SVG paths.
- Keep a short obvious callback inline when that is easier to read. Expand callbacks with several actions or decisions. No rule requires every callback to become a named function.
- CSS: one declaration per line and a separate block for each rule. Preserve rule order, selector specificity, repeated overrides, animation timing and media-query behavior during mechanical formatting.
- HTML: indent meaningful sections and give long elements/attribute lists breathing room. Preserve meaningful whitespace, identifiers, ARIA relationships and native bridge wiring.
- These conventions require no formatter. The repository does not configure Prettier.

## Names

Use names that explain purpose and meaning. Prefer action names for functions (`renderRepoCards`, `loadBackupStatus`) and descriptive data names (`selectedRepoId`, `lastResponseAt`). Boolean names should reveal the condition (`isLoading`, `hasVerifiedBackup`, `canRetry`). Avoid unexplained one-letter aliases except familiar, tightly scoped indexes or coordinates.

Units matter: distinguish milliseconds, seconds, bytes, timestamps and percentages. Shared constants can name meaningful repeated timings, but replacing a literal must preserve its value and scope.

Naming changes are structural cleanup, not mechanical formatting. Existing API routes, JSON fields, workspace IDs, DOM IDs/classes, exported names and diagnostic event codes are contracts. Do not rename them for style without tracing consumers, checking compatibility and using a separately scoped change.

## Functions and modules

Group code by responsibility: obtaining information, deciding what it means, rendering it and responding to user actions. A function may coordinate those steps when its purpose remains obvious. Do not invent layers, generic factories or tiny helpers merely to satisfy an arbitrary line-count limit.

Prefer visible decision steps over nested ternaries with several outcomes. A short guard clause is useful when it makes the normal path clear. Moving branches or extracting functions requires a separate, tested refactoring change; preserve decision priority and fallbacks.

For the frontend, the existing responsibilities include:

| File | Contribution |
|---|---|
| `web/menu.js` | Menu cards, selection, controls and coordinating status updates |
| `web/app.js` | Full status-page presentation and interactions |
| `web/repo-status.js` | Shared interpretation of repo status and status icons |
| `web/readiness.js` | Displaying helper-observed access and notification readiness |
| `web/menu.css` / `web/style.css` | Styling the corresponding interfaces |

The table lists the responsibilities of the existing frontend modules. Extend existing module boundaries before adding another module without a clear need.

## Comments and explanations

Explain a decision or constraint that the code alone would not reveal. Do not narrate every assignment. Keep user-facing product explanations separate from developer comments.

A useful comment might explain why a prior archive remains until upload acknowledgement, or why an observation cannot be converted into a green status. When a callback or asynchronous operation is unfamiliar, explain it once in the reading guide or at the meaningful boundary rather than repeating a tutorial throughout production code.

State side effects at important boundaries: writes a saved setting, starts a backup request, sends a native command, or renders information. Do not describe an HTTP acceptance response as a completed backup or a displayed percentage as confirmed upload.

## Representative examples

The examples illustrate formatting that preserves behavior.

### A. Formatting a real date-display function

The current `when` function in `web/menu.js` is dense:

```javascript
function when(value){if(!value)return 'Not yet';return new Date(value).toLocaleString(undefined,{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'});}
```

The same function can be laid out as:

```javascript
function when(value) {
  if (!value) {
    return 'Not yet';
  }

  return new Date(value).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}
```

Read it as two contributions: missing information produces the existing fallback; available information is formatted using the same existing locale/options. This example deliberately preserves the existing name and behavior. A later rename such as `formatObservedTime` requires checking all callers in a separate cleanup.

### B. Keeping a small callback understandable

Illustrative JavaScript:

```javascript
const repoNames = repos.map((repo) => repo.name);
```

`map` visits each repo, and the callback returns its name. The result is a new array of names. This callback is simple enough to remain inline. A callback that creates elements, attaches handlers and makes several decisions should use multiple lines, or a well-named function if that clarifies the responsibility.

### C. Formatting a real CSS rule

The current rule in `web/menu.css`:

```css
.open-repo .folder-shape{display:block}
```

Readable layout:

```css
.open-repo .folder-shape {
  display: block;
}
```

The first part identifies the folder shape inside the open-repo button; the declaration controls its display. The selector and value remain identical. Reordering nearby rules or merging duplicate selectors is a different change because CSS order can affect the result.

## Separate changes and verification

| Change type | Examples | Required distinction |
|---|---|---|
| Mechanical formatting | Whitespace, line breaks, consistent indentation | Keep expressions, order and meaningful whitespace unchanged; inspect the diff and run relevant checks. |
| Structural cleanup | Rename variables, extract functions, reorganize code | Trace callers and contracts; use the behavioral regression tests for the affected code and relevant Golden Gate checks. |
| Behavior fix | Change a fallback, condition, timing or side effect | Reproduce the defect, define the expected result, add a regression and make a separate fix commit. |

Do not quietly combine categories. Changing `||` to `??`, adding `await`, moving a guard, adjusting timer duration, changing event-handler lifetime or consolidating CSS overrides can change behavior even if the result looks cleaner. A test failure during cleanup calls for diagnosis, not weaker expectations.

Start substantial cleanup from a tested baseline and review it separately. Every application change follows the release checks and host requirements in [Releasing](RELEASING.md). Standards alone are not new test coverage or evidence that a visible interaction works.

## Code review checklist

- Can the reader explain the function's contribution, input, output/side effect and failure path?
- Are names and units meaningful, and are unfamiliar decisions explained selectively?
- Are dense unrelated statements expanded without unnecessary abstractions?
- Is this formatting, structural cleanup or a behavior change, and does the commit stay within that category?
- Are interfaces, guard conditions, operation ordering, stored observations and CSS behavior preserved where required?
- Which checks actually ran, and which browser or native checks remain open?

In a review, identify the revision, explain the change and its rationale, and document verification and any remaining manual checks. For manual checks, give the command, working directory and expected result. Keep credentials out of review discussions.

## Scope of the standards

These standards and examples describe how new and deliberately changed code is written. Propose changes to the standards separately from broad changes to existing code.
