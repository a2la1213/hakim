/* Cerveau 3D d'Anamnèse — nuage de souvenirs (brain_layout) rendu en three.js.
   Offline : three vendored dans /vendor/three/ (importmap "three" dans brain.html).
   Nœuds = sphères instanciées (couleur = région, taille = importance/recall) + halo additif.
   Arêtes = co-activation (0 pour l'instant : géré). OrbitControls + raycaster + légende.
   MDT (WM3) : toggle « mémoire de travail » — nœuds wm==='focus' vifs (glow blanc-chaud
   additif + taille ↑), wm==='halo' en lueur ténue, le reste en veille (atténué).
   Un InstancedMesh partage UN matériau : l'« emissive » par nœud passe par la couche
   de points additifs (couleur par sommet = glow perçu) + boost de l'instanceColor.
   Détail (3D-detail) : survol → tooltip avec date+heure (node.ts, epoch s) ; clic sur
   un nœud → panneau latéral droit avec le souvenir COMPLET via /api/memory?id=N
   (contenu intégral, date exacte, rubrique, facettes, importance/rappels, affect,
   session). L'ancien « épinglage » du tooltip est FONDU dans ce panneau. */
import * as THREE from 'three';
import { OrbitControls } from '/vendor/three/OrbitControls.js';

const SCALE = 40;                       // brain_layout ∈ ~[-0.7,0.7] → nuage ~±28 unités
const GRAY = new THREE.Color('#4a5f5c'); // rubric null / affect absent

const canvas = document.getElementById('scene');
const tooltip = document.getElementById('tooltip');
const countsEl = document.getElementById('counts');
const legendEl = document.getElementById('legend');
const legendReset = document.getElementById('legend-reset');
const emptyMsg = document.getElementById('empty-msg');
const affectToggle = document.getElementById('affect-toggle');
const wmToggle = document.getElementById('wm-toggle');
const wmCountsEl = document.getElementById('wm-counts');
const detailEl = document.getElementById('detail');
const detailIdEl = document.getElementById('detail-id');
const detailBody = document.getElementById('detail-body');
const detailClose = document.getElementById('detail-close');

/* ---------- scène de base ---------- */
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setSize(innerWidth, innerHeight);

const scene = new THREE.Scene();
scene.background = new THREE.Color('#030a0c');
scene.fog = new THREE.FogExp2(0x030a0c, 0.0075);

const camera = new THREE.PerspectiveCamera(55, innerWidth / innerHeight, 0.1, 4000);
camera.position.set(0, 12, 70);

scene.add(new THREE.AmbientLight(0x7fb8ae, 0.8));
const dir = new THREE.DirectionalLight(0xffffff, 1.15);
dir.position.set(40, 60, 50);
scene.add(dir);
const heart = new THREE.PointLight(0x2dd4bf, 60, 0, 1.6); // lueur teal au cœur du nuage
scene.add(heart);

const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true;
controls.dampingFactor = 0.06;
controls.minDistance = 4;
controls.maxDistance = 500;

addEventListener('resize', () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
});

/* ---------- état ---------- */
let nodes = [], edges = [];
let mesh = null, halo = null, lines = null;
let regionColors = new Map();           // path|null → THREE.Color
const hiddenRegions = new Set();        // paths (ou '∅') masqués via la légende
let affectMode = false;
let wmMode = false;                     // MDT allumée : focus vif / halo ténu / reste en veille
const WHITE = new THREE.Color(1, 1, 1);
const WM_FOCUS_SCALE = 1.3;             // taille légèrement ↑ des nœuds en focus
let focusIdx = [];                      // indices des nœuds focus (pulsation MDT, borné à 24)
let pinnedIdx = -1;                     // nœud sélectionné par clic → panneau de détail (-1 = aucun)
const raycaster = new THREE.Raycaster();
const mouse = new THREE.Vector2();
let mouseMoved = false, mouseIn = false;
const _m = new THREE.Matrix4(), _c = new THREE.Color();

