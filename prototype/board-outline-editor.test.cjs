'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');

const html = fs.readFileSync(path.join(__dirname, 'board-outline-editor.html'), 'utf8');
const match = html.match(/<script>([\s\S]*?)<\/script>/i);
assert.ok(match, 'editor script must exist');
const source = match[1];

function createHarness(tolerance = '1.0') {
  const elements = new Map();
  function element(id) {
    if (!elements.has(id)) elements.set(id, {
      value: id === 'length' ? '1600' : id === 'width' ? '520' : id === 'tolerance' ? tolerance : '',
      disabled: false, onclick: null, onchange: null, textContent: '', addEventListener() {}
    });
    return elements.get(id);
  }
  const svg = {
    innerHTML: '', attributes: {},
    setAttribute(name, value) { this.attributes[name] = value; },
    addEventListener() {},
    createSVGPoint() { return { x: 0, y: 0, matrixTransform() { return { x: this.x, y: this.y }; } }; },
    getScreenCTM() { return { inverse() { return {}; } }; },
    setPointerCapture() {}
  };
  const document = { getElementById(id) { return id === 'svg' ? svg : element(id); } };
  const context = vm.createContext({ document, confirm: () => true });
  new vm.Script(source, { filename: 'board-outline-editor.js' }).runInContext(context);
  return { context, svg, element, model: () => vm.runInContext('model', context), selected: () => vm.runInContext('selected', context) };
}

function cubic(p0, p1, p2, p3, t) {
  const u = 1 - t;
  return {
    x: u*u*u*p0.x + 3*u*u*t*p1.x + 3*u*t*t*p2.x + t*t*t*p3.x,
    y: u*u*u*p0.y + 3*u*u*t*p1.y + 3*u*t*t*p2.y + t*t*t*p3.y
  };
}

test('editor script parses and renders the closed outline using cubic segments', () => {
  assert.doesNotThrow(() => new vm.Script(source));
  const app = createHarness();
  assert.equal(app.model().anchors.length, 6);
  const fill = app.svg.innerHTML.match(/<path class="board-fill" d="([^"]+)"/);
  assert.ok(fill);
  assert.equal((fill[1].match(/ C /g) || []).length, 6);
  assert.ok(fill[1].endsWith(' Z'));
});

test('De Casteljau insertion preserves the selected cubic segment', () => {
  const app = createHarness();
  const original = JSON.parse(JSON.stringify(app.model().anchors));
  app.element('add').onclick();
  const anchors = app.model().anchors;
  const insertedIndex = app.selected();
  const segmentIndex = insertedIndex - 1;
  const oldA = original[segmentIndex];
  const oldB = original[(segmentIndex + 1) % original.length];
  const a = anchors[segmentIndex];
  const mid = anchors[insertedIndex];
  const b = anchors[(insertedIndex + 1) % anchors.length];
  let maxError = 0;
  for (let k = 0; k <= 500; k++) {
    const t = k / 500;
    const expected = cubic(
      {x: oldA.x, y: oldA.y}, {x: oldA.ox, y: oldA.oy},
      {x: oldB.ix, y: oldB.iy}, {x: oldB.x, y: oldB.y}, t
    );
    const actual = t <= 0.5
      ? cubic({x:a.x,y:a.y}, {x:a.ox,y:a.oy}, {x:mid.ix,y:mid.iy}, {x:mid.x,y:mid.y}, t*2)
      : cubic({x:mid.x,y:mid.y}, {x:mid.ox,y:mid.oy}, {x:b.ix,y:b.iy}, {x:b.x,y:b.y}, (t-0.5)*2);
    maxError = Math.max(maxError, Math.hypot(expected.x-actual.x, expected.y-actual.y));
  }
  assert.ok(maxError < 1e-8, 'split should be exact within floating-point precision');
});

test('deleting the inserted point respects strict tolerance and undo/redo', () => {
  const app = createHarness('0.1');
  app.element('add').onclick();
  assert.equal(app.model().anchors.length, 7);
  app.element('del').onclick();
  assert.equal(app.model().anchors.length, 6);
  const message = app.element('feedback').textContent;
  const bound = Number(message.match(/Abweichungsobergrenze: ([0-9.]+) mm/)[1]);
  assert.ok(bound <= 0.1, message);
  app.element('undo').onclick();
  assert.equal(app.model().anchors.length, 7);
  app.element('redo').onclick();
  assert.equal(app.model().anchors.length, 6);
});

test('deletion is refused if its conservative deviation bound exceeds tolerance', () => {
  const app = createHarness('0.1');
  app.element('del').onclick();
  assert.equal(app.model().anchors.length, 6);
  assert.match(app.element('feedback').textContent, /Nicht gelöscht/);
});

test('length and width edits scale the geometry in millimetres', () => {
  const app = createHarness();
  const before = {...app.model().anchors[1]};
  app.element('length').value = '1800';
  app.element('width').value = '600';
  app.element('length').onchange();
  assert.equal(app.model().length_mm, 1800);
  assert.equal(app.model().width_mm, 600);
  assert.ok(Math.abs(app.model().anchors[1].x - before.x * (600/520)) < 1e-9);
  assert.ok(Math.abs(app.model().anchors[1].y - before.y * (1800/1600)) < 1e-9);
});

test('continuity mode cycles Corner, Smooth and Symmetric', () => {
  const app = createHarness();
  app.element('mode').onclick();
  assert.equal(app.model().anchors[0].mode, 'smooth');
  app.element('mode').onclick();
  const a = app.model().anchors[0];
  assert.equal(a.mode, 'symmetric');
  const incoming = Math.hypot(a.ix-a.x, a.iy-a.y);
  const outgoing = Math.hypot(a.ox-a.x, a.oy-a.y);
  assert.ok(Math.abs(incoming-outgoing) < 1e-8);
  app.element('mode').onclick();
  assert.equal(app.model().anchors[0].mode, 'corner');
});
