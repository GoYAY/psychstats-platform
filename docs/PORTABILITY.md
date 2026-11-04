# 可移植路径与提交身份

项目内部文件根据脚本位置计算路径，运行不依赖原开发者的用户目录。外部材料通过参数或环境变量指定。

## 本地材料配置

| 环境变量 | 默认位置（相对于项目根目录） | 用途 |
| --- | --- | --- |
| `PSY_STATS_OCR_TEXT` | `data/高级心理统计.txt` | OCR 文本审计 |
| `PSY_STATS_RAG_INDEX` | `rag/rag_data/index.pkl` | 检索与切块审计 |
| `PSY_STATS_BASIC_PDF` | `data/basic-textbook.pdf` | 基础教材索引和指定教材集成测试 |
| `PSY_STATS_ADVANCED_PDF` | `data/高级心理统计.pdf` | 高级教材 PDF 审计 |
| `PSY_STATS_DRIFT_PDF` | `data/papers/drift.pdf` | 使用该文献的显式在线验证 |
| `PSY_STATS_DTP_PDF` | `data/papers/dtp.pdf` | 使用该文献的 PDF/生成验证 |
| `PSY_STATS_BROWN_PDF` | `data/papers/brown2011.pdf` | 使用该文献的多来源验证 |

可以指定自己的绝对路径，也可以使用相对于项目根目录的路径。留空时使用默认位置。

```powershell
$env:PSY_STATS_OCR_TEXT = 'materials/my-textbook.txt'
$env:PSY_STATS_RAG_INDEX = 'rag/rag_data/my-index.pkl'
python rag/audit_ocr.py
```

`rag/build_index_basic.py --pdf` 与 `rag/build_index.py --src` 也可直接指定输入。原件和索引不会随仓库提供；依赖特定教材页数或既有任务的集成测试需要自行准备对应材料。

## 工具与部署路径

Windows 下第三方许可目录的完整路径可能较长，使用 Git 下载时为该仓库启用长路径：

```powershell
git -c core.longpaths=true clone https://github.com/GoYAY/psychstats-platform.git
```

OCR 使用当前 Python 环境。字体、绘图 QA 目录、服务器私有存储等使用运行配置。系统字体候选路径和服务器服务模板属于操作系统/部署约定，应按实际主机配置。

在线验证工具可能调用模型，仅在明确准备好材料、凭证和预算时执行。本轮路径测试使用临时目录和测试替身。

## Git 提交身份

维护者使用公开账号名与 GitHub noreply 邮箱提交。重新克隆仓库后，建议在仓库内配置自己的公开姓名和 noreply 邮箱，避免把私人邮箱写入后续提交。
