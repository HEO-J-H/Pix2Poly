"""도움말 색인 만들기: README·docs/*.md 를 제목(##) 단위로 잘라 web/help.json 으로.

웹(브라우저)과 로컬 서버(/v1/help/search)가 같은 색인을 쓴다. 모델·외부 서비스 없이 문서에서 찾기만 한다.
실행: python scripts/build_help.py  (문서를 고친 뒤)
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ["docs/user-guide.md", "docs/pbr-pipeline.md", "README.md", "docs/system-design.md", "docs/gpu-worker.md"]


def sections(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    out, title, buf = [], path.stem, []
    for line in text.splitlines():
        m = re.match(r"^#{1,3}\s+(.+)", line)
        if m:
            if "".join(buf).strip():
                out.append({"title": title, "text": "\n".join(buf).strip(), "src": path.relative_to(ROOT).as_posix()})
            title, buf = m.group(1).strip(), []
        else:
            buf.append(line)
    if "".join(buf).strip():
        out.append({"title": title, "text": "\n".join(buf).strip(), "src": path.relative_to(ROOT).as_posix()})
    return out


def build() -> list[dict]:
    docs = []
    for s in SOURCES:
        p = ROOT / s
        if p.exists():
            docs += [d for d in sections(p) if len(d["text"]) > 40 and "도움말 검색" not in d["title"]]  # 예시 질문이 모든 검색에 걸림
    return docs


if __name__ == "__main__":
    docs = build()
    (ROOT / "web" / "help.json").write_text(json.dumps(docs, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"help.json: {len(docs)} sections")
