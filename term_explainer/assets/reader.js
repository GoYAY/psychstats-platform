'use strict';
(()=>{const mounted=new WeakMap();
function mountPersonalQuiz(root,{signal,quiz:provided}={}){
  mounted.get(root)?.();const controller=new AbortController();
  const dispose=()=>{controller.abort();signal?.removeEventListener('abort',dispose);mounted.delete(root);};
  if(signal?.aborted)return {dispose};signal?.addEventListener('abort',dispose,{once:true});mounted.set(root,dispose);
  for(const el of root.querySelectorAll('.math,.symbol-math')){
    if(window.katex){try{window.katex.render(el.dataset.latex,el,{displayMode:el.classList.contains('math'),trust:false,strict:'error',throwOnError:true});}catch{el.setAttribute('aria-label','公式以文本显示');}}
  }
  const data=root.querySelector('#quiz-data');
  if(data||provided){const quiz=provided||JSON.parse(data.textContent);const feedback=root.querySelector('#quiz-feedback');
    for(const button of root.querySelectorAll('.quiz-option')){button.addEventListener('click',()=>{
      for(const other of root.querySelectorAll('.quiz-option'))other.setAttribute('aria-pressed',String(other===button));
      const selected=quiz.options.find(o=>o.id===button.dataset.option);
      feedback.textContent=(selected.id===quiz.correct_option?'回答正确。':'这一项不符合。')+selected.explanation;
    },{signal:controller.signal});}
  }
  return {dispose};
}
window.PsychPersonalTeaching={mountPersonalQuiz};
document.addEventListener('DOMContentLoaded',()=>mountPersonalQuiz(document),{once:true});
})();
