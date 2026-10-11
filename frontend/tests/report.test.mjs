import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';
function loadRoute(ai = false, fail = false) {
  const calls = [];
  class Anthropic {
    static APIError = class extends Error {};
    messages = { create: async input => {
      calls.push(input);
      if (fail) throw new Anthropic.APIError("sensitive provider message");
      return { content: [{ type: 'text', text: JSON.stringify({ verdict: 'Cotton is impractical for this lot.', summary: 'Choose a garden crop.', pros: ['a', 'b', 'c'], cons: ['a', 'b', 'c'], first_steps: ['a', 'b', 'c'] }) }] };
    } };
  }
  const source = fs.readFileSync(new URL('../src/app/api/report/route.ts', import.meta.url), 'utf8');
  const context = { exports: {}, Response, TextEncoder, process: { env: ai ? { ANTHROPIC_API_KEY: 'test' } : {} }, require: name => name === '@anthropic-ai/sdk' ? { default: Anthropic } : name === '@/lib/format' ? { factorLabel: x => x, scoreTone: s => s >= 75 ? 'strong' : s >= 50 ? 'fair' : 'weak' } : {} };
  vm.runInNewContext(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, context);
  return { calls, post: (crop, acres) => context.exports.POST(new Request('http://localhost/api/report', { method: 'POST', body: JSON.stringify({ crop, acres }) })) };
}
const crop = { id: 'cotton', name: 'Cotton', score: 40, factors: { soil_ph: 100, drainage: 100, season_temp: 100, frost_risk: 100, rainfall: 100, local_history: 100 }, scale: { fit: 'too_small', min_practical_acres: 500, note: 'Land size caps the score at 40.' }, flags: ['Too small'], action_plan: {}, risk_notes: [] };
test('live backend water and management guidance do not block acreage-aware summaries', async () => {
  const route = loadRoute(true);
  const source = { title: 'UF/IFAS Extension', url: 'https://edis.ifas.ufl.edu/' };
  const detail = { ...crop, provenance: { mode: 'live', sources: [], fawn_station: null },
    water_plan: { ideal_monthly_low_mm: 90, ideal_monthly_high_mm: 120,
      season_status: 'within crop threshold', irrigation_sensitivity: 'routine monitoring',
      note: 'Monitor field soil moisture.', source },
    management_guidance: { soil_health_practices: ['Test soil before fertilizing'],
      rotation_guidance: 'Confirm crop rotation with UF/IFAS Extension.', source } };
  const response = await route.post(detail, 0.25);
  assert.equal(response.status, 200);
  assert.equal((await response.json()).source, 'ai');
  const prompt = JSON.parse(route.calls[0].messages[0].content.split('\n\n')[0]);
  assert.equal(prompt.acres, 0.25);
  assert.equal(prompt.crop.score, detail.score);
  assert.equal(prompt.crop.scale.fit, 'too_small');
  assert.equal(prompt.crop.provenance.mode, 'live');
  // Extra guidance stays outside the trusted AI projection; validation still applies.
  assert.equal(prompt.crop.water_plan, undefined);
  assert.equal((await route.post({ ...detail, unexpected: 'field' }, 0.25)).status, 400);
  assert.equal((await route.post({ ...detail, score: 101 }, 0.25)).status, 400);
  assert.equal((await route.post({ ...detail, factors: {} }, 0.25)).status, 400);
});
test('report sends acreage, scale and flags and accepts backend detail fields', async () => {
  const route = loadRoute(true);
  assert.equal((await (await route.post(crop, 0.1)).json()).source, 'ai');
  const prompt = JSON.parse(route.calls[0].messages[0].content.split('\n\n')[0]);
  assert.equal(prompt.acres, 0.1);
  assert.match(prompt.land_size_context, /backyard/);
  assert.equal(prompt.crop.scale.fit, 'too_small');
  assert.deepEqual(prompt.crop.flags, ['Too small']);
  assert.match(route.calls[0].system, /Never recommend cotton/);
  await route.post(crop, 100);
  assert.equal(route.calls.length, 2);
});
test('fallback explains missing acreage and discourages undersized field production', async () => {
  const route = loadRoute();
  const small = await (await route.post(crop, 0.1)).json();
  assert.match(small.report.summary, /backyard/);
  assert.match(small.report.first_steps.join(' '), /instead of planning commercial field production/);
  const missing = await (await route.post(crop)).json();
  assert.match(missing.report.summary, /recommendation confidence/);
  assert.equal((await route.post(crop, 0.09)).status, 400);
});

test('committed crop evidence strings fit the report request bound', async () => {
  const route = loadRoute();
  const detail = { ...crop, requirements: { source_notes: 'Verified UF/IFAS source note. '.repeat(27) } };
  assert.equal((await route.post(detail, 0.25)).status, 200);
  const oversized = { ...crop, requirements: { source_notes: 'x'.repeat(1025) } };
  assert.equal((await route.post(oversized, 0.25)).status, 413);
});

test('provider failure returns a usable report and saved provenance reaches the prompt', async () => {
  const route = loadRoute(true, true);
  const saved = { ...crop, provenance: { mode: 'demo', sources: [], fawn_station: null } };
  const response = await route.post(saved, 0.25);
  assert.equal(response.status, 200);
  const body = await response.json();
  assert.equal(body.source, 'fallback');
  assert.doesNotMatch(JSON.stringify(body), /sensitive provider message/);
  const prompt = JSON.parse(route.calls[0].messages[0].content.split('\n\n')[0]);
  assert.equal(prompt.acres, 0.25);
  assert.equal(prompt.crop.provenance.mode, 'demo');
});
