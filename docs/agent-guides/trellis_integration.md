# TRELLIS 로컬 GPU 추론(trellis.cpp) 도입 가이드

> 과제에 `[guide:trellis_integration]` 가 붙으면 코딩 에이전트가 이 문서를 읽습니다. 맨 아래 '진행 기록·배운 점'은 작업마다 자동으로 쌓입니다.

## 1. 무엇인가
- **trellis.cpp** (https://github.com/pwilkin/trellis.cpp): Microsoft **TRELLIS.2-4B** 이미지→3D 파이프라인을 GGML 기반 C++ 로 옮긴 단독 실행 프로그램.
  실행 시 Python 불필요, 결과는 **GLB**. Linux·Windows 용 미리 빌드된 실행 파일(CUDA / Vulkan / ROCm)이 릴리스에 있음.
- 가중치: Hugging Face 의 GGUF 변환본 (예: `LocalAI-io/TRELLIS.2-4B-GGUF`, `ilintar/trellis2-gguf`).
- 웹 버전(web/multiview.js)이 쓰는 것은 **TRELLIS(1) 공개 Space** — 이것과 별개. 이 가이드는 **로컬 버전(backend/) 선택 엔진**용.

## 2. 라이선스 (도입 전 반드시 확인)
- 원본 모델 TRELLIS.2: Microsoft 공식 저장소 표기 기준 MIT — GGUF 모델 카드는 원본 라이선스를 따른다고 명시.
- **trellis.cpp 자체 라이선스는 조사 시점(2026-10-26)에 확인 못 함** → 저장소 LICENSE 파일 확인 전에는 코드·바이너리를 저장소에 포함하지 말 것.
  포함하지 않고 "사용자가 직접 설치한 실행 파일 경로"만 설정으로 받는 방식이면 라이선스 영향 없음.

## 3. GPU·환경 요구
- NVIDIA(CUDA), AMD(ROCm), 기타(Vulkan) GPU. 4B 모델 f16 GGUF 는 수 GB 단위 — VRAM 이 부족하면 양자화본 사용.
- **CPU 기본 경로(heightfield)는 항상 그대로 동작해야 함.** GPU·실행 파일이 없으면 이 엔진은 목록에서 숨기거나 "설치 안 됨" 안내.

## 4. 파이프라인 인터페이스 (작게, 테스트 가능하게)
1. `backend/app/` 에 `trellis_cpp.py`: `available() -> bool` (환경변수 `TRELLIS_CPP_BIN` 경로와 모델 파일 존재 확인), `run(image_path, out_glb, timeout) -> Path` (subprocess 호출, 실패 시 한국어 오류).
2. 엔진 목록에 `trellis_cpp` 추가 — `available()` 이 False 면 선택 불가 + 설치 안내 링크.
3. 테스트: subprocess 를 가짜로 바꿔(monkeypatch) 인자 구성·타임아웃·오류 메시지만 검사. **실제 GPU·바이너리를 테스트에 요구하지 말 것.**
4. README 로컬 버전 절에 설치 방법(릴리스 내려받기, GGUF 내려받기, 환경변수 설정) 추가.

## 5. 기대 효과
- 공개 Space 대기열·하루 사용량 제한 없이 로컬에서 반복 생성, 사진이 외부로 나가지 않음(개인정보).
- 품질은 TRELLIS.2 기준 — heightfield(부조) 방식보다 완전한 입체.

## 하지 말 것
- 바이너리·가중치를 저장소에 커밋, 설치 안 된 환경에서 오류로 앱이 멈추게 하기, CPU 기본 경로 변경.

## 출처
- https://github.com/pwilkin/trellis.cpp/wiki · https://huggingface.co/LocalAI-io/TRELLIS.2-4B-GGUF · https://huggingface.co/ilintar/trellis2-gguf · https://github.com/microsoft/TRELLIS

## 진행 기록·배운 점
