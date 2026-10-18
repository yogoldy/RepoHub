const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const model = require('../web/setup.js');
const fixture = {
  configured: true, reviewed: false, source: {mode: 'manual', paths: ['/projects/non-git']},
  workspaces: [{path: '/projects/non-git'}], destination: '/cloud/Backups', revision: 'one',
  settings: {battery: {frequency_minutes: 60, after_edits: false, edit_delay_minutes: 5},
    adapter: {frequency_minutes: 60, after_edits: false, edit_delay_minutes: 5}},
};
const draft = model.createDraft(fixture);
model.addPaths(draft, ['/projects/Git', '/projects/non-git']);
assert.deepEqual(model.payload(draft).source.paths, ['/projects/non-git', '/projects/Git']);
assert.equal(fixture.source.paths.length, 1, 'Draft changes cannot mutate saved configuration');

class Node {
  constructor() { this.children = []; this.hidden = false; this.disabled = false; this.textContent = ''; }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  setAttribute(name, value) { this[name] = value; }
  querySelector() { return {focus() {}}; }
  focus() {}
  showModal() { this.open = true; }
  close() { this.open = false; }
}
async function actualController(backupNow) {
  const html = fs.readFileSync('web/setup.html', 'utf8');
  const nodes = Object.fromEntries([...html.matchAll(/id="([^"]+)"/g)].map(match => [match[1], new Node()]));
  nodes.steps.children = Array.from({length: 5}, () => new Node());
  const calls = [], listeners = {};
  let currentOperation;
  let discoveryReads = 0;
  const context = vm.createContext({
    console, setTimeout, Uint8Array, crypto: require('node:crypto').webcrypto,
    // An unhosted WKWebView confirm returns false; draft reload must still work.
    confirm: () => false,
    document: {getElementById: id => nodes[id], createElement: () => new Node(),
      createTextNode: value => ({textContent: value})},
    addEventListener: (name, handler) => { listeners[name] = handler; },
    webkit: {messageHandlers: {repoHub: {postMessage: value => calls.push({native: value})}}},
    fetch: async (path, options = {}) => {
      const value = options.body ? JSON.parse(options.body) : undefined;
      calls.push({path, value});
      let result;
      if (path === '/api/setup') result = structuredClone(fixture);
      else if (path === '/api/session') result = {token: 'fresh-token'};
      else if (path === '/api/discovery/start') result = {id: 'discovery', state: 'running'};
      else if (path === '/api/discovery') {
        assert.equal(nodes['cancel-discovery'].disabled, false, 'Each rescan must be cancellable');
        assert.equal(nodes.reload.disabled, true, 'Reload waits for an active scan');
        discoveryReads += 1;
        result = discoveryReads <= 2 ? {id: 'discovery', state: 'complete', visited: 3, results: [
          {path: '/projects/Git', selectable: true}], incomplete: false} : {
          id: 'discovery', state: 'failed', visited: 0, results: [], incomplete: true,
          warnings: [{reason: 'git_unavailable', path: '/projects'}]};
      } else if (path === '/api/setup/review') {
        assert.equal(options.headers['X-RepoHub-Token'], 'fresh-token');
        currentOperation = {id: 'check', state: 'complete', value: {review: 'checked',
          workspaces: [{path: '/projects/non-git', backup_path: '/cloud/Backups/non-git'}], removed: []}};
        result = {id: 'check'};
      } else if (path === '/api/setup/apply') {
        assert.equal(value.review, 'checked');
        currentOperation = {id: 'save', state: 'complete', value: {configured: true}};
        result = {id: 'save'};
      } else if (path === '/api/setup/operation') result = currentOperation;
      else throw new Error('Unexpected request: ' + path);
      return {ok: true, json: async () => result};
    },
  });
  vm.runInContext(fs.readFileSync('web/setup.js', 'utf8'), context);
  for (let turn = 0; turn < 10; turn++) await new Promise(resolve => setImmediate(resolve));
  assert.equal(calls.filter(call => call.path === '/api/setup/apply').length, 0);
  nodes['pick-sources'].onclick();
  assert.equal(nodes.reload.disabled, true, 'Reload waits for the native picker');
  const sourcePicker = calls.filter(call => call.native?.action === 'chooseRepoFolders').at(-1).native;
  await listeners.repoHubSetupPicked({detail: {
    request_id: sourcePicker.request_id, cancelled: false, paths: ['/projects/discard-this-draft'],
  }});
  assert.equal(nodes.sources.children.length, 2);
  assert.equal(nodes.reload.disabled, false);
  await nodes.reload.onclick();
  for (let turn = 0; turn < 10; turn++) await new Promise(resolve => setImmediate(resolve));
  assert.equal(nodes.sources.children.length, 1, 'Reload discards only the unsaved draft without a browser confirmation');
  assert.equal(calls.filter(call => call.path === '/api/setup/apply').length, 0);
  for (let scan = 0; scan < 2; scan++) {
    nodes['find-git'].onclick();
    const picked = calls.filter(call => call.native?.action === 'chooseDiscoveryParent').at(-1).native;
    await listeners.repoHubSetupPicked({detail: {request_id: picked.request_id, cancelled: false, paths: ['/projects']}});
    assert.equal(nodes['add-discovered'].disabled, false);
  }
  const selection = nodes['discovery-results'].children[0].children[0].children[0];
  selection.checked = true; selection.onchange(); nodes['add-discovered'].onclick();
  nodes['find-git'].onclick();
  const unavailable = calls.filter(call => call.native?.action === 'chooseDiscoveryParent').at(-1).native;
  await listeners.repoHubSetupPicked({detail: {request_id: unavailable.request_id, cancelled: false, paths: ['/projects']}});
  assert.match(nodes['discovery-status'].textContent, /Git is not available.*Add folders manually/);
  assert.equal(nodes['add-discovered'].disabled, true);
  await nodes.next.onclick();
  await nodes.next.onclick();
  assert.match(nodes['access-status'].textContent, /helper can read/);
  assert.equal(nodes.next.disabled, false);
  assert.equal(calls.filter(call => call.path === '/api/setup/apply').length, 0);
  await nodes.next.onclick();
  await nodes.next.onclick();
  if (backupNow) await nodes['finish-backup'].onclick();
  else await nodes.next.onclick();
  assert.equal(calls.filter(call => call.path === '/api/setup/apply').length, 1);
  assert.equal(calls.find(call => call.path === '/api/setup/apply').value.backup_now, backupNow);
  assert.deepEqual(calls.find(call => call.path === '/api/setup/apply').value.draft.source.paths,
    ['/projects/non-git', '/projects/Git']);
  assert.equal(nodes.complete.hidden, false);
  assert.equal(nodes.reload.disabled, false, 'The completed view can reload saved setup');
  assert.equal(calls.some(call => call.native?.action === 'requestNotifications'), false);
  assert.equal(calls.some(call => call.path === '/api/backup'), false);
  await nodes.reload.onclick();
  for (let turn = 0; turn < 10; turn++) await new Promise(resolve => setImmediate(resolve));
  assert.equal(nodes.complete.hidden, true, 'Reload exits the old completion view');
  assert.equal(nodes['setup-actions'].hidden, false);
  assert.equal(nodes['discovery-panel'].hidden, true, 'Reload removes results belonging to the discarded draft');
  assert.equal(nodes['discovery-results'].children.length, 0);
  assert.equal(nodes['access-status'].textContent, '');
  assert.equal(nodes['review-paths'].children.length, 0);
  assert.equal(nodes.next.disabled, false);
  assert.equal(nodes.reload.disabled, false);
  assert.equal(nodes.sources.children.length, 1);
  assert.equal(calls.filter(call => call.path === '/api/setup/apply').length, 1, 'Reload cannot save configuration');
}
(async () => {
  await actualController(false); await actualController(true);
  console.log('Actual welcome controller keeps drafts separate, checks access, and saves only explicitly');
})().catch(error => { console.error(error); process.exitCode = 1; });
