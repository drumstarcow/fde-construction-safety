"""遍历源码做 AST 解析，捕获语法错误。"""
import ast, os, sys

root = os.path.join("src", "safety_backend")
bad = []
for dirpath, _, files in os.walk(root):
    if "__pycache__" in dirpath:
        continue
    for f in files:
        if not f.endswith(".py"):
            continue
        p = os.path.join(dirpath, f)
        try:
            ast.parse(open(p, encoding="utf-8").read())
        except SyntaxError as e:
            bad.append(f'{p}: {e}')
print('解析失败：', bad or '无')
sys.exit(1 if bad else 0)
