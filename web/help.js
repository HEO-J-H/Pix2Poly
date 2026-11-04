// ❓ 도움말 검색 — README·문서(help.json)에서 질문과 가장 맞는 부분을 찾아 보여 줌 (브라우저 안에서만, 전송 없음)
// 한국어는 2글자 조각, 영어는 단어로 나눠 비교 (형태소 분석기·AI 모델 없이도 잘 맞음)
(function () {
  const STOP = new Set(["the", "and", "for", "with", "how", "what", "해", "어떻게", "뭐", "무엇"]);
  function tokens(t) {
    const out = [];
    for (const w of (t || "").toLowerCase().match(/[a-z0-9]+|[가-힣]+/g) || []) {
      if (STOP.has(w)) continue;
      if (/[가-힣]/.test(w)) { if (w.length <= 2) out.push(w); else for (let i = 0; i < w.length - 1; i++) out.push(w.slice(i, i + 2)); }
      else if (w.length > 1) out.push(w);
    }
    return out;
  }
  let docs = null, idf = {};
  async function load() {
    if (docs) return docs;
    docs = await (await fetch("help.json")).json();
    const df = {};
    docs.forEach(d => { d.tf = {}; tokens(d.title + " " + d.title + " " + d.text).forEach(w => d.tf[w] = (d.tf[w] || 0) + 1);
      d.len = Object.values(d.tf).reduce((a, b) => a + b, 0); Object.keys(d.tf).forEach(w => df[w] = (df[w] || 0) + 1); });
    const n = docs.length, avg = docs.reduce((a, d) => a + d.len, 0) / n;
    Object.entries(df).forEach(([w, c]) => idf[w] = Math.log(1 + (n - c + 0.5) / (c + 0.5)));
    docs.forEach(d => d.norm = 1 - 0.75 + 0.75 * d.len / avg);
    return docs;
  }
  function search(q, k = 3) {
    const qs = [...new Set(tokens(q))];
    return docs.map(d => ({ d, s: qs.reduce((s, w) => { const f = d.tf[w] || 0; return s + (f ? idf[w] * f * 2.4 / (f + 1.4 * d.norm) : 0); }, 0) }))
      .filter(x => x.s > 1).sort((a, b) => b.s - a.s).slice(0, k).map(x => x.d);
  }
  const esc = s => s.replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const md = s => esc(s).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/`([^`]+)`/g, "<code>$1</code>").replace(/^\s*[-\d.]+\s+/gm, "• ").replace(/\n/g, "<br>");
  const SAMPLES = ["사진 몇 장 찍어야 해?", "GLB 와 OBJ 차이", "배경 지우기", "사진이 서버로 전송돼?", "반짝이는 물체"];

  const css = document.createElement("style");
  css.textContent = `.helpbtn{position:fixed;top:14px;right:14px;z-index:40;min-height:44px;padding:0 16px;border-radius:999px;border:1px solid var(--line);background:var(--surface);color:var(--text);font:inherit;cursor:pointer;box-shadow:0 4px 16px rgba(0,0,0,.12)}
.helpbtn.inhead{position:static;box-shadow:none;flex:none;align-self:center}
dialog.help{width:min(640px,calc(100vw - 32px));max-height:80vh;border:1px solid var(--line);border-radius:18px;padding:0;background:var(--surface);color:var(--text)}
dialog.help::backdrop{background:rgba(0,0,0,.4)}.help .hd{display:flex;gap:8px;padding:14px;border-bottom:1px solid var(--line)}
.help input{flex:1;min-height:44px;padding:0 14px;border:1px solid var(--line);border-radius:12px;font:inherit;background:var(--bg);color:var(--text)}
.help .bd{padding:6px 16px 16px;overflow:auto;max-height:60vh}.help .chips{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0}
.help .chips button{min-height:36px;padding:0 12px;border-radius:999px;border:1px solid var(--line);background:var(--bg);color:var(--text);font:inherit;font-size:14px;cursor:pointer}
.help article{border-top:1px solid var(--line);padding:12px 0}.help article h3{margin:0 0 4px;font-size:16px}.help small{color:var(--muted)}`;
  document.head.appendChild(css);
  const btn = Object.assign(document.createElement("button"), { className: "helpbtn", type: "button", textContent: "❓ 도움말" });
  btn.setAttribute("aria-haspopup", "dialog");
  const dlg = document.createElement("dialog");
  dlg.className = "help"; dlg.setAttribute("aria-label", "도움말 검색");
  dlg.innerHTML = `<div class="hd"><input type="search" placeholder="궁금한 것을 입력하세요" aria-label="도움말 검색어"><button type="button" class="link" aria-label="닫기">닫기</button></div>
<div class="bd"><div class="chips">${SAMPLES.map(s => `<button type="button">${esc(s)}</button>`).join("")}</div><div class="res" aria-live="polite"></div>
<p><small>README·설계 문서에서 찾은 내용입니다 (새로 지어내지 않음). 질문은 전송되지 않습니다. · <a href="https://github.com/HEO-J-H/Pix2Poly/blob/main/docs/user-guide.md" target="_blank" rel="noopener" title="사진 1장·여러 각도·잘 찍는 법·결과 파일·제한 사항">📖 사용 안내 전체 보기</a></small></p></div>`;
  const head = document.querySelector("header");
  if (head) { btn.classList.add("inhead"); head.appendChild(btn); } else document.body.append(btn);  // 헤더 안에 — 탭을 가리지 않게
  document.body.append(dlg);
  const input = dlg.querySelector("input"), res = dlg.querySelector(".res");
  async function run(q) {
    await load();
    const hits = q.trim() ? search(q) : [];
    res.innerHTML = !q.trim() ? "" : hits.length ? hits.map(d => `<article><h3>${esc(d.title)}</h3><div>${md(d.text.slice(0, 900))}</div><small>${esc(d.src)}</small></article>`).join("")
      : `<p>관련 내용을 찾지 못했습니다. 다른 말로 물어보거나 <a href="https://github.com/HEO-J-H/Pix2Poly/issues" target="_blank" rel="noopener">GitHub 이슈</a>에 남겨 주세요.</p>`;
  }
  let t; input.addEventListener("input", () => { clearTimeout(t); t = setTimeout(() => run(input.value), 150); });
  dlg.querySelectorAll(".chips button").forEach(b => b.onclick = () => { input.value = b.textContent; run(b.textContent); });
  dlg.querySelector(".hd button").onclick = () => dlg.close();
  btn.onclick = () => { dlg.showModal(); input.focus(); };
  window.pix2polyHelp = { tokens, search: async (q, k) => (await load(), search(q, k)) };
})();
