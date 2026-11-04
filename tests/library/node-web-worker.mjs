import {Worker} from 'node:worker_threads';
export class NodeWebWorker{
 constructor(url){this.worker=new Worker(new URL('./node-worker-bridge.mjs',import.meta.url),{workerData:{url:String(url)}});this.worker.on('message',data=>this.onmessage?.({data}));this.worker.on('error',error=>this.onerror?.(error));}
 postMessage(value){this.worker.postMessage(value);}
 terminate(){return this.worker.terminate();}
}
