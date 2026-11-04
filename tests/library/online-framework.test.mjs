import test from 'node:test';import assert from 'node:assert/strict';
import {createOnlineFrameworkTransport} from '../../site/assets/library/online-framework-transport.mjs';
import {startFrameworkOrganizer} from '../../site/assets/library/framework-autogroup.mjs';
import {packageFixture} from './helpers.mjs';

test('revoking organizer consent during session lookup prevents any submission',async()=>{
 const control=new AbortController();let sent=0;
 const client={session:async()=>{control.abort();},create:async()=>{sent++;return {id:'j',state:'draft'};},start:async()=>{sent++;}};
 await assert.rejects(createOnlineFrameworkTransport(client).submit({terms:[]},'key',{signal:control.signal}),{name:'AbortError'});
 assert.equal(sent,0);
});

test('organization uses the same authenticated task API and resumes an existing queued task',async()=>{
 const events=[];const client={session:async()=>events.push('session'),create:async(value,key)=>{events.push({value,key});return {id:'job-a',state:'queued'};},start:async()=>{throw Error('Must not restart queued job');},get:async()=>({id:'job-a',state:'complete',usage:{calls:1}}),result:async()=>({groups:[],unassigned:[],calls:1})};
 const transport=createOnlineFrameworkTransport(client);assert.equal((await transport.submit({terms:[]},'hash-key')).taskId,'job-a');
 assert.equal(events[1].value.kind,'organize');assert.equal(events[1].value.model_allowed,true);assert.equal(events[1].value.network_allowed,false);
 const result=await transport.get('job-a');assert.equal(result.status,'complete');assert.equal(result.result.calls,1);
});

test('old loopback consent never enables remote transmission and only one transport sends',async()=>{
 let sent=0;const prefs=new Map([['framework-organizer',{enabled:true,consentVersion:2,processedTerms:{}}]]),p=packageFixture();
 const store={getPreference:async k=>prefs.get(k),setPreference:async(k,v)=>prefs.set(k,structuredClone(v)),snapshot:async()=>({version:1,records:{...p,graphViews:[],frameworks:[],contexts:[]}}),commit:async()=>{throw Error('Failed suggestion cannot change records');}};
 const transport={submit:async()=>{sent++;return {taskId:'job-a'};},get:async()=>({status:'failed',error:{message:'test failure'},calls:0})};
 const organizer=startFrameworkOrganizer({store,transport,getPublicContext:async()=>({}),fetcher:()=>{throw Error('Local service must not be contacted');}});
 await organizer.ready;await organizer.runNow();assert.equal(sent,0);await organizer.setEnabled(true);await organizer.runNow();assert.equal(sent,1);organizer.dispose();
 assert.equal(prefs.get('framework-organizer-online').consentVersion,3);
});
