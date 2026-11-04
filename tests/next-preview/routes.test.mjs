import test from 'node:test';
import assert from 'node:assert/strict';
import {classifyHref} from '../../site/next-preview/lib/routes.mjs';
const ctx={basePath:'/psy-stats',legacyOrigin:'http://127.0.0.1:8765/psy-stats/',page:'terms/sem.html'};
test('resolves relative migrated route without duplicated base path',()=>{
 assert.equal(classifyHref('../index.html?topic=regression',ctx).href,'/psy-stats/?topic=regression');
 assert.equal(classifyHref('variable.html#plain',ctx).href,'/psy-stats/terms/variable/#plain');
 assert.equal(classifyHref('/psy-stats/terms/sem/',ctx).kind,'preview');
});
test('keeps legacy pages and downloads on their real destinations',()=>{
 assert.equal(classifyHref('p-value.html',ctx).href,'http://127.0.0.1:8765/psy-stats/terms/p-value.html');
 assert.equal(classifyHref('../practice.html',ctx).kind,'legacy');
 assert.equal(classifyHref('../analysis-code/sem.R',ctx).kind,'download');
 assert.equal(classifyHref('#formula',ctx).kind,'anchor');
 assert.equal(classifyHref('https://example.org/sem.html',ctx).kind,'external');
});
