// 웹(브라우저) 높이맵 메시·PBR 계산 단위 테스트 — DOM 이 필요 없는 순수 함수만 (node --test web/tests)
import { test } from "node:test";
import assert from "node:assert/strict";
import { luminance, heightfield, pbrMaps, toOBJ } from "../pix2poly.js";

const W = 8, H = 6, N = W * H;
const ramp = new Float32Array(N * 3);  // 왼쪽 어둡고 오른쪽 밝은 회색 기울기
for (let i = 0; i < H; i++) for (let j = 0; j < W; j++) {
  const v = j / (W - 1), k = (i * W + j) * 3;
  ramp[k] = ramp[k + 1] = ramp[k + 2] = v;
}

test("heightfield: 꼭짓점·삼각형 수, 높이 = 밝기 × 배율, 뒤집기", () => {
  const gray = luminance(ramp, N);
  const m = heightfield(gray, W, H, 0.5);
  assert.equal(m.pos.length, N * 3);
  assert.equal(m.uv.length, N * 2);
  assert.equal(m.idx.length, (W - 1) * (H - 1) * 6);
  assert.ok(Math.abs(m.pos[2]) < 1e-6);                       // 맨 왼쪽(검정) 높이 0
  assert.ok(Math.abs(m.pos[(W - 1) * 3 + 2] - 0.5) < 1e-4);   // 맨 오른쪽(흰색) 높이 = 배율
  const inv = heightfield(gray, W, H, 0.5, true);
  assert.ok(Math.abs(inv.pos[2] - 0.5) < 1e-4);                // 뒤집으면 반대
  assert.ok(Math.max(...m.idx) < N);                           // 삼각형이 범위 밖 점을 가리키지 않음
  assert.ok(m.pos.every(Number.isFinite) && m.uv.every((x) => x >= 0 && x <= 1));
});

test("pbrMaps: 5종 맵 크기·값 범위 0~1, 평평한 회색은 노멀이 위쪽", () => {
  const maps = pbrMaps(ramp, W, H);
  for (const k of ["normal", "roughness", "metallic", "ao"]) {
    assert.ok(maps[k].every((x) => Number.isFinite(x) && x >= 0 && x <= 1), k);
  }
  assert.equal(maps.normal.length, N * 3);
  const flat = new Float32Array(N * 3).fill(0.5);
  const f = pbrMaps(flat, W, H);
  assert.ok(Math.abs(f.normal[2] - 1) < 1e-6);                // 기울기 없으면 노멀 (0.5, 0.5, 1)
  assert.ok(f.roughness.every((x) => x === 0.5));              // 변화가 없으면 중간 거칠기
});

test("toOBJ: v·vt·f 줄 수가 메시와 맞음", () => {
  const m = heightfield(luminance(ramp, N), W, H);
  const lines = toOBJ(m).split("\n");
  assert.equal(lines.filter((l) => l.startsWith("v ")).length, N);
  assert.equal(lines.filter((l) => l.startsWith("vt ")).length, N);
  assert.equal(lines.filter((l) => l.startsWith("f ")).length, m.idx.length / 3);
});
