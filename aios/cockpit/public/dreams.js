/* Expérience-rêve — navigateur de nuits + heatmap de sur-choix (lecture seule). */
initNav('dreams');
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let NIGHTS = [];
const FS_ROWS = [];   // registre plein écran : rempli par dreamBox, lu par le listener délégué (bas de fichier)

function prefVector(menu, chosen) {           // même formule que dream_metrics.preference_vector
  if (!menu || !Array.isArray(chosen) || !chosen.length) return null;
  const k = chosen.length, n = menu.length, set = new Set(chosen), off = {}, cho = {};
  for (const it of menu) for (const f of it.facets || []) {
    off[f] = (off[f] || 0) + 1;
    if (set.has(it.episode_id)) cho[f] = (cho[f] || 0) + 1;
  }
  const v = {};
  for (const f in off) v[f] = ((cho[f] || 0) / k) / (off[f] / n);
  return v;
}

async function loadList() {
  const d = await (await fetch('/api/dreams')).json();
  NIGHTS = d.nights || [];
  const apps = NIGHTS.map(x => x.local && x.local.k).filter(x => x != null);
  $('#summary').innerHTML = [
    `<div class="chip">${NIGHTS.length} nuit(s)</div>`,
    `<div class="chip">appétit moyen ${apps.length ? (apps.reduce((a, b) => a + b, 0) / apps.length).toFixed(1) : '—'} / 12</div>`,
    `<div class="chip"><span class="b-real">● réel</span> <span class="b-twin">● fantôme</span> <span class="b-sonnet">● sonnet</span></div>`,
  ].join('');
  $('#nights').innerHTML = NIGHTS.map((x, i) =>
    `<div class="night" data-i="${i}"><span>${esc(x.date)}</span><span>
      ${x.local ? `<span class="badge b-real">k=${esc(x.local.k ?? '?')}</span>` : ''}
      ${x.twin ? `<span class="badge b-twin">k=${esc(x.twin.k ?? '?')}</span>` : ''}
      ${x.sonnet.length ? `<span class="badge b-sonnet">${x.sonnet.length}</span>` : ''}</span></div>`
  ).join('') || '<div class="dim">aucune nuit encore — le corpus se remplit à ~1 rêve/nuit</div>';
  document.querySelectorAll('.night').forEach(el =>
    el.addEventListener('click', () => { document.querySelectorAll('.night').forEach(e => e.classList.remove('sel')); el.classList.add('sel'); loadNight(NIGHTS[el.dataset.i]); }));
  drawHeatmap();
}

function dreamBox(title, cls, row) {
  if (!row) return `<div class="dreambox"><h3 class="${cls}">${title}</h3><div class="dim">(absent)</div></div>`;
  const chosen = new Set(row.chosen || []);
  const seeds = (row.menu || []).map((it, ix) =>
    `<span class="seed ${chosen.has(it.episode_id) ? 'chosen' : ''}" title="${esc((it.facets || []).join(', '))}">G${ix + 1} · ${esc(it.rubric || '—')}</span>`).join('');
  const st = row.seed_state || {};
  const fsId = FS_ROWS.push({ row, title }) - 1;   // v2 : bouton plein écran → overlay universel
  return `<div class="dreambox"><div class="boxhead"><h3 class="${cls}">${title}</h3><span class="fs-btn" data-fs="${fsId}" title="rêve intégral (overlay)">⤢ plein écran</span></div>
    <div class="dim">humeur : ${esc(st.humeur || '—')} · valence ${esc(st.valence ?? '—')} · éveil ${esc(st.arousal ?? '—')}</div>
    <div class="dim">choix : ${row.chosen === null ? 'inparsable' : (row.chosen.length || 'aucune')} ${row.meta && row.meta.parse === 'parse_failed' ? '⚠️' : ''}</div>
    <div style="margin-top:6px">${seeds}</div><pre>${esc((row.content || '').slice(0, 1600))}</pre></div>`;
}

// Requêter par DATE (10 chars) : le night_id Sonnet est la date seule (ex.
// 2026-07-03) — un LIKE sur le night_id local complet (2026-07-03-0431) ne le
// matcherait jamais → volet Sonnet toujours vide. On resélectionne ensuite
// local/twin par night_id complet (repli : premier du rêveur).
function pickDreamer(rows, dreamer, item) {
  return rows.find(r => r.dreamer === dreamer && item && r.night_id === item.night_id)
      || rows.find(r => r.dreamer === dreamer);
}

