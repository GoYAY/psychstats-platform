import test from 'node:test';
import assert from 'node:assert/strict';
import {readFavorites,writeFavorites,readSession,writeSession} from '../../site/next-preview/lib/storage.mjs';
import {findOffsets} from '../../site/next-preview/lib/text-find.mjs';
import {filterTerms,searchTerms} from '../../site/next-preview/lib/search.mjs';
const terms=[{id:'variable',zh:'变量',topic:'foundations',level:'basic',has_r:false},{id:'sem',zh:'结构方程模型',topic:'structural-equation-modeling',level:'advanced',has_r:true,body_text:'潜变量测量指标'}];
test('reads legacy favorites and rejects malformed ids and payloads',()=>{
 assert.deepEqual([...readFavorites({getItem:key=>key==='psych-favorites-v1'?'["variable",null,"../bad"]':null})],['variable']);
 assert.equal(readFavorites({getItem:()=>'{bad'}).size,0);
 assert.equal(readFavorites({getItem:()=>{throw Error('denied')}}).size,0);
 let saved;assert.equal(writeFavorites({setItem:(key,value)=>{saved=[key,value]}},new Set(['sem'])),true);
 assert.deepEqual(saved,['psych-favorites-v1','["sem"]']);
 assert.equal(writeFavorites({setItem:()=>{throw Error('denied')}},new Set()),false);
});
test('filters topic, difficulty and R separately and searches full body',()=>{
 assert.deepEqual(filterTerms('',{topic:'foundations'},terms).map(t=>t.id),['variable']);
 assert.deepEqual(filterTerms('',{level:'advanced',has_r:'true'},terms).map(t=>t.id),['sem']);
 assert.deepEqual(searchTerms('测量指标',{},terms).map(t=>t.id),['sem']);
 assert.deepEqual(searchTerms('测量指标',{topic:'foundations'},terms),[]);
});
test('blocked session storage does not break page restoration',()=>{
 assert.equal(readSession({getItem:()=>{throw Error('denied')}},'filters',null),null);
 assert.equal(writeSession({setItem:()=>{throw Error('denied')}},'filters',{}),false);
 assert.deepEqual(readSession({getItem:()=>'{bad'},'filters',{}),{});
});
test('page search ignores whitespace and gives original text offsets',()=>{
 assert.deepEqual(findOffsets('潜变量与潜变量','   '),[]);
 assert.deepEqual(findOffsets('潜变量与潜变量','潜变量'),[[0,3],[4,7]]);
 assert.deepEqual(findOffsets('R r RStudio','r'),[[0,1],[2,3],[4,5]]);
});
