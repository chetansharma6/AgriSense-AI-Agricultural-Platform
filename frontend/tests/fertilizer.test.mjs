import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';

function load(path, requireMap = {}, extra = {}) {
  const context = { exports: {}, Response, TextEncoder, process: { env: {} }, console, ...extra, require: (n) => requireMap[n] ?? {} };
  const source = fs.readFileSync(new URL(path, import.meta.url), 'utf8');
  vm.runInNewContext(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, context);
  return context.exports;
}
const f = load('../src/lib/fertilizer.ts');
const sandy = { texture: 'sand', drainage: 'Somewhat excessively drained', sand_pct: 90, soil_ph: 6.0, organic_matter_pct: 1 };
const make = (id, n, acres, conditions = sandy) => f.contextFromCrop({ id, nutrient_plan: { n_lb_per_acre: n }, conditions }, acres);
const ids = (list) => list.map((x) => x.id);

test('different crops produce different fertilizer options', () => {
  const peanutList = f.recommendFertilizers(make('peanut', 0, 2));
  const corn = f.recommendFertilizers(make('sweet_corn', 180, 2));
  const open = (list) => ids(list.filter((x) => !x.conditional));
  assert.notDeepEqual(open(peanutList), open(corn));
  assert.ok(open(corn).includes('controlled_release_n') && open(corn).includes('nitrogen_soluble'));
  assert.ok(!open(peanutList).includes('nitrogen_soluble'));
});

test('zero nitrogen figure is not treated as proof nitrogen is never needed', () => {
  const peanutList = f.recommendFertilizers(make('peanut', 0, 2));
  const nitrogen = peanutList.find((x) => x.id === 'nitrogen_soluble');
  assert.ok(nitrogen, 'still listed, not hidden');
  assert.match(nitrogen.conditional, /not a guarantee/);
  assert.ok(peanutList.indexOf(nitrogen) > peanutList.findIndex((x) => !x.conditional));
  // Nitrogen is never the only signal: P/K stay soil-test dependent for every crop.
  for (const cropList of [peanutList, f.recommendFertilizers(make('sweet_corn', 180, 2))]) {
    for (const id of ['potassium_focused', 'pk_no_nitrogen']) assert.match(cropList.find((x) => x.id === id).conditional, /soil test/i);
  }
  // Unknown nitrogen data is flagged rather than guessed.
  assert.ok(f.recommendFertilizers(make('tomato', null, 2)).find((x) => x.id === 'nitrogen_soluble').whyAgriSense.some((r) => /no nitrogen figure/.test(r)));
});

test('conditional options always sort after unconditional ones', () => {
  for (const [crop, n] of [['peanut', 0], ['tomato', 200], ['cotton', 60]]) {
    const flags = f.recommendFertilizers(make(crop, n, 2)).map((x) => x.conditional !== null);
    assert.equal(JSON.stringify(flags), JSON.stringify([...flags].sort((a, b) => Number(a) - Number(b))));
  }
});

test('P and K products need a soil test showing low levels to be unconditional, and are dropped when adequate', () => {
  const base = make('tomato', 200, 1);
  const low = f.recommendFertilizers({ ...base, soilTest: { k: 'low' } });
  assert.equal(low.find((x) => x.id === 'potassium_focused').conditional, null);
  assert.ok(low.find((x) => x.id === 'potassium_focused').whyAgriSense.some((r) => /^Soil test:/.test(r)));
  const ok = f.recommendFertilizers({ ...base, soilTest: { k: 'adequate', p: 'high' } });
  assert.ok(!ids(ok).includes('potassium_focused') && !ids(ok).includes('pk_no_nitrogen'));
  assert.match(ok.find((x) => x.id === 'balanced_soluble').conditional, /adequate or high phosphorus/);
  // Regional estimates are labelled and never presented as soil test.
  const sand = f.recommendFertilizers(base).flatMap((x) => x.whyAgriSense).filter((r) => /fast-draining/.test(r));
  assert.ok(sand.length && sand.every((r) => /^Regional estimate:/.test(r) && /not a soil test/.test(r)));
  assert.ok(!f.recommendFertilizers(base).flatMap((x) => x.whyAgriSense).some((r) => /^Soil test:/.test(r)));
});

