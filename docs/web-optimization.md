# 웹 버전(web/) 성능·메모리 가이드

브라우저 안에서만 처리하는 사진 1장 → 부조 3D(`web/index.html`, `web/pix2poly.js`)와 여러 각도 AI(`web/multiview.js`) 기준.
코드를 바꾸면 이 문서도 함께 고칠 것.

## 지금 크기 상한 (연산 부하)
| 단계 | 크기 | 위치 |
|---|---|---|
| 텍스처(PBR 5장) | 512×512 고정 — 원본이 커도 512 로 줄여 계산 | `build()` → `imageToRGB(im, 512)` |
| 메시 격자 | 32~256 (기본 128) — 꼭짓점 = 격자² (256 이면 65,536개) | 세부 조정 슬라이더 `grid` |
| 여러 각도 사진 | 최대 8장 | `mvSet()` |
| 화면 렌더 | `devicePixelRatio` 를 따름 | `resize()` |

- 큰 사진은 `canvas` 에 512 로 그리는 순간 줄어들어 계산량이 사진 크기와 무관.
- 느린 기기에서 멈추면: 메시 해상도(격자)를 낮추는 것이 가장 효과가 큼 (계산·GPU 메모리 모두 격자² 에 비례).
- 메모리 부족 오류(`RangeError`, `allocation`)는 화면에 "메시 해상도를 낮춰 보세요"로 안내 (`friendlyBuildError()`).

## 메모리 관리 규칙
1. **3D 를 바꿔 끼울 때는 `freeMesh()`** — `scene.remove` 만 하면 GPU 메모리가 남는다. 형상(geometry)·재질(material)·
   재질에 붙은 텍스처(map·normalMap·roughnessMap·metalnessMap·aoMap)를 모두 `dispose()`.
   (2026-11-05 수정 전: 형상만 지워 PBR 텍스처 5장(약 5MB GPU)이 다시 만들 때마다 쌓였고, 여러 각도 결과(GLB)는 아예 지우지 않았음)
2. **`URL.createObjectURL` 은 쓰고 나면 `revokeObjectURL`** —
   - 내려받기 링크: 클릭 2초 뒤 해제.
   - 여러 각도 미리보기 썸네일: 새 사진을 넣을 때 이전 주소 해제 (`mvSet()`).
   - 여러 각도 결과 GLB: 새 결과를 받을 때 이전 주소 해제.
   - 사진 1장 목록(`items[].url`)은 목록에 있는 동안 화면에 쓰이므로 유지.
3. 결과(`items[k].result`)는 사진마다 하나만 보관 — 같은 사진을 다시 만들면 덮어씀.

## 점검 방법
- 브라우저 개발자 도구 → Memory/Performance: 같은 사진으로 [3D 만들기]를 10번 눌러도 GPU·JS 힙이 계속 늘지 않아야 함.
- three.js 를 쓰는 코드에서 `renderer.info.memory` 의 `geometries`·`textures` 가 결과 1개 분량(형상 1·텍스처 5)으로 유지되는지.
- 콘솔 오류 없음, 예시 이미지로 3번 연속 생성·여러 각도 예시 2번 넣기 정상 (2026-11-05 확인).

## 더 줄이고 싶을 때 (아직 안 함)
- 계산을 Web Worker 로 옮겨 화면 멈춤 없애기 (`pix2poly.js` 함수는 DOM 을 쓰는 `imageToRGB`·`toCanvas` 만 빼면 그대로 옮길 수 있음).
- `OffscreenCanvas`·`createImageBitmap` 로 이미지 디코딩을 백그라운드에서.
