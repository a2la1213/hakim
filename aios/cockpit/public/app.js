/* Cockpit v2 — dashboard. Toute valeur dynamique passe par esc(). */
initNav('dashboard');
const $ = (id) => document.getElementById(id);
const fmtT = (ts) => new Date((ts || 0) * 1000).toLocaleTimeString('fr-FR');
const fmtIso = (t) => (t ? fmtT(Date.parse(t) / 1000) : new Date().toLocaleTimeString('fr-FR'));
const ago = (ms) => { const s = Math.floor((Date.now() - ms) / 1000); if (s < 60) return s + 's'; if (s < 3600) return Math.floor(s / 60) + 'min'; return Math.floor(s / 3600) + 'h'; };

/* ---- HUMEUR : orbe + valence/arousal + 9 barres (données /api/anamnese.affect + mood) ---- */
function renderMood(a) {
  const aff = a.affect || {}, mood = a.mood || {};
  const val = mood.valence ?? 0, aro = mood.arousal ?? 0;
  // teinte de l'orbe : glisse teal→rose selon la valence ; période de respiration liée à l'arousal
  const hue = val >= 0 ? '' : 'filter:hue-rotate(-90deg) saturate(.8);';
  const period = REDUCED ? '' : `--orb-period:${(6 - 3 * Math.min(1, Math.max(0, aro))).toFixed(1)}s;`;
  const bars = Object.entries(aff).map(([h, v]) => `
    <div style="flex:1;text-align:center;min-width:0;">
      <div style="height:26px;display:flex;align-items:flex-end;">
        <div style="width:100%;height:${Math.round(v * 100)}%;border-radius:3px;background:${v >= 0.55 ? 'linear-gradient(180deg,var(--teal),rgba(45,212,191,.15))' : 'linear-gradient(180deg,#134e4a,rgba(19,78,74,.2))'};"></div>
      </div>
      <div style="color:var(--txt-4);font-size:6.5px;margin-top:2px;overflow:hidden;">${esc(h.slice(0, 4))}</div>
    </div>`).join('');
  $('mood-body').innerHTML = `
    <div style="display:flex;gap:14px;align-items:center;">
      <div class="orb" style="width:64px;height:64px;flex-shrink:0;${hue}${period}"></div>
      <div style="flex:1;min-width:0;">
        <div class="voice" style="font-size:15px;margin-bottom:8px;">« ${esc(mood.label || '…')} »</div>
        <div style="display:flex;gap:8px;align-items:center;font-size:9px;color:var(--txt-4);margin-bottom:4px;">
          <span style="width:44px;">valence</span><div class="bar" style="flex:1;"><i style="width:${Math.round((val + 1) * 50)}%"></i></div><span>${val >= 0 ? '+' : ''}${(+val).toFixed(2)}</span></div>
        <div style="display:flex;gap:8px;align-items:center;font-size:9px;color:var(--txt-4);">
          <span style="width:44px;">éveil</span><div class="bar rose" style="flex:1;"><i style="width:${Math.round(aro * 100)}%"></i></div><span>${(+aro).toFixed(2)}</span></div>
      </div>
    </div>
    <div style="display:flex;gap:4px;margin-top:12px;">${bars}</div>
    <div class="voice" style="font-size:11px;color:var(--txt-3);margin-top:10px;cursor:pointer;" id="self-line">${esc((a.self || '').slice(0, 160))} <span class="read-more">▸</span></div>`;
  const sl = $('self-line');
  if (sl) sl.onclick = () => showDetail({ title: 'Auto-modèle — Anamnèse', meta: [], text: a.self || '', voice: true });
}

/* ---- PENSÉES / MÉMOIRES : extrait + clic → showEpisode(id) (fin du tronqué) ---- */
function renderThoughts(list) {
  $('thoughts').innerHTML = (list || []).slice(0, 6).map(t => `
    <div class="list-item" onclick="showEpisode(${Number(t.id)})">
      <div class="voice" style="font-size:11.5px;line-height:1.6;border-left:2px solid rgba(249,168,212,.35);padding-left:10px;">
        « ${esc((t.content || '').slice(0, 150))}${(t.content || '').length > 150 ? '…' : ''} <span class="read-more">▸ lire tout</span></div>
      <div style="font-size:8px;color:var(--txt-4);margin-top:2px;">${esc(t.role)} · ${fmtT(t.ts)}</div>
    </div>`).join('') || '<div class="kv">(rien)</div>';
}
function renderMemories(list) { /* même pattern que renderThoughts, sans .voice, badge importance */
  $('memories').innerHTML = (list || []).slice(0, 6).map(m => `
    <div class="list-item" onclick="showEpisode(${Number(m.id)})">
      <div style="font-size:11px;color:var(--txt-2);">${esc((m.content || '').slice(0, 110))}${(m.content || '').length > 110 ? '…' : ''}</div>
      <div style="font-size:8px;color:var(--txt-4);margin-top:2px;">${esc(m.role)} · imp ${(+m.importance || 0).toFixed(2)} · ${fmtT(m.ts)}</div>
    </div>`).join('') || '<div class="kv">(rien)</div>';
}

