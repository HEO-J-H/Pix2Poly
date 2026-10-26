// Pix2Poly 웹 버전 — backend/app/services 의 높이맵 메시·PBR 생성 알고리즘을 브라우저로 옮긴 것.
// 이미지는 서버로 보내지 않고 이 페이지 안에서만 처리한다.

// ─────────────── 이미지 → 배열 ───────────────
export function imageToRGB(img, size) {
  const c = document.createElement("canvas");
  c.width = c.height = size;
  const g = c.getContext("2d");
  g.drawImage(img, 0, 0, size, size);
  const d = g.getImageData(0, 0, size, size).data;
  const rgb = new Float32Array(size * size * 3);
  for (let i = 0; i < size * size; i++) {
    rgb[i * 3] = d[i * 4] / 255; rgb[i * 3 + 1] = d[i * 4 + 1] / 255; rgb[i * 3 + 2] = d[i * 4 + 2] / 255;
  }
  return { rgb, w: size, h: size, canvas: c };
}

export function luminance(rgb, n) {
  const g = new Float32Array(n);
  for (let i = 0; i < n; i++) g[i] = 0.2126 * rgb[i * 3] + 0.7152 * rgb[i * 3 + 1] + 0.0722 * rgb[i * 3 + 2];
  return g;
}

// numpy 'reflect' 패딩과 같은 인덱스 (가장자리 값을 반복하지 않음)
function reflect(i, n) {
  if (n === 1) return 0;
  const p = 2 * (n - 1);
  i = ((i % p) + p) % p;
  return i < n ? i : p - i;
}

// ─────────────── 필터 (pbr_generator.py 와 동일) ───────────────
export function sobel(gray, w, h) {
  const gx = new Float32Array(w * h), gy = new Float32Array(w * h);
  const at = (y, x) => gray[reflect(y, h) * w + reflect(x, w)];
  let mx = 1e-6, my = 1e-6;
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const a = at(y - 1, x - 1), b = at(y - 1, x), c = at(y - 1, x + 1);
    const d = at(y, x - 1), f = at(y, x + 1);
    const g = at(y + 1, x - 1), hh = at(y + 1, x), k = at(y + 1, x + 1);
    const vx = (c + 2 * f + k) - (a + 2 * d + g);
    const vy = (g + 2 * hh + k) - (a + 2 * b + c);
    gx[y * w + x] = vx; gy[y * w + x] = vy;
    mx = Math.max(mx, Math.abs(vx)); my = Math.max(my, Math.abs(vy));
  }
  const m = Math.max(mx, my, 1e-6);  // X·Y 같은 값으로 나눠 기울기 비율 유지
  for (let i = 0; i < w * h; i++) { gx[i] /= m; gy[i] /= m; }
  return [gx, gy];
}

export function boxBlur(arr, w, h, r) {
  const k = 2 * r + 1, tmp = new Float32Array(w * h), out = new Float32Array(w * h);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    let s = 0;
    for (let d = -r; d <= r; d++) s += arr[reflect(y + d, h) * w + x];
    tmp[y * w + x] = s;
  }
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    let s = 0;
    for (let d = -r; d <= r; d++) s += tmp[y * w + reflect(x + d, w)];
    out[y * w + x] = s / (k * k);
  }
  return out;
}

const clamp01 = (v) => (v < 0 ? 0 : v > 1 ? 1 : v);

