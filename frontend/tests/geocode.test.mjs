import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const __dirname = path.dirname(fileURLToPath(import.meta.url));

const unavailable = 'Location search is unavailable right now. Click the map or enter coordinates instead.';
function loadRoute(fetch) {
  const source = fs.readFileSync(path.join(__dirname, '../src/app/api/geocode/route.ts'), 'utf8');
  const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
  const context = { exports: {}, require: () => ({ locationSearchUnavailable: unavailable }),
    fetch, Response, URL, URLSearchParams, AbortSignal, setTimeout, process, console };
  vm.runInNewContext(compiled, context);
  return q => context.exports.GET(new Request(`http://localhost/api/geocode?${new URLSearchParams({ q })}`));
}
const city = (name, state = 'Florida', lat = '28.03', lon = '-82.15') => ({
  lat, lon, address: { city: name, county: 'Hillsborough County', state },
});

test('validates input without calling upstream', async () => {
  const get = loadRoute(() => { throw new Error('Unexpected upstream call'); });
  for (const q of ['', '   ', 'x'.repeat(101)]) assert.equal((await get(q)).status, 400);
});

test('ZIP results use the first place, filter Florida, and cache trimmed queries', async () => {
  let calls = 0;
  const get = loadRoute(async url => {
    calls++;
    if (url.endsWith('99999')) return new Response(null, { status: 404 });
    return Response.json({ places: [{ 'place name': 'Plant City', 'state abbreviation': url.endsWith('30301') ? 'GA' : 'FL', latitude: '28.013', longitude: '-82.1339' }] });
  });
  const result = await (await get(' 33563 ')).json();
  assert.deepEqual(result.results, [{ label: 'Plant City, FL', lat: 28.013, lon: -82.1339, county: null, state: 'FL' }]);
  await get('33563');
  assert.equal(calls, 1);
  assert.deepEqual((await (await get('30301')).json()).results, []);
  assert.deepEqual((await (await get('99999')).json()).results, []);
});

test('city lookups coalesce, cache case-insensitively, and reject non-Florida/out-of-bounds points', async () => {
  let calls = 0;
  const get = loadRoute(async (url, options) => {
    calls++;
    const query = new URL(url).searchParams;
    assert.equal(query.get('bounded'), '1');
    assert.equal(query.get('viewbox'), '-87.7,31.1,-79.9,24.3');
    assert.equal(query.get('countrycodes'), 'us');
    assert.match(options.headers['User-Agent'], /AgriSense/);
    assert(options.signal instanceof AbortSignal);
    return Response.json([city('Plant City'), city('Atlanta', 'Georgia'), city('Outside', 'Florida', '35'), city('Invalid', 'Florida', 'NaN'), { ...city('Weston'), name: 'Atlanta', addresstype: 'road', category: 'highway' }]);
  });
  const responses = await Promise.all([get('Plant City'), get('plant city')]);
  assert.equal(calls, 1);
  assert.deepEqual((await responses[0].json()).results, [{ label: 'Plant City, Hillsborough County, FL', lat: 28.03, lon: -82.15, county: 'Hillsborough County', state: 'FL' }]);
  await get('PLANT CITY');
  assert.equal(calls, 1);
});

test('different city requests start at least one second apart, and failures can retry', async () => {
  const starts = [];
  let active = 0;
  const get = loadRoute(async () => {
    assert.equal(active++, 0);
    starts.push(Date.now());
    await new Promise(resolve => setTimeout(resolve, 20));
    active--;
    if (starts.length === 1) throw new Error('Upstream unavailable');
    return Response.json([]);
  });
  const responses = await Promise.all([get('Fail'), get('Hastings')]);
  assert.equal(responses[0].status, 502);
  assert.equal((await responses[0].json()).detail, unavailable);
  assert.equal(responses[1].status, 200);
  assert(starts[1] - starts[0] >= 1000);
  assert.equal((await get('Fail')).status, 200);
});

test('ZIP upstream failures produce the fallback message and are not cached', async () => {
  let calls = 0;
  const get = loadRoute(async () => { calls++; return new Response(null, { status: 503 }); });
  for (let i = 0; i < 2; i++) {
    const response = await get('33563');
    assert.equal(response.status, 502);
    assert.equal((await response.json()).detail, unavailable);
  }
  assert.equal(calls, 2);
});
