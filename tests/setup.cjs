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
  const context = vm.createContext({
    console, setTimeout, Uint8Array, crypto: require('node:crypto').webcrypto,
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
      else if (path === '/api/setup/review') {
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
  assert.equal(nodes.complete.hidden, false);
  assert.equal(calls.some(call => call.native?.action === 'requestNotifications'), false);
  assert.equal(calls.some(call => call.path === '/api/backup'), false);
}
(async () => {
  await actualController(false); await actualController(true);
  console.log('Actual welcome controller keeps drafts separate, checks access, and saves only explicitly');
})().catch(error => { console.error(error); process.exitCode = 1; });
