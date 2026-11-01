#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""知识库语义检索：BM25 + 字符二元组（无需联网、无需依赖）
命中后沿知识图谱做一跳扩展，输出必带引用（条目编号 + 来源）。
"""
import json, math, re, sys
from collections import Counter, defaultdict

import os as _os
BASE = _os.path.dirname(_os.path.abspath(__file__)) + _os.sep
KB = json.load(open(BASE + 'knowledge.json', encoding='utf-8'))
GRAPH = json.load(open(BASE + 'graph.json', encoding='utf-8'))

def toks(s):
    s = re.sub(r'[\s，。；：、（）()【】「」/·—""''?:,.]', '', s)
    bi = [s[i:i+2] for i in range(len(s)-1)]
    uni = [c for c in s if '\u4e00' <= c <= '\u9fff']
    return bi + uni

DOCS = []
for k in KB:
    d = k['title'] + ' ' + k['content'] + ' ' + k['topic'] + ' ' + ''.join(k['rel'])
    DOCS.append((k, toks(d)))

N = len(DOCS)
df = Counter()
for _, t in DOCS: df.update(set(t))
idf = {w: math.log(1 + (N - c + 0.5) / (c + 0.5)) for w, c in df.items()}
avgdl = sum(len(t) for _, t in DOCS) / N
K1, B = 1.5, 0.75

def bm25(q):
    qt = toks(q); score = []
    for k, t in DOCS:
        tf = Counter(t); s = 0.0
        for w in qt:
            if w not in tf: continue
            f = tf[w]; s += idf.get(w, 0) * f * (K1 + 1) / (f + K1 * (1 - B + B * len(t) / avgdl))
        if s > 0: score.append((s, k))
    score.sort(key=lambda x: -x[0])
    return score

NEI = defaultdict(list)
for e in GRAPH['edges']:
    NEI[e['from']].append((e['rel'], e['to']))
    NEI[e['to']].append((e['rel'], e['from']))
LABEL = {n['id']: n['label'] for n in GRAPH['nodes']}

def search(q, topk=3, expand=1):
    hits = bm25(q)[:topk]
    out = []
    for s, k in hits:
        out.append({'score': round(s, 2), 'id': k['id'], 'title': k['title'],
                    'content': k['content'], 'source': k['source'], 'topic': k['topic']})
        if expand:
            rel = []
            for r, t in NEI.get(k['id'], [])[:6]:
                if t in LABEL and t != k['id']: rel.append(f'{LABEL[t]}({r})')
            if rel: out[-1]['related'] = rel
    return out

if __name__ == '__main__':
    qs = sys.argv[1:] or ['整改照片对不上原隐患怎么办', '交接要包含哪些内容才算完成', '模型能不能直接销项']
    for q in qs:
        print('='*60); print('问：' + q)
        res = search(q)
        if not res: print('知识库里没有；不编。'); continue
        for i, r in enumerate(res, 1):
            print(f"[{i}] {r['title']}（{r['id']}·{r['topic']}·来源 {r['source']}·相关度 {r['score']}）")
            print('    ' + r['content'])
            if r.get('related'): print('    关联：' + ' / '.join(r['related'][:4]))