"""Verify markdown stripping on simulated LLM output"""
import sys; sys.path.insert(0, ".")
from app.processing_skill import clean_output

llm_output = """## 实验目的

**核心目标**：掌握数字图像的傅里叶变换方法。

*具体内容*：
1. 理解 fft2 和 fftshift 函数的使用
2. 掌握频率域滤波器的设计方法

> 提示：注意频谱的对称性

---

实验结果表明：低频分量集中在中心区域。
"""

cleaned = clean_output(llm_output)
print('=== ORIGINAL (with markdown) ===')
print(llm_output[:200])
print()
print('=== CLEANED (no markdown) ===')
print(cleaned[:200])
print()

for sym in ['**', '*', '`', '# ', '> ', '---']:
    sym_stripped = sym.strip()
    assert sym_stripped not in cleaned, f'Still contains: {sym}'
print('PASS: No markdown symbols remain')
print('Content preserved:', '实验目的' in cleaned and '傅里叶变换' in cleaned)
