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
    if (name in overrides) return { __esModule: true, ...overrides[name] };
    if (name.endsWith('.json') && name.startsWith('@/')) return JSON.parse(fs.readFileSync(new URL(`../src/${name.slice(2)}`, import.meta.url), 'utf8'));
    if (name.startsWith('@/')) return load(`${name.slice(2)}.ts${fs.existsSync(new URL(`../src/${name.slice(2)}.tsx`, import.meta.url)) ? 'x' : ''}`);
    if (name.endsWith('.css')) return new Proxy({}, { get: (_, key) => String(key) });
    if (name.startsWith('./')) {
      const base = `${rel.split('/').slice(0, -1).join('/')}/${name.slice(2)}`;
      return load(`${base}${fs.existsSync(new URL(`../src/${base}.tsx`, import.meta.url)) ? '.tsx' : '.ts'}`);
    }
    return nodeRequire(name);
  };
  vm.runInThisContext(`(function(exports, mod, require){${out}\n})`)(mod.exports, mod, req);
  cache.set(key, mod.exports);
  return mod.exports;
}


const Link = ({ children, ...props }) => React.createElement('a', props, children);
const Card = load('components/CropCard.tsx', { 'next/link': { default: Link } }).default;
let mounted;
beforeEach(async () => {
  if (mounted) await act(async () => mounted.unmount());
  document.body.innerHTML = '<div id="root"></div>';
  mounted = createRoot(document.getElementById('root'));
});
const crop = { id: 'tomato', name: 'Tomato', score: 82, season_label: 'Sep–May',
 factors: {soil_ph: null, drainage: 0, season_temp: 92}, scale: null, price: null, avg_yield: null,
 limited_by: [], flags: [], action_plan: {first_test: 'Test soil pH', major_risk: 'Freeze damage', planting_window: 'October–February'} };
const demo = { mode: 'demo', sources: [{status: 'live', data_status: 'live'}] };
async function render(Component, props) { await act(async () => mounted.render(React.createElement(Component, props))); }
test('featured crop uses supplied evidence, preserves navigation context and labels demo provenance', async () => {
 const before = JSON.stringify(crop);
 await render(Card, {crop, rank:1, lat:28.03, lon:-82.15, acres:0.1, place:'Plant City', featured:true, provenance:demo});
 assert.match(document.body.textContent, /Your Best Match/);
 assert.match(document.body.textContent, /82.*100/);
 assert.match(document.body.textContent, /October–February/);
 assert.match(document.body.textContent, /92.*100/);
 assert.match(document.body.textContent, /Freeze damage/);
 assert.match(document.body.textContent, /Test soil pH/);
 assert.match(document.body.textContent, /Demo data.*not live measurements/);
 assert.doesNotMatch(document.body.textContent, /Live data/);
 const url = new URL(document.querySelector('a').href);
 assert.equal(url.pathname, '/crops/tomato');
 assert.equal(url.searchParams.get('acres'), '0.1');
 assert.equal(url.searchParams.get('place'), 'Plant City');
 assert.equal(JSON.stringify(crop), before);
 assert.equal(document.querySelector('details').open, false);
 assert.equal(document.querySelectorAll('[role="meter"]').length, 2);
});
test('unavailable guidance and score never imply a verified recommendation', async () => {
 await render(Card, {crop: {...crop, id:null, score:null, factors:null, action_plan:null, season_label:null}, rank:1, lat:28, lon:-82, featured:true});
 for (const text of ['Score unavailable', 'Factor evidence is unavailable', 'No specific risk information', 'first step is unavailable', 'Planting window unavailable', 'live measurements are not verified', 'Growing plan unavailable']) assert.ok(document.body.textContent.includes(text), text);
 assert.equal(document.querySelector('a'), null);
 assert.equal(document.querySelector('[role="meter"]'), null);
});
test('a critical limitation is shown before other risks', async () => {
 await render(Card, {crop: {...crop, limited_by:['soil_ph']}, rank:2, lat:28, lon:-82, confidence:{available_factors:3,total_factors:6}});
 assert.match(document.querySelector('dl').textContent, /Limited by.*soil pH/i);
 assert.match(document.body.textContent, /Partial data.*Some evidence is missing/);
});

