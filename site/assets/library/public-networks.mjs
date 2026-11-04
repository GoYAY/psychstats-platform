// Public networks are projections, never imported into the user's records on view.
export function publicFramework(graph,id){
 const template=graph.frameworks?.find(f=>'official:'+f.id===id);if(!template)return null;
 const core=new Set(template.core),members=[...new Set([...template.core,...template.oneHop])].map(id=>({space:'official',id}));
 return {id,title:template.title,description:'官方预设 · 免费查阅。创建个人副本后可调整成员与关系。',scope:'本主题术语及其已发布的一跳关联；连线沿用官方术语页的知识关系。',publicTemplate:template.id,origin:'template',members,memberDetails:members.map(ref=>({ref,role:core.has(ref.id)?'core':'supporting',reason:core.has(ref.id)?'本主题术语':'已发布的跨主题关联'}))};
}
