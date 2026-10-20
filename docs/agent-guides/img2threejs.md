# img2threejs 연동 가이드 (코딩 에이전트용)

> 과제에 `[guide:img2threejs]` 가 붙어 있으면 코딩 에이전트가 이 문서를 함께 읽습니다.
> 작업이 끝날 때마다 맨 아래 **진행 기록·배운 점**에 한 줄씩 자동으로 쌓입니다 — 다음 작업은 그 기록을 보고 같은 실수를 피합니다.
> 사람이 언제든 고쳐도 됩니다. 사실이 바뀌면(img2threejs 버전 등) 이 문서부터 고치세요.

## 1. img2threejs 가 무엇인지 (사실)
- 저장소: https://github.com/img2threejs/img2threejs · 라이선스 **Apache-2.0** (상업 이용 가능, 고지 유지)
- 이미지 한 장 → **코드로 된 절차적 Three.js 모델** (`createXxxModel(spec, options)` 가 `THREE.Group` 을 돌려주는 TypeScript 팩토리).
- **서버에서 부르는 엔진이 아니다.** Claude Code·Codex 같은 *비전 기능이 있는 AI 에이전트 안에서* `/img2threejs` 스킬로 돌린다.
  이미지를 보고 설계 스펙(`spec.json`, ObjectSculptSpec)을 만드는 단계에 AI 의 시각 판단이 필요하다.
- 그 뒤 단계는 **표준 라이브러리만 쓰는 파이썬 스크립트** (Python ≥ 3.10, pip 설치 없음):
  - 검증: `python forge/stage2_spec/validate_sculpt_spec.py spec.json --strict-quality`
  - 코드 생성: `python forge/stage3_build/generate_threejs_factory.py spec.json --out createObjectModel.ts`
- GLB 는 기본 출력이 아니다 (별도 플러그인 `img2glb`). → 이번 범위에서 제외.

## 2. Pix2Poly 에서의 설계 (결정 사항)
- **역할 분담:** 사람이 Claude Code 에서 `/img2threejs <이미지>` 로 `spec.json` 을 만든다 → Pix2Poly 에 **spec.json 을 업로드** →
  Pix2Poly 가 검증·코드 생성(stage2 검증, stage3 생성)을 돌려 결과 파일을 내려준다.
- img2threejs 설치 위치는 환경변수 **`IMG2THREEJS_HOME`** (저장소를 클론한 폴더). 없거나 스크립트가 없으면 **사용 불가**.
- **사용 불가일 때 조용히 다른 엔진(heightfield)으로 바꾸지 않는다.** API 는 `503` + 이유(설치 방법)를 돌려준다.
  ← PR #1 이 거절된 이유: 엔진 이름만 받고 실제로는 heightfield 를 돌렸음.
- 외부 스크립트 실행은 `subprocess.run([sys.executable, 스크립트, ...], timeout=120)` 로만, `shell=True` 금지, 경로는 `Path` 로.
- **테스트는 진짜 img2threejs 없이** 돈다: `tmp_path` 에 가짜 `forge/stage2_spec/validate_sculpt_spec.py`·
  `forge/stage3_build/generate_threejs_factory.py` 를 만들어 `IMG2THREEJS_HOME` 을 그 폴더로 지정 (monkeypatch.setenv).

## 3. 단계별 과제 (위에서부터 하나씩 — 각 단계는 테스트 통과로 끝)
1. **엔진 목록 `backend/app/services/engines.py`** — `ENGINES = {"heightfield": ..., "triposr": ..., "img2threejs": ...}` 각 항목에
   `available() -> tuple[bool, str]`(가능 여부, 이유). img2threejs 는 `IMG2THREEJS_HOME` 과 두 스크립트 존재로 판단.
   `GET /v1/engines` 가 `[{name, available, reason}]` 반환. 테스트: 환경변수 없음 → img2threejs available=False + 이유에 'IMG2THREEJS_HOME'.
2. **어댑터 `backend/app/services/img2threejs_runner.py`** — `build_from_spec(spec_path, out_dir) -> dict[str, Path]`:
   검증 스크립트 실행(실패 시 stderr 를 담은 ValueError) → 생성 스크립트로 `out_dir/createObjectModel.ts` 생성 → spec 사본 저장.
   테스트: 가짜 스크립트로 성공(파일 생성)·검증 실패(ValueError)·시간 초과 처리.
3. **API `POST /v1/jobs/img2threejs-spec`** (`backend/app/main.py`) — spec.json 업로드(크기 1MB 제한, JSON 파싱 확인) →
   사용 불가면 503, 가능하면 잡 생성 후 백그라운드로 2단계 실행, 결과 경로를 job detail 에. `JobType.img2threejs_spec` 추가(`schemas.py`).
   테스트: 사용 불가 503, 잘못된 JSON 400, 가짜 설치로 queued.
4. **문서·화면** — README 에 '사용법: Claude Code 에서 /img2threejs → spec.json 을 Pix2Poly 에 업로드' 절, `backend/static/index.html`
   에 spec 업로드 칸(엔진 사용 불가면 안내 문구). (문서·화면은 자동 머지 대상)

## 4. 하지 말 것
- 엔진 이름만 추가하고 실제 처리를 안 하는 변경 (PR #1 실패 원인)
- 테스트에서 네트워크·실제 img2threejs·Node 필요
- img2threejs 코드를 이 저장소로 복사 (설치 위치를 가리키기만 한다)

## 진행 기록·배운 점
- 2026-10-20 PR #1: 엔진 이름만 추가 → 사람이 수정 요청. 교훈: '선택 엔진'은 실제 호출·결과 파일·사용 불가 시 명확한 오류까지가 한 세트.
