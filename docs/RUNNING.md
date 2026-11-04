# 模块与运行说明

## 常态网站

运行 README 中的静态构建和 HTTP 预览命令。`site/dist` 是本地构建产物，不提交。

## 术语 Skill

入口为 `term_explainer/skills/explain-research-term/SKILL.md`。保留同目录全部依赖，由支持 Skill 的宿主加载。它定义教学规则；程序生成另外依赖后台、绘图工具及模型服务。

## 本地知识库与画布组装

静态基础站与知识库前端分别维护。现有组装工具入口：

```powershell
python tools/prepare_local_library_preview.py --help
```

组装工具可指定基础站和输出目录，知识库界面使用 `site/assets/library` 和 `site/library`。请先查看实际参数，再选择本地预览或在线生成模式，避免以历史测试目录作为基础站。

## 生成与自动整理服务

- API：`tools/serve_term_generation.py`。
- 任务执行器：`tools/term_generation_worker.py`。
- 框架整理：`tools/serve_frameworks.py`。
- 配置示例：`deploy/term-generation.env.example`。
- 依赖定义：`tools/requirements-term-generation.in` 及 `.lock`。

锁文件保留开发环境记录，新系统安装后应实际检查兼容性。配置示例默认关闭生成，模型密钥通过服务环境变量配置。

生成还需要中文字体与图示 QA 工具；工具清单在 `deploy/figure-qa-manifest.json`，分发前需核对其来源及许可。没有这些依赖时不要直接开启生成。

服务模板保留既有测试站路径，部署到其他主机时需要修改运行用户、目录、域名、私有存储和限额。首次归档没有自动部署或启用服务。

## 测试范围

完整历史测试集合中有些依赖未随包提供的教材、fixtures、预览目录、浏览器、R 环境或真实服务。实际已执行的适用检查和结果统一记录在 `VERIFICATION.md`。
