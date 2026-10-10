import { test, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { createRequire } from 'node:module';
import ts from 'typescript';
import { JSDOM } from 'jsdom';

const dom = new JSDOM('<!doctype html><div id="root"></div>', { url: 'http://localhost/' });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, HTMLElement: dom.window.HTMLElement,
  Node: dom.window.Node, MouseEvent: dom.window.MouseEvent, IS_REACT_ACT_ENVIRONMENT: true });
Object.defineProperty(globalThis, 'navigator', { value: dom.window.navigator, configurable: true });
const nodeRequire = createRequire(import.meta.url);
const React = nodeRequire('react');
const { createRoot } = nodeRequire('react-dom/client');
const { act } = React;

const cache = new Map();
/** Compile a src/ TypeScript module; `overrides` replaces named imports (e.g. next/navigation). */
function load(rel, overrides = {}) {
  const key = rel + JSON.stringify(Object.keys(overrides));
  if (cache.has(key) && !Object.keys(overrides).length) return cache.get(key);
  const file = new URL(`../src/${rel}`, import.meta.url);
  const source = fs.readFileSync(file, 'utf8');
  const out = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true } }).outputText;
  const mod = { exports: {} };
  const req = (name) => {
    if (name in overrides) return overrides[name];
    if (name.startsWith('@/')) return load(`${name.slice(2)}.ts${fs.existsSync(new URL(`../src/${name.slice(2)}.tsx`, import.meta.url)) ? 'x' : ''}`);
    if (name.startsWith('./')) return load(`${rel.split('/').slice(0, -1).join('/')}/${name.slice(2)}.ts`);
    return nodeRequire(name);
  };
  vm.runInThisContext(`(function(exports, mod, require){${out}\n})`)(mod.exports, mod, req);
  cache.set(key, mod.exports);
  return mod.exports;
}

const marianna = JSON.parse(fs.readFileSync(new URL('../src/mocks/marianna.json', import.meta.url), 'utf8'));
const detail = (id) => marianna.crops[id];
const Fertilizer = load('components/FertilizerRecommendations.tsx').default;
const root = () => document.getElementById('root');
let mounted;

async function render(element) {
  document.body.innerHTML = '<div id="root"></div>';
  mounted = createRoot(root());
  await act(async () => { mounted.render(element); });
}
const names = () => [...document.querySelectorAll('article h3')].map((h) => h.textContent);
const chip = (label) => [...document.querySelectorAll('[role=group] button')].find((b) => b.textContent === label);
const click = (el) => act(async () => { el.dispatchEvent(new MouseEvent('click', { bubbles: true })); });
const explainButton = () => [...document.querySelectorAll('button')].find((b) => b.textContent === 'Explain with AI');
beforeEach(async () => { if (mounted) await act(async () => mounted.unmount()); mounted = undefined; globalThis.fetch = undefined; });

test('fertilizer section renders heading, soil-test caveat, six filter chips and cards', async () => {
  await render(React.createElement(Fertilizer, { crop: detail('potato'), acres: 0.25 }));
  assert.equal(document.querySelector('h2').textContent, 'Recommended Fertilizers');
  assert.match(root().textContent, /Explore fertilizer options suited to your crop, land size, and available soil information\./);
  assert.match(root().textContent, /A soil test is recommended before selecting fertilizer quantities or application rates/);
  assert.match(document.querySelector('[data-testid=soil-data-status]').textContent, /No soil-test results/);
  assert.deepEqual([...document.querySelectorAll('[role=group] button')].map((b) => b.textContent),
    ['All', 'Eco-Friendly', 'Cost-Effective', 'Organic', 'Low Maintenance', 'Small-Space Friendly']);
  assert.equal(chip('All').getAttribute('aria-pressed'), 'true');
  assert.ok(names().length >= 4);
  // Unconditional options come first; conditional (soil-test) options are labelled.
  assert.match(document.querySelector('article').textContent, /Controlled-Release Nitrogen|Slow-Release|Compost/);
  assert.ok([...document.querySelectorAll('article')].some((a) => /Conditional:/.test(a.textContent)));
  assert.ok([...document.querySelectorAll('article')].every((a) => /Relative cost \(\$+, estimate\)/.test(a.textContent) && /Why AgriSense recommends this/.test(a.textContent)));
});

test('different crops show different options, and sources state what they support', async () => {
  await render(React.createElement(Fertilizer, { crop: detail('peanut'), acres: 5 }));
  const peanut = names();
  await act(async () => mounted.unmount());
  await render(React.createElement(Fertilizer, { crop: detail('potato'), acres: 5 }));
  assert.notDeepEqual(peanut, names());
  assert.ok([...document.querySelectorAll('article a')].every((a) => a.href.startsWith('https://')));
  assert.ok([...document.querySelectorAll('article')].some((a) => /Supports: /.test(a.textContent)));
});

test('filter chips update the displayed options', async () => {
  await render(React.createElement(Fertilizer, { crop: detail('potato'), acres: 0.25 }));
  const all = names();
  await click(chip('Organic'));
  const organic = names();
  assert.ok(organic.length > 0 && organic.length < all.length);
  assert.equal(chip('Organic').getAttribute('aria-pressed'), 'true');
  assert.equal(chip('All').getAttribute('aria-pressed'), 'false');
  assert.match(root().textContent, /Showing \d+ of \d+ options/);
  assert.match(root().textContent, /Organic products can still cause runoff/);
  await click(chip('Organic'));
  assert.deepEqual(names(), all, 'toggling off restores every option');
  await click(chip('Eco-Friendly'));
  assert.notDeepEqual(names(), all);
  await click(chip('All'));
  assert.deepEqual(names(), all);
});

