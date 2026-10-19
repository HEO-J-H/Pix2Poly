# GPU 워커 연동 (TripoSR / InstantMesh)

Pix2Poly API 서버(`FastAPI`)는 **가벼운 CPU 메시(heightfield)** 또는 **외부 GPU 환경에서 돌아가는 TripoSR**을 선택할 수 있습니다. TripoSR/InstantMesh는 **PyTorch·CUDA·대용량 가중치**가 필요하므로, 보통 **별도 Python 가상환경 또는 Docker**에 설치합니다.

## 아키텍처

```
[브라우저] → [Pix2Poly FastAPI] → 잡 큐(현재 인메모리) → mesh_worker
                                              ↓
                               PIX2POLY_MESH_BACKEND=triposr 일 때
                                              ↓
                     subprocess: TripoSR의 run.py (별도 venv의 python)
                                              ↓
                     outputs/<job_id>/model.obj, model.glb
```

## 1) TripoSR (권장 첫 단계)

- **저장소**: https://github.com/VAST-AI-Research/TripoSR  
- **논문**: https://arxiv.org/abs/2403.02151  
- **요구사항**: NVIDIA GPU 권장(README 기준 단일 이미지 약 **6GB VRAM** 수준), PyTorch+CUDA, `pip install -r requirements.txt`

### 설치 (요약)

1. TripoSR을 **Pix2Poly 밖의 경로**에 클론 (예: `D:\repos\TripoSR`).
2. 해당 폴더에서 **전용 venv** 생성 후 TripoSR 의존성 설치.
3. `python run.py examples/chair.png --output-dir output/` 로 한 번 수동 실행해 동작 확인.

### Pix2Poly와 연결

환경 변수(또는 시스템 환경 변수)를 설정합니다.

| 변수 | 설명 |
|------|------|
| `PIX2POLY_MESH_BACKEND` | `triposr` 로 설정 |
| `PIX2POLY_TRIPOSR_REPO_PATH` | TripoSR 클론 **절대 경로** ( `run.py` 가 있는 폴더) |
| `PIX2POLY_TRIPOSR_PYTHON` | TripoSR venv의 `python.exe` **전체 경로** (기본값 `python`) |
| `PIX2POLY_TRIPOSR_DEVICE` | 선택. TripoSR `run.py`에 그대로 전달 (예: `cuda:0`, `cpu`). 비우면 `--device` 인자를 붙이지 않음(TripoSR 기본값). `run.bat`/`apply-triposr-env.bat`는 기본으로 `cuda:0`을 넣으며, CUDA가 없으면 TripoSR이 CPU로 폴백함. |

### Windows GPU setup (TripoSR)

