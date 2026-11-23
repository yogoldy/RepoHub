// Execute the shipped preference page with an isolated, typed native bridge.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const crypto = require('node:crypto').webcrypto;
const policy = require('../web/repo-status.js');
const html = fs.readFileSync('web/menu.html', 'utf8');
const nodes = new Map([...html.matchAll(/\bid="([^"]+)"/g)].map(match => [match[1], {}]));
const get = id => nodes.get(id);
const listeners = {};
let saved = 'pending';
let fail = false;
let hold = false;
let discard = false;
let release;
let home = 0;
const calls = [];
const root = {
  crypto, RepoStatus: policy,
  addEventListener: (name, action) => { listeners[name] = action; },
  RepoHubSettings: {confirmDiscard: async dirty => !dirty || discard, showHome() { home++; }},
  webkit: {messageHandlers: {repoHub: {postMessage(body) {
    calls.push(body);
    const reply = () => {
      const result = body.action === 'getMenuAppearance' ? 'loaded'
        : fail || body.revision !== saved ? 'conflict' : 'saved';
      if (result === 'saved') saved = body.mode;
      listeners.repoHubMenuAppearance({detail: {request_id: body.request_id,
        result, mode: saved, revision: saved}});
    };
    if (hold && body.action === 'saveMenuAppearance') release = reply;
    else queueMicrotask(reply);
  }}}},
};
const context = {window: root, document: {getElementById: get},
  Uint8Array, setTimeout, clearTimeout};
vm.runInNewContext(fs.readFileSync('web/menu-appearance.js', 'utf8'), context);
const page = root.RepoHubMenuAppearance;
const change = mode => { get('menu-count-mode').value = mode; get('menu-count-mode').onchange(); };
const tick = () => new Promise(resolve => setImmediate(resolve));
(async () => {
  await page.open();
  assert.equal(saved, 'pending');
  assert(get('menu-appearance-save').disabled);
  // Inject only shared presentation results: the page must not reinterpret raw data.
  page.update({backup: {}}, [{category: 'backup_pending', label: 'First backup pending', phase: 'changed'},
    {category: 'backed_up', label: 'Backed up', phase: 'ready', ready: true}]);
  assert.equal(get('menu-count-preview').textContent, '1');
  change('edits');
  assert.equal(get('menu-count-preview').textContent, '');
  assert.equal(saved, 'pending', 'Changing the select never saves');
  assert.equal(await page.leave(), false);
  assert.equal(get('menu-count-mode').value, 'edits');
  discard = true;
  assert.equal(await page.leave(), true);
  assert.equal(get('menu-count-mode').value, 'pending');
  change('edits');
  fail = true;
  await get('menu-appearance-save').onclick();
  assert.equal(saved, 'pending');
  assert.equal(get('menu-count-mode').value, 'edits');
  assert.match(get('menu-appearance-error').textContent, /changed elsewhere/);
  fail = false;
  hold = true;
  const save = get('menu-appearance-save').onclick();
  await tick();
  const count = calls.length;
  await get('menu-appearance-save').onclick();
  assert.equal(calls.length, count);
  assert.equal(await page.leave(), false, 'A save cannot be interrupted by Close or Back');
  assert(get('menu-count-mode').disabled);
  release();
  await save;
  assert.equal(saved, 'edits');
  assert.equal(home, 1);
  hold = false;
  await page.open();
  assert.equal(get('menu-count-mode').value, 'edits');
  assert(get('menu-appearance-save').disabled);
  assert(calls.every(call => /^[a-f0-9]{24}$/.test(call.request_id)));
  console.log('Appearance preference: preview, explicit save, discard, conflicts, serialization and reload passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
