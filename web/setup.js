/* One explicit save activates the reviewed draft; discovery only adds candidates. */
(function(root) {
  const steps = ['sources', 'destination', 'access', 'schedule', 'review'];
  function createDraft(value) {
    return {mode: value.source.mode, home: value.source.home || '',
      paths: value.source.paths || value.workspaces.map(row => row.path),
      destination: value.destination, settings: JSON.parse(JSON.stringify(value.settings)),
      revision: value.revision, discovery_parent: value.discovery_parent || ''};
  }
  function payload(state) {
    return {source: state.mode === 'home' ? {mode: 'home', home: state.home}
      : {mode: 'manual', paths: [...state.paths]}, destination: state.destination,
      settings: state.settings, revision: state.revision, discovery_parent: state.discovery_parent};
  }
  function addPaths(state, paths) {
    state.paths = [...new Set([...state.paths, ...paths])];
  }
  const model = {createDraft, payload, addPaths};
  if (typeof module === 'object' && module.exports) { module.exports = model; return; }
  const $ = id => document.getElementById(id);
  const native = !!root.webkit?.messageHandlers?.repoHub;
  let draft, initial, step = 0, busy = false, receipt = null, receiptDraft = '', pending = null, discovery = null;
  const chosen = new Set();
  function send(action, extra = {}) {
    if (native) root.webkit.messageHandlers.repoHub.postMessage({action, ...extra});
  }
  async function request(path, value) {
    let options = {};
    if (value !== undefined) {
      const session = await fetch('/api/session');
      if (!session.ok) throw new Error('The local helper is unavailable.');
      options = {method: 'POST', headers: {'Content-Type': 'application/json',
        'X-RepoHub-Token': (await session.json()).token}, body: JSON.stringify(value)};
    }
    const response = await fetch(path, options);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'The helper could not complete this request.');
    return data;
  }
  function failure(error) { $('error').textContent = error.message; }
  function pathRow(name, location, remove) {
    const li = document.createElement('li'), content = document.createElement('div');
    const title = document.createElement('strong'), detail = document.createElement('small');
    title.textContent = name; detail.textContent = location; content.append(title, detail); li.append(content);
    if (remove) {
      const button = document.createElement('button'); button.type = 'button'; button.textContent = 'Remove';
      button.onclick = remove; li.append(button);
    }
    return li;
  }
  function render() {
    if (!draft) return;
    for (let index = 0; index < steps.length; index++) {
      $('step-' + steps[index]).hidden = index !== step;
      $('steps').children[index].setAttribute('aria-current', index === step ? 'step' : 'false');
    }
    for (const mode of ['home', 'manual']) $('mode-' + mode).setAttribute('aria-pressed', String(draft.mode === mode));
    $('source-description').textContent = draft.mode === 'home'
      ? 'Every immediate visible subfolder is monitored, including non-Git folders. New immediate children are added automatically.'
      : 'Each selected folder is one backup source. Git discovery adds reviewed folders to this list.';
    const paths = draft.mode === 'home' ? (draft.home ? [draft.home] : []) : draft.paths;
    $('sources').replaceChildren(...paths.map(path => pathRow(path.split('/').at(-1), path,
      draft.mode === 'manual' ? () => { draft.paths = draft.paths.filter(item => item !== path); receipt = null; render(); } : null)));
    $('pick-sources').textContent = draft.mode === 'home' ? 'Choose repo-home folder…' : 'Add folders…';
    $('destination').textContent = draft.destination || 'No destination selected';
    $('continue-current').hidden = !initial.configured;
    $('browser-note').hidden = native;
    $('back').disabled = step === 0 || busy;
    $('next').textContent = step === 4 ? 'Finish setup' : 'Next';
    $('next').disabled = busy || !!pending || (step === 2 && !receipt);
    $('finish-backup').hidden = step !== 4;
    for (const id of ['mode-home', 'mode-manual', 'check-access', 'finish-backup', 'continue-current', 'reload']) $(id).disabled = busy;
    for (const id of ['pick-sources', 'pick-destination', 'find-git', 'privacy', 'notifications', 'login']) $(id).disabled = !native || busy || !!pending;
    $('find-git').disabled ||= draft.mode === 'home';
    if (receipt && step === 4) {
      $('review-paths').replaceChildren(...receipt.workspaces.map(row => pathRow(
        row.path.split('/').at(-1), row.path + ' → ' + row.backup_path)));
      $('review-removals').textContent = receipt.removed.length
        ? receipt.removed.length + ' previously monitored folders will be removed from monitoring. Their backups stay intact.' : '';
      $('review-old').textContent = receipt.destination_changed && receipt.previous_destination
        ? 'Previous archives stay at ' + receipt.previous_destination : '';
      $('review-schedule').textContent = ['battery', 'adapter'].map(power => {
        const value = draft.settings[power];
        return (power === 'battery' ? 'Battery: ' : 'Power adapter: ')
          + (value.frequency_minutes ? 'every ' + value.frequency_minutes + ' minutes' : 'timed backups off')
          + (value.after_edits ? ', ' + value.edit_delay_minutes + ' minutes after edits' : ', after-edit backups off');
      }).join(' · ');
    }
  }
  function show(index) {
    step = index; $('feedback').textContent = ''; render(); $('step-' + steps[step]).querySelector('h2').focus();
  }
  async function operation(kind, value) {
    const started = await request('/api/setup/' + kind, value);
    while (true) {
      const result = await request('/api/setup/operation');
      if (result.id !== started.id) throw new Error('Another setup operation started. Reload setup.');
      if (result.state === 'failed') throw new Error(result.error + (result.conflict ? ' Reload setup to review the current configuration.' : ''));
      if (result.state === 'complete') return result.value;
      await new Promise(resolve => setTimeout(resolve, 500));
    }
  }
  async function check() {
    busy = true; receipt = null; render(); $('error').textContent = '';
    $('access-status').textContent = 'Checking the selected files, destination and available space…';
    try {
      const value = payload(draft), fingerprint = JSON.stringify(value);
      const checked = await operation('review', value);
      if (fingerprint !== JSON.stringify(payload(draft))) throw new Error('Your choices changed. Check access again.');
      receipt = checked; receiptDraft = fingerprint;
      $('access-status').textContent = 'The helper can read your selected sources and write to the chosen destination.';
      return true;
    } catch (error) { $('access-status').textContent = 'Access or layout needs attention. Review the message and retry.'; failure(error); return false; }
    finally { busy = false; render(); }
  }
  function choose(action) {
    const bytes = new Uint8Array(12); crypto.getRandomValues(bytes);
    pending = {id: [...bytes].map(value => value.toString(16).padStart(2, '0')).join(''), action};
    send(action, {request_id: pending.id}); render();
  }
  root.addEventListener('repoHubSetupPicked', async event => {
    const value = event.detail;
    if (!pending || value?.request_id !== pending.id) return;
    const action = pending.action; pending = null;
    if (value.cancelled) { $('feedback').textContent = 'Selection cancelled. Your saved configuration is unchanged.'; render(); return; }
    if (!Array.isArray(value.paths) || !value.paths.length || value.paths.some(path => typeof path !== 'string' || !path.startsWith('/'))) return render();
    receipt = null; $('error').textContent = '';
    if (action === 'chooseBackupDestination') draft.destination = value.paths[0];
    else if (action === 'chooseDiscoveryParent') {
      draft.discovery_parent = value.paths[0];
      try { await startDiscovery(); } catch (error) { failure(error); }
    } else if (draft.mode === 'home') draft.home = value.paths[0];
    else addPaths(draft, value.paths);
    render();
  });
  async function startDiscovery() {
    discovery = await request('/api/discovery/start', {parent: draft.discovery_parent});
    chosen.clear(); $('discovery-panel').hidden = false;
    while (true) {
      const current = await request('/api/discovery');
      if (current.id !== discovery.id) throw new Error('Discovery changed. Start another scan.');
      discovery = current;
      $('discovery-status').textContent = current.visited + ' folders checked · ' + current.results.length
        + ' candidates · ' + current.state + (current.incomplete ? '. Results are incomplete; some areas were skipped or unavailable.' : '');
      if (current.state !== 'running') break;
      await new Promise(resolve => setTimeout(resolve, 500));
    }
    $('discovery-results').replaceChildren(...discovery.results.map(row => {
      const li = document.createElement('li'), label = document.createElement('label'), input = document.createElement('input');
      input.type = 'checkbox'; input.disabled = !row.selectable;
      input.onchange = () => input.checked ? chosen.add(row.path) : chosen.delete(row.path);
      label.append(input, document.createTextNode(' ' + row.path));
      if (!row.selectable) label.append(document.createTextNode(row.reason === 'external_git_storage'
        ? ' — Git history is stored outside this repo; not supported by discovery.' : ' — Invalid Git marker.'));
      li.append(label); return li;
    }));
    $('cancel-discovery').disabled = true;
  }
  function scheduleFields() {
    $('schedule-fields').replaceChildren(...['battery', 'adapter'].map(power => {
      const section = document.createElement('section'), heading = document.createElement('h3');
      heading.textContent = power === 'battery' ? 'On battery' : 'On power adapter'; section.append(heading);
      for (const [field, title, choices] of [
        ['frequency_minutes', 'Back up every', [0, 15, 30, 60, 120, 240]],
        ['edit_delay_minutes', 'Wait after the last edit', [2, 5, 10, 15, 30]],
      ]) {
        const label = document.createElement('label'), select = document.createElement('select');
        label.textContent = title;
        for (const minutes of choices) {
          const option = document.createElement('option'); option.value = String(minutes);
          option.textContent = minutes === 0 ? 'Off' : minutes + ' minutes'; select.append(option);
        }
        select.value = String(draft.settings[power][field]);
        select.onchange = () => { draft.settings[power][field] = Number(select.value); receipt = null; };
        label.append(select); section.append(label);
      }
      const label = document.createElement('label'), input = document.createElement('input');
      input.type = 'checkbox'; input.checked = draft.settings[power].after_edits;
      input.onchange = () => { draft.settings[power].after_edits = input.checked; receipt = null; };
      label.append(input, document.createTextNode(' Also back up after edits')); section.append(label);
      return section;
    }));
  }
  async function finish(backupNow) {
    if (!receipt || receiptDraft !== JSON.stringify(payload(draft))) { failure(new Error('Review the current choices before saving.')); return; }
    busy = true; render(); $('error').textContent = ''; $('feedback').textContent = 'Applying reviewed setup…';
    try {
      await operation('apply', {draft: payload(draft), review: receipt.review, backup_now: backupNow});
      for (const name of steps) $('step-' + name).hidden = true;
      $('complete').hidden = false; $('setup-actions').hidden = true; $('continue-current').hidden = true;
      $('complete-copy').textContent = backupNow ? 'A backup was requested. Check its status in the menu bar.' : 'Your schedule is active. No backup was started by this save.';
      $('feedback').textContent = '';
    } catch (error) { failure(error); busy = false; render(); }
  }
  $('back').onclick = () => show(step - 1);
  $('next').onclick = async () => {
    if (step === 4) return finish(false);
    if (step === 0 && !(draft.mode === 'home' ? draft.home : draft.paths.length)) return failure(new Error('Choose at least one source.'));
    if (step === 1 && !draft.destination) return failure(new Error('Choose an iCloud backup folder.'));
    if (step === 3 && (!receipt || receiptDraft !== JSON.stringify(payload(draft))) && !await check()) return;
    show(step + 1);
    if (step === 2) await check();
  };
  $('finish-backup').onclick = () => finish(true); $('check-access').onclick = check;
  for (const mode of ['home', 'manual']) $('mode-' + mode).onclick = () => {
    if (draft.mode === 'home' && mode === 'manual') $('feedback').textContent = 'Current folders are kept. Individual mode stops automatically adding new immediate children.';
    draft.mode = mode; receipt = null; render();
  };
  $('pick-sources').onclick = () => choose(draft.mode === 'home' ? 'chooseRepoHome' : 'chooseRepoFolders');
  $('pick-destination').onclick = () => choose('chooseBackupDestination');
  $('find-git').onclick = () => choose('chooseDiscoveryParent');
  $('add-discovered').onclick = () => { addPaths(draft, [...chosen]); receipt = null; render(); $('feedback').textContent = chosen.size + ' repos added to your draft. Review before saving.'; };
  $('cancel-discovery').onclick = async () => { try { if (discovery) await request('/api/discovery/cancel', {id: discovery.id}); } catch (error) { failure(error); } };
  $('continue-current').onclick = async () => {
    try { await request('/api/setup/continue', {revision: initial.revision}); send('closeSetup'); $('feedback').textContent = 'Current settings retained.'; }
    catch (error) { failure(error); }
  };
  $('privacy').onclick = () => send('privacySettings'); $('notifications').onclick = () => send('requestNotifications');
  $('login').onclick = () => send('loginSettings'); $('quit').onclick = () => send('quit'); $('done').onclick = () => send('closeSetup');
  $('help').onclick = () => $('help-dialog').showModal(); $('help-close').onclick = () => $('help-dialog').close();
  async function load() {
    try {
      initial = await request('/api/setup'); draft = createDraft(initial);
      receipt = null; step = 0; pending = null; $('error').textContent = '';
      $('existing-note').hidden = !initial.configured; scheduleFields(); render();
      if (initial.recovery_required) throw new Error('An interrupted setup save needs recovery. Restart RepoHub before continuing.');
    } catch (error) { failure(error); $('next').disabled = true; }
  }
  $('reload').onclick = () => {
    if (!draft || root.confirm('Discard this draft and reload saved settings?')) void load();
  };
  void load();
})(typeof globalThis === 'object' ? globalThis : this);
