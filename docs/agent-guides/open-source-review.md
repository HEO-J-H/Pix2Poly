# 오픈소스 3D 변환 라이브러리 — 라이선스 검토

**목적:** Pix2Poly 에 넣거나 연결할 때 "상업 이용(광고·유료 기능 포함)이 되는가"를 한 장으로 판단.
**원칙:** 기본 설치에는 MIT·Apache-2.0·BSD 만. 그 밖의 것은 사용자가 따로 받는 **선택 기능**으로만, 화면에 라이선스를 알린다.
(법률 자문이 아님 — 실제 유료화 전에는 각 저장소의 LICENSE 원문을 다시 확인할 것. 검토일 2026-11)

## 이미지/영상 → 3D 모델

| 이름 | 코드 | 가중치(모델 파일) | Pix2Poly 판단 |
|---|---|---|---|
| TripoSR | MIT | MIT | ✅ 기본 후보 (`triposr_runner.py`) |
| TRELLIS (Microsoft) | MIT | MIT | ✅ 단, 일부 렌더 의존성(nvdiffrast 등)은 **NVIDIA 비상업 라이선스** → 메시 추출 경로만 사용, 해당 의존성은 선택 설치 |
| InstantMesh | Apache-2.0 | Apache-2.0 | ✅ 후보 |
| Stable Fast 3D / SPAR3D | Stability AI Community License | 같음 | ⚠️ 연 매출 100만 달러 미만 무료 — 선택 기능만 |
| Hunyuan3D-2 | Tencent Hunyuan Community License | 같음 | ❌ 라이선스 적용 지역에서 **대한민국·EU·영국 제외** → 쓰지 않음 |
| COLMAP (사진측량) | BSD-3 | — | ✅ (`colmap_runner.py`) |

## 메시 처리·내보내기

| 이름 | 라이선스 | 판단 |
|---|---|---|
| trimesh | MIT | ✅ 사용 중 |
| Open3D | MIT | ✅ |
| xatlas (UV 펼침) | MIT | ✅ |
| Three.js (웹 뷰어·GLB/OBJ 내보내기) | MIT | ✅ 사용 중 |
| PyMeshLab | GPL-3.0 | ❌ 함께 배포하면 GPL 의무 — 쓰지 않음 |
| Blender (bpy) | GPL | ⚠️ 별도 프로그램으로 실행만(파이프), 코드에 포함하지 않음 |
| rembg (배경 제거) | MIT (U²-Net 가중치 Apache-2.0) | ✅ 사용 중 |

## 새 라이브러리를 넣을 때 확인 순서
1. 코드 LICENSE 와 **가중치 라이선스를 따로** 본다 (코드는 MIT 인데 모델이 비상업인 경우가 흔함).
2. 지역·매출·사용자 수 제한 문구(Territory, revenue, MAU)를 찾는다.
3. 의존성 중 비상업·GPL 이 끼어 있는지 `pip show` / requirements 로 확인.
4. 통과하면 이 표에 한 줄 추가하고, 선택 기능이면 웹 화면에 라이선스 이름을 표시.