const keyOf = n => n.rubric || '∅';
const radiusOf = n => 0.28 + 0.55 * (n.importance ?? 0.5) + 0.06 * Math.min(n.recall_count ?? 0, 5);
// (audit du 2026-10-20, C-H4) : les guillemets aussi — un chemin de rubrique piégé ne sort plus d'un attribut
const esc = s => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

/* ts epoch (secondes, float) → date+heure fr : « 2 juil. 2026 · 17:32 » (court)
   ou « jeudi 2 juillet 2026 · 17:32:05 » (long). ts absent/invalide → null. */
function fmtDate(ts, long = false) {
  const t = Number(ts);
  if (!Number.isFinite(t) || t <= 0) return null;
  const d = new Date(t * 1000);
  const day = d.toLocaleDateString('fr-FR', long
    ? { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }
    : { day: 'numeric', month: 'short', year: 'numeric' });
  const time = d.toLocaleTimeString('fr-FR', long
    ? { hour: '2-digit', minute: '2-digit', second: '2-digit' }
    : { hour: '2-digit', minute: '2-digit' });
  return `${day} · ${time}`;
}

/* Palette stable : rubriques triées → teintes en angle d'or (bien séparées, déterministe). */
function buildPalette() {
  regionColors = new Map();
  const paths = [...new Set(nodes.map(n => n.rubric).filter(Boolean))].sort();
  paths.forEach((p, i) => regionColors.set(p, new THREE.Color().setHSL(((i * 137.508) % 360) / 360, 0.6, 0.6)));
  regionColors.set('∅', GRAY.clone());
}
function regionColor(n) { return regionColors.get(keyOf(n)) || GRAY; }
/* Affect : valence → teinte (rouge -1 → vert +1), arousal → saturation/éclat. Null → gris. */
function affectColor(n) {
  if (n.valence == null && n.arousal == null) return GRAY;
  const v = Math.max(-1, Math.min(1, n.valence ?? 0));
  const a = Math.max(0, Math.min(1, n.arousal ?? 0.3));
  return new THREE.Color().setHSL(((v + 1) / 2) * 0.36, 0.45 + 0.5 * a, 0.42 + 0.25 * a);
}
const colorOf = n => (affectMode ? affectColor(n) : regionColor(n));

/* ---------- construction du nuage ---------- */
function makeHaloTexture() {
  const c = document.createElement('canvas'); c.width = c.height = 64;
  const g = c.getContext('2d');
  const grad = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  grad.addColorStop(0, 'rgba(255,255,255,.9)');
  grad.addColorStop(0.35, 'rgba(255,255,255,.28)');
  grad.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = grad; g.fillRect(0, 0, 64, 64);
  return new THREE.CanvasTexture(c);
}

