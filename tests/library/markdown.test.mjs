import test from 'node:test';
import assert from 'node:assert/strict';
import {packageFixture} from './helpers.mjs';
const core=await import('../../site/assets/library/markdown.mjs').catch(()=>null);
function api(){assert.ok(core,'Markdown library projection is not implemented');return core;}
const snapshot=()=>{const p=packageFixture();return {version:1,records:Object.fromEntries(Object.entries(p).filter(([,v])=>Array.isArray(v)))};};
const decoded=file=>new TextDecoder().decode(file.bytes);

test('text originals use readable text extensions in Markdown exports',async()=>{
 const s=snapshot(),hash='a'.repeat(64);Object.assign(s.records.sources[0],{blobHash:hash,fileName:'paper.txt',originalStatus:'saved'});
 const projected=await api().projectMarkdown(s,{includeOriginals:true});const original=projected.files.find(f=>f.path.startsWith('原件/'));
 assert.ok(original.path.endsWith('.txt'));assert.equal(original.mime,'text/plain');
});
test('projection escapes YAML, Windows filenames and raw HTML without exposing evidence',async()=>{
 const state=snapshot();state.records.terms[0].zh='CON:<样本>\n注释';state.records.terms[0].aliases=['a:\n---'];state.records.evidence[0].data.text+='PRIVATE_EVIDENCE_SENTINEL';state.records.revisions[0].lesson.blocks[1].paragraphs[0].text='<script>alert(1)</script>';
 const output=await api().projectMarkdown(state,{includeOriginals:false,includeEvidence:false});const term=output.files.find(f=>f.path.startsWith('术语/'));
 assert.ok(term);assert.ok(!/[<>:"\\|?*\n]/.test(term.path.split('/').pop()));assert.ok(decoded(term).includes('a:\\n---'));assert.ok(!decoded(term).includes('<script>'));
 assert.ok(!output.files.filter(f=>f.bytes).map(decoded).join('').includes('PRIVATE_EVIDENCE_SENTINEL'));
 assert.equal(output.manifest.kind,'personal-library-reading');
});
test('same-name notes get distinct stable paths and personal links point to real files',async()=>{
 const state=snapshot(),other=structuredClone(state.records.terms[0]);other.id='another-sample';other.currentRevisionId=null;state.records.terms.push(other);
 state.records.edges.push({id:'edge',from:{space:'personal',id:'sample'},to:{space:'personal',id:'another-sample'},type:'next',reason:'继续学习',status:'confirmed',origin:'user',refs:[],revisionId:'rev-demo'});
 const first=await api().projectMarkdown(state,{}),second=await api().projectMarkdown(state,{});const paths=first.files.filter(f=>f.path.startsWith('术语/')).map(f=>f.path);
 assert.equal(new Set(paths).size,2);assert.deepEqual(first.files.map(f=>f.path),second.files.map(f=>f.path));
 const main=first.files.find(f=>decoded(f).includes('rev-demo'));assert.ok(decoded(main).includes(encodeURIComponent(paths.find(p=>p!==main.path).split('/').pop())));
});
test('static reading preserves every option explanation and necessary helper meanings',async()=>{
 const state=snapshot(),lesson=state.records.revisions[0].lesson;lesson.glossary=[{term:'辅助术语',explanation:'辅助说明'}];lesson.formulas=[{latex:'x=1',symbols:[{symbol:'x',meaning:'示例符号'}]}];
 const out=await api().projectMarkdown(state,{}),body=out.files.filter(f=>f.path.startsWith('术语/')).map(decoded).join('');assert.ok(body.includes('辅助说明'));assert.ok(body.includes('示例符号'));assert.ok(body.includes('$$'));for(const id of ['A','B','C','D'])assert.ok(body.includes(id+'：'));
});
test('reading export cannot silently include private evidence',async()=>{await assert.rejects(()=>api().projectMarkdown(snapshot(),{includeEvidence:true}),e=>e.code==='INVALID_PACKAGE');});
test('external Markdown becomes a separate unverified note and never rewrites its base',async()=>{
 const state=snapshot(),before=JSON.stringify(state),source='---\nid: "sample"\n---\n# 我的修改\n<script>alert(1)</script>';
 const note=await api().importMarkdown(source,{fileName:'edited.md',baseRevisionId:'rev-demo'});assert.equal(note.origin,'external-markdown');assert.equal(note.revisionId,'rev-demo');assert.equal(note.text,source);assert.equal(JSON.stringify(state),before);
});
test('several excerpts of one original produce one original link and file',async()=>{const state=snapshot(),hash='a'.repeat(64);state.records.sources[0].blobHash=hash;state.records.sources[0].originalStatus='saved';state.records.sources.push({...state.records.sources[0],id:'source-two',localId:'s2'});state.records.revisions[0].sourceMap.s2='source-two';state.records.revisions[0].lesson.blocks[3].paragraphs[0].refs[0]={source_id:'s2',start:0,end:10};const projected=await api().projectMarkdown(state,{includeOriginals:true});assert.equal(projected.files.filter(f=>f.path.startsWith('原件/')).length,1);assert.equal(projected.files.filter(f=>f.bytes).map(decoded).join('').match(/打开归档原件/g).length,1);});
