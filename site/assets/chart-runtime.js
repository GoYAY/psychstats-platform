(function(window,document){
 'use strict';
 var script=document.currentScript,loaderURL=new URL(script.dataset.chartLoader,script.src).href,moduleURL=new URL(script.dataset.chartModule,script.src).href;
 if(new URL(moduleURL).origin!==new URL(script.src).origin)return;
 window.PsychPageRuntime.register('instant-charts',function(ctx){
  var nodes=Array.from(ctx.main.querySelectorAll('[data-instant-chart]')),instances=[],active=true,saved={};
  nodes.forEach(function(node){try{var data=JSON.parse(node.dataset.chartData),key=node.dataset.instantChart,selected=ctx.state[key]?.selectedCategory;saved[key]={selectedCategory:data.series[0].points.some(function(p){return p.category===selected;})?selected:null};}catch{}});
  if(nodes.length)import(loaderURL).then(function(module){if(!active||ctx.signal.aborted)return;nodes.forEach(function(node){try{var data=JSON.parse(node.dataset.chartData),key=node.dataset.instantChart;instances.push({key:key,mount:module.enhanceChart(node,{data:data,moduleURL:moduleURL,signal:ctx.signal,state:ctx.state[key]})});}catch{}});}).catch(function(){});
  return {dispose:function(){active=false;instances.forEach(function(i){saved[i.key]=i.mount.capture();i.mount.dispose();});},capture:function(){instances.forEach(function(i){saved[i.key]=i.mount.capture();});return Object.fromEntries(Object.entries(saved).map(function(i){return [i[0],Object.assign({},i[1])];}));}};
 });
})(window,document);
