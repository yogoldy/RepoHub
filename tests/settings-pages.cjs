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
  assert(get('settings-dialog').open);
  assert(!get('settings-home').hidden, 'Saved global schedule returns to Settings home');
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

  await context.openSettings();
  assert(!get('settings-home').hidden);
  assert(get('settings-back').hidden);
  await get('settings-nav-schedule').onclick();
  assert(get('settings-home').hidden);
  assert(!get('settings-page-schedule').hidden);
  assert(!get('schedule-actions').hidden);
  change('adapter-frequency', '30');
  const accessRequest = context.window.RepoHubSettings.openAccess(); await tick();
  assert(get('settings-discard').open);
  get('settings-keep').onclick(); await accessRequest;
  assert(!get('settings-page-schedule').hidden, 'Native access entry cannot hide a declined dirty draft');
  assert.equal(Number(get('adapter-frequency').value), 30);
  const back = get('settings-back').onclick(); await tick();
  get('settings-keep').onclick(); await back;
  assert(!get('settings-page-schedule').hidden);
  const backDiscard = get('settings-back').onclick(); await tick();
  get('settings-discard-confirm').onclick(); await backDiscard;
  assert(!get('settings-home').hidden);
  assert.equal(Number(get('adapter-frequency').value), 240);
  assert.equal(writes.length, 3, 'Back/discard does not save');
  for (const page of ['notifications', 'updates', 'help', 'access']) {
    get('settings-nav-' + page).onclick();
    assert(!get('settings-page-' + page).hidden);
    assert(get('settings-home').hidden);
    assert(get('schedule-actions').hidden);
    await get('settings-back').onclick();
    assert(!get('settings-home').hidden);
  }
  assert(get('check-updates').disabled, 'Browser has no native update bridge');
  let closedWorkspace;
  context.window.RepoHubWorkspaces = {close: async closeDialog => { closedWorkspace = closeDialog; }};
  get('settings-form').hidden = true;
  await get('settings-back').onclick(); assert.equal(closedWorkspace, false);
  await get('settings-close').onclick(); assert.equal(closedWorkspace, true);
  assert(html.indexOf('id="settings-close"') < html.indexOf('id="settings-content"'));
  assert(html.indexOf('id="settings-content"') < html.indexOf('id="settings-form"'));
  const rows = [...html.matchAll(/id="(settings-nav-[^"]+|workspace-open)" class="settings-row"/g)].map(m => m[1]);
  assert.equal(rows.length, 6);
  assert.equal(rows.at(-1), 'settings-nav-access');
  console.log('Actual settings controller: explicit save, discard/Escape, failed and duplicate saves, and revision-checked inheritance passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
