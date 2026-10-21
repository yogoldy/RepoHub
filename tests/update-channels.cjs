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
let experimental = 'disabled';
let badReply;
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
      listeners.repoHubUpdateChannel({detail: {request_id: body.request_id, result, channel, revision,
        experimental_channels: experimental, ...badReply}});
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
  assert(get('update-channel-controls').hidden);
  assert(get('update-channel-actions').hidden);
  assert(get('update-channel').disabled);
  assert(!get('check-updates').disabled);
  assert.match(get('update-channel-description').textContent, /Stable/);
  change('dev');
  const ordinaryCalls = calls.length;
  await get('update-channel-save').onclick();
  assert.equal(calls.length, ordinaryCalls, 'A DOM edit must not enable experimental saving');
  experimental = 'enabled';
  await page.open();
  assert(!get('update-channel-controls').hidden);
  assert(!get('update-channel-actions').hidden);
  assert(!get('update-channel').disabled);
  change('dev');
  assert.equal(channel, 'stable');
  assert.equal(await page.leave(), false);
  discard = true;
  assert.equal(await page.leave(), true);
  assert.equal(get('update-channel').value, 'stable');
  for (failure of ['busy', 'conflict', 'experimental_disabled']) {
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
  // Unknown, missing and internally inconsistent native policy replies fail closed.
  for (badReply of [
    {experimental_channels: undefined}, {experimental_channels: true},
    {experimental_channels: 'outside'}, {experimental_channels: 'disabled', channel: 'dev'},
  ]) {
    await page.open();
    assert(get('update-channel-controls').hidden);
    assert(get('update-channel-save').disabled);
    assert.match(get('update-channel-error').textContent, /unsupported/);
  }
  badReply = undefined;
  channel = 'stable';
  experimental = 'disabled';
  hold = true;
  const opening = page.open();
  assert(get('update-channel-controls').hidden, 'Do not flash controls before native policy loads');
  release();
  await opening;
  hold = false;
  assert(get('update-channel-controls').hidden);
  delete root.webkit;
  // The bridge is captured at load, so test the actual browser-only module separately.
  const preview = {...root};
  vm.runInNewContext(fs.readFileSync('web/update-channels.js', 'utf8'), {
    window: preview, document: {getElementById: get}, Uint8Array, setTimeout, clearTimeout,
  });
  await preview.RepoHubUpdateChannels.open();
  assert(get('update-channel-controls').hidden);
  assert(get('update-channel-save').disabled);
  assert(get('check-updates').disabled);
  assert(calls.every(call => /^[a-f0-9]{24}$/.test(call.request_id)));
  console.log('Update channel controller: Stable-only defaults, opt-in, invalid replies, save/discard and busy/conflict passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
