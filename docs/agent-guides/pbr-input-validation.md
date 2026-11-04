# PBR 맵 생성 — 입력 조건과 오류 처리

`backend/app/services/pbr_generator.py` 의 `validate_pbr_input()` / `generate_pbr_maps()` 기준 (코드가 바뀌면 이 문서도 같이 고칠 것).

## 받는 입력
| 항목 | 조건 | 어디서 확인 |
|---|---|---|
| 파일 | 존재하고 0바이트가 아님 | `validate_pbr_input` |
| 형식 | Pillow 가 열 수 있는 이미지 (PNG·JPEG·WebP·BMP·TIFF 등). 열어서 `verify()` 가 통과해야 함 | `validate_pbr_input` |
| 최소 해상도 | 가로·세로 모두 16px 이상 | `validate_pbr_input` |
| 파일 크기 | 장당 50MB 까지 (업로드 단계) | `main.py` `MAX_IMAGE_BYTES` → HTTP 413 |
| 장 수 | 한 번에 200장까지 (여러 장 업로드) | `main.py` `MAX_FILES` → HTTP 413 |
| URL 수집 | 응답 `Content-Type` 이 `image/` 로 시작해야 함 | `main.py` URL 수집 |

## 처리 방식
- 색 공간: 어떤 입력이든 RGB 로 변환 (투명도·흑백·CMYK 도 RGB 로).
- 해상도: 정사각형으로 맞춤. 512px 보다 크면 **512×512 로 축소**, 가로·세로 모두 512px 보다 작으면 긴 변 크기의 정사각형 (LANCZOS).
  → 비율이 정사각형이 아닌 사진은 늘어나 보일 수 있음. 타일·벽면처럼 반복되는 질감 사진이 가장 잘 맞음.
- 만드는 맵 5종 (`out_dir/pbr/*.png`): albedo(입력 그대로) · normal(밝기 기울기, Sobel) · roughness · metallic · ao.

## 오류와 메시지
| 상황 | 예외 | 사용자에게 보일 것 |
|---|---|---|
| 파일 없음·빈 파일 | `ValueError: PBR input image is empty or does not exist` | 이미지가 비어 있거나 업로드되지 않음 |
| 깨진 파일·이미지 아님 | `ValueError: Invalid or corrupted PBR image file` | 이미지 파일이 손상됐거나 지원하지 않는 형식 |
| 16px 미만 | `ValueError: PBR input image resolution too low (WxH)` | 너무 작은 이미지 — 16×16 이상 |
| 50MB 초과 | HTTP 413 | 파일이 너무 큼 (장당 50MB 까지) |

- 호출하는 곳: `mesh_worker.py` (사진 1장 작업), `video_pipeline.py` (영상에서 대표 프레임). 두 곳 모두 `ValueError` 를
  작업 실패 사유로 기록하므로, 메시지를 바꾸면 화면 문구도 함께 확인할 것.

## 테스트
- 정상: 64×64 PNG → 맵 5개 생성.
- 실패: 0바이트 파일, 텍스트 파일을 .png 로 저장한 것, 8×8 이미지 → 각각 위 `ValueError`.