function buildScene() {
  if (!nodes.length) { emptyMsg.style.display = 'block'; return; }

  // barycentre → cible caméra
  const center = new THREE.Vector3();
  nodes.forEach(n => center.add(new THREE.Vector3(n.x, n.y, n.z)));
  center.multiplyScalar(SCALE / nodes.length);
  controls.target.copy(center);
  heart.position.copy(center);
  let radius = 0;
  nodes.forEach(n => radius = Math.max(radius, center.distanceTo(new THREE.Vector3(n.x * SCALE, n.y * SCALE, n.z * SCALE))));
  camera.position.set(center.x + radius * 0.7, center.y + radius * 0.55, center.z + radius * 1.7);

  // sphères instanciées (raycastables via instanceId)
  const geo = new THREE.SphereGeometry(1, 14, 10);
  const mat = new THREE.MeshStandardMaterial({ roughness: 0.3, metalness: 0.1, emissive: 0x062a26, emissiveIntensity: 1.15 });
  mesh = new THREE.InstancedMesh(geo, mat, nodes.length);
  nodes.forEach((n, i) => {
    _m.makeScale(radiusOf(n), radiusOf(n), radiusOf(n)).setPosition(n.x * SCALE, n.y * SCALE, n.z * SCALE);
    mesh.setMatrixAt(i, _m);
    mesh.setColorAt(i, colorOf(n));
  });
  scene.add(mesh);
  // pulsation MDT : indices des nœuds focus (positions déjà dans nodes[], réutilisées), borné à 24
  focusIdx = nodes.map((n, i) => (n.wm === 'focus' ? i : -1)).filter(i => i >= 0).slice(0, 24);

  // halo additif (saillance : luminosité ∝ importance)
  const pos = new Float32Array(nodes.length * 3), col = new Float32Array(nodes.length * 3);
  nodes.forEach((n, i) => { pos[i * 3] = n.x * SCALE; pos[i * 3 + 1] = n.y * SCALE; pos[i * 3 + 2] = n.z * SCALE; });
  const hgeo = new THREE.BufferGeometry();
  hgeo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  hgeo.setAttribute('color', new THREE.BufferAttribute(col, 3));
  halo = new THREE.Points(hgeo, new THREE.PointsMaterial({
    size: 2.6, map: makeHaloTexture(), vertexColors: true, transparent: true,
    depthWrite: false, blending: THREE.AdditiveBlending, sizeAttenuation: true,
  }));
  scene.add(halo);

  // arêtes de co-activation (0 pour l'instant : ce bloc ne s'exécute pas — pas de crash)
  const byId = new Map(nodes.map((n, i) => [n.id, i]));
  const valid = edges.filter(e => byId.has(e.a) && byId.has(e.b));
  if (valid.length) {
    const maxW = Math.max(...valid.map(e => e.w || 0), 1e-6);
    const lp = new Float32Array(valid.length * 6), lc = new Float32Array(valid.length * 6);
    valid.forEach((e, i) => {
      const A = nodes[byId.get(e.a)], B = nodes[byId.get(e.b)];
      lp.set([A.x * SCALE, A.y * SCALE, A.z * SCALE, B.x * SCALE, B.y * SCALE, B.z * SCALE], i * 6);
      // blending additif : teal pondéré par le poids (voies consolidées brillent, faibles s'estompent)
      _c.set('#2dd4bf').multiplyScalar(0.25 + 0.75 * Math.min(1, (e.w || 0) / 2));
      lc.set([_c.r, _c.g, _c.b], i * 6);
      lc.set([_c.r, _c.g, _c.b], i * 6 + 3);
    });
    const lgeo = new THREE.BufferGeometry();
    lgeo.setAttribute('position', new THREE.BufferAttribute(lp, 3));
    lgeo.setAttribute('color', new THREE.BufferAttribute(lc, 3));
    lines = new THREE.LineSegments(lgeo, new THREE.LineBasicMaterial({
      vertexColors: true, transparent: true, opacity: 0.8,
      blending: THREE.AdditiveBlending, depthWrite: false,
    }));
    lines.userData.valid = valid;
    lines.userData.maxW = maxW;
    scene.add(lines);
  }
  applyColors();
}

