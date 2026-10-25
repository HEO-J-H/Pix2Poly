// 여러 각도 사진 → 하나의 3D (AI) — 공개 Hugging Face 데모를 브라우저에서 직접 호출 (서버·비용 없음)
// 엔진: TRELLIS (Microsoft, MIT) 의 다중 이미지 모드 — 각도 순서 상관없이 2~4장, 색까지 입힌 GLB.
// 무료 공유 GPU(ZeroGPU)라 대기열·하루 사용량 제한이 있고, 사진은 Hugging Face 서버로 전송된다(페이지에 안내·동의).
// 설계·한계·대안 엔진: docs/agent-guides/multiview.md
// 참고: @gradio/client 2.x 의 submit() 반복자는 이 Space 에서 메시지 없이 끝나 predict() 를 쓴다 (2026-10 확인).
import { Client, handle_file } from "https://cdn.jsdelivr.net/npm/@gradio/client@2.7.1/dist/index.min.js";

export const ENGINE = {
  space: "trellis-community/TRELLIS",
  name: "TRELLIS (Microsoft · MIT)",
  url: "https://huggingface.co/spaces/trellis-community/TRELLIS",
};

/** files: File[] (2~8장). onStatus(text) 로 진행 상황. 결과 {glbUrl, videoUrl, seconds} */
export async function generate(files, onStatus = () => {}, opts = {}) {
  if (files.length < 2) throw new Error("서로 다른 각도의 사진을 2장 이상 넣어 주세요");
  const t0 = performance.now();
  onStatus("AI 서버에 연결 중…");
  const client = await Client.connect(ENGINE.space);
  await client.predict("/start_session", {}).catch(() => {});   // 세션이 필요 없는 버전이면 무시
  const imgs = files.slice(0, 8).map((f) => handle_file(f));
  const tick = setInterval(() => {
    onStatus(`3D 생성 중… ${Math.round((performance.now() - t0) / 1000)}초 (보통 30초~2분, 대기열이 있으면 더 걸려요)`);
  }, 1000);
  let res;
  try {
    res = await client.predict("/generate_and_extract_glb", {
      image: imgs[0],
      multiimages: imgs.map((im) => ({ image: im, caption: null })),
      seed: opts.seed ?? 0,
      ss_guidance_strength: 7.5, ss_sampling_steps: 12,
      slat_guidance_strength: 3, slat_sampling_steps: 12,
      multiimage_algo: opts.algo || "stochastic",   // 'multidiffusion' 은 각도가 고르게 많을 때 더 나을 수 있음
      mesh_simplify: opts.simplify ?? 0.95,
      texture_size: opts.texture ?? 1024,
    });
  } catch (e) {
    throw new Error(friendly(e?.message || String(e)));
  } finally {
    clearInterval(tick);
  }
  const data = res?.data || [];
  const pick = (x) => (x && (x.url || x.video?.url || x.value?.url)) || null;
  const glbUrl = pick(data[1]) || pick(data[2]);
  if (!glbUrl) throw new Error("GLB 결과가 없습니다 — 잠시 후 다시 시도해 주세요");
  return { glbUrl, videoUrl: pick(data[0]), seconds: Math.round((performance.now() - t0) / 1000) };
}

export function friendly(msg) {
  const m = /Try again in ([\d:]+)/.exec(msg);
  if (/quota|ZeroGPU|exceeded/i.test(msg))
    return "무료 GPU 하루 사용량을 다 썼습니다" + (m ? ` (약 ${m[1].split(":").slice(0, 2).join("시간 ")}분 뒤 다시 가능)` : "")
      + ". Hugging Face 에 로그인한 브라우저에서 하면 사용량이 늘어납니다.";
  if (/queue|full/i.test(msg)) return "AI 서버 대기열이 가득 찼습니다. 잠시 후 다시 시도해 주세요.";
  return msg;
}