// ─────────────── PBR 맵 (값 0..1, 채널 수 1 또는 3) ───────────────
export function pbrMaps(rgb, w, h, normalStrength = 2.0) {
  const n = w * h, gray = luminance(rgb, n);
  const [gx, gy] = sobel(gray, w, h);
  const normal = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) {
    const x = gx[i] * normalStrength, y = gy[i] * normalStrength, len = Math.sqrt(x * x + y * y + 1) + 1e-8;
    normal[i * 3] = (-x / len + 1) / 2; normal[i * 3 + 1] = (y / len + 1) / 2;  /* OpenGL +Y (glTF·Blender·Unity) */ normal[i * 3 + 2] = (1 / len + 1) / 2;
  }
  const b4 = boxBlur(gray, w, h, 4), rough = new Float32Array(n);
  let dmax = 0;
  for (let i = 0; i < n; i++) { rough[i] = Math.abs(gray[i] - b4[i]); dmax = Math.max(dmax, rough[i]); }
  for (let i = 0; i < n; i++) rough[i] = dmax < 1e-8 ? 0.5 : clamp01((rough[i] / dmax) * 2.5);
  const metal = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const r = rgb[i * 3], g = rgb[i * 3 + 1], b = rgb[i * 3 + 2];
    const mx = Math.max(r, g, b), mn = Math.min(r, g, b), sat = mx > 1e-6 ? (mx - mn) / (mx + 1e-8) : 0;
    metal[i] = clamp01(gray[i] * (1 - sat) * 1.5 - 0.6);
  }
  const ao = new Float32Array(n);
  for (const r of [4, 8, 16]) {
    const bl = boxBlur(gray, w, h, r);
    for (let i = 0; i < n; i++) ao[i] += Math.max(bl[i] - gray[i], 0);
  }
  let amax = 0;
  for (let i = 0; i < n; i++) { ao[i] /= 3; amax = Math.max(amax, ao[i]); }
  for (let i = 0; i < n; i++) ao[i] = 1 - clamp01((amax > 1e-8 ? ao[i] / amax : ao[i]) * 2);
  return { albedo: rgb, normal, roughness: rough, metallic: metal, ao, gray };
}

export function toCanvas(data, w, h, channels) {
  const c = document.createElement("canvas");
  c.width = w; c.height = h;
  const g = c.getContext("2d"), im = g.createImageData(w, h);
  for (let i = 0; i < w * h; i++) {
    for (let k = 0; k < 3; k++) im.data[i * 4 + k] = Math.round(clamp01(data[channels === 3 ? i * 3 + k : i]) * 255);
    im.data[i * 4 + 3] = 255;
  }
  g.putImageData(im, 0, 0);
  return c;
}

// ─────────────── 높이맵 메시 (mesh_from_image.py 와 동일, 화면에서 바로 서도록 y 를 위로) ───────────────
export function heightfield(gray, w, h, heightScale = 0.45, invert = false) {
  const pos = new Float32Array(w * h * 3), uv = new Float32Array(w * h * 2);
  for (let i = 0; i < h; i++) for (let j = 0; j < w; j++) {
    const k = i * w + j, v = invert ? 1 - gray[k] : gray[k];
    pos[k * 3] = (j / (w - 1)) * 2 - 1;
    pos[k * 3 + 1] = 1 - (i / (h - 1)) * 2;
    pos[k * 3 + 2] = v * heightScale;
    uv[k * 2] = j / (w - 1); uv[k * 2 + 1] = 1 - i / (h - 1);
  }
  const idx = new Uint32Array((w - 1) * (h - 1) * 6);
  let t = 0;
  for (let i = 0; i < h - 1; i++) for (let j = 0; j < w - 1; j++) {
    const a = i * w + j;
    idx[t++] = a; idx[t++] = a + w; idx[t++] = a + 1;
    idx[t++] = a + 1; idx[t++] = a + w; idx[t++] = a + w + 1;
  }
  return { pos, uv, idx };
}

export function toOBJ(m) {
  const out = ["# Pix2Poly web — heightfield mesh", "mtllib model.mtl", "usemtl pix2poly"];
  for (let i = 0; i < m.pos.length; i += 3) out.push(`v ${m.pos[i].toFixed(5)} ${m.pos[i + 1].toFixed(5)} ${m.pos[i + 2].toFixed(5)}`);
  for (let i = 0; i < m.uv.length; i += 2) out.push(`vt ${m.uv[i].toFixed(5)} ${m.uv[i + 1].toFixed(5)}`);
  for (let i = 0; i < m.idx.length; i += 3) {
    const a = m.idx[i] + 1, b = m.idx[i + 1] + 1, c = m.idx[i + 2] + 1;
    out.push(`f ${a}/${a} ${b}/${b} ${c}/${c}`);
  }
  return out.join("\n") + "\n";
}
