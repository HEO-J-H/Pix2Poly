/**
 * Pix2Poly 3D viewer
 * - Three.js 0.160 ES module
 * - Blender-like OrbitControls (left/middle = rotate, right = pan, wheel = zoom)
 * - PBR textures (MeshStandardMaterial) loaded from job pbr_paths
 * - SimplifyModifier polygon slider (live decimation in browser)
 * - Texture map panel: Albedo / Normal / Roughness / Metallic / AO
 */
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { OBJLoader } from "three/addons/loaders/OBJLoader.js";
import { SimplifyModifier } from "three/addons/modifiers/SimplifyModifier.js";

// ---------------------------------------------------------------------------
// Module state
// ---------------------------------------------------------------------------

let scene, camera, renderer, controls;
let meshRoot = null;
let originalGeometries = new Map(); // mesh uuid → original BufferGeometry
let raf = null;
let inited = false;
let canvasEl, sectionEl, img2dEl;
let polyCountEl, simplifySliderEl;

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

function disposeObject(obj) {
  if (!obj) return;
  obj.traverse((child) => {
    if (child.geometry) child.geometry.dispose();
    if (child.material) {
      const mats = Array.isArray(child.material) ? child.material : [child.material];
      mats.forEach((m) => {
        Object.values(m).forEach((v) => { if (v && v.isTexture) v.dispose(); });
        m.dispose();
      });
    }
  });
}

function countTriangles(root) {
  let total = 0;
  root.traverse((child) => {
    if (child.isMesh && child.geometry) {
      const idx = child.geometry.index;
      if (idx) {
        total += idx.count / 3;
      } else {
        const pos = child.geometry.attributes.position;
        if (pos) total += pos.count / 3;
      }
    }
  });
  return Math.round(total);
}

function updatePolyCount() {
  if (!polyCountEl || !meshRoot) return;
  polyCountEl.textContent = "삼각형: " + countTriangles(meshRoot).toLocaleString();
}

function fitCameraToObject(group) {
  const box = new THREE.Box3().setFromObject(group);
  if (box.isEmpty()) return;
  const center = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());
  const maxDim = Math.max(size.x, size.y, size.z, 1e-4);
  const dist = maxDim / (2 * Math.tan((camera.fov * Math.PI) / 360));
  const offset = dist * 1.15;
  camera.position.set(
    center.x + offset * 0.75,
    center.y + offset * 0.55,
    center.z + offset
  );
  camera.near = maxDim / 200;
  camera.far = maxDim * 200;
  camera.updateProjectionMatrix();
  controls.target.copy(center);
  controls.update();
}

// ---------------------------------------------------------------------------
// PBR material helpers
// ---------------------------------------------------------------------------

const _texCache = new Map();

function _loadTex(url, colorSpace) {
  if (!url) return null;
  if (_texCache.has(url)) return _texCache.get(url);
  const loader = new THREE.TextureLoader();
  const tex = loader.load(url);
  if (colorSpace) tex.colorSpace = colorSpace;
  _texCache.set(url, tex);
  return tex;
}

function applyPbrMaps(meshRootObj, pbrUrls) {
  if (!pbrUrls || typeof pbrUrls !== "object") return;
  if (pbrUrls.error) return;

  const base = ""; // paths are absolute server URLs already
  const albedoMap    = pbrUrls.albedo    ? _loadTex(pbrUrls.albedo,    THREE.SRGBColorSpace)   : null;
  const normalMap    = pbrUrls.normal    ? _loadTex(pbrUrls.normal,    THREE.LinearSRGBColorSpace) : null;
  const roughnessMap = pbrUrls.roughness ? _loadTex(pbrUrls.roughness, THREE.LinearSRGBColorSpace) : null;
  const metalnessMap = pbrUrls.metallic  ? _loadTex(pbrUrls.metallic,  THREE.LinearSRGBColorSpace) : null;
  const aoMap        = pbrUrls.ao        ? _loadTex(pbrUrls.ao,        THREE.LinearSRGBColorSpace) : null;

  meshRootObj.traverse((child) => {
    if (!child.isMesh) return;
    // UV 없는 메시(사진측량 COLMAP 결과)는 텍스처를 입힐 수 없음 → 정점 색 또는 밝은 회색으로 형태가 보이게
    if (!child.geometry.attributes.uv) {
      if (!child.geometry.attributes.normal) child.geometry.computeVertexNormals();  // 노멀 없으면 조명이 안 받아 까맣게 보임
      const hasColor = !!child.geometry.attributes.color;
      child.material = new THREE.MeshStandardMaterial({ color: hasColor ? 0xffffff : 0xc9c4bc, vertexColors: hasColor,
                                                        roughness: 0.85, metalness: 0, side: THREE.DoubleSide });
      return;
    }
    const mat = new THREE.MeshStandardMaterial({
      side: THREE.DoubleSide,
      vertexColors: false,
    });
    if (albedoMap)    { mat.map = albedoMap; }
    if (normalMap)    { mat.normalMap = normalMap; mat.normalScale.set(1, 1); }
    if (roughnessMap) { mat.roughnessMap = roughnessMap; mat.roughness = 1.0; }
    if (metalnessMap) { mat.metalnessMap = metalnessMap; mat.metalness = 1.0; }
    if (aoMap)        { mat.aoMap = aoMap; mat.aoMapIntensity = 0.8; }

    // Ensure second UV set for AO if needed
    if (aoMap && !child.geometry.attributes.uv2 && child.geometry.attributes.uv) {
      child.geometry.setAttribute("uv2", child.geometry.attributes.uv);
    }

    const old = child.material;
    if (Array.isArray(old)) old.forEach((m) => m.dispose());
    else if (old) old.dispose();
    child.material = mat;
  });
}

