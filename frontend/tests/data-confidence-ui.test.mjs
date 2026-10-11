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

const LandSummary = load('components/LandSummary.tsx').default;
let mounted;
beforeEach(async () => {
  if (mounted) await act(async () => mounted.unmount());
  document.body.innerHTML = '<div id="root"></div>';
  mounted = createRoot(document.getElementById('root'));
});
const fixture = () => ({
  conditions: null, warnings: [], location: null, crops: [], scoring: null,
  confidence: { level: 'high', available_factors: 5, total_factors: 6, partial: true,
    data_status: 'cached', county_history_status: 'withheld',
    available_factor_names: ['soil_ph', 'frost_risk'], missing_factor_names: ['local_history'],
    notes: ['Fallback estimates; county values withheld.'] },
  provenance: { mode: 'cached', fawn_station: null, sources: [
    { name: 'Soil survey', status: 'live', data_status: 'live', url: 'https://example.com/soil',
      data_period: '2016–2025', geographic_level: 'Map unit', detail: 'Estimated soil properties',
      limitations: ['Not a field measurement'] },
    { name: 'County harvests', status: 'failed', data_status: 'cached', url: 'javascript:alert(1)', limitations: ['Values withheld'] },
  ] },
});
async function render(response) {
  await act(async () => mounted.render(React.createElement(LandSummary, { response })));
}
test('compact summary starts closed; disclosure updates accessibility and preserves details', async () => {
  const response = fixture();
  const original = JSON.stringify(response);
  await render(response);
  const button = document.querySelector('button');
  const panel = document.getElementById(button.getAttribute('aria-controls'));
  assert.equal(button.textContent.replace('⌄', '').trim(), 'View source details');
  assert.equal(button.getAttribute('aria-expanded'), 'false');
  assert.equal(panel.getAttribute('aria-hidden'), 'true');
  assert.ok(panel.hasAttribute('inert'));
  const summary = document.querySelector('[aria-label="Data coverage summary"]').textContent;
  assert.match(summary, /High data coverage.*5 of 6 factors available.*Saved cached data.*2 sources.*Partial result/);
  await act(async () => button.click());
  assert.equal(button.getAttribute('aria-expanded'), 'true');
  assert.equal(panel.getAttribute('aria-hidden'), 'false');
  assert.ok(!panel.hasAttribute('inert'));
  assert.match(panel.textContent, /Soil pH, Freeze risk/);
  assert.match(panel.textContent, /Missing factors: Local harvest history/);
  assert.match(panel.textContent, /County history: Withheld/);
  assert.match(panel.textContent, /Reporting period: 2016–2025/);
  assert.match(panel.textContent, /Geographic coverage: Map unit/);
  assert.match(panel.textContent, /Estimated soil properties.*Not a field measurement/);
  assert.match(panel.textContent, /Source: Failed/);
  assert.doesNotMatch(panel.textContent, /live · live|soil_ph|frost_risk/);
  assert.equal(panel.querySelector('a').href, 'https://example.com/soil');
  assert.equal(panel.querySelectorAll('a').length, 1);
  assert.equal(JSON.stringify(response), original);
  await act(async () => button.click());
  assert.equal(button.getAttribute('aria-expanded'), 'false');
  assert.ok(panel.hasAttribute('inert'));
});
test('summary updates from response data and supports zero factors and missing confidence', async () => {
  const response = fixture();
  response.confidence.level = 'low';
  response.confidence.available_factors = 0;
  response.confidence.data_status = 'demo';
  response.provenance.sources = [];
  await render(response);
  const summary = () => document.querySelector('[aria-label="Data coverage summary"]').textContent;
  assert.match(summary(), /Low data coverage.*0 of 6 factors available.*Saved demo data.*0 sources/);
  response.confidence = null;
  response.provenance.sources = [fixture().provenance.sources[0]];
  await render(response);
  assert.match(summary(), /Data coverage unavailable.*Factor availability unknown.*1 source/);
});