test('filters change the list and eco is not simply organic', () => {
  const all = f.recommendFertilizers(make('tomato', 200, 0.25));
  const organic = f.applyFilters(all, ['organic']);
  const eco = f.applyFilters(all, ['eco']);
  assert.ok(organic.length > 0 && organic.length < all.length && organic.every((x) => x.organic));
  assert.ok(eco.length < all.length);
  assert.ok(eco.some((x) => !x.organic), 'non-organic slow release can be eco-friendly');
  assert.equal(f.applyFilters(all, []).length, all.length);
  const both = f.applyFilters(all, ['eco', 'organic']);
  assert.ok(both.every((x) => x.organic && x.traits.eco));
  assert.ok(f.applyFilters(all, ['low_maintenance']).every((x) => x.traits.low_maintenance));
  assert.ok(f.applyFilters(all, ['cost']).every((x) => x.cost === '$'));
});

test('sandy soil lowers eco rating of soluble fertilizer', () => {
  const sol = (c) => f.recommendFertilizers(make('tomato', 200, 5, c)).find((x) => x.id === 'nitrogen_soluble');
  assert.equal(sol(sandy).traits.eco, false);
  assert.ok(sol(sandy).whyAgriSense.some((r) => /leaching/.test(r)));
});

test('acreage changes ranking and small-space filtering', () => {
  const rank = (a) => ids(f.recommendFertilizers(make('sweet_corn', 180, a)));
  const backyard = rank(0.25), large = rank(100);
  assert.notDeepEqual(backyard, large);
  assert.ok(backyard.indexOf('compost') < large.indexOf('compost'));
  assert.ok(large.indexOf('nitrogen_soluble') < backyard.indexOf('nitrogen_soluble'));
  assert.ok(f.applyFilters(f.recommendFertilizers(make('sweet_corn', 180, 100)), ['small_space']).length === 0);
  assert.ok(f.applyFilters(f.recommendFertilizers(make('sweet_corn', 180, 0.25)), ['small_space']).length > 0);
});

test('missing acreage is handled gracefully', () => {
  const list = f.recommendFertilizers(make('tomato', 200, undefined));
  assert.ok(list.length > 3 && list.every((x) => Number.isFinite(x.score)));
  assert.ok(list[0].whyAgriSense.some((r) => /no acreage was given/.test(r)));
});

test('missing soil-test data never fabricates deficiencies, rates or prices', () => {
  const list = f.recommendFertilizers(make('tomato', 200, 1));
  const text = JSON.stringify(list);
  assert.ok(!/deficien/i.test(text.replace(/does not estimate deficiencies/g, '')));
  assert.ok(!/\d+\s*(lb|kg|pounds?)\s*(\/|per)\s*(acre|ft|sq)/i.test(text) || /lb N per acre per season/.test(text));
  assert.ok(!/\$\d/.test(text));
  const kOnly = list.find((x) => x.id === 'potassium_focused');
  assert.match(kOnly.conditional, /soil test/i);
  assert.ok(list.every((x) => /^\${1,3}$/.test(x.cost)));
});

test('soil-test results, when supplied, adjust recommendations', () => {
  const base = make('tomato', 200, 1);
  const withP = f.recommendFertilizers({ ...base, soilTest: { p: 'high', k: 'low' } });
  const bal = f.recommendFertilizers(base).find((x) => x.id === 'balanced_soluble');
  assert.ok(withP.find((x) => x.id === 'balanced_soluble').score < bal.score);
  assert.equal(withP.find((x) => x.id === 'potassium_focused').conditional, null);
});

