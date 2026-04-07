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
- `scripts/`: **로컬 전용** 실행 스크립트 (Windows)
- `docs/`: 기술 조사 및 시스템 설계

## 로컬 전용 실행 (권장)

GitHub Pages 없이 **본인 PC에서만** 서버 + 테스트 UI를 띄우는 방식입니다.

1. 저장소 클론 후 `C:\Pix2Poly` (또는 원하는 경로)로 이동
2. 아래 중 하나 실행:
   - **프로젝트 루트에서 더블클릭:** `run.bat` (권장)
   - **또는** `scripts\start-local.bat`
   - **PowerShell:** `cd` 를 저장소 루트로 맞춘 뒤 `.\scripts\start-local.ps1`  
     (실행 정책 오류 시: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`)
3. **`run.bat` / `start-local.bat` 실행 시 약 2초 뒤 브라우저가 자동으로 열립니다.** (안 열리면 직접 `http://127.0.0.1:8000/ui/` 접속)  
   - API 문서: `http://127.0.0.1:8000/docs`
4. 다른 포트: PowerShell에서 `$env:PORT="8080"; .\scripts\start-local.ps1` / CMD에서 `set PORT=8080` 후 `start-local.bat`

`index.html`을 파일로 직접 열면(`file://`) API 호출이 막힐 수 있으므로, **반드시 위 주소로 접속**하세요.

## 파일 저장 시 자동 재시작 (hot reload)

`run.bat` / `scripts\start-local.*` 는 내부에서 **`backend/run_dev.py`** 를 실행합니다.

- **uvicorn `--reload` + WatchFiles** 로 `backend/app/` · `backend/static/` 아래 파일이 바뀌면 서버가 다시 로드됩니다.
- 감시 확장자: `.py`, `.html`, `.htm`, `.css`, `.js`, `.json`
- `.venv`, `uploads/`, `outputs/` 는 감시 경로에서 빼 두었습니다 (전체 `backend/` 대신 `app/` + `static/` 만 감시).

### (선택) nodemon으로 프로세스 전체 재시작

Node가 있다면 저장 시 **uvicorn 프로세스를 통째로 다시 띄우는** 방식입니다. (`run_dev.py`보다 무겁고, 보통은 `run_dev.py`만으로 충분합니다.)

```bash
npm install
npm run dev:nodemon
```

`nodemon.json` 은 Windows 기준으로 `backend` 에서 venv의 `uvicorn` 을 실행합니다. macOS/Linux에서는 `backend/run_dev.py` 사용을 권장합니다.

## 수동 실행 (동일 동작)

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python run_dev.py
```

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
