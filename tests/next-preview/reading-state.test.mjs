import test from 'node:test';
import assert from 'node:assert/strict';
import {restoreReadingState} from '../../site/next-preview/lib/reading-state.mjs';

test('restoring an unanswered history entry clears later quiz feedback',()=>{
 const feedback={hidden:false},classes=new Set(['wrong']);
 const button={dataset:{idx:'1'},nextElementSibling:feedback,classList:{remove(...values){values.forEach(v=>classes.delete(v));}},setAttribute(name,value){this[name]=value;}};
 const result={textContent:'回答错误。'},quiz={querySelectorAll:()=>[button],querySelector:()=>result};
 const root={querySelectorAll:selector=>selector==='.quiz'?[quiz]:[]};
 restoreReadingState(root,{quizzes:[null],pins:[],details:[],tabs:[]});
 assert.equal(button['aria-pressed'],'false');assert.equal(feedback.hidden,true);assert.equal(result.textContent,'');assert.equal(classes.size,0);
});