test('only catalog categories and verified sources appear, each with the claim it supports and no brands', () => {
  const allowed = new Set(['https://edis.ifas.ufl.edu/publication/CV002', 'https://edis.ifas.ufl.edu/publication/SS163', 'https://edis.ifas.ufl.edu/cv296',
    'https://edis.ifas.ufl.edu/cv101', 'https://ask.ifas.ufl.edu/publication/SS661', 'https://ask.ifas.ufl.edu/publication/AG496', 'https://www.epa.gov/nutrientpollution/sources-and-solutions-agriculture']);
  for (const [crop, n] of [['cotton', 60], ['peanut', 0], ['tomato', 200]]) {
    for (const x of f.recommendFertilizers(make(crop, n, 500))) {
      assert.ok(x.sources.every((s) => allowed.has(s.url) && s.supports.length > 20));
      assert.ok(!/miracle|scotts|osmocote|jobe|espoma/i.test(JSON.stringify(x)));
    }
  }
  const sourceUrls = (crop, n, id) => f.recommendFertilizers(make(crop, n, 5)).find((x) => x.id === id).sources.map((s) => s.url);
  assert.ok(sourceUrls('peanut', 0, 'potassium_focused').includes('https://ask.ifas.ufl.edu/publication/AG496'));
  assert.ok(!sourceUrls('tomato', 200, 'potassium_focused').includes('https://ask.ifas.ufl.edu/publication/AG496'));
  assert.ok(!sourceUrls('cotton', 60, 'controlled_release_n').some((u) => u.includes('cv296')), 'vegetable-only source not cited for field crops');
  assert.equal(sourceUrls('tomato', 200, 'compost').join(), 'https://ask.ifas.ufl.edu/publication/SS661,https://edis.ifas.ufl.edu/cv101');
});

test('cost categories carry a stated basis and are never prices', () => {
  for (const x of f.recommendFertilizers(make('tomato', 200, 1))) {
    assert.match(x.cost, /^\${1,3}$/);
    assert.ok(x.costBasis.length > 20 && !/\$\d/.test(x.costBasis));
  }
  assert.ok(f.FILTERS.find((x) => x.id === 'cost').basis.includes('not retail prices'));
});

test('pH note is described as an estimate and only appears out of range', () => {
  const ctx = { ...make('tomato', 200, 1, { ...sandy, soil_ph: 8 }), phIdeal: [6, 6.8] };
  assert.match(f.phNote(ctx), /Regional data estimates/);
  assert.equal(f.phNote({ ...ctx, conditions: { ...sandy, soil_ph: 6.2 } }), null);
});

function route(ai, fail, text) {
  const calls = [];
  class Anthropic {
    static APIError = class extends Error {};
    messages = { create: async (input) => { calls.push(input); if (fail) throw new Anthropic.APIError('x'); return { content: [{ type: 'text', text }] }; } };
  }
  const exports = load('../src/app/api/fertilizer-explain/route.ts', { '@anthropic-ai/sdk': { default: Anthropic }, '@/lib/fertilizer': f },
    { process: { env: ai ? { ANTHROPIC_API_KEY: 'k' } : {} } });
  return { calls, post: (body) => exports.POST(new Request('http://x/api', { method: 'POST', body: JSON.stringify(body) })) };
}
const body = { crop: { id: 'tomato', nutrient_plan: { n_lb_per_acre: 200 }, conditions: sandy }, acres: 1 };

test('Anthropic failure or missing key yields empty explanations, not an error', async () => {
  for (const r of [route(false, false, ''), route(true, true, ''), route(true, false, 'not json')]) {
    const res = await r.post(body);
    assert.equal(res.status, 200);
    assert.deepEqual(await res.json(), { explanations: {}, source: 'none' });
  }
});

test('Anthropic explanations are limited to deterministic ids and never see invented data', async () => {
  const r = route(true, false, JSON.stringify({ explanations: { compost: 'Good for sandy soil.', invented_brand: 'Buy X' } }));
  const res = await r.post(body);
  const json = await res.json();
  assert.deepEqual(json, { explanations: { compost: 'Good for sandy soil.' }, source: 'ai' });
  assert.match(r.calls[0].system, /Never invent soil-test values/);
  assert.match(r.calls[0].messages[0].content, /"soil_test_available":false/);
  assert.equal((await route(true, false, '{}').post({ crop: { id: 'kudzu' } })).status, 400);
});

