import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';

const context = { exports: {}, Intl, Date };
const source = fs.readFileSync(new URL('../src/lib/format.ts', import.meta.url), 'utf8');
vm.runInNewContext(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, context);
const f = context.exports;

test('acreage in notes and summaries preserves manually entered fractional lots', () => {
 for (const acres of [0.1, 0.25, 0.5, 2.7, 1000]) {
  const text = f.formatDisplayText(`Growing area: ${acres} acres.`);
  assert.equal(text, `Growing area: ${acres.toLocaleString('en-US')} acres.`);
  assert.equal(f.formatDisplayText(text), text);
 }
});

test('whole-number units and yields preserve zero and missing data', () => {
 assert.equal(f.formatDays(271.6), '272 days');
 assert.equal(f.formatDays(365), '365 days');
 assert.equal(f.formatMillimeters(1281.4), '1,281 mm');
 assert.equal(f.formatYield({ value:719.6, unit:'LB / ACRE' }), '720 lb/acre');
 assert.equal(f.formatYield({ value:374, unit:'CWT / ACRE' }), '374 cwt/acre');
 assert.equal(f.formatDays(null), 'No data');
 assert.equal(f.formatYield({ value:0, unit:'LB / ACRE' }), '0 lb/acre');
});

test('currency keeps both dollar signs, two decimals, and normalized units', () => {
 for(const [low,high,unit,expected] of [[55,61.6,'CWT','$55.00–$61.60 per cwt'],[.63,.95,'LB','$0.63–$0.95 per lb'],[4.84,7.42,'BU','$4.84–$7.42 per bu']]) {
  assert.equal(f.formatPrice({low,high,unit:`$ / ${unit}`}),expected);
 }
 assert.equal(f.formatPrice({low:null,high:5,unit:'$ / LB'}),'No data');
});

test('frost dates use stable month names and reject invalid dates', () => {
 assert.equal(f.formatFrostDate('02-27'),'Feb 27');
 assert.equal(f.formatFrostDate('02-29'),'Feb 29');
 assert.equal(f.formatFrostDate('02-31'),'No data');
 assert.equal(f.formatFrostDate(null),'No data');
});

test('temperature text uses proper minus signs and stays unchanged if formatted twice', () => {
 assert.equal(f.formatTemperature(21.9),'21.9°C (71°F)');
 const text=f.formatDisplayText('Hard freezes (-2 C or colder); crop tolerates about 0');
 assert(text.includes('−2.0°C (28°F)'));
 assert(text.includes("this crop doesn't tolerate frost"));
 assert.equal(f.formatDisplayText(text),text);
 assert.equal(f.formatDisplayText('43.7 TONS / ACRE'),'44 tons/acre');
 assert.equal(f.formatDisplayText('23,000 acres and 1,000 mm; 1,000 lb/acre'), '23,000 acres and 1,000 mm; 1,000 lb/acre');
 assert.equal(f.formatDisplayText('$1,000.00–$1,500.00 per cwt'), '$1000.00–$1500.00 per cwt');
 assert.equal(f.formatDisplayText('10-15 C'),'10.0–15.0°C (50–59°F)');
 assert(f.formatDisplayText('crop tolerates about 0.5').includes('0.5'));
});

test('factor details format weighted days, drainage, and zero ideal without mutating data', () => {
 const detail={value:.8,unit:'freeze days in season',ideal:'<= 0'};
 assert.equal(f.formatFactorDetail('frost_risk',detail),'1 freeze days in season · ideal: none');
 assert.equal(detail.value,.8);
 assert.equal(detail.ideal,'<= 0');
 assert.equal(f.formatFactorDetail('drainage',{value:'Well drained',ideal:'Moderately well drained'}),'well drained · ideal: moderately well drained');
 assert.equal(f.formatGuideTitle('Chapter 6. Watermelon'),'UF/IFAS guide: Watermelon ↗');
});
