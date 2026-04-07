# Pix2Poly 기술 조사 요약

## 1) 단일 이미지 → 3D

### 후보

- **TripoSR**: 피드포워드 단일 이미지 3D 재구성, 속도·오픈소스 측면에서 MVP에 적합
- **InstantMesh**: sparse-view 재구성과 결합해 메시 품질 향상

### 제품화

- 출력 표준: GLB/OBJ + 텍스처 번들
- 배경 제거(rembg 등) 전처리 옵션

## 2) 다중 이미지 → 3D

- **3D Gaussian Splatting 계열** (예: MVSplat): sparse multi-view에서 품질·속도 균형
- 객체 중심 vs 장면 중심 파이프라인 분리 검토
- 다중 뷰 시 카메라 포즈 추정·정렬 단계 포함

## 3) URL 기반 이미지

- `img`, `srcset`, `og:image` 등에서 URL 수집
- 상대 경로 정규화, 중복 제거
- **정책**: robots.txt, ToS, 저작권, 요청 제한

## 4) PBR 텍스처

- BaseColor, Normal, Roughness, Metallic, AO, Height 추정
- 필요 시 seamless 처리 및 ORM 패킹 (엔진별)

## 5) 메시 최적화

- 리토폴로지 → 타겟 폴리 수
- 고폴리 → 저폴리 베이크 (Normal/AO 등)
- 웹/모바일/PC 프리셋

## 6) MVP 순서 제안

1. 단일 이미지 파이프라인
2. URL 인제스트 + 이미지 선택
3. 다중 이미지 파이프라인
4. 리토폴로지·베이크 자동화 고도화
