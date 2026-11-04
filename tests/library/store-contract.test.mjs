import test from 'node:test';
import assert from 'node:assert/strict';
const core=await import('../../site/assets/library/store.mjs').catch(()=>null);
function api(){assert.ok(core,'IndexedDB library storage is not implemented');return core;}
test('denied or absent browser persistence fails rather than claiming durable memory',async()=>{await assert.rejects(()=>api().openLibrary({environment:'qa',libraryId:'one',owner:null},{factory:null}),e=>e.code==='STORAGE_UNAVAILABLE');});
test('invalid environment and library identities never open a database',async()=>{let opened=false;const factory={open(){opened=true;throw Error('must not open');}};await assert.rejects(()=>api().openLibrary({environment:'../escape',libraryId:'one',owner:null},{factory}));assert.equal(opened,false);});
test('browser security denial becomes an explicit storage error',async()=>{await assert.rejects(()=>api().openLibrary({environment:'qa',libraryId:'one',owner:null},{factory:{open(){throw new DOMException('Denied','SecurityError');}}}),e=>e.code==='STORAGE_UNAVAILABLE');});
