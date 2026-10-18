// Exercise the shipped scan request and fetch wrapper without any daily helper.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('web/menu.js', 'utf8');
const html = fs.readFileSync('web/menu.html', 'utf8');
assert.match(html, /<button id="rescan"[^>]*type="button"[^>]*>[\s\S]*?<span id="rescan-label">Rescan now<\/span>\s*<\/button>/);
const nodes = {rescan: {disabled: false}, 'rescan-label': {textContent: 'Rescan now'},
  notice: {textContent: ''}};
// Updating the button's entire text would remove its new icon on the first click.
Object.defineProperty(nodes.rescan, 'textContent', {
  set() { throw new Error('Rescan must preserve the button icon'); },
});
const calls = [];
let acknowledge;
let rejectScan = false;
let loads = 0;
const context = vm.createContext({
  $: selector => nodes[selector.slice(1)], requestingRescan: false, sessionToken: 'expired',
  AbortController, setTimeout, clearTimeout,
  load: async () => { loads++; },
  fetch: async (path, options = {}) => {
    calls.push({path, options});
    if (path === '/api/session') return {ok: true, json: async () => ({token: 'current-token'})};
    assert.equal(path, '/api/scan', 'Rescan must never invoke the backup endpoint');
    assert.equal(options.method, 'POST');
    assert.equal(options.headers['X-RepoHub-Token'], 'current-token');
    assert.equal(options.body, '{}');
    if (rejectScan) return {ok: false, json: async () => ({error: 'Synthetic refusal'})};
    return new Promise(resolve => { acknowledge = () => resolve({
      ok: true, json: async () => ({accepted: true}),
    }); });
  },
});
vm.runInContext(source.slice(source.indexOf('async function api('),
  source.indexOf('function nativeAction(')), context);
vm.runInContext(source.slice(source.indexOf('async function rescanNow('),
  source.indexOf("$('#backup').onclick=")), context);

(async () => {
  const first = nodes.rescan.onclick();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(nodes.rescan.disabled, true);
  assert.equal(nodes['rescan-label'].textContent, 'Requesting scan…');
  await nodes.rescan.onclick();
  assert.equal(calls.filter(call => call.path === '/api/scan').length, 1,
    'Repeated clicks cannot submit concurrent scan requests');
  acknowledge();
  await first;
  assert.equal(loads, 1);
  assert.equal(nodes.rescan.disabled, false);
  assert.equal(nodes['rescan-label'].textContent, 'Rescan now');
  assert.equal(nodes.notice.textContent, 'Scan requested. Status will update automatically.');
  assert.doesNotMatch(nodes.notice.textContent, /completed|backed up|verified/i);

  rejectScan = true;
  await nodes.rescan.onclick();
  assert.equal(nodes.rescan.disabled, false);
  assert.equal(nodes['rescan-label'].textContent, 'Rescan now');
  assert.equal(loads, 1, 'A rejected request cannot claim a refreshed result');
  assert.match(nodes.notice.textContent, /Scan could not be requested.*Synthetic refusal/);
  assert.equal(calls.filter(call => call.path === '/api/session').length, 2);
  console.log('Rescan controller: fresh token, duplicate guard, accepted versus completed, and failure recovery passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
