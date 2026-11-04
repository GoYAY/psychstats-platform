import assert from 'node:assert/strict';
import {isolatedPage} from './native-cdp.mjs';
const b=await isolatedPage(9296,1440);
try{
 await b.page.send('Page.navigate',{url:'http://127.0.0.1:8773/psy-stats/qa/library-host.html'});await b.until('document.readyState==="complete"');
 await b.run(`(async()=>{const {mountFrameworkSidebar}=await import('/psy-stats/assets/library/framework-sidebar.mjs');const a={space:'personal',id:'a'},c={space:'pending',id:'c'},f={id:'f',title:'人机框架',scope:'判断随互动变化',description:'共同变化',origin:'user',locks:{title:false,members:false},members:[a,c],memberDetails:[{ref:a,role:'core',reason:'主要研究变化'},{ref:c,role:'supporting',reason:'必要监控机制'}]},records={terms:[{id:'a',zh:'认知漂移',trashed:false}],revisions:[],graphViews:[],contexts:[{id:'c',name:'元认知',definition:'观察思考'},{id:'other',name:'元认知控制',definition:'调整思考'}]};window.sideCommands=[];mountFrameworkSidebar(document.querySelector('main'),{framework:f,frameworks:[f],selectedId:'f',records,catalogue:[],templates:[],model:{nodes:[{ref:a,label:'认知漂移'},{ref:c,label:'元认知'}]},onCommand:async x=>sideCommands.push(x),onSelect:()=>{},organizerState:{report:{review:[{frameworkId:'f',ref:a,action:'remove',reason:'人工核对范围'}],conflicts:[]}}});})()`);
 assert.ok(await b.run(`document.querySelector('[data-framework-scope]')?.textContent.includes('判断随互动变化')`),'Scope must be visible');
 assert.equal(await b.run(`document.querySelector('[data-member-key="personal:a"] [data-member-role]')?.textContent`),'核心');
 assert.equal(await b.run(`document.querySelector('[data-member-key="pending:c"] [data-member-role]')?.textContent`),'辅助');
 assert.ok(await b.run(`!!document.querySelector('[data-framework-add] option[value="pending|other"]')`),'Shared independent brief must be addable');
 assert.ok(await b.run(`!!document.querySelector('[data-organizer-dismiss]')`),'Review-only result must be dismissible');
 console.log(JSON.stringify({scenario:'sidebar',status:'passed',scope:true,roles:true,sharedBriefs:true,reviewDismiss:true,providerCalls:0}));
}finally{await b.close();}