/* ---- LABO DES RÊVES : badge verdict (1re ligne « VERDICT » du /api/dreams/verdict) + nuits récentes ---- */
async function renderDreams() {
  try {
    const [v, d] = await Promise.all([
      (await fetch('/api/dreams/verdict')).json(),
      (await fetch('/api/dreams')).json(),
    ]);
    const m = /VERDICT : \[([^\]]+)\]/.exec(v.text || '');
    const label = m ? m[1] : '…';
    const cls = { 'PROUVÉ': 'ok', 'RÉFUTÉ': 'err', 'INSUFFISANT': 'warn', 'BRUIT': 'muted' }[label] || '';
    const nights = (d.nights || []).slice(0, 7).reverse();
    const barsN = nights.map(n => `<div title="${esc(n.date)} k=${n.local ? esc(String(n.local.k ?? '?')) : '—'}" style="flex:1;height:${n.local && n.local.k != null ? 8 + n.local.k * 3 : 4}px;background:${n.local ? 'linear-gradient(180deg,var(--teal),transparent)' : 'rgba(94,141,135,.2)'};border-radius:3px;align-self:flex-end;"></div>`).join('');
    $('dreams-summary').innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;gap:12px;">
        <span class="badge ${cls}">VERDICT : ${esc(label)}</span>
        <div style="display:flex;gap:3px;flex:1;max-width:280px;height:34px;">${barsN || ''}</div>
        <span class="kv">${(d.nights || []).length} nuit(s) au journal</span>
      </div>
      <div id="dreams-corpus" style="margin-top:10px;"></div>`;
    renderDreamsCorpus();                 // 2e ligne : expérience du corpus (async, ne bloque pas)
  } catch (_) { $('dreams-summary').innerHTML = '<div class="kv">(labo indisponible)</div>'; }
}

/* ---- expérience d'ablation du corpus : verdict A/B/C + progression + écart ON−OFF (le cœur du labo) ---- */
async function renderDreamsCorpus() {
  const el = $('dreams-corpus');
  if (!el) return;
  try {
    const [a, t] = await Promise.all([
      (await fetch('/api/dreams/ablation')).json(),
      (await fetch('/api/dreams/trend')).json(),
    ]);
    const m = /VERDICT COMBIN[ÉE] : \[([^\]]+)\]/.exec(a.text || '');
    const lab = m ? m[1] : '…';
    const cls = { 'PROUVÉ': 'ok', 'NON SOUTENU': 'err', 'INSUFFISANT': 'warn', 'PLAUSIBLE++': '' }[lab] ?? '';
    const pts = (t.nights || []).filter(x => x.qwen != null || x.sonnet != null);
    const g = (p) => (p.qwen != null && p.sonnet != null) ? (p.qwen + p.sonnet) / 2 : (p.qwen ?? p.sonnet ?? 0);
    const last = pts.length ? g(pts[pts.length - 1]).toFixed(2) : '—';
    const spark = pts.slice(-10).map(p => {
      const v = g(p), h = Math.max(2, Math.min(1, Math.max(0, v)) * 22);
      return `<div title="${esc(p.date)} · écart ${v.toFixed(2)}" style="width:5px;height:${h}px;background:${v > 0 ? 'var(--teal)' : 'rgba(249,168,212,.5)'};border-radius:2px;align-self:flex-end;"></div>`;
    }).join('');
    el.innerHTML = `<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
        <span class="badge ${cls}" title="Portes A/B/C pré-enregistrées">🧪 corpus : ${esc(lab)}</span>
        <span class="kv">${pts.length}/10 nuits</span>
        <span class="kv" title="rétention anamnèse ON − OFF (moyenne des 2 archis) ; >0 = le corpus façonne">écart ON−OFF ${last}</span>
        <div style="display:flex;gap:2px;height:24px;align-items:flex-end;">${spark}</div>
      </div>`;
  } catch (_) { el.innerHTML = ''; }
}

/* ---- FLUX LIVE (transplanté du cockpit v1) : hooks + événements de sessions, dédupliqués ---- */
const feed = []; const seen = new Set();
function addFeed(it, key) { if (seen.has(key)) return; seen.add(key); feed.unshift(it); if (feed.length > 80) feed.pop(); renderFeed(); }
function renderFeed() {
  $('feed').innerHTML = feed.map(f => {
    const hot = f.kind === 'tool' || f.kind === 'hook';
    const cls = hot ? ' hot' : (f.kind === 'user' ? ' user' : '');
    const icon = hot ? '⚙ ' : (f.kind === 'user' ? '› ' : '● ');
    return `<div class="feed-line${cls}" title="${esc((f.label || '') + ' ' + (f.text || ''))}">${esc(f.time)} ${icon}${esc(f.label || '')} <span style="color:var(--txt-4);">${esc(f.text || '')}</span></div>`;
  }).join('') || '<div class="kv">(en attente d’activité…)</div>';
  $('feed-count').textContent = '· ' + feed.length;
}

/* ---- SESSIONS + CONVERSATIONS D'AGENTS (transplanté du v1, restylé .list-item) ---- */
let sessData = { total: 0, active: 0, list: [] };
let agentData = { total: 0, active: 0, list: [] };
function renderSessions(data) {
  sessData = Array.isArray(data) ? { total: data.length, active: 0, list: data } : (data || sessData);
  // alimente le flux live depuis les événements récents des transcripts (cadence SSE inchangée)
  (sessData.list || []).forEach(s => (s.recent || []).forEach(e => {
    const key = 'S' + s.short + (e.t || '') + (e.name || e.text || '');
    if (e.kind === 'tool') addFeed({ time: fmtIso(e.t), kind: 'tool', label: e.name || 'outil', text: s.short }, key);
    else if (e.kind === 'user') addFeed({ time: fmtIso(e.t), kind: 'user', label: '', text: e.text || '' }, key);
    else if (e.kind === 'say') addFeed({ time: fmtIso(e.t), kind: 'say', label: '', text: e.text || '' }, key);
  }));
  paintSessions();
}
function renderAgents(data) { agentData = data || agentData; paintSessions(); }
function paintSessions() {
  const list = sessData.list || [], ags = agentData.list || [];
  $('sess-count').textContent = '· ' + (list.length < (sessData.total || 0) ? list.length + '/' + sessData.total : list.length)
    + (agentData.total ? ' · ' + agentData.total + ' agents' : '');
  const sHtml = list.map((s, i) => `
    <div class="list-item" data-sess="${i}">
      <div style="display:flex;gap:8px;align-items:center;">
        <span style="width:7px;height:7px;border-radius:50%;flex-shrink:0;background:${s.active ? 'var(--ok)' : 'rgba(255,255,255,.15)'};${s.active ? 'box-shadow:0 0 8px var(--ok);' : ''}"></span>
        <span class="mono" style="font-size:10px;color:var(--txt-2);">${esc(s.short)}</span>
        <span style="font-size:9px;color:var(--txt-4);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1;" title="${esc(s.project || '')}">${esc(s.project || '')}</span>
        <span style="font-size:8px;color:var(--txt-4);flex-shrink:0;">il y a ${esc(ago(s.mtime))}</span>
      </div>
      <div class="mono" style="font-size:8.5px;color:var(--txt-4);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:2px;">
        ${(s.recent || []).slice(-4).map(e => esc(e.kind === 'tool' ? '⚙' + (e.name || '') : (e.kind === 'user' ? '› ' : '· ') + (e.text || '').slice(0, 26))).join('  ')}
      </div>
    </div>`).join('') || '<div class="kv">(aucune session)</div>';
  const aHtml = ags.map((a, i) => `
    <div class="list-item" data-agent="${i}">
      <div style="display:flex;gap:8px;align-items:center;">
        <span style="width:7px;height:7px;border-radius:50%;flex-shrink:0;background:${a.active ? 'var(--ok)' : 'rgba(255,255,255,.15)'};${a.active ? 'box-shadow:0 0 8px var(--ok);' : ''}"></span>
        <span style="font-size:10px;color:var(--teal-hi);">${esc(a.type)}</span>
        ${a.wf ? `<span class="badge" style="font-size:8px;">⛓ ${esc(a.wf)}</span>` : ''}
        <span style="font-size:8px;color:var(--txt-4);margin-left:auto;flex-shrink:0;">${esc(ago(a.mtime))}</span>
      </div>
      <div style="font-size:9px;color:var(--txt-3);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${esc(a.desc || a.id)}</div>
    </div>`).join('') || '<div class="kv">(aucun sous-agent récent)</div>';
  $('sessions').innerHTML = sHtml
    + `<div style="font-size:8px;letter-spacing:2px;color:var(--txt-4);margin:10px 0 4px;">⛓ CONVERSATIONS D'AGENTS${agentData.active ? ` <span style="color:var(--ok);">· ${Number(agentData.active) || 0} actif</span>` : ''}</div>`
    + aHtml;
  $('sessions').querySelectorAll('[data-sess]').forEach(n => { n.onclick = () => openSession(list[+n.dataset.sess]); });
  $('sessions').querySelectorAll('[data-agent]').forEach(n => { n.onclick = () => openAgentConvo(ags[+n.dataset.agent]); });
}
async function openSession(s) {
  if (!s) return;
  const title = 'Session ' + (s.short || '');
  const meta = [['projet', s.project], ['dernière activité', 'il y a ' + ago(s.mtime)]];
  const base = [{ txt: s.active ? 'ACTIVE' : 'INACTIVE', cls: s.active ? 'ok' : '' }];
  if (!s.rel) {   // repli : aperçu tronqué si pas de chemin de transcript
    const lines = (s.recent || []).map(e =>
      (e.t ? fmtIso(e.t) + '  ' : '') + (e.kind === 'tool' ? '⚙ ' + (e.name || 'outil') : (e.kind === 'user' ? '› ' : '● ') + (e.text || ''))).join('\n');
    return showDetail({ title, badges: base, meta, text: lines || '(aucun événement récent)' });
  }
  showDetail({ title, badges: base, meta, text: 'chargement de la conversation…' });
  try {   // transcript COMPLET à la demande (réutilise /api/agent → getAgentConvo, flux SSE intact)
    const d = await (await fetch('/api/agent?file=' + encodeURIComponent(s.rel))).json();
    if (d.error) return showDetail({ title, badges: base, meta, text: 'Erreur : ' + d.error });
    const txt = (d.turns || []).map(t => {
      const lbl = t.kind === 'tool' ? '⚙ ' + (t.name || 'outil') : t.kind === 'result' ? '↩ résultat'
        : t.kind === 'think' ? '✻ réflexion' : t.role === 'user' ? '› prompt' : '● assistant';
      return lbl + '\n' + (t.text || '');
    }).join('\n\n──────────\n\n');
    showDetail({ title, badges: [{ txt: (d.turns || []).length + ' tours' }, ...base], meta, text: txt || '(conversation vide)' });
  } catch (_) { showDetail({ title, badges: base, meta, text: 'Erreur de chargement.' }); }
}
async function openAgentConvo(a) {
  if (!a || !a.rel) return;
  const title = 'Agent ' + (a.type || '') + (a.wf ? ' · wf ' + a.wf : '');
  showDetail({ title, meta: [['description', a.desc || a.id]], text: 'chargement de la conversation…' });
  try {
    const d = await (await fetch('/api/agent?file=' + encodeURIComponent(a.rel))).json();
    if (d.error) { showDetail({ title, meta: [], text: 'Erreur : ' + d.error }); return; }
    const txt = (d.turns || []).map(t => {
      const lbl = t.kind === 'tool' ? '⚙ ' + (t.name || 'outil') : t.kind === 'result' ? '↩ résultat'
        : t.kind === 'think' ? '✻ réflexion' : t.role === 'user' ? '› prompt' : '● agent';
      return lbl + '\n' + (t.text || '');
    }).join('\n\n──────────\n\n');
    showDetail({
      title,
      badges: [{ txt: (d.turns || []).length + ' tours' }, ...(a.active ? [{ txt: 'ACTIF', cls: 'ok' }] : [])],
      meta: [['description', a.desc || a.id], ['projet', a.project]],
      text: txt || '(conversation vide)',
    });
  } catch (_) { showDetail({ title, meta: [], text: 'Erreur de chargement.' }); }
}

