/* (14/11, Ahmed : « pouvoir renommer les pistes de voix et pouvoir modifier manuellement le mix […] que je puisse aussi modifier et
   enregistrer mes mix » ; « chaque nouveau mix ou master s'enregistre en version v1, v2, v3 au lieu d'écraser l'ancien » ; des profils
   « voix téléphone », « voix radio », « voix proche ») l'ÉDITION de la page Studio, à côté du multipiste (studio-pistes.js, dont elle
   reprend la machinerie : window.StudioPistes) :
   - dans le réglage d'une piste : son NOM, et son PROFIL (choisi, entendu AVANT/APRÈS sur un extrait que le Mac rend avec le même
     graphe que le mix, posé, réglé à la main, gardé sous un nom) ;
   - TES MIX : garder le mix actuel sous un nom, le rappeler, le renommer, l'effacer ; l'état du mix (à la main ? porté ? modifié ?) ;
     un mix à la main décoche le mix automatique (sinon le rendu le referait) ;
   - les VERSIONS (v1, v2… jamais écrasées) : écouter, comparer A/B (à niveau égal, on bascule sans perdre sa place), revenir au mix
     d'une version, la nommer, l'effacer du Mac.
   Tout passe par /api/studio/projet/edition (anamnese/jarvis/studio_edition.py). Tout texte venu du disque passe par esc(). */
