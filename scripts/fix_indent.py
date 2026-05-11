"""修复 ui_main.py 中的所有缩进错误"""
import re

with open('E:/Cursor/Project/projects/ai-doc-processor/app/ui_main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 修复所有 `                xxx` (16空格) 应该是 `        xxx` (8空格) 的情况
# 模式：在方法内部（前面有 def 或 8空格缩进代码），顶级缩进应该是8空格
lines = content.split('\n')
fixed = 0
for i in range(len(lines)):
    stripped = lines[i].lstrip()
    if not stripped:
        continue
    # 计算当前缩进
    indent = len(lines[i]) - len(stripped)
    # 如果是16空格缩进但在方法内部（前一行是8空格缩进），改成8空格
    if indent == 16:
        # 查找上一个非空行
        prev = i - 1
        while prev >= 0 and not lines[prev].strip():
            prev -= 1
        if prev >= 0:
            prev_indent = len(lines[prev]) - len(lines[prev].lstrip())
            if prev_indent <= 8:
                lines[i] = '        ' + stripped
                fixed += 1

result = '\n'.join(lines)
with open('E:/Cursor/Project/projects/ai-doc-processor/app/ui_main.py', 'w', encoding='utf-8') as f:
    f.write(result)
print(f'Fixed {fixed} lines')
