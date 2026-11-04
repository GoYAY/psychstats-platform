// Real local browser checks for the shared diagram frame; no provider requests.
import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {isolatedPage} from './native-cdp.mjs';
const folder=resolve(process.env.DTP_QA_JOB||'.superpowers/sdd/2026-10-18-personal-term-explainer-phase1/live/dtp-user-pdf/dtp-complete-run','preview');
const out=resolve('logs/term-explainer/figure-frame-browser');
await mkdir(out,{recursive:true});
const css=await readFile(resolve('term_explainer/assets/reader.css'),'utf8');
const reports=[];
for(const width of [1440,390,320]){
 const browser=await isolatedPage(9278,width);
 try{
  await browser.page.send('Page.navigate',{url:pathToFileURL(resolve(folder,'index.html')).href});
  await browser.until('document.readyState==="complete" && document.querySelector("figure img")?.complete');
  // Exercise the actual shared asset even before an old preview is re-exported.
  await browser.run(`(()=>{const s=document.createElement('style');s.textContent=${JSON.stringify(css)};document.head.append(s)})()`);
  const inspect=()=>browser.run(`(()=>{const f=document.querySelector('figure'),s=getComputedStyle(f),r=f.getBoundingClientRect(),i=f.querySelector('img').getBoundingClientRect(),c=f.querySelector('figcaption').getBoundingClientRect();return {shadow:s.boxShadow,background:s.backgroundColor,radius:parseFloat(s.borderRadius),border:parseFloat(s.borderTopWidth),padding:parseFloat(s.paddingLeft),width:innerWidth,scroll:document.documentElement.scrollWidth,inside:i.left>r.left&&i.right<r.right&&c.left>r.left&&c.bottom<r.bottom,imageLoaded:f.querySelector('img').naturalWidth>0}})()`);
  const before=await inspect();
  assert.notEqual(before.shadow,'none','Diagram must have a visible theme-tinted shadow');
  assert.ok(!['rgba(0, 0, 0, 0)','rgb(255, 255, 255)'].includes(before.background),'Frame must have a pale nonwhite background');
  assert.ok(before.radius>=12 && before.border===0 && before.padding>=12);
  assert.ok(before.inside && before.imageLoaded && before.scroll<=width,JSON.stringify(before));
  await browser.run(`document.documentElement.style.setProperty('--accent','#8754bc')`);
  const after=await inspect();
  assert.notEqual(before.shadow,after.shadow,'Shadow must follow the shared theme token');
  assert.notEqual(before.background,after.background,'Background must follow the shared theme token');
  await browser.run(`document.documentElement.style.removeProperty('--accent');document.querySelector('figure').scrollIntoView({behavior:'instant',block:'center'})`);
  const png=await browser.page.send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
  await writeFile(resolve(out,`${width}.png`),Buffer.from(png.data,'base64'));
  reports.push({width,status:'pass',...before,themeResponds:true});
 }finally{await browser.close()}
}
await writeFile(resolve(out,'report.json'),JSON.stringify(reports,null,2));
console.log('Diagram frame passed at 1440/390/320: tinted shadow/background, borderless radius, image/caption containment, theme response and no overflow.');