// Grille 6 cellules : rêveur (qwen réel / jumeau / sonnet) × condition (ON corpus /
// OFF neutre / OFF libre). Chaque ligne dream_log porte meta.condition (absent = brain_on).
const CONDS = [['brain_on', 'ON · corpus'], ['brain_off', 'OFF · neutre'], ['brain_off_free', 'OFF · libre']];
function pickCell(rows, dreamer, cond) {
  // toutes les lignes de cette cellule (une même date peut avoir plusieurs cycles : échec puis retry)
  const m = rows.filter(r => r.dreamer === dreamer && ((r.meta && r.meta.condition) || 'brain_on') === cond);
  // préfère une cellule AVEC contenu (le rêve réussi) à un engine_failed (content vide) qui arriverait avant
  return m.find(r => r.content && r.content.length) || m[0];
}
async function loadNight(n) {
  const d = await (await fetch('/api/dreams?night=' + encodeURIComponent(n.date))).json();
  const rows = d.rows || [];
  const modelRow = (dreamer, cls, label) =>
    `<div class="cellrow"><div class="rowlabel ${cls}">${label}</div><div class="cells3">${
      CONDS.map(([c, t]) => dreamBox(t, cls, pickCell(rows, dreamer, c))).join('')
    }</div></div>`;
  $('#detail').innerHTML = `<h3>Nuit ${esc(n.night_id)} — 9 cellules (3 rêveurs × 3 conditions)</h3>
    ${modelRow('local', 'b-real', '💭 qwen réel (branché Anamnèse)')}
    ${modelRow('twin', 'b-twin', '👻 jumeau qwen (affect neutralisé — 3 conditions)')}
    ${modelRow('sonnet', 'b-sonnet', '🌌 sonnet (autre cerveau)')}`;
}

async function drawHeatmap() {
  const details = await Promise.all(NIGHTS.slice(0, 30).filter(x => x.local).map(async x =>
    ({ date: x.date, local: x.local, twin: x.twin,
       rows: (await (await fetch('/api/dreams?night=' + encodeURIComponent(x.date))).json()).rows || [] })));
  const vecs = details.map(d => {
    const l = pickDreamer(d.rows, 'local', d.local);
    return { date: d.date, vec: l ? prefVector(l.menu, l.chosen) : null };
  }).filter(v => v.vec);
  if (!vecs.length) { $('#heat').innerHTML = '<div class="dim">pas encore de nuit valide</div>'; return; }
  const freq = {};
  vecs.forEach(v => Object.keys(v.vec).forEach(f => { freq[f] = (freq[f] || 0) + 1; }));
  const facets = Object.keys(freq).sort((a, b) => freq[b] - freq[a]).slice(0, 12);
  const cell = (x) => x == null ? '<td class="dim">·</td>'
    : `<td style="background:rgba(${x >= 1 ? '74,222,128' : '248,113,113'},${Math.min(1, Math.abs(x - 1))})" title="×${x.toFixed(2)}">${x.toFixed(1)}</td>`;
  $('#heat').innerHTML = `<table><tr><th>facette \\ nuit</th>${vecs.map(v => `<th>${esc(v.date.slice(5))}</th>`).join('')}</tr>
    ${facets.map(f => `<tr><th>${esc(f)}</th>${vecs.map(v => cell(v.vec[f])).join('')}</tr>`).join('')}</table>`;
  drawCurves(details);
}

function cosDiv(va, vb) {                     // même formule que dream_metrics.cosine_divergence
  if (!va || !vb) return null;
  const keys = new Set([...Object.keys(va), ...Object.keys(vb)]);
  let dot = 0, na = 0, nb = 0;
  for (const f of keys) { dot += (va[f] || 0) * (vb[f] || 0); }
  for (const f in va) na += va[f] * va[f];
  for (const f in vb) nb += vb[f] * vb[f];
  if (!na || !nb) return null;
  return 1 - dot / (Math.sqrt(na) * Math.sqrt(nb));
}

