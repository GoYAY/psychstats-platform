import test from 'node:test';
// Online deliveries retain internal per-document read offsets, not visible quotes.
test('online document readings survive strict package import validation',async()=>{
 const {validatePackage}=await import('../../site/assets/library/contract.mjs');
 const p=packageFixture(),value=[{source_id:'s1',original_sha256:'a'.repeat(64),handled_sections:1,total_sections:1,source_mapping:[]}];
 p.revisions[0].provenance.document_readings=value;p.revisions[0].lesson.provenance.document_readings=value;
 assert.equal(validatePackage(p,new Map(),{catalogue:[]}).revisions[0].provenance.document_readings.length,1);
});
import assert from 'node:assert/strict';
import {packageFixture} from './helpers.mjs';
test('source-located English display metadata and new percent semantics import without weakening strict fields',()=>{
 const p=packageFixture(),l=p.revisions[0].lesson;
 const identity={en:'Sample',basis:'source_located_model_mapping',refs:[{source_id:'s1',start:0,end:6}]};
 l.provenance.verified_identity=identity;l.provenance.original_anchor=structuredClone(l.term);
 p.revisions[0].provenance=structuredClone(l.provenance);
 assert.equal(core.validatePackage(p,new Map(),{catalogue:[]}).revisions[0].lesson.provenance.verified_identity.en,'Sample');
 l.provenance.unreviewedExtra=true;assert.throws(()=>core.validatePackage(p,new Map(),{catalogue:[]}));
});
const core=await import('../../site/assets/library/contract.mjs').catch(()=>null);
function api(){assert.ok(core,'Library package validation is not implemented');return core;}
test('valid private package keeps its original scope and pending review',()=>{const p=packageFixture();const v=api().validatePackage(p,new Map(),{catalogue:[]});assert.equal(v.revisions[0].lesson.provenance.human_scientific_review,'pending');assert.equal(v.sources[0].originalStatus,'missing');});
test('unsupported versions and missing source references fail closed',()=>{for(const edit of [p=>p.schemaVersion=2,p=>p.revisions[0].sourceIds=['unknown'],p=>p.revisions[0].assetIds=['unknown'],p=>p.revisions[0].lesson.blocks[0].paragraphs[0].refs[0].end=999]){const p=packageFixture();edit(p);assert.throws(()=>api().validatePackage(p,new Map(),{catalogue:[]}));}});
test('same Chinese names with different identities are not merged',()=>{const p=packageFixture();p.terms.push({...p.terms[0],id:'another-sample',currentRevisionId:null});const v=api().validatePackage(p,new Map(),{catalogue:[]});assert.equal(v.terms.length,2);});
test('metadata URLs and nested credentials cannot become trusted content',()=>{for(const edit of [p=>p.works[0].url='javascript:alert(1)',p=>p.revisions[0].provenance.api_key='do-not-export',p=>p.extra={password:'hidden'}]){const p=packageFixture();edit(p);assert.throws(()=>api().validatePackage(p,new Map(),{catalogue:[]}));}});
test('complete terms win over embedded shorter words',()=>{const result=api().resolveTermRef('潜变量',[{id:'variable',zh:'变量',kind:'classic',aliases:[]}]);assert.equal(result.ref,null);assert.equal(result.candidates.length,0);});
test('ambiguous alias returns candidates instead of choosing a term',()=>{const result=api().resolveTermRef('TIRT',[{id:'one',zh:'方法一',aliases:['TIRT'],kind:'personal'},{id:'two',zh:'方法二',aliases:['TIRT'],kind:'personal'}]);assert.equal(result.ref,null);assert.equal(result.candidates.length,2);});
test('unknown personal relation targets remain addressable without a fake page',()=>{const p=packageFixture();p.edges=[{id:'edge-demo',from:{space:'personal',id:'sample'},to:{space:'personal',id:'future-term'},type:'next',reason:'有依据的关联',refs:[{source_id:'s1',start:0,end:10}],status:'suggested',origin:'model',revisionId:'rev-demo'}];assert.equal(api().validatePackage(p,new Map(),{catalogue:[]}).edges[0].to.id,'future-term');});
test('formula macros cannot smuggle HTML or executable links into readers',()=>{const p=packageFixture();p.revisions[0].lesson.formulas=[{latex:'\\href{javascript:alert(1)}{x}',symbols:[],refs:[]}];assert.throws(()=>api().validatePackage(p,new Map(),{catalogue:[]}));});
