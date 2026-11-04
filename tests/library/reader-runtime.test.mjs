import test from 'node:test';import assert from 'node:assert/strict';
import {packageFixture} from './helpers.mjs';

test('opening a lesson starts independent quiz and glossary resources together, then mounts both',async()=>{
 const before={document:globalThis.document,window:globalThis.window,innerWidth:globalThis.innerWidth},scripts=[];
 class Element{constructor(tag='div'){this.tagName=tag.toUpperCase();this.dataset={};this.style={};}append(){}setAttribute(){}querySelector(){return null;}querySelectorAll(){return [];}replaceChildren(){}remove(){}}
 const window={};globalThis.window=window;globalThis.innerWidth=390;
 globalThis.document={createElement:tag=>new Element(tag),createTextNode:text=>({text}),querySelectorAll:()=>[],head:{append(s){if(s.tagName==='SCRIPT')scripts.push(s);}}};
 let reader;const mounted=[];
 const finish=async()=>{for(let round=0;round<4;round++){for(const script of scripts.filter(s=>!s.done)){script.done=true;if(String(script.src).endsWith('legacy-reader.js'))window.PsychPersonalTeaching={mountPersonalQuiz:()=>{mounted.push('quiz');return {dispose(){}};}};if(String(script.src).endsWith('legacy-glossary.js'))window.PsychPersonalGlossary={mountPersonalGlossary:()=>{mounted.push('glossary');return {dispose(){}};}};script.onload();}await new Promise(resolve=>setImmediate(resolve));}};
 try{
  const {mountReader}=await import('../../site/assets/library/reader.mjs?parallel-runtime-test');
  const revision=packageFixture().revisions[0];revision.lesson.blocks=[];revision.lesson.formulas=[];revision.lesson.visual=null;revision.lesson.quiz=null;
  reader=mountReader(new Element(),{revision});await new Promise(resolve=>setImmediate(resolve));
  assert.deepEqual(scripts.map(s=>new URL(s.src).pathname.split('/').pop()).sort(),['legacy-glossary.js','legacy-reader.js'],'Independent resources must not wait for each other');
  await finish();assert.equal(await reader.ready,true);assert.deepEqual(mounted,['quiz','glossary']);
 }finally{await finish();await reader?.ready;reader?.dispose();for(const [k,v]of Object.entries(before))if(v===undefined)delete globalThis[k];else globalThis[k]=v;}
});

test('retry after one script failure reuses its pending sibling and still mounts a reopened reader',async()=>{
 const before={document:globalThis.document,window:globalThis.window,innerWidth:globalThis.innerWidth},scripts=[],window={};
 class Element{constructor(tag='div'){this.tagName=tag.toUpperCase();this.dataset={};this.style={};}append(){}setAttribute(){}querySelector(){return null;}querySelectorAll(){return [];}replaceChildren(){}remove(){}}
 globalThis.window=window;globalThis.innerWidth=390;globalThis.document={createElement:t=>new Element(t),createTextNode:text=>({text}),querySelectorAll:()=>[],head:{append(s){if(s.tagName==='SCRIPT')scripts.push(s);}}};
 const tick=()=>new Promise(resolve=>setImmediate(resolve));let first,second;
 const revision=packageFixture().revisions[0];revision.lesson.blocks=[];revision.lesson.formulas=[];revision.lesson.visual=null;revision.lesson.quiz=null;
 const settle=async()=>{window.PsychPersonalTeaching={mountPersonalQuiz:()=>({dispose(){}})};window.PsychPersonalGlossary={mountPersonalGlossary:()=>({dispose(){}})};for(let round=0;round<3;round++){for(const s of scripts.filter(s=>!s.done)){s.done=true;s.onload();}await tick();}};
 try{
  const {mountReader}=await import('../../site/assets/library/reader.mjs?retry-script-flight-test');
  first=mountReader(new Element(),{revision});const failed=assert.rejects(first.ready,/读者交互资源未能载入/);await tick();
  const reader=scripts.find(s=>String(s.src).endsWith('legacy-reader.js'));reader.done=true;reader.onerror();await failed;
  second=mountReader(new Element(),{revision});await tick();
  assert.equal(scripts.filter(s=>String(s.src).endsWith('legacy-glossary.js')).length,1,'Retry must reuse the pending glossary flight');
  assert.equal(scripts.filter(s=>String(s.src).endsWith('legacy-reader.js')).length,2,'Only the failed script may retry');
  await settle();assert.equal(await second.ready,true);
 }finally{await settle();await first?.ready.catch(()=>{});await second?.ready.catch(()=>{});first?.dispose();second?.dispose();for(const [k,v]of Object.entries(before))if(v===undefined)delete globalThis[k];else globalThis[k]=v;}
});
