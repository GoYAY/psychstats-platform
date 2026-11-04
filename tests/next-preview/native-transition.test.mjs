import test from 'node:test';import assert from 'node:assert/strict';
const api=await import('../../site/next-preview/lib/native-transition.mjs').catch(()=>({}));
test('asynchronous API refusal still commits once and cleans owned names',async()=>{
 let commits=0;const source={style:{}},document={documentElement:{dataset:{}},startViewTransition:()=>({ready:Promise.reject(Error('refused')),finished:Promise.reject(Error('refused')),skipTransition(){}})};
 const motion=api.runNativeTransition({document,source,kind:'cover',commit:()=>commits++});await motion.finished;assert.equal(commits,1);assert.equal(source.style.viewTransitionName,'');assert.equal(document.documentElement.dataset.psychTransition,undefined);
});
test('unsupported and reduced motion commit once without temporary names',async()=>{
 assert.equal(typeof api.runNativeTransition,'function');for(const reduced of [false,true]){let commits=0;const source={style:{}},document={documentElement:{dataset:{}},startViewTransition:reduced?()=>{throw Error('must not use')}:undefined};const motion=api.runNativeTransition({document,source,commit:()=>commits++,reduced});await motion.finished;assert.equal(commits,1);assert.equal(source.style.viewTransitionName,undefined);}
});
test('shared element names are unique across commit and released when finished',async()=>{
 assert.equal(typeof api.runNativeTransition,'function');const source={style:{}},target={style:{}},dataset={};let commits=0,finish;
 const document={documentElement:{dataset},startViewTransition:update=>{assert.equal(source.style.viewTransitionName,'psych-morph');const updateCallbackDone=Promise.resolve().then(update);return {updateCallbackDone,ready:updateCallbackDone,finished:updateCallbackDone.then(()=>new Promise(r=>finish=r)),skipTransition(){finish?.();}};}};
 const motion=api.runNativeTransition({document,kind:'expand',source,commit:()=>{commits++;assert.equal(source.style.viewTransitionName,'');},target:()=>target});await motion.ready;assert.equal(commits,1);assert.equal(target.style.viewTransitionName,'psych-morph');finish();await motion.finished;assert.equal(target.style.viewTransitionName,'');assert.equal(dataset.psychTransition,undefined);
});
test('API refusal falls back to a single commit',async()=>{
 assert.equal(typeof api.runNativeTransition,'function');let n=0;const motion=api.runNativeTransition({document:{documentElement:{dataset:{}},startViewTransition(){throw Error('unsupported');}},commit:()=>n++});await motion.finished;assert.equal(n,1);
});
test('stale completion cannot erase newer transition names or active state',async()=>{
 assert.equal(typeof api.runNativeTransition,'function');const body={style:{}},dataset={},finishes=[];
 const document={documentElement:{dataset},startViewTransition:update=>{const updateCallbackDone=Promise.resolve().then(update);return {updateCallbackDone,ready:updateCallbackDone,finished:updateCallbackDone.then(()=>new Promise(r=>finishes.push(r))),skipTransition(){}};}};
 const a=api.runNativeTransition({document,kind:'cover',body:()=>body,commit(){}});await a.ready;
 const b=api.runNativeTransition({document,kind:'cover',body:()=>body,commit(){}});await b.ready;finishes[0]();await a.finished;
 assert.equal(body.style.viewTransitionName,'psych-body');assert.equal(dataset.psychTransition,'cover');finishes[1]();await b.finished;assert.equal(body.style.viewTransitionName,'');assert.equal(dataset.psychTransition,undefined);
});
