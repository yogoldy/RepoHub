/* Run the actual schedule controller with isolated API responses, never daily settings. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'web/menu.html'), 'utf8');
const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map(match => match[1]);
assert.equal(new Set(ids).size, ids.length);
class Element {
  constructor() {
    this.value = ''; this.checked = false; this.disabled = false;
    this.hidden = false; this.open = false; this.listeners = {};
  }
  addEventListener(event, callback) { this.listeners[event] = callback; }
  showModal() { this.open = true; }
  close() { this.open = false; }
  focus() {}
}
const nodes = new Map(ids.map(id => [id, new Element()]));
const get = id => { assert(nodes.has(id), 'Existing HTML control: ' + id); return nodes.get(id); };
const policy = {
  battery: {frequency_minutes: 60, after_edits: false, edit_delay_minutes: 5},
  adapter: {frequency_minutes: 240, after_edits: false, edit_delay_minutes: 5},
};
let fail = false, hold = false, resume, override = true;
const writes = [];
const context = {
  window: {}, $: selector => get(selector.slice(1)),
  settingsRepo: null, settingsRevision: '', defaultsRevision: '', settingsDefaults: null,
  sessionToken: '', menuState: {repos: [{id: 'repo-a', name: 'Synthetic repo'}]},
  load: async () => {},
  api: async (url, payload) => {
    if (url === '/api/session') return {token: 'synthetic-token'};
    if (payload === undefined) return {
      settings: structuredClone(policy), defaults: structuredClone(policy),
      revision: 'original-revision', defaults_revision: 'original-defaults',
      override, power_source: 'adapter',
    };
    writes.push({url, payload: JSON.parse(JSON.stringify(payload))});
    if (hold) await new Promise(resolve => { resume = resolve; });
    if (fail) throw new Error('Settings changed elsewhere. Reload before saving.');
    return {settings: payload.settings, revision: 'new-revision'};
  },
};
const code = fs.readFileSync(path.join(root, 'web/menu.js'), 'utf8');
const start = code.indexOf('const powerName =');
const end = code.indexOf("window.addEventListener('resize'", start);
assert(start > 0 && end > start);
vm.createContext(context);
vm.runInContext(code.slice(start, end), context);
const tick = () => new Promise(resolve => setImmediate(resolve));
const submit = () => get('settings-form').onsubmit({preventDefault() {}});
function change(id, value) {
  get(id).value = value;
  get('settings-form').listeners.change();
}
(async () => {
  await context.openSettings();
  assert(get('settings-dialog').open);
  assert(get('settings-save').disabled, 'No-change saves are disabled');
  await submit(); assert.equal(writes.length, 0);
  change('adapter-frequency', '120');
  assert(!get('settings-save').disabled);
  const close = get('settings-close').onclick(); await tick();
  assert(get('settings-discard').open);
  get('settings-keep').onclick(); await close;
  assert(get('settings-dialog').open);
  assert.equal(Number(get('adapter-frequency').value), 120);
  assert.equal(writes.length, 0, 'Edits and navigation never persist');

  let prevented = false;
  get('settings-dialog').listeners.cancel({preventDefault() { prevented = true; }});
  await tick(); assert(prevented); assert(get('settings-discard').open);
  get('settings-discard').listeners.cancel({preventDefault() {}});
  await tick(); assert(get('settings-dialog').open, 'Escape keeps the unsaved draft');

  fail = true;
  await submit();
  assert(get('settings-dialog').open);
  assert.equal(Number(get('adapter-frequency').value), 120);
  assert.match(get('settings-error').textContent, /still here/);
  assert.equal(writes.at(-1).payload.revision, 'original-revision');
  assert(!get('settings-save').disabled, 'Failed save can be retried');

  fail = false; hold = true;
  const saving = submit(); await tick();
  assert(get('settings-save').disabled);
  assert(get('adapter-frequency').disabled);
  const count = writes.length;
  await submit(); await get('settings-close').onclick();
  assert.equal(writes.length, count, 'One save request while busy');
  assert(get('settings-dialog').open, 'Closing cannot interrupt an in-flight save');
  resume(); await saving; hold = false;
  assert(!get('settings-dialog').open);
  assert.equal(writes.at(-1).url, '/api/settings');
  assert.equal(writes.at(-1).payload.settings.adapter.frequency_minutes, 120);

  await context.openSettings('repo-a');
  get('repo-defaults').checked = true;
  get('repo-defaults').onchange();
  await submit();
  assert.equal(writes.at(-1).url, '/api/repo-settings/repo-a');
  assert.equal(writes.at(-1).payload.settings, null);
  assert.equal(writes.at(-1).payload.defaults_revision, 'original-defaults');

  override = false;
  await context.openSettings('repo-a');
  assert(get('battery-frequency').disabled);
  get('repo-defaults').checked = false; get('repo-defaults').onchange();
  assert(!get('settings-save').disabled, 'Opting out of inheritance is a real edit');
  const discard = get('settings-close').onclick(); await tick();
  get('settings-discard-confirm').onclick(); await discard;
  assert(!get('settings-dialog').open);
  assert(get('repo-defaults').checked, 'Discard restores the saved inheritance choice');
  assert.equal(writes.length, 3);
  console.log('Actual settings controller: explicit save, discard/Escape, failed and duplicate saves, and revision-checked inheritance passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
