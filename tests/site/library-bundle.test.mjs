import test from 'node:test';import assert from 'node:assert/strict';
import {mkdtemp,writeFile,readFile,rm} from 'node:fs/promises';import os from 'node:os';import path from 'node:path';import {pathToFileURL} from 'node:url';
import {fileURLToPath} from 'node:url';
import {LibraryError} from '../../site/assets/library/contract.mjs';
let bundleLibrary;try{({bundleLibrary}=await import('../../tools/bundle-library.mjs'));}catch(e){if(e.code!=='ERR_MODULE_NOT_FOUND')throw e;}
test('startup bundle removes static request waterfall but keeps lazy routes and asset URLs functional',async()=>{
 assert.equal(typeof bundleLibrary,'function','Missing library startup bundler');
 const folder=await mkdtemp(path.join(os.tmpdir(),'psychstats-bundle-'));
 try{
  await writeFile(path.join(folder,'values.mjs'),'export const value=7;');
  await writeFile(path.join(folder,'lazy.mjs'),'export const value=11;');
  await writeFile(path.join(folder,'app.mjs'),`import {value} from './values.mjs';export const initial=value;export const asset=new URL('catalogue.json',import.meta.url).href;export const worker=new URL('archive.worker.mjs',import.meta.url).href;export async function later(){return(await import('./lazy.mjs')).value;}`);
  const result=await bundleLibrary(folder),module=await import(pathToFileURL(path.join(folder,result.entry)).href);
  assert.equal(module.initial,7);assert.equal(await module.later(),11);
  assert.equal(module.asset,pathToFileURL(path.join(folder,'catalogue.json')).href);assert.equal(module.worker,pathToFileURL(path.join(folder,'archive.worker.mjs')).href);
  assert.deepEqual(result.staticImports,[]);assert.deepEqual(result.dynamicImports,['./lazy.mjs']);
  assert.ok((await readFile(path.join(folder,'values.mjs'),'utf8')).includes('value=7'),'Keep source modules used by workers/lazy entries');
 }finally{await rm(folder,{recursive:true,force:true});}
});

test('errors from the real bundled contract retain identity for external ZIP consumers, without trusting JSON lookalikes',async()=>{
 const folder=await mkdtemp(path.join(os.tmpdir(),'psychstats-error-bundle-'));
 try{
  const contract=fileURLToPath(new URL('../../site/assets/library/contract.mjs',import.meta.url));
  await writeFile(path.join(folder,'app.mjs'),`import {LibraryError} from ${JSON.stringify(contract)};export function fail(){throw new LibraryError('QUOTA','本机存储空间不足');}`);
  const result=await bundleLibrary(folder),compiled=await import(pathToFileURL(path.join(folder,result.entry)).href);
  let caught;try{compiled.fail();}catch(e){caught=e;}
  assert.equal(caught instanceof LibraryError,true,'External archive must preserve bundled storage errors');
  assert.equal(caught.code,'QUOTA');assert.equal(caught.message,'本机存储空间不足');
  assert.equal({name:'LibraryError',code:'QUOTA',message:'forged'} instanceof LibraryError,false);
  assert.equal(Object.assign(Error('forged'),{name:'LibraryError',code:'QUOTA'}) instanceof LibraryError,false);
 }finally{await rm(folder,{recursive:true,force:true});}
});
