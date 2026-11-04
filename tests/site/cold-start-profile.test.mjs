import test from 'node:test';
import assert from 'node:assert/strict';
import {summarizeCPUProfile} from '../../tools/cold-start-profile.mjs';

test('attributes sampled time to actual leaf and caller without counting idle as JS work',()=>{
 const profile={nodes:[{id:1,callFrame:{functionName:'(root)',url:''},children:[2,4]},
  {id:2,callFrame:{functionName:'initialize',url:'https://cdst.site/psy-stats-test/assets/app.mjs',lineNumber:9},children:[3]},
  {id:3,callFrame:{functionName:'validate',url:'https://cdst.site/psy-stats-test/assets/data.mjs',lineNumber:19}},
  {id:4,callFrame:{functionName:'(idle)',url:''}}],samples:[3,3,2,4],timeDeltas:[1000,2000,3000,4000]};
 const result=summarizeCPUProfile(profile);
 assert.equal(result.sampledMs,10);assert.equal(result.idleMs,4);
 assert.equal(result.functions.find(f=>f.name==='validate').selfMs,3);
 assert.equal(result.functions.find(f=>f.name==='initialize').selfMs,3);
 assert.equal(result.functions.find(f=>f.name==='initialize').inclusiveMs,6);
 assert.equal(result.functions.find(f=>f.name==='validate').line,20);
 assert.equal(result.functions.some(f=>f.name==='(idle)'),false);
});

test('empty and partial sample profiles remain diagnostic rather than invented timing',()=>{
 assert.deepEqual(summarizeCPUProfile({nodes:[]}),{sampledMs:0,idleMs:0,functions:[]});
 const result=summarizeCPUProfile({nodes:[],samples:[99],timeDeltas:[500]});
 assert.equal(result.sampledMs,0.5);assert.equal(result.functions.length,0);
});