/* ---------- couleurs / filtres (région masquée = sphère échelle 0 + halo noir) ---------- */
function applyColors() {
  if (!mesh) return;
  nodes.forEach((n, i) => {
    const hidden = hiddenRegions.has(keyOf(n));
    // MDT : focus légèrement plus gros ; veille = taille normale (l'atténuation est chromatique)
    const r = hidden ? 0 : radiusOf(n) * (wmMode && n.wm === 'focus' ? WM_FOCUS_SCALE : 1);
    _m.makeScale(r, r, r).setPosition(n.x * SCALE, n.y * SCALE, n.z * SCALE);
    mesh.setMatrixAt(i, _m);
    if (hidden) mesh.setColorAt(i, _c.setScalar(0));
    else {
      _c.copy(colorOf(n));
      if (wmMode) {
        if (n.wm === 'focus') _c.lerp(WHITE, 0.3).multiplyScalar(1.3);  // vif, tiré vers le blanc
        else if (n.wm !== 'halo') _c.multiplyScalar(0.3);               // veille : atténué
      }
      mesh.setColorAt(i, _c);
    }
    // halo additif : noir = invisible ; c'est LUI qui porte l'« emissive » perçue de la MDT
    if (hidden) _c.setScalar(0);
    else {
      const base = 0.25 + 0.6 * (n.importance ?? 0.5);
      _c.copy(colorOf(n));
      if (!wmMode) _c.multiplyScalar(base);
      else if (n.wm === 'focus') _c.lerp(WHITE, 0.45).multiplyScalar(1.7); // glow marqué
      else if (n.wm === 'halo') _c.multiplyScalar(Math.max(base, 0.5));    // lueur ténue
      else _c.multiplyScalar(base * 0.12);                                 // veille : quasi éteint
    }
    halo.geometry.attributes.color.setXYZ(i, _c.r, _c.g, _c.b);
  });
  mesh.instanceMatrix.needsUpdate = true;
  if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
  halo.geometry.attributes.color.needsUpdate = true;

  if (lines) {
    const byId = new Map(nodes.map((n, i) => [n.id, i]));
    const { valid, maxW } = lines.userData;
    const lc = lines.geometry.attributes.color;
    valid.forEach((e, i) => {
      const A = nodes[byId.get(e.a)], B = nodes[byId.get(e.b)];
      const off = hiddenRegions.has(keyOf(A)) || hiddenRegions.has(keyOf(B));
      // teal pondéré par le poids (voies consolidées brillent, faibles s'estompent)
      let t = off ? 0 : 0.25 + 0.75 * Math.min(1, (e.w || 0) / 2);
      if (wmMode && !A.wm && !B.wm) t *= 0.25; // MDT : les voies hors focus/halo se mettent en veille
      _c.set('#2dd4bf').multiplyScalar(t); lc.setXYZ(i * 2, _c.r, _c.g, _c.b);
      _c.set('#2dd4bf').multiplyScalar(t); lc.setXYZ(i * 2 + 1, _c.r, _c.g, _c.b);
    });
    lc.needsUpdate = true;
  }
}

/* ---------- légende ---------- */
function buildLegend() {
  const counts = new Map();
  nodes.forEach(n => counts.set(keyOf(n), (counts.get(keyOf(n)) || 0) + 1));
  const entries = [...counts.entries()].sort((a, b) => (a[0] === '∅') - (b[0] === '∅') || a[0].localeCompare(b[0]));
  legendEl.innerHTML = '';
  entries.forEach(([key, count]) => {
    const col = regionColors.get(key) || GRAY;
    const row = document.createElement('div');
    row.className = 'lg';
    row.title = key === '∅' ? 'sans rubrique' : key;
    row.innerHTML = `<span class="sw" style="background:#${col.getHexString()};color:#${col.getHexString()}"></span>` +
      `<span class="lp">${key === '∅' ? 'sans rubrique' : esc(key)}</span><span class="lc">${esc(count)}</span>`;
    row.addEventListener('click', () => {
      hiddenRegions.has(key) ? hiddenRegions.delete(key) : hiddenRegions.add(key);
      row.classList.toggle('off', hiddenRegions.has(key));
      legendReset.style.display = hiddenRegions.size ? 'inline-block' : 'none';
      if (pinnedIdx >= 0 && hiddenRegions.has(keyOf(nodes[pinnedIdx]))) { closeDetail(); hideTooltip(); }
      applyColors();
    });
    legendEl.appendChild(row);
  });
}
legendReset.addEventListener('click', () => {
  hiddenRegions.clear();
  legendEl.querySelectorAll('.lg.off').forEach(r => r.classList.remove('off'));
  legendReset.style.display = 'none';
  applyColors();
});

affectToggle.addEventListener('change', () => { affectMode = affectToggle.checked; applyColors(); });
wmToggle.addEventListener('change', () => { wmMode = wmToggle.checked; applyColors(); });

