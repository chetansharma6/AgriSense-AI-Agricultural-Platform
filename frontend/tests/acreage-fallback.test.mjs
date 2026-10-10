import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import ts from 'typescript';

function loadModules(fetchImpl) {
  const modules = new Map();
  function load(filename) {
    if (modules.has(filename)) return modules.get(filename);
    if (filename.endsWith('.json')) return { default: JSON.parse(fs.readFileSync(filename, 'utf8')) };
    const context = { exports: {}, structuredClone, fetch: fetchImpl, AbortController, URLSearchParams,
      setTimeout, clearTimeout, process: { env: { NEXT_PUBLIC_USE_MOCKS: 'false', NEXT_PUBLIC_API_URL: 'https://api.example.test' } },
      require(name) {
        let target = path.resolve(path.dirname(filename), name);
        if (!path.extname(target)) target = fs.existsSync(`${target}.ts`) ? `${target}.ts` : path.join(target, 'index.ts');
        return load(target);
      } };
    vm.runInNewContext(ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
    }).outputText, context);
    modules.set(filename, context.exports);
    return context.exports;
  }
  return { api: load(path.resolve('src/lib/api.ts')), mocks: load(path.resolve('src/mocks/index.ts')) };
}
const unavailable = async () => { throw new TypeError('network down'); };
const coords = [28.03, -82.15];

test('outage fallback applies arbitrary small acreage and preserves saved measurements', async () => {
  const { api, mocks } = loadModules(unavailable);
  const baseline = mocks.getMockRecommend(...coords);
  for (const acres of [0.1, 0.25, 0.5, 0.99, 2.7, 7]) {
    const result = await api.getRecommendations(...coords, acres);
    assert.deepEqual(result.conditions, baseline.conditions);
    assert.equal(result.provenance.mode, 'demo');
    assert.match(result.warnings[0], /Live data is temporarily unavailable/);
    for (const crop of result.crops) {
      const original = baseline.crops.find(item => item.id === crop.id);
      assert.deepEqual(crop.factors, original.factors);
      assert.deepEqual(crop.factor_details, original.factor_details);
      assert.ok(crop.score <= original.score);
      assert.equal(crop.est_gross_value, null);
      if (['cotton', 'peanut', 'soybean', 'field_corn', 'sugarcane'].includes(crop.id)) {
        assert.equal(crop.scale.fit, 'too_small');
        assert.ok(crop.score <= 40);
      }
      if (acres < 1) assert.ok(crop.score <= 74);
    }
    const cotton = await api.getCropDetail('cotton', ...coords, acres);
    assert.equal(cotton.score, result.crops.find(crop => crop.id === 'cotton').score);
    assert.deepEqual(cotton.scale, result.crops.find(crop => crop.id === 'cotton').scale);
    assert.equal(cotton.provenance.mode, 'demo');
  }
});

test('large property and missing acreage preserve scores without carrying over caps', async () => {
  const { api, mocks } = loadModules(unavailable);
  const baseline = mocks.getMockRecommend(...coords);
  const large = await api.getRecommendations(...coords, 1000);
  const missing = await api.getRecommendations(...coords);
  for (const original of baseline.crops) {
    const crop = large.crops.find(item => item.id === original.id);
    assert.equal(crop.scale.fit, 'good');
    assert.equal(crop.score, original.score);
    assert.equal(missing.crops.find(item => item.id === original.id).score, original.score);
  }
  await api.getRecommendations(...coords, 0.1);
  assert.deepEqual(mocks.getMockRecommend(...coords).crops, baseline.crops);
});

test('live requests forward acreage and keep successful responses intact', async () => {
  const calls = [];
  const live = { crops: [], warnings: [], provenance: { mode: 'live' } };
  const { api } = loadModules(async (url, options) => { calls.push({ url, options }); return Response.json(live); });
  assert.deepEqual(await api.getRecommendations(...coords, 0.1), live);
  assert.equal(new URL(calls[0].url).searchParams.get('acres'), '0.1');
  assert.equal(calls[0].options.headers, undefined);
});