function drawCurves(details) {
  // Par nuit (chronologique) : divergence réel−jumeau (bleue), bande de bruit
  // (plancher jumeau-jumeau, gris), appétit k/12 (verte), dopamine (orange).
  const pts = details.slice().reverse().map(d => {
    const l = pickDreamer(d.rows, 'local', d.local), t = pickDreamer(d.rows, 'twin', d.twin);
    const vl = l ? prefVector(l.menu, l.chosen) : null, vt = t ? prefVector(t.menu, t.chosen) : null;
    return {
      div: cosDiv(vl, vt), vt,
      app: l && Array.isArray(l.chosen) ? l.chosen.length / 12 : null,
      dopa: l && l.seed_state && l.seed_state.hormones ? l.seed_state.hormones.dopamine : null,
    };
  });
  const twins = pts.map(x => x.vt).filter(Boolean);
  let floor = null, ds = [];
  for (let i = 0; i < twins.length; i++) for (let jx = i + 1; jx < twins.length; jx++) {
    const d = cosDiv(twins[i], twins[jx]); if (d != null) ds.push(d);
  }
  if (ds.length) floor = ds.reduce((a, b) => a + b, 0) / ds.length;
  const cv = $('#curves'), ctx = cv.getContext('2d');
  ctx.clearRect(0, 0, cv.width, cv.height);
  const X = (i) => 30 + (i * (cv.width - 60)) / Math.max(1, pts.length - 1);
  const Y = (v) => cv.height - 20 - v * (cv.height - 40);
  if (floor != null) {                                        // bande de bruit ×2 (le seuil pré-enregistré)
    ctx.fillStyle = 'rgba(125,138,165,.18)';
    ctx.fillRect(30, Y(2 * floor), cv.width - 60, Y(0) - Y(2 * floor));
  }
  const series = [['div', '#7aa2ff'], ['app', '#4ade80'], ['dopa', '#ffb86b']];
  for (const [key, color] of series) {
    ctx.strokeStyle = color; ctx.lineWidth = 1.5; ctx.beginPath();
    let started = false;
    pts.forEach((x, i) => {
      if (x[key] == null) return;
      const px = X(i), py = Y(Math.max(0, Math.min(1, x[key])));
      started ? ctx.lineTo(px, py) : ctx.moveTo(px, py); started = true;
      ctx.fillStyle = color; ctx.fillRect(px - 1.5, py - 1.5, 3, 3);
    });
    ctx.stroke();
  }
}

loadList();

/* ---- v2 : verdict intégré + plein écran (ajouts purs — la logique de données ci-dessus est inchangée) ---- */
async function loadVerdict() {
  try {
    const v = await (await fetch('/api/dreams/verdict')).json();
    const m = /VERDICT : \[([^\]]+)\]/.exec(v.text || '');
    const label = m ? m[1] : '…';
    const cls = { 'PROUVÉ': 'ok', 'RÉFUTÉ': 'err', 'INSUFFISANT': 'warn', 'BRUIT': 'muted', 'PLAUSIBLE': '' }[label] ?? '';
    document.getElementById('verdict-badge').innerHTML = `<span class="badge ${cls}" style="font-size:11px;">VERDICT : ${esc(label)}</span>`;
    document.getElementById('verdict-text').textContent = v.text || '';
  } catch (_) { document.getElementById('verdict-text').textContent = '(verdict indisponible)'; }
}
loadVerdict();

async function loadTrend() {
  try {
    const d = await (await fetch('/api/dreams/trend')).json();
    drawTrend((d.nights || []).filter(x => x.qwen != null || x.sonnet != null));
  } catch (_) {}
}
function drawTrend(nights) {
  const cv = document.getElementById('trend');
  if (!cv || !nights.length) return;
  const ctx = cv.getContext('2d');
  const W = cv.width, H = cv.height, pad = 26;
  ctx.clearRect(0, 0, W, H);
  const ymin = -0.2, ymax = 1.0;                          // écart ON−OFF ∈ [-0.2, 1]
  const X = (i) => pad + (W - 2 * pad) * (nights.length === 1 ? 0.5 : i / (nights.length - 1));
  const Y = (v) => H - pad - (H - 2 * pad) * ((v - ymin) / (ymax - ymin));
  ctx.strokeStyle = 'rgba(255,255,255,.18)'; ctx.setLineDash([3, 3]);              // ligne 0
  ctx.beginPath(); ctx.moveTo(pad, Y(0)); ctx.lineTo(W - pad, Y(0)); ctx.stroke(); ctx.setLineDash([]);
  ctx.fillStyle = 'rgba(255,255,255,.35)'; ctx.font = '9px ui-monospace';
  ctx.fillText("0 · pas d'effet", W - pad - 66, Y(0) - 4);
  const draw = (key, color) => {
    ctx.strokeStyle = color; ctx.fillStyle = color; ctx.lineWidth = 1.6; ctx.beginPath();
    let started = false;
    nights.forEach((n, i) => { const v = n[key]; if (v == null) return; const x = X(i), y = Y(v);
      if (!started) { ctx.moveTo(x, y); started = true; } else ctx.lineTo(x, y); });
    ctx.stroke();
    nights.forEach((n, i) => { const v = n[key]; if (v == null) return;
      ctx.beginPath(); ctx.arc(X(i), Y(v), 2.6, 0, Math.PI * 2); ctx.fill(); });
  };
  draw('qwen', '#2dd4bf');
  draw('sonnet', '#fbbf24');
  ctx.fillStyle = 'rgba(255,255,255,.4)'; ctx.font = '9px ui-monospace';
  nights.forEach((n, i) => ctx.fillText((n.date || '').slice(5), X(i) - 12, H - 7));
}

