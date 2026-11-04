import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';import vm from 'node:vm';
test('ordinary public page never imports library implementation or opens storage',()=>{
 const path='site/assets/library-runtime.js';assert.ok(fs.existsSync(path),'Small library lifecycle adapter missing');
 let mount;const window={PsychPageRuntime:{register:(name,fn)=>mount=fn}},document={currentScript:{src:'https://example.com/psy/assets/library-runtime.js',dataset:{libraryModule:'library/app.mjs'}}};
 vm.runInNewContext(fs.readFileSync(path,'utf8'),{window,document,URL});assert.equal(typeof mount,'function');assert.deepEqual(Object.keys(mount({main:{querySelector:()=>null}})),[]);
});
