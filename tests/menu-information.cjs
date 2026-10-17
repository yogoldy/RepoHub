// Exercise the shipped information controller without a native bridge or saved data.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync('web/menu.html', 'utf8');
const source = fs.readFileSync('web/menu.js', 'utf8');
const nodes = new Map();
for (const match of html.matchAll(/id="([^"]+)"/g)) {
  assert.ok(!nodes.has(match[1]), 'Duplicate HTML id: ' + match[1]);
  nodes.set(match[1], {hidden: false, scrollTop: 100, focus() { this.focused = true; }});
}
const pages = ['home', 'status', 'things'].map(infoPage => ({dataset: {infoPage}}));
const dialog = nodes.get('info-dialog');
dialog.showModal = () => { dialog.open = true; };
dialog.close = () => { dialog.open = false; };
const folder = {
  offsetWidth: 10,
  classList: {add() { folder.highlighted = true; }, remove() { folder.highlighted = false; }},
  scrollIntoView() { folder.scrolled = true; },
};
nodes.get('cards').querySelectorAll = () => [{dataset: {repoId: 'selected'},
  parentElement: {querySelector: () => folder}}];
let reset;
const context = vm.createContext({
  $: selector => nodes.get(selector.slice(1)),
  document: {querySelectorAll: selector => selector === '[data-info-page]' ? pages : []},
  selectedId: 'selected', menuState: {repos: [{id: 'selected', name: 'Test repo'}]},
  motion: () => 'auto', clearTimeout() {}, setTimeout(callback) { reset = callback; return 1; },
});
vm.runInContext(source.slice(source.indexOf('const infoDialog ='),
  source.indexOf("window.addEventListener('repoHubFinderError'")), context);
function checkPage(page) {
  assert.deepEqual(pages.filter(row => !row.hidden).map(row => row.dataset.infoPage), [page]);
  assert.equal(nodes.get('info-back').hidden, page === 'home');
  assert.equal(nodes.get('info-content').scrollTop, 0);
  assert.equal(nodes.get('info-title').focused, true);
}
nodes.get('info').onclick();
assert.equal(dialog.open, true);
checkPage('home');
nodes.get('info-nav-status').onclick();
checkPage('status');
nodes.get('info-back').onclick();
checkPage('home');
nodes.get('info-nav-things').onclick();
checkPage('things');
nodes.get('show-folder').onclick();
assert.equal(dialog.open, false);
assert.equal(folder.highlighted, true);
assert.equal(folder.scrolled, true);
assert.match(nodes.get('folder-demo-status').textContent, /Test repo/);
reset();
assert.equal(folder.highlighted, false);
nodes.get('info').onclick();
checkPage('home');
nodes.get('info-close').onclick();
assert.equal(dialog.open, false);
// The technical region is outside the repo pane and before global backup controls.
assert.match(html, /<section id="detail"[^>]*>[\s\S]*?<\/section>\s*<section id="technical-panel"[^>]*><\/section>\s*<div class="controls">/);
assert.ok(source.indexOf('const technicalMarkup') > source.indexOf('id="report-status"'));
console.log('Information navigation, selected-folder demonstration and detail-region checks passed');

// Render two repositories through the actual detail controller and preserve each
// disclosure independently, including a late toggle from a removed DOM node.
const detailNodes = new Map();
const activeDocument = {activeElement: null, getElementById: id => detailNodes.get(id)};
function region(id) {
  let markup = '';
  const node = {contains: child => child?.region === id};
  Object.defineProperty(node, 'innerHTML', {
    get: () => markup,
    set(value) {
      for (const [key, child] of detailNodes) {
        if (child.region === id) { child.isConnected = false; detailNodes.delete(key); }
      }
      markup = value;
      for (const match of value.matchAll(/<[^>]*?\sid="([^"]+)"[^>]*>/g)) {
        detailNodes.set(match[1], {region: id, isConnected: true,
          open: /\bopen\b/.test(match[0]), focus() { activeDocument.activeElement = this; }});
      }
    },
  });
  detailNodes.set(id, node);
  return node;
}
const detailRegion = region('detail');
const technicalRegion = region('technical-panel');
const repo = {id: 'a', name: 'First repo', health: {fresh: true}, needs_backup: false,
  last_backup: {archive: '/current', sha256: 'abc'},
  verification: {state: 'matched', archive: '/current'}, cloud: {state: 'uploaded', archive: '/current'}};
const renderContext = vm.createContext({
  $: selector => detailNodes.get(selector.slice(1)), document: activeDocument,
  menuState: {repos: [repo, {...repo, id: 'b', name: 'Second repo'}]},
  selectedId: 'a', technicalOpen: new Set(), retryingRepo: null,
  clientFreshness: 'current', RepoStatus: require('../web/repo-status.js'),
  view: row => require('../web/repo-status.js').present(row),
  escape: value => String(value ?? ''), when: value => value || 'Not yet', bytes: () => '1 MB',
  openSettings() {}, window: {},
});
vm.runInContext(source.slice(source.indexOf('function renderDetail()'),
  source.indexOf('function selectRepo(')), renderContext);
vm.runInContext('renderDetail()', renderContext);
assert.match(detailRegion.innerHTML, /id="report-status"/);
assert.doesNotMatch(detailRegion.innerHTML, /id="technical-details"/);
assert.match(technicalRegion.innerHTML, /Technical details/);
const oldDisclosure = detailNodes.get('technical-details');
oldDisclosure.open = true;
oldDisclosure.ontoggle();
vm.runInContext("selectedId = 'b'; renderDetail()", renderContext);
assert.equal(detailNodes.get('technical-details').open, false);
oldDisclosure.open = false;
oldDisclosure.ontoggle(); // Must not erase repo A's remembered open state.
vm.runInContext("selectedId = 'a'; renderDetail()", renderContext);
assert.equal(detailNodes.get('technical-details').open, true);
const toggle = detailNodes.get('technical-toggle');
activeDocument.activeElement = toggle;
vm.runInContext("menuState.repos[0].name = 'Updated repo'; renderDetail()", renderContext);
assert.equal(activeDocument.activeElement, toggle); // Unchanged technical DOM keeps focus.
vm.runInContext("selectedId = 'missing'; renderDetail()", renderContext);
assert.equal(technicalRegion.innerHTML, '');
console.log('Technical disclosure stays repo-scoped across selection, refresh and empty state');
