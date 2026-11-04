// Execute the real browser archive worker inside a Node worker, not a ZIP mock.
import {parentPort,workerData} from 'node:worker_threads';
globalThis.self=globalThis;globalThis.postMessage=value=>parentPort.postMessage(value);
await import(workerData.url);
parentPort.on('message',data=>globalThis.onmessage({data}));