/* ---- INVENTAIRE ACTIF (transplanté du v1) : MCP / skills / agents / CLIs / plugins ---- */
function renderInventory(inv) {
  if (!inv) return;
  const dotc = { connected: 'var(--ok)', auth: 'var(--warn)', down: 'var(--err)' };
  const chip = (inner, title) => `<span class="mono" ${title ? `title="${esc(title)}"` : ''} style="font-size:9px;padding:2px 8px;border:1px solid rgba(45,212,191,.16);border-radius:99px;color:var(--txt-3);white-space:nowrap;">${inner}</span>`;
  const group = (name, n, inner) => `<div style="margin-bottom:9px;">
    <div style="font-size:8px;letter-spacing:2px;color:var(--txt-4);margin-bottom:4px;">${esc(name)}${n != null ? ' · ' + Number(n) : ''}</div>
    <div style="display:flex;flex-wrap:wrap;gap:4px;">${inner || '<span class="kv">(vide)</span>'}</div></div>`;
  const mcp = (inv.mcp || []).map(m => chip(`<span style="color:${dotc[m.status] || 'var(--txt-4)'};">●</span> ${esc(m.name)}`, m.status)).join('');
  const skills = (inv.skills || []).map(s => chip(esc(s.name), s.desc || '')).join('');
  const agents = (inv.agents || []).map(a => chip(esc(a.name), a.source || '')).join('');
  const clis = (inv.clis || []).map(c => chip(`${esc(c.name)}${c.version ? ` <span style="color:var(--txt-4);">${esc(c.version)}</span>` : ''}`, c.kind || '')).join('');
  const plugins = (inv.plugins || []).map(p => chip(esc(String(p.name || '').split('@')[0]))).join('');
  $('inventory').innerHTML =
    group('MCP', (inv.mcp || []).length, mcp)
    + group('SKILLS', (inv.skills || []).length, skills)
    + group('AGENTS', (inv.agents || []).length, agents)
    + group('CLIS', (inv.clis || []).length, clis)
    + group('PLUGINS', (inv.plugins || []).length, plugins);
  const conn = (inv.mcp || []).filter(m => m.status === 'connected').length;
  $('inv-sum').textContent = `· ${conn}/${(inv.mcp || []).length} MCP · ${(inv.skills || []).length} skills · ${(inv.agents || []).length} agents · ${(inv.clis || []).length} CLI · ${(inv.plugins || []).length} plugins`;
}

