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
const SCREEN_WIDTH = 900;
const SCREEN_HEIGHT = 450;

function createHarness(tolerance = '1.0') {
  const elements = new Map();
  const listeners = {};
  function element(id) {
    if (!elements.has(id)) elements.set(id, {
      value: id === 'length' ? '1600' : id === 'width' ? '520' : id === 'tolerance' ? tolerance : '',
      disabled: false, onclick: null, onchange: null, textContent: '', className: '', addEventListener() {}
    });
    return elements.get(id);
  }
  const svg = {
    innerHTML: '', attributes: {},
    setAttribute(name, value) { this.attributes[name] = value; },
    addEventListener(name, callback) { listeners[name] = callback; },
    screenTransform() {
      const [vx, vy, vw, vh] = this.attributes.viewBox.split(' ').map(Number);
      const scale = Math.min(SCREEN_WIDTH / vw, SCREEN_HEIGHT / vh);
      return { vx, vy, vw, vh, scale, left:(SCREEN_WIDTH-vw*scale)/2, top:(SCREEN_HEIGHT-vh*scale)/2 };
    },
    createSVGPoint() {
      const owner = this;
      return { x: 0, y: 0, matrixTransform() {
        const t = owner.screenTransform();
        return { x:t.vx+(this.x-t.left)/t.scale, y:t.vy+(this.y-t.top)/t.scale };
      } };
    },
    getScreenCTM() { return { inverse() { return {}; } }; },
    setPointerCapture() {}
  };
  const document = { getElementById(id) { return id === 'svg' ? svg : element(id); } };
  const context = vm.createContext({ document, confirm: () => true });
  new vm.Script(source, { filename: 'board-outline-editor.js' }).runInContext(context);
  const clientPoint = world => { const t=svg.screenTransform(); return {x:t.left+(world.x-t.vx)*t.scale,y:t.top+(world.y-t.vy)*t.scale}; };
  return { context, svg, listeners, element, clientPoint, model: () => vm.runInContext('model', context), selected: () => vm.runInContext('selected', context), validate: () => vm.runInContext('validateOutline()', context), redraw: () => vm.runInContext('draw()', context) };
}

function assertSymmetric(anchors) {
  assert.equal(anchors.length % 2, 0, 'symmetric outlines have an even number of anchors');
  const mid = anchors.length / 2;
  const close = (a, b) => Math.abs(a - b) < 1e-7;
  for (let i = 1; i < mid; i++) {
    const a = anchors[i], b = anchors[anchors.length - i];
    assert.ok(close(b.x, -a.x) && close(b.y, a.y));
    assert.ok(close(b.ix, -a.ox) && close(b.iy, a.oy));
    assert.ok(close(b.ox, -a.ix) && close(b.oy, a.iy));
    assert.equal(b.mode, a.mode);
  }
  for (const i of [0, mid]) {
    const a = anchors[i];
    assert.ok(close(a.x, 0));
    assert.ok(close(a.ix, -a.ox) && close(a.iy, a.oy));
  }
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
  assertSymmetric(app.model().anchors);
  assert.equal(app.validate().valid, true, app.validate().reason);
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
  assert.equal(anchors.length, 8);
  assertSymmetric(anchors);
  const insertedIndex = app.selected();
  const mid = anchors[insertedIndex];
  const a = anchors[(insertedIndex - 1 + anchors.length) % anchors.length];
  const b = anchors[(insertedIndex + 1) % anchors.length];
  const oldA = original.find(point => point.id === a.id);
  const oldB = original.find(point => point.id === b.id);
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
  assert.equal(app.model().anchors.length, 8);
  assertSymmetric(app.model().anchors);
  app.element('del').onclick();
  assert.equal(app.model().anchors.length, 6);
  assertSymmetric(app.model().anchors);
  const message = app.element('feedback').textContent;
  const bound = Number(message.match(/Abweichungsobergrenze: ([0-9.]+) mm/)[1]);
  assert.ok(bound <= 0.1, message);
  app.element('undo').onclick();
  assert.equal(app.model().anchors.length, 8);
  assertSymmetric(app.model().anchors);
  app.element('redo').onclick();
  assert.equal(app.model().anchors.length, 6);
  assertSymmetric(app.model().anchors);
});

