const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!=null)n.textContent=text;if(cls)n.className=cls;return n;};
const link=(text,href)=>{const a=el('a',text);a.href=href;return a;};
export function mountGuide(root,{onlineGeneration=false}={}){
 const guide=el('article',null,'library-guide'),intro=el('header',null,'library-guide-intro');
 intro.append(el('p','使用指南','guide-eyebrow'),el('h2','把一个新概念，放进你的知识网络'),el('p','先免费浏览官方网络；遇到想深入理解的新术语，再生成科普、保存文献，逐步积累自己的知识。'));guide.append(intro);
 const access=el('section',null,'guide-access');access.setAttribute('aria-label','免费功能与模型生成');
 const free=el('div');free.append(el('h3','免费查阅与管理'),el('p','官方10个主题的知识网络和术语科普均可免费查阅。阅读已有内容、手动创建框架或简短笔记、整理成员、导入与导出备份，也不会发起模型请求。'),link('打开官方知识网络','#view=network&framework=official:foundations'));
 const generated=el('div');generated.append(el('h3','模型生成个人知识'),el('p','新术语的完整科普、图示与自动知识整理需要调用模型。当前先验证产品功能，不接入收款；手动整理和重复阅读已有内容不发起模型请求。'),el('p',onlineGeneration?'当前为邀请内测：在“生成科普”中验证邀请，提供术语和可选文献后提交。任务在后台处理，可稍后领取并保存到本机；框架自动整理需要另行确认摘要发送范围。':'当前站点尚未启用在线生成。可导入已生成的科普包；本机自动整理需配置本机模型服务，并明确同意后才能使用。','guide-service-status'));access.append(free,generated);guide.append(access);
 const starting=el('section',null,'guide-start');starting.append(el('h3','任何领域的术语，都可以成为起点'),el('p','至少提供术语名称。最好补充英文名、你所指的定义或使用场景，以及相关文献；同名概念会先确认语境，避免把其他领域的含义混进来。'));
 const example=el('blockquote','“我想理解‘元认知’。请结合我提供的文献，解释它的含义、具体表现和使用情境，并给出可读的图示与相关概念。”');starting.append(example);
 const material=el('dl',null,'guide-materials');for(const [title,copy] of [
  ['仅有名称','先提示补充定义或文献；仍没有文献时，征得同意后检索公开来源，并请你确认目标概念。'],
  ['提供一篇文献','先辨认该术语在论文中的位置与含义，提取直接相关的部分，再按需要追读参考文献与必要补充材料。'],
  ['提供多篇文献','比较定义、适用条件和文献之间的关系，围绕术语整合解释；正文保持简洁，来源留在知识库中便于追溯。']
 ])material.append(el('dt',title),el('dd',copy));starting.append(material);guide.append(starting);
 const pages=el('section',null,'guide-pages');pages.append(el('h3','这几个页面，分别怎么用'));const grid=el('div',null,'guide-page-grid');
 for(const page of [
  {view:'list',title:'术语',purpose:'检索和阅读已经保存的个人知识。',steps:['在名称、别名和正文中搜索，或用标签缩小范围。','打开科普阅读定义、现实例子、图示、公式与理解练习；点击正文中的强调词查看简释或跳转。','导入科普包保存内容；“更新已有科普”先展示修订差异，确认后采用，旧修订与批注仍保留。']},
  {view:'works',title:'文献',purpose:'集中查找术语背后的来源与原件。',steps:['按题名、作者或DOI检索，按年份与原件状态筛选。这里的文献检索针对书目信息。','展开条目查看归档来源；有本机原件时可以打开或下载。','删除原件前查看影响范围；书目信息与其他术语仍需要的共享文件会按提示保留。']},
  {view:'network',title:'知识关系',purpose:'从一个概念看见它在框架中的位置。',steps:['右栏顶部切到“框架”，选择官方网络或自己的框架；切回“术语”后检索并选择节点。','默认展示一个代表术语的局部关系。点击质点、关联框或列表项，所选术语会聚焦到可见区域中心并展开一跳关系；保持当前缩放，背景不做长距离平移。再次点击选中节点或按Esc收起。','拖动空白平移、滚轮缩放；也可使用放大、缩小和适应全图。右栏可以收起，留下完整画布；窄屏选择术语后会收起右栏，点击“术语栏”可重新打开。','官方网络可点击阅读、拖动节点，或用方向键调整当前查看布局；这些调整不改动官方内容。需要保存个人布局、添加成员、手动连线及填写关系说明时，可先创建免费个人副本。','模型自动整理须先授权：它可以推荐框架、补充简释和推断关联。推断会保留标识，可修改、撤销或移除；未建全文的节点会提示“详细科普页尚未建立”。']},
  {view:'trash',title:'回收区',purpose:'恢复误删术语，或确认永久删除。',steps:['术语移入回收区后，可在这里恢复。','永久删除会提示修订、批注和文献的影响范围；确认前先做完整备份。已下载的旧备份不会随之删除。']},
  {view:'backup',title:'备份与设置',purpose:'保存、迁移和离线阅读你的积累。',steps:['定期下载“私人完整备份（含原文）”；换设备或浏览器时，用导入功能恢复。','Markdown阅读导出便于在Obsidian等工具中阅读，且可选择附带原件；阅读导出不包含私有证据记录，恢复本库请使用完整备份。','外部Markdown可以导入为个人笔记。需要离线阅读时，先联网启用并完成资源缓存。','可请求浏览器保留本机资料。完整删除本库需两次确认，只影响当前环境，不会删除官方内容或已下载的备份。']}
 ]){
  const section=el('section',null,'guide-page');section.append(el('h4',page.title),el('p',page.purpose,'guide-purpose'));const list=el('ul');for(const step of page.steps)list.append(el('li',step));section.append(list);const a=link('进入'+page.title,'#view='+page.view);a.dataset.guidePage=page.view;section.append(a);grid.append(section);
 }pages.append(grid);guide.append(pages);
 const privacy=el('section',null,'guide-privacy');privacy.append(el('h3','你的资料保存在哪里？'),el('p','术语、文献原件、批注和个人网络保存在当前网站地址下的当前浏览器中，不会自动跨设备同步。更换浏览器、清理网站数据或使用不同站点地址时，需要用完整备份迁移。'),el('p','普通查阅和手动整理在本机完成。授权模型服务后，生成任务会发送必要资料；当前框架自动整理发送术语名称、操作定义、必要摘要与已有关系，不发送PDF原件、证据原文或批注。提交任务前请核对发送范围。'));guide.append(privacy);root.append(guide);
}
