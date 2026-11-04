import test from 'node:test';
import assert from 'node:assert/strict';
import {packageFixture} from './helpers.mjs';
import {readerProjection,wordTokens,mountReader} from '../../site/assets/library/reader.mjs';

test('one reader compiles term names once across paragraphs and preserves complete-word protection',async()=>{
 const {createWordTokenizer}=await import('../../site/assets/library/reader.mjs');assert.equal(typeof createWordTokenizer,'function');
 let reads=0;const catalogue=Array.from({length:200},(_,i)=>({zh:'其他术语'+i,get aliases(){reads++;return [];}}));catalogue.push({zh:'潜变量'});
 const tokenize=createWordTokenizer([{id:'v',term:'变量'},{id:'i',term:'IRT'}],catalogue,{zh:'潜变量'});
 for(const text of ['潜变量与变量。','DIRT IRT IRTests。','第二段变量。']){
  const out=tokenize(text,'plain_explanation');assert.equal(out.map(t=>t.text).join(''),text);
 }
 assert.equal(reads,200,'Paragraphs must reuse the same term-name index');
 assert.deepEqual(tokenize('潜变量与变量。','plain_explanation').filter(t=>t.note).map(t=>[t.text,t.note]),[['变量','v']]);
 assert.deepEqual(tokenize('DIRT IRT IRTests。','plain_explanation').filter(t=>t.note).map(t=>t.text),['IRT']);
 assert.deepEqual(tokenize('变量','academic_expression'),[{text:'变量'}]);
});
test('static intent projects only allowed metadata and discards pending chart selection, not quiz',async()=>{
 const revision=packageFixture().revisions[0];revision.lesson.visual={kind:'statistical',origin:'teaching',title:'频数',alt:'图',takeaway:'甲类2人',presentation:{version:1,focus:'local',numeric_role:'exact',layout:'single',interaction:'none'},payload:{chart_type:'bar',x_label:'类别',y_label:'人数',series:[{label:'组',x:['甲'],y:[2]}]}};
 const view=readerProjection(revision);assert.equal(view.visual.interactiveData,null);assert.deepEqual(view.visual.presentation,revision.lesson.visual.presentation);assert.notEqual(view.visual.presentation,revision.lesson.visual.presentation);
 const before={document:globalThis.document,innerWidth:globalThis.innerWidth};class Element{constructor(){this.dataset={};this.style={};}append(){}setAttribute(){}}
 globalThis.document={createElement:()=>new Element(),createTextNode:text=>({text})};globalThis.innerWidth=390;
 try{let release;const pending=new Promise(r=>release=r);const reader=mountReader(new Element(),{revision,resolveAsset:()=>pending,state:{selected:'d',chart:{selectedCategory:'甲'}}});assert.deepEqual(reader.capture(),{selected:'d',chart:null});reader.dispose();release(null);assert.equal(await reader.ready,false);}finally{for(const [k,v]of Object.entries(before))if(v===undefined)delete globalThis[k];else globalThis[k]=v;}
});
test('reader projects teaching only, preserving four distinct feedbacks',()=>{
 const p=packageFixture();p.revisions[0].lesson.glossary=[{id:'g',term:'样本',explanation:'说明',refs:[{excerpt:'PRIVATE'}]}];
 const view=readerProjection(p.revisions[0],p.sources,p.works);
 assert.equal(view.quiz.options.length,4);assert.equal(view.sources[0],'教学文献');
 assert.ok(!JSON.stringify(view).includes('source_id'));assert.ok(!JSON.stringify(view).includes('PRIVATE'));assert.equal(view.glossary[0].explanation,'说明');
});
test('longest complete terms and current term protect internal short names',()=>{
 const notes=[{id:'g',term:'变量',explanation:'属性'},{id:'l',term:'载荷',explanation:'强度'}];
 const tokens=wordTokens('潜变量和变量、载荷。','detailed_explanation',notes,[{zh:'潜变量'}],{zh:'潜变量'});
 assert.deepEqual(tokens.filter(t=>t.note).map(t=>t.text),['变量','载荷']);
 for(const id of ['real_question','academic_expression','quiz'])assert.equal(wordTokens('变量',id,notes,[],{}).filter(t=>t.note).length,0);
});
test('English aliases use full boundaries and ambiguity stays plain',()=>{
 const notes=[{id:'a',term:'IRT',explanation:'one'},{id:'b',term:'SEM',explanation:'two'},{id:'c',term:'SEM',explanation:'three'}];
 assert.deepEqual(wordTokens('DIRT IRT IRTests SEM','plain_explanation',notes,[],{}).filter(t=>t.note).map(t=>t.text),['IRT']);
});
test('reader projects safe bar data without evidence and keeps unsupported visuals static',()=>{
 const p=packageFixture(),lesson=p.revisions[0].lesson;
 lesson.visual={kind:'statistical',origin:'teaching',title:'睡眠频数',alt:'人数',takeaway:'7小时最多',refs:[{excerpt:'PRIVATE'}],payload:{chart_type:'bar',x_label:'时长',x_unit:'小时',y_label:'频数',y_unit:'人',series:[{label:'学生',x:['6','7','8'],y:[0,6,4]}]}};
 const view=readerProjection(p.revisions[0],p.sources,p.works);
 assert.deepEqual(view.visual.interactiveData?.series[0].points,[{category:'6',value:0},{category:'7',value:6},{category:'8',value:4}]);
 assert.ok(!JSON.stringify(view).includes('PRIVATE'));
 lesson.visual.payload.chart_type='scatter';assert.equal(readerProjection(p.revisions[0]).visual.interactiveData,null);
});
test('reader retains quiz and chart state while selected asset is still loading',async()=>{
 const before={document:globalThis.document,innerWidth:globalThis.innerWidth};
 class Element{constructor(){this.dataset={};this.style={};}append(){}setAttribute(){}querySelector(){return null;}}
 globalThis.document={createElement:()=>new Element(),createTextNode:text=>({text})};globalThis.innerWidth=390;
 try{
  const revision=packageFixture().revisions[0];revision.lesson.visual={kind:'statistical',origin:'teaching',title:'频数',alt:'图',takeaway:'甲类有2人。',payload:{chart_type:'bar',x_label:'类别',y_label:'人数',series:[{label:'组',x:['甲'],y:[2]}]}};
  let saved={selected:'d',chart:{selectedCategory:'甲'}};
  for(let i=0;i<2;i++){
   let release;const pending=new Promise(resolve=>release=resolve),reader=mountReader(new Element(),{revision,resolveAsset:()=>pending,state:saved});
   saved=reader.capture();assert.deepEqual(saved,{selected:'d',chart:{selectedCategory:'甲'}});reader.dispose();release(null);assert.equal(await reader.ready,false);
  }
 }finally{for(const [key,value] of Object.entries(before))if(value===undefined)delete globalThis[key];else globalThis[key]=value;}
});
