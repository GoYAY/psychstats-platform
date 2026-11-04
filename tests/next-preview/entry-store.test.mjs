import test from 'node:test';import assert from 'node:assert/strict';
const api=await import('../../site/next-preview/lib/entry-store.mjs').catch(()=>({}));
test('outgoing traversal captures displayed identity without writing the destination',()=>{
 assert.equal(typeof api.createEntryStore,'function');const store=api.createEntryStore({id:()=> 'entry-1'}),shown={url:'https://example.org/psy-stats/terms/sem.html',view:{key:'term:sem'},state:{psychView:{id:'sem-entry'}}};
 const saved=store.capture(shown,{layout:{pageState:{quizzes:['0']}},search:{query:'路径',scope:'page'},focus:{id:'q'}},'https://example.org/psy-stats/index.html');assert.equal(saved.replace,false);assert.equal(saved.state.psychView.key,'term:sem');assert.equal(store.resolve({psychView:{id:'sem-entry'}}).psychView.layout.pageState.quizzes[0],'0');assert.equal(store.resolve({psychView:{id:'sem-entry'}}).psychView.search.scope,'page');
});
