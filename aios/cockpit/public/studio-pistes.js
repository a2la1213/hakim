/* (13/11, Ahmed : « un vrai studio complet avec différentes pistes et différents réglages, un peu comme Logic Pro simplifié ») la vue
   multipiste de la page Studio : les pistes d'un projet (anamnese/jarvis/studio_projet.py) et leurs formes d'onde sur une ligne du temps,
   leurs curseurs (volume, panoramique, muet, solo, égaliseur, compression, envois, autotune), les zones, la lecture, l'enregistrement de
   papa posé à l'instant de la lecture (le micro et le calage de studio-page.js : window.StudioAudio), le mix et le master par Hakim.
   L'écoute se mixe en direct dans le navigateur (WebAudio : gains, panoramiques, filtres, compresseur, réverb et délai approchés) ; le
   rendu final reste celui du Mac (ffmpeg), mesuré. Chaque réglage part avec la version vue (rev) : si Hakim a changé le projet entre-
   temps, la page recharge. Tout texte venu du disque passe par esc(). */
(() => {
  const $ = (id) => document.getElementById(id);
  const A = () => window.StudioAudio;
  const H = () => ({ 'X-Jeton': window.jeton() });
  const lsLire = (k, d) => { try { const v = localStorage.getItem(k); return v === null ? d : v; } catch (_) { return d; } };
  const lsEcrire = (k, v) => { try { localStorage.setItem(k, v); } catch (_) {} };
  const dire = (t, ms) => (A() ? A().dire(t, ms) : null);
  const COULEUR_ZONE = { papa: '#facc15', hakim: '#2dd4bf', instru: '#94a3b8', tous: '#a78bfa' };
  const VOIX = new Set(['voix_hakim', 'voix_papa', 'voix_origine', 'voix']);
  const NOTES = { '1/4': 1, '1/8': 0.5, '1/8.': 0.75, '1/16': 0.25, '1/4.': 1.5, '1/2': 2 };
  // (13/11, le studio pro) le nettoyage de chaque voix : chaque étape « auto » (la mesure décide), « oui » (forcée), « non » (coupée)
  const ETAPES_PRO = [['souffle', 'Souffle, bruit de fond'], ['ronflement', 'Ronflement 50 Hz'], ['clics', 'Clics de bouche'], ['ecretage', 'Écrêtage'],
    ['plosives', 'Plosives (p, b)'], ['respirations', 'Respirations (baissées)'], ['porte', 'Porte douce entre les phrases'], ['nivellement', 'Nivellement (rider)'],
    ['continu', 'Décalage continu']];
  const TYPES_VOIX = [['principale', 'principale'], ['double', 'double'], ['back', 'back (chœur)'], ['adlib', 'ad-lib']];
  const s = { projets: [], projet: null, choisie: lsLire('studio-projet', ''), pps: Number(lsLire('studio-pps', '10')) || 10, pos: 0, lecture: null,
    formes: new Map(), detail: '', rec: null, zones: null };
  const mmss = (t) => { t = Math.max(0, Number(t) || 0); const m = Math.floor(t / 60); return `${m}:${(t - m * 60).toFixed(1).padStart(4, '0')}`; };
  const lireTemps = (v) => { const x = String(v || '').trim().replace(',', '.'); const m = x.match(/^(\d+):(\d+(?:\.\d+)?)$/); return m ? +m[1] * 60 + +m[2] : Number(x) || 0; };

  async function json(chemin) {
    const r = await fetch(chemin, { headers: H() });
    const o = await r.json().catch(() => ({}));
    if (!r.ok || o.ok === false) throw new Error(o.erreur || `erreur ${r.status}`);
    return o;
  }
  async function poster(chemin, corps) {
    const r = await fetch(chemin, { method: 'POST', headers: { ...H(), 'Content-Type': 'application/json' }, body: JSON.stringify(corps || {}) });
    const o = await r.json().catch(() => ({}));
    if (r.status === 409 && /changé/.test(o.erreur || '')) { dire('Hakim a changé le projet entre-temps : je recharge.'); await chargerProjet(); throw new Error('rechargé'); }
    if (!r.ok || o.ok === false) throw new Error(o.erreur || `erreur ${r.status}`);
    return o;
  }

  /* ---------- les projets ---------- */
  async function chargerListe() {
    try { s.projets = (await json('/api/studio/projets')).projets || []; } catch (_) { return; }
    const sel = $('mpProjet');
    const vu = s.projets.find(p => p.id === s.choisie);
    if (!vu && s.projets[0]) s.choisie = s.projets[0].id;
    sel.innerHTML = s.projets.length ? s.projets.map(p => `<option value="${esc(p.id)}"${p.id === s.choisie ? ' selected' : ''}>${esc(p.titre)} · ${esc(p.pistes)} pistes</option>`).join('')
      : '<option value="">Aucun projet : crée-en un</option>';
    const p = s.projets.find(x => x.id === s.choisie);
    if (p && (!s.projet || s.projet.id !== p.id || s.projet.rev !== p.rev) && !s.lecture && !s.rec) await chargerProjet();
    if (!p) { s.projet = null; $('mpVue').hidden = true; }
  }
  async function chargerProjet() {
    if (!s.choisie) return;
    try { s.projet = (await json(`/api/studio/projet?id=${encodeURIComponent(s.choisie)}`)).projet; } catch (e) { dire(`Projet illisible : ${e.message}`); return; }
    s.zones = null;
    $('mpVue').hidden = false;
    rendreTout();
    for (const t of s.projet.pistes) if (t.f && !s.formes.has(t.f)) chargerForme(t.f);
  }
  async function chargerForme(f) {
    s.formes.set(f, null);
    try { s.formes.set(f, await json(`/api/studio/forme?f=${encodeURIComponent(f)}`)); dessinerPistes(); } catch (_) { s.formes.delete(f); }
  }
  const remplacer = (o) => { if (o && o.projet) { s.projet = o.projet; rendreTout(); } };
  function regler(piste, reglages) {
    if (!s.projet) return;
    const t = s.projet.pistes.find(x => x.id === piste);
    // les réglages imbriqués (égaliseur, compressions, studio pro) se fusionnent : le reste de la tranche ne bouge pas
    if (t) for (const [k, v] of Object.entries(reglages)) t[k] = v && typeof v === 'object' && !Array.isArray(v) && t[k] && typeof t[k] === 'object' ? { ...t[k], ...v } : v;
    appliquerEnDirect();
    return poster('/api/studio/projet/regler', { id: s.projet.id, rev: s.projet.rev, piste, reglages }).then((o) => { s.projet.rev = o.projet.rev; }).catch((e) => { if (e.message !== 'rechargé') dire(e.message); });
  }

  /* ---------- l'affichage ---------- */
  const dureeProjet = () => Math.max(5, Number(s.projet && s.projet.duree_s) || Math.max(5, ...(s.projet ? s.projet.pistes.map(t => (s.formes.get(t.f) || {}).duree_s || 0) : [5])));
  function rendreTout() {
    const p = s.projet;
    if (!p) return;
    const bpm = Number(p.tempo) || 0;
    $('mpInfos').textContent = `${p.titre} · ${mmss(dureeProjet())} · ${bpm ? `${bpm} BPM` : 'tempo ?'} · ${p.tonalite || 'tonalité ?'} · version ${p.rev}`;
    rendreGrille(); rendreZones(); rendreDetail(); rendreRendus(); rendreMaster();
  }
  // le master du projet : sa cible, ses 3 bandes, ses graves en mono, son dither (réglés ici, gardés dans le projet)
  function rendreMaster() {
    const m = s.projet.master || {};
    $('mpCible').value = m.cible === 'club' ? 'club' : 'streaming';
    $('mpMultibande').checked = m.multibande !== false;
    $('mpMonoGraves').checked = Number(m.mono_graves_hz ?? 120) > 0;
    $('mpDither').checked = m.dither16 !== false;
    $('mpMasterDit').textContent = `${m.cible === 'club' ? 'Club, −9 LUFS' : 'Streaming, −14 LUFS'}, crête ≤ −1 dBTP ; le son entier, ta version et l’instru, dans Hakim › Chansons.`;
  }
  function rendreGrille() {
    const p = s.projet, L = Math.ceil(dureeProjet() * s.pps);
    const lignes = [`<div class="mp-ligne regle"><div class="mp-tete vide">${esc(p.tempo ? 'mesures' : 'secondes')}</div><div class="mp-piste" style="width:${L}px;height:26px"><canvas id="mpRegle" width="${L}" height="26"></canvas></div></div>`,
      `<div class="mp-ligne zones"><div class="mp-tete vide">zones</div><div class="mp-piste" id="mpZonesLigne" style="width:${L}px;height:26px">${(p.zones || []).map(z =>
        `<div class="mp-zone" style="left:${z.debut_s * s.pps}px;width:${Math.max(4, (z.fin_s - z.debut_s) * s.pps)}px;background:${COULEUR_ZONE[z.qui] || '#94a3b8'}" title="${esc(z.nom)}">${esc(z.nom)}</div>`).join('')}</div></div>`];
    for (const t of p.pistes) {
      lignes.push(`<div class="mp-ligne${s.detail === t.id ? ' choisie' : ''}" data-ligne="${esc(t.id)}"><div class="mp-tete">`
        + `<div class="nom" data-detail="${esc(t.id)}"><span class="pastille" style="background:${esc(t.couleur || '#94a3b8')}"></span>${esc(t.nom)}</div>`
        + `<div class="boutons"><button type="button" class="m${t.muet ? ' on' : ''}" data-muet="${esc(t.id)}" aria-label="Muet">M</button>`
        + `<button type="button" class="s${t.solo ? ' on' : ''}" data-solo="${esc(t.id)}" aria-label="Solo">S</button>`
        + `<button type="button" data-detail="${esc(t.id)}" aria-label="Réglages">⚙</button></div>`
        + `<input type="range" min="-30" max="12" step="0.5" value="${Number(t.volume_db) || 0}" data-volume="${esc(t.id)}" aria-label="Volume de ${esc(t.nom)}">`
        + `</div><div class="mp-piste" style="width:${L}px;height:58px"><canvas data-onde="${esc(t.id)}" width="${L}" height="58"></canvas></div></div>`);
    }
    $('mpGrille').innerHTML = lignes.join('') + '<div class="mp-tete-lecture" id="mpCurseur"></div>';
    dessinerRegle(); dessinerPistes(); placerCurseur();
  }
  function dessinerRegle() {
    const c = $('mpRegle'); if (!c) return;
    const g = c.getContext('2d'), p = s.projet, bpm = Number(p.tempo) || 0;
    g.clearRect(0, 0, c.width, c.height);
    g.fillStyle = getComputedStyle(document.body).getPropertyValue('--txt-3') || '#888'; g.strokeStyle = g.fillStyle; g.font = '10px system-ui';
    const D = dureeProjet();
    if (bpm) {
      const mes = 60 / bpm * (Number(p.mesure) || 4), t0 = Number(p.premier_temps_s) || 0, pas = Math.max(1, Math.ceil(40 / (mes * s.pps)));
      for (let k = 0; t0 + k * mes <= D; k += pas) { const x = (t0 + k * mes) * s.pps; g.fillRect(x, 14, 1, 12); g.fillText(String(k + 1), x + 2, 11); }
    } else for (let t = 0; t <= D; t += 5) { const x = t * s.pps; g.fillRect(x, 16, 1, 10); g.fillText(mmss(t).replace(/\.0$/, ''), x + 2, 11); }
  }
  function dessinerPistes() {
    if (!s.projet) return;
    for (const c of document.querySelectorAll('canvas[data-onde]')) {
      const t = s.projet.pistes.find(x => x.id === c.dataset.onde), f = t && s.formes.get(t.f), g = c.getContext('2d');
      g.clearRect(0, 0, c.width, c.height);
      if (!t || !f) continue;
      const regions = (t.regions && t.regions.length) ? t.regions : [{ debut_s: 0, source_debut_s: 0, duree_s: null }];
      g.globalAlpha = t.muet ? 0.3 : 0.9;
      for (const r of regions) {
        const d0 = Number(r.source_debut_s) || 0, dur = r.duree_s == null ? f.duree_s - d0 : Number(r.duree_s);
        const x0 = (Number(r.debut_s) || 0) * s.pps, w = Math.max(1, dur * s.pps);
        g.fillStyle = 'rgba(148,163,184,.12)'; g.fillRect(x0, 2, w, c.height - 4);
        g.fillStyle = t.couleur || '#94a3b8';
        const mi = c.height / 2;
        for (let x = 0; x < w; x++) {
          const a = Math.floor((d0 + x / s.pps) / f.pas_s), b = Math.max(a + 1, Math.floor((d0 + (x + 1) / s.pps) / f.pas_s));
          let m = 0; for (let i = a; i < b && i < f.pics.length; i++) m = Math.max(m, f.pics[i]);
          const h = Math.max(1, m / 100 * (mi - 3));
          g.fillRect(x0 + x, mi - h, 1, 2 * h);
        }
      }
      g.globalAlpha = 1;
    }
  }
  function placerCurseur() {
    const c = $('mpCurseur'); if (!c) return;
    c.style.left = `${128 + s.pos * s.pps}px`;
    $('mpTemps').textContent = mmss(s.pos);
  }

  /* ---------- le détail d'une piste ---------- */
  function rendreDetail() {
    const el = $('mpDetail'), t = s.projet && s.projet.pistes.find(x => x.id === s.detail);
    if (!t) { el.hidden = true; return; }
    el.hidden = false;
    const n = (v, d = 0) => Number.isFinite(Number(v)) ? Number(v) : d;
    const autres = s.projet.pistes.filter(x => x.id !== t.id);
    const champ = (cle, lib, v, a, b, pas) => `<label>${lib}<input type="number" data-champ="${cle}" value="${n(v)}" min="${a}" max="${b}" step="${pas}"></label>`;
    el.innerHTML = `<h3 style="margin-top:0">⚙ ${esc(t.nom)} <span class="g">${esc(t.role)}</span></h3>`
      + `<div class="mp-grille2">`
      + champ('pan', 'Panoramique (−1 gauche, +1 droite)', t.pan, -1, 1, 0.05)
      + champ('eq.coupe_bas_hz', 'Coupe-bas (Hz, 0 = sans)', t.eq.coupe_bas_hz, 0, 400, 5)
      + champ('eq.grave_db', 'Graves (dB)', t.eq.grave_db, -12, 12, 0.5)
      + champ('eq.medium_db', 'Médiums (dB)', t.eq.medium_db, -12, 12, 0.5)
      + champ('eq.medium_hz', 'Médiums à (Hz)', t.eq.medium_hz, 150, 8000, 10)
      + champ('eq.aigu_db', 'Aigus (dB)', t.eq.aigu_db, -12, 12, 0.5)
      + `<label>Compression<select data-champ="comp.actif"><option value="1"${t.comp.actif ? ' selected' : ''}>oui</option><option value="0"${t.comp.actif ? '' : ' selected'}>non</option></select></label>`
      + champ('comp.seuil_db', 'Seuil (dB)', t.comp.seuil_db, -50, 0, 1)
      + champ('comp.ratio', 'Ratio', t.comp.ratio, 1, 20, 0.5)
      + champ('deesser', 'Dé-esseur (0 à 1)', t.deesser, 0, 1, 0.05)
      + champ('reverb', 'Réverb (0 à 1)', t.reverb, 0, 1, 0.05)
      + champ('delai', 'Délai (0 à 1)', t.delai, 0, 1, 0.05)
      + `<label>Délai : note<select data-champ="delai_note">${Object.keys(NOTES).map(k => `<option${t.delai_note === k ? ' selected' : ''}>${k}</option>`).join('')}</select></label>`
      + (VOIX.has(t.role) ? `<label>Autotune<select data-champ="autotune"><option value=""${!t.autotune ? ' selected' : ''}>non</option><option value="leger"${t.autotune === 'leger' ? ' selected' : ''}>léger</option><option value="fort"${t.autotune === 'fort' ? ' selected' : ''}>fort</option></select></label>` : '')
      + `<label>Creusée sous<select data-champ="sidechain.cle"><option value="">rien</option>${autres.map(x => `<option value="${esc(x.id)}"${(t.sidechain || {}).cle === x.id ? ' selected' : ''}>${esc(x.nom)}</option>`).join('')}</select></label>`
      + champ('sidechain.db', 'de (dB)', (t.sidechain || {}).db, 0, 12, 0.5)
      + `</div>` + (VOIX.has(t.role) ? proDetail(t, champ) : '')
      + `<div class="sous">L’écoute ici approche le rendu (nettoyage, autotune et sidechain seulement au rendu sur le Mac).</div>`
      + `<div class="gestes">${!VOIX.has(t.role) && ['instru', 'ajout'].includes(t.role) ? `<button type="button" data-separer="${esc(t.id)}">✂︎ Séparer en pistes</button>` : ''}`
      + `<button type="button" data-retirer="${esc(t.id)}">🗑 Retirer la piste</button><button type="button" data-detail="">Fermer</button></div>`;
  }
  // le studio pro d'une voix : son nettoyage étape par étape, son type, son calage ; et ce que le dernier rendu en a dit
  function proDetail(t, champ) {
    const pro = t.pro || { actif: false }, cr = t.comp_rapide || {};
    const choix = (cle, v, opts) => `<select data-champ="${cle}">${opts.map(([val, lib]) => `<option value="${val}"${String(v) === val ? ' selected' : ''}>${lib}</option>`).join('')}</select>`;
    const mode = (k, lib) => `<label>${lib}${choix(`pro.${k}`, pro[k] || 'auto', [['auto', 'auto (mesuré)'], ['oui', 'oui, forcé'], ['non', 'non, coupé']])}</label>`;
    const dernier = (s.projet.rendus || []).slice(-1)[0], rp = dernier && (dernier.pro || []).find(x => x.id === t.id);
    return `<h4 style="margin:10px 0 4px">🎙️ Studio pro (le nettoyage ne corrige que ce que la mesure trouve)</h4><div class="mp-grille2">`
      + `<label>Nettoyage${choix('pro.actif', pro.actif ? '1' : '0', [['1', 'oui'], ['0', 'non']])}</label>`
      + `<label>Cette voix est${choix('pro.type', pro.type || 'principale', TYPES_VOIX)}</label>`
      + ETAPES_PRO.map(([k, lib]) => mode(k, lib)).join('')
      + champ('pro.respirations_db', 'Respirations baissées de (dB)', pro.respirations_db ?? -8, -30, 0, 1)
      + `<label>Calage sur la voix principale${choix('pro.calage', pro.calage || 'auto', [['auto', 'auto (doubles, backs)'], ['non', 'non']])}</label>`
      + `<label>Délai jeté en fin de phrase${choix('pro.delai_jete', pro.delai_jete || 'auto', [['auto', 'auto (ad-libs)'], ['oui', 'oui'], ['non', 'non']])}</label>`
      + `<label>Crêtes (compression rapide)${choix('comp_rapide.actif', cr.actif ? '1' : '0', [['1', 'oui'], ['0', 'non']])}</label>`
      + champ('saturation', 'Saturation, présence (0 à 1)', t.saturation ?? 0, 0, 1, 0.05)
      + champ('eq.coupe_haut_hz', 'Coupe-haut (Hz, 0 = sans)', (t.eq || {}).coupe_haut_hz ?? 0, 0, 20000, 100)
      + `</div>` + (rp ? `<div class="sous">Dernier rendu : ${esc(rp.resume)}</div>` : '');
  }
  function valeurChamp(e) {
    const k = e.dataset.champ, v = e.value;
    if (k === 'comp.actif' || k === 'comp_rapide.actif' || k === 'pro.actif') return [k, v === '1'];
    if (k === 'autotune' || k === 'delai_note' || k === 'sidechain.cle' || (k.startsWith('pro.') && k !== 'pro.respirations_db')) return [k, v];
    return [k, Number(v)];
  }

  /* ---------- les zones ---------- */
  function rendreZones() {
    const z = s.zones || (s.zones = (s.projet.zones || []).map(x => ({ ...x })));
    $('mpZones').innerHTML = z.length ? z.map((x, i) => `<div class="zone" data-zone="${i}"><input type="text" data-z="nom" value="${esc(x.nom)}" aria-label="Nom de la zone">`
      + `<input type="text" data-z="debut_s" value="${esc(mmss(x.debut_s))}" aria-label="Début"><input type="text" data-z="fin_s" value="${esc(mmss(x.fin_s))}" aria-label="Fin">`
      + `<select data-z="qui" aria-label="À qui">${['papa', 'hakim', 'instru'].map(q => `<option value="${q}"${x.qui === q ? ' selected' : ''}>${q === 'papa' ? 'toi' : q === 'hakim' ? 'Hakim' : 'instru'}</option>`).join('')}</select>`
      + `<button type="button" data-zone-sup="${i}" aria-label="Retirer la zone">✕</button></div>`).join('') : '<div class="vide">Aucune zone.</div>';
  }

  /* ---------- les rendus ---------- */
  function rendreRendus() {
    const l = (s.projet.rendus || []).slice().reverse();
    $('mpRendus').innerHTML = l.length ? l.map(r => {
      const m = r.master || {}, f = r.fichiers || {};
      const son = (k, nom) => (f[k] && f[k].mp3 ? `<div class="son"><div class="tete">${nom}</div><div class="gestes"><button type="button" data-lire="${esc(f[k].mp3)}">▶︎ Écouter</button><button type="button" data-dl="${esc(f[k].mp3)}" aria-label="Télécharger">⬇︎</button></div></div>` : '');
      return `<div class="son"><div class="tete"><b>${esc(r.nom)}</b><span class="meta">${esc(new Date((r.t || 0) * 1000).toLocaleString('fr-FR', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }))}</span></div>`
        + `<div class="mesures">${esc(m.lufs)} LUFS · crête vraie ${esc(m.crete_dbtp)} dBTP (MP3 ${esc(r.mp3_crete_dbtp)}) · PLR ${esc(m.plr_db)} dB · LRA ${esc(m.lra)} LU</div>`
        + `<ul class="conseils">${(r.avis || []).map(a => `<li>${esc(a)}</li>`).join('')}</ul>`
        + son('complet', 'Le son entier') + son('zones_papa', 'Ta version (tes zones en instru)') + son('instru', 'L’instru seule')
        + (f.complet && f.complet.wav16 ? `<div class="son"><div class="tete">WAV 16 bits (avec dither)</div><div class="gestes"><button type="button" data-dl="${esc(f.complet.wav16)}" aria-label="Télécharger le WAV 16 bits">⬇︎</button></div></div>` : '')
        + (r.pistes && r.pistes.length ? `<details><summary>Les pistes séparées (${r.pistes.length})</summary>${r.pistes.map(x => `<div class="son"><div class="tete">${esc(x.split('/').pop())}</div><div class="gestes"><button type="button" data-lire="${esc(x)}">▶︎</button><button type="button" data-dl="${esc(x)}">⬇︎</button></div></div>`).join('')}</details>` : '')
        + '</div>';
    }).join('') : '<div class="vide">Pas encore de mix : « Mixer et masteriser ».</div>';
  }

  /* ---------- l'écoute, mixée en direct (WebAudio) ---------- */
  let reverbIR = null;
  function ir(c) {
    if (reverbIR && reverbIR.sampleRate === c.sampleRate) return reverbIR;
    const n = Math.floor(c.sampleRate * 1.6), b = c.createBuffer(2, n, c.sampleRate);
    for (let k = 0; k < 2; k++) { const d = b.getChannelData(k); for (let i = 0; i < n; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(10, -3 * i / n) * 0.12; }
    return (reverbIR = b);
  }
  const lin = (db) => Math.pow(10, (Number(db) || 0) / 20);
  function gainEffectif(t) {
    const solo = s.projet.pistes.some(x => x.solo && !x.muet);
    return t.muet || (solo && !t.solo) ? 0 : lin(t.volume_db);
  }
  async function jouer(depuis, version = $('mpVersion').value, T0 = null) {
    const c = await A().contexte();
    arreterLecture();
    const p = s.projet, tampons = {};
    dire('Chargement des pistes…', 0);
    await Promise.all(p.pistes.filter(t => t.f).map(async t => { try { tampons[t.id] = await A().tamponDe(t.f); } catch (_) {} }));
    dire('', 1);
    const quand = T0 != null ? T0 : c.currentTime + 0.12, bus = c.createGain(), rv = c.createConvolver(), rvRet = c.createGain(), dl = c.createDelay(4), fb = c.createGain(), dlRet = c.createGain();
    rv.buffer = ir(c); rvRet.gain.value = 0.5; rv.connect(rvRet); rvRet.connect(bus);
    const bpm = Number(p.tempo) || 0;
    dl.delayTime.value = bpm ? 60 / bpm * 0.75 : 0.375; fb.gain.value = 0.35; dl.connect(fb); fb.connect(dl); dl.connect(dlRet); dlRet.gain.value = 0.6; dlRet.connect(bus);
    bus.connect(c.destination);
    const noeuds = {}, sources = [];
    for (const t of p.pistes) {
      const tb = tampons[t.id]; if (!tb) continue;
      const entree = c.createGain(), hp = c.createBiquadFilter(), gr = c.createBiquadFilter(), md = c.createBiquadFilter(), ai = c.createBiquadFilter();
      hp.type = 'highpass'; gr.type = 'lowshelf'; md.type = 'peaking'; ai.type = 'highshelf';
      const comp = c.createDynamicsCompressor(), zone = c.createGain(), vol = c.createGain(), pan = c.createStereoPanner(), envR = c.createGain(), envD = c.createGain();
      entree.connect(hp); hp.connect(gr); gr.connect(md); md.connect(ai); ai.connect(comp); comp.connect(zone); zone.connect(vol); vol.connect(pan); pan.connect(bus);
      pan.connect(envR); envR.connect(rv); pan.connect(envD); envD.connect(dl);
      noeuds[t.id] = { hp, gr, md, ai, comp, vol, pan, envR, envD };
      // les voix se taisent dans les zones de papa (sa version), fondus de 40 ms
      if (version === 'papa' && VOIX.has(t.role)) for (const z of (p.zones || []).filter(z => z.qui === 'papa')) {
        const a = quand + z.debut_s - depuis, b = quand + z.fin_s - depuis;
        if (b <= quand) continue;
        zone.gain.setValueAtTime(1, Math.max(quand, a - 0.04)); zone.gain.linearRampToValueAtTime(0, Math.max(quand, a));
        zone.gain.setValueAtTime(0, Math.max(quand, b)); zone.gain.linearRampToValueAtTime(1, Math.max(quand, b + 0.04));
      }
      const regions = (t.regions && t.regions.length) ? t.regions : [{ debut_s: 0, source_debut_s: 0, duree_s: null }];
      for (const r of regions) {
        const d0 = Number(r.source_debut_s) || 0, dur = r.duree_s == null ? tb.duration - d0 : Number(r.duree_s), deb = Number(r.debut_s) || 0;
        if (deb + dur <= depuis) continue;
        const saute = Math.max(0, depuis - deb), src = c.createBufferSource(), g = c.createGain();
        src.buffer = tb; g.gain.value = lin(r.gain_db); src.connect(g); g.connect(entree);
        src.start(quand + Math.max(0, deb - depuis), d0 + saute, Math.max(0.01, dur - saute));
        sources.push(src);
      }
    }
    s.lecture = { c, quand, depuis, sources, noeuds, bus, version };
    appliquerEnDirect();
    $('mpLire').textContent = '⏸';
    const fin = depuis + (dureeProjet() - depuis);
    const tic = () => {
      if (!s.lecture || s.lecture.c !== c) return;
      s.pos = Math.min(fin, depuis + Math.max(0, c.currentTime - quand));
      placerCurseur();
      if (s.pos >= fin - 0.02 && !s.rec) return arreterLecture();
      s.lecture.raf = requestAnimationFrame(tic);
    };
    s.lecture.raf = requestAnimationFrame(tic);
    return s.lecture;
  }
  function appliquerEnDirect() {
    const l = s.lecture; if (!l || !s.projet) return;
    const now = l.c.currentTime;
    for (const t of s.projet.pistes) {
      const n = l.noeuds[t.id]; if (!n) continue;
      n.vol.gain.setTargetAtTime(gainEffectif(t), now, 0.02);
      n.pan.pan.setTargetAtTime(Math.max(-1, Math.min(1, Number(t.pan) || 0)), now, 0.02);
      const eq = t.eq || {};
      n.hp.frequency.value = Number(eq.coupe_bas_hz) >= 20 ? Number(eq.coupe_bas_hz) : 10;
      n.gr.frequency.value = Number(eq.grave_hz) || 120; n.gr.gain.value = Number(eq.grave_db) || 0;
      n.md.frequency.value = Number(eq.medium_hz) || 1000; n.md.Q.value = Number(eq.medium_q) || 1; n.md.gain.value = Number(eq.medium_db) || 0;
      n.ai.frequency.value = Number(eq.aigu_hz) || 8000; n.ai.gain.value = Number(eq.aigu_db) || 0;
      const c = t.comp || {};
      n.comp.threshold.value = c.actif ? Number(c.seuil_db) || -20 : 0; n.comp.ratio.value = c.actif ? Number(c.ratio) || 3 : 1;
      n.envR.gain.value = Number(t.reverb) || 0; n.envD.gain.value = (Number(t.delai) || 0) * 0.6;
    }
  }
  function arreterLecture() {
    const l = s.lecture; if (!l) return;
    s.lecture = null;
    cancelAnimationFrame(l.raf);
    for (const x of l.sources) try { x.stop(); } catch (_) {}
    try { l.bus.disconnect(); } catch (_) {}
    $('mpLire').textContent = '▶︎';
  }

  /* ---------- poser sa voix : la prise à l'instant de la lecture ---------- */
  async function enregistrer() {
    if (s.rec) return s.rec.finir();
    const a = A();
    if (!a || a.occupe()) return dire('Une autre prise ou une mesure est en cours.');
    $('mpRec').disabled = true;
    try {
      const c = await a.contexte();
      await a.lireRoute();
      const m = await a.ouvrirMicro(), cal = a.latence(), sortie = a.route(), kal = a.calageActuel(), depuis = s.pos;
      dire([m.avertir, sortie.avertir, kal ? '' : 'Décalage pas encore mesuré pour cette sortie : mesure-le plus bas (« T’enregistrer », 2).'].filter(Boolean).join(' '), 9000);
      const T0 = c.currentTime + 3.2;
      for (let k = 3; k >= 1; k--) a.clic(c, T0 - k, k === 3 ? 0.6 : 0.4);
      await jouer(depuis, 'papa', T0);                          // tu entends ta version : tes zones en instru
      const r = a.capter(c, m, T0, (n) => { $('mpNiveau').style.width = `${Math.min(100, n * 140)}%`; });
      $('mpRec').textContent = '■ Arrêter'; $('mpRec').classList.add('actif'); $('mpRec').disabled = false;
      $('mpRecEtat').textContent = `Prise à partir de ${mmss(depuis)} (décalage ${cal} ms retiré).`;
      let fini = false;
      s.rec = { finir: async () => {
        if (fini) return; fini = true;
        arreterLecture();
        let prise = null;
        try { prise = r.arreter(); } catch (e) { $('mpRecEtat').textContent = `Prise perdue : ${e.message}`; }
        s.rec = null;
        $('mpRec').textContent = '● Poser ma voix'; $('mpRec').classList.remove('actif'); $('mpNiveau').style.width = '0';
        if (!prise || prise.x.length < prise.sr) { if (prise) $('mpRecEtat').textContent = 'Prise trop courte, rien gardé.'; return; }
        $('mpRecEtat').textContent = `Envoi de la prise (${mmss(prise.x.length / prise.sr)})…`;
        const q = new URLSearchParams({ id: s.projet.id, debut: String(depuis), latence: String(cal), cle: sortie.cle, sortie: sortie.nom, micro: prise.micro || '',
          methode: kal ? kal.methode : 'estimation', titre: 'Voix de papa' });
        try {
          const rep = await fetch(`/api/studio/projet-prise?${q}`, { method: 'POST', headers: { ...H(), 'Content-Type': 'audio/wav' }, body: a.enWav(prise.x, prise.sr) });
          const o = await rep.json().catch(() => ({}));
          if (!rep.ok || !o.ok) throw new Error(o.erreur || `erreur ${rep.status}`);
          remplacer(o);
          for (const t of s.projet.pistes) if (t.f && !s.formes.has(t.f)) chargerForme(t.f);
          $('mpRecEtat').textContent = 'Ta voix est posée dans le projet (piste « Voix de papa »). Réécoute, règle, puis « Mixer et masteriser ».';
          a.recharger();
        } catch (e) { $('mpRecEtat').textContent = `Prise non envoyée : ${e.message}`; }
      } };
    } catch (e) {
      s.rec = null; $('mpRec').disabled = false; $('mpRec').textContent = '● Poser ma voix'; $('mpRec').classList.remove('actif'); arreterLecture();
      dire(/Permission|NotAllowed/i.test(String(e && (e.name || e.message))) ? 'Micro refusé : autorise-le pour le cockpit.' : `Pas d’enregistrement : ${e.message}`);
    }
  }

  /* ---------- les gestes ---------- */
  $('mpProjet').addEventListener('change', () => { s.choisie = $('mpProjet').value; lsEcrire('studio-projet', s.choisie); arreterLecture(); s.pos = 0; s.detail = ''; chargerProjet(); });
  $('mpLire').addEventListener('click', () => (s.lecture ? arreterLecture() : jouer(s.pos).catch(e => dire(e.message))));
  $('mpDebut').addEventListener('click', () => { const l = !!s.lecture; arreterLecture(); s.pos = 0; placerCurseur(); if (l) jouer(0); });
  $('mpRec').addEventListener('click', enregistrer);
  $('mpVersion').addEventListener('change', () => { if (s.lecture) jouer(s.pos); });
  const zoom = (f) => { const x = $('mpScroll').scrollLeft / s.pps; s.pps = Math.max(2, Math.min(80, s.pps * f)); lsEcrire('studio-pps', String(s.pps)); rendreGrille(); $('mpScroll').scrollLeft = x * s.pps; };
  $('mpZoomPlus').addEventListener('click', () => zoom(1.5));
  $('mpZoomMoins').addEventListener('click', () => zoom(1 / 1.5));
  $('mpGrille').addEventListener('click', (ev) => {
    const b = ev.target.closest('button,[data-detail]');
    const d = b ? b.dataset : {};
    if (d.muet) { const t = s.projet.pistes.find(x => x.id === d.muet); regler(t.id, { muet: !t.muet }); return rendreGrille(); }
    if (d.solo) { const t = s.projet.pistes.find(x => x.id === d.solo); regler(t.id, { solo: !t.solo }); return rendreGrille(); }
    if (d.detail !== undefined && b) { s.detail = s.detail === d.detail ? '' : d.detail; rendreGrille(); return rendreDetail(); }
    // toucher la règle, les zones ou une forme d'onde : la lecture va là
    const piste = ev.target.closest('.mp-piste');
    if (!piste) return;
    const x = ev.clientX - piste.getBoundingClientRect().left;
    s.pos = Math.max(0, Math.min(dureeProjet(), x / s.pps));
    placerCurseur();
    if (s.lecture && !s.rec) jouer(s.pos);
  });
  $('mpGrille').addEventListener('input', (ev) => {
    const e = ev.target;
    if (!e.dataset.volume) return;
    const t = s.projet.pistes.find(x => x.id === e.dataset.volume);
    t.volume_db = Number(e.value); appliquerEnDirect();
  });
  $('mpGrille').addEventListener('change', (ev) => { const e = ev.target; if (e.dataset.volume) regler(e.dataset.volume, { volume_db: Number(e.value) }); });
  $('mpDetail').addEventListener('change', (ev) => {
    const e = ev.target.closest('[data-champ]'); if (!e || !s.detail) return;
    const [k, v] = valeurChamp(e), [a, b] = k.split('.');
    const t = s.projet.pistes.find(x => x.id === s.detail);
    const r = b ? { [a]: { ...(a === 'sidechain' ? { cle: (t.sidechain || {}).cle || '', db: (t.sidechain || {}).db || 0 } : {}), [b]: v } } : { [a]: v };
    if (a === 'sidechain' && b === 'cle' && v && !Number(r.sidechain.db)) r.sidechain.db = 2;
    if (a === 'sidechain') t.sidechain = r.sidechain;
    regler(s.detail, r);
  });
  $('mpDetail').addEventListener('click', async (ev) => {
    const b = ev.target.closest('button'); if (!b) return;
    const d = b.dataset;
    try {
      if (d.detail !== undefined) { s.detail = ''; rendreGrille(); return rendreDetail(); }
      if (d.retirer) { if (!confirm('Retirer cette piste du projet ?')) return; remplacer(await poster('/api/studio/projet/retirer', { id: s.projet.id, rev: s.projet.rev, piste: d.retirer })); s.detail = ''; return rendreDetail(); }
      if (d.separer) { b.disabled = true; await poster('/api/studio/projet/separer', { id: s.projet.id, piste: d.separer, separer: '4' }); dire('Séparation en file sur le Mac : les pistes arrivent dans une minute ou deux.'); A().recharger(); }
    } catch (e) { if (e.message !== 'rechargé') dire(e.message); b.disabled = false; }
  });
  $('mpZones').addEventListener('change', (ev) => {
    const e = ev.target.closest('[data-z]'), z = e && s.zones[Number(e.closest('[data-zone]').dataset.zone)];
    if (!z) return;
    z[e.dataset.z] = e.dataset.z === 'debut_s' || e.dataset.z === 'fin_s' ? lireTemps(e.value) : e.value;
  });
  $('mpZones').addEventListener('click', (ev) => { const b = ev.target.closest('[data-zone-sup]'); if (b) { s.zones.splice(Number(b.dataset.zoneSup), 1); rendreZones(); } });
  $('mpZoneAjout').addEventListener('click', () => {
    const bpm = Number(s.projet.tempo) || 0, l = bpm ? 4 * 60 / bpm * 8 : 15;    // 8 mesures, sinon 15 s
    s.zones.push({ nom: 'Couplet de papa', debut_s: Math.round(s.pos * 10) / 10, fin_s: Math.round(Math.min(dureeProjet(), s.pos + l) * 10) / 10, qui: 'papa' });
    rendreZones();
  });
  $('mpZonesOk').addEventListener('click', async () => {
    try { remplacer(await poster('/api/studio/projet/zones', { id: s.projet.id, rev: s.projet.rev, zones: s.zones })); s.zones = null; rendreZones(); dire('Zones gardées.'); }
    catch (e) { if (e.message !== 'rechargé') dire(e.message); }
  });
  for (const id of ['mpCible', 'mpMultibande', 'mpMonoGraves', 'mpDither']) $(id).addEventListener('change', async () => {
    if (!s.projet) return;
    try { remplacer(await poster('/api/studio/projet/reglages', { id: s.projet.id, rev: s.projet.rev, cible: $('mpCible').value, multibande: $('mpMultibande').checked,
      mono_graves_hz: $('mpMonoGraves').checked ? 120 : 0, dither16: $('mpDither').checked })); }
    catch (e) { if (e.message !== 'rechargé') dire(e.message); }
  });
  $('mpRendre').addEventListener('click', async () => {
    $('mpRendre').disabled = true;
    try { await poster('/api/studio/projet/rendre', { id: s.projet.id, mix_auto: $('mpMixAuto').checked, pistes_separees: $('mpPistesSep').checked });
      dire('Hakim mixe et masterise sur le Mac (une à trois minutes) : le résultat arrive ici et dans Hakim › Chansons.'); A().recharger(); }
    catch (e) { dire(e.message); } finally { $('mpRendre').disabled = false; }
  });
  // un nouveau projet : depuis une de ses chansons ou une instru du Studio (séparé sur le Mac, en file)
  $('mpNouveau').addEventListener('click', async () => {
    $('mpCreer').hidden = !$('mpCreer').hidden;
    if ($('mpCreer').hidden) return;
    try {
      const e = await json('/api/studio/etat');
      const opt = (f, t, g, bpm) => `<option value="${esc(f)}" data-bpm="${Number(bpm) || 0}">${esc(g)} · ${esc(t)}</option>`;
      $('mpSource').innerHTML = [...(e.chansons || []).filter(c => c.f).map(c => opt(c.f, c.titre, 'sa chanson', c.bpm)), ...(e.instrus || []).map(i => opt(i.f, i.titre, 'instru', 0))].join('');
    } catch (err) { dire(err.message); }
  });
  $('mpCreerNon').addEventListener('click', () => { $('mpCreer').hidden = true; });
  $('mpCreerOk').addEventListener('click', async () => {
    const f = $('mpSource').value; if (!f) return;
    const garder = [...document.querySelectorAll('.mpGarder')].filter(x => x.checked).map(x => x.value);
    $('mpCreerOk').disabled = true;
    try {
      const bpm = Number(($('mpSource').selectedOptions[0] || { dataset: {} }).dataset.bpm) || 0;     // le tempo qu'ACE-Step a reçu : sûr
      await poster('/api/studio/projet/creer', { f, separer: $('mpSeparer').value, voix: $('mpVoix').value, garder: garder.length === 3 ? [] : garder, tempo: bpm });
      $('mpCreer').hidden = true; dire('Le projet se prépare sur le Mac (séparation en pistes, une à deux minutes).'); A().recharger();
    } catch (e) { dire(e.message); } finally { $('mpCreerOk').disabled = false; }
  });
  // la liste suit les calculs (un projet prêt, un rendu fini, un réglage de Hakim) quand rien ne joue
  setInterval(() => { if (!document.hidden && !s.lecture && !s.rec) chargerListe(); }, 8000);
  window.addEventListener('pagehide', arreterLecture);
  chargerListe();
  window.StudioPistes = { _s: s, mmss, lireTemps };
})();
