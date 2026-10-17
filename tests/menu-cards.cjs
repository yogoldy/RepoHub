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
const animations = [];
let reducedMotion = false;
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
    this.scrollLeft = 0;
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
  get clientWidth() { return 530; }
  get scrollWidth() { return Math.max(530, this.children.length * 180 - 10); }
  getBoundingClientRect() {
    if (this.id === 'cards') return {left: 0, right: 530};
    const slot = this.parentElement;
    const rail = slot.parentElement;
    const left = 1 + rail.children.indexOf(slot) * 180 - rail.scrollLeft;
    return {left, right: left + 170};
  }
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
  scrollBy(options) {
    this.scrollLeft = Math.max(0, Math.min(this.scrollWidth - this.clientWidth,
      this.scrollLeft + options.left));
    this.events.scroll?.();
  }
  animate(keyframes, options) {
    const animation = {keyframes, options, cancelled: false, cancel() { this.cancelled = true; }};
    animations.push(animation);
    return animation;
  }
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
const state = {repos: Array.from({length: 13}, (_, index) => ({...structuredClone(repo), id: 'id-' + index})), backup: {}};
const unchanged = JSON.stringify(state);
const frames = [];
const proofs = [];
function captureProof(label, failedSurface = null, changedRow = null) {
  const rows = structuredClone(frames.at(-1)[1]);
  if (changedRow) Object.assign(rows.find(row => row.repo_id === changedRow.repo_id), changedRow);
  proofs.push({label, failedSurface, status: structuredClone(state), rows,
    selected: frames.at(-1)[3]});
}
let timingCalls = 0;
const context = vm.createContext({document, $: selector => document.querySelector(selector),
  menuState: state, observedMenuState: state, selectedId: null, retryingRepo: null, detailsAnimation: null,
  technicalOpen: new Set(), clientFreshness: 'current',
  RepoStatus: {...policy, timing(...args) { timingCalls++; return policy.timing(...args); }},
  RepoDiagnostics: diagnostics, diagnosticView: {observe(...args) { frames.push(args); }},
  view: row => policy.present(row, state.backup), percentLabel: value => value + '%',
  escape: encode, when: value => value || 'Not yet', bytes: () => '1 MB',
  window: {matchMedia: () => ({matches: reducedMotion})}, openSettings() {},
});
const source = fs.readFileSync('web/menu.js', 'utf8');
vm.runInContext(source.slice(source.indexOf('function percentLabel('), source.indexOf('function unreachable(')), context);
const render = () => vm.runInContext('render()', context);
const cards = () => get('cards').querySelectorAll('.repo-card');
const last = () => frames.at(-1);
render();
assert.equal(timingCalls, 13, 'One timing projection per repo per render');
assert.equal(cards().length, 13);
assert.equal(get('repo-expansion').hidden, true);
assert.equal(last()[3], null);
assert.ok(last()[1].every(row => row.card_timing.text_matches && !row.detail_timing));
assert.equal(get('position').textContent, '1–3 of 13 repos');
assert.equal(get('previous').disabled, true);
captureProof('collapsed');
// A post-sleep stale frame stays non-green on both actual render surfaces.
state.repos[0].health = {fresh: false, reasons: ['Repo checks stopped updating']};
vm.runInContext("selectedId = 'id-0'", context);
render();
assert.equal(cards()[0].querySelector('.card-status').textContent, 'Waiting for fresh checks');
assert.equal(cards()[0].classList.contains('ready'), false);
assert.equal(get('detail').querySelector('.status-headline').textContent, 'Waiting for fresh backup status.');
assert.match(get('summary').textContent, /1 awaiting fresh checks/);
captureProof('stale-card-and-detail');
state.repos.forEach(row => { row.health = {fresh: false}; });
render();
assert.equal(get('summary').textContent, 'Waiting for fresh status · 13 repos');
state.repos.forEach(row => { row.health = {fresh: true}; });
vm.runInContext('selectedId = null', context);
render();
assert.equal(cards()[0].querySelector('.card-status').textContent, 'Backed up');
get('next').click();
assert.equal(get('position').textContent, '4–6 of 13 repos');
assert.equal(get('previous').disabled, false);
get('previous').click();
assert.equal(get('position').textContent, '1–3 of 13 repos');
const beforeExpansion = timingCalls;
cards()[0].click();
assert.equal(timingCalls - beforeExpansion, state.repos.length, 'Expanding reuses the frame projection');
assert.ok(!get('cards').contains(get('repo-expansion')));
assert.equal(cards()[0].getAttribute('aria-expanded'), 'true');
assert.equal(last()[1].length, 13, 'The horizontal row remains available while details are open');
assert.equal(last()[1][0].detail_timing.text_matches, true);
assert.equal(last()[1][0].timing, last()[1][0].detail_timing.receipt);
assert.equal(animations.length, 1);
assert.equal(animations[0].options.duration, 160);
assert.equal(animations[0].keyframes[0].transform, 'translateY(-6px)');
captureProof('expanded');
render();
assert.equal(animations.length, 1, 'Polling cannot replay the selection cue');
cards()[4].click();
assert.equal(last()[3], 'id-4');
assert.equal(get('technical-details').dataset.repoId, 'id-4');
assert.equal(root.querySelectorAll('#technical-details').length, 1);
assert.equal(cards()[0].getAttribute('aria-expanded'), 'false');
assert.equal(animations.length, 2);
assert.equal(animations[0].cancelled, true, 'Switching cancels the old cue');
cards()[4].click();
render();
assert.equal(last()[3], null, 'Polling must preserve collapsed selection');
assert.equal(get('repo-expansion').hidden, true);
assert.equal(animations[1].cancelled, true);
assert.equal(JSON.stringify(state), unchanged, 'Rendering cannot mutate backup/scheduler input');
reducedMotion = true;
cards()[3].click();
assert.equal(get('repo-expansion').hidden, false);
assert.equal(animations.length, 2, 'Reduced motion skips the animation');
get('all-repos').click();
assert.equal(get('repo-expansion').hidden, true);
reducedMotion = false;
const originalAnimate = get('repo-expansion').animate;
get('repo-expansion').animate = undefined;
cards()[3].click();
assert.equal(get('repo-expansion').hidden, false, 'Animation support cannot block details');
get('all-repos').click();
get('repo-expansion').animate = originalAnimate;
state.repos[0].needs_backup = true;
state.repos[0].verification = {state: 'different', archive: '/private/current', changes: {
  counts: {repo_files: 1, git_data: 0, finder_metadata: 0}}};
