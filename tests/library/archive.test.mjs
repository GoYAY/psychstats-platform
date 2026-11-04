import test from 'node:test';
import assert from 'node:assert/strict';
import {zipSync,strToU8} from '../../site/assets/vendor/fflate/fflate.mjs';
import {packageFixture} from './helpers.mjs';
import {NodeWebWorker} from './node-web-worker.mjs';
const guards=await import('../../site/assets/library/archive-guards.mjs').catch(()=>null),archive=await import('../../site/assets/library/archive.mjs').catch(()=>null);
function api(){assert.ok(guards,'ZIP guards are not implemented');return guards;}
function plans(){assert.ok(archive,'Backup restore planning is not implemented');return archive;}
const empty=()=>({version:0,records:Object.fromEntries(['terms','revisions','works','sources','evidence','edges','annotations','assets'].map(k=>[k,[]]))});
function apply(snapshot,plan){const copy=structuredClone(snapshot);for(const w of plan.writes){copy.records[w.kind]=copy.records[w.kind].filter(r=>r.id!==w.id);copy.records[w.kind].push(w.value);}return copy;}
test('limits allow each exact boundary and reject the next unit without allocating it',()=>{
 const g=api();assert.doesNotThrow(()=>g.checkLimits({compressed:268435456,expanded:1073741824,file:134217728,files:10000}));
 for(const value of [{compressed:268435457},{expanded:1073741825},{file:134217729},{files:10001}])assert.throws(()=>g.checkLimits(value),e=>e.code==='LIMIT');
});
test('CRC32 matches an independently known check value',()=>{assert.equal(api().crc32(strToU8('123456789')),0xcbf43926);});

test('a saved UTF-8 original survives backup as text rather than invalid PDF',async()=>{
 const previous=globalThis.Worker;globalThis.Worker=NodeWebWorker;
 try{
 const p=packageFixture(),hash='2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824';
 p.sources[0].blobHash=hash;p.sources[0].fileName='paper.txt';p.sources[0].originalStatus='saved';
 const records=Object.fromEntries(Object.entries(p).filter(([,v])=>Array.isArray(v)));
 const blob=await plans().exportBackup({version:1,records},async()=>new Blob(['hello'],{type:'text/plain'}));
 const {unzipSync,strFromU8}=await import('../../site/assets/vendor/fflate/fflate.mjs');const files=unzipSync(new Uint8Array(await blob.arrayBuffer()));
 assert.ok(files['originals/'+hash+'.txt']);assert.equal(strFromU8(files['originals/'+hash+'.txt']),'hello');
 }finally{globalThis.Worker=previous;}
});
test('central directory identifies regular files and rejects unsafe paths',async()=>{
 const bytes=zipSync({'a.txt':strToU8('hello')});const rows=await api().readDirectory(new Blob([bytes]));assert.equal(rows.length,1);assert.equal(rows[0].name,'a.txt');assert.equal(rows[0].size,5);assert.equal(rows[0].crc,0x3610a686);
 for(const name of ['../a.txt','a/../../b.txt','nested.zip'])await assert.rejects(()=>api().readDirectory(new Blob([zipSync({[name]:strToU8('x')})])));
});
test('explicit visual intent survives actual worker export and import unchanged',async()=>{
 const previous=globalThis.Worker;globalThis.Worker=NodeWebWorker;
 try{
  const p=packageFixture(),policy={version:1,focus:'local',numeric_role:'exact',layout:'single',interaction:'inspect'};
  p.revisions[0].lesson.visual={kind:'statistical',title:'人数',alt:'两类人数',takeaway:'乙类较多',origin:'teaching',refs:[],presentation:policy,payload:{chart_type:'bar',x_label:'类别',y_label:'人数',series:[{label:'学生',x:['甲','乙'],y:[2,3]}]}};
  const records=Object.fromEntries(Object.entries(p).filter(([,v])=>Array.isArray(v))),blob=await plans().exportBackup({version:1,records},async()=>null),staged=new Map();
  const inspected=await plans().inspectBackup(blob,{stageBlob:async(h,b)=>{staged.set(h,b);return h;},discardStaged:async()=>staged.clear()});
  assert.deepEqual(inspected.validated.revisions[0].lesson.visual.presentation,policy);
 }finally{globalThis.Worker=previous;}
});
test('central symlinks, duplicate names and corrupt endings are rejected',async()=>{
 const bytes=zipSync({'a.txt':strToU8('x')});const offset=bytes.findIndex((v,i)=>v===0x50&&bytes[i+1]===0x4b&&bytes[i+2]===1&&bytes[i+3]===2);const link=bytes.slice();new DataView(link.buffer).setUint32(offset+38,0xa0000000,true);await assert.rejects(()=>api().readDirectory(new Blob([link])));
 await assert.rejects(()=>api().readDirectory(new Blob([bytes.subarray(0,bytes.length-15)])));
 const pair=zipSync({'a.txt':strToU8('x'),'b.txt':strToU8('y')});for(let i=0;i<pair.length-4;i++)if(pair[i]===98&&pair[i+1]===46&&pair[i+2]===116&&pair[i+3]===120&&pair[i+4]===116)pair[i]=97;
 await assert.rejects(()=>api().readDirectory(new Blob([pair])));
});
test('unchanged restore is a no-op and importing a new package writes five records',async()=>{
 const p=packageFixture();const newPlan=await plans().planRestore(empty(),p);assert.equal(newPlan.writes.length,5);
 const snapshot=apply(empty(),newPlan);assert.equal((await plans().planRestore(snapshot,p)).writes.length,0);
});
test('same-ID conflicts retain a coherent foreign branch and remain idempotent',async()=>{
 const p=packageFixture(),snapshot=apply(empty(),await plans().planRestore(empty(),p)),changed=structuredClone(p);changed.terms[0].zh='另一含义的样本';
 const plan=await plans().planRestore(snapshot,changed);const term=plan.writes.find(w=>w.kind==='terms').value,revision=plan.writes.find(w=>w.kind==='revisions').value,evidence=plan.writes.find(w=>w.kind==='evidence').value;
 assert.notEqual(term.id,'sample');assert.equal(term.currentRevisionId,revision.id);assert.equal(revision.termId,term.id);assert.equal(evidence.revisionId,revision.id);
 const restored=apply(snapshot,plan);assert.equal(restored.records.terms.length,2);assert.equal((await plans().planRestore(restored,changed)).writes.length,0);
});
test('cancelled inspections and exports never start background work',async()=>{const controller=new AbortController();controller.abort();assert.equal(typeof plans().inspectBackup,'function');assert.equal(typeof plans().exportBackup,'function');await assert.rejects(()=>plans().inspectBackup(new Blob(),{signal:controller.signal}),e=>e.code==='CANCELLED');await assert.rejects(()=>plans().exportBackup(empty(),()=>null,{signal:controller.signal}),e=>e.code==='CANCELLED');});
