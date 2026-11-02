"""도움말 검색 (로컬 서버용) — web/help.json(README·문서 조각)에서 질문과 맞는 부분을 BM25 로 찾는다.

웹의 help.js 와 같은 방식(한국어 2글자 조각 + 영어 단어). 모델·외부 서비스 없음 → 설치·이미지 크기 그대로.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

HELP_JSON = Path(__file__).resolve().parents[3] / "web" / "help.json"
STOP = {"the", "and", "for", "with", "how", "what", "해", "어떻게", "뭐", "무엇"}


def tokens(text: str) -> list[str]:
    out = []
    for w in re.findall(r"[a-z0-9]+|[가-힣]+", (text or "").lower()):
        if w in STOP:
            continue
        if re.match(r"[가-힣]", w):
            out += [w] if len(w) <= 2 else [w[i:i + 2] for i in range(len(w) - 1)]
        elif len(w) > 1:
            out.append(w)
    return out


@lru_cache(maxsize=1)
def _index(path: str = str(HELP_JSON)):
    docs = json.loads(Path(path).read_text(encoding="utf-8")) if Path(path).exists() else []
    tfs = [Counter(tokens(f"{d['title']} {d['title']} {d['text']}")) for d in docs]
    lens = [sum(t.values()) for t in tfs]
    avg = (sum(lens) / len(lens)) if lens else 1
    df = Counter(w for t in tfs for w in t)
    idf = {w: math.log(1 + (len(docs) - c + 0.5) / (c + 0.5)) for w, c in df.items()}
    return docs, tfs, lens, avg, idf


def search(query: str, k: int = 3, path: str = str(HELP_JSON)) -> list[dict]:
    docs, tfs, lens, avg, idf = _index(path)
    q = set(tokens(query))
    scored = []
    for d, tf, dl in zip(docs, tfs, lens):
        s = sum(idf[w] * tf[w] * 2.4 / (tf[w] + 1.4 * (0.25 + 0.75 * dl / avg)) for w in q if tf.get(w))
        if s > 1:
            scored.append((s, d))
    return [{"title": d["title"], "text": d["text"][:900], "src": d["src"], "score": round(s, 2)}
            for s, d in sorted(scored, key=lambda x: -x[0])[:k]]
