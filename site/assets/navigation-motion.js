(function(window){
  'use strict';
  var active=null, reduce=matchMedia('(prefers-reduced-motion: reduce)');
  function cancel(){if(active)active();active=null;}
  function syncIndicator(){
    var pill=document.querySelector('.nav-motion-indicator'),box=pill?.getBoundingClientRect();
    window.PsychNavigationMotion?.syncNav(box);
  }
  function clip(rect,main){if(!rect)return 'inset(0px)';return 'inset('+Math.max(0,rect.top-main.top)+'px '+Math.max(0,main.right-rect.left-rect.width)+'px '+Math.max(0,main.bottom-rect.top-rect.height)+'px '+Math.max(0,rect.left-main.left)+'px round 18px)';}
  function contentLayer(main,elements){
    var layer=document.createElement('div');layer.className='soft-outgoing-layer';layer.inert=true;layer.setAttribute('aria-hidden','true');
    var top=document.querySelector('.site-head').getBoundingClientRect().bottom;
    if(elements)top=Math.max(top,elements[0].getBoundingClientRect().top);
    layer.style.clipPath='inset('+Math.max(0,top)+'px 0 0 0)';
    function position(node,box,left,y){Object.assign(node.style,{position:'absolute',left:(box.left-left)+'px',top:(box.top-y)+'px',width:box.width+'px',height:box.height+'px',margin:'0',transform:'none',maxWidth:'none'});}
    var host=layer,left=0,y=0;
    if(!elements){
      // Retain main > child styling without cloning the full page/hidden cards.
      var box=main.getBoundingClientRect();host=main.cloneNode(false);position(host,box,0,0);host.style.padding=getComputedStyle(main).padding;layer.appendChild(host);left=box.left;y=box.top;
    }
    (elements||Array.from(main.children)).forEach(function(element){
      var box=element.getBoundingClientRect();if(element.hidden||element.tagName==='SCRIPT'||box.bottom<top||box.top>innerHeight||!box.width)return;
      var grid=element.matches('.term-grid'),copy=element.cloneNode(!grid);position(copy,box,left,y);copy.style.padding=getComputedStyle(element).padding;
      if(grid)Array.from(element.children).forEach(function(card){var bounds=card.getBoundingClientRect();if(card.hidden||bounds.bottom<top||bounds.top>innerHeight)return;var clone=card.cloneNode(true);position(clone,bounds,box.left,box.top);var style=getComputedStyle(card);clone.style.borderColor=style.borderColor;clone.style.boxShadow=style.boxShadow;clone.style.transition='none';copy.appendChild(clone);});
      host.appendChild(copy);
    });
    layer.removeAttribute('id');layer.querySelectorAll('[id]').forEach(function(node){node.removeAttribute('id');});return layer;
  }
  async function transition(options){
    cancel();var main=document.querySelector('body > main');
    if(!main||reduce.matches||!main.animate){options.commit();return;}
    var root=document.documentElement, kind=options.kind||'cover', distance=options.direction==='previous'?-28:28;
    var bounds=main.getBoundingClientRect(), source=options.origin?.rect, finished=false, animations=[], layer=null, incoming=null, sequence=null, sequenceMarker=null;
    function clean(){if(finished)return;finished=true;animations.forEach(function(a){a.cancel();});if(sequence){sequence.classList.remove('soft-sequence-portal');sequenceMarker.replaceWith(sequence);}layer?.remove();incoming?.remove();root.classList.remove('soft-motion-active','soft-kind-expand','soft-kind-collapse','soft-kind-slide','soft-kind-cover');reduce.removeEventListener('change',onReduce);if(active===stop)active=null;}
    function stop(){clean();}
    function onReduce(){if(reduce.matches)stop();}
    active=stop;reduce.addEventListener('change',onReduce);
    root.classList.add('soft-motion-active','soft-kind-'+kind);
    try{
      if(kind==='cover'||options.elements){
        // Preserve the current viewport when a topic becomes shorter/empty.
        if(options.elements)main.style.minHeight=Math.max(0,innerHeight-bounds.top)+'px';
        layer=contentLayer(main,options.elements);layer.style.zIndex='21';document.body.appendChild(layer);
        options.commit();var nextMain=document.querySelector('body>main');incoming=contentLayer(nextMain,options.elements);incoming.classList.add('soft-incoming-depth');incoming.style.zIndex='22';document.body.appendChild(incoming);
        var heading=options.elements?options.elements[0].querySelector('h2'):nextMain.querySelector('h1'),headingBox=heading?.getBoundingClientRect();
        if(headingBox)incoming.style.transformOrigin=headingBox.left+'px '+headingBox.top+'px';
        animations.push(incoming.animate([{opacity:0,transform:'scale(0.995)'},{opacity:1,transform:'scale(1)'}],{duration:200,easing:'cubic-bezier(.22,1,.36,1)',fill:'both'}));
        await animations[0].finished.catch(function(){});
      }else{
        // Move the already rendered outgoing main into one inert layer. No whole
        // tree clone, per-node computed-style loop, or Shadow DOM CSS reload.
        layer=document.createElement('div');layer.className='soft-outgoing-layer';layer.inert=true;layer.setAttribute('aria-hidden','true');
        options.commit();layer.appendChild(main);document.body.appendChild(layer);
        Object.assign(main.style,{position:'absolute',left:bounds.left+'px',top:bounds.top+'px',width:bounds.width+'px',margin:'0'});
        var next=document.querySelector('body > main'), duration=kind==='slide'?420:kind==='expand'||kind==='collapse'?320:200;
        // Keep desktop viewport-anchored controls outside the transformed main.
        // Moving their existing DOM retains links, focus, and delegated events.
        if(matchMedia('(min-width: 1200px)').matches){
          sequence=next.querySelector('.term-sequence');
          if(sequence){sequenceMarker=document.createComment('sequence-motion-anchor');sequence.before(sequenceMarker);sequence.classList.add('soft-sequence-portal');document.body.appendChild(sequence);}
        }
        if(kind==='collapse'){
          var origin=options.origin,target=origin?.kind==='practice'?next.querySelector('.practice-reading'):origin?.kind==='analysis'?next.querySelector('.analysis-card[data-analysis-id="'+origin.cardId+'"]'):next.querySelector('.term-card[data-id="'+origin?.cardId+'"]');
          var dest=target?.getBoundingClientRect()||source;
          layer.style.zIndex='22';var frame={top:0,left:0,right:innerWidth,bottom:innerHeight};
          animations.push(layer.animate([{clipPath:'inset(0px)',opacity:1},{clipPath:clip(dest,frame),opacity:0}],{duration:duration,easing:'cubic-bezier(.22,1,.36,1)',fill:'both'}));
        }else{
          animations.push(next.animate([{opacity:kind==='expand'||kind==='cover'?1:0,transform:kind==='slide'?'translateX('+distance+'px) scale(0.995)':'scale(0.995)',clipPath:kind==='expand'?clip(source,next.getBoundingClientRect()):'inset(0px)'},
            {opacity:1,transform:'translateX(0px) scale(1)',clipPath:'inset(0px)'}],{duration:duration,easing:'cubic-bezier(.22,1,.36,1)',fill:'both'}));
        }
        await Promise.all(animations.map(function(a){return a.finished.catch(function(){});}));
      }
    }finally{clean();}
  }
  window.PsychSoftMotion={transition:transition,cancel:cancel,syncIndicator:syncIndicator,get running(){return !!active;}};
})(window);
