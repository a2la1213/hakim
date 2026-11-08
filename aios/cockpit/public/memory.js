/* Cockpit v2 — vue Mémoire : explorateur (+ analytique en T6). */
initNav('memory');
const $ = (id) => document.getElementById(id);
let offset = 0;
const LIM = 30;

let searchSeq = 0; // jeton anti-course : seule la DERNIÈRE recherche émise a le droit de peindre
async function search() {
  const seq = ++searchSeq;
  const p = new URLSearchParams({
    q: $('q').value, role: $('f-role').value, rubric: $('f-rubric').value,
    facet: $('f-facet').value, min_imp: $('f-minimp').value || '0',
    limit: LIM, offset,
  });
  let d = { total: 0, rows: [] };
  try { d = await (await fetch('/api/episodes?' + p)).json(); } catch (_) {}
  if (seq !== searchSeq) return; // réponse périmée (une recherche plus récente est partie) : jeter
  $('results-info').textContent = `${d.total} souvenir(s) · ${offset + 1}–${offset + (d.rows || []).length}`;
  $('results').innerHTML = (d.rows || []).map(r => `
    <div class="list-item" onclick="showEpisode(${Number(r.id)})" style="border-bottom:1px solid rgba(255,255,255,.04);">
      <div style="display:flex;gap:8px;align-items:baseline;">
        <span class="badge" style="flex-shrink:0;">${esc(r.role)}</span>
        <span style="font-size:12px;color:var(--txt-2);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1;">${esc(r.snippet || '')}</span>
      </div>
      <div style="font-size:8.5px;color:var(--txt-4);margin-top:3px;">
        ${esc(r.rubric || '—')} · imp ${(+r.importance || 0).toFixed(2)} · ${new Date(r.ts * 1000).toLocaleDateString('fr-FR')}
        ${(r.facets || []).slice(0, 4).map(f => `<span class="badge" style="font-size:7px;padding:0 6px;margin-left:4px;">${esc(f)}</span>`).join('')}
      </div>
    </div>`).join('') || '<div class="kv">(aucun résultat)</div>';
  $('prev').style.visibility = offset > 0 ? 'visible' : 'hidden';
  $('next').style.visibility = offset + LIM < d.total ? 'visible' : 'hidden';
}
let deb;
['q', 'f-role', 'f-rubric', 'f-facet', 'f-minimp'].forEach(id =>
  $(id).addEventListener('input', () => { clearTimeout(deb); deb = setTimeout(() => { offset = 0; search(); }, 300); }));
$('prev').onclick = () => { offset = Math.max(0, offset - LIM); search(); };
$('next').onclick = () => { offset += LIM; search(); };

document.querySelectorAll('.tab').forEach(t => t.onclick = () => {
  document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
  t.classList.add('active');
  $('explore').style.display = t.dataset.tab === 'explore' ? '' : 'none';
  $('analytics').style.display = t.dataset.tab === 'analytics' ? '' : 'none';
  if (t.dataset.tab === 'analytics' && typeof renderAnalytics === 'function') renderAnalytics();
});
search();

