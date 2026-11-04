// Build-time only. Collapse startup's static ESM graph; retain lazy feature URLs.
import path from 'node:path';import {fileURLToPath} from 'node:url';
import {build} from '../chart_widget/node_modules/esbuild/lib/main.js';
export async function bundleLibrary(directory){
 const folder=path.resolve(directory),outfile=path.join(folder,'app-boot.mjs');
 const result=await build({entryPoints:[path.join(folder,'app.mjs')],outfile,bundle:true,format:'esm',platform:'browser',target:'es2022',minify:true,legalComments:'eof',metafile:true,
  plugins:[{name:'preserve-lazy-feature-boundaries',setup(builder){builder.onResolve({filter:/.*/},args=>args.kind==='dynamic-import'?{path:args.path,external:true}:undefined);}}]});
 const output=Object.values(result.metafile.outputs).find(x=>x.entryPoint);
 return {entry:'app-boot.mjs',bytes:output.bytes,staticImports:output.imports.filter(i=>i.kind!=='dynamic-import').map(i=>i.path),dynamicImports:output.imports.filter(i=>i.kind==='dynamic-import').map(i=>i.path)};
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url))console.log(JSON.stringify(await bundleLibrary(process.argv[2])));
