import {buildIndex,updateIndex,search,selectContext} from './search.mjs';
let index;
self.onmessage=event=>{const {id,type,records,changes,query,options}=event.data;try{if(type==='build')index=buildIndex(records);if(type==='update')updateIndex(index,changes);const result=type==='search'?search(index,query,options):type==='context'?selectContext(index,query,options):{indexed:index.documents.size,updated:index.lastUpdated};self.postMessage({id,result});}catch(e){self.postMessage({id,error:{code:e.code||'SEARCH_ERROR',message:e.message}});}};
