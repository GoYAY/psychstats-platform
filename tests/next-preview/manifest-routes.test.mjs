import test from 'node:test';
import assert from 'node:assert/strict';
import {parseView} from '../../site/next-preview/lib/view-state.mjs';
import {classifyHref} from '../../site/next-preview/lib/routes.mjs';
const manifest={pages:{index:{canonicalPath:'/psy-stats/',aliases:[{path:'/psy-stats/index.html'}]},'term:sem':{canonicalPath:'/psy-stats/terms/sem/',aliases:[{path:'/psy-stats/terms/sem.html'}]}}};
test('manifest route resolves old html details and topic query to the same view',()=>{
 assert.deepEqual(parseView('https://example.org/psy-stats/terms/sem.html#formula',manifest),{key:'term:sem',topic:'foundations',hash:'#formula'});
 assert.deepEqual(parseView('https://example.org/psy-stats/index.html?topic=favorites',manifest),{key:'index',topic:'favorites',hash:''});
 assert.equal(parseView('https://example.org/psy-stats/terms/missing.html',manifest),null);
});
test('same-origin absolute and relative migrated links preserve query and hash',()=>{
 const ctx={manifest,page:'terms/sem.html',origin:'https://example.org'};
 assert.equal(classifyHref('../index.html?topic=regression',ctx).href,'/psy-stats/index.html?topic=regression');
 assert.equal(classifyHref('https://example.org/psy-stats/terms/sem.html#formula',ctx).kind,'preview');
 assert.equal(classifyHref('https://other.org/psy-stats/terms/sem.html',ctx).kind,'external');
});
