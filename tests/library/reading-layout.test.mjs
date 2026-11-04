import test from 'node:test';
import assert from 'node:assert/strict';
import {readingSections} from '../../site/assets/library/reading-layout.mjs';
import {readerProjection} from '../../site/assets/library/reader.mjs';
import {packageFixture} from './helpers.mjs';

test('page navigation covers exactly rendered teaching modules in reading order',()=>{
 const l=packageFixture().revisions[0].lesson;l.visual={kind:'story'};l.formulas=[{latex:'x',symbols:[]}];l.limitations=[{text:'范围'}];
 const ids=readingSections(l).map(s=>s.id);
 assert.ok(ids.indexOf('visual')===ids.indexOf('plain_explanation')+1);
 assert.ok(ids.indexOf('formulas')===ids.indexOf('detailed_explanation')+1);
 assert.deepEqual(ids.slice(-3),['quiz','evidence-scope','sources']);
 assert.equal(new Set(ids).size,ids.length);
});
test('absent optional modules create no empty navigation entries',()=>{
 const l=packageFixture().revisions[0].lesson;l.visual=null;l.formulas=[];l.quiz=null;l.limitations=[];
 const ids=readingSections(l).map(s=>s.id);
 assert.ok(!ids.includes('visual')&&!ids.includes('formulas')&&!ids.includes('quiz')&&!ids.includes('evidence-scope'));
 assert.equal(ids.at(-1),'sources');
});
test('verified source name is displayed while source anchors and private refs remain private',()=>{
 const p=packageFixture(),r=p.revisions[0];r.lesson.term.en='';
 r.lesson.provenance={verified_identity:{en:'Situational judgement test',refs:[{source_id:'PRIVATE'}]}};
 const projection=readerProjection(r,p.sources,p.works);
 assert.equal(projection.term.en,'Situational judgement test');assert.ok(!JSON.stringify(projection).includes('PRIVATE'));
 assert.equal(r.lesson.term.en,'');
});
