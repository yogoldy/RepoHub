/* Shared folder controller: both the new menu pages and existing full-page host. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const tick = () => new Promise(resolve => setImmediate(resolve));
async function surface(file) {
  const html = fs.readFileSync(path.join(root, 'web', file), 'utf8');
  class Element {
    constructor() { this.hidden = false; this.open = false; this.children = []; this.listeners = {}; }
    append(...items) { this.children.push(...items); }
    replaceChildren(...items) { this.children = items; }
    setAttribute(name, value) { this[name] = value; }
    addEventListener(name, action) { this.listeners[name] = action; }
    showModal() { this.open = true; }
    close() { this.open = false; }
  }
  const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map(match => match[1]);
  const nodes = new Map(ids.map(id => [id, new Element()]));
  const get = id => nodes.get(id) || null;
  get('workspace-form').hidden = true;
  let discard = false, block = false, release, fail = true, homeCount = 0;
  let saved = {mode: 'home', home: '/synthetic/repos'};
  const calls = [];
  const context = {
    document: {getElementById: get, createElement: () => new Element()},
    AbortController, setTimeout, clearTimeout,
    Event: class { constructor(type) { this.type = type; } },
    addEventListener() {}, dispatchEvent() {}, confirm: () => discard,
    fetch: async (url, options = {}) => {
      const payload = options.body ? JSON.parse(options.body) : undefined;
      calls.push({url, payload});
      let value;
      if (url === '/api/session') value = {token: 'fixture-token'};
      else if (url === '/api/workspaces' && !payload) value = {
        revision: 'saved-revision', configuration: {source: saved,
          workspaces: [{path: '/synthetic/repos/Project', active: true}]},
      };
      else {
        assert.equal(options.headers['X-RepoHub-Token'], 'fixture-token');
        assert.equal(payload.revision, 'saved-revision');
        if (url === '/api/workspaces/preview') value = {
          review: 'reviewed-source', workspaces: [{path: '/synthetic/repos/Project'}], removed: [],
        };
        else {
          assert.equal(payload.review, 'reviewed-source');
          if (block) await new Promise(resolve => { release = resolve; });
          if (fail) return {ok: false, status: 409, json: async () => ({error: 'Selection changed. Reload before saving.'})};
          saved = payload.source;
          value = {revision: 'new-revision'};
        }
      }
      return {ok: true, status: 200, json: async () => structuredClone(value)};
    },
  };
  if (file === 'menu.html') context.RepoHubSettings = {
    leaveSchedule: async () => true,
    confirmDiscard: async dirty => !dirty || discard,
    workspaceOpened() {}, showHome() { homeCount++; },
  };
  vm.runInNewContext(fs.readFileSync(path.join(root, 'web/workspace-setup.js'), 'utf8'), context);
  await get('workspace-open').onclick();
  get('workspace-manual-mode').onclick();
  await get('workspace-cancel').onclick();
  assert(get('settings-dialog').open, file + ': declined discard keeps dialog open');
  assert(!get('workspace-form').hidden);
  assert.equal(saved.mode, 'home');
  let prevented = false;
  get('settings-dialog').listeners.cancel({preventDefault() { prevented = true; }});
  await tick(); assert(prevented); assert(!get('workspace-form').hidden);
  discard = true;
  await get('workspace-cancel').onclick();
  assert(get('workspace-form').hidden);
  assert.equal(calls.filter(call => call.payload && call.url === '/api/workspaces').length, 0);
  if (file === 'menu.html') assert.equal(homeCount, 1);
  else assert(!get('settings-dialog').open);

  await get('workspace-open').onclick();
  get('workspace-manual-mode').onclick();
  await get('workspace-form').onsubmit({preventDefault() {}});
  assert(!get('workspace-review').hidden);
  assert.equal(saved.mode, 'home', 'Review never persists');
  block = true;
  const saving = get('workspace-form').onsubmit({preventDefault() {}});
  await tick();
  const before = calls.length;
  await get('workspace-form').onsubmit({preventDefault() {}});
  await context.RepoHubWorkspaces.close(true);
  assert.equal(calls.length, before, 'No duplicate submit or close while saving');
  assert(get('settings-dialog').open);
  release(); await saving; block = false;
  assert(!get('workspace-form').hidden);
  assert(!get('workspace-reload').hidden, 'Conflict offers explicit reload');
  assert.equal(saved.mode, 'home', 'Conflict preserves the saved source');
  assert.equal(get('workspace-manual-mode')['aria-pressed'], 'true', 'Conflict keeps the draft');
  fail = false;
  await get('workspace-form').onsubmit({preventDefault() {}});
  await get('workspace-form').onsubmit({preventDefault() {}});
  assert.equal(saved.mode, 'manual');
  assert.deepEqual(saved.paths, ['/synthetic/repos/Project']);
  assert(get('workspace-form').hidden);
  assert.equal(calls.filter(call => call.payload && call.url === '/api/workspaces').length, 2);
  if (file === 'menu.html') assert.equal(homeCount, 2);
  else assert(!get('settings-dialog').open);
}
(async () => {
  await surface('menu.html');
  await surface('index.html');
  console.log('Both folder hosts: guarded cancellation, review-only staging, save serialization and conflict preservation passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
