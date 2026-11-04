import {fail,validateStoredRecords} from './contract.mjs';
import {refKey} from './graph-identity.mjs';
export function declaredFrameworkRefs(records,framework,views=records.graphViews||[]){
 const refs=new Map();const put=r=>refs.set(refKey(r),structuredClone(r));
 for(const view of views.filter(v=>v.frameworkId===framework.id)){for(const n of view.nodes||[])put(n.ref);for(const g of view.groups||[])for(const r of g.members)put(r);for(const c of view.contextRefs||[])put({space:'pending',id:c.id});}
 return [...refs.values()];
}
export function inspectLegacyMembership(snapshot,frameworkId){
 const frame=snapshot.records.frameworks.find(f=>f.id===frameworkId);if(!frame)fail('CONFLICT','框架已不存在。');
 const views=(snapshot.records.graphViews||[]).filter(v=>v.frameworkId===frameworkId),groupViews=views.filter(v=>v.groups?.length),declared=declaredFrameworkRefs(snapshot.records,frame,groupViews.length?groupViews.map(v=>({...v,nodes:[]})):views),known=new Set(declared.map(refKey)),members=frame.members||[];
 return {declared,extra:declared.length?members.filter(r=>!known.has(refKey(r))):[],uncertain:declared.length?[]:structuredClone(members)};
}
export function planMembershipCleanup(snapshot,{frameworkId,removeRefs}){
 const old=snapshot.records.frameworks.find(f=>f.id===frameworkId);if(!old)fail('CONFLICT','框架已不存在。');
 const remove=new Set(removeRefs.map(refKey));if(remove.size!==removeRefs.length||removeRefs.some(r=>!old.members.some(m=>refKey(m)===refKey(r))))fail('CONFLICT','成员已变化，请重新检查。');
 const value=structuredClone(old);value.members=value.members.filter(r=>!remove.has(refKey(r)));value.revision++;value.updatedAt=new Date().toISOString();value.locks.members=true;
 if(value.provenance){value.origin='user';value.provenance.memberReasons=value.provenance.memberReasons.filter(r=>!remove.has(refKey(r.ref)));}
 if(value.memberDetails)value.memberDetails=value.memberDetails.filter(r=>!remove.has(refKey(r.ref)));
 if(value.excludedMembers)for(const ref of removeRefs)if(!value.excludedMembers.some(r=>refKey(r.ref)===refKey(ref)))value.excludedMembers.push({ref:structuredClone(ref),reason:'已手动移出框架'});
 const next=structuredClone(snapshot.records);next.frameworks=next.frameworks.map(f=>f.id===frameworkId?value:f);validateStoredRecords(next);
 return {plan:{writes:[{kind:'frameworks',id:frameworkId,value}],deletes:[],blobRefs:[],impact:[]},inverse:{records:[{kind:'frameworks',id:frameworkId,before:structuredClone(old),after:structuredClone(value)}]}};
}