/* ---------- tooltip (survol — le clic ouvre le panneau de détail) ---------- */
function showTooltip(idx, x, y) {
  const n = nodes[idx];
  const col = colorOf(n).getHexString();
  const affect = (n.valence != null || n.arousal != null)
    ? `<span>val <b>${(+n.valence || 0).toFixed(2)}</b></span><span>aro <b>${(+n.arousal || 0).toFixed(2)}</b></span>` : '';
  const wmBadge = n.wm === 'focus' || n.wm === 'halo' ? `<span>mdt <b>${n.wm}</b></span>` : '';
  const when = fmtDate(n.ts);            // date+heure du souvenir (node.ts, additif)
  tooltip.innerHTML =
    `<span class="tt-rubric" style="color:#${col};border-color:#${col}66">${esc(n.rubric || 'sans rubrique')}</span>` +
    `<div class="tt-snip">${esc(n.snippet || '')}${(n.snippet || '').length >= 90 ? '…' : ''}</div>` +
    (when ? `<div class="tt-date">🕒 <b>${when}</b></div>` : '') +
    `<div class="tt-meta"><span>#${esc(n.id)}</span><span>importance <b>${(+n.importance || 0).toFixed(2)}</b></span>` +
    `<span>rappels <b>${n.recall_count ?? 0}</b></span>${affect}${wmBadge}</div>` +
    '<div class="tt-pin">clic · souvenir complet</div>';
  tooltip.hidden = false;
  const w = tooltip.offsetWidth, h = tooltip.offsetHeight;
  tooltip.style.left = Math.min(x + 16, innerWidth - w - 12) + 'px';
  tooltip.style.top = Math.min(y + 12, innerHeight - h - 12) + 'px';
}
function hideTooltip() { tooltip.hidden = true; }

/* ---------- panneau de détail (clic → souvenir COMPLET via /api/memory) ---------- */
function closeDetail() { pinnedIdx = -1; detailEl.hidden = true; }

function openDetail(idx) {
  const n = nodes[idx];
  pinnedIdx = idx;
  detailIdEl.textContent = `#${n.id}`;
  detailEl.hidden = false;
  detailBody.innerHTML = `<div class="d-loading">chargement du souvenir #${n.id}…</div>`;
  fetch(`/api/memory?id=${n.id}`)
    .then(r => r.json().then(m => ({ ok: r.ok, m })))
    .then(({ ok, m }) => {
      if (pinnedIdx !== idx) return;     // un autre nœud a été sélectionné entre-temps
      if (!ok || m.error) throw new Error(m.error || `souvenir #${n.id} introuvable`);
      renderDetail(n, m);
    })
    .catch(e => {
      if (pinnedIdx === idx) detailBody.innerHTML = `<div class="d-err">${esc(e.message || 'erreur /api/memory')}</div>`;
    });
}

function renderDetail(n, m) {
  const col = colorOf(n).getHexString();
  const when = fmtDate(m.ts ?? n.ts, true) || 'date inconnue';
  const facets = (m.facets && m.facets.length)
    ? m.facets.map(f => `<span class="d-facet">${esc(f)}</span>`).join('')
    : '<span class="d-none">aucune</span>';
  const kv = [
    ['rôle', m.role || '–'],
    ['importance', m.importance != null ? (+m.importance).toFixed(2) : '–'],
    ['rappels', m.recall_count ?? 0],
    ['valence', m.enc_valence != null ? (+m.enc_valence).toFixed(2) : '–'],
    ['arousal', m.enc_arousal != null ? (+m.enc_arousal).toFixed(2) : '–'],
    ['session', m.session_id ?? '–'],
  ].map(([k, v]) => `<div class="d-kv"><span>${k}</span><b>${esc(v)}</b></div>`).join('');
  detailBody.innerHTML =
    `<span class="d-rubric" style="color:#${col};border-color:#${col}66">${esc(m.rubric || 'sans rubrique')}</span>` +
    (n.wm ? `<span class="d-wm">mémoire de travail · ${esc(n.wm)}</span>` : '') +
    `<div class="d-date">🕒 <b>${esc(when)}</b></div>` +
    `<div class="d-text">${esc(m.content || '')}</div>` +
    `<div class="d-sec">facettes</div><div class="d-facets">${facets}</div>` +
    `<div class="d-sec">signaux</div><div class="d-meta">${kv}</div>`;
}

