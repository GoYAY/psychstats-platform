import test from 'node:test';import assert from 'node:assert/strict';
const api=await import('../../site/next-preview/lib/navigation-controller.mjs').catch(()=>({}));
const manifest={pages:{index:{canonicalPath:'/psy-stats/',aliases:[]},paths:{canonicalPath:'/psy-stats/paths/',aliases:[]},'term:sem':{canonicalPath:'/psy-stats/terms/sem/',aliases:[]}}};
test('late response cannot replace the last selected view',async()=>{
 assert.equal(typeof api.createNavigationController,'function');const waits={},commits=[];
 const controller=api.createNavigationController({manifest,loader:{load:key=>new Promise(resolve=>waits[key]=resolve)},prepare:async()=>{},getCurrent:()=>({url:'https://example.org/psy-stats/',view:{key:'index'}}),capture:()=>({}),commit:x=>commits.push(x.view.key),transition:({commit})=>{commit();return {finished:Promise.resolve(),skip(){}};}});
 const a=controller.navigate('https://example.org/psy-stats/terms/sem/'),b=controller.navigate('https://example.org/psy-stats/paths/');waits.paths({kind:'paths'});assert.equal((await b).ok,true);waits['term:sem']({kind:'term'});assert.equal((await a).ok,false);assert.deepEqual(commits,['paths']);controller.dispose();
});
test('preparation failure preserves current view and no-op creates no history',async()=>{
 assert.equal(typeof api.createNavigationController,'function');const commits=[];
 const c=api.createNavigationController({manifest,loader:{load:async()=>({})},prepare:async()=>{throw Error('offline')},getCurrent:()=>({url:'https://example.org/psy-stats/',view:{key:'index'}}),capture:()=>({}),commit:x=>commits.push(x),transition:()=>{throw Error('must not animate')}});
 assert.equal((await c.navigate('https://example.org/psy-stats/')).unchanged,true);
 assert.equal((await c.navigate('https://example.org/psy-stats/paths/')).error.message,'offline');assert.deepEqual(commits,[]);c.dispose();
});
