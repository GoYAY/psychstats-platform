import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';

let api;
try {api=await import('../../site/assets/charts/data.mjs');}catch(e){if(e.code!=='ERR_MODULE_NOT_FOUND')throw e;api={};}
const official=JSON.parse(await readFile(new URL('../../site/content/plain_visuals/foundations.json',import.meta.url)))['central-tendency-and-dispersion'];
const personal=()=>({kind:'statistical',origin:'teaching',title:'睡眠记录的频数',alt:'三个睡眠时长类别',takeaway:'7小时人数最多',payload:{chart_type:'bar',x_label:'睡眠时长',x_unit:'小时',y_label:'频数',y_unit:'人',series:[{label:'学生',x:['6','7','8'],y:[0,6,4]}]}});
test('explicit none and facets stay static; invalid intent never becomes legacy',()=>{
 const v=personal();v.presentation={version:1,focus:'local',numeric_role:'exact',layout:'single',interaction:'none'};
 assert.equal(api.personalBarData(v),null);
 v.presentation.interaction='inspect';assert.deepEqual(api.personalBarData(v).series[0].points.map(p=>p.value),[0,6,4]);
 v.presentation.version=2;assert.equal(api.personalBarData(v),null);
 v.presentation=null;assert.equal(api.personalBarData(v),null);
 v.presentation={version:1,focus:'whole',numeric_role:'relative',layout:'facets',interaction:'none'};v.payload.series.push(structuredClone(v.payload.series[0]));assert.equal(api.personalBarData(v),null);
});
test('real official counts, zeros and weighted means survive without modifying source',()=>{
 assert.equal(typeof api.officialBarData,'function','official adapter not implemented');
 const before=JSON.stringify(official),data=api.officialBarData(official);
 assert.equal(data.series.length,2);
 assert.deepEqual(data.series[0].points.map(p=>p.value),[0,0,0,2,6,2,0,0,0]);
 assert.deepEqual(data.series[1].points.map(p=>p.value),[2,0,2,0,2,0,2,0,2]);
 for(const s of data.series){assert.equal(s.points.length,9);assert.equal(s.points.reduce((n,p)=>n+p.value,0),10);assert.equal(s.points.reduce((n,p)=>n+Number(p.category)*p.value,0),800);}
 assert.deepEqual(data.reference,{value:80,label:'两班均分80分'});assert.equal(JSON.stringify(official),before);
});
test('personal projection keeps original units and zero values, drops private or executable fields',()=>{
 assert.equal(typeof api.personalBarData,'function','personal adapter not implemented');
 const source=personal();source.refs=[{quote:'private evidence'}];source.payload.url='javascript:alert(1)';source.payload.series[0].id='model-id';
 const result=api.personalBarData(source);
 assert.equal(result.xLabel,'睡眠时长（小时）');assert.equal(result.yLabel,'频数（人）');
 assert.deepEqual(result.series[0],{id:'s0',label:'学生',points:[{category:'6',value:0},{category:'7',value:6},{category:'8',value:4}]});
 assert.ok(!JSON.stringify(result).includes('private'));assert.ok(!JSON.stringify(result).includes('javascript'));assert.ok(!JSON.stringify(result).includes('model-id'));
});
test('reject unsupported graphics and invalid arrays rather than fabricate observations',()=>{
 assert.equal(typeof api.personalBarData,'function');
 for(const kind of ['story','line','scatter','histogram']){const p=personal();if(kind==='story')p.kind=kind;else p.payload.chart_type=kind;assert.equal(api.personalBarData(p),null);}
 const mutations=[p=>p.payload.series[0].x.push('9'),p=>p.payload.series[0].x[1]='6',p=>p.payload.series[0].y[0]=-1,p=>p.payload.series[0].y[0]=true,p=>p.payload.series[0].y[0]=Infinity,p=>p.payload.series[0].y[0]=NaN,p=>p.payload.series[0].x[0]='长'.repeat(25),p=>p.payload.series=Array(5).fill(p.payload.series[0]),p=>{p.payload.series[0].x=Array.from({length:201},(_,i)=>String(i));p.payload.series[0].y=Array(201).fill(1);},p=>p.payload.series.push({label:'第二组',x:['6','8','9'],y:[1,2,3]})];
 for(const mutate of mutations){const p=personal();mutate(p);assert.equal(api.personalBarData(p),null);}
});
test('host validation rejects invalid or unaligned categories and isolates unknown fields',()=>{
 assert.equal(typeof api.validateBarData,'function');
 const base={version:1,title:'图',xLabel:'类别',yLabel:'人数',note:'教学',series:[{id:'x',label:'组',points:[{category:'甲',value:0}]}]};
 for(const mutate of [p=>p.series[0].points[0].value=false,p=>p.series[0].points.push({category:'甲',value:1}),p=>p.series[0].points[0].category='',p=>p.title='长'.repeat(121)]){const p=structuredClone(base);mutate(p);assert.equal(api.validateBarData(p),null);}
 base.quote='secret';base.series[0].html='<script>';
 assert.deepEqual(api.validateBarData(base),{version:1,title:'图',xLabel:'类别',yLabel:'人数',note:'教学',series:[{id:'s0',label:'组',points:[{category:'甲',value:0}]}]});
});
