(function(window,document){
 'use strict';
 var script=document.currentScript,moduleURL=new URL(script.dataset.libraryModule||'library/app.mjs',script.src).href;
 var chartHost=script.dataset.chartModule?{moduleURL:new URL(script.dataset.chartModule,script.src).href}:null;
 if(chartHost&&new URL(chartHost.moduleURL).origin!==new URL(script.src).origin)chartHost=null;
 window.PsychPageRuntime.register('personal-library',function(ctx){
  if(!ctx.main.querySelector('[data-library-root]')){
   var origin=new URL(window.location?.href||script.src).searchParams.get('from-library');
   if(typeof origin==='string'&&/^[A-Za-z0-9][A-Za-z0-9_:.\-]{0,191}$/.test(origin)){
    var back=document.createElement('a');back.textContent='← 返回知识画布';back.href=new URL('library/index.html#view=network&framework='+encodeURIComponent(origin)+'&canvas-return=1',ctx.siteRoot).href;back.className='library-canvas-backlink';back.style.cssText='display:inline-block;margin:0 0 20px;padding:10px 16px;border-radius:10px;background:#f1f4fb;text-decoration:none;color:#3556a3;font-size:14px';ctx.main.prepend(back);
   }return {};
  }
  var active=true,app=null;
  import(moduleURL).then(function(module){
   if(!active||ctx.signal.aborted)return;
   app=module.mountLibrary({main:ctx.main,siteRoot:ctx.siteRoot,environment:'local-library-preview',signal:ctx.signal,state:ctx.state,chartHost:chartHost});
   return app.ready;
  }).catch(function(error){if(active&&!ctx.signal.aborted){var status=ctx.main.querySelector('[data-library-status]');if(status)status.textContent='知识库未能打开：'+error.message+'。请刷新重试，已有资料不会因此被清空。';}});
  return {dispose:function(){active=false;app?.dispose();},capture:function(){return app?.capture()||{};}};
 });
})(window,document);
