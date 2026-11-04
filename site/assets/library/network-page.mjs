import {buildGraph} from './graph-model.mjs';
import {mountCanvas} from './canvas.mjs';
import {defaultGraphView,planGraphCommand,planGraphInverse} from './graph-commands.mjs';
import {planFrameworkCommand} from './framework-commands.mjs';
import {legacyFrameworks} from './framework-schema.mjs';
import {mountFrameworkSidebar} from './framework-sidebar.mjs';
import {canonical} from './framework-summary.mjs';
import {planReviewDecision} from './semantic-suggestions.mjs';
import {planMembershipCleanup} from './framework-boundaries.mjs';
import {crossFrameworkRelations} from './graph.mjs';
import {refKey} from './graph-identity.mjs';
import {representativeNode} from './graph-focus.mjs';
import {publicFramework} from './public-networks.mjs';
export function restoreFrameworkView(current,state,saved){if(!state.view||!Object.hasOwn(state,'savedView')||canonical(saved||null)!==canonical(state.savedView)||state.view.id!==current.id||state.view.frameworkId!==current.frameworkId)return current;return structuredClone(state.view);}
export function frameworkView(records,id){const exact=(records.graphViews||[]).find(v=>v.id===id),saved=exact||(records.graphViews||[]).find(v=>v.frameworkId===id);return saved?structuredClone(saved):defaultGraphView('view-'+id.slice(0,175),id);}
export function savedViewOptions(records,officialGraph={frameworks:[]}){const entries=(officialGraph.frameworks||[]).map(f=>({id:'official:'+f.id,title:'官方 · '+f.title,public:true}));entries.push(...(records.frameworks||[]).map(f=>({id:f.id,title:f.title,frameworkId:f.id})));const counts=new Map();for(const v of records.graphViews||[]){const count=counts.get(v.frameworkId)||0;counts.set(v.frameworkId,count+1);if(count||!entries.some(o=>o.frameworkId===v.frameworkId))entries.push({id:v.id,title:v.title+' · 保存的布局',frameworkId:v.frameworkId});}return entries;}
const strip=v=>{const {selected,...saved}=v;return saved;};
function applied(snapshot,plan){const next=structuredClone(snapshot);for(const d of plan.deletes)next.records[d.kind]=next.records[d.kind].filter(r=>r.id!==d.id);for(const w of plan.writes)next.records[w.kind]=[...(next.records[w.kind]||[]).filter(r=>r.id!==w.id),w.value];return next;}
export function mountNetwork(root,{store,catalogue,siteRoot,signal,onRead,onMessage=()=>{},organizer,state={}}){
 const abort=new AbortController();let workspaceState=state.workspace||{},sidebarTab=state.sidebarTab||'terms',disposed=false,snapshot,officialGraph={terms:[],edges:[],frameworks:[]},controller,sidebar,view,framework,selectedId='',sequence=0,undo=[],redo=[];
 const canvasRoot=document.createElement('div');root.append(canvasRoot);
 const project=()=>buildGraph({records:framework?.publicTemplate?{...snapshot.records,edges:[]}:snapshot.records,catalogue,officialGraph:framework?.publicTemplate?{...officialGraph,edges:officialGraph.edges.filter(e=>officialGraph.frameworks.find(f=>f.id===framework.publicTemplate).edgeKeys.includes(e.key))}:officialGraph,view,framework:framework?.legacyTemplate?null:framework||{members:[]}});
 const crossRelations=ref=>framework?.publicTemplate?[]:crossFrameworkRelations(ref,{records:snapshot.records,officialGraph,framework}).map(edge=>{const target=refKey(edge.from)===refKey(ref)?edge.to:edge.from,node=buildGraph({records:snapshot.records,catalogue,officialGraph,framework:{members:[target]}}).nodes[0];return {edge,ref:target,label:node?.label||target.id,frameworkId:snapshot.records.frameworks.find(f=>f.id!==framework.id&&f.members.some(r=>refKey(r)===refKey(target)))?.id||null};});
 const sidebarState=()=>({framework,activeTab:sidebarTab,onTabChange:value=>{sidebarTab=value;},model:project(),selection:controller?.capture().selected,frameworks:savedViewOptions(snapshot.records,officialGraph),selectedId,records:snapshot.records,catalogue,templates:officialGraph.frameworks,organizerState:organizer?.getState(),signal:abort.signal,onSelect:(ref,options)=>controller.select(ref,options),onCommand:command});
 function updateSidebar(){sidebar?.update(sidebarState());}
 async function ensureFrameworks(){const known=new Set(snapshot.records.frameworks.map(f=>f.id)),rows=legacyFrameworks(snapshot.records.graphViews).filter(f=>!known.has(f.id));if(!rows.length)return;await store.commit({writes:rows.map(value=>({kind:'frameworks',id:value.id,value})),deletes:[],blobRefs:[],impact:[]},{expectedVersion:snapshot.version,signal:abort.signal});snapshot=await store.snapshot();}
 async function changeFramework(id,{restore=false}={}){
  const token=++sequence;workspaceState=controller?.captureWorkspace?.()||workspaceState;sidebar?.dispose();controller?.dispose();snapshot=await store.snapshot();if(disposed||token!==sequence)return;if(!publicFramework(officialGraph,id))await ensureFrameworks();if(disposed||token!==sequence)return;
  const exact=snapshot.records.graphViews.find(v=>v.id===id);framework=publicFramework(officialGraph,id)||snapshot.records.frameworks.find(f=>f.id===(exact?.frameworkId||id))||null;
  if(framework?.legacyTemplate){try{const result=planFrameworkCommand(snapshot,{kind:'materializeLegacy',id:framework.id},{catalogue,officialGraph});await store.commit(result.plan,{expectedVersion:snapshot.version,signal:abort.signal});snapshot=await store.snapshot();framework=snapshot.records.frameworks.find(f=>f.id===framework.id);}catch(e){onMessage(e.message,true);}}
  selectedId=framework?(exact?.id||framework.id):'';view=framework?frameworkView(snapshot.records,selectedId):defaultGraphView('empty','empty');
  if(restore&&state.frameworkId===selectedId)view=restoreFrameworkView(view,state,snapshot.records.graphViews.find(v=>v.id===view.id)||null);
  const model=project(),returning=restore&&state.frameworkId===selectedId&&(Object.hasOwn(state,'selection')||state.view?.selected),representative=returning?null:representativeNode(model,framework),selection=returning?state.selection||state.view?.selected||null:representative?{kind:'node',key:refKey(representative)}:null;if(!restore)sidebarTab='terms';
  controller=mountCanvas(canvasRoot,{workspace:workspaceState,readOnly:!!framework?.publicTemplate,onCrossRelations:crossRelations,model,view,selection,signal:abort.signal,onCommand:command,onSelect:selection=>sidebar?.update({selection}),onRead:node=>onRead(node,capture())});await controller.ready;if(disposed||token!==sequence)return;
  sidebar=mountFrameworkSidebar(controller.sidebarRoot,sidebarState());const params=new URLSearchParams(location.hash.slice(1));params.set('view','network');params.delete('term');if(selectedId)params.set('framework',selectedId);else params.delete('framework');history.replaceState(history.state,'','#'+params);
 }
 async function command(c){
  if(disposed)throw Error('画布页面已离开。');
  if(c.scope==='organize'){if(!organizer)throw Error('本机自动整理暂未初始化。');if(c.action==='enable')await organizer.setEnabled(c.enabled);else if(c.action==='undo')await organizer.undoLast();else if(c.action==='dismiss')await organizer.dismissReport();else await organizer.runNow({retry:true});return;}
  if(c.scope==='choose'){await changeFramework(c.id);return;}
  if(framework?.publicTemplate&&c.scope!=='template'&&!(c.scope==='framework'&&c.kind==='create')){if(c.kind==='setViewport'){view={...strip(controller.capture()),...(c.mode?{mode:c.mode}:{})};return {transient:true};}if(c.kind==='move'){const captured=strip(controller.capture());view={...captured,nodes:captured.nodes.map(n=>refKey(n.ref)===refKey(c.ref)?{...n,x:c.x,y:c.y,pinned:true}:n)};return {model:project(),view,transient:true};}throw Error('官方网络可免费查阅；请先创建个人副本，再编辑内容。');}
  const before=snapshot,presentation=controller?.capture(),baseView=presentation?strip(presentation):view;let result,source,target,restored,newId;
  if(c.kind==='undo'||c.kind==='redo'){
   source=c.kind==='undo'?undo:redo;target=c.kind==='undo'?redo:undo;if(!source.length)return {model:project(),view};const entry=source.at(-1);result=planGraphInverse(before,entry.inverse);restored=entry.presentation;
  }else if(c.scope==='template'){
   const template=officialGraph.frameworks.find(f=>f.id===c.templateId);if(!template)throw Error('官方示例暂不可用。');newId='fw-'+crypto.randomUUID();const members=[...new Set([...template.core,...template.oneHop])].map(id=>({space:'official',id}));result=planFrameworkCommand(before,{kind:'create',id:newId,title:template.title,members,origin:'template',description:'从已发布术语选入，可自由修改。'},{catalogue,officialGraph});
  }else if(c.scope==='membership-review'){
   result=c.action==='cleanup'?planMembershipCleanup(before,{frameworkId:c.frameworkId,removeRefs:c.removeRefs}):planReviewDecision(before,c);
  }else if(c.scope==='framework'){
   result=planFrameworkCommand(before,c,{catalogue,officialGraph});if(c.kind==='create')newId=c.id;
  }else if(c.scope==='context'){
   if(!framework)throw Error('请先创建框架。');const a=planGraphCommand(before,{kind:'addContext',viewId:view.id,view:baseView,revisionId:c.revisionId,glossaryId:c.glossaryId},{catalogue,officialGraph}),middle=applied(before,a.plan),saved=middle.records.graphViews.find(v=>v.id===view.id),context=saved.contextRefs.find(r=>r.revisionId===c.revisionId&&r.glossaryId===c.glossaryId),b=planFrameworkCommand(middle,{kind:'addMember',id:framework.id,ref:{space:'pending',id:context.id}},{catalogue,officialGraph});result={plan:{writes:[...a.plan.writes,...b.plan.writes],deletes:[],blobRefs:[],impact:[]},inverse:{records:[...a.inverse.records,...b.inverse.records]}};
  }else if(c.kind==='setVisibility'&&!c.visible){
   result=planFrameworkCommand(before,{kind:'removeMember',id:framework.id,ref:c.ref},{catalogue,officialGraph});
  }else{
   if(!framework)throw Error('请先创建框架，再保存位置。');result=planGraphCommand(before,{...c,viewId:view.id,view:c.view||baseView,updatedAt:new Date().toISOString()},{catalogue,officialGraph});
  }
  await store.commit(result.plan,{expectedVersion:before.version,signal:abort.signal});if(disposed)return;
  if(source){source.pop();target.push({inverse:result.inverse,presentation});}else{undo.push({inverse:result.inverse,presentation});redo=[];}
  snapshot=await store.snapshot();if(disposed)return;framework=snapshot.records.frameworks.find(f=>f.id===framework?.id)||null;
  if(newId||!framework){await changeFramework(newId||snapshot.records.frameworks[0]?.id||'');return;}
  view=snapshot.records.graphViews.find(v=>v.id===view.id)||restored&&strip(restored)||baseView;const next={model:project(),view,selection:restored?restored.selected:controller.capture().selected};controller.update(next);updateSidebar();onMessage('框架与画布已保存到本机。');return next;
 }
 function capture(){const value=controller?.capture();return {workspace:controller?.captureWorkspace?.()||workspaceState,sidebarTab,frameworkId:selectedId,view:value?strip(value):view,selection:value?.selected||null,savedView:structuredClone(snapshot?.records.graphViews.find(v=>v.id===view?.id)||null)};}
 const ready=(async()=>{try{const response=await fetch(new URL('./official-graph.json',import.meta.url),{signal:abort.signal});if(!response.ok)throw Error('官方关系暂不可读取');officialGraph=await response.json();}catch(e){if(disposed)return;onMessage('官方示例暂不可读取；私人框架与备份仍可使用。',true);}if(disposed)return;snapshot=await store.snapshot();const id=new URLSearchParams(location.hash.slice(1)).get('framework')||state.frameworkId||snapshot.records.frameworks[0]?.id||snapshot.records.graphViews[0]?.id||(officialGraph.frameworks[0]?'official:'+officialGraph.frameworks[0].id:'');await changeFramework(id,{restore:true});})();
 function dispose(){if(disposed)return;disposed=true;sequence++;sidebar?.dispose();controller?.dispose();abort.abort();signal?.removeEventListener('abort',dispose);}
 async function refreshModel(){if(disposed)return;snapshot=await store.snapshot();if(disposed)return;sidebar?.refreshChoices(savedViewOptions(snapshot.records,officialGraph));if(root.querySelector('form[data-dirty=true]')){onMessage('模型整理已保存；你的未提交输入保留，可完成编辑后重新读取。');return;}if(framework?.publicTemplate){updateSidebar();return;}if(!framework){await changeFramework(snapshot.records.frameworks[0]?.id||'');return;}framework=snapshot.records.frameworks.find(f=>f.id===framework.id)||null;if(!framework){await changeFramework(snapshot.records.frameworks[0]?.id||'');return;}controller.update({model:project(),view:strip(controller.capture())});updateSidebar();}
 signal?.addEventListener('abort',dispose,{once:true});if(signal?.aborted)dispose();return {ready,dispose,capture,refreshModel,updateOrganizer:s=>sidebar?.update({organizerState:s}),officialGraph:()=>officialGraph};
}