(() => {
  const $ = (id) => document.getElementById(id);
  const P = () => window.StudioPistes;
  const A = () => window.StudioAudio;
  const H = () => ({ 'X-Jeton': window.jeton() });
  const dire = (t, ms) => (A() ? A().dire(t, ms) : null);
  const e = { profils: [], ab: null, gen: 0, mixMain: null, apercu: null, essai: '', tampons: new Map() };
  const projet = () => (P() && P()._s.projet) || null;
  const quand = (t) => new Date((t || 0) * 1000).toLocaleString('fr-FR', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
  const n1 = (v) => (v === null || v === undefined || v === '' || !Number.isFinite(Number(v)) ? '?' : String(Math.round(Number(v) * 10) / 10));
  const lin = (db) => Math.pow(10, (Number(db) || 0) / 20);
  const mmss = (t) => (P() ? P().mmss(t) : String(t));

  async function edition(quoi, corps = {}, avecRev = true) {
    const p = projet(); if (!p) throw new Error('aucun projet');
    const o = await P().poster('/api/studio/projet/edition', { quoi, id: p.id, ...(avecRev ? { rev: p.rev } : {}), ...corps });
    if (o.projet) P().remplacer(o);
    return o;
  }
  const ok = (f) => async (...a) => { try { return await f(...a); } catch (err) { if (err.message !== 'rechargé') dire(err.message); return null; } };
  async function chargerProfils() {
    try {
      const r = await fetch('/api/studio/profils', { headers: H() });
      const o = await r.json().catch(() => ({}));
      if (r.ok && o.ok) e.profils = o.profils || [];
    } catch (_) {}
  }

  /* ---------- l'état du mix et tes mix nommés ---------- */
  function etat() {
    const p = projet(); if (!p) return;
    const x = p.edition_etat || { mix_main: false, mix_courant: null, modifie: false };
    // un mix fait à la main : le rendu le garde tel quel (le mix automatique décoché) ; on ne recoche pas à la place de papa
    if (e.mixMain !== x.mix_main) { e.mixMain = x.mix_main; if ($('mpMixAuto')) $('mpMixAuto').checked = !x.mix_main; }
    const l = (p.mixes || []);
    const porte = x.mix_courant ? `Le projet porte ${/^v\d+$/.test(x.mix_courant) ? 'le mix de la version' : 'ton mix'} « ${esc(x.mix_courant)} »${x.modifie ? ' (modifié depuis)' : ''}.` : '';
    const main = x.mix_main ? ' Réglé à la main depuis le dernier mix auto : « Mixer et masteriser » le garde tel quel (le mix auto est décoché ; si tu le coches, ton mix est d’abord gardé dans tes mix).' : '';
    $('mpMixes').innerHTML = `<div class="ed-etat${x.mix_main ? ' main' : ''}">${porte}${main || (porte ? '' : 'Tes mix : garde le mix actuel sous un nom pour y revenir quand tu veux.')}</div>`
      + `<div class="rangee"><select id="edMix" aria-label="Tes mix">${l.length ? l.map(m => `<option value="${esc(m.nom)}"${m.nom === x.mix_courant ? ' selected' : ''}>${esc(m.nom)} · ${esc(quand(m.t))}${m.par === 'hakim' ? ' · Hakim' : m.par === 'auto' ? ' · gardé avant le mix auto' : ''}</option>`).join('') : '<option value="">Aucun mix gardé</option>'}</select>`
      + `<button type="button" id="edMixRappeler"${l.length ? '' : ' disabled'}>↺ Rappeler</button>`
      + `<button type="button" id="edMixGarder">💾 Garder le mix actuel…</button>`
      + `<button type="button" id="edMixRenommer"${l.length ? '' : ' disabled'} aria-label="Renommer ce mix">✎</button>`
      + `<button type="button" id="edMixSuppr"${l.length ? '' : ' disabled'} aria-label="Effacer ce mix">🗑</button></div>`;
  }
  $('mpMixes').addEventListener('click', ok(async (ev) => {
    const b = ev.target.closest('button'); if (!b) return;
    const nom = $('edMix') ? $('edMix').value : '';
    if (b.id === 'edMixGarder') {
      const p = projet(), x = p.edition_etat || {};
      const n = prompt('Le nom de ce mix (le même nom le remplace) :', x.mix_courant && !/^v\d+$/.test(x.mix_courant) ? x.mix_courant : '');
      if (!n || !n.trim()) return;
      if ((p.mixes || []).some(m => m.nom.toLowerCase() === n.trim().toLowerCase()) && !confirm(`Remplacer ton mix « ${n.trim()} » par les réglages actuels ?`)) return;
      const o = await edition('garder_mix', { nom: n.trim() }, false);
      return dire(o.remplace ? `Mix « ${o.nom} » remplacé.` : `Mix « ${o.nom} » gardé.`);
    }
    if (!nom) return;
    if (b.id === 'edMixRappeler') {
      if (!confirm(`Remettre les réglages de ton mix « ${nom} » sur les pistes ? (Garde d’abord le mix actuel si tu veux y revenir.)`)) return;
      const o = await edition('rappeler_mix', { nom });
      return dire(`Mix « ${o.nom} » rappelé : ${o.dit}.`, 8000);
    }
    if (b.id === 'edMixRenommer') {
      const n = prompt('Le nouveau nom de ce mix :', nom);
      if (!n || !n.trim() || n.trim() === nom) return;
      await edition('renommer_mix', { nom, nouveau: n.trim() }, false);
      return;
    }
    if (b.id === 'edMixSuppr') {
      if (!confirm(`Effacer ton mix « ${nom} » ? (Les versions rendues restent.)`)) return;
      await edition('supprimer_mix', { nom }, false);
    }
  }));

  /* ---------- l'écoute A/B (les versions, l'aperçu d'un profil) ---------- */
  // deux sons lus ensemble, un seul entendu : basculer garde la place (fondu de 10 ms) ; « à niveau égal » ramène le plus fort au
  // niveau du plus doux (LUFS mesurés sur le Mac), pour juger le mix et pas le volume
  async function tampon(c, f) {
    if (e.tampons.has(f)) return e.tampons.get(f);
    const r = await fetch(`/api/studio/son?f=${encodeURIComponent(f)}`, { headers: H() });
    if (!r.ok) throw new Error('son introuvable (effacé ?)');
    const b = await c.decodeAudioData(await r.arrayBuffer());
    if (e.tampons.size >= 4) e.tampons.delete(e.tampons.keys().next().value);       // deux paires au plus en mémoire
    e.tampons.set(f, b);
    return b;
  }
  function arreterAB() {
    e.gen += 1;
    const x = e.ab; if (!x) return;
    e.ab = null;
    cancelAnimationFrame(x.raf);
    for (const src of [x.sa, x.sb]) try { src.stop(); } catch (_) {}
    try { x.ga.disconnect(); x.gb.disconnect(); } catch (_) {}
    afficherAB();
  }
  async function ecouterAB(fa, fb, opts) {
    if (P() && P()._s.lecture && window.StudioPistes) try { document.getElementById('mpLire').click(); } catch (_) {}   // le multipiste se tait
    arreterAB();
    const gen = e.gen;
    const c = await A().contexte();
    opts.lieu.textContent = 'Chargement…';
    const [ta, tb] = await Promise.all([tampon(c, fa), tampon(c, fb)]);
    if (gen !== e.gen) return;
    const ga = c.createGain(), gb = c.createGain(), sa = c.createBufferSource(), sb = c.createBufferSource();
    sa.buffer = ta; sb.buffer = tb; sa.connect(ga); sb.connect(gb); ga.connect(c.destination); gb.connect(c.destination);
    const t0 = c.currentTime + 0.08, depuis = Math.max(0, Number(opts.depuis) || 0);
    const x = { c, sa, sb, ga, gb, cote: opts.cote || 'A', dA: opts.gA || 0, dB: opts.gB || 0, t0, depuis, duree: Math.max(ta.duration, tb.duration),
      lieu: opts.lieu, noms: opts.noms || ['A', 'B'], bouton: opts.bouton, zone: opts.zone || 'versions' };
    ga.gain.value = x.cote === 'A' ? lin(x.dA) : 0; gb.gain.value = x.cote === 'B' ? lin(x.dB) : 0;
    sa.start(t0, Math.min(depuis, Math.max(0, ta.duration - 0.05))); sb.start(t0, Math.min(depuis, Math.max(0, tb.duration - 0.05)));
    e.ab = x;
    const tic = () => {
      if (e.ab !== x) return;
      const pos = depuis + Math.max(0, c.currentTime - t0);
      if (pos >= x.duree) return arreterAB();
      afficherAB(pos);
      x.raf = requestAnimationFrame(tic);
    };
    x.raf = requestAnimationFrame(tic);
    sa.onended = () => { if (e.ab === x && c.currentTime - t0 + depuis >= x.duree - 0.1) arreterAB(); };
  }
  function basculerAB() {
    const x = e.ab; if (!x) return false;
    x.cote = x.cote === 'A' ? 'B' : 'A';
    const now = x.c.currentTime;
    x.ga.gain.setTargetAtTime(x.cote === 'A' ? lin(x.dA) : 0, now, 0.005);
    x.gb.gain.setTargetAtTime(x.cote === 'B' ? lin(x.dB) : 0, now, 0.005);
    afficherAB();
    return true;
  }
  function afficherAB(pos) {
    const x = e.ab;
    for (const b of document.querySelectorAll('[data-ab-bascule]')) b.classList.toggle('ed-ab-on', !!x && b === x.bouton);
    if (!x) { for (const l of document.querySelectorAll('.ed-ab-lieu')) l.textContent = ''; return; }
    const p = pos === undefined ? x.depuis + Math.max(0, x.c.currentTime - x.t0) : pos;
    x.lieu.innerHTML = `<span class="ed-cote${x.cote === 'B' ? ' b' : ''}">${esc(x.cote === 'A' ? x.noms[0] : x.noms[1])}</span> ${esc(mmss(p))} / ${esc(mmss(x.duree))}`;
  }
  // la page se redessine (un réglage, Hakim qui change le projet) : l'écoute continue, son affichage suit les nouveaux éléments
  function rebrancher() {
    const x = e.ab; if (!x) return;
    const [l, b] = x.zone === 'apercu' ? ['edApLieu', 'edApBascule'] : ['edAbLieu', 'edAbBascule'];
    if (!$(l) || !document.body.contains($(l))) return arreterAB();
    x.lieu = $(l); x.bouton = $(b);
    afficherAB();
  }
  // les gains « à niveau égal » : le plus fort ramené au plus doux (jamais monté : pas de crête au-dessus du master)
  function gains(la, lb, egal) {
    if (!egal || !Number.isFinite(Number(la)) || !Number.isFinite(Number(lb))) return [0, 0];
    const m = Math.min(Number(la), Number(lb));
    return [m - Number(la), m - Number(lb)];
  }

  /* ---------- les versions ---------- */
  const FICHIERS = [['complet', 'le son entier'], ['zones_papa', 'ta version (tes zones en instru)'], ['instru', 'l’instru seule']];
  // « ce qui change » d'une version à l'autre (studio_edition.differences) : les clés des réglages dites avec les mots de la page
  const LIBELLES = { volume_db: 'volume (dB)', pan: 'panoramique', 'eq.coupe_bas_hz': 'coupe-bas (Hz)', 'eq.coupe_haut_hz': 'coupe-haut (Hz)',
    'eq.grave_db': 'graves (dB)', 'eq.grave_hz': 'graves à (Hz)', 'eq.medium_db': 'médiums (dB)', 'eq.medium_hz': 'médiums à (Hz)',
    'eq.medium_q': 'largeur des médiums', 'eq.aigu_db': 'aigus (dB)', 'eq.aigu_hz': 'aigus à (Hz)', 'comp.actif': 'compression',
    'comp.seuil_db': 'compression : seuil (dB)', 'comp.ratio': 'compression : ratio', 'comp.attaque_ms': 'compression : attaque (ms)',
    'comp.relache_ms': 'compression : relâche (ms)', 'comp.gain_db': 'compression : gain (dB)', 'comp_rapide.actif': 'crêtes',
    'comp_rapide.seuil_db': 'crêtes : seuil (dB)', 'comp_rapide.ratio': 'crêtes : ratio', deesser: 'dé-esseur', reverb: 'réverb',
    delai: 'écho', delai_note: 'écho : note', 'sidechain.cle': 'creusée sous', 'sidechain.db': 'creusée de (dB)', 'master.cible': 'cible du master',
    'master.lufs': 'LUFS du master', 'profil.nom': 'profil', 'profil.actif': 'profil actif' };
  const enMots = (l) => String(l).replace(/(^|: |, )([a-z_]+(?:\.[a-z_]+)?)(?= )/g, (m, a, k) => a + (LIBELLES[k] || k));
  function diffHtml() {
    const d = e.diff; if (!d) return '';
    const t = `De v${esc(d.a)} à v${esc(d.b)} :`;
    if (!Array.isArray(d.l)) return `<div class="sous">${t} inconnu (une des deux vient d’avant les versions : ses réglages n’ont pas été gardés).</div>`;
    return d.l.length ? `<div class="sous">${t}</div><ul class="conseils">${d.l.map(x => `<li>${esc(enMots(x))}</li>`).join('')}</ul>`
      : `<div class="sous">${t} rien dans les réglages (le même mix).</div>`;
  }
  function rendus() {
    const p = projet(); if (!p) return;
    etat();
    const vs = (p.versions || []).slice().reverse();
    const det = new Map((p.rendus || []).map(r => [r.nom, r]));
    const opt = (sel) => vs.map(v => `<option value="${esc(v.v)}"${String(v.v) === String(sel) ? ' selected' : ''}>v${esc(v.v)}${v.nom ? ' · ' + esc(v.nom) : ''}</option>`).join('');
    const a0 = e.choixA || (vs[1] && vs[1].v), b0 = e.choixB || (vs[0] && vs[0].v);
    const ab = vs.length >= 2 ? `<div class="ed-ab"><div class="sous">Comparer deux versions : elles jouent ensemble, tu n’en entends qu’une, « A ⇄ B » bascule sans perdre ta place.</div>`
      + `<div class="rangee"><label class="ligne">A<select id="edA" aria-label="Version A">${opt(a0)}</select></label><label class="ligne">B<select id="edB" aria-label="Version B">${opt(b0)}</select></label>`
      + `<select id="edQuoi" aria-label="Quel fichier">${FICHIERS.map(([k, l]) => `<option value="${k}"${(e.quoi || 'complet') === k ? ' selected' : ''}>${l}</option>`).join('')}</select></div>`
      + `<div class="rangee"><button type="button" id="edAbLire">▶︎ Écouter A/B</button><button type="button" id="edAbBascule" data-ab-bascule="1">A ⇄ B</button><button type="button" id="edAbStop" aria-label="Arrêter">■</button>`
      + `<label class="ligne"><input type="checkbox" id="edEgal"${e.egal === false ? '' : ' checked'}><span>à niveau égal</span></label><span class="ed-ab-lieu" id="edAbLieu"></span></div>`
      + `<div class="rangee"><button type="button" id="edAbDiff">≠ Ce qui change</button></div><div id="edAbDiffZone">${diffHtml()}</div></div>` : '';
    $('mpRendus').innerHTML = !vs.length ? '<div class="vide">Pas encore de version : « Mixer et masteriser » fait la v1 (puis v2, v3… sans jamais écraser).</div>'
      : ab + vs.map(v => {
        const m = v.master || {}, f = v.fichiers || {}, r = det.get(v.rendu);
        const son = (k, nom) => (f[k] && f[k].mp3 ? `<div class="son"><div class="tete">${nom}</div><div class="gestes"><button type="button" data-lire="${esc(f[k].mp3)}">▶︎ Écouter</button><button type="button" data-dl="${esc(f[k].mp3)}" aria-label="Télécharger">⬇︎</button></div></div>` : '');
        const ecoute = f.complet && f.complet.mp3 ? f.complet.mp3 : '';
        return `<div class="son ed-v" data-v="${esc(v.v)}"><div class="tete"><b>v${esc(v.v)}</b>${v.nom ? ` « ${esc(v.nom)} »` : ''}`
          + `<span class="meta">${esc(quand(v.t))}${v.mix_auto === true ? ' · mix auto' : v.mix_auto === false ? ' · mix à la main' : ''}${v.par === 'hakim' ? ' · par Hakim' : ''}${v.cible === 'club' ? ' · club' : ''}</span></div>`
          + `<div class="mesures">${esc(n1(m.lufs))} LUFS · crête vraie ${esc(n1(m.crete_dbtp))} dBTP (MP3 ${esc(n1(v.mp3_crete_dbtp))}) · PLR ${esc(n1(m.plr_db))} dB · LRA ${esc(n1(m.lra))} LU</div>`
          + `<div class="gestes">${ecoute ? `<button type="button" data-lire="${esc(ecoute)}">▶︎ Écouter</button><button type="button" data-dl="${esc(ecoute)}" aria-label="Télécharger">⬇︎</button>` : '<span class="sous">fichiers effacés</span>'}`
          + `<button type="button" data-ed-nommer="${esc(v.v)}">✎ Nommer</button>`
          + (v.photo ? `<button type="button" data-ed-revenir="${esc(v.v)}">↺ Revenir à ce mix</button>` : '<span class="sous">réglages d’avant les versions</span>')
          + `<button type="button" data-ed-suppr="${esc(v.v)}" aria-label="Effacer cette version du Mac">🗑</button></div>`
          + `<details><summary>Détails</summary>${r ? `<ul class="conseils">${(r.avis || []).map(x => `<li>${esc(x)}</li>`).join('')}</ul>` : ''}`
          + son('zones_papa', 'Ta version (tes zones en instru)') + son('instru', 'L’instru seule')
          + (f.complet && f.complet.wav16 ? `<div class="son"><div class="tete">WAV 16 bits (avec dither)</div><div class="gestes"><button type="button" data-dl="${esc(f.complet.wav16)}" aria-label="Télécharger le WAV 16 bits">⬇︎</button></div></div>` : '')
          + (v.pistes && v.pistes.length ? `<div class="sous">Pistes séparées : ${v.pistes.map(x => `<button type="button" data-dl="${esc(x)}">${esc(x.split('/').pop())}</button>`).join(' ')}</div>` : '')
          + '</details></div>';
      }).join('');
    rebrancher();
  }
  function versionDe(v) { const p = projet(); return p && (p.versions || []).find(x => String(x.v) === String(v)); }
  $('mpRendus').addEventListener('change', (ev) => {
    if (ev.target.id === 'edA') e.choixA = ev.target.value;
    if (ev.target.id === 'edB') e.choixB = ev.target.value;
    if (ev.target.id === 'edQuoi') e.quoi = ev.target.value;
    if (ev.target.id === 'edEgal') e.egal = ev.target.checked;
    if ((ev.target.id === 'edA' || ev.target.id === 'edB') && e.diff) { e.diff = null; if ($('edAbDiffZone')) $('edAbDiffZone').innerHTML = ''; }
    if (e.ab && ev.target.id !== 'edEgal' && ev.target.closest('.ed-ab')) arreterAB();
  });
  $('mpRendus').addEventListener('click', ok(async (ev) => {
    const b = ev.target.closest('button'); if (!b) return;
    const d = b.dataset;
    if (b.id === 'edAbLire') {
      const va = versionDe($('edA').value), vb = versionDe($('edB').value), k = $('edQuoi').value;
      const fa = va && va.fichiers[k] && va.fichiers[k].mp3, fb = vb && vb.fichiers[k] && vb.fichiers[k].mp3;
      if (!fa || !fb) return dire('Ce fichier manque dans une des deux versions.');
      const [gA, gB] = gains(va.master.lufs, vb.master.lufs, $('edEgal').checked && k === 'complet');
      return ecouterAB(fa, fb, { gA, gB, lieu: $('edAbLieu'), noms: [`A v${va.v}`, `B v${vb.v}`], bouton: $('edAbBascule'), zone: 'versions' });
    }
    if (b.id === 'edAbDiff') {
      const a = $('edA').value, vb = $('edB').value;
      const o = await edition('comparer', { a: 'v' + a, b: 'v' + vb }, false);
      e.diff = { a, b: vb, l: o.differences };
      if ($('edAbDiffZone')) $('edAbDiffZone').innerHTML = diffHtml();
      return;
    }
    if (b.id === 'edAbBascule') return basculerAB() || dire('Lance d’abord « Écouter A/B ».');
    if (b.id === 'edAbStop') return arreterAB();
    if (d.edNommer) {
      const v = versionDe(d.edNommer);
      const n = prompt(`Le nom de la v${d.edNommer} (vide : sans nom) :`, (v && v.nom) || '');
      if (n === null) return;
      return edition('nommer_version', { v: 'v' + d.edNommer, nom: n.trim() }, false);
    }
    if (d.edRevenir) {
      if (!confirm(`Remettre les réglages de la v${d.edRevenir} sur les pistes ? Le prochain rendu les gardera tels quels (une nouvelle version). Garde d’abord le mix actuel dans « Tes mix » si tu veux y revenir.`)) return;
      const o = await edition('revenir', { v: 'v' + d.edRevenir });
      return dire(`Le mix de la v${o.v} est revenu : ${o.dit}.`, 8000);
    }
    if (d.edSuppr) {
      if (!confirm(`Effacer la v${d.edSuppr} du Mac (ses fichiers) ? La copie sur ton téléphone reste. Son numéro ne sera pas repris.`)) return;
      arreterAB();
      const o = await edition('supprimer_version', { v: 'v' + d.edSuppr }, false);
      return dire(`v${o.v} effacée du Mac (${o.effaces} fichiers).`);
    }
  }));

  /* ---------- une piste : son nom, son profil ---------- */
  const CHAMPS_PROFIL = [['coupe_bas_hz', 'Coupe-bas (Hz, 0 = sans)', 0, 1000, 10], ['coupe_haut_hz', 'Coupe-haut (Hz, 0 = sans)', 0, 20000, 100],
    ['grave_db', 'Graves (dB)', -12, 12, 0.5], ['grave_hz', 'Graves à (Hz)', 40, 400, 5], ['medium_db', 'Médiums (dB)', -12, 12, 0.5],
    ['medium_hz', 'Médiums à (Hz)', 150, 8000, 10], ['medium_q', 'Largeur (Q)', 0.3, 6, 0.1], ['aigu_db', 'Aigus (dB)', -12, 12, 0.5],
    ['aigu_hz', 'Aigus à (Hz)', 2000, 16000, 100], ['seuil_db', 'Compression : seuil (dB)', -50, 0, 1], ['ratio', 'Ratio (1 = sans)', 1, 20, 0.5],
    ['attaque_ms', 'Attaque (ms)', 0.1, 200, 0.5], ['relache_ms', 'Relâche (ms)', 5, 2000, 5], ['saturation', 'Saturation (0 à 1)', 0, 1, 0.05],
    ['sortie_db', 'Sortie (dB)', -24, 12, 0.5]];
  function detail(t) {
    const el = $('mpEdPiste'); if (!el || !t) return;
    const pr = t.profil && typeof t.profil === 'object' ? t.profil : null;
    if (e.pour !== t.id) { e.pour = t.id; e.essai = pr ? pr.nom : ''; e.apercu = null; }
    const connus = e.profils.map(x => x.nom);
    const choix = e.essai;
    const opts = [['', pr ? 'aucun (retirer le sien)' : 'aucun'], ...e.profils.map(x => [x.nom, x.nom + (x.depart ? (x.modifie ? ' (de départ, réglé)' : '') : ' (le tien)')]),
      ...(pr && !connus.includes(pr.nom) ? [[pr.nom, pr.nom + ' (de cette piste)']] : [])];
    const x = e.profils.find(y => y.nom === choix);
    const pose = pr && choix === pr.nom;
    el.innerHTML = `<h4 style="margin:10px 0 4px">✏️ Nom et profil de voix</h4><div class="mp-grille2">`
      + `<label>Nom de la piste<input type="text" id="edNom" value="${esc(t.nom)}" maxlength="60"></label>`
      + `<label>Profil (voix téléphone, radio, proche…)<select id="edProfil">${opts.map(([v, l]) => `<option value="${esc(v)}"${v === choix ? ' selected' : ''}>${esc(l)}</option>`).join('')}</select></label></div>`
      + (pr && pose ? `<div class="mp-grille2" style="margin-top:6px">`
        + `<label>Profil actif<select data-pf="actif"><option value="1"${pr.actif !== false ? ' selected' : ''}>oui</option><option value="0"${pr.actif === false ? ' selected' : ''}>non (coupé)</option></select></label>`
        + `<label>Pente des coupures<select data-pf="pente"><option value="12"${Number(pr.pente) !== 24 ? ' selected' : ''}>12 dB/oct (douce)</option><option value="24"${Number(pr.pente) === 24 ? ' selected' : ''}>24 dB/oct (raide)</option></select></label>`
        + CHAMPS_PROFIL.map(([k, l, a, b, s]) => `<label>${l}<input type="number" data-pf="${k}" value="${Number.isFinite(Number(pr[k])) ? Number(pr[k]) : 0}" min="${a}" max="${b}" step="${s}"></label>`).join('')
        + `</div>` : '')
      + `<div class="gestes">${choix ? `<button type="button" id="edApercu">👂 Avant / après</button>` : ''}`
      + (choix && !pose ? `<button type="button" class="principal" id="edPoser">✓ Poser « ${esc(choix)} » sur la piste</button>` : '')
      + (pr && pose ? `<button type="button" id="edGarderProfil">💾 Garder ce profil…</button>` : '')
      + (x && (!x.depart || x.modifie) ? `<button type="button" id="edSupprProfil">${x.depart ? '↺ Remettre « ' + esc(x.nom) + ' » d’origine' : '🗑 Effacer le profil « ' + esc(x.nom) + ' »'}</button>` : '')
      + `</div><div id="edApercuZone">${apercuHtml()}</div>`;
    rebrancher();
  }
  function apercuHtml() {
    const a = e.apercu; if (!a) return '';
    return `<div class="ed-ab"><div class="sous">Extrait de ${esc(n1(a.duree_s))} s à ${esc(mmss(a.debut_s))}, voix ${esc(a.voix)} : avant ${esc(n1(a.lufs_avant))} LUFS, après « ${esc(a.profil)} » ${esc(n1(a.lufs_apres))} LUFS.</div>`
      + `<div class="rangee"><button type="button" id="edApLire">▶︎ Écouter</button><button type="button" id="edApBascule" data-ab-bascule="1">Avant ⇄ Après</button><button type="button" id="edApStop" aria-label="Arrêter">■</button>`
      + `<label class="ligne"><input type="checkbox" id="edApEgal"${e.apEgal === false ? '' : ' checked'}><span>à niveau égal</span></label><span class="ed-ab-lieu" id="edApLieu"></span></div></div>`;
  }
  // le nom et le choix du profil (le reste du réglage passe par studio-pistes.js)
  $('mpDetail').addEventListener('change', ok(async (ev) => {
    const t = ev.target, p = projet(), piste = P() && P()._s.detail;
    if (!p || !piste) return;
    if (t.id === 'edNom') {
      const n = t.value.trim(); if (!n) return;
      try { await edition('renommer', { piste, nom: n }); } catch (err) { const x = p.pistes.find(y => y.id === piste); t.value = x ? x.nom : ''; throw err; }
      P().rendreGrille();
      return dire(`Piste renommée « ${n} ».`);
    }
    if (t.id === 'edProfil') {
      e.essai = t.value; e.apercu = null; arreterAB();
      const x = p.pistes.find(y => y.id === piste);
      if (!t.value && x && x.profil) {
        if (!confirm('Retirer le profil de cette piste ?')) { e.essai = x.profil.nom; return detail(x); }
        await edition('retirer_profil', { piste });
        return;
      }
      return detail(x);
    }
    if (t.id === 'edApEgal') { e.apEgal = t.checked; return; }
    const k = t.dataset && t.dataset.pf;
    if (k) {
      const v = k === 'actif' ? t.value === '1' : Number(t.value);
      await edition('regler_profil', { piste, reglages: { [k]: v } });
    }
  }));
  $('mpDetail').addEventListener('click', ok(async (ev) => {
    const b = ev.target.closest('button'); if (!b || !b.id.startsWith('ed')) return;
    const p = projet(), piste = P() && P()._s.detail, t = p && p.pistes.find(y => y.id === piste);
    if (!t) return;
    if (b.id === 'edApercu') {
      b.disabled = true; arreterAB();
      dire('Le Mac rend l’extrait avant et après…', 0);
      try {
        const pose = t.profil && e.essai === t.profil.nom;
        const o = await edition('apercu', { piste, ...(pose ? {} : { nom: e.essai }), debut_s: P()._s.pos }, false);
        e.apercu = o.apercu; dire('', 1);
        $('edApercuZone').innerHTML = apercuHtml();
      } finally { b.disabled = false; }
      return;
    }
    if (b.id === 'edApLire') {
      const a = e.apercu; if (!a) return;
      const [gA, gB] = gains(a.lufs_avant, a.lufs_apres, $('edApEgal').checked);
      return ecouterAB(a.avant, a.apres, { gA, gB, lieu: $('edApLieu'), noms: ['Avant', 'Après'], bouton: $('edApBascule'), zone: 'apercu' });
    }
    if (b.id === 'edApBascule') return basculerAB() || dire('Lance d’abord « Écouter ».');
    if (b.id === 'edApStop') return arreterAB();
    if (b.id === 'edPoser') {
      await edition('appliquer_profil', { piste, nom: e.essai });
      return dire(`Profil « ${e.essai} » posé : il s’entend au rendu (et dans « Avant / après »).`);
    }
    if (b.id === 'edGarderProfil') {
      const n = prompt('Garder le profil de cette piste sous le nom (pour tous tes projets) :', t.profil.nom || '');
      if (!n || !n.trim()) return;
      if (e.profils.some(x => x.nom.toLowerCase() === n.trim().toLowerCase()) && !confirm(`Remplacer le profil « ${n.trim()} » ?`)) return;
      const o = await edition('garder_profil', { piste, nom: n.trim() }, false);
      e.profils = o.profils || e.profils; e.essai = o.profil.nom;
      detail(projet().pistes.find(y => y.id === piste));
      return dire(`Profil « ${o.profil.nom} » gardé.`);
    }
    if (b.id === 'edSupprProfil') {
      const x = e.profils.find(y => y.nom === e.essai); if (!x) return;
      if (!confirm(x.depart ? `Remettre « ${x.nom} » à ses réglages de départ ?` : `Effacer le profil « ${x.nom} » ? (Les pistes qui l’ont gardent leurs réglages.)`)) return;
      const o = await edition('supprimer_profil', { nom: x.nom }, false);
      e.profils = o.profils || e.profils;
      if (!x.depart) e.essai = t.profil ? t.profil.nom : '';
      return detail(t);
    }
  }));

  window.addEventListener('pagehide', arreterAB);
  chargerProfils().then(() => { const p = projet(); if (p && P()._s.detail) { const t = p.pistes.find(y => y.id === P()._s.detail); if (t) detail(t); } });
  window.StudioEdition = { detail, rendus, etat, _e: e, gains, arreterAB, basculerAB };
  if (projet()) rendus();
})();