function fixVertexColors(gltfScene) {
  gltfScene.traverse((child) => {
    if (!child.isMesh || !child.geometry) return;
    if (child.geometry.attributes.color && child.material) {
      const mats = Array.isArray(child.material) ? child.material : [child.material];
      mats.forEach((m) => { m.vertexColors = true; });
    }
  });
}

// ---------------------------------------------------------------------------
// Polygon decimation
// ---------------------------------------------------------------------------

function storeOriginalGeometries(root) {
  originalGeometries.clear();
  root.traverse((child) => {
    if (!child.isMesh || !child.geometry) return;
    originalGeometries.set(child.uuid, child.geometry.clone());
  });
}

export function applySimplify(ratio) {
  if (!meshRoot || originalGeometries.size === 0) return;
  const modifier = new SimplifyModifier();

  meshRoot.traverse((child) => {
    if (!child.isMesh) return;
    const orig = originalGeometries.get(child.uuid);
    if (!orig) return;

    if (ratio >= 0.99) {
      child.geometry.dispose();
      child.geometry = orig.clone();
    } else {
      const posCount = orig.attributes.position.count;
      const toRemove = Math.floor(posCount * (1.0 - ratio));
      if (toRemove <= 0) {
        child.geometry.dispose();
        child.geometry = orig.clone();
      } else {
        const simplified = modifier.modify(orig.clone(), toRemove);
        simplified.computeVertexNormals();
        child.geometry.dispose();
        child.geometry = simplified;
      }
    }
  });

  updatePolyCount();
}

// ---------------------------------------------------------------------------
// Resize
// ---------------------------------------------------------------------------

function onResize() {
  if (!canvasEl || !canvasEl.parentElement) return;
  const pw = canvasEl.parentElement.clientWidth || 600;
  const ph = Math.max(360, Math.min(580, window.innerHeight * 0.52));
  camera.aspect = pw / ph;
  camera.updateProjectionMatrix();
  renderer.setSize(pw, ph);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
}

// ---------------------------------------------------------------------------
// Render loop
// ---------------------------------------------------------------------------

