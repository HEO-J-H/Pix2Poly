# Pix2Poly

URL 기반 이미지 분석으로 최적화된 3D 오브젝트와 PBR 텍스처를 생성하는 웹 툴입니다.

## 핵심 목표

- 단일 이미지 기반 3D 생성 (Single Image to 3D)
- 다중 이미지 기반 3D 생성 (Multi-Image to 3D)
- URL 기반 이미지 수집 + 분석 + 3D 생성
- PBR 텍스처 세트 (BaseColor, Normal, Roughness, Metallic, AO 등)
- 실시간 렌더링 친화적 메시 최적화 (리토폴로지, 베이크)

## 구조

- `backend/`: FastAPI 서버 (잡 생성·조회, URL 인제스트)
- `docs/`: 기술 조사 및 시스템 설계

## 빠른 시작

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

- API 문서: `http://localhost:8000/docs`
- 브라우저 테스트 UI: `http://localhost:8000/` → `/ui/` 로 연결 (단일·다중 이미지, URL 인제스트)

업로드 파일은 `backend/uploads/<job_id>/` 에 저장됩니다. (향후 3D 결과물은 `backend/outputs/<job_id>/` 예정)

## API

| Method | Path | 설명 |
|--------|------|------|
| POST | `/v1/jobs/single-image` | 단일 이미지 잡 |
| POST | `/v1/jobs/multi-image` | 다중 이미지 잡 |
| POST | `/v1/jobs/url` | URL에서 이미지 후보 수집 후 잡 |
| GET | `/v1/jobs/{job_id}` | 잡 상태 조회 |

## 참고

- [AeroScan_TwinTex](https://github.com/HEO-J-H/AeroScan_TwinTex)
- [TripoSR (arXiv)](https://arxiv.org/abs/2403.02151)
- [InstantMesh (arXiv)](https://arxiv.org/abs/2404.07191)
- [MVSplat](https://github.com/donydchen/mvsplat)

## URL 수집 시 주의

`robots.txt` 준수, ToS·저작권 확인, rate limit 적용이 필요합니다. 자세한 내용은 `docs/system-design.md`를 참고하세요.
