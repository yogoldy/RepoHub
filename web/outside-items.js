/* Review content a repo points to outside its folder. Choices never change backup status. */
(function(root) {
  const $ = id => document.getElementById(id);
  const escape = value => String(value == null ? '' : value).replace(/[&<>"']/g,
    c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const clone = value => JSON.parse(JSON.stringify(value));
  let repoId = null, saved = null, draft = null, revision = '', report = null;
  let loading = false, saving = false, removing = false, generation = 0;
  let kept = [], confirmItem = null;

  async function call(path, payload) {
    const options = {};
    if (payload !== undefined) {
      const session = await (await root.fetch('/api/session')).json();
      options.method = 'POST';
      options.headers = {'Content-Type': 'application/json', 'X-RepoHub-Token': session.token};
      options.body = JSON.stringify(payload);
    }
    const response = await root.fetch(path, options);
    const value = await response.json();
    if (!response.ok) throw new Error(value.error || 'Request failed');
    return value;
  }

  function bytes(n) {
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let i = 0;
    while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
    return new Intl.NumberFormat(undefined, {maximumFractionDigits: 1}).format(n) + ' ' + units[i];
  }
  function size(item) {
    if (typeof item.bytes !== 'number') return 'size unknown';
    return (item.complete ? '' : 'at least ') + bytes(item.bytes);
  }
  function dirty() {
    return !!saved && JSON.stringify(draft) !== JSON.stringify(saved);
  }
  function option(value, label, current) {
    return '<option value="' + value + '"' + (value === current ? ' selected' : '') + '>' + label + '</option>';
  }
  function describeCheckout(item) {
    if (item.state !== 'present') return 'Removed · nothing left to back up';
    const changes = item.changed_files === 0 ? 'no uncommitted changes'
      : item.changed_files == null ? 'uncommitted changes unknown'
      : item.changed_files + ' uncommitted ' + (item.changed_files === 1 ? 'change' : 'changes');
    return size(item) + ' · ' + changes;
  }

  function renderList() {
    if (!report) { $('outside-list').innerHTML = ''; return; }
    const folders = report.linked_folders || [];
    const checkouts = report.checkouts || [];
    const reinstall = report.reinstall || [];
    let markup = '';
    if (folders.length) {
      markup += '<section class="outside-group"><h3>Linked folders</h3>' + folders.map(item => {
        if (item.blocked) return '<div class="outside-item"><p><strong>' + escape(item.path) + '</strong> <small>→ '
          + escape(item.target) + '</small></p><p class="settings-note">Kept as a link: ' + escape(item.blocked) + '.</p></div>';
        const current = draft.linked_folders[item.path] || 'link_only';
        return '<div class="outside-item"><p><strong>' + escape(item.path) + '</strong> <small>→ '
          + escape(item.target) + ' · ' + escape(size(item)) + '</small></p>'
          + '<select data-link="' + escape(item.path) + '" aria-label="Backup choice for ' + escape(item.path) + '">'
          + option('link_only', 'Keep link only', current) + option('include', 'Include contents', current)
          + '</select></div>';
      }).join('') + '</section>';
    }
    if (checkouts.length) {
      markup += '<section class="outside-group"><h3>Linked checkouts</h3>'
        + '<select id="outside-checkouts" aria-label="Backup choice for linked checkouts">'
        + option('committed_only', 'Committed work only', draft.checkouts)
        + option('include', 'Include checkout folders', draft.checkouts) + '</select>'
        + checkouts.map(item => '<p class="outside-item"><strong>' + escape(item.name) + '</strong> <small>'
          + escape(describeCheckout(item)) + '</small></p>').join('')
        + '<p class="settings-note">Applies to checkouts created later too; each included checkout is saved as its own verified archive. Committed work is already in this repo\'s Git data.</p></section>';
    }
    if (reinstall.length) {
      markup += '<section class="outside-group"><h3>Reinstall on a new Mac</h3>'
        + '<p class="settings-note">Links to installed tools restore as links. Their targets are never copied.</p><ul>'
        + reinstall.map(item => '<li><strong>' + escape(item.path) + '</strong> <small>→ '
          + escape(item.target) + '</small></li>').join('') + '</ul></section>';
    }
    if (kept.length) {
      const day = value => new Intl.DateTimeFormat(undefined, {month: 'short', day: 'numeric'}).format(new Date(value));
      markup += '<section class="outside-group"><h3>Kept after removal</h3>' + kept.map(item => {
        const label = item.reason === 'excluded' ? 'No longer included'
          : 'Removed ' + (item.kind === 'checkouts' ? 'checkout' : 'linked folder');
        const until = item.keep_until ? ' · kept until ' + day(item.keep_until) : ' · kept';
        return '<div class="outside-item"><p><strong>' + escape(item.name) + '</strong> <small>'
          + escape(label + until) + '</small></p><button type="button" data-remove="' + escape(item.item) + '">'
          + (confirmItem === item.item ? 'Confirm remove' : 'Remove now') + '</button></div>';
      }).join('') + '<p class="settings-note">Backups of removed items are kept for 30 days, then deleted automatically.</p></section>';
    }
    $('outside-list').innerHTML = markup
      || '<p class="settings-note">Nothing outside this folder was found in the latest check.</p>';
  }

  function renderState() {
    const busy = loading || saving || removing;
    $('outside-save').disabled = busy || !dirty();
    $('outside-save').textContent = saving ? 'Saving…' : 'Save changes';
    $('outside-cancel').disabled = saving;
    const list = $('outside-list');
    const selects = list.querySelectorAll ? list.querySelectorAll('select, button') : [];
    for (const select of selects) select.disabled = busy;
    $('outside-note').textContent = loading ? 'Checking items outside this folder…'
      : 'Choices are saved on this Mac. Included folders are saved as separate verified archives beside the repo backup, and Backed up appears only after every archive is verified and uploaded.';
  }

  function apply(result) {
    report = result.items;
    saved = clone(result.choices);
    draft = clone(saved);
    revision = result.revision;
    kept = result.kept || [];
    confirmItem = null;
    renderList();
  }

  async function open(id) {
    const current = ++generation;
    repoId = id;
    report = saved = draft = null;
    loading = true;
    $('outside-error').textContent = '';
    renderList();
    renderState();
    try {
      const result = await call('/api/outside/' + encodeURIComponent(id));
      if (current === generation) apply(result);
    } catch (error) {
      if (current === generation) $('outside-error').textContent = error.message;
    } finally {
      if (current === generation) { loading = false; renderState(); }
    }
  }

  async function leave() {
    if (saving || removing) return false;
    if (!await root.RepoHubSettings.confirmDiscard(dirty())) return false;
    generation++;
    loading = false;
    confirmItem = null;
    if (saved) draft = clone(saved);
    renderList();
    $('outside-error').textContent = '';
    renderState();
    return true;
  }

  $('outside-list').onchange = event => {
    const target = event.target;
    if (!draft || !target) return;
    if (target.dataset && target.dataset.link) draft.linked_folders[target.dataset.link] = target.value;
    else if (target.id === 'outside-checkouts') draft.checkouts = target.value;
    renderState();
  };
  $('outside-list').onclick = async event => {
    const id = event.target && event.target.dataset && event.target.dataset.remove;
    if (!id || loading || saving || removing) return;
    if (confirmItem !== id) { confirmItem = id; renderList(); return; }
    const item = kept.find(entry => entry.item === id);
    removing = true;
    $('outside-error').textContent = '';
    renderState();
    try {
      const draftKept = dirty() ? clone(draft) : null;
      apply(await call('/api/outside/' + encodeURIComponent(repoId) + '/remove', {item: id, ref: item.ref}));
      if (draftKept) { draft = draftKept; renderList(); }
    } catch (error) {
      $('outside-error').textContent = error.message;
    } finally {
      removing = false;
      renderState();
    }
  };
  $('outside-cancel').onclick = () => $('settings-back').click();
  $('outside-save').onclick = async () => {
    if (loading || saving || !dirty()) return;
    saving = true;
    $('outside-error').textContent = '';
    renderState();
    try {
      apply(await call('/api/outside/' + encodeURIComponent(repoId), {choices: clone(draft), revision}));
      if (root.RepoHubSettings.finishRepoPage) root.RepoHubSettings.finishRepoPage();
    } catch (error) {
      $('outside-error').textContent = error.message + ' Your choices are still here; nothing was confirmed saved.';
    } finally {
      saving = false;
      renderState();
    }
  };
  root.RepoHubOutside = {open, leave};
})(window);
