/* (10/11, lettre de Hakim de 18:14 écrite à la demande de papa) la page « Fil d'actualité » : ses publications (/api/actualite, derrière
   le jeton), la plus récente d'abord ; ce qui est arrivé depuis ta dernière visite est marqué (badges.js). Les fichiers sont des pièces
   (/api/pieces/<id>), chargées avec le jeton, jamais ouvertes comme une page : une image en aperçu, un son joué ici, le reste
   téléchargé (dans l'appli : Téléchargements). Tout ce qui vient du fil passe par esc() avant d'entrer dans le HTML. */
(() => {
  const $ = (id) => document.getElementById(id);
  const H = () => ({ 'X-Jeton': jeton() });
  const IMAGES = new Set(['png', 'jpg', 'jpeg', 'gif', 'webp']);
  const SONS = { mp3: 'audio/mpeg', m4a: 'audio/mp4', aac: 'audio/aac', ogg: 'audio/ogg', wav: 'audio/wav', flac: 'audio/flac', opus: 'audio/ogg' };
  const blobs = new Map();
  let depuis = Date.now(), dernier = '';
  const dire = (t) => { $('bulle').textContent = t; clearTimeout(dire.m); dire.m = setTimeout(() => { $('bulle').textContent = ''; }, 5000); };
  const taille = (n) => n < 1024 ? `${n} o` : n < 1048576 ? `${Math.round(n / 1024)} Ko` : `${(n / 1048576).toFixed(1).replace('.', ',')} Mo`;
  const quand = (ts) => new Date(ts).toLocaleString('fr-FR', { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });

  async function blob(id) {
    if (blobs.has(id)) return blobs.get(id);
    const r = await fetch(`/api/pieces/${encodeURIComponent(id)}`, { headers: H() });
    if (!r.ok) throw new Error(r.status === 403 ? 'jeton refusé : recharge la page' : `fichier indisponible (${r.status})`);
    const b = await r.blob();
    blobs.set(id, b);
    return b;
  }

  function htmlPiece(p) {
    const t = String(p.type || '').toLowerCase(), nom = `${esc(p.titre || p.nom)} · ${esc(taille(Number(p.taille) || 0))}`;
    if (IMAGES.has(t)) return `<div class="fichier"><img data-apercu="${esc(p.id)}" alt="${esc(p.titre || p.nom)}">`
      + `<div class="gestes"><span class="nom">${nom}</span><button type="button" data-garder="${esc(p.id)}" data-nom="${esc(p.nom)}">⬇ enregistrer</button></div></div>`;
    if (SONS[t]) return `<div class="fichier"><span class="nom">🎵 ${nom}</span><div class="gestes">`
      + `<button type="button" data-ecouter="${esc(p.id)}" data-son="${esc(SONS[t])}">▶ écouter</button>`
      + `<button type="button" data-garder="${esc(p.id)}" data-nom="${esc(p.nom)}">⬇ enregistrer</button></div></div>`;
    return `<div class="fichier"><span class="nom">📄 ${nom}</span><div class="gestes">`
      + `<button type="button" data-garder="${esc(p.id)}" data-nom="${esc(p.nom)}">⬇ enregistrer</button></div></div>`;
  }

  function rendre(l) {
    const cle = JSON.stringify(l.map(x => x.id));
    if (cle === dernier) return;
    dernier = cle;
    $('fil').innerHTML = l.length ? l.map(x => `<article class="glass pub${x.ts > depuis ? ' nouveau' : ''}" data-id="${esc(x.id)}">`
      + `<div class="quand">${esc(quand(x.ts))}</div>${x.texte ? `<div class="texte">${esc(x.texte)}</div>` : ''}`
      + `${x.piece ? htmlPiece(x.piece) : ''}</article>`).join('')
      : '<div class="vide">Rien pour l’instant. Quand Hakim publie un mot ou un fichier pour toi, il arrive ici.</div>';
    for (const img of document.querySelectorAll('img[data-apercu]:not([src])')) {
      blob(img.dataset.apercu).then((b) => { img.src = URL.createObjectURL(b); }).catch(() => img.remove());
    }
  }

  async function charger() {
    try {
      const r = await fetch('/api/actualite', { headers: H(), cache: 'no-store' });
      if (!r.ok) throw new Error(`le cockpit répond ${r.status}`);
      const d = await r.json();
      rendre(Array.isArray(d.publications) ? d.publications : []);
    } catch (e) { if (!dernier) $('fil').innerHTML = `<div class="vide">${esc(String(e.message || e))}</div>`; }
  }

  $('fil').addEventListener('click', async (e) => {
    const b = e.target.closest('button[data-ecouter], button[data-garder]');
    if (!b) return;
    b.disabled = true;
    try {
      if (b.dataset.ecouter) {
        const brut = await blob(b.dataset.ecouter);
        const a = document.createElement('audio');
        a.controls = true; a.preload = 'auto'; a.src = URL.createObjectURL(new Blob([brut], { type: b.dataset.son || 'audio/mpeg' }));
        b.replaceWith(a);
        a.play().catch(() => {});
        return;
      }
      const brut = await blob(b.dataset.garder), nom = b.dataset.nom || 'fichier';
      if (window.HakimApp && window.HakimApp.enregistrer) {            // l'appli Android : le fichier va dans Téléchargements
        const b64 = await new Promise((ok, ko) => { const r = new FileReader(); r.onload = () => ok(String(r.result).split(',')[1] || ''); r.onerror = ko; r.readAsDataURL(brut); });
        dire(window.HakimApp.enregistrer(b64, nom) || 'enregistré dans Téléchargements');
      } else {
        const a = document.createElement('a');
        a.href = URL.createObjectURL(new Blob([brut], { type: 'application/octet-stream' })); a.download = nom;
        document.body.appendChild(a); a.click(); a.remove();
      }
      b.disabled = false;
    } catch (err) { b.disabled = false; dire(String(err.message || err)); }
  });

  Badges.ouvrir('actualite').then((t) => { depuis = Number(t) || depuis; dernier = ''; charger(); }).catch(() => {});
  charger();
  setInterval(() => { if (document.visibilityState === 'visible') charger(); }, 20000);
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') charger(); });
})();
