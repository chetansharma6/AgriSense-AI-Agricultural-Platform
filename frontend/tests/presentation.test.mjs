import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';

function compile(name, dependencies = {}) {
 const context = { exports: {}, Intl, require: (path) => dependencies[path] };
 const source = fs.readFileSync(new URL(`../src/lib/${name}.ts`, import.meta.url), 'utf8');
 vm.runInNewContext(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, context);
 return context.exports;
}
const f = compile('presentation', { './format': compile('format') });

test('place labels normalize FL and county suffixes without duplication', () => {
 assert.equal(f.placeLabel('Plant City, Hillsborough County, FL'), 'Plant City, Hillsborough County, Florida');
 assert.equal(f.placeLabel(null, 'Jackson'), 'Jackson County, Florida');
 assert.equal(f.placeLabel(null, 'Jackson County'), 'Jackson County, Florida');
 assert.equal(f.placeLabel('Florida'), 'Florida');
});

test('main limit follows frequency of lowest factor rather than the single worst score', () => {
 const crops = [
  {name:'Tomato',score:90,factors:{soil_ph:10,drainage:20}},
  {name:'Potato',score:89,factors:{soil_ph:90,drainage:5}},
  {name:'Watermelon',score:88,factors:{soil_ph:20,drainage:30}},
  {name:'Corn',score:87,factors:{soil_ph:50,drainage:10}},
  {name:'Peanut',score:86,factors:{soil_ph:60,drainage:10}},
 ];
 const before=JSON.stringify(crops);
 assert.equal(f.resultsSummary(crops), 'Best fits here: Tomato, Potato, Watermelon. Main limit: Drainage (average factor score 15/100 across the top 5).');
 assert.equal(JSON.stringify(crops),before);
});

test('missing factors and empty rankings produce useful summaries', () => {
 assert.match(f.resultsSummary([]), /no crop recommendations available.*factor data unavailable/);
 assert.match(f.resultsSummary([{name:'Tomato',score:null,factors:null}]), /Tomato.*factor data unavailable/);
 assert.match(f.resultsSummary([{name:'Tomato',score:50,factors:{drainage:0}}]), /average factor score 0\/100/);
});
