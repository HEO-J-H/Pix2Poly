# Pix2Poly

URL 기반 이미지 분석으로 최적화된 3D 오브젝트와 PBR 텍스처를 생성하는 웹 툴입니다.

**👉 바로 써 보기 (설치 없음): https://heo-j-h.github.io/Pix2Poly/** — 사진 한 장으로 높이맵 3D 메시(GLB·OBJ)와 PBR 텍스처 5종을
브라우저 안에서 만듭니다(이미지는 서버로 전송되지 않음).
**여러 각도 사진 → 하나의 3D (AI)**: 한 제품을 2~4장 찍어 넣으면 공개 AI 데모(TRELLIS, MIT)로 색까지 입힌 GLB 를 만듭니다 —
무료 공유 GPU 라 대기·하루 사용량 제한이 있고, 이 기능만 사진이 Hugging Face 서버로 전송됩니다(동의 후). 설계: `docs/agent-guides/multiview.md`. TripoSR(GPU)·영상 재구성(COLMAP) 같은 고급 기능은 아래 로컬 실행 버전에서 사용합니다.

## 여러 각도 사진 → 하나의 3D, 내 PC에서 (외부 전송 없음)

1. 이 저장소를 내려받아 압축 풀기 (Windows, Python 3.10+)
2. `scripts\install-colmap.bat` — 공식 [COLMAP](https://github.com/colmap/colmap/releases)(BSD) 설치. NVIDIA GPU 가 있으면 CUDA판(정밀 복원), 없으면 일반판(대략적인 형태)
3. `run.bat` → 화면의 **여러 장**에 같은 물체를 돌며 찍은 사진 **5장 이상**(권장 15~40장, 옆 사진과 60% 이상 겹치게)

사진 5장 이상 + COLMAP 이 있으면 자동으로 사진측량(SfM → MVS → Poisson 메시)을 쓰고, 복원된 점이 너무 적으면 결과 대신 이유를 알려 줍니다.

- **색 입히기**: 설치 스크립트가 OpenMVS(AGPL, 별도 실행 파일로만 호출)도 받아 둡니다. 정밀 복원 뒤 사진 색을 텍스처로 입히고, 색을 못 찾은 부분이 25%를 넘으면 복원 점의 색(정점 색) 메시로 대신합니다.
- **배경 지우기**(선택): 화면의 체크 하나 — rembg(MIT, isnet 모델)로 이 PC 에서 처리합니다. 1장은 물체만 남기고(배경 높이 0), 여러 장은 사진마다 마스크를 만들어 물체에서만 특징점을 찾습니다. 모델(약 170MB)은 처음 쓸 때 한 번 내려받습니다.

## 핵심 목표

- 단일 이미지 기반 3D 생성 (Single Image to 3D)
- 다중 이미지 기반 3D 생성 (Multi-Image to 3D)
- URL 기반 이미지 수집 + 분석 + 3D 생성
- PBR 텍스처 세트 (BaseColor, Normal, Roughness, Metallic, AO 등)
- 실시간 렌더링 친화적 메시 최적화 (리토폴로지, 베이크)

## 구조

- `backend/`: FastAPI 서버 (잡 생성·조회, URL 인제스트)
- `scripts/`: **로컬 전용** 실행 스크립트 (Windows)
- `docs/`: 기술 조사 및 시스템 설계 (`video-to-3d-references.md`, **`gpu-worker.md`**: TripoSR GPU 워커 연동)

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

- **uvicorn `--reload` + WatchFiles** 로 `backend/app/` 아래 소스가 바뀌면 서버가 다시 로드됩니다.
- **`backend/static/`(HTML/CSS/JS)은 감시하지 않습니다.** 정적 파일은 저장 후 브라우저에서 새로고침하면 됩니다. `static`까지 감시하면 Windows에서 `index.html` 등이 반복 감지되어 **무한 재시작**에 빠질 수 있습니다.
- 감시 확장자: `.py`, `.html`, `.htm`, `.css`, `.js`, `.json` (위 `app/` 경로 안에서만 적용)
- `.venv`, `uploads/`, `outputs/`, **`static/`** 은 감시하지 않습니다.

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

- 업로드: `backend/uploads/<job_id>/`
- **단일·다중 이미지 잡**: 백그라운드에서 **명도(heightfield) 기반 메시**를 생성해  
  `backend/outputs/<job_id>/model.obj` · `model.glb` 로 저장합니다. 브라우저에서 `/outputs/...` 또는 UI의 다운로드 버튼으로 받을 수 있습니다.  
  (이 방식은 AI 단일뷰 3D가 아니라 **즉시 동작하는 베이스라인**입니다.)  
- **FBX**: 런타임에 FBX 인코더를 넣지 않았습니다. Blender/MeshLab 등에서 OBJ를 가져와 FBX로 내보내면 됩니다.

### TripoSR GPU 워커 (선택)

기본은 CPU **heightfield** 입니다. **TripoSR**을 쓰려면 TripoSR을 별도 클론·설치한 뒤 환경 변수를 설정합니다. 자세한 절차·트러블슈팅은 **`docs/gpu-worker.md`** 를 보세요.

- `PIX2POLY_MESH_BACKEND=triposr`
- `PIX2POLY_TRIPOSR_REPO_PATH` = TripoSR 클론 경로
- `PIX2POLY_TRIPOSR_PYTHON` = TripoSR용 `python.exe` (PyTorch+CUDA)
- `PIX2POLY_TRIPOSR_DEVICE` = 선택 (`cuda:0` / `cpu`; `run.bat`은 기본 `cuda:0`)

Windows에서 GPU용 PyTorch·`torchmcubes` 정렬: `scripts/setup-triposr-gpu-windows.bat`

**InstantMesh** 는 레포마다 출력 경로가 달라 자동 복사 로직은 넣지 않았습니다. 동일 문서에 확장 방법을 적어 두었습니다.

## img2threejs 연동 (선택 엔진)

Claude Code 등에서 `/img2threejs <이미지>` 로 생성한 `spec.json` 을 Pix2Poly 에 업로드하여 Three.js 코드(`createObjectModel.ts`)를 생성할 수 있습니다.

1. 로컬 환경변수 설정: `IMG2THREEJS_HOME=<img2threejs 레포 경로>`
2. API / UI에서 `POST /v1/jobs/img2threejs-spec` 로 `spec.json` 업로드

## API

| Method | Path | 설명 |
|--------|------|------|
| POST | `/v1/jobs/single-image` | 단일 이미지 잡 |
| POST | `/v1/jobs/multi-image` | 다중 이미지 잡 |
| POST | `/v1/jobs/url` | URL에서 이미지 후보 수집 후 잡 |
| POST | `/v1/jobs/video-url` | 영상 URL 잡 (프레임·3D 파이프라인은 워커 연동 예정) |
| POST | `/v1/jobs/img2threejs-spec` | img2threejs 스펙(spec.json) 기반 Three.js 코드 생성 잡 |
| GET | `/v1/engines` | 사용 가능한 엔진 목록 조회 |
| GET | `/v1/jobs/{job_id}` | 잡 상태 조회 |

## 참고

- [AeroScan_TwinTex](https://github.com/HEO-J-H/AeroScan_TwinTex)
- [TripoSR (arXiv)](https://arxiv.org/abs/2403.02151)
- [InstantMesh (arXiv)](https://arxiv.org/abs/2404.07191)
- [MVSplat](https://github.com/donydchen/mvsplat)

## URL 수집 시 주의

`robots.txt` 준수, ToS·저작권 확인, rate limit 적용이 필요합니다. 자세한 내용은 `docs/system-design.md`를 참고하세요.