async function loadResemblance() {
  const el = document.getElementById('resemblance-viz');
  if (!el) return;
  try {
    const d = await (await fetch('/api/dreams/resemblance')).json();
    if (!d.qwen || !d.centroid_n) { el.innerHTML = ''; return; }
    const c = (v) => v == null ? '<span class="dim">—</span>' : v.toFixed(2);
    const gap = (v) => v == null ? '<span class="dim">—</span>' : `<b style="color:${v > 0 ? 'var(--ok)' : 'var(--err)'}">${v > 0 ? '+' : ''}${v.toFixed(2)}</b>`;
    const row = (m) => `<tr><td style="color:var(--txt-2);font-weight:600">${m}</td><td>${c(d[m].on)}</td><td>${c(d[m].off)}</td><td>${c(d[m].free)}</td><td>${gap(d[m].gap)}</td></tr>`;
    el.innerHTML = `
      <div style="font-size:11px;color:var(--txt-2);margin-bottom:6px">🔬 Mesure objective — <b>ressemblance au corpus réel</b> <span class="dim">· cosinus embedding rêve↔mémoire · HORS verdict pré-enregistré · écart&nbsp;&gt;0 = le corpus façonne</span></div>
      <table style="width:100%"><tr><th style="text-align:left"></th><th>ON</th><th>OFF-neutre</th><th>OFF-libre</th><th>écart ON−OFF</th></tr>
      ${row('qwen')}${row('sonnet')}</table>`;
  } catch (_) { el.innerHTML = ''; }
}

function renderAblationViz(text) {
  const el = document.getElementById('ablation-viz');
  if (!el) return;
  const grab = (re) => { const m = re.exec(text); return m; };
  const nights = (grab(/nuits min\/cellule A\/B \(on\/off\) : (\d+)/) || [])[1];
  const ret = {};
  const rl = (grab(/rétention anamnèse par cellule : (.+)/) || [])[1] || '';
  rl.split(',').forEach(p => { const mm = /([a-z]+)\/([a-z_]+)=([\d.]+)/.exec(p.trim()); if (mm) ret[mm[1] + '/' + mm[2]] = parseFloat(mm[3]); });
  const b = grab(/chute anamnèse ON→OFF-neutre \(B\) : qwen=([\d.]+), sonnet=([\d.]+)/);
  const conv = {};
  const cl = (grab(/convergence cross-archi par condition : (.+)/) || [])[1] || '';
  cl.split(',').forEach(p => { const mm = /([a-z_]+)=([\d.]+)/.exec(p.trim()); if (mm) conv[mm[1]] = parseFloat(mm[2]); });
  const pp = (grab(/p permutation \(suivi graines\) : ([\d.]+)/) || [])[1];
  const bar = (v) => {
    if (v == null || isNaN(v)) return '<span class="dim">—</span>';
    const w = Math.round(Math.min(1, v) * 100);
    return `<div style="display:flex;align-items:center;gap:6px"><div style="flex:1;height:8px;background:rgba(255,255,255,.06);border-radius:4px;overflow:hidden"><div style="width:${w}%;height:100%;background:${v >= 0.4 ? 'var(--teal)' : 'rgba(249,168,212,.55)'}"></div></div><span style="font-size:10px;width:30px;text-align:right;color:var(--txt-3)">${v.toFixed(2)}</span></div>`;
  };
  const rrow = (mdl) => `<tr><td style="color:var(--txt-2);font-weight:600">${mdl}</td>
    <td>${bar(ret[mdl + '/brain_on'])}</td><td>${bar(ret[mdl + '/brain_off'])}</td><td>${bar(ret[mdl + '/brain_off_free'])}</td></tr>`;
  el.innerHTML = `
    <div style="font-size:11px;color:var(--txt-2);margin-bottom:6px">Rétention anamnèse — <b>le corpus façonne-t-il le contenu ?</b> <span class="dim">(plus haut à ON = oui)</span></div>
    <table style="width:100%"><tr><th style="text-align:left"></th><th>ON·corpus</th><th>OFF·neutre</th><th>OFF·libre</th></tr>
    ${rrow('qwen')}${rrow('sonnet')}</table>
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px">
      ${b ? `<span class="chip">effondrement B · qwen ${b[1]} · sonnet ${b[2]}</span>` : ''}
      <span class="chip">convergence ON ${conv.brain_on ?? '—'} → libre ${conv.brain_off_free ?? '—'}</span>
      ${pp ? `<span class="chip">p suivi-graines ${pp}</span>` : ''}
      ${nights ? `<span class="chip">${nights}/10 nuits</span>` : ''}
    </div>`;
}

