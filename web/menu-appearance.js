/* This page chooses a count, not a new interpretation of repository state. */
(function(root) {
  const $ = id => document.getElementById(id);
  const bridge = root.webkit?.messageHandlers?.repoHub;
  const modes = new Set(['pending', 'edits', 'none']);
  const pending = new Map();
  let savedMode = 'pending';
  let revision = 'pending';
  let loading = false;
  let saving = false;
  let generation = 0;
  let status = null;
  let states = [];

  function request(action, fields = {}) {
    const bytes = new Uint8Array(12);
    root.crypto.getRandomValues(bytes);
    const requestID = [...bytes].map(value => value.toString(16).padStart(2, '0')).join('');
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        pending.delete(requestID);
        reject(new Error('The app did not confirm this change. Your draft is still here.'));
      }, 8000);
      pending.set(requestID, {resolve, reject, timer});
      try {
        bridge.postMessage({action, request_id: requestID, ...fields});
      } catch (error) {
        clearTimeout(timer);
        pending.delete(requestID);
        reject(error);
      }
    });
  }

  root.addEventListener('repoHubMenuAppearance', event => {
    const detail = event.detail;
    const call = pending.get(detail?.request_id);
    if (!call) return;
    clearTimeout(call.timer);
    pending.delete(detail.request_id);
    if (detail.result !== 'saved' && detail.result !== 'loaded') {
      call.reject(new Error(detail.result === 'conflict'
        ? 'This setting changed elsewhere. Reopen this page before saving.'
        : 'The app could not confirm this setting. Your draft is still here.'));
    } else if (!modes.has(detail.mode) || !modes.has(detail.revision)) {
      call.reject(new Error('The app returned an unsupported setting.'));
    } else {
      call.resolve(detail);
    }
  });

  function dirty() {
    return $('menu-count-mode').value !== savedMode;
  }

  function render() {
    const mode = $('menu-count-mode').value;
    $('menu-count-mode').disabled = loading || saving;
    $('menu-appearance-save').disabled = !bridge || loading || saving || !dirty();
    $('menu-appearance-save').textContent = saving ? 'Saving…' : 'Save changes';
    $('menu-appearance-cancel').disabled = saving;
    const descriptions = {
      pending: 'Counts repos whose status is waiting for a backup, including first backups.',
      edits: 'Counts confirmed file, Git or protected metadata changes. Excludes first backups and changes still being checked.',
      none: 'Shows the icon without a numeric count.',
    };
    $('menu-count-description').textContent = descriptions[mode] || '';
    const summary = status ? root.RepoStatus.summarizeMenuBar(states, mode,
      status.backup, status.data_cloud) : null;
    $('menu-count-preview').textContent = summary?.title.trim() || '';
    $('menu-count-caption').textContent = summary?.tooltip || 'Waiting for current status…';
    $('menu-appearance-note').textContent = !bridge
      ? 'Preview only. Save this preference in the installed Mac app.'
      : loading ? 'Loading the saved preference…' : 'Saved separately on this Mac.';
  }

  async function open() {
    const current = ++generation;
    $('menu-appearance-error').textContent = '';
    $('menu-count-mode').value = savedMode;
    loading = !!bridge;
    render();
    if (!bridge) return;
    try {
      const result = await request('getMenuAppearance');
      if (current !== generation) return;
      savedMode = result.mode;
      revision = result.revision;
      $('menu-count-mode').value = savedMode;
    } catch (error) {
      if (current === generation) $('menu-appearance-error').textContent = error.message;
    } finally {
      if (current === generation) {
        loading = false;
        render();
      }
    }
  }

  async function leave() {
    if (saving) return false;
    if (!await root.RepoHubSettings.confirmDiscard(dirty())) return false;
    generation++;
    loading = false;
    $('menu-count-mode').value = savedMode;
    $('menu-appearance-error').textContent = '';
    render();
    return true;
  }

  $('menu-count-mode').onchange = render;
  $('menu-appearance-cancel').onclick = () => $('settings-back').click();
  $('menu-appearance-save').onclick = async () => {
    if (!bridge || loading || saving || !dirty()) return;
    const mode = $('menu-count-mode').value;
    if (!modes.has(mode)) return;
    saving = true;
    $('menu-appearance-error').textContent = '';
    render();
    try {
      const result = await request('saveMenuAppearance', {mode, revision});
      savedMode = result.mode;
      revision = result.revision;
      root.RepoHubSettings.showHome();
    } catch (error) {
      $('menu-appearance-error').textContent = error.message;
    } finally {
      saving = false;
      render();
    }
  };
  root.RepoHubMenuAppearance = {open, leave, recordNative(value, summary) {
    void root.RepoDiagnostics.recordMenuBar(value, summary);
  }, update(value, presentations) {
    status = value;
    states = presentations;
    render();
  }};
})(window);
