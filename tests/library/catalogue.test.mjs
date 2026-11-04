import test from 'node:test';import assert from 'node:assert/strict';
import {matchTerm,reconcileCatalogue,termURL} from '../../site/assets/library/catalogue.mjs';
test('ambiguous aliases return candidates and whole terms are matched',()=>{
 const official=[{id:'variable',zh:'变量',aliases:[],published:true},{id:'latent',zh:'潜变量',aliases:['TIRT'],published:true}];
 assert.equal(matchTerm('潜变量',official,[]).ref.id,'latent');assert.equal(matchTerm('不认识的潜变量',official,[]).ref,null);
 const ambiguous=matchTerm('TIRT',official,[{id:'other',zh:'另一含义',aliases:['TIRT']}]);assert.equal(ambiguous.ref,null);assert.equal(ambiguous.candidates.length,2);
});
test('unpublished and removed terms never fabricate routes or replacements',()=>{
 assert.equal(termURL({space:'pending',id:'future'},[],[],new URL('https://example.com/psy/')),null);
 assert.equal(termURL({space:'official',id:'gone'},[],[],new URL('https://example.com/psy/')),null);
 const old={terms:[{id:'gone',zh:'旧术语'}]},next={catalogueVersion:'v2',terms:[{id:'new',zh:'旧术语',published:true}]};
 const e={id:'e',from:{space:'personal',id:'a'},to:{space:'official',id:'gone'},status:'confirmed'};
 assert.equal(reconcileCatalogue(old,next,[e]).unavailable.length,1);assert.equal(reconcileCatalogue(old,next,[e]).candidates.length,0);
});
test('dismissed version does not reappear, upgrades are candidates only',()=>{
 const old={terms:[]},next={catalogueVersion:'v2',terms:[{id:'future',published:true}]},edge={id:'e',to:{space:'pending',id:'future'},status:'dismissed',catalogueVersion:'v2'};
 assert.equal(reconcileCatalogue(old,next,[edge]).candidates.length,0);assert.equal(reconcileCatalogue(old,next,[{...edge,status:'suggested'}]).candidates.length,1);
});
