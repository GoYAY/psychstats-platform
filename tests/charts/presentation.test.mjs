import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {validatePackage} from '../../site/assets/library/contract.mjs';
import {packageFixture} from '../library/helpers.mjs';
import {personalBarData} from '../../site/assets/charts/data.mjs';
let validate;
try{({validatePresentation:validate}=await import('../../site/assets/charts/presentation.mjs'));}catch(e){if(e.code!=='ERR_MODULE_NOT_FOUND')throw e;}
const vectors=JSON.parse(await readFile(new URL('../fixtures/visual-presentation.json',import.meta.url),'utf8'));
test('shared vectors enforce explicit policies and keep original input',()=>{
 assert.equal(typeof validate,'function','Executable presentation validator missing');
 for(const c of vectors.cases){const v=structuredClone(vectors.visuals[c.base]);if('presentation'in c)v.presentation=structuredClone(c.presentation);if(c.override_payload)v.payload=structuredClone(c.override_payload);const before=structuredClone(v);
  if(c.ok){const actual=validate(v,{required:!!c.required});assert.deepEqual(actual,c.presentation??null,c.name);if(actual)actual.focus='changed';}
  else assert.throws(()=>validate(v,{required:!!c.required}),undefined,c.name);
  assert.deepEqual(v,before,c.name);
 }
});
test('real import accepts new metadata but still rejects unknown executable fields',()=>{
 const p=packageFixture(),v=structuredClone(vectors.visuals.bar1);Object.assign(v,{title:'教学图',alt:'人数',takeaway:'甲乙对照',origin:'teaching',refs:[],presentation:{version:1,focus:'local',numeric_role:'exact',layout:'single',interaction:'inspect'}});p.revisions[0].lesson.visual=v;
 const validated=validatePackage(p);assert.deepEqual(validated.revisions[0].lesson.visual.presentation,v.presentation);
 v.presentation.js='alert(1)';assert.throws(()=>validatePackage(p));delete v.presentation.js;v.presentation.version=2;assert.throws(()=>validatePackage(p));
});
test('new inspect bounds mirror the actual adapter, legacy fallback remains',()=>{
 const base=structuredClone(vectors.visuals.bar1);base.presentation={version:1,focus:'local',numeric_role:'exact',layout:'single',interaction:'inspect'};
 assert.ok(personalBarData(base));
 for(const [key,limit]of [['title',120],['takeaway',400],['alt',1000]]){const v=structuredClone(base);v[key]='字'.repeat(limit+1);assert.throws(()=>validate(v));assert.equal(personalBarData(v),null);}
 for(const x of [[1,'1'],[1e-6,'0.000001']]){const v=structuredClone(base);v.payload.series[0].x=x;assert.throws(()=>validate(v));}
});
