// Check rendered table semantics, real output links, and narrow-screen containment.
import assert from 'node:assert/strict';
import {mkdir,writeFile,readFile,readdir} from 'node:fs/promises';
import {isolatedPage,args} from './native-cdp.mjs';
const {port='8771',cdp='9292'}=args(),base=`http://127.0.0.1:${port}/psy-stats/`;
const checks=[];
for(const width of [1440,390]){
 const ctx=await isolatedPage(cdp,width);
 try{
  for(const route of ['terms/descriptive-statistics.html','analyses/describe.html','analyses/t-tests.html']){
   await ctx.page.send('Page.navigate',{url:base+route});
   await ctx.until(`location.href===${JSON.stringify(base+route)}&&document.readyState==='complete'&&!!window.PsychSoftNavigation`);
   const grouped=route.endsWith('/t-tests.html');
   const result=await ctx.run(`(()=>{
    const grouped=${grouped}, table=[...document.querySelectorAll('.paper-table')].find(t=>t.caption.textContent.includes(grouped?'各组描述统计':'研究变量的描述统计'));
    if(!table)return {missing:true};
    for(let e=table;e;e=e.parentElement)if(e.tagName==='DETAILS')e.open=true;
    table.scrollIntoView({block:'center',behavior:'instant'});
    const frame=table.closest('.paper-table-scroll'),headers=[...table.tHead.rows[0].cells];
    return {headers:headers.map(c=>c.textContent.trim()),rows:[...table.tBodies[0].rows].map(r=>[...r.cells].map(c=>c.textContent.replace('⟵','').trim())),
     rowHeaders:table.querySelectorAll('tbody th[scope=row]').length,
     numericAlignment:[...table.querySelectorAll('.analysis-numeric')].every(c=>getComputedStyle(c).textAlign==='right'),
     lines:[getComputedStyle(table).borderTopWidth,getComputedStyle(table.tHead).borderBottomWidth,getComputedStyle(table).borderBottomWidth],
     noVerticalBorders:[...table.querySelectorAll('th,td')].every(c=>getComputedStyle(c).borderLeftWidth==='0px'&&getComputedStyle(c).borderRightWidth==='0px'),
     contained:document.documentElement.scrollWidth<=innerWidth+1&&frame.getBoundingClientRect().right<=innerWidth+1,
     locators:[...table.querySelectorAll('[data-analysis-locate]')].map(b=>b.dataset.analysisLocate)};
   })()`);
   assert.equal(result.missing,undefined,route);
   assert.deepEqual(result.headers,grouped?['研究变量','组别','有效样本量 n','均值 M','标准差 SD']:['研究变量','有效样本量 n','均值 M','标准差 SD','中位数 Mdn','四分位距 IQR']);
   assert.deepEqual(result.rows,grouped?[
    ['成绩增量（gain）','练习回忆组（retrieval）','90','9.87','8.59'],
    ['成绩增量（gain）','对照组（control）','90','2.63','8.28']
   ]:[['压力分数（stress）','360','48.61','8.06','49.00','10.53']]);
   assert.equal(result.rowHeaders,grouped?2:1);
   assert.ok(result.numericAlignment&&result.noVerticalBorders&&result.contained,JSON.stringify({width,route,result}));
   assert.deepEqual(result.lines,['2px','1px','2px']);
   if(route==='analyses/describe.html'){
    assert.deepEqual(result.locators,['n','mean','sd','median','iqr']);
    for(const field of result.locators){
     assert.equal(await ctx.run(`(()=>{document.querySelector('[data-analysis-locate="${field}"]').click();return document.activeElement.dataset.analysisSource===${JSON.stringify(field)}})()`),true,'Output locator '+field);
    }
    await ctx.run("document.querySelector('.paper-primary').scrollIntoView({block:'center',behavior:'instant'})");
   }
   await mkdir('logs/descriptive-tables',{recursive:true});
   const shot=await ctx.page.send('Page.captureScreenshot',{format:'png'});
   await writeFile(`logs/descriptive-tables/${route.replaceAll('/','-')}-${width}.png`,Buffer.from(shot.data,'base64'));
   checks.push({width,route,...result});
  }
 }finally{await ctx.close();}
}
const files=(await readdir('site/content/analysis_cases')).filter(n=>n.endsWith('.json'));
for(const file of files){
 const slug=file.slice(0,-5),raw=`analysis-logs/${slug}.txt`;
 assert.deepEqual(await readFile('site/descriptive-table-preview/'+raw),await readFile('site/prefetch-coverage-preview/'+raw),'Raw log must stay unchanged: '+slug);
}
await writeFile('logs/descriptive-tables/browser-qa.json',JSON.stringify({checks,unchangedRawLogs:files.length},null,2));
console.log(JSON.stringify({checks:checks.length,unchangedRawLogs:files.length,success:true}));
