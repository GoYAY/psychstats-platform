import test from 'node:test';
import assert from 'node:assert/strict';
const core=await import('../../site/assets/library/safe-assets.mjs').catch(()=>null);
function api(){assert.ok(core,'Safe private asset validation is not implemented');return core;}
test('byte fingerprints match a hand-checked SHA256 value',async()=>{assert.equal(await api().sha256(new TextEncoder().encode('abc')),'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad');});
test('PDF bytes cannot disguise themselves as a PNG',async()=>{await assert.rejects(()=>api().safeAsset(new TextEncoder().encode('%PDF-1.7\nexample'),{mime:'image/png',path:'assets/a.png'}));});
test('supported PDF receives a real fingerprint and keeps its MIME',async()=>{const value=await api().safeAsset(new TextEncoder().encode('%PDF-1.7\nexample'),{mime:'application/pdf',path:'originals/a.pdf'});assert.equal(value.mime,'application/pdf');assert.equal(value.hash.length,64);});
test('path traversal and arbitrary executables are rejected',async()=>{for(const path of ['../outside.pdf','assets/../../a.pdf','assets/a.js','C:/outside.pdf'])await assert.rejects(()=>api().safeAsset(new TextEncoder().encode('%PDF-1.7'),{mime:'application/pdf',path}));});
