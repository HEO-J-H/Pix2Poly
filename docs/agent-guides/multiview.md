# 여러 각도 사진 → 하나의 3D (AI) 가이드

> 과제에 `[guide:multiview]` 가 붙으면 코딩 에이전트가 이 문서를 읽습니다. 맨 아래 '진행 기록·배운 점'은 작업마다 자동으로 쌓입니다.

## 1. 지금 구조 (web/multiview.js)
- 브라우저에서 **공개 Hugging Face 데모를 직접 호출** — Pix2Poly 서버·GPU 비용 없음.
- 엔진: **TRELLIS** 다중 이미지 모드 (`trellis-community/TRELLIS` Space, MIT) — 각도 순서 상관없이 2~8장 → 색까지 입힌 **GLB** + 회전 영상.
- 호출: `@gradio/client@2.7.1` 의 `Client.connect(space)` → `/start_session` → `/generate_and_extract_glb`
  (`image`, `multiimages=[{image, caption}]`, `multiimage_algo='stochastic'|'multidiffusion'`, `mesh_simplify`, `texture_size`).
  **`submit()` 반복자는 이 Space 에서 메시지 없이 끝나므로 `predict()` 사용** (2026-10 확인).
- 시험 결과: 예시 버섯 3장 → 약 25~30초, GLB 약 1.5MB.

## 2. 한계와 사용자 안내 (페이지에 반드시 유지)
- **무료 공유 GPU(ZeroGPU)**: 대기열이 있고 방문자(IP)별 하루 사용량이 정해져 있음 — 초과 시 "Try again in HH:MM:SS" 오류 → `friendly()` 로 한국어 안내.
  Hugging Face 로그인 브라우저는 사용량이 늘어남.
- **사진이 Hugging Face 서버로 전송됨** → 동의 체크 없이는 버튼 비활성 (개인정보 안내).
- 공개 Space 는 운영자가 바꾸거나 내릴 수 있음 → 실패 시 원인 문구를 그대로 보여 주고, 대안 엔진으로 바꿀 수 있게 `ENGINE` 한 곳에 모음.

## 3. 대안 엔진 (조사 결과)
| 엔진 | 입력 | 결과 | 라이선스 | 상태 |
|---|---|---|---|---|
| TRELLIS 다중 이미지 (현재) | 2~8장, 순서 무관 | 텍스처 GLB | MIT | Space 실행 중 |
| Hunyuan3D-2mv (`tencent/Hunyuan3D-2mv`) | 앞·뒤·왼·오른쪽 지정 | 형태만 (무채색) — `/shape_generation`, `/generation_all` | Tencent Hunyuan 커뮤니티 (EU·영국·한국 일부 제한) | Space 실행 중 |
| Hunyuan3D 2.1 | 이미지·다중 뷰 | 텍스처 포함 | 위와 같음 | 로컬 VRAM 약 29GB |
| TRELLIS.2 | 공식은 단일 이미지 | — | MIT | 다중 뷰 미지원 |
| COLMAP 사진 측량 (로컬 버전) | 20~50장 | 가장 사실적 | BSD | Pix2Poly 로컬 |

## 4. 다음 단계 후보 (작게, 테스트 가능하게)
1. 엔진 선택 칸: TRELLIS(기본) / Hunyuan3D-2mv(앞·뒤·좌·우 칸 4개) — `ENGINE` 을 목록으로.
2. 사진 품질 점검(브라우저): 너무 작거나 흐린 사진, 같은 사진 중복 경고.
3. 결과 GLB 에 기존 PBR 맵(노멀·거칠기) 덧붙이기 옵션.
4. 실패율 기록: 성공·사용량 초과·기타 오류 횟수를 화면에 (localStorage, 개인용).

## 하지 말 것
- 사용자 동의 없이 사진 전송, 토큰을 페이지에 넣기(공개 저장소), 비상업 라이선스 엔진을 기본값으로.

## 출처
- https://huggingface.co/spaces/trellis-community/TRELLIS · https://github.com/microsoft/TRELLIS
- https://huggingface.co/tencent/Hunyuan3D-2mv · https://github.com/Tencent-Hunyuan/Hunyuan3D-2
- https://triposr.org/blog/hunyuan3d-vs-trellis (2026 비교) · https://trellis2.app/blog/best-image-to-3d-models-huggingface

## 진행 기록·배운 점
- 2026-10-25 웹 연결 완료: 버섯 3장 25초. `submit()` 반복자 대신 `predict()`. 시험을 여러 번 하면 그날 무료 GPU 사용량이 바닥남.
