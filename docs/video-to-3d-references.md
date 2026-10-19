# URL·영상 기반 3D 생성 — 참고 자료 (Pix2Poly)

웹에서 **영상 URL**(또는 직접 `.mp4` 링크)을 받아 프레임을 뽑고, **전통 SfM** 또는 **신경망 기반 단안 영상 재구성**으로 3D를 만드는 흐름을 설계할 때 참고할 수 있는 자료 모음입니다.

## 파이프라인 개요 (제품 관점)

1. **인제스트**: URL에서 영상 파일 확보 (직접 링크, 또는 `yt-dlp` 등으로 스트림 추출 — 라이선스·ToS 준수 필수)
2. **전처리**: `ffmpeg`로 프레임 추출(초당 N프레임), 해상도·길이 상한
3. **재구성 (택일)**  
   - **클래식**: COLMAP SfM + MVS → 메시/포인트클라우드  
   - **신경망(단안 영상)**: 포즈·깊이·4D 표현 학습 후 메시/GS 익스포트
4. **후처리**: 리토폴로지, PBR 베이크, GLB 패키징

---

## 전통 포토그래메트리 (영상 → 프레임 → SfM)

| 자료 | 유형 | 링크 |
|------|------|------|
| **COLMAP** | 오픈소스 SfM+MVS, 공식 문서 | https://colmap.github.io/ |
| **COLMAP** | GitHub | https://github.com/colmap/colmap |
| **Structure-from-Motion Revisited** | 학술 (CVPR 2016) | https://openaccess.thecvf.com/content_cvpr_2016/papers/Schonberger_Structure-From-Motion_Revisited_CVPR_2016_paper.pdf |
| **COLMAP 튜토리얼** | 공식 튜토리얼 (영상 입력 시 프레임 다운샘플링 권고 등) | https://colmap.github.io/tutorial.html |
| **Photogrammetry on GPU (DigitalOcean)** | 블로그/튜토리얼 | https://www.digitalocean.com/community/tutorials/photogrammetry-pipeline-on-a-gpu-droplet |

영상은 **연속 프레임이 너무 많으면** 매칭이 느려지므로, COLMAP 문서에서도 **프레임 레이트 다운샘플링**을 권장합니다.

---

## 단안 RGB 영상 → 밀집/동적 3D (신경망·최근 동향)

| 이름 | 개요 | 프로젝트 / 논문 |
|------|------|-----------------|
| **NeuralRecon** | 단안 영상의 실시간 일관 TSDF 재구성 | [GitHub](https://github.com/zju3dv/NeuralRecon/) · [프로젝트](https://zju3dv.github.io/neuralrecon/) · CVPR 2021 |
| **MonST3R** | 움직임이 있는 장면에서 기하 추정, 동적 포인트 클라우드 | [GitHub](https://github.com/Junyi42/monst3r) · [프로젝트](https://monst3r-project.github.io/) · ICLR 2025 |
| **SLAM3R** | 단안 RGB 영상 실시간 밀집 재구성 | [GitHub](https://github.com/PKU-VCL-3DV/SLAM3R) · CVPR 2025 Highlight |
| **Shape of Motion** | 단일 영상에서 4D 재구성 | [GitHub](https://github.com/vye16/shape-of-motion) · ICCV 2025 Highlight |
| **MoDGS** | 캐주얼 단안 영상 → 동적 가우시안 스플래팅 | [프로젝트](https://modgs.github.io/) · [arXiv](https://arxiv.org/abs/2406.00434) · ICLR 2025 |
| **SplineGS** | 단안 영상 동적 3DGS, COLMAP-free 등 | [arXiv](https://arxiv.org/abs/2412.09982) |
| **video_to_world** | 영상 확산 모델 시퀀스의 3D 월드 재구성 | [GitHub](https://github.com/lukasHoel/video_to_world) · [arXiv](https://arxiv.org/abs/2603.16736) |

GPU 메모리·처리 시간은 모델마다 크게 다릅니다(예: MonST3R README에서 긴 시퀀스 기준 VRAM 언급). 제품에서는 **프레임 수·해상도 상한**이 필수입니다.

---

## 멀티뷰·NVS와의 연결

- **MVSplat** 등 sparse multi-view 3DGS: 영상에서 뽑은 **키프레임 + 추정 포즈**를 묶어 넣는 식으로 연결 가능  
  - GitHub: https://github.com/donydchen/mvsplat  

---

## Pix2Poly에 넣을 때의 실무 체크리스트

- [ ] 저작권·이용약관: 영상 다운로드·재가공 허용 여부  
- [ ] `robots.txt` / 크롤링 정책 (페이지 URL만 줄 때)  
- [ ] SSRF 방지, 파일 크기·길이 제한, 로컬 경로 저장소 분리  
- [ ] 워커에서 `ffmpeg` / (선택) `yt-dlp` / COLMAP 또는 Python 추론 컨테이너 분리  

---

## 관련 키워드 (검색용)

`monocular video 3D reconstruction`, `dynamic gaussian splatting monocular`, `video novel view synthesis`, `SLAM dense mapping RGB`, `structure from motion video frames`
