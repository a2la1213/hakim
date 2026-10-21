/* Cockpit v2 — overlay de détail universel : la fin du texte tronqué. */
(function () {
  let ov = null;
  function close() { if (ov) { ov.remove(); ov = null; document.removeEventListener('keydown', onKey); } }
  function onKey(e) { if (e.key === 'Escape') close(); }

  window.showDetail = function ({ title, badges = [], meta = [], text = '', voice = false }) {
    close();
    ov = document.createElement('div');
    ov.className = 'overlay';
    ov.innerHTML = `<div class="overlay-panel">
      <span class="close" title="fermer (Échap)">✕</span>
      <h3>${esc(title)}</h3>
      <div class="meta">${badges.map(b => `<span class="badge ${esc(b.cls || '')}">${esc(b.txt)}</span>`).join('')}</div>
      <div class="meta">${meta.filter(([, v]) => v !== null && v !== undefined && v !== '').map(([k, v]) => `<span class="kv">${esc(k)} <b>${esc(v)}</b></span>`).join('')}</div>
      <div class="full-text ${voice ? 'voice' : ''}">${esc(text)}</div>
    </div>`;
    ov.addEventListener('click', (e) => { if (e.target === ov || e.target.classList.contains('close')) close(); });
    document.addEventListener('keydown', onKey);
    document.body.appendChild(ov);
  };

  window.showEpisode = async function (id) {
    id = Number(id);
    if (!Number.isInteger(id) || id < 0) return;
    try {
      const ep = await (await fetch('/api/memory?id=' + id)).json();
      if (ep.error) return;
      const d = ep.ts ? new Date(ep.ts * 1000).toLocaleString('fr-FR') : '';
      window.showDetail({
        title: `Souvenir #${ep.id} · ${ep.role || ''}`,
        badges: (ep.facets || []).slice(0, 8).map(f => ({ txt: f })),
        meta: [['date', d], ['rubrique', ep.rubric], ['importance', ep.importance != null ? (+ep.importance).toFixed(2) : null],
               ['rappels', ep.recall_count], ['valence', ep.enc_valence != null ? (+ep.enc_valence).toFixed(2) : null],
               ['éveil', ep.enc_arousal != null ? (+ep.enc_arousal).toFixed(2) : null]],
        text: ep.content || '',
        voice: ['thought', 'reflection', 'dream', 'reasoning'].includes(ep.role),
      });
    } catch (_) { /* réseau : silencieux */ }
  };
})();
