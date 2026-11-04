import test from 'node:test';import assert from 'node:assert/strict';
const api=await import('../../site/next-preview/lib/reading-layout.mjs').catch(()=>({}));
test('reading layout restores known heights only at matching width and captures observed dimensions',()=>{
 assert.equal(typeof api.mountReadingLayout,'function');const previous=globalThis.ResizeObserver,css=globalThis.CSS;let notify,disconnected=false;
 globalThis.CSS={supports:()=>true};globalThis.ResizeObserver=class{constructor(fn){notify=fn}observe(){}disconnect(){disconnected=true}};
 try{const blocks=[{style:{}},{style:{}}],root={querySelectorAll:()=>blocks};const saved={viewport:1440,sizes:[400,900]};
 const first=api.mountReadingLayout(root,{saved,viewportWidth:1440});assert.equal(blocks[1].style.containIntrinsicBlockSize,'auto 900px');notify([{target:blocks[0],contentRect:{height:450},borderBoxSize:[{blockSize:472}]}]);assert.equal(first.capture().sizes[0],450);first.dispose();assert.equal(disconnected,true);
 const mobile=[{style:{}}];const second=api.mountReadingLayout({querySelectorAll:()=>mobile},{saved,viewportWidth:390});assert.equal(mobile[0].style.containIntrinsicBlockSize,undefined);second.dispose();
 }finally{globalThis.ResizeObserver=previous;globalThis.CSS=css;}
});