test('homepage selection methods share feedback and preserve location in analysis navigation', async () => {
 let mapProps;
 let searchProps;
 let destination;
 const Home = load('app/page.tsx', {
  'next/image': {default: () => null},
  'next/navigation': {useRouter: () => ({push: (url) => { destination = url; }})},
  '@/components/MapLoader': {default: (props) => { mapProps = props; return null; }},
  '@/components/LocationSearch': {default: (props) => { searchProps = props; return null; }},
 }).default;
 await render(Home, {});
 const message = () => document.getElementById('location-message').textContent;
 const saved = JSON.parse(fs.readFileSync(new URL('../src/mocks/plant_city.json', import.meta.url), 'utf8'));
 const preview = document.querySelector('[aria-labelledby="example-heading"]');
 const strawberry = saved.recommend.crops.find((crop) => crop.id === 'strawberry');
 assert.ok(preview.textContent.includes(String(strawberry.score)));
 assert.ok(preview.textContent.includes(strawberry.flags[0]));
 const exampleUrl = new URL(preview.querySelector('a').href);
 assert.equal(exampleUrl.pathname, '/results');
 assert.equal(Number(exampleUrl.searchParams.get('lat')), saved.recommend.location.lat);
 assert.equal(Number(exampleUrl.searchParams.get('lon')), saved.recommend.location.lon);
 await act(async () => [...document.querySelectorAll('button')].find((b) => b.textContent.includes('Plant City')).click());
 assert.match(message(), /Ready to analyze: Plant City/);
 assert.equal(searchProps.selectedLabel, 'Selected: Plant City');
 assert.equal(mapProps.value.lat, 28.03);
 assert.match(document.body.textContent, /Location selected/);
 await act(async () => document.querySelector('form').dispatchEvent(new dom.window.Event('submit', {bubbles:true,cancelable:true})));
 assert.equal(new URL(destination, 'http://localhost').searchParams.get('place'), 'Plant City');
 await act(async () => searchProps.onSelect({lat:29.71,lon:-81.5,label:'Hastings, FL'}));
 assert.match(message(), /Hastings, FL/);
 await act(async () => mapProps.onChange(27.1234, -81.4321));
 assert.match(message(), /27.1234, -81.4321/);
 assert.match(document.querySelector('button[type="submit"]').textContent, /Analyze selected location/);
 assert.equal(document.querySelector('button[type="submit"]').disabled, false);
 const input = [...document.querySelectorAll('input')].find((input) => input.placeholder === '27.8000');
 await act(async () => {
  Object.getOwnPropertyDescriptor(dom.window.HTMLInputElement.prototype, 'value').set.call(input, '28.5');
  input.dispatchEvent(new dom.window.Event('input', {bubbles:true}));
 });
 assert.match(message(), /28.5000, -81.4321/);
 await act(async () => mapProps.onChange(40, -81));
 assert.match(message(), /Location must be in Florida/);
 assert.equal(document.querySelector('button[type="submit"]').disabled, true);
});

test('results feature the actual highest score before land details and open its plan', async () => {
 const response = {crops:[{...crop,id:'potato',name:'Potato',score:40},{...crop,score:82}],provenance:demo};
 const before = JSON.stringify(response);
 const Results = load('app/results/ResultsClient.tsx', {
  'next/navigation': {useSearchParams: () => new URLSearchParams('lat=28.03&lon=-82.15&acres=0.1&place=Plant+City')},
  'next/link': {default: Link},
  '@/lib/api': {getRecommendations: async () => response, ApiError: class extends Error {}},
  '@/components/CropCard': {default: Card},
  '@/components/LandSummary': {default: () => React.createElement('section', {'data-land':true}, 'Land details')},
 }).default;
 await render(Results, {});
 const hero = document.querySelector('.results-hero');
 assert.match(hero.textContent, /Plant City, Florida.*0.1 acres.*Demo data/);
 assert.equal(hero.querySelector('a').getAttribute('href'), '/');
 const featured = document.querySelector('article');
 assert.equal(featured.querySelector('h2').textContent, 'Your Best Match');
 assert.equal(featured.querySelector('h3').textContent, 'Tomato');
 assert.ok(featured.compareDocumentPosition(document.querySelector('[data-land]')) & dom.window.Node.DOCUMENT_POSITION_FOLLOWING);
 const url = new URL(featured.querySelector('a').href);
 assert.equal(url.pathname, '/crops/tomato');
 assert.equal(url.searchParams.get('lat'), '28.0300');
 assert.equal(url.searchParams.get('lon'), '-82.1500');
 assert.equal(url.searchParams.get('acres'), '0.1');
 assert.equal(JSON.stringify(response), before);
});

test('location search hides superseded choices after another selection and retains new search errors', async () => {
 const Search = load('components/LocationSearch.tsx', {
  '@/lib/api': { searchLocation: async (query) => {
   if (query === 'missing') return [];
   return [{label:'Plant City, FL',lat:28.03,lon:-82.15},{label:'Hastings, FL',lat:29.71,lon:-81.5}];
  }, ApiError: class extends Error {} },
 }).default;
 const props = {selectedLabel:'',onSelect:()=>{}};
 await render(Search, props);
 async function search(query) {
  await act(async () => {
   const input = document.querySelector('input');
   Object.getOwnPropertyDescriptor(dom.window.HTMLInputElement.prototype, 'value').set.call(input, query);
   input.dispatchEvent(new dom.window.Event('input', {bubbles:true}));
  });
  await act(async () => document.querySelector('form').dispatchEvent(new dom.window.Event('submit', {bubbles:true,cancelable:true})));
 }
 await search('town');
 assert.match(document.body.textContent, /Choose a Florida location below/);
 await render(Search, {...props,selectedLabel:'Selected: Marianna'});
 assert.doesNotMatch(document.body.textContent, /Choose a Florida location below/);
 assert.equal(document.querySelector('[aria-label="Matching Florida locations"]'), null);
 await search('missing');
 assert.match(document.body.textContent, /No Florida match/);
});

test('data page preserves scoring weights, source links and visible limitations', async () => {
 const About = load('app/about/page.tsx').default;
 await render(About, {});
 assert.match(document.body.textContent, /01.*Agricultural Data.*02.*Suitability Scoring.*03.*AI Interpretation/);
 assert.match(document.body.textContent, /Anthropic.*never invents scores/);
 assert.equal(document.querySelectorAll('table tbody tr').length, 6);
 assert.equal(document.querySelector('[aria-labelledby="sources-heading"]').querySelectorAll('a').length, 5);
 assert.equal(document.querySelector('[aria-labelledby="limitations-heading"]').closest('details'), null);
 assert.match(document.querySelector('[aria-labelledby="limitations-heading"]').textContent, /50 km.*map-unit averages.*statewide data/);
 assert.equal(document.querySelectorAll('details').length, 4);
});
