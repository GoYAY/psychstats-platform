import {mkdir,readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const base='https://cdst.site/psy-stats/',rows=[];
for(const path of ['index.html','terms/sem.html','assets/navigation-motion.js?v=50b6119d46','assets/soft-navigation.js?v=4d3cf45796','assets/site.css?v=efb946cbc9','assets/vendor/katex/fonts/KaTeX_Main-Regular.woff2']){
 try{
  const start=performance.now(),response=await fetch(base+path,{signal:AbortSignal.timeout(20000)}),bytes=Buffer.from(await response.arrayBuffer());
  const local=await readFile('site/dist/'+path.split('?')[0]),hash=value=>createHash('sha256').update(value).digest('hex');
  rows.push({path,status:response.status,totalMs:performance.now()-start,decodedBytes:bytes.length,onlineHash:hash(bytes),localHash:hash(local),sameAsDist:bytes.equals(local),headers:Object.fromEntries([...response.headers].filter(([key])=>['cache-control','content-encoding','content-type','etag','last-modified','server','vary'].includes(key)))});
 }catch(error){rows.push({path,error:error.message});}
}
await mkdir('logs/complete-nav',{recursive:true});const file=`logs/complete-nav/online-version-audit-${Date.now()}.json`;await writeFile(file,JSON.stringify({base,rows},null,2));console.log(file,JSON.stringify(rows));if(rows.some(r=>r.error||r.status!==200))process.exitCode=1;
