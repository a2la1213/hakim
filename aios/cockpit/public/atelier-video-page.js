/* (13/11) la page Atelier, partie VIDÉO : la médiathèque (collections, dépôt depuis le téléphone ou le PC avec sa jauge, aperçus, choix des
   photos dans l'ordre, musiques à écouter, effacement), la vidéo (format, durée, rythme, transitions, textes), l'aperçu en petit, l'export, et
   les vidéos finies (voir, télécharger la vidéo et la couverture, refaire, effacer). Les fichiers passent derrière le jeton (blobs).
   Sur un appareil sans atelier visuel (pas de Mac), les sections « image » et « clip » se cachent. */
(() => {
  const $ = (id) => document.getElementById(id);
  const H = () => ({ 'X-Jeton': window.jeton() });
  const esc = window.esc;
  let etat = null, collection = '', choisies = [], musique = null, minuteur = 0, sig = '', sigApercu = '', apercuAttendu = '';
  const garder = (k, v) => { try { localStorage.setItem(`atelier-video-${k}`, v); } catch (_) {} };
  const relire = (k) => { try { return localStorage.getItem(`atelier-video-${k}`) || ''; } catch (_) { return ''; } };
  const dire = (t, ms = 6000) => { const b = $('bulle'); if (!b) return; b.textContent = t; clearTimeout(dire.m); if (ms) dire.m = setTimeout(() => { b.textContent = ''; }, ms); };
  const duree = (s) => { s = Math.round(Number(s) || 0); return s ? `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}` : '—'; };
  const mo = (n) => (n >= 1 << 20 ? `${(n / (1 << 20)).toFixed(1).replace('.', ',')} Mo` : `${Math.max(1, Math.round(n / 1024))} Ko`);
  const valeur = (nom) => (document.querySelector(`input[name="${nom}"]:checked`) || {}).value || '';
  const FORMATS = { '9:16': 'TikTok · Reels', '4:5': 'Post Insta', '1:1': 'Carré' };

  async function poster(chemin, corps) {
    const r = await fetch(chemin, { method: 'POST', headers: { ...H(), 'Content-Type': 'application/json' }, body: JSON.stringify(corps || {}) });
    const o = await r.json().catch(() => ({}));
    if (!r.ok || o.ok === false) throw new Error(o.erreur || `erreur ${r.status}`);
    return o;
  }
  const blobs = new Map();
  function urlDe(chemin) {
    if (blobs.has(chemin)) return blobs.get(chemin);
    const p = fetch(chemin, { headers: H() }).then((r) => { if (!r.ok) throw new Error('fichier introuvable'); return r.blob(); }).then((b) => URL.createObjectURL(b));
    blobs.set(chemin, p);
    p.catch(() => blobs.delete(chemin));
    return p;
  }
  const media = (c, f, apercu) => `/api/atelier/media/fichier?c=${encodeURIComponent(c)}&f=${encodeURIComponent(f)}${apercu ? '&apercu=1' : ''}`;
  const fichierVideo = (f) => `/api/atelier/video/fichier?f=${encodeURIComponent(f)}`;
  const vue = 'IntersectionObserver' in window ? new IntersectionObserver((l) => {
    for (const e of l) if (e.isIntersecting) { vue.unobserve(e.target); remplir(e.target); }
  }, { rootMargin: '200px' }) : null;
  function remplir(img) { urlDe(img.dataset.src).then((u) => { img.src = u; }).catch(() => { img.alt = 'introuvable'; }); }
  function observer(r) { for (const img of r.querySelectorAll('img[data-src]')) { if (vue) vue.observe(img); else remplir(img); } }

  /* ---------- la médiathèque ---------- */
  const col = () => (etat && etat.collections.find(c => c.nom === collection)) || null;
  function rendreCollections() {
    const l = etat.collections;
    if (!l.some(c => c.nom === collection)) collection = (l.find(c => c.nom === relire('collection')) || l[0] || {}).nom || '';
    $('collections').innerHTML = l.length
      ? l.map(c => `<button type="button" data-collection="${esc(c.nom)}" aria-pressed="${c.nom === collection}">${esc(c.nom)} <span class="g">${c.photos.length} 📷 · ${c.musiques.length} ♪</span></button>`).join('')
        + (col() && !col().photos.length && !col().musiques.length ? `<button type="button" data-effacer-collection="${esc(collection)}" aria-label="Effacer la collection vide « ${esc(collection)} »">✕ Effacer « ${esc(collection)} »</button>` : '')
      : '<span class="sous">Aucune collection : crée la première (une collection de vêtements = un dossier).</span>';
  }
  function rendrePhotos() {
    const c = col(), ph = c ? c.photos : [];
    choisies = choisies.filter(f => ph.some(p => p.f === f));
    $('photosMedia').innerHTML = ph.map((p) => {
      const i = choisies.indexOf(p.f);
      return `<div class="media" ${i >= 0 ? 'aria-current="true"' : ''}><button type="button" class="choix-photo" data-photo="${esc(p.f)}" aria-pressed="${i >= 0}"
        aria-label="${esc(p.f)}${i >= 0 ? `, photo ${i + 1}` : ''}">${p.apercu ? `<img data-src="${esc(media(c.nom, p.f, true))}" alt="">` : ''}</button>`
        + `${i >= 0 ? `<span class="rang">${i + 1}</span>` : ''}<button type="button" class="effacer" data-effacer-photo="${esc(p.f)}" aria-label="Effacer ${esc(p.f)}">✕</button></div>`;
    }).join('');
    $('aidePhotos').textContent = !c ? '' : ph.length ? (choisies.length ? `${choisies.length} photo${choisies.length > 1 ? 's' : ''} choisie${choisies.length > 1 ? 's' : ''}, dans cet ordre.`
      : `Touche les photos à montrer, dans l’ordre (aucune : les ${ph.length} de la collection).`) : 'Pas encore de photo dans cette collection : dépose-les ci-dessus.';
    $('gestesPhotos').hidden = !ph.length;
    observer($('photosMedia'));
  }
  function rendreMusiques() {
    const c = col();
    // ses musiques d'abord, puis celles des autres collections
    const toutes = [];
    for (const k of etat.collections) for (const m of k.musiques) toutes.push({ ...m, c: k.nom });
    toutes.sort((a, b) => (a.c === collection ? 0 : 1) - (b.c === collection ? 0 : 1));
    if (musique && musique !== '-' && !toutes.some(m => `${m.c}/${m.f}` === musique)) musique = null;
    if (musique === null) musique = toutes.length ? `${toutes[0].c}/${toutes[0].f}` : '-';
    const ligne = (val, nom, meta, lecture) => `<div class="musique" ${musique === val ? 'aria-current="true"' : ''}>`
      + `<button type="button" role="radio" aria-checked="${musique === val}" data-musique="${esc(val)}">${musique === val ? '●' : '○'}</button>`
      + `<span class="nom">${esc(nom)}</span><span class="meta">${esc(meta)}</span>${lecture || ''}</div>`;
    $('musiquesMedia').innerHTML = toutes.map(m => ligne(`${m.c}/${m.f}`, m.f, `${m.c !== collection ? `${m.c} · ` : ''}${m.duree_s ? duree(m.duree_s) : mo(m.taille)}${m.bpm ? ` · ${Math.round(m.bpm)} BPM` : ''}`,
      `<button type="button" data-ecouter="${esc(media(m.c, m.f))}" aria-label="Écouter ${esc(m.f)}">▶︎</button>`
      + `<button type="button" data-effacer-musique="${esc(m.f)}" data-c="${esc(m.c)}" aria-label="Effacer ${esc(m.f)}">✕</button>`)).join('')
      + ligne('-', 'Sans musique (tu ajoutes un son dans TikTok)', 'grille à 120 BPM', '');
    void c;
  }

  /* ---------- les vidéos ---------- */
  function rendreVideos() {
    const v = etat.videos || [];
    $('videosFinies').innerHTML = v.length ? v.map((x) => {
      const m = [x.duree_s ? `${Math.round(x.duree_s)} s` : '', x.bpm ? `${Math.round(x.bpm)} BPM` : '', x.lufs !== null && x.lufs !== undefined ? `${String(x.lufs).replace('.', ',').replace('-', '−')} LUFS` : ''].filter(Boolean).join(' · ');
      return `<figure class="tuile"><div class="cadre vertical">${x.vignette ? `<img data-src="${esc(fichierVideo(x.vignette))}" alt="${esc(x.titre)}">` : ''}</div>`
        + `<figcaption>${esc(x.titre)}<div class="meta">${esc(m)}${x.raison ? ` · ${esc(x.raison)}` : ''}</div><div class="gestes">`
        + x.videos.map(f => `<button type="button" data-voir-video="${esc(f.f)}" data-titre="${esc(x.titre)}">▶︎ ${esc(FORMATS[f.format] || f.format)}</button>`
          + `<button type="button" data-dl="${esc(f.f)}" aria-label="Télécharger la vidéo ${esc(f.format)}">⬇︎</button>`).join('')
        + (x.couverture ? `<button type="button" data-dl="${esc(x.couverture)}" aria-label="Télécharger la couverture">🖼 Couverture</button>` : '')
        + `<button type="button" data-refaire="${esc(x.nom)}" aria-label="Refaire « ${esc(x.titre)} »">↻ Refaire</button>`
        + `<button type="button" data-effacer-video="${esc(x.nom)}" aria-label="Effacer « ${esc(x.titre)} »">✕</button></div></figcaption></figure>`;
    }).join('') : '<div class="vide">Aucune vidéo pour l’instant.</div>';
    observer($('videosFinies'));
  }
  function rendreApercu() {
    const a = (etat.apercus || [])[0], z = $('apercuZone');
    const attendu = !!apercuAttendu && (!a || a.nom.slice(0, 15) < apercuAttendu);
    const vivant = (etat.enCours || []).some(x => x.type === 'apercu' && x.etat === 'en cours');
    const s = attendu ? (vivant ? 'attente' : 'rate') : a ? a.nom : '';
    if (s === sigApercu) return;
    sigApercu = s;
    if (attendu) { z.hidden = false; z.innerHTML = `<div class="sous">${vivant ? 'L’aperçu se monte…' : 'L’aperçu ne s’est pas monté (voir la ligne en rouge).'}</div>`; return; }
    if (!a || !a.videos.length) { z.hidden = true; z.innerHTML = ''; return; }
    z.hidden = false;
    z.innerHTML = `<div class="sous">Aperçu (petit) : ${esc(a.titre)}${a.bpm ? ` · ${Math.round(a.bpm)} BPM` : ''}${a.coupes ? ` · ${a.coupes} coupes` : ''}${a.raison ? ` · ${esc(a.raison)}` : ''}</div><div class="sous">Chargement…</div>`;
    urlDe(fichierVideo(a.videos[0].f)).then((u) => {
      if (sigApercu !== s) return;
      z.lastElementChild.outerHTML = `<video controls playsinline autoplay src="${esc(u)}" aria-label="Aperçu de ${esc(a.titre)}"></video>`;
    }).catch(() => { z.lastElementChild.textContent = 'Aperçu introuvable.'; });
  }
  function rendreCalculs() {
    // les vidéos en cours, sous les boutons (la carte « En cours » de la page reste celle de l'atelier visuel)
    const bloc = $('calculsVideo');
    const c = etat.enCours || [];
    bloc.innerHTML = c.map((x) => {
      const p = x.progres ? x.progres.f : 0, quoi = `${x.type === 'apercu' ? '👁 Aperçu' : '🎞️ Vidéo'} « ${esc(x.titre)} »`;
      if (x.etat === 'ratée') return `<div class="calcul rate">${quoi} : ratée${x.erreur ? ` (${esc(x.erreur)})` : ''}</div>`;
      return `<div class="calcul"><div class="tete"><span>${quoi} — ${Math.round(p * 100)} %${x.progres && x.progres.texte ? ` · ${esc(x.progres.texte)}` : ''}</span>`
        + `<button type="button" data-arreter-video="${esc(x.tache)}" aria-label="Arrêter « ${esc(x.titre)} »">Arrêter</button></div>`
        + `<div class="jauge" role="progressbar" aria-label="${esc(x.titre)}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${Math.round(p * 100)}"><i style="width:${Math.round(p * 100)}%"></i></div></div>`;
    }).join('');
  }
  function rendre() {
    if (!etat) return;
    $('videoCarte').hidden = !etat.allume;
    for (const s of document.querySelectorAll('[data-visuel]')) s.hidden = !etat.visuel_installe;
    if (!etat.allume) return;
    const s = JSON.stringify([etat.collections, etat.videos, collection, choisies, musique]);
    if (s !== sig) { sig = s; rendreCollections(); rendrePhotos(); rendreMusiques(); rendreVideos(); }
    rendreApercu(); rendreCalculs();
  }

  async function charger() {
    clearTimeout(minuteur);
    let avant = etat ? (etat.enCours || []).filter(x => x.etat === 'en cours').length : 0;
    try {
      const r = await fetch('/api/atelier/media/etat', { headers: H(), cache: 'no-store' });
      if (r.ok) {
        etat = await r.json();
        rendre();
        const maintenant = (etat.enCours || []).filter(x => x.etat === 'en cours').length;
        if (avant > maintenant) dire('Une vidéo est prête ✨');
        avant = maintenant;
      }
    } catch (_) {}
    const actif = etat && (etat.enCours || []).some(x => x.etat === 'en cours');
    minuteur = setTimeout(charger, document.hidden ? 30000 : actif ? 2500 : 15000);
  }
  document.addEventListener('visibilitychange', () => { if (!document.hidden) charger(); });

  /* ---------- le dépôt : un fichier après l'autre, avec sa jauge ---------- */
  function envoyer(f, c, ligne) {
    return new Promise((ok) => {
      const x = new XMLHttpRequest();
      x.open('POST', `/api/atelier/media/deposer?collection=${encodeURIComponent(c)}`);
      x.setRequestHeader('X-Jeton', window.jeton());
      x.setRequestHeader('X-Nom', encodeURIComponent(f.name));
      x.setRequestHeader('Content-Type', 'application/octet-stream');
      x.upload.onprogress = (e) => { if (e.lengthComputable) ligne.textContent = `${f.name} — ${Math.round(100 * e.loaded / e.total)} %`; };
      x.onload = () => {
        let o = {}; try { o = JSON.parse(x.responseText); } catch (_) {}
        if (x.status === 200 && o.ok) { ligne.textContent = `✓ ${o.fichier || f.name}${o.fichier && o.fichier !== f.name ? ` (${f.name})` : ''}`; ok(true); }
        else { ligne.textContent = `✕ ${f.name} : ${o.erreur || `erreur ${x.status}`}`; ligne.className = 'rate'; ok(false); }
      };
      x.onerror = () => { ligne.textContent = `✕ ${f.name} : envoi coupé`; ligne.className = 'rate'; ok(false); };
      x.send(f);
    });
  }
  $('deposerMedia').addEventListener('click', () => {
    if (!collection) { dire('Crée d’abord une collection (＋ Collection).'); return; }
    $('fichiersMedia').click();
  });
  $('fichiersMedia').addEventListener('change', async (e) => {
    const l = [...e.target.files]; e.target.value = '';
    if (!l.length || !collection) return;
    const c = collection, zone = $('envois');
    zone.innerHTML = '';
    let bons = 0;
    for (const f of l) {
      const ligne = document.createElement('div'); ligne.textContent = `${f.name} — en attente`; zone.appendChild(ligne);
      if (f.size > 200 * 1024 * 1024) { ligne.textContent = `✕ ${f.name} : trop lourd (200 Mo au plus)`; ligne.className = 'rate'; continue; }
      if (await envoyer(f, c, ligne)) bons++;
      if (bons && bons % 4 === 0) charger();
    }
    dire(`${bons} fichier${bons > 1 ? 's' : ''} rangé${bons > 1 ? 's' : ''} dans « ${c} ».`);
    charger();
  });
  $('nouvelleCollection').addEventListener('click', async () => {
    const n = (window.prompt('Le nom de la collection (par exemple « Hiver 2026 ») :') || '').trim();
    if (!n) return;
    try { const o = await poster('/api/atelier/media/collection', { nom: n }); collection = o.nom; garder('collection', o.nom); choisies = []; await charger(); }
    catch (e) { dire(e.message); }
  });
  $('toutesPhotos').addEventListener('click', () => { const c = col(); choisies = c ? c.photos.map(p => p.f).slice(0, 30) : []; sig = ''; rendre(); });
  $('aucunePhoto').addEventListener('click', () => { choisies = []; sig = ''; rendre(); });

  /* ---------- la vidéo ---------- */
  for (const [id, k] of [['marqueVideo', 'marque'], ['appelVideo', 'appel']]) {
    $(id).value = relire(k);
    $(id).addEventListener('change', () => garder(k, $(id).value.trim()));
  }
  function demande(apercu) {
    const c = col();
    const q = { collection, photos: choisies.map(f => `${collection}/${f}`), musique: musique && musique !== '-' ? musique : '', format: valeur('fmtVideo'),
      duree_s: Number(valeur('dureeVideo')) || 15, rythme: valeur('rythmeVideo'), transition: valeur('transitionVideo'), marque: $('marqueVideo').value.trim(),
      piece: $('pieceVideo').value.trim(), prix: $('prixVideo').value.trim(), appel: $('appelVideo').value.trim(), apercu };
    if (!c || !c.photos.length) return null;
    return q;
  }
  async function lancer(apercu) {
    const q = demande(apercu);
    if (!q) { dire('Il faut au moins une photo dans la collection.'); return; }
    const b = $(apercu ? 'apercuVideo' : 'exporterVideo'); b.disabled = true;
    try {
      const o = await poster('/api/atelier/video/creer', q);
      if (apercu) { apercuAttendu = String(o.nom || '').slice(0, 15); sigApercu = '-'; $('apercuZone').hidden = false; $('apercuZone').innerHTML = '<div class="sous">L’aperçu se monte…</div>'; }
      dire(apercu ? 'L’aperçu se monte (quelques secondes).' : 'C’est parti : la vidéo se monte, en pleine qualité.');
      charger();
    } catch (e) { dire(`Pas lancée : ${e.message}`, 9000); } finally { b.disabled = false; }
  }
  $('apercuVideo').addEventListener('click', () => lancer(true));
  $('exporterVideo').addEventListener('click', () => lancer(false));

  // refaire : la recette revient dans le formulaire (collection, photos, musique, réglages, textes), à changer puis exporter
  function refaire(nom) {
    const x = (etat.videos || []).find(v => v.nom === nom);
    if (!x) return;
    const r = x.recette || {};
    const ph = (r.photos || []).filter(p => p.collection);
    if (ph.length) { collection = ph[0].collection; choisies = ph.filter(p => p.collection === collection).map(p => p.fichier); }
    musique = r.musique && r.musique.collection ? `${r.musique.collection}/${r.musique.fichier}` : '-';
    const cocher = (nom2, v) => { const i = document.querySelector(`input[name="${nom2}"][value="${CSS.escape(String(v))}"]`); if (i) i.checked = true; };
    cocher('fmtVideo', (r.formats || [])[0] || '9:16'); cocher('dureeVideo', Math.round(r.duree_s || 15)); cocher('rythmeVideo', r.rythme || 'auto');
    cocher('transitionVideo', r.transition || 'auto');
    const t = r.textes || {};
    $('marqueVideo').value = t.marque || ''; $('pieceVideo').value = t.piece || ''; $('prixVideo').value = t.prix || ''; $('appelVideo').value = t.appel || '';
    sig = ''; rendre();
    $('t-video').scrollIntoView({ behavior: 'smooth', block: 'start' });
    dire('La recette est revenue : change ce que tu veux, puis Aperçu ou Exporter.');
  }

  /* ---------- le lecteur (celui de la page) ---------- */
  let retour = null;
  async function ouvrir(chemin, titre) {
    const l = $('lecteur');
    retour = document.activeElement;
    l.innerHTML = '<div class="sous" style="color:#fff">Chargement…</div>'; l.hidden = false;
    try {
      const u = await urlDe(chemin);
      if (l.hidden) return;
      l.innerHTML = `<video controls playsinline autoplay src="${esc(u)}" aria-label="${esc(titre)}"></video><div class="gestes"><button type="button" data-fermer>✕ Fermer</button></div>`;
      const b = l.querySelector('[data-fermer]'); if (b) b.focus();
    } catch (e) { l.hidden = true; dire(e.message); }
  }
  async function telecharger(f) {
    try { const a = document.createElement('a'); a.href = await urlDe(fichierVideo(f)); a.download = f; document.body.appendChild(a); a.click(); a.remove(); } catch (e) { dire(e.message); }
  }
  let son = null;
  async function ecouter(chemin, b) {
    if (son && son.dataset.c === chemin && !son.paused) { son.pause(); b.textContent = '▶︎'; return; }
    if (son) son.pause();
    for (const x of document.querySelectorAll('[data-ecouter]')) x.textContent = '▶︎';
    try { son = new Audio(await urlDe(chemin)); son.dataset.c = chemin; son.onended = () => { b.textContent = '▶︎'; }; await son.play(); b.textContent = '❚❚'; }
    catch (e) { dire('Lecture impossible.'); }
  }

  document.addEventListener('click', async (ev) => {
    const t = ev.target.closest('button'); if (!t || !$('videoCarte').contains(t)) return;
    const d = t.dataset;
    if (d.collection) { collection = d.collection; garder('collection', collection); choisies = []; sig = ''; rendre(); }
    else if (d.photo) {
      const i = choisies.indexOf(d.photo);
      if (i >= 0) choisies.splice(i, 1); else if (choisies.length < 30) choisies.push(d.photo); else dire('30 photos au plus.');
      sig = ''; rendre();
      const nb = document.querySelector(`[data-photo="${CSS.escape(d.photo)}"]`); if (nb) nb.focus();
    } else if (d.musique) { musique = d.musique; sig = ''; rendre(); }
    else if (d.ecouter) ecouter(d.ecouter, t);
    else if (d.effacerPhoto || d.effacerMusique) {
      const f = d.effacerPhoto || d.effacerMusique, c = d.c || collection;
      if (!window.confirm(`Effacer « ${f} » de la médiathèque ?`)) return;
      try { await poster('/api/atelier/media/effacer', { collection: c, fichier: f }); choisies = choisies.filter(x => x !== f); dire('Effacé.'); charger(); } catch (e) { dire(e.message); }
    } else if (d.effacerCollection) {
      try { await poster('/api/atelier/media/effacer', { collection: d.effacerCollection, fichier: '' }); collection = ''; dire('Collection effacée.'); charger(); } catch (e) { dire(e.message); }
    } else if (d.voirVideo) ouvrir(fichierVideo(d.voirVideo), d.titre || '');
    else if (d.dl) telecharger(d.dl);
    else if (d.refaire) refaire(d.refaire);
    else if (d.effacerVideo) {
      if (!window.confirm('Effacer cette vidéo de l’atelier ? (sa copie sur ton téléphone reste)')) return;
      try { await poster('/api/atelier/video/effacer', { nom: d.effacerVideo }); dire('Effacée.'); charger(); } catch (e) { dire(e.message); }
    } else if (d.arreterVideo) {
      t.disabled = true;
      try { await poster('/api/atelier/video/arreter', { tache: d.arreterVideo }); dire('Arrêtée.'); charger(); } catch (e) { dire(e.message); t.disabled = false; }
    } else return;
    ev.stopPropagation();
  }, true);
  charger();
})();