test('deletion is refused if its conservative deviation bound exceeds tolerance', () => {
  const app = createHarness('0.1');
  app.element('del').onclick();
  assert.equal(app.model().anchors.length, 6);
  assert.match(app.element('feedback').textContent, /Mittellinie/);
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


test('numeric coordinate entry moves the anchor and both handles in millimetres', () => {
  const app = createHarness();
  vm.runInContext('selected=1;draw()', app.context);
  app.element('anchorX').value = '12.5';
  app.element('anchorY').value = '-720.25';
  app.element('inX').value = '-34';
  app.element('inY').value = '-680';
  app.element('outX').value = '38';
  app.element('outY').value = '-755';
  app.element('applyCoords').onclick();
  const a = app.model().anchors[1], mirror = app.model().anchors[5];
  assert.equal(a.x, 12.5);
  assert.equal(a.y, -720.25);
  assert.equal(a.ix, -34);
  assert.equal(a.iy, -680);
  assert.equal(a.ox, 38);
  assert.equal(a.oy, -755);
  assert.equal(mirror.x, -12.5);
  assert.equal(mirror.y, -720.25);
  assert.equal(mirror.ix, -38);
  assert.equal(mirror.iy, -755);
  assert.equal(mirror.ox, 34);
  assert.equal(mirror.oy, -680);
  assertSymmetric(app.model().anchors);
});

test('dragging an anchor or handle on either side mirrors the other side', () => {
  const app = createHarness();
  const anchors = app.model().anchors;
  const before = JSON.parse(JSON.stringify(anchors));
  const firstViewBox=app.svg.attributes.viewBox, start=app.clientPoint(before[1]), scale=app.svg.screenTransform().scale;
  app.listeners.pointerdown({
    target:{closest:()=>({dataset:{type:'anchor',i:'1'}})},
    clientX:start.x, clientY:start.y, pointerId:1
  });
  app.listeners.pointermove({clientX:start.x+24,clientY:start.y+18});
  app.listeners.pointermove({clientX:start.x+48,clientY:start.y+36});
  assert.equal(app.svg.attributes.viewBox,firstViewBox,'camera must remain fixed during anchor drag');
  app.listeners.pointerup();
  assert.ok(Math.abs(anchors[1].x-(before[1].x+48/scale))<1e-8);
  assert.ok(Math.abs(anchors[1].y-(before[1].y+36/scale))<1e-8);
  assertSymmetric(anchors);

  const oldPortOut={x:anchors[5].ox,y:anchors[5].oy},portScreen=app.clientPoint(oldPortOut),portViewBox=app.svg.attributes.viewBox;
  app.listeners.pointerdown({
    target:{closest:()=>({dataset:{type:'out',i:'5'}})},
    clientX:portScreen.x, clientY:portScreen.y, pointerId:2
  });
  app.listeners.pointermove({clientX:portScreen.x-13,clientY:portScreen.y+9});
  assert.equal(app.svg.attributes.viewBox,portViewBox,'camera must remain fixed during handle drag');
  app.listeners.pointerup();
  assertSymmetric(anchors);
  assert.equal(anchors[1].ix,-anchors[5].ox);
  assert.equal(anchors[1].iy,anchors[5].oy);
});

test('tail outgoing X handle is freely movable and its opposite handle stays mirrored', () => {
  const app = createHarness();
  const tail = app.model().anchors[3];
  const initialOutX = tail.ox,screen=app.clientPoint(tail),scale=app.svg.screenTransform().scale;
  const initialViewBox=app.svg.attributes.viewBox;
  app.listeners.pointerdown({
    target:{closest:()=>({dataset:{type:'out',i:'3'}})},
    clientX:screen.x, clientY:screen.y, pointerId:7
  });
  app.listeners.pointermove({clientX:screen.x+32,clientY:screen.y});
  assert.equal(app.svg.attributes.viewBox,initialViewBox,'camera must stay fixed during tail-handle drag');
  app.listeners.pointerup();
  assert.ok(Math.abs(tail.ox-(initialOutX+32/scale))<1e-8, 'tail outgoing handle X must follow the pointer');
  assert.ok(Math.abs(tail.ix+tail.ox)<1e-8, 'incoming handle must mirror outgoing X');
  assert.ok(Math.abs(tail.oy-tail.y)<1e-8 && Math.abs(tail.iy-tail.y)<1e-8);
  assertSymmetric(app.model().anchors);
  assert.equal(app.validate().valid,true,app.validate().reason);
});

test('control points and Bézier handle markers are small while drag hit areas stay large', () => {
  const app = createHarness();
  assert.match(app.svg.innerHTML, /class="anchor-hit"[^>]*r="25"/);
  assert.match(app.svg.innerHTML, /class="anchor(?: selected)?"[^>]*r="7"/);
  assert.match(app.svg.innerHTML, /class="handle-hit" data-type="out"[^>]*r="18"/);
  assert.match(app.svg.innerHTML, /class="handle"[^>]*r="5"/);
});

test('bottom-left orientation indicator shows positive X and Y axes', () => {
  const app = createHarness();
  assert.match(app.svg.innerHTML,/class="axis-indicator"/);
  assert.match(app.svg.innerHTML,/>\+X</);
  assert.match(app.svg.innerHTML,/>\+Y</);
});

test('numeric tail outgoing X coordinate remains editable', () => {
  const app = createHarness();
  vm.runInContext('selected=3;draw()', app.context);
  const tail=app.model().anchors[3],newOutX=tail.ox+45;
  app.element('outX').value=String(newOutX);
  app.element('applyCoords').onclick();
  assert.ok(Math.abs(tail.ox-newOutX)<1e-8);
  assert.ok(Math.abs(tail.ix+tail.ox)<1e-8);
  assert.equal(app.validate().valid,true,app.validate().reason);
});

test('zoom buttons, fit view and blank-canvas panning update the viewport', () => {
  const app = createHarness();
  const initial = app.svg.attributes.viewBox.split(' ').map(Number);
  app.element('zoomIn').onclick();
  const zoomed = app.svg.attributes.viewBox.split(' ').map(Number);
  assert.ok(zoomed[2] < initial[2]);
  app.element('fitView').onclick();
  const fitted = app.svg.attributes.viewBox.split(' ').map(Number);
  assert.ok(Math.abs(fitted[2] - initial[2]) < 1e-8);
  app.listeners.pointerdown({target:{closest:()=>null},clientX:0,clientY:0,pointerId:1});
  app.listeners.pointermove({clientX:15,clientY:25});
  app.listeners.pointerup();
  const panned = app.svg.attributes.viewBox.split(' ').map(Number);
  assert.notEqual(panned[0], fitted[0]);
  assert.notEqual(panned[1], fitted[1]);
  let prevented = false;
  app.listeners.wheel({clientX:0,clientY:0,deltaY:-100,preventDefault(){prevented=true}});
  const wheelZoom = app.svg.attributes.viewBox.split(' ').map(Number);
  assert.equal(prevented, true);
  assert.ok(wheelZoom[2] < panned[2]);
});


test('starter outline exterior dimensions match declared 1600 x 520 mm', () => {
  const app = createHarness();
  const result = app.validate();
  assert.equal(result.valid, true, result.reason);
  assert.ok(Math.abs(result.bounds.maxY - result.bounds.minY - 1600) < 1e-6);
  assert.ok(Math.abs(result.bounds.maxX - result.bounds.minX - 520) < 1e-6);
  assert.match(app.svg.innerHTML, /1600\.0 mm/);
  assert.match(app.svg.innerHTML, /520\.0 mm/);
});

test('self-intersecting symmetric outlines are marked invalid and block JSON export', () => {
  const app = createHarness();
  app.model().anchors = [
    {id:'nose',x:0,y:-100,ix:-300,iy:-300,ox:300,oy:-300,mode:'corner'},
    {id:'starboard',x:100,y:0,ix:-300,iy:300,ox:100,oy:100,mode:'corner'},
    {id:'tail',x:0,y:100,ix:-100,iy:100,ox:100,oy:100,mode:'corner'},
    {id:'port',x:-100,y:0,ix:-100,iy:100,ox:300,oy:300,mode:'corner'}
  ];
  app.redraw();
  const validation = app.validate();
  assert.equal(validation.valid, false);
  assert.match(validation.reason, /Selbstüberschneidung/);
  assert.match(app.element('integrity').textContent, /Kontur ungültig/);
  assert.equal(app.element('export').disabled, true);
});

test('adjacent duplicate anchors are rejected as degenerate geometry', () => {
  const app = createHarness();
  const anchors = app.model().anchors;
  Object.assign(anchors[2], {...anchors[1], id:anchors[2].id});
  vm.runInContext('syncMirrorData(model.anchors[2],model.anchors[4])', app.context);
  const validation = app.validate();
  assert.equal(validation.valid, false);
  assert.match(validation.reason, /übereinander/);
  app.redraw();
  assert.equal(app.element('export').disabled, true);
});