function animate() {
  raf = requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

function ensureInit() {
  if (inited) return;
  canvasEl        = document.getElementById("viewer-canvas");
  // 지금 화면엔 접히는 섹션이 없음(뷰어가 항상 가운데) — 없으면 숨김 표시만 받는 빈 객체로
  sectionEl       = document.getElementById("viewer-section") || { hidden: false };
  img2dEl         = document.getElementById("viewer-2d-img");
  polyCountEl     = document.getElementById("poly-count");
  simplifySliderEl = document.getElementById("simplify-slider");

  if (!canvasEl || !sectionEl) return;

  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0c0f14);

  const pw = canvasEl.parentElement.clientWidth || 700;
  const ph = Math.max(360, Math.min(580, window.innerHeight * 0.52));
  camera = new THREE.PerspectiveCamera(45, pw / ph, 0.001, 5000);

  renderer = new THREE.WebGLRenderer({ canvas: canvasEl, antialias: true, alpha: false });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(pw, ph);
  if ("outputColorSpace" in renderer) renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.0;

  // Blender-like controls
  controls = new OrbitControls(camera, canvasEl);
  controls.enableDamping = true;
  controls.dampingFactor = 0.06;
  controls.screenSpacePanning = false;
  controls.minDistance = 0.01;
  controls.maxDistance = 5000;
  controls.mouseButtons.LEFT   = THREE.MOUSE.ROTATE;
  controls.mouseButtons.MIDDLE = THREE.MOUSE.ROTATE;
  controls.mouseButtons.RIGHT  = THREE.MOUSE.PAN;

  // Lighting
  const hemi = new THREE.HemisphereLight(0xffffff, 0x2a3038, 0.9);
  const dir1 = new THREE.DirectionalLight(0xffffff, 1.2);
  dir1.position.set(4, 12, 8);
  const dir2 = new THREE.DirectionalLight(0xc8d0e0, 0.4);
  dir2.position.set(-6, -4, -8);
  scene.add(hemi, dir1, dir2);

  window.addEventListener("resize", onResize);
  new ResizeObserver(onResize).observe(canvasEl.parentElement);

  // Simplify slider wiring
  if (simplifySliderEl) {
    simplifySliderEl.addEventListener("input", () => {
      const ratio = parseFloat(simplifySliderEl.value);
      applySimplify(ratio);
    });
  }

  animate();
  inited = true;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export function hideViewer() {
  if (sectionEl) sectionEl.hidden = true;
  if (img2dEl) { img2dEl.removeAttribute("src"); img2dEl.hidden = true; }
  if (meshRoot && scene) {
    scene.remove(meshRoot);
    disposeObject(meshRoot);
    meshRoot = null;
  }
  originalGeometries.clear();
}

export async function updateViewerFromJob(data) {
  ensureInit();
  if (!inited) return;

  if (!data || data.status !== "succeeded" || !data.detail) {
    hideViewer();
    return;
  }

  const outs     = data.detail._output_urls || [];
  const previews = data.detail._preview_urls || [];
  const pbrPaths = data.detail.pbr_paths || {};

  const glbUrl     = outs.find((u) => /\.glb(\?|$)/i.test(u));
  const objFileUrl = outs.find((u) => /\.obj(\?|$)/i.test(u));
  const image2d    = previews[0] || null;

  if (!glbUrl && !objFileUrl) { hideViewer(); return; }

  sectionEl.hidden = false;

  // Update 2D texture panel with albedo (or input image)
  if (img2dEl) {
    const src2d = pbrPaths.albedo ? (window._apiBase || "") + "/" + pbrPaths.albedo.replace(/^\//, "") : image2d;
    if (src2d) {
      img2dEl.src = src2d;
      img2dEl.hidden = false;
      img2dEl.referrerPolicy = "no-referrer";
    } else {
      img2dEl.hidden = true;
    }
  }

  // Build PBR URL map with full server paths
  const apiBase = (window._apiBase || "").replace(/\/$/, "");
  const pbrUrls = {};
  for (const [k, rel] of Object.entries(pbrPaths)) {
    if (k !== "error" && rel) {
      pbrUrls[k] = apiBase + "/" + rel.replace(/^\//, "");
    }
  }

  // Store PBR URLs globally so the texture tab buttons can reference them
  window._currentPbrUrls = pbrUrls;

  // Dispose previous mesh
  if (meshRoot) { scene.remove(meshRoot); disposeObject(meshRoot); meshRoot = null; }
  originalGeometries.clear();

  // Reset simplify slider
  if (simplifySliderEl) simplifySliderEl.value = "1";

  meshRoot = new THREE.Group();

  try {
    if (glbUrl) {
      const loader = new GLTFLoader();
      const gltf = await loader.loadAsync(glbUrl);
      fixVertexColors(gltf.scene);
      meshRoot.add(gltf.scene);
    } else if (objFileUrl) {
      const loader = new OBJLoader();
      const obj = await loader.loadAsync(objFileUrl);
      obj.traverse((child) => {
        if (child.isMesh) {
          child.material = new THREE.MeshStandardMaterial({
            color: 0xcccccc,
            roughness: 0.8,
            metalness: 0.05,
            side: THREE.DoubleSide,
          });
        }
      });
      meshRoot.add(obj);
    }

    // Apply PBR textures if available
    if (Object.keys(pbrUrls).length > 0) {
      applyPbrMaps(meshRoot, pbrUrls);
    }

    storeOriginalGeometries(meshRoot);
    scene.add(meshRoot);
    fitCameraToObject(meshRoot);
    updatePolyCount();
  } catch (e) {
    console.warn("Viewer load failed:", e);
    hideViewer();
  }
}

/**
 * Switch the 2D texture panel to show a specific PBR map.
 * Called from index.html tab buttons.
 */
export function showTexture(mapName) {
  if (!img2dEl) return;
  const urls = window._currentPbrUrls || {};
  const url = urls[mapName];
  if (url) {
    img2dEl.src = url;
    img2dEl.hidden = false;
  }
}