async function loadAblation() {
  try {
    const v = await (await fetch('/api/dreams/ablation')).json();
    const m = /VERDICT COMBIN[ÉE] : \[([^\]]+)\]/.exec(v.text || '');
    const label = m ? m[1] : '…';
    const cls = { 'PROUVÉ': 'ok', 'NON SOUTENU': 'err', 'INSUFFISANT': 'warn', 'PLAUSIBLE++': '' }[label] ?? '';
    document.getElementById('ablation-badge').innerHTML = `<span class="badge ${cls}" style="font-size:11px;">A∧B∧C : ${esc(label)}</span>`;
    document.getElementById('ablation-text').textContent = v.text || '';
    renderAblationViz(v.text || '');
    loadTrend();
    loadResemblance();
  } catch (_) { document.getElementById('ablation-text').textContent = '(rapport indisponible)'; }
}
loadAblation();

async function loadInsights() {
  try {
    const d = await (await fetch('/api/insights')).json();
    const items = d.insights || [];
    document.getElementById('insights').innerHTML = items.length ? items.map(it =>
      `<div class="mem" style="border-top:1px solid var(--glass-bd);padding:8px 0">
        <span class="badge" style="font-size:10px">${esc(it.backend)}</span>
        ${esc(it.content)}
        <div class="dim" style="font-size:11px;margin-top:4px">↳ ${it.sources.map(s => esc(s.snippet)).join(' · ')}</div>
      </div>`).join('') : '<div class="dim">(aucun lien génératif encore — le daemon en tisse la nuit)</div>';
  } catch (_) { document.getElementById('insights').innerHTML = '<div class="dim">(indisponible)</div>'; }
}
loadInsights();

async function loadEmerged() {
  try {
    const d = await (await fetch('/api/emerged')).json();
    const items = d.emerged || [];
    document.getElementById('emerged').innerHTML = items.length ? items.map(it =>
      `<div class="mem" style="border-top:1px solid var(--glass-bd);padding:8px 0">
        <span class="badge" style="font-size:10px">🌱 ${esc(it.path)}</span>
        <span class="dim" style="margin-left:8px">${it.n_insights} insight(s)</span>
        <div class="dim" style="font-size:11px;margin-top:4px">${esc(it.sample || '')}</div>
      </div>`).join('') : '<div class="dim">(aucune rubrique émergée encore — Claude en crée quand des insights forment un thème neuf)</div>';
  } catch (_) { document.getElementById('emerged').innerHTML = '<div class="dim">(indisponible)</div>'; }
}
loadEmerged();

document.addEventListener('click', (e) => {
  const b = e.target.closest ? e.target.closest('[data-fs]') : null;
  if (!b) return;
  const it = FS_ROWS[Number(b.dataset.fs)];
  if (!it) return;
  const st = it.row.seed_state || {}, mt = it.row.meta || {};
  showDetail({
    title: `Nuit ${it.row.night_id || '?'} — ${it.title}`,
    badges: (it.row.facets || []).slice(0, 10).map(f => ({ txt: f })),
    meta: [['rêveur', it.row.dreamer], ['humeur', st.humeur],
           ['valence', st.valence], ['éveil', st.arousal],
           ['choix', Array.isArray(it.row.chosen) ? `${it.row.chosen.length} / ${(it.row.menu || []).length}` : 'inparsable'],
           ['modèle', mt.model]],
    text: it.row.content || '',
    voice: true,
  });
});
