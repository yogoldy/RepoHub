// Exercise the actual render/controller with an isolated DOM double. Real layout
// and WebKit pixels remain browser/native acceptance checks.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const policy = require('../web/repo-status.js');
const diagnostics = require('../web/diagnostics-client.js');
const decode = value => value.replace(/&(amp|lt|gt|quot|#39);/g,
  (_, key) => ({amp: '&', lt: '<', gt: '>', quot: '"', '#39': "'"}[key]));
const encode = value => String(value).replace(/[&<>"']/g,
  key => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[key]));
let root;
let activeElement = null;
class Text {
  constructor(text) { this.textContent = decode(text); }
  get outerHTML() { return encode(this.textContent); }
}
class Element {
  constructor(tag = 'div') {
    this.tag = tag;
    this.attributes = {};
    this.childNodes = [];
    this.events = {};
    this.style = {values: {}, setProperty(key, value) { this.values[key] = value; }};
    this.dataset = new Proxy({}, {
      get: (_, key) => this.attributes['data-' + key.replace(/[A-Z]/g, c => '-' + c.toLowerCase())],
      set: (_, key, value) => { this.setAttribute('data-' + key.replace(/[A-Z]/g,
        c => '-' + c.toLowerCase()), value); return true; },
    });
  }
  get children() { return this.childNodes.filter(child => child instanceof Element); }
  get lastElementChild() { return this.children.at(-1); }
  get className() { return this.attributes.class || ''; }
  set className(value) { this.attributes.class = value; }
  get classList() { return {contains: value => this.className.split(' ').includes(value)}; }
  get id() { return this.attributes.id; }
  get hidden() { return Object.hasOwn(this.attributes, 'hidden'); }
  set hidden(value) { if (value) this.attributes.hidden = ''; else delete this.attributes.hidden; }
  get open() { return Object.hasOwn(this.attributes, 'open'); }
  set open(value) { if (value) this.attributes.open = ''; else delete this.attributes.open; }
  setAttribute(key, value) { this.attributes[key] = String(value); }
  getAttribute(key) { return this.attributes[key] ?? null; }
  removeAttribute(key) { delete this.attributes[key]; }
  append(...children) { children.forEach(child => this.insertBefore(child, null)); }
  insertBefore(child, before) {
    child.remove?.();
    const index = before ? this.childNodes.indexOf(before) : this.childNodes.length;
    this.childNodes.splice(index, 0, child);
    child.parentElement = this;
  }
  remove() {
    if (this.parentElement) {
      const parent = this.parentElement;
      parent.childNodes.splice(parent.childNodes.indexOf(this), 1);
      this.parentElement = null;
    }
  }
  get isConnected() { return this === root || !!this.parentElement?.isConnected; }
  getClientRects() { return !this.isConnected || this.closestHidden() ? [] : [1]; }
  closestHidden() { return this.hidden || this.parentElement?.closestHidden(); }
  matches(selector) {
    return selector[0] === '.' ? this.classList.contains(selector.slice(1))
      : selector[0] === '#' ? this.id === selector.slice(1) : this.tag === selector;
  }
  closest(selector) { return this.matches(selector) ? this : this.parentElement?.closest(selector); }
  querySelectorAll(selector) {
    return this.children.flatMap(child => [
      ...(child.matches(selector) ? [child] : []), ...child.querySelectorAll(selector),
    ]);
  }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  contains(child) { return child === this || this.children.some(node => node.contains(child)); }
  addEventListener(event, callback) { this.events[event] = callback; }
  click() { (this.onclick || this.events.click)?.({target: this}); }
  focus() { activeElement = this; }
  scrollIntoView() { this.scrolled = true; }
  get textContent() { return this.childNodes.map(child => child.textContent).join(''); }
  set textContent(value) { this.childNodes = [new Text(encode(value))]; }
  get innerHTML() { return this.childNodes.map(child => child.outerHTML).join(''); }
  get outerHTML() {
    const attrs = Object.entries(this.attributes).map(([key, value]) => ` ${key}="${encode(value)}"`).join('');
    return `<${this.tag}${attrs}>${this.innerHTML}</${this.tag}>`;
  }
  set innerHTML(markup) {
    this.children.forEach(child => { child.parentElement = null; });
    this.childNodes = [];
    const stack = [this];
    for (const token of markup.match(/<!--[\s\S]*?-->|<[^>]+>|[^<]+/g) || []) {
      if (/^<(!|\?)/.test(token)) continue;
      if (token.startsWith('</')) { stack.pop(); continue; }
      if (!token.startsWith('<')) { stack.at(-1).append(new Text(token)); continue; }
      const tag = token.match(/^<([\w-]+)/)[1];
      const node = new Element(tag);
      for (const match of token.slice(tag.length + 1, -1).matchAll(/([\w:-]+)(?:="([^"]*)")?/g)) {
        node.setAttribute(match[1], decode(match[2] || ''));
      }
      stack.at(-1).append(node);
      if (!['meta', 'link', 'input', 'br', 'hr'].includes(tag) && !token.endsWith('/>')) stack.push(node);
    }
  }
}
root = new Element('document');
root.innerHTML = fs.readFileSync('web/menu.html', 'utf8');
const document = {querySelector: selector => root.querySelector(selector),
  querySelectorAll: selector => root.querySelectorAll(selector),
  getElementById: id => root.querySelector('#' + id), createElement: tag => new Element(tag),
  get activeElement() { return activeElement; }};
const get = id => document.getElementById(id);
const repo = {id: 'id-0', name: 'Same repo name', health: {fresh: true}, needs_backup: false,
  last_backup: {archive: '/private/current', sha256: 'sha'},
  verification: {state: 'matched', archive: '/private/current'},
  cloud: {state: 'uploaded', archive: '/private/current'},
  schedule_evidence: {state: 'scheduled', reason: 'periodic', due_at: '2026-10-18T01:00:00+00:00', due_in_seconds: 100},
  backup_location: {state: 'cloud_confirmed', created_at: '2026-10-17T20:00:00+00:00'}};
const state = {repos: Array.from({length: 7}, (_, index) => ({...structuredClone(repo), id: 'id-' + index})), backup: {}};
const unchanged = JSON.stringify(state);
const frames = [];
const proofs = [];
function captureProof(label, failedSurface = null, changedRow = null) {
  const rows = structuredClone(frames.at(-1)[1]);
  if (changedRow) Object.assign(rows.find(row => row.repo_id === changedRow.repo_id), changedRow);
  proofs.push({label, failedSurface, status: structuredClone(state), rows,
    selected: frames.at(-1)[3]});
}
let columns = 3;
let scrollY = 200;
let timingCalls = 0;
const context = vm.createContext({document, $: selector => document.querySelector(selector),
  menuState: state, observedMenuState: state, selectedId: null, retryingRepo: null, gridScrollTop: 0,
  technicalOpen: new Set(), clientFreshness: 'current',
  RepoStatus: {...policy, timing(...args) { timingCalls++; return policy.timing(...args); }},
  RepoDiagnostics: diagnostics, diagnosticView: {observe(...args) { frames.push(args); }},
  view: row => policy.present(row, state.backup), percentLabel: value => value + '%',
  escape: encode, when: value => value || 'Not yet', bytes: () => '1 MB',
  getComputedStyle: () => ({getPropertyValue: () => String(columns)}),
  window: {matchMedia: () => ({matches: true}), get scrollY() { return scrollY; },
    scrollTo(options) { scrollY = options.top; }}, openSettings() {},
});
const source = fs.readFileSync('web/menu.js', 'utf8');
vm.runInContext(source.slice(source.indexOf('function percentLabel('), source.indexOf('function unreachable(')), context);
const render = () => vm.runInContext('render()', context);
const cards = () => get('cards').querySelectorAll('.repo-card');
const last = () => frames.at(-1);
const visibleCards = () => cards().filter(card => !card.parentElement.hidden);
render();
assert.equal(timingCalls, 7, 'One timing projection per repo per render');
assert.equal(cards().length, 7);
assert.equal(get('repo-expansion').hidden, true);
assert.equal(last()[3], null);
assert.ok(last()[1].every(row => row.card_timing.text_matches && !row.detail_timing));
captureProof('collapsed');
cards()[0].click();
assert.equal(timingCalls, 14, 'Expanding must reuse this frame projection');
assert.equal(get('cards').children.length, 7);
assert.ok(!get('cards').contains(get('repo-expansion')), 'All rows stay above the detail panel');
const main = get('repo-expansion').parentElement;
assert.ok(main.children.indexOf(get('cards').parentElement) < main.children.indexOf(get('repo-expansion')));
assert.equal(root.querySelectorAll('#technical-details').length, 1);
assert.equal(get('technical-details').dataset.repoId, 'id-0');
assert.equal(cards()[0].getAttribute('aria-expanded'), 'true');
assert.equal(last()[1][0].detail_timing.text_matches, true);
assert.equal(visibleCards().length, 1);
assert.equal(last()[1].length, 1);
assert.equal(last()[1][0].timing, last()[1][0].detail_timing.receipt);
captureProof('expanded');
cards()[4].click();
assert.equal(last()[3], 'id-4');
assert.equal(get('cards').children.length, 7);
assert.equal(get('technical-details').dataset.repoId, 'id-4');
assert.equal(get('cards').style.values['--selected-column'], String(4 % columns + 1));
assert.equal(cards()[0].getAttribute('aria-expanded'), 'false');
columns = 2;
vm.runInContext('updatePosition()', context);
assert.equal(get('cards').children.length, 7);
assert.equal(get('technical-details').dataset.repoId, 'id-4');
assert.equal(get('cards').style.values['--selected-column'], String(4 % columns + 1));
cards()[2].click();
assert.equal(get('cards').children.length, 7);
assert.equal(get('technical-details').dataset.repoId, 'id-2');
assert.equal(get('cards').style.values['--selected-column'], String(2 % columns + 1));
assert.equal(root.querySelectorAll('#technical-details').length, 1);
cards()[2].click();
render();
assert.equal(last()[3], null, 'Polling must preserve collapsed selection');
assert.equal(get('repo-expansion').hidden, true);
assert.equal(visibleCards().length, 7);
assert.equal(scrollY, 200, 'Returning restores overview scroll position');
assert.equal(JSON.stringify(state), unchanged, 'Rendering must not mutate backup/scheduler input');
state.repos[0].needs_backup = true;
state.repos[0].verification = {state: 'different', archive: '/private/current', changes: {
  counts: {repo_files: 1, git_data: 0, finder_metadata: 0}}};
render();
assert.equal(cards()[0].querySelector('.card-status').textContent, 'Edits confirmed');
assert.match(cards()[0].querySelector('.card-next').textContent, /^Next backup /);
cards()[0].click();
assert.equal(last()[1][0].detail_timing.text_matches, true);
assert.equal(visibleCards().length, 1);
assert.equal(last()[1].length, 1);
state.repos[0].schedule_evidence = {state: 'manual', reason: 'manual'};
render();
assert.equal(cards()[0].querySelector('.card-next').textContent, 'Manual only');
assert.equal(get('detail').querySelector('.next-backup').textContent, 'Next backup: manual only.');
// Mutate nodes made by the real card renderer. Correct detail cannot mask them.
cards()[1].click();
const card = cards()[1];
const compact = policy.compactTiming(policy.timing(state.repos[1], state.backup));
card.querySelector('.card-next').textContent = 'Next check wrong time';
assert.equal(diagnostics.readCardTiming(card, compact).text_matches, false);
captureProof('bad-card-text-or-hidden-line', 'card', {repo_id: 'id-1',
  card_timing: diagnostics.readCardTiming(card, compact)});
render();
card.querySelector('.card-next').querySelector('time').remove();
assert.equal(diagnostics.readCardTiming(card, compact).due_at, null);
captureProof('missing-card-time', 'card', {repo_id: 'id-1',
  card_timing: diagnostics.readCardTiming(card, compact)});
render();
card.querySelector('.card-next').hidden = true;
assert.equal(diagnostics.readCardTiming(card, compact).text_matches, false);
captureProof('bad-card-text-or-hidden-line', 'card', {repo_id: 'id-1',
  card_timing: diagnostics.readCardTiming(card, compact)});
render();
card.querySelector('.card-next').remove();
assert.equal(diagnostics.readCardTiming(card, compact).text_matches, false);
captureProof('bad-card-text-or-hidden-line', 'card', {repo_id: 'id-1',
  card_timing: diagnostics.readCardTiming(card, compact)});
render();
get('detail').querySelector('.next-backup').remove();
assert.equal(diagnostics.readDetailTiming(get('detail'), policy.timing(state.repos[1], state.backup)).text_matches, false);
captureProof('missing-expanded-line', 'detail', {repo_id: 'id-1',
  detail_timing: diagnostics.readDetailTiming(get('detail'), policy.timing(state.repos[1], state.backup))});
render();
const keyboard = get('cards').events.keydown;
get('all-repos').click();
assert.equal(visibleCards().length, 7);
assert.equal(get('repo-expansion').hidden, true);
cards()[1].click();
keyboard({key: 'Escape', target: cards()[1], preventDefault() {}});
assert.equal(get('repo-expansion').hidden, true);
keyboard({key: 'ArrowDown', target: cards()[0], preventDefault() {}});
assert.equal(activeElement, cards()[2]);
assert.equal(last()[3], null, 'Arrow navigation moves focus without opening a panel');
cards()[4].click();
state.repos.reverse();
render();
assert.equal(last()[3], 'id-4', 'Reordering follows identity, not the old slot');
state.repos = state.repos.filter(row => row.id !== 'id-4');
render();
assert.equal(get('repo-expansion').hidden, true, 'Removed repo closes without selecting another');
state.repos = [];
render();
assert.equal(cards().length, 0);
assert.equal(get('repo-expansion').hidden, true);
assert.equal(get('position').textContent, '0 repos');
console.log('Actual grid controller: shared projections, collapsed defaults, grid/focused layout, keyboard, refresh and DOM timing faults passed');

if (process.argv.includes('--proofs')) console.log(JSON.stringify(proofs));
