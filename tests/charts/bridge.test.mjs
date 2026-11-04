import test from 'node:test';import assert from 'node:assert/strict';import vm from 'node:vm';import {readFile} from 'node:fs/promises';
test('official bridge preserves saved state before loader import resolves',async()=>{
 const code=await readFile(new URL('../../site/assets/chart-runtime.js',import.meta.url),'utf8');let register;
 const data={series:[{points:[{category:'甲',value:2}]}]},node={dataset:{instantChart:'one',chartData:JSON.stringify(data)}};
 const context={URL,window:{PsychPageRuntime:{register:(name,fn)=>register=fn}},document:{currentScript:{src:'https://local.test/assets/chart-runtime.js',dataset:{chartLoader:'loader.mjs',chartModule:'widget.mjs'}}}};
 const script=new vm.Script(code,{importModuleDynamically:()=>new Promise(()=>{})});script.runInNewContext(context);
 const life=register({main:{querySelectorAll:()=>[node]},signal:new AbortController().signal,state:{one:{selectedCategory:'甲'}}});
 assert.deepEqual(JSON.parse(JSON.stringify(life.capture())),{one:{selectedCategory:'甲'}});life.dispose();assert.deepEqual(JSON.parse(JSON.stringify(life.capture())),{one:{selectedCategory:'甲'}});
});
