/* (06/11) la page Atelier : la galerie (images, clips), créer une image, créer un clip, les créations en cours avec leur jauge.
   Les fichiers passent derrière le jeton : chargés en blob (les vignettes d'abord ; un clip seulement quand on l'ouvre). */
(() => {
  const $ = (id) => document.getElementById(id);
  const H = () => ({ 'X-Jeton': window.jeton() });
  let etat = null, choisies = [], minuteur = 0, bulleMin = 0;
  const dire = (t, ms = 6000) => { $('bulle').textContent = t; clearTimeout(bulleMin); if (ms) bulleMin = setTimeout(() => { $('bulle').textContent = ''; }, ms); };
  const duree = (s) => { s = Math.round(Number(s) || 0); return s ? `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}` : '—'; };
  const date = (t) => t ? new Date(t * 1000).toLocaleString('fr-FR', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '';
  const FORMATS = { carre: 'carré', '9:16': '9:16', '16:9': '16:9' };

  async function poster(chemin, corps) {
    const r = await fetch(chemin, { method: 'POST', headers: { ...H(), 'Content-Type': 'application/json' }, body: JSON.stringify(corps || {}) });
    const o = await r.json().catch(() => ({}));
    if (!r.ok || o.ok === false) throw new Error(o.erreur || `erreur ${r.status}`);
    return o;
  }
  const blobs = new Map();
  async function urlDe(f) {
    if (blobs.has(f)) return blobs.get(f);
    const p = fetch(`/api/atelier/fichier?f=${encodeURIComponent(f)}`, { headers: H() })
      .then((r) => { if (!r.ok) throw new Error('fichier introuvable'); return r.blob(); })
      .then((b) => URL.createObjectURL(b));
    blobs.set(f, p);
    p.catch(() => blobs.delete(f));
    return p;
  }
  // les vignettes : chargées quand elles approchent de l'écran
  const vue = 'IntersectionObserver' in window ? new IntersectionObserver((l) => {
    for (const e of l) if (e.isIntersecting) { vue.unobserve(e.target); remplir(e.target); }
  }, { rootMargin: '200px' }) : null;
  function remplir(img) { urlDe(img.dataset.f).then((u) => { img.src = u; }).catch(() => { img.alt = 'introuvable'; }); }
  function observer(racine) { for (const img of racine.querySelectorAll('img[data-f]')) { if (vue) vue.observe(img); else remplir(img); } }

  async function telecharger(f) {
    try { const a = document.createElement('a'); a.href = await urlDe(f); a.download = f; document.body.appendChild(a); a.click(); a.remove(); }
    catch (e) { dire(e.message); }
  }
  let retour = null;
  async function ouvrir(f, video, titre) {
    const l = $('lecteur');
    retour = document.activeElement;
    l.innerHTML = '<div class="sous" style="color:#fff">Chargement…</div>';
    l.hidden = false;
    try {
      const u = await urlDe(f);
      if (l.hidden) return;
      l.innerHTML = (video ? `<video controls playsinline autoplay src="${u}" aria-label="${esc(titre)}"></video>` : `<img src="${u}" alt="${esc(titre)}">`)
        + `<div class="gestes"><button type="button" data-dl="${esc(f)}">⬇︎ Télécharger</button><button type="button" data-fermer>✕ Fermer</button></div>`;
      const b = l.querySelector('[data-fermer]'); if (b) b.focus();
    } catch (e) { l.hidden = true; dire(e.message); }
  }
  function fermer() {
    const l = $('lecteur'), v = l.querySelector('video');
    if (v) v.pause();
    l.hidden = true; l.innerHTML = '';
    if (retour && retour.focus) retour.focus();
  }

  /* ---------- l'affichage ---------- */
  function rendreCalculs() {
    const c = etat.enCours || [];
    $('calculsCarte').hidden = !c.length;
    $('calculs').innerHTML = c.map((x) => {
      const p = x.progres ? x.progres.f : 0;
      const quoi = `${x.type === 'image' ? '🖼️ Image' : '🎬 Clip'} « ${esc(x.titre)} »`;
      if (x.etat === 'ratée') return `<div class="calcul rate">${quoi} : ratée${x.erreur ? ` (${esc(x.erreur)})` : ''}</div>`;
      return `<div class="calcul"><div class="tete"><span>${quoi} — ${Math.round(p * 100)} %${x.progres && x.progres.texte ? ` · ${esc(x.progres.texte)}` : ''}</span>`
        + `<button type="button" data-arreter="${esc(x.tache)}" aria-label="Arrêter « ${esc(x.titre)} »">Arrêter</button></div>`
        + `<div class="jauge" role="progressbar" aria-label="${esc(x.titre)}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${Math.round(p * 100)}"><i style="width:${Math.round(p * 100)}%"></i></div></div>`;
    }).join('');
  }
  function rendreGalerie() {
    const im = etat.images || [];
    $('images').innerHTML = im.length ? im.map((x) => `<figure class="tuile"><div class="cadre"><img data-f="${esc(x.f)}" alt="${esc(x.titre)}"></div>`
      + `<figcaption>${esc(x.titre)}<div class="meta">${esc(FORMATS[x.format] || x.format || '')} · ${esc(date(x.date))}${x.par === 'papa' ? ' · pour papa' : ''}</div>`
      + `<div class="gestes"><button type="button" data-voir="${esc(x.f)}" data-titre="${esc(x.titre)}">Voir</button>`
      + `<button type="button" data-dl="${esc(x.f)}" aria-label="Télécharger « ${esc(x.titre)} »">⬇︎</button></div></figcaption></figure>`).join('')
      : '<div class="vide">Aucune image pour l’instant.</div>';
    const cl = etat.clips || [];
    $('clips').innerHTML = cl.length ? cl.map((x) => {
      const v0 = x.videos[0] || {};
      return `<figure class="tuile"><div class="cadre">${v0.vignette ? `<img data-f="${esc(v0.vignette)}" alt="${esc(x.titre)}">` : ''}</div>`
        + `<figcaption>${esc(x.titre)}<div class="meta">« ${esc(x.chanson)} » · ${esc(duree(x.duree_s))} · ${esc(x.style || '')}</div>`
        + `<div class="gestes">${x.videos.map(v => `<button type="button" data-video="${esc(v.f)}" data-titre="${esc(x.titre)}">▶︎ ${esc(v.format)}</button>`
          + `<button type="button" data-dl="${esc(v.f)}" aria-label="Télécharger le ${esc(v.format)}">⬇︎</button>`).join('')}</div></figcaption></figure>`;
    }).join('') : '<div class="vide">Aucun clip pour l’instant.</div>';
    observer($('images')); observer($('clips'));
  }
  function rendreChoix() {
    const s = $('chanson'), garde = s.value;
    const ch = etat.chansons || [];
    s.innerHTML = ch.length ? ch.map(c => `<option value="${esc(c.nom)}">${esc(c.titre)} (${esc(duree(c.duree_s))})</option>`).join('') : '<option value="">Aucune chanson prête</option>';
    if (garde && ch.some(c => c.nom === garde)) s.value = garde;
    const im = etat.images || [];
    choisies = choisies.filter(n => im.some(x => x.nom === n));
    $('selection').innerHTML = im.map(x => {
      const i = choisies.indexOf(x.nom);
      return `<button type="button" data-choisir="${esc(x.nom)}" aria-pressed="${i >= 0}" aria-label="${esc(x.titre)}${i >= 0 ? `, image ${i + 1}` : ''}">`
        + `<img data-f="${esc(x.f)}" alt="">${i >= 0 ? `<span class="rang">${i + 1}</span>` : ''}</button>`;
    }).join('');
    $('aideSelection').textContent = im.length ? 'Touche les images à montrer, dans l’ordre voulu.' : 'Crée d’abord une image ci-dessus.';
    observer($('selection'));
    $('creerClip').disabled = !(ch.length && choisies.length);
  }
  function rendre() { if (!etat) return; rendreCalculs(); rendreGalerie(); rendreChoix(); }

  let sigGalerie = '';
  async function charger() {
    clearTimeout(minuteur);
    try {
      const r = await fetch('/api/atelier/etat', { headers: H(), cache: 'no-store' });
      if (r.ok) {
        const e = await r.json();
        const avant = etat ? etat.enCours.filter(x => x.etat === 'en cours').length : 0;
        const s = JSON.stringify([e.images, e.clips, e.chansons]);
        etat = e;
        if (s !== sigGalerie) { sigGalerie = s; rendre(); } else rendreCalculs();   // la galerie ne clignote pas à chaque jauge
        if (avant > e.enCours.filter(x => x.etat === 'en cours').length) dire('Une création est prête ✨');
      }
    } catch (_) {}
    const actif = etat && etat.enCours && etat.enCours.some(x => x.etat === 'en cours');
    minuteur = setTimeout(charger, document.hidden ? 30000 : actif ? 3000 : 15000);
  }
  document.addEventListener('visibilitychange', () => { if (!document.hidden) charger(); });

  /* ---------- les gestes ---------- */
  const valeur = (nom) => (document.querySelector(`input[name="${nom}"]:checked`) || {}).value || '';
  $('creerImage').addEventListener('click', async () => {
    const d = $('description').value.trim();
    if (d.length < 3) { dire('Décris l’image : ce qu’on y voit, le style, la lumière.'); $('description').focus(); return; }
    const b = $('creerImage'); b.disabled = true;
    try { await poster('/api/atelier/image', { description: d, format: valeur('fmtImage'), titre: $('titreImage').value.trim() }); dire('C’est parti : l’image se calcule sur le Mac.'); $('titreImage').value = ''; charger(); }
    catch (e) { dire(`Pas lancée : ${e.message}`, 9000); } finally { b.disabled = false; }
  });
  $('creerClip').addEventListener('click', async () => {
    const b = $('creerClip'); b.disabled = true;
    try {
      await poster('/api/atelier/clip', { chanson: $('chanson').value, images: choisies, style: valeur('style'), format: valeur('fmtClip'),
        duree_s: Number($('dureeClip').value) || 0, debut_s: Number($('debutClip').value) || 0, titre: $('titreClip').value.trim() });
      dire('C’est parti : le clip se monte sur le Mac.'); charger();
    } catch (e) { dire(`Pas lancé : ${e.message}`, 9000); } finally { b.disabled = !(choisies.length && etat && etat.chansons.length); }
  });
  document.addEventListener('click', async (ev) => {
    const t = ev.target.closest('button'); if (!t) return;
    if (t.dataset.choisir) {
      const n = t.dataset.choisir, i = choisies.indexOf(n);
      if (i >= 0) choisies.splice(i, 1); else if (choisies.length < 12) choisies.push(n); else dire('12 images au plus.');
      rendreChoix();
      const nb = document.querySelector(`[data-choisir="${CSS.escape(n)}"]`); if (nb) nb.focus();
    } else if (t.dataset.voir) ouvrir(t.dataset.voir, false, t.dataset.titre);
    else if (t.dataset.video) ouvrir(t.dataset.video, true, t.dataset.titre);
    else if (t.dataset.dl) telecharger(t.dataset.dl);
    else if (t.hasAttribute('data-fermer')) fermer();
    else if (t.dataset.arreter) {
      t.disabled = true;
      try { await poster('/api/atelier/arreter', { tache: t.dataset.arreter }); dire('Arrêtée.'); charger(); } catch (e) { dire(e.message); t.disabled = false; }
    }
  });
  $('lecteur').addEventListener('click', (e) => { if (e.target === $('lecteur')) fermer(); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !$('lecteur').hidden) fermer(); });
  charger();
})();
