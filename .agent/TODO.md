# 코딩 에이전트 할 일 (3dflowhub 본사 엔진이 처리)

`- [ ] (agent)` 항목을 위에서부터 처리합니다. 사람이 직접 적어도 됩니다.
- [x] (agent:대체됨) img2threejs 엔진 연동 (PR #1) — 이름만 추가돼 수정 요청, 아래 가이드 단계 과제로 대체
- [ ] (agent) [p-c73411627e|사이트·UX] AssetFurnace(image-to-3dlab) 파이프라인 검토: 로컬 실행형 올인원 이미지-to-3D 파이프라인인 AssetFurnace 코드를 참조하여 로컬 Apple Silicon 및 PC 환경에서의 텍스처·리깅 파이프라인 완성도를 높입니다.
- [ ] (agent) [guide:img2threejs] 1단계 (PR #1 대체): backend/app/services/engines.py 엔진 목록(available()=(bool, 이유)) + GET /v1/engines, backend/tests/test_core.py 에 테스트
- [ ] (agent) [guide:img2threejs] 2단계 (PR #1 대체): backend/app/services/img2threejs_runner.py build_from_spec(spec_path, out_dir) — 검증·코드 생성 스크립트 실행, 가짜 설치로 테스트
- [ ] (agent) [guide:img2threejs] 3단계 (PR #1 대체): backend/app/main.py POST /v1/jobs/img2threejs-spec + backend/app/schemas.py JobType.img2threejs_spec, 사용 불가 503·잘못된 JSON 400 테스트
- [ ] (agent) [guide:img2threejs] 4단계 (PR #1 대체): README.md 사용법 절 + backend/static/index.html spec 업로드 칸
