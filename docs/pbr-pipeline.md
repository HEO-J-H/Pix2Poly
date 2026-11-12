# PBR 텍스처 만들기 — 웹 버전과 로컬 버전

같은 알고리즘(밝기 → 높이·기울기)을 두 곳에서 돌린다. 어떤 걸 쓸지 고를 때 보는 표.

| | 웹 (브라우저) | 로컬 (FastAPI 서버) |
|---|---|---|
| 코드 | `web/pix2poly.js` (`pbrMaps`) | `backend/app/services/pbr_generator.py` (`generate_pbr_maps`) |
| 설치 | 없음 — https://heo-j-h.github.io/Pix2Poly/ | `run.bat` (Python) |
| 사진 전송 | 없음 (브라우저 안에서만) | 없음 (내 PC 안에서만) |
| 텍스처 크기 | 512×512 | 원본이 512 보다 크면 512, 작으면 긴 변 크기 |
| 만드는 맵 | Base Color·Normal·Roughness·Metallic·AO | 같음 (`out_dir/pbr/*.png`) |
| Normal 세기 | 세부 조정 슬라이더 | `normal_strength` (기본 2.0) |
| 함께 만드는 것 | 높이맵 메시 GLB·OBJ (격자 32~256) | 높이맵 메시 + 선택 엔진(TripoSR·COLMAP·TRELLIS) |
| 입력 검사 | 화면 안내(`friendlyBuildError`) | `validate_pbr_input` — 형식·16px 이상·50MB 이하 |

## 어떻게 만드나 (둘 다)
1. 사진을 정사각형으로 맞춤 → RGB.
2. **Base Color**: 사진 그대로.
3. **밝기(회색)** 를 높이로 보고 Sobel 로 기울기 → **Normal**.
4. 밝기·대비로 **Roughness**(밝을수록 매끈하게 보정), 채도로 **Metallic**(대부분 0 에 가깝게), 주변보다 어두운 곳을 **AO**.

## 잘 나오는 사진
- 정면에서 고르게 비춘 평평한 표면: 벽돌·타일·나무결·천·돌.
- 그림자·반사가 강하면 높이가 틀어짐 → 흐린 날·확산광에서.
- 사진 속 원근이 크면 텍스처가 늘어남 → 정면에서.

## 한계
- 사진 한 장의 밝기로 높이를 추정하므로 실제 깊이와 다를 수 있다 (어두운 색 = 낮다고 봄).
- Metallic 은 추정이 약하다 — 금속 재질은 직접 칠하는 편이 낫다.
- 자세한 입력 조건·오류: `docs/agent-guides/pbr-input-validation.md`, 웹 메모리: `docs/web-optimization.md`.
