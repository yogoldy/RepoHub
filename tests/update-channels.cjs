const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const crypto = require('node:crypto').webcrypto;
const nodes = new Map([...fs.readFileSync('web/menu.html', 'utf8').matchAll(/\bid="([^"]+)"/g)].map(m => [m[1], {}]));
const get = id => nodes.get(id);
const listeners = {};
let channel = 'stable';
let revision = 'initial';
let discard = false;
let failure = '';
let hold = false;
let release;
const calls = [];
const root = {
  crypto, addEventListener(name, callback) { listeners[name] = callback; },
  RepoHubSettings: {confirmDiscard: async dirty => !dirty || discard},
  webkit: {messageHandlers: {repoHub: {postMessage(body) {
    calls.push(body);
    const reply = () => {
      let result = body.action === 'getUpdateChannel' ? 'loaded' : failure || 'saved';
      if (result === 'saved') {
        channel = body.channel;
        revision = '12345678-1234-1234-1234-123456789abc';
      }
      listeners.repoHubUpdateChannel({detail: {request_id: body.request_id, result, channel, revision}});
    };
    if (hold) release = reply;
    else queueMicrotask(reply);
  }}}},
};
vm.runInNewContext(fs.readFileSync('web/update-channels.js', 'utf8'), {
  window: root, document: {getElementById: get}, Uint8Array, setTimeout, clearTimeout,
});
const page = root.RepoHubUpdateChannels;
const change = value => { get('update-channel').value = value; get('update-channel').onchange(); };
(async () => {
  await page.open();
  assert.equal(get('update-channel').value, 'stable');
  change('dev');
  assert.equal(channel, 'stable');
  assert.equal(await page.leave(), false);
  discard = true;
  assert.equal(await page.leave(), true);
  assert.equal(get('update-channel').value, 'stable');
  for (failure of ['busy', 'conflict']) {
    change('dev');
    await get('update-channel-save').onclick();
    assert.equal(channel, 'stable');
    assert.equal(get('update-channel').value, 'dev');
    assert(get('update-channel-error').textContent);
  }
  failure = '';
  hold = true;
  const save = get('update-channel-save').onclick();
  const count = calls.length;
  await get('update-channel-save').onclick();
  assert.equal(calls.length, count);
  assert.equal(await page.leave(), false);
  assert(get('check-updates').disabled);
  release();
  await save;
  hold = false;
  assert.equal(channel, 'dev');
  await page.open();
  assert.equal(get('update-channel').value, 'dev');
  assert(get('update-channel-save').disabled);
  assert.match(get('update-channel-note').textContent, /does not downgrade/);
  change('foreign');
  assert(get('update-channel-save').disabled);
  assert(calls.every(call => /^[a-f0-9]{24}$/.test(call.request_id)));
  console.log('Update channel controller: save/discard, busy/conflict, no duplicate saves and reload passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