1. **드라이버**: 최신 NVIDIA Game Ready / Studio 드라이버.
2. **CUDA Toolkit**: PyTorch **cu124**와 맞추려면 **CUDA 12.4** 툴킷을 권장합니다(예: [CUDA 12.4 설치 파일](https://developer.download.nvidia.com/compute/cuda/12.4.0/local_installers/cuda_12.4.0_551.61_windows.exe)). 13.x만 있으면 `torchmcubes` CMake가 꼬일 수 있습니다. `torchmcubes` 빌드 시 **nvcc**가 필요하고, 빌드 스크립트는 **Ninja**를 써서 Visual Studio에 깔린 CUDA 13용 MSBuild 타깃과 **CUDA 12 nvcc**가 섞이지 않게 합니다.
3. **Visual Studio 2022 Build Tools**: 워크로드 **Desktop development with C++** (이미 CPU용 `torchmcubes` 빌드에 썼다면 동일).
4. **TripoSR venv를 GPU용으로 올리기** (저장소 루트에서):

   ```bat
   scripts\setup-triposr-gpu-windows.bat
   ```

   이 스크립트는 `third_party\TripoSR\.venv`에 **PyTorch cu124** 휠, **CMake 3.27**, **torchmcubes** 빌드에 필요한 도구를 맞추고, `scripts\patch_torch_cuda_nvtx.py`로 PyTorch `cuda.cmake`를 한 줄 패치합니다(외부 프로젝트에서 `find_package(Torch)` 시 **nvtx3**를 CUDA 툴킷 include에서 찾도록). TripoSR venv에서 **PyTorch를 다시 설치**하면 이 패치가 덮어씌워지므로, 그 후에는 같은 스크립트를 다시 실행하거나 `pip-install-torchmcubes-vcvars.bat`만 다시 돌리면 됩니다.

5. **확인** (`third_party\TripoSR`에서 venv 활성화 후):

   ```bat
   python -c "import torch, torchmcubes; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')"
   ```

6. **Pix2Poly 실행**: `run.bat` → `apply-triposr-env.bat`가 `PIX2POLY_TRIPOSR_DEVICE=cuda:0`을 설정합니다. CPU만 쓰려면 `set PIX2POLY_TRIPOSR_DEVICE=cpu` 후 서버 실행.

**Windows PowerShell 예시**

```powershell
$env:PIX2POLY_MESH_BACKEND = "triposr"
$env:PIX2POLY_TRIPOSR_REPO_PATH = "D:\repos\TripoSR"
$env:PIX2POLY_TRIPOSR_PYTHON = "D:\repos\TripoSR\.venv\Scripts\python.exe"
$env:PIX2POLY_TRIPOSR_DEVICE = "cuda:0"
cd C:\Pix2Poly\backend
.\.venv\Scripts\python.exe run_dev.py
```

이후 UI에서 단일 이미지 잡을 올리면, 백그라운드에서 `run.py` 가 호출되고 완료되면 `outputs/<job_id>/model.obj` 등이 생성됩니다.

### 트러블슈팅

- **torchmcubes / CUDA**: TripoSR README의 *Troubleshooting* 참고. Windows에서는 **CUDA 12.4 + cu124 PyTorch + Ninja** 조합을 권장합니다. `CUDA::nvToolsExt` / `nvtx3` CMake 오류가 나면 `scripts\patch_torch_cuda_nvtx.py`가 적용됐는지, `CUDA_PATH`가 12.4를 가리키는지 확인하세요.
- **타임아웃**: `triposr_runner.py` 의 `timeout_s` 는 필요 시 늘리기.
- **경로에 공백**: 가능하면 짧은 경로 사용.

---

## 2) InstantMesh

- **저장소**: https://github.com/TencentARC/InstantMesh  
- **논문**: https://arxiv.org/abs/2404.07191  

실행 커맨드·출력 폴더가 **버전/브랜치마다 다를 수 있어**, 현재 Pix2Poly 저장소에는 **자동 복사 로직을 넣지 않았습니다.** TripoSR과 동일하게 **서브프로세스 + 출력 디렉터리 고정** 패턴으로 `mesh_worker` 에 분기만 추가하면 됩니다.

권장: TripoSR 연동이 안정화된 뒤, 사용 중인 InstantMesh 커밋에 맞춰 `instantmesh_runner.py` 를 포크하여 PR.

---

## 3) Docker (선택)

프로덕션에서는 다음을 권장합니다.

- **API 컨테이너**: Pix2Poly FastAPI만 (CPU 가능).
- **워커 컨테이너**: CUDA 베이스 이미지 + TripoSR 설치, Redis/RQ로 잡 소비.

이 저장소에는 샘플 `Dockerfile` 을 아직 포함하지 않았습니다. 필요 시 `docs/system-design.md` 와 함께 확장하면 됩니다.

---

## 4) 학습·블로그·튜토리얼 (참고)

- TripoSR 공식 README (설치·VRAM·`--bake-texture`)
- Papers With Code: TripoSR 페이지
- COLMAP으로 영상→프레임→SfM 하는 워크플로 (기하 전처리와 병행 시): `docs/video-to-3d-references.md`
