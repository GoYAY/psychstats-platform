// Offline synthetic fixtures only. Never reads the DTP paper or any API key.
import assert from 'node:assert/strict';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {writeFile} from 'node:fs/promises';
import {isolatedPage} from './native-cdp.mjs';
const folder=resolve('logs/term-explainer/full-job-delivery-qa');
const results=[];
for(const kind of ['story','statistical']){
  for(const width of [1440,390]){
    const browser=await isolatedPage(9278,width);
    try{
      await browser.page.send('Page.navigate',{url:pathToFileURL(resolve(folder,kind,'index.html')).href});
      await browser.until('document.readyState==="complete" && !!document.querySelector(".quiz-option")');
      const metrics=await browser.run(`({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,
        images:[...document.images].map(i=>({loaded:i.complete&&i.naturalWidth>0,source:i.currentSrc})),
        questionFirst:[...document.querySelectorAll('main>section')][0].id==='real_question'})`);
      assert.ok(metrics.scrollWidth<=width,JSON.stringify(metrics));
      assert.ok(metrics.questionFirst);
      assert.ok(metrics.images.length>0&&metrics.images.every(i=>i.loaded));
      await browser.run(`document.querySelector('[data-option="a"]').click()`);
      const correct=await browser.run('document.getElementById("quiz-feedback").textContent');
      assert.match(correct,/回答正确/);
      await browser.run(`document.querySelector('[data-option="c"]').click()`);
      const wrong=await browser.run('document.getElementById("quiz-feedback").textContent');
      assert.match(wrong,/学校名称是标识信息/);
      assert.doesNotMatch(wrong,/回答正确/);
      const png=await browser.page.send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
      await writeFile(resolve(folder,`${kind}-${width}.png`),Buffer.from(png.data,'base64'));
      results.push({kind,width,metrics,correct,wrong,status:'pass',actualDtp:false});
    }finally{await browser.close();}
  }
}
await writeFile(resolve(folder,'browser-qa.json'),JSON.stringify(results,null,2));
console.log('4 local browser layouts passed; images, overflow and per-option feedback checked.');
