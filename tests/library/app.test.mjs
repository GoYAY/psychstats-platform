import test from 'node:test';import assert from 'node:assert/strict';
import {parseLibraryRoute,libraryContext} from '../../site/assets/library/app.mjs';
test('private routes carry stable identities, malformed routes stay local list',()=>{
 assert.deepEqual(parseLibraryRoute('#term=cognitive-drift'),{view:'term',id:'cognitive-drift',block:null});
 assert.equal(parseLibraryRoute('#term=%3Cscript%3E').view,'list');assert.equal(parseLibraryRoute('#view=works').view,'works');
 assert.equal(parseLibraryRoute('#view=generate').view,'generate');
});
test('same origin production and test path libraries are independent',async()=>{
 const a=await libraryContext('https://example.com/psy-stats/','local-library-preview'),b=await libraryContext('https://example.com/psy-stats-test/','local-library-preview');assert.notEqual(a.environment,b.environment);assert.equal(a.owner,null);
});
