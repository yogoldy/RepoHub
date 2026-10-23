/* A channel is a per-Mac update preference, not repository or backup state. */
(function(root) {
  const $ = id => document.getElementById(id);
  const bridge = root.webkit?.messageHandlers?.repoHub;
  const channels = new Set(['stable', 'dev']);
  const requests = new Map();
  let saved = 'stable';
  let revision = 'initial';
  let experimentalEnabled = false;
  let policyLoaded = !bridge;
  let loading = false;
  let saving = false;
  let generation = 0;

  function request(action, fields = {}) {
    const bytes = new Uint8Array(12);
    root.crypto.getRandomValues(bytes);
    const requestID = [...bytes].map(value => value.toString(16).padStart(2, '0')).join('');
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        requests.delete(requestID);
        reject(new Error('The app did not confirm this setting. Reopen this page to check the saved channel.'));
      }, 8000);
      requests.set(requestID, {resolve, reject, timer});
      try {
        bridge.postMessage({action, request_id: requestID, ...fields});
      } catch (error) {
        clearTimeout(timer);
        requests.delete(requestID);
        reject(error);
      }
    });
  }

  root.addEventListener('repoHubUpdateChannel', event => {
    const detail = event.detail;
    const call = requests.get(detail?.request_id);
    if (!call) return;
    requests.delete(detail.request_id);
    clearTimeout(call.timer);
    if (!['loaded', 'saved'].includes(detail.result)) {
      const messages = {
        busy: 'Wait for the current backup or update check to finish, then try again.',
        conflict: 'The saved channel changed elsewhere. Reopen this page before saving.',
        experimental_disabled: 'Experimental updates are not enabled on this Mac.',
      };
      call.reject(new Error(messages[detail.result] || 'The app could not save this channel.'));
    } else if (!channels.has(detail.channel) || typeof detail.revision !== 'string'
        || !/^(initial|[a-f0-9-]{36})$/i.test(detail.revision)
        || !['enabled', 'disabled'].includes(detail.experimental_channels)
        || (detail.experimental_channels === 'disabled' && detail.channel !== 'stable')) {
      call.reject(new Error('The app returned an unsupported channel setting.'));
    } else {
      call.resolve(detail);
    }
  });

  function render() {
    $('update-channel-controls').hidden = !experimentalEnabled || loading;
    $('update-channel-actions').hidden = !experimentalEnabled || loading;
    $('update-channel').disabled = !experimentalEnabled || !bridge || loading || saving;
    $('update-channel-save').disabled = !experimentalEnabled || !bridge || loading || saving
      || !channels.has($('update-channel').value) || $('update-channel').value === saved;
    $('update-channel-save').textContent = saving ? 'Saving…' : 'Save changes';
    $('update-channel-cancel').disabled = saving;
    $('check-updates').disabled = !bridge || !policyLoaded || loading || saving;
    const descriptions = {
      stable: 'Public releases promoted after automated checks and installed-Mac acceptance.',
      dev: 'Experimental builds. Release notes record local checks, GitHub checks and installed acceptance.',
    };
    $('update-channel-description').textContent = loading ? ''
      : !policyLoaded ? 'Update settings are unavailable. Reopen this page to try again.'
      : experimentalEnabled
      ? descriptions[$('update-channel').value] || ''
      : 'Stable updates are checked automatically. You can also check now.';
    $('update-channel-note').textContent = !bridge ? 'Preview only. Save this preference in the installed Mac app.'
      : loading ? 'Loading this Mac’s update settings…'
      : experimentalEnabled ? 'Experimental channels are enabled on this Mac. Switching channels does not downgrade an installed newer build.' : '';
  }

  async function open() {
    const current = ++generation;
    $('update-channel-error').textContent = '';
    $('update-channel').value = saved;
    experimentalEnabled = false;
    policyLoaded = !bridge;
    loading = !!bridge;
    render();
    if (!bridge) return;
    try {
      const result = await request('getUpdateChannel');
      if (current !== generation) return;
      saved = result.channel;
      revision = result.revision;
      experimentalEnabled = result.experimental_channels === 'enabled';
      policyLoaded = true;
      $('update-channel').value = saved;
    } catch (error) {
      if (current === generation) $('update-channel-error').textContent = error.message;
    } finally {
      if (current === generation) { loading = false; render(); }
    }
  }

  async function leave() {
    if (saving) return false;
    if (!await root.RepoHubSettings.confirmDiscard($('update-channel').value !== saved)) return false;
    generation++;
    loading = false;
    $('update-channel').value = saved;
    $('update-channel-error').textContent = '';
    render();
    return true;
  }

  $('update-channel').onchange = render;
  $('update-channel-cancel').onclick = () => $('settings-back').click();
  $('update-channel-save').onclick = async () => {
    if ($('update-channel-save').disabled) return;
    const channel = $('update-channel').value;
    saving = true;
    $('update-channel-error').textContent = '';
    render();
    try {
      const result = await request('saveUpdateChannel', {channel, revision});
      saved = result.channel;
      revision = result.revision;
      experimentalEnabled = result.experimental_channels === 'enabled';
      policyLoaded = true;
      $('update-channel').value = saved;
    } catch (error) {
      $('update-channel-error').textContent = error.message;
    } finally {
      saving = false;
      render();
    }
  };
  root.RepoHubUpdateChannels = {open, leave};
})(window);