render();
assert.equal(cards()[0].querySelector('.card-status').textContent, 'Edits confirmed');
assert.match(cards()[0].querySelector('.card-next').textContent, /^Next backup /);
cards()[0].click();
assert.equal(last()[1][0].detail_timing.text_matches, true);
state.repos[0].schedule_evidence = {state: 'manual', reason: 'manual'};
render();
assert.equal(cards()[0].querySelector('.card-next').textContent, 'Manual only');
assert.equal(get('detail').querySelector('.next-backup').textContent, 'Next backup: manual only.');
// Mutate nodes made by the actual card renderer. Correct detail cannot mask them.
const card = cards()[1];
const compact = policy.compactTiming(policy.timing(state.repos[1], state.backup));
card.querySelector('.card-next').textContent = 'Next check wrong time';
assert.equal(diagnostics.readCardTiming(card, compact).text_matches, false);
captureProof('wrong-card-text', 'card', {repo_id: 'id-1',
  card_timing: diagnostics.readCardTiming(card, compact)});
render();
card.querySelector('.card-next').querySelector('time').remove();
assert.equal(diagnostics.readCardTiming(card, compact).due_at, null);
captureProof('missing-card-time', 'card', {repo_id: 'id-1',
  card_timing: diagnostics.readCardTiming(card, compact)});
render();
card.querySelector('.card-next').hidden = true;
assert.equal(diagnostics.readCardTiming(card, compact).text_matches, false);
captureProof('hidden-card-line', 'card', {repo_id: 'id-1',
  card_timing: diagnostics.readCardTiming(card, compact)});
render();
card.querySelector('.card-next').remove();
assert.equal(diagnostics.readCardTiming(card, compact).text_matches, false);
captureProof('missing-card-line', 'card', {repo_id: 'id-1',
  card_timing: diagnostics.readCardTiming(card, compact)});
render();
get('detail').querySelector('.next-backup').remove();
const currentTiming = policy.timing(state.repos[0], state.backup);
assert.equal(diagnostics.readDetailTiming(get('detail'), currentTiming).text_matches, false);
captureProof('missing-expanded-line', 'detail', {repo_id: 'id-0',
  detail_timing: diagnostics.readDetailTiming(get('detail'), currentTiming)});
render();
const keyboard = get('cards').events.keydown;
keyboard({key: 'Escape', target: cards()[0], preventDefault() {}});
assert.equal(get('repo-expansion').hidden, true);
keyboard({key: 'ArrowRight', target: cards()[0], preventDefault() {}});
assert.equal(activeElement, cards()[1]);
assert.equal(last()[3], null, 'Arrow navigation moves focus without opening a panel');
keyboard({key: 'End', target: cards()[1], preventDefault() {}});
assert.equal(activeElement, cards().at(-1));
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
console.log('Actual horizontal controller: shared projections, collapsed defaults, paging, animation/reduced-motion, refresh and DOM timing faults passed');
if (process.argv.includes('--proofs')) console.log(JSON.stringify(proofs));
