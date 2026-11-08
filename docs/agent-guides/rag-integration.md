# 도움말 검색(RAG) — 결정 기록

**결론: 이미 구현됨. LangChain·LlamaIndex·FAISS+sentence-transformers·llama.cpp 같은 무거운 RAG 는 넣지 않는다.**
(같은 과제가 2026-11 에 열 번 넘게 다시 제안되어 남기는 기록 — 새 제안은 이 문서를 먼저 볼 것)

## 지금 있는 것
| 부분 | 파일 | 하는 일 |
|---|---|---|
| 색인 만들기 | `scripts/build_help.py` | README·docs/*.md 를 제목(##) 단위로 잘라 `web/help.json` |
| 브라우저 검색 | `web/help.js` | 헤더 ❓ 도움말 → 한국어 2글자 조각 + 영어 단어 BM25, 예시 질문, 질문은 전송 안 함 |
| 로컬 서버 검색 | `backend/app/services/help_search.py`, `GET /v1/help/search` | 같은 색인·같은 방식 |
| 테스트 | `backend/tests/test_help_search.py` | 관련 결과·없는 말·엔드포인트 |
| 사용 안내 | `docs/user-guide.md` | 도움말 창에서 링크 |

## 왜 무거운 RAG 가 아닌가
- 공개 사이트(GitHub Pages)는 **서버가 없다** — 서버용 RAG 는 방문자에게 닿지 않는다.
- 답이 문서 안에 있다 — 생성 모델 없이 '찾아서 보여 주기'로 충분하고, 지어낸 답이 나오지 않는다.
- 모델(수백 MB~수 GB)을 넣으면 설치·이미지 크기·기동 시간이 늘고, sentence-transformers 는 PyTorch 가 따라온다.
- 라이선스·의존성이 늘면 Windows 가정용 PC 설치(run.bat)가 깨질 위험이 커진다.

## 다시 검토할 조건
- 문서가 수백 쪽 이상으로 늘어 단어 검색이 자주 빗나갈 때 → 먼저 동의어 사전·제목 가중치를 시도.
- 그래도 부족하면 브라우저에서 도는 작은 임베딩(transformers.js, MIT) 을 선택 기능으로 — 서버 없이.

## 고칠 때
- 문서를 고친 뒤 `python scripts/build_help.py` 로 `web/help.json` 다시 만들기.
- '도움말 검색' 자기 소개 절은 색인에서 뺀다(예시 질문이 모든 검색에 걸림).
