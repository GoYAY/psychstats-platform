import test from 'node:test';import assert from 'node:assert/strict';
import {createGenerationClient} from '../../site/assets/library/generation-client.mjs';

test('generation requests use same-origin cookies, CSRF and an explicit idempotency key',async()=>{
 const calls=[];const client=createGenerationClient({apiRoot:'https://example.org/psy-stats-test/api/term-explainer/',origin:'https://example.org',fetcher:async(url,opts)=>{calls.push({url:String(url),...opts});return Response.json({csrf:'csrf-test',id:'job-test'});}});
 await client.login('invite-test');await client.create({kind:'lesson'},'stable-key');await client.get('job-test');
 assert.ok(calls.every(c=>c.url.startsWith('https://example.org/psy-stats-test/api/term-explainer/')));
 assert.ok(calls.every(c=>c.credentials==='same-origin'&&c.cache==='no-store'));
 assert.equal(calls[1].headers['X-CSRF-Token'],'csrf-test');assert.equal(calls[1].headers['Idempotency-Key'],'stable-key');
 assert.equal(calls.filter(c=>c.url.endsWith('/jobs')).length,1);
});
test('foreign endpoints, missing submission keys and server errors do not trigger retries',async()=>{
 assert.throws(()=>createGenerationClient({apiRoot:'https://other.example/api/',origin:'https://example.org'}));let calls=0;
 const client=createGenerationClient({apiRoot:'https://example.org/api/',origin:'https://example.org',fetcher:async()=>{calls++;return Response.json({error:{code:'budget_exhausted',message:'已达测试上限'}},{status:429});}});
 await assert.rejects(()=>client.create({},''));assert.equal(calls,0);
 await assert.rejects(()=>client.session(),e=>e.code==='budget_exhausted');assert.equal(calls,1);
});

test('explicit resume sends only version through the authenticated endpoint without retries',async()=>{
 const calls=[];const client=createGenerationClient({apiRoot:'https://example.org/api/',origin:'https://example.org',fetcher:async(url,opts)=>{calls.push({url:String(url),...opts});return Response.json({csrf:'test-token'});}});
 await client.login('invite');await client.resume('job-one',7);
 assert.equal(calls[1].url,'https://example.org/api/jobs/job-one/resume');assert.equal(calls[1].method,'POST');
 assert.deepEqual(JSON.parse(calls[1].body),{version:7});assert.equal(calls[1].headers['X-CSRF-Token'],'test-token');assert.equal(calls.length,2);
});
test('result streams the artifact and reports bytes against the declared length',async()=>{
 const parts=[new Uint8Array(700),new Uint8Array(1300)];
 const body=new ReadableStream({start(controller){for(const part of parts)controller.enqueue(part);controller.close();}});
 const client=createGenerationClient({apiRoot:'https://example.org/api/',origin:'https://example.org',fetcher:async()=>new Response(body,{headers:{'Content-Type':'application/zip','Content-Length':'2000'}})});
 const seen=[];const blob=await client.result('job-one',{onProgress:p=>seen.push(p)});
 assert.equal(blob.size,2000);assert.equal(blob.type,'application/zip');
 assert.deepEqual(seen[0],{received:0,total:2000});
 assert.equal(seen.at(-1).received,2000);
 assert.ok(seen.every((p,i)=>p.total===2000&&(i===0||p.received>=seen[i-1].received)));
});
test('json results stay json and never report download progress',async()=>{
 let progress=0;const client=createGenerationClient({apiRoot:'https://example.org/api/',origin:'https://example.org',fetcher:async()=>Response.json({revision:1})});
 assert.deepEqual(await client.result('job-one',{onProgress:()=>progress++}),{revision:1});assert.equal(progress,0);
});