/* ---- SSE (cadence inchangée : /api/stream tel quel, mêmes événements que le v1) ---- */
function connect() {
  const es = new EventSource('/api/stream');
  es.addEventListener('open', () => { $('feed-count').textContent = '· ' + feed.length; });
  es.addEventListener('error', () => { $('feed-count').textContent = '· reconnexion…'; });
  // humeur/pensées/mémoires en live comme au v1 (le poll 30 s reste en filet) — dédup sur le
  // payload brut : un tick identique ne repeint pas (sinon l'orbe redémarrerait toutes les 1,5 s).
  es.addEventListener('anamnese', (e) => { try { if (e.data === connect._anam) return; connect._anam = e.data; const a = JSON.parse(e.data); renderMood(a); renderThoughts(a.thoughts); renderMemories(a.memories); } catch (_) {} });
  es.addEventListener('inventory', (e) => { try { renderInventory(JSON.parse(e.data)); } catch (_) {} });
  es.addEventListener('sessions', (e) => { try { renderSessions(JSON.parse(e.data)); } catch (_) {} });
  es.addEventListener('agents', (e) => { try { renderAgents(JSON.parse(e.data)); } catch (_) {} });
  es.addEventListener('hooks', (e) => {
    try {
      JSON.parse(e.data).forEach(ev => addFeed(
        { time: fmtT(ev.ts), kind: 'hook', label: ev.tool || ev.type, text: ev.summary || ev.type },
        'H' + ev.ts + (ev.tool || '') + (ev.summary || '')));
    } catch (_) {}
  });
}

/* ---- boot ---- */
(async function boot() {
  [['feed', 480], ['sessions', 420], ['inventory', 420]].forEach(([id, h]) => { const n = $(id); n.style.maxHeight = h + 'px'; n.style.overflowY = 'auto'; });
  try {
    const a = await (await fetch('/api/anamnese')).json();
    renderMood(a); renderThoughts(a.thoughts); renderMemories(a.memories);
    $('mem-count').textContent = '· ' + ((a.memories || []).length) + ' récentes';
  } catch (_) {}
  renderDreams();
  setInterval(async () => { try { const a = await (await fetch('/api/anamnese')).json(); renderMood(a); renderThoughts(a.thoughts); renderMemories(a.memories); } catch (_) {} }, 30000);
  // SSE + sessions + inventaire : logique du v1 transplantée (fallback REST puis flux live).
  fetch('/api/inventory').then(r => r.json()).then(renderInventory).catch(() => {});
  fetch('/api/agents').then(r => r.json()).then(renderAgents).catch(() => {});
  connect();
})();
