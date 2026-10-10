import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';

function loadApi(fetchImpl) {
  const sample = { crops: [{ id: 'tomato' }], warnings: [], provenance: { mode: 'demo' } };
  const detail = { id: 'tomato', provenance: { mode: 'demo' } };
  const source = fs.readFileSync(new URL('../src/lib/api.ts', import.meta.url), 'utf8');
  const compiled = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const context = {
    exports: {}, fetch: fetchImpl, AbortController, URLSearchParams,
    setTimeout, clearTimeout, structuredClone,
    process: { env: { NEXT_PUBLIC_USE_MOCKS: 'false', NEXT_PUBLIC_API_URL: 'https://api.example.test' } },
    require(path) {
      if (path === './location') return { locationSearchUnavailable: 'unavailable' };
      if (path === '../mocks') return {
        getMockRecommend: () => structuredClone(sample),
        getMockCropDetail: () => structuredClone(detail),
      };
      return {};
    },
  };
  vm.runInNewContext(compiled, context);
  return context.exports;
}

test('connection failures return saved recommendations with an explicit warning', async () => {
  const api = loadApi(async () => { throw new TypeError('network down'); });
  const result = await api.getRecommendations(27.94, -82.29, 7);
  assert.equal(result.crops.length, 1);
  assert.match(result.warnings[0], /Live data is temporarily unavailable/);
  assert.equal(result.provenance.mode, 'demo');
});

test('backend 5xx falls back but client validation errors remain visible', async () => {
  const unavailable = loadApi(async () => Response.json({ detail: 'slow' }, { status: 503 }));
  assert.equal((await unavailable.getCropDetail('tomato', 27.94, -82.29)).id, 'tomato');

  const invalid = loadApi(async () => Response.json({ detail: 'Location must be in Florida' }, { status: 400 }));
  await assert.rejects(() => invalid.getRecommendations(40, -74), /Location must be in Florida/);
});
