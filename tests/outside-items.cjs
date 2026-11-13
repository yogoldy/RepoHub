// Execute the shipped outside-item page with isolated API responses.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync('web/menu.html', 'utf8');
const nodes = new Map([...html.matchAll(/\bid="([^"]+)"/g)].map(match => [match[1], {}]));
const get = id => nodes.get(id);
const posts = [];
let revision = 'r1';
let fail = false, hold = false, release, discard = false, finished = 0;
let saved = {linked_folders: {node_modules: 'link_only'}, checkouts: 'committed_only'};
const items = {linked_folders: [{path: 'node_modules', target: '/x/node_modules', target_type: 'directory', bytes: 2048, complete: true}],
  reinstall: [{path: '.venv/bin/python3', target: '/opt/homebrew/bin/python3', target_type: 'file'}],
  checkouts: [{name: 'draft', path: '/x/draft', state: 'present', bytes: 10, complete: false, changed_files: 0}]};
const respond = (ok, value) => ({ok, json: async () => value});
const root = {
  RepoHubSettings: {confirmDiscard: async dirty => !dirty || discard, finishRepoPage() { finished++; }},
  fetch: async (path, options = {}) => {
    if (path === '/api/session') return respond(true, {token: 't'});
    if (!options.method) return respond(true, {items, choices: structuredClone(saved), revision});
    const body = JSON.parse(options.body);
    posts.push(body);
    if (hold) await new Promise(resolve => { release = resolve; });
    if (fail || body.revision !== revision) return respond(false, {error: 'Choices changed. Reopen this page before saving.'});
    saved = body.choices;
    revision = 'r' + (posts.length + 1);
    return respond(true, {items, choices: structuredClone(saved), revision});
  },
};
vm.runInNewContext(fs.readFileSync('web/outside-items.js', 'utf8'),
  {window: root, document: {getElementById: get}, Intl, JSON});
const page = root.RepoHubOutside;
const tick = () => new Promise(resolve => setImmediate(resolve));
const choose = value => get('outside-list').onchange({target: {dataset: {link: 'node_modules'}, value}});
(async () => {
  await page.open('repo-a');
  assert.match(get('outside-list').innerHTML, /Keep link only/);
  assert.match(get('outside-list').innerHTML, /at least 10 B · no uncommitted changes/);
  assert.match(get('outside-list').innerHTML, /Reinstall on a new Mac/);
  assert(get('outside-save').disabled, 'No-change saves are disabled');
  choose('include');
  assert(!get('outside-save').disabled);
  assert.equal(posts.length, 0, 'Changing a choice never saves');
  assert.equal(await page.leave(), false, 'Declined discard keeps the draft');
  discard = true;
  assert.equal(await page.leave(), true);
  assert(get('outside-save').disabled, 'Discard restores the saved choices');
  discard = false;
  choose('include');
  fail = true;
  await get('outside-save').onclick();
  assert.match(get('outside-error').textContent, /still here/);
  assert.equal(saved.linked_folders.node_modules, 'link_only');
  assert(!get('outside-save').disabled, 'Failed save can be retried');
  fail = false; hold = true;
  const saving = get('outside-save').onclick();
  await tick();
  const count = posts.length;
  await get('outside-save').onclick();
  assert.equal(posts.length, count, 'One save request while busy');
  assert.equal(await page.leave(), false, 'Back cannot interrupt a save');
  release(); await saving; hold = false;
  assert.equal(saved.linked_folders.node_modules, 'include');
  assert.equal(posts.at(-1).revision, 'r1');
  assert.equal(finished, 1);
  assert(get('outside-save').disabled);
  console.log('Outside-item page: explicit save, discard, failure, duplicate and busy guards passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