detailClose.addEventListener('click', closeDetail);
addEventListener('keydown', ev => { if (ev.key === 'Escape') closeDetail(); });

function pick() {
  if (!mesh) return -1;
  raycaster.setFromCamera(mouse, camera);
  const hits = raycaster.intersectObject(mesh);
  for (const h of hits) {
    if (h.instanceId != null && !hiddenRegions.has(keyOf(nodes[h.instanceId]))) return h.instanceId;
  }
  return -1;
}

let lastMouse = { x: 0, y: 0 };
canvas.addEventListener('pointermove', ev => {
  mouse.x = (ev.clientX / innerWidth) * 2 - 1;
  mouse.y = -(ev.clientY / innerHeight) * 2 + 1;
  lastMouse = { x: ev.clientX, y: ev.clientY };
  mouseMoved = true; mouseIn = true;
});
canvas.addEventListener('pointerleave', () => { mouseIn = false; hideTooltip(); });
let downAt = null;
canvas.addEventListener('pointerdown', ev => { downAt = { x: ev.clientX, y: ev.clientY }; });
canvas.addEventListener('pointerup', ev => {
  // clic « sec » seulement (pas un drag d'orbite) → ouvre/ferme le panneau de détail
  if (!downAt || Math.hypot(ev.clientX - downAt.x, ev.clientY - downAt.y) > 5) return;
  const idx = pick();
  if (idx >= 0) { hideTooltip(); openDetail(idx); }
  else closeDetail();
});

/* ---------- boucle ---------- */
function animate() {
  requestAnimationFrame(animate);
  controls.update();
  // pulsation douce des nœuds focus (MDT allumée, hors reduced-motion) — ~24 setMatrixAt max
  if (wmMode && !window.REDUCED && mesh && focusIdx.length) {
    const t = performance.now() * 0.001;
    for (const i of focusIdx) {
      const n = nodes[i];
      if (hiddenRegions.has(keyOf(n))) continue;      // masqué : échelle 0 posée par applyColors
      const r = radiusOf(n) * WM_FOCUS_SCALE * (1 + 0.08 * Math.sin(t * 2 + i));
      _m.makeScale(r, r, r).setPosition(n.x * SCALE, n.y * SCALE, n.z * SCALE);
      mesh.setMatrixAt(i, _m);
    }
    mesh.instanceMatrix.needsUpdate = true;
  }
  if (mouseMoved && mouseIn) {           // le survol reste actif même panneau ouvert
    mouseMoved = false;
    const idx = pick();
    if (idx >= 0) { showTooltip(idx, lastMouse.x, lastMouse.y); canvas.style.cursor = 'pointer'; }
    else { hideTooltip(); canvas.style.cursor = ''; }
  }
  renderer.render(scene, camera);
}

/* ---------- go ---------- */
fetch('/api/brain')
  .then(r => r.json())
  .then(data => {
    nodes = Array.isArray(data.nodes) ? data.nodes : [];
    edges = Array.isArray(data.edges) ? data.edges : [];
    countsEl.innerHTML = `<b>${nodes.length}</b> nœuds · <b>${edges.length}</b> arêtes de co-activation`;
    // MDT : compteur de légende (calculé sur les nœuds VISIBLES — robuste même sans data.wm)
    const focusN = nodes.filter(n => n.wm === 'focus').length;
    const haloN = nodes.filter(n => n.wm === 'halo').length;
    wmCountsEl.innerHTML = `focus <b>${focusN}</b> · halo <b>${haloN}</b>`;
    buildPalette();
    buildScene();
    buildLegend();
  })
  .catch(() => { countsEl.textContent = 'erreur de chargement /api/brain'; emptyMsg.style.display = 'block'; });

animate();
