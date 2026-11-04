import assert from 'node:assert/strict';
import {mkdir,writeFile,readFile,readdir} from 'node:fs/promises';
import {isolatedPage,args} from './native-cdp.mjs';
const {port='8772',cdp='9292'}=args(),base=`http://127.0.0.1:${port}/psy-stats/`,checks=[];
const targets=[['terms/spearman-correlation.html',2,'correlation'],
 ['terms/correlation-coefficient.html',2,'correlation'],['terms/partial-correlation.html',4,'correlation-types'],
 ['analyses/correlation.html',2,'correlation'],['analyses/correlation-types.html',4,'correlation-types'],
 ['analyses/ranks.html',3,'ranks'],['analyses/friedman-sign.html',2,'friedman-sign']];
for(const width of [1440,390]){
 const ctx=await isolatedPage(cdp,width);
 try{
  for(const [route,count,slug] of targets){
   await ctx.page.send('Page.navigate',{url:base+route});
   await ctx.until(`location.href===${JSON.stringify(base+route)}&&document.readyState==='complete'`);
   const result=await ctx.run(`(()=>{
    const section=document.querySelector('.paper-results'),table=section.querySelector('.paper-primary table');
    table.scrollIntoView({block:'center',behavior:'instant'});
    const headers=[...table.tHead.rows[0].cells],rows=[...table.tBodies[0].rows];
    return {headers:headers.map(h=>h.textContent),rows:rows.map(r=>[...r.cells].map(c=>c.textContent.replace('⟵','').trim())),
      numericAlignment:[...table.querySelectorAll('.analysis-numeric')].every(c=>getComputedStyle(c).textAlign==='right'),
      contains:document.documentElement.scrollWidth<=innerWidth+1,
      locators:[...table.querySelectorAll('[data-analysis-locate]')].map(b=>b.dataset.analysisLocate),
      sourceLinks:[...section.querySelectorAll('a[download]')].map(a=>a.getAttribute('href'))};
   })()`);
   assert.equal(result.rows.length,count,route);assert.ok(result.numericAlignment&&result.contains,route);
   assert.ok(result.sourceLinks.some(link=>new URL(link,base+route).pathname.endsWith('/assets/paper-results/'+slug+'.json')),route+' wrong teaching case');
   if(slug==='correlation'){
    assert.equal(result.rows[0][1],'Pearson r');assert.equal(result.rows[1][1],'Spearman ρ');
    assert.equal(result.rows[1].at(-3),'—');assert.equal(result.rows[1].at(-2),'—');
    assert.equal(result.rows[1].at(-1),'<0.001');
    if(route.startsWith('analyses/'))assert.ok(result.locators.includes('rho'));
   }
   if(slug==='correlation-types'){
    assert.deepEqual(result.rows.map(r=>r[1]),['偏相关 r（控制年龄）','Kendall τ','点二列相关 r','φ 系数']);
    assert.equal(result.rows[0][3],'357');assert.equal(result.rows[1][3],'—');
    assert.equal(result.rows[2].at(-1),'—');assert.equal(result.rows[3].at(-1),'—');
   }
   for(const field of result.locators){
    assert.equal(await ctx.run(`(()=>{document.querySelector('.paper-primary [data-analysis-locate="${field}"]').click();return document.activeElement.dataset.analysisSource===${JSON.stringify(field)}})()`),true,route+' locator '+field);
   }
   await ctx.run("document.querySelector('.paper-primary').scrollIntoView({block:'center',behavior:'instant'})");
   await mkdir('logs/paper-table-audit',{recursive:true});
   const shot=await ctx.page.send('Page.captureScreenshot',{format:'png'});
   await writeFile(`logs/paper-table-audit/${route.replaceAll('/','-')}-${width}.png`,Buffer.from(shot.data,'base64'));
   checks.push({width,route,...result});
  }
 }finally{await ctx.close();}
}
const files=(await readdir('site/content/analysis_cases')).filter(n=>n.endsWith('.json'));
for(const file of files){const path='analysis-logs/'+file.replace('.json','.txt');assert.deepEqual(await readFile('site/paper-table-audit-preview/'+path),await readFile('site/prefetch-coverage-preview/'+path));}
await writeFile('logs/paper-table-audit/method-browser-qa.json',JSON.stringify({checks,unchangedRawLogs:files.length},null,2));
console.log(JSON.stringify({checks:checks.length,unchangedRawLogs:files.length,success:true}));
