# -*- coding: utf-8 -*-
"""audit_v2.detectors —— OCR 形式特征检测器（只读，不判断 OCR 正确性）。

硬性语义约束：
  * triggered 只表示「检测到某种形式特征」
  * confidence 只表示「检测器对该形式特征本身的把握」
  * severity_hint 只表示「人工审核优先级提示」
  三者都【不表示】OCR 是否正确；本层不产生 risk score，不做 PASS/FAIL。
"""
