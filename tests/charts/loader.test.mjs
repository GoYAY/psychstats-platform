import test from 'node:test';import assert from 'node:assert/strict';
let api;try{api=await import('../../site/assets/charts/loader.mjs');}catch(e){if(e.code!=='ERR_MODULE_NOT_FOUND')throw e;api={};}
// Minimal DOM boundary; lifecycle is exercised with actual browser/React in CDP.
class Element{
 constructor(){this.children=[];this.style={};this.dataset={};this.isConnected=true;this.attrs=new Map();this.ownerDocument={createElement:()=>new Element()};}
 append(x){this.children.push(x);x.parent=this;}remove(){if(this.parent)this.parent.children=this.parent.children.filter(x=>x!==this);}setAttribute(k,v){this.attrs.set(k,v);}removeAttribute(k){this.attrs.delete(k);}getBoundingClientRect(){return{width:500,height:400,top:0,bottom:400};}querySelector(){return null;}
}
const data={version:1,title:'图',xLabel:'类别',yLabel:'频数',note:'教学',series:[{label:'组',points:[{category:'甲',value:0}]}]};
test('missing module leaves static region intact and resolves false',async()=>{
 assert.equal(typeof api.enhanceChart,'function','loader missing');const el=new Element();
 const chart=api.enhanceChart(el,{data,moduleURL:new URL('./missing-widget.mjs',import.meta.url).href});
 assert.equal(el.style.visibility,undefined);assert.equal(await chart.ready,false);assert.equal(el.children.length,0);chart.dispose();chart.dispose();
});
test('aborted or invalid enhancement cannot hide static content or mount',async()=>{
 assert.equal(typeof api.enhanceChart,'function');const controller=new AbortController();controller.abort();
 for(const value of [data,{...data,series:[]}]){const el=new Element();const chart=api.enhanceChart(el,{data:value,moduleURL:'file:///not-present.mjs',signal:controller.signal});assert.equal(await chart.ready,false);assert.equal(el.children.length,0);assert.equal(chart.capture().selectedCategory,null);}
});
test('pending observer preserves validated selection over two rapid returns',async()=>{
 const before=globalThis.IntersectionObserver;globalThis.IntersectionObserver=class{observe(){}disconnect(){}};
 try{
  let state={selectedCategory:'甲'};
  for(let i=0;i<2;i++){const chart=api.enhanceChart(new Element(),{data,moduleURL:'file:///unused.mjs',state});state=chart.capture();assert.deepEqual(state,{selectedCategory:'甲'});chart.dispose();assert.deepEqual(chart.capture(),state);}
  const invalid=api.enhanceChart(new Element(),{data,moduleURL:'file:///unused.mjs',state:{selectedCategory:'unknown'}});assert.deepEqual(invalid.capture(),{selectedCategory:null});invalid.dispose();
 }finally{if(before===undefined)delete globalThis.IntersectionObserver;else globalThis.IntersectionObserver=before;}
});
