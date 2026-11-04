# -*- coding: utf-8 -*-
"""audit_v2.schema —— 常量、枚举与语义约定。

语义硬约束（禁止在后续阶段被弱化）：
  EXACT            chunk 文本在【原始页文本】中逐字命中
  CLEANED_EXACT    chunk 文本在【清洗后页文本】中逐字命中（清洗删除了行）
  OVERLAP_PREFIX   chunk 文本 = 人工拼接的重叠前缀 + 可命中的核心部分
  AMBIGUOUS        同一页内出现多次，无法唯一定位
  NOT_FOUND        未能定位

  traceability_status 只描述「能否定位来源」，绝不描述「OCR 是否正确」。
"""

SCHEMA_VERSION = "1.0"
AUDIT_VERSION = "0.1.0-p0-traceability"
RANDOM_SEED = 42

MATCH_EXACT = "EXACT"
MATCH_CLEANED_EXACT = "CLEANED_EXACT"
MATCH_OVERLAP_PREFIX = "OVERLAP_PREFIX"
MATCH_AMBIGUOUS = "AMBIGUOUS"
MATCH_NOT_FOUND = "NOT_FOUND"

STATUS_BY_METHOD = {
    MATCH_EXACT: "TRACEABLE_EXACT",
    MATCH_CLEANED_EXACT: "TRACEABLE_CLEANED",
    MATCH_OVERLAP_PREFIX: "TRACEABLE_PARTIAL",
    MATCH_AMBIGUOUS: "AMBIGUOUS",
    MATCH_NOT_FOUND: "NOT_FOUND",
}

# 复刻 build_index.py 的清洗规则（只用于定位，不用于改写数据）
import re  # noqa: E402

PAGE_MARKER_RE = re.compile(r"=== 第 (\d+) 页 ===")
CHAP_RE = re.compile(r"^(第[一二三四五六七八九十百]+章)(.*)$")
PAGENUM_RE = re.compile(r"^\s*/?\s*\d{1,3}\s*/?\s*$")
BOOKTITLE = "高级心理统计"

# 负面测试用：旧字段（已知不可信）
LEGACY_OFFSET_FIELD = "offset"