/* ---- Analytique : SVG maison, zéro lib. Humeur = PROXY (enc_* au moment de l'écriture). ---- */
function svgLine(pts, w, h, color, glow) {
  if (!pts.length) return '';
  const xs = (i) => (i / Math.max(1, pts.length - 1)) * (w - 20) + 10;
  const lo = Math.min(...pts), hi = Math.max(...pts), rng = (hi - lo) || 1;
  const ys = (v) => h - 14 - ((v - lo) / rng) * (h - 28);
  const d = pts.map((v, i) => `${i ? 'L' : 'M'}${xs(i).toFixed(1)},${ys(v).toFixed(1)}`).join(' ');
  return `<path d="${d}" fill="none" stroke="${color}" stroke-width="1.8" ${glow ? `style="filter:drop-shadow(0 0 4px ${color})"` : ''}/>`;
}
function chartCard(title, note, inner) {
  return `<div class="glass" style="margin-bottom:12px;"><div class="sec-label">${title} <span class="dim">${note || ''}</span></div>${inner}</div>`;
}
async function renderAnalytics() {
  let d = null;
  try { d = await (await fetch('/api/analytics')).json(); } catch (_) {}
  if (!d) { $('charts').innerHTML = '<div class="kv">(analytique indisponible)</div>'; return; }
  const daily = d.daily || [];
  const humeur = chartCard('◈ HUMEUR DANS LE TEMPS', '· proxy : valence/éveil encodés à l\'écriture (90 j)',
    `<svg width="100%" height="90" viewBox="0 0 600 90" preserveAspectRatio="none">
      ${svgLine(daily.map(x => x.val ?? 0), 600, 90, '#2dd4bf', true)}
      ${svgLine(daily.map(x => x.aro ?? 0), 600, 90, '#f9a8d4', false)}
    </svg>
    <div style="display:flex;gap:14px;font-size:9px;color:var(--txt-4);"><span style="color:#2dd4bf;">━ valence</span><span style="color:#f9a8d4;">━ éveil</span></div>`);
  const mx = Math.max(1, ...daily.map(x => x.n));
  const croissance = chartCard('▤ SOUVENIRS / JOUR', `· ${daily.reduce((s, x) => s + x.n, 0)} sur 90 j`,
    `<div style="display:flex;gap:2px;align-items:flex-end;height:60px;">
      ${daily.map(x => `<div title="${esc(x.d)} : ${x.n}" style="flex:1;height:${Math.round((x.n / mx) * 100)}%;background:rgba(45,212,191,.45);border-radius:2px 2px 0 0;min-width:2px;"></div>`).join('')}
    </div>`);
  const mf = Math.max(1, ...(d.top_facets || []).map(x => x.n));
  const facettes = chartCard('✧ TOP FACETTES', '',
    (d.top_facets || []).map(x => `
      <div style="display:flex;gap:8px;align-items:center;font-size:10px;margin:3px 0;">
        <span style="width:130px;color:var(--txt-3);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${esc(x.slug)}</span>
        <div class="bar" style="flex:1;"><i style="width:${Math.round((x.n / mf) * 100)}%"></i></div>
        <span style="color:var(--txt-4);width:40px;text-align:right;">${x.n}</span></div>`).join(''));
  const mr = Math.max(1, ...(d.by_rubric || []).map(x => x.n));
  const rubriques = chartCard('◈ PAR RUBRIQUE DE TÊTE', '',
    (d.by_rubric || []).map(x => `
      <div style="display:flex;gap:8px;align-items:center;font-size:10px;margin:3px 0;">
        <span style="width:130px;color:var(--txt-3);">${esc(x.top)}</span>
        <div class="bar rose" style="flex:1;"><i style="width:${Math.round((x.n / mr) * 100)}%"></i></div>
        <span style="color:var(--txt-4);width:40px;text-align:right;">${x.n}</span></div>`).join(''));
  const mo = Math.max(1, ...(d.by_role || []).map(x => x.n));
  const roles = chartCard('▣ RÉPARTITION PAR RÔLE', '',
    (d.by_role || []).map(x => `
      <div style="display:flex;gap:8px;align-items:center;font-size:10px;margin:3px 0;">
        <span style="width:130px;color:var(--txt-3);">${esc(x.role)}</span>
        <div class="bar" style="flex:1;"><i style="width:${Math.round((x.n / mo) * 100)}%"></i></div>
        <span style="color:var(--txt-4);width:40px;text-align:right;">${x.n}</span></div>`).join(''));
  const nights = {}; (d.dream_nights || []).forEach(r => { const day = (r.night_id || '').slice(0, 10); nights[day] = nights[day] || {}; if (r.dreamer === 'local') nights[day].k = r.k; });
  const nightKeys = Object.keys(nights).sort().slice(-30);
  const reves = chartCard('🌙 ACTIVITÉ DES RÊVES', '· appétit par nuit (30 dernières)',
    nightKeys.length ? `<div style="display:flex;gap:3px;align-items:flex-end;height:44px;">
      ${nightKeys.map(day => `<div title="${esc(day)} k=${nights[day].k ?? '—'}" style="flex:1;height:${nights[day].k != null ? 10 + nights[day].k * 7 : 4}%;background:linear-gradient(180deg,var(--teal),transparent);border-radius:2px;"></div>`).join('')}
    </div>` : '<div class="kv">(aucune nuit encore — le corpus se remplit)</div>');
  let arbre = '';
  try {
    const rub = await (await fetch('/api/rubrics')).json();
    const now = Date.now() / 1000;
    arbre = chartCard('🌳 ARBRE DES RUBRIQUES', `· ${(rub.rows || []).length} nœuds — le cerveau qui grandit`,
      (rub.rows || []).map(r => `
        <div style="display:flex;gap:8px;align-items:center;font-size:10.5px;margin:2px 0;padding-left:${r.depth * 16}px;">
          <span style="color:${r.depth === 0 ? 'var(--teal-hi)' : 'var(--txt-2)'};">${r.depth === 0 ? '◈' : '└'} ${esc(r.path.split('/').pop())}</span>
          ${now - (r.created_ts || 0) < 7 * 86400 ? '<span class="badge ok" style="font-size:7px;padding:0 6px;">nouveau</span>' : ''}
          <span style="color:var(--txt-4);margin-left:auto;">${r.memory_count} souvenir(s)</span>
        </div>`).join('') || '<div class="kv">(arbre vide)</div>');
  } catch (_) {}
  $('charts').innerHTML = humeur + croissance + facettes + rubriques + roles + reves + arbre;
}
