# 首次归档验证

日期：2026-11-05（Asia/Shanghai）。对象：从本地开发目录整理的私有仓库初始副本。

| 检查 | 本次结果 |
| --- | --- |
| 白名单原文件复制 | 1,655 份逐文件 SHA-256 与源文件一致 |
| Python 语法 | 345 个文件可解析；历史审计脚本文档字符串有一项转义警告 |
| 常态网站构建 | `python site/build.py --mode public --check` 通过：90 页、15 个术语、15 个问题、7 个数据集 |
| 知识库与画布测试 | `node --test tests/library/*.test.mjs`：222/222 通过 |
| 术语合同、框架与模型请求协议测试 | `python -m unittest tests.term_explainer.test_contract tests.term_explainer.test_frameworks_v2 tests.term_explainer.test_frameworks tests.term_explainer.test_deepseek_wire`：43/43 通过，使用测试替身 |
| 常见凭证格式与目录筛查 | 见本次交付文件清单；未纳入真实配置、账本、原文、教材页图片或索引 |

画布首次检查缺少一份合成测试 JSON；补入 `tests/fixtures/framework-semantics.json` 后，上述画布测试全部通过。

新增归档文档与忽略规则单独提供。构建所需图表指纹记录从既有记录提取四个校验字段，保留原图表 SHA 与来源指纹，移除本机路径等审计详情。其余所选原文件保持字节一致。

`.gitattributes` 禁止 Git 自动转换换行，保留已有构建指纹对应的源文件字节。`CHECKSUMS.sha256` 列出归档文件校验值。

本次未运行付费模型、OCR全流程、全文索引重建、浏览器视觉检查、R重算或服务器部署。完整历史测试中依赖教材和运行环境的部分留待对应环境执行。

在线源码对应关系：上传对象为本地当前源码。实际服务器版本及服务器侧独立修补需在后续部署前核对。
