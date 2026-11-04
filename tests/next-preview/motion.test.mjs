import test from 'node:test';
import assert from 'node:assert/strict';
import {motionFrames,createMotionController,canPrefetch} from '../../site/next-preview/lib/motion.mjs';
import {ordinaryClick} from '../../site/next-preview/lib/routes.mjs';
test('motion distinguishes adjacent direction and reduced preference',()=>{
 assert.equal(motionFrames('slide',-1,false).options.duration,420);
 assert.ok(motionFrames('slide',-1,false).frames[0].transform.includes('-28px'));
 assert.equal(motionFrames('expand',1,false).options.duration,320);
 assert.equal(motionFrames('topic',1,true).options.duration,0);
});
test('new motion cancels old owner and stale completion cannot clean the new one',async()=>{
 const controller=createMotionController();let cancelled=0;
 const old=controller.start(()=>cancelled++);const next=controller.start(()=>cancelled++);
 assert.equal(cancelled,1);assert.equal(old.current(),false);assert.equal(next.current(),true);
 old.finish();assert.equal(next.current(),true);controller.cancel();assert.equal(cancelled,2);
});
test('only intentional migrated candidates prefetch; modified clicks are native',()=>{
 assert.equal(canPrefetch('preview',{saveData:true}),false);
 assert.equal(canPrefetch('legacy',{}),false);
 assert.equal(canPrefetch('preview',{effectiveType:'2g'}),false);
 assert.equal(canPrefetch('preview',{}),true);
 assert.equal(ordinaryClick({button:0,ctrlKey:true}),false);
 assert.equal(ordinaryClick({button:0}),true);
});