test('crop detail integrates fertilizers without replacing existing sections', () => {
  const detail = fs.readFileSync(new URL('../src/app/crops/[id]/CropDetailClient.tsx', import.meta.url), 'utf8');
  assert.match(detail, /<FertilizerRecommendations key=\{`\$\{key\}:fertilizer`\} crop=\{crop\} acres=\{landAcres\}/);
  for (const id of ['feeding-soil', 'water-planning', 'track-record', 'action-plan']) assert.match(detail, new RegExp(id));
  const ui = fs.readFileSync(new URL('../src/components/FertilizerRecommendations.tsx', import.meta.url), 'utf8');
  for (const label of ['Recommended Fertilizers', 'Explore fertilizer options suited to your crop, land size, and available soil information.',
    'A soil test is recommended before selecting fertilizer quantities or application rates', 'aria-pressed']) assert.ok(ui.includes(label), label);
  // Mobile: wrapping chips, 44px touch targets, single column below lg.
  assert.match(ui, /flex-wrap/); assert.match(ui, /min-h-11/); assert.match(ui, /lg:grid-cols-2/);
  assert.match(ui, /unavailable right now\. The recommendations below are unaffected/);
});

test('identical explanation requests share one provider call; failures are retried, not cached', async () => {
  const r = route(true, false, JSON.stringify({ explanations: { compost: 'Compost suits Potato in Jackson County.' } }));
  const withCounty = { ...body, crop: { ...body.crop, county: 'Jackson' } };
  await r.post(withCounty); await r.post(withCounty);
  assert.equal(r.calls.length, 1);
  assert.match(r.calls[0].messages[0].content, /"county":"Jackson"/);
  assert.match(r.calls[0].messages[0].content, /"acres":1/);
  assert.match(r.calls[0].messages[0].content, /"crop":"Tomato"/);
  assert.ok(r.calls[0].max_tokens >= 4000, 'room for the model to think and finish the JSON');
  const bad = route(true, false, 'not json');
  await bad.post(body); await bad.post(body);
  assert.equal(bad.calls.length, 2);
});

test('explanations that invent quantities, prices or grades are discarded', async () => {
  const invented = { compost: 'Apply 50 lb per acre.', slow_release_balanced: 'Costs $12 a bag.', balanced_soluble: 'Use 10-10-10 weekly.', nitrogen_soluble: 'Adds 20% more yield.' };
  const res = await route(true, false, JSON.stringify({ explanations: { ...invented, controlled_release_n: 'Fits Tomato with fewer applications.' } })).post(body);
  assert.deepEqual(await res.json(), { explanations: { controlled_release_n: 'Fits Tomato with fewer applications.' }, source: 'ai' });
});

test('the route never echoes credentials and builds its own recommendation list', async () => {
  const source = fs.readFileSync(new URL('../src/app/api/fertilizer-explain/route.ts', import.meta.url), 'utf8');
  assert.ok(!/ANTHROPIC_API_KEY[^?]*Response\.json/.test(source));
  assert.match(source, /recommendFertilizers\(ctx\)/);
  assert.ok(!/ranking|score/.test(source.split('const key = JSON.stringify')[0].split('const facts')[1] ?? ''), 'scores are not sent to the model');
});

test('every saved demo crop (all four sets, 13 crops each) produces fertilizer options', () => {
  for (const name of ['marianna', 'hastings', 'plant_city', 'belle_glade']) {
    const crops = JSON.parse(fs.readFileSync(new URL(`../src/mocks/${name}.json`, import.meta.url), 'utf8')).crops;
    assert.equal(Object.keys(crops).length, 13);
    for (const crop of Object.values(crops)) {
      const list = f.recommendFertilizers(f.contextFromCrop(crop, 2));
      assert.ok(list.length >= 4 && list.some((x) => !x.conditional), `${name}/${crop.id}`);
    }
  }
});
