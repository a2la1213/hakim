/* Cockpit — CHAT (Claude via CLI abonnement + éventuels modèles locaux Ollama/MLX),
   avec mode comparaison côte à côte. But : juger À LA MAIN ce que les benchmarks
   ne disent pas (qualité de rêve, de réflexion, de conversation). */
initNav('chat');

const $ = (id) => document.getElementById(id);
const state = { models: [], hist: { A: [], B: [] }, busy: false };

function optionsFor(sel, models, preferred) {
  sel.innerHTML = models.map(m =>
    `<option value="${esc(m.via)}::${esc(m.id)}">${esc(m.label)} · ${esc(m.via)}</option>`).join('');
  const hit = models.findIndex(m => preferred && m.id.includes(preferred));
  if (hit >= 0) sel.selectedIndex = hit;
}

async function loadModels() {
  try {
    const r = await (await fetch('/api/models')).json();
    state.models = [...(r.claude || []), ...(r.ollama || []), ...(r.mlx || [])];
    if (!state.models.length) { $('hint').textContent = r.note || 'aucun modèle disponible'; return; }
    optionsFor($('mA'), state.models, 'sonnet');   // défaut A : le cerveau actuel
    optionsFor($('mB'), state.models, 'opus');     // défaut B : le comparatif
    $('hint').textContent = (r.note ? r.note + ' · ' : '')
      + `${state.models.length} modèles · MLX chargé : ${r.mlx_loaded || 'aucun'}`;
  } catch (e) { $('hint').textContent = 'cockpit : /api/models injoignable'; }
}

function render(side) {
  const log = $('l' + side);
  log.innerHTML = state.hist[side].map(m => {
    if (m.role === 'user') return `<div class="msg u"><span class="who">toi</span>${esc(m.content)}</div>`;
    if (m.error) return `<div class="msg err"><span class="who">erreur</span>${esc(m.error)}</div>`;
    // met en valeur un appel d'outil, quel que soit le format (Qwen JSON ou Gemma call:)
    const raw = m.content || '';
    const qwen = raw.match(/<tool_call>\s*([\s\S]*?)\s*<\/tool_call>/);
    const gemma = raw.match(/<\|tool_call>\s*([\s\S]*?)\s*<tool_call\|>/);
    const call = qwen ? qwen[1] : (gemma ? gemma[1] : null);
    const rest = call ? raw.replace(qwen ? qwen[0] : gemma[0], '').trim() : raw;
    return `<div class="msg a"><span class="who">modèle</span>${esc(rest)}`
      + (call ? `<div class="tool">⚙︎ ${esc(call)}</div>` : '') + '</div>';
  }).join('');
  log.scrollTop = log.scrollHeight;
}

async function ask(side, text) {
  const sel = $('m' + side).value;
  if (!sel) return;
  const [via, model] = sel.split('::');
  $('t' + side).textContent = $('m' + side).selectedOptions[0].textContent;
  state.hist[side].push({ role: 'user', content: text });
  render(side);
  $('ms' + side).textContent = '…';
  try {
    const r = await (await fetch('/api/chat', {
      method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() },
      body: JSON.stringify({ via, model, messages: state.hist[side].filter(m => !m.error),
        max_tokens: 512, think: $('think').checked })
    })).json();
    if (r.error && !r.text) state.hist[side].push({ role: 'assistant', error: r.error });
    else state.hist[side].push({ role: 'assistant', content: r.text });
    $('ms' + side).textContent = r.ms != null ? `${(r.ms / 1000).toFixed(1)} s` : '';
  } catch (e) {
    state.hist[side].push({ role: 'assistant', error: String(e.message || e) });
    $('ms' + side).textContent = '';
  }
  render(side);
}

async function send() {
  const q = $('q').value.trim();
  if (!q || state.busy) return;
  state.busy = true; $('send').disabled = true; $('q').value = '';
  const two = $('cmp').checked;
  // séquentiel si les deux sont MLX : un seul modèle tient en mémoire à la fois
  const bothMlx = two && $('mA').value.startsWith('mlx') && $('mB').value.startsWith('mlx');
  if (two && !bothMlx) await Promise.all([ask('A', q), ask('B', q)]);
  else { await ask('A', q); if (two) await ask('B', q); }
  state.busy = false; $('send').disabled = false; $('q').focus();
}

$('cmp').addEventListener('change', (e) => {
  $('mB').disabled = !e.target.checked;
  $('pB').hidden = !e.target.checked;
  $('cols').classList.toggle('two', e.target.checked);
});
$('send').addEventListener('click', send);
$('q').addEventListener('keydown', (e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) send(); });
$('clear').addEventListener('click', () => {
  state.hist.A = []; state.hist.B = []; render('A'); render('B');
  $('msA').textContent = ''; $('msB').textContent = '';
});

loadModels();
