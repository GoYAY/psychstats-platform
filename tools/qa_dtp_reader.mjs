// Actual local DTP output QA. No public deployment, remote navigation or model calls.
import assert from 'node:assert/strict';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {readFile,writeFile} from 'node:fs/promises';
import {isolatedPage} from './native-cdp.mjs';
const folder=resolve(process.env.DTP_QA_JOB||'.superpowers/sdd/2026-10-18-personal-term-explainer-phase1/live/dtp-user-pdf/dtp-complete-run');
const output=resolve('logs/term-explainer/dtp-delivery-review');
const lesson=JSON.parse(await readFile(resolve(folder,'lesson.json'),'utf8'));
const rows=[];
for(const width of [1440,390]){
  const browser=await isolatedPage(9278,width);
  try{
    await browser.page.send('Page.navigate',{url:pathToFileURL(resolve(folder,'preview/index.html')).href});
    await browser.until('document.readyState==="complete" && document.querySelector(".math .katex")!==null');
    const metrics=await browser.run(`({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,
      title:document.querySelector('h1').textContent,
      images:[...document.images].map(i=>({loaded:i.complete&&i.naturalWidth>0,source:i.currentSrc})),
      mathErrors:document.querySelectorAll('.katex-error,.math[aria-label]').length,
      renderedMath:document.querySelectorAll('.math .katex,.symbol-math .katex').length,
      scopeNotes:document.querySelectorAll('#evidence-scope p').length,
      relations:[...document.querySelectorAll('aside li a')].map(a=>a.getAttribute('href')),
      sections:[...document.querySelectorAll('main>section')].map(s=>s.id)})`);
    assert.ok(metrics.scrollWidth<=width,JSON.stringify(metrics));
    assert.equal(metrics.title,'优势特质剖面计分法');
    assert.ok(metrics.images.every(i=>i.loaded));
    assert.equal(metrics.images.length,1);
    assert.equal(metrics.mathErrors,0); assert.equal(metrics.renderedMath,6);
    assert.equal(metrics.scopeNotes,2); assert.equal(metrics.relations.length,2);
    assert.equal(metrics.sections[0],'real_question');
    assert.ok(metrics.sections.indexOf('formulas')<metrics.sections.indexOf('how_to_use'));
    for(const option of lesson.quiz.options){
      await browser.run(`document.querySelector('[data-option="${option.id}"]').click()`);
      const feedback=await browser.run('document.getElementById("quiz-feedback").textContent');
      assert.ok(feedback.endsWith(option.explanation));
      assert.equal(feedback.startsWith('回答正确。'),option.id===lesson.quiz.correct_option);
    }
    for(const section of ['top','formulas']){
      await browser.run(section==='top'?'window.scrollTo({top:0,behavior:"instant"})':`document.getElementById('formulas').scrollIntoView({behavior:'instant'})`);
      const png=await browser.page.send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
      await writeFile(resolve(output,`${width}-${section}.png`),Buffer.from(png.data,'base64'));
    }
    rows.push({width,metrics,status:'pass',actualDtp:true,modelCalls:0});
  }finally{await browser.close();}
}
await writeFile(resolve(output,'browser-qa.json'),JSON.stringify(rows,null,2));
console.log('Actual DTP desktop/mobile-width QA passed: six rendered math items, four option explanations, image, knowledge links, scope notes and no page overflow.');