test('multiple filters combine and an empty result explains itself', async () => {
  await render(React.createElement(Fertilizer, { crop: detail('potato'), acres: 0.25 }));
  await click(chip('Eco-Friendly'));
  const eco = names();
  await click(chip('Low Maintenance'));
  const both = names();
  assert.ok(both.length <= eco.length && both.every((n) => eco.includes(n)));
  assert.equal(chip('Eco-Friendly').getAttribute('aria-pressed'), 'true');
  assert.equal(chip('Low Maintenance').getAttribute('aria-pressed'), 'true');
  await click(chip('Eco-Friendly')); await click(chip('Low Maintenance'));
  await click(chip('Cost-Effective')); await click(chip('Low Maintenance'));
  assert.equal(names().length, 0);
  assert.match(root().textContent, /No fertilizer category matches every selected filter/);
  assert.equal(document.querySelectorAll('article').length, 0);
});

test('large acreage hides small-space options; missing acreage is explained', async () => {
  await render(React.createElement(Fertilizer, { crop: detail('potato'), acres: 150 }));
  await click(chip('Small-Space Friendly'));
  assert.match(root().textContent, /No fertilizer category matches/);
  await act(async () => mounted.unmount());
  await render(React.createElement(Fertilizer, { crop: detail('potato') }));
  assert.match(root().textContent, /Acreage was not provided/);
  assert.ok(names().length >= 4);
});

const json = (body, ok = true, status = 200) => Promise.resolve({ ok, status, json: async () => body });

test('Explain with AI shows explanations once without changing order or repeating calls', async () => {
  const calls = [];
  globalThis.fetch = (url, init) => { calls.push({ url, body: JSON.parse(init.body) }); return json({ explanations: { compost: 'Compost suits Potato on sandy soil.' }, source: 'ai' }); };
  await render(React.createElement(Fertilizer, { crop: detail('potato'), acres: 2 }));
  const before = names();
  await click(explainButton());
  assert.match(root().textContent, /AI explanation:.*Compost suits Potato/);
  assert.deepEqual(names(), before);
  assert.equal(explainButton(), undefined, 'button is removed so the call is not repeated');
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, '/api/fertilizer-explain');
  assert.equal(calls[0].body.crop.id, 'potato');
  assert.equal(calls[0].body.acres, 2);
  assert.ok(!('fertilizers' in calls[0].body) && !JSON.stringify(calls[0].body).includes('score'), 'client never sends rankings');
});

test('loading state is announced and API failures keep the deterministic cards', async () => {
  let release;
  globalThis.fetch = () => new Promise((resolve) => { release = resolve; });
  await render(React.createElement(Fertilizer, { crop: detail('potato'), acres: 2 }));
  const before = names();
  await click(explainButton());
  assert.equal(document.querySelector('[role=status]:not([aria-live])')?.textContent, 'Writing explanations…');
  assert.deepEqual(names(), before);
  await act(async () => release({ ok: false, status: 502, json: async () => ({}) }));
  const alert = document.querySelector('[role=alert]');
  assert.match(alert.textContent, /unavailable right now/);
  assert.deepEqual(names(), before);

  for (const failing of [() => Promise.reject(new Error('offline')), () => json({ explanations: {}, source: 'none' }), () => json('garbage')]) {
    await act(async () => mounted.unmount());
    globalThis.fetch = failing;
    await render(React.createElement(Fertilizer, { crop: detail('potato'), acres: 2 }));
    await click(explainButton());
    assert.match(document.querySelector('[role=alert]').textContent, /recommendations below are unaffected/);
    assert.deepEqual(names(), before);
  }
});

test('selecting a crop on the detail page renders fertilizers beside existing sections', async () => {
  const params = new URLSearchParams({ lat: '30.8', lon: '-85.25', acres: '2' });
  const stub = () => null;
  const Detail = load('app/crops/[id]/CropDetailClient.tsx', {
    'next/navigation': { __esModule: true, useParams: () => ({ id: 'peanut' }), useSearchParams: () => params },
    'next/link': { __esModule: true, default: ({ href, children, ...rest }) => React.createElement('a', { href, ...rest }, children) },
    '@/lib/api': { __esModule: true, ApiError: class extends Error {}, getCropDetail: async (id) => detail(id) },
    '@/components/AiReport': { __esModule: true, default: stub }, '@/components/FactorChart': { __esModule: true, default: stub },
  }).default;
  const errors = [];
  const original = console.error;
  console.error = (...args) => errors.push(args.join(' '));
  try {
    await render(React.createElement(Detail));
  await act(async () => { await new Promise((r) => setTimeout(r, 20)); });
  const headings = [...document.querySelectorAll('h2')].map((h) => h.textContent);
  assert.ok(headings.includes('Recommended Fertilizers'), headings.join('|'));
  for (const existing of ['Local track record', 'Feeding the soil', 'Growing it']) assert.ok(headings.includes(existing), existing);
  assert.ok(headings.indexOf('Recommended Fertilizers') > headings.indexOf('Feeding the soil'));
  assert.match(root().textContent, /Showing \d+ of \d+ options for Peanut/);
  await click(chip('Organic'));
  assert.ok(names().length >= 1);
  } finally { console.error = original; }
  assert.deepEqual(errors, [], 'no React warnings such as duplicate keys');
});
