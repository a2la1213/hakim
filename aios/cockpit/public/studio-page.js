/* (06/11) la page Studio : ses sons, lui faire écouter, t'enregistrer (décompte, latence compensée), le mix par Hakim.
   L'enregistrement : un seul AudioContext pour l'instru et le micro ; chaque morceau du micro est daté sur la même horloge que l'instru
   (playbackTime), on garde ce qui suit le départ de l'instru (T0). Le retard qui reste (sortie du casque + entrée du micro + le tampon)
   est la LATENCE, mesurée une fois (clic ou en tapant) et retirée au mix. Le micro s'ouvre SANS effets (sans annulation d'écho) :
   c'est ce qui garde le son dans le casque Bluetooth (appli 1.83) et la voix intacte.
   (10/11, Ahmed : « toujours le micro du smartphone, même s'il est en écouteurs Bluetooth, et calculer le décalage de l'écoute et de la
   voix ») dans l'appli (1.95 et plus), le micro du téléphone par l'appli (StudioMicro.java), horodaté par Android ; ailleurs, le micro
   intégré choisi par son nom ; le décalage mesuré et gardé PAR SORTIE (studio-calage.js, studio.js). */
(() => {
  const $ = (id) => document.getElementById(id);
  const H = () => ({ 'X-Jeton': window.jeton() });
  const TAMPON = 2048;
  const C = window.StudioCalage;                       // (10/11) les calculs du calage (studio-calage.js)
  const App = window.HakimApp && typeof window.HakimApp.studioMicroOuvrir === 'function' ? window.HakimApp : null;   // l'appli 1.95 et plus
  let rec = null;
  let etat = null, instruChoisie = localStorage.getItem('studio-instru') || '', priseChoisie = null, bulleMin = 0;
  const lsLire = (k, d) => { try { const v = localStorage.getItem(k); return v === null ? d : v; } catch (_) { return d; } };
  const lsEcrire = (k, v) => { try { localStorage.setItem(k, v); } catch (_) {} };
  const dire = (t, ms = 6000) => { $('bulle').textContent = t; clearTimeout(bulleMin); if (ms) bulleMin = setTimeout(() => { $('bulle').textContent = ''; }, ms); };
  const duree = (s) => { s = Math.round(Number(s) || 0); return s ? `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}` : '—'; };
  const date = (t) => t ? new Date((t > 1e12 ? t : t * 1000)).toLocaleString('fr-FR', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '';

  async function poster(chemin, corps, type = 'application/json') {
    const r = await fetch(chemin, { method: 'POST', headers: { ...H(), 'Content-Type': type }, body: type === 'application/json' ? JSON.stringify(corps || {}) : corps });
    const o = await r.json().catch(() => ({}));
    if (!r.ok || o.ok === false) throw new Error(o.erreur || `erreur ${r.status}`);
    return o;
  }
  // les sons passent derrière le jeton : chargés en blob, gardés le temps de la page
  const blobs = new Map();
  async function urlDe(f) {
    if (blobs.has(f)) return blobs.get(f);
    const r = await fetch(`/api/studio/son?f=${encodeURIComponent(f)}`, { headers: H() });
    if (!r.ok) throw new Error('son introuvable');
    const u = URL.createObjectURL(await r.blob());
    blobs.set(f, u);
    return u;
  }
  async function lire(bouton, f) {
    const zone = bouton.closest('.son');
    let a = zone.querySelector('audio');
    if (a) { a.remove(); return; }
    bouton.disabled = true;
    try { a = document.createElement('audio'); a.controls = true; a.preload = 'auto'; a.src = await urlDe(f); zone.appendChild(a); a.play().catch(() => {}); }
    catch (e) { dire(e.message); } finally { bouton.disabled = false; }
  }
  async function telecharger(f) {
    try { const a = document.createElement('a'); a.href = await urlDe(f); a.download = f.split('/').pop(); document.body.appendChild(a); a.click(); a.remove(); }
    catch (e) { dire(e.message); }
  }
  async function faireEcouter(f, titre) {
    try { await poster('/api/studio/ecouter', { f, titre }); dire(`Hakim écoute « ${titre} »…`); charger(); }
    catch (e) { dire(`Pas d’écoute : ${e.message}`); }
  }

  /* ---------- l'affichage ---------- */
  function gestesSon(f, titre, extra = '') {
    return `<div class="gestes"><button type="button" data-lire="${esc(f)}">▶︎ Écouter</button><button type="button" data-dl="${esc(f)}" aria-label="Télécharger">⬇︎</button>`
      + `<button type="button" data-ecouter="${esc(f)}" data-titre="${esc(titre)}">👂 Faire écouter à Hakim</button>${extra}</div>`;
  }
  function rendre() {
    if (!etat) return;
    // les calculs
    const calc = [...etat.travaux.map(t => ({ titre: `${t.type === 'mixer' ? 'Mix' : 'Instru (Demucs)'} ${t.titre ? `« ${t.titre} »` : ''}`, etat: t.etat,
      p: t.etapes ? (t.etape || 0) / t.etapes : 0, texte: t.erreur || t.texte })),
      ...etat.chansons.filter(c => c.etat === 'en cours').map(c => ({ titre: `Hakim compose « ${c.titre} »`, etat: 'en cours',
        p: c.progres ? c.progres.etape / c.progres.etapes : 0.05, texte: c.progres ? c.progres.texte : 'démarrage' }))]
      .filter(c => c.etat !== 'fini');
    $('calculsCarte').hidden = !calc.length;
    $('calculs').innerHTML = calc.map(c => `<div class="calcul${c.etat === 'raté' ? ' rate' : ''}"><b>${esc(c.titre)}</b> — ${esc(c.etat)}${c.texte ? ` : ${esc(c.texte)}` : ''}`
      + `${c.etat === 'raté' ? '' : `<div class="jauge"><i style="width:${Math.round(c.p * 100)}%"></i></div>`}</div>`).join('');
    // les instrus
    const instrus = [...etat.instrus.map(i => ({ f: i.f, t: `${i.titre}${i.origine === 'demucs' ? '' : ' (importée)'} · ${duree(i.duree_s)}` })),
      ...etat.chansons.filter(c => c.f && c.instrumental).map(c => ({ f: c.f, t: `${c.titre} (Hakim, ${c.style}${c.bpm ? `, ${c.bpm} BPM` : ''}) · ${duree(c.duree_s)}` }))];
    if (!instrus.some(i => i.f === instruChoisie)) instruChoisie = instrus.length ? instrus[0].f : '';
    $('instru').innerHTML = instrus.length ? instrus.map(i => `<option value="${esc(i.f)}"${i.f === instruChoisie ? ' selected' : ''}>${esc(i.t)}</option>`).join('')
      : '<option value="">Aucune instru : importe-en une, demande-la à Hakim, ou fais celle d’une de ses chansons (🎹 plus bas)</option>';
    $('rec').disabled = !instruChoisie && !rec;
    $('ecouterInstru').disabled = !instruChoisie;
    // les prises
    const prises = etat.prises;
    priseChoisie = prises.find(p => p.choisie) || null;
    $('prises').innerHTML = prises.length ? prises.map(p => `<div class="son" data-prise="${esc(p.id)}"><div class="tete">${p.choisie ? '<span class="g choisie">★ choisie</span>' : ''}`
      + `<span>${esc(p.titre)}</span><span class="meta">${date(p.ts)} · ${duree(p.duree_s)} · décalage ${Math.round(p.latence_ms || 0)} ms${p.sortie ? ` · 🎧 ${esc(p.sortie)}` : ''}${p.micro ? ` · 🎤 ${esc(p.micro)}` : ''}</span></div>`
      + `<div class="gestes"><button type="button" data-ensemble="${esc(p.id)}">▶︎ Avec l’instru</button><button type="button" data-lire="${esc(p.f)}">Voix seule</button>`
      + `<button type="button" data-choisir="${esc(p.id)}"${p.choisie ? ' disabled' : ''}>★ Choisir</button>`
      + `<button type="button" data-caler="${esc(p.id)}" title="Appliquer le calage du curseur à cette prise">⇆ Calage actuel</button>`
      + `<button type="button" data-effacer="${esc(p.id)}" aria-label="Effacer la prise">🗑</button></div></div>`).join('') : '<div class="vide">Aucune prise.</div>';
    $('mixer').disabled = !priseChoisie;
    $('mixPrise').textContent = priseChoisie ? `Prise choisie : ${priseChoisie.titre} (${duree(priseChoisie.duree_s)}, calage ${Math.round(priseChoisie.latence_ms || 0)} ms)` : 'Choisis une prise (★) au-dessus.';
    montrerCalage();                                   // (10/11) le décalage de la sortie où papa écoute, et ceux gardés
    // les morceaux mixés
    $('mixes').innerHTML = etat.mixes.length ? etat.mixes.map(m => `<div class="son"><div class="tete"><span>${esc(m.titre)}</span>`
      + `<span class="meta">${date(m.date)} · ${duree(m.duree_s)}${m.mesure ? ` · ${m.mesure.lufs} LUFS, crête ${m.mesure.crete_db} dB` : ''}${m.telephone ? ' · 📱' : ''}</span></div>`
      + (m.conseils && m.conseils.length ? `<div class="sous" style="margin-top:4px">Hakim entend :</div><ul class="conseils">${m.conseils.map(c => `<li>${esc(c)}</li>`).join('')}</ul>` : '')
      + gestesSon(m.f, m.titre, m.f_wav ? `<button type="button" data-dl="${esc(m.f_wav)}">⬇︎ WAV</button>` : '') + '</div>').join('')
      : '<div class="vide">Aucun morceau mixé pour l’instant.</div>';
    // ses sons
    const ch = etat.chansons.filter(c => c.f);
    $('chansons').innerHTML = ch.length ? ch.map(c => `<div class="son"><div class="tete"><span>${esc(c.titre)}</span>`
      + `<span class="g" title="${esc(c.style || '')}">${esc(String(c.style || '').split(',')[0].slice(0, 32))}</span>${c.instrumental ? '<span class="g ok">instru</span>' : ''}${c.autotune ? '<span class="g">autotune</span>' : ''}`
      + `<span class="meta">${date(c.date)} · ${duree(c.duree_s)}${c.telephone ? ' · 📱' : ''}</span></div>`
      + gestesSon(c.f, c.titre, c.instrumental ? '' : `<button type="button" data-instru="${esc(c.f)}" title="Demucs retire sa voix">🎹 En faire une instru</button>`) + '</div>').join('')
      : '<div class="vide">Pas encore de chanson. Demande-lui d’en chanter une dans Parler, ou une instru ci-dessus.</div>';
    // l'écoute en cours
    const e = etat.ecoute;
    $('ecoute').innerHTML = e && e.actif ? `👂 Hakim écoute « ${esc(e.titre)} » : ${duree(e.position_s)} / ${duree(e.duree_s)}`
      + `${e.mots && e.mots.length ? `<br>Il a entendu : « ${esc(e.mots[e.mots.length - 1])} »` : ''} <button type="button" id="arreterEcoute">■ Arrêter</button>`
      : e && e.fin ? `Dernière écoute : « ${esc(e.titre)} » (${esc(e.fin)}).` : '';
  }
  let minuteur = 0;
  async function charger() {
    clearTimeout(minuteur);
    try { const r = await fetch('/api/studio/etat', { headers: H() }); if (r.ok) { etat = await r.json(); rendre(); } } catch (_) {}
    const vif = etat && (etat.travaux.some(t => t.etat !== 'fini' && t.etat !== 'raté') || etat.chansons.some(c => c.etat === 'en cours') || (etat.ecoute && etat.ecoute.actif));
    if (!document.hidden) minuteur = setTimeout(charger, vif ? 2500 : 15000);
  }
  document.addEventListener('visibilitychange', () => { if (!document.hidden) charger(); });

  /* ---------- l'audio ---------- */
  let ctx = null;
  const contexte = async () => { if (!ctx) ctx = new (window.AudioContext || window.webkitAudioContext)({ latencyHint: 'interactive' }); if (ctx.state !== 'running') await ctx.resume(); return ctx; };
  const tampons = new Map();
  async function tamponDe(f) {
    if (tampons.has(f)) return tampons.get(f);
    const c = await contexte();
    const r = await fetch(`/api/studio/son?f=${encodeURIComponent(f)}`, { headers: H() });
    if (!r.ok) throw new Error('son introuvable');
    const b = await c.decodeAudioData(await r.arrayBuffer());
    tampons.set(f, b);
    return b;
  }
  const crete = (d) => { let m = 0; for (let i = 0; i < d.length; i += 4) m = Math.max(m, Math.abs(d[i])); return m; };

  /* ---------- le micro (10/11, Ahmed : « toujours le micro du smartphone, même s'il est en écouteurs Bluetooth ») ----------
     Dans l'appli : le micro du téléphone, ouvert par l'appli (StudioMicro.java), jamais par getUserMedia : dans la WebView, Chromium
     choisit lui-même le casque Bluetooth comme micro de communication (SCO : 16 kHz mono, et l'instru passe en mode appel).
     Dans un navigateur : l'entrée intégrée, choisie par son nom (StudioCalage.choisirMicroWeb), jamais celle d'un casque. */
  let microNom = lsLire('studio-micro-nom', '');
  const NOMS_MICRO = { telephone: 'le micro du téléphone ✓', bluetooth: '⚠︎ le micro des écouteurs', casque_fil: '⚠︎ le micro du casque', usb: 'un micro USB', autre: 'un autre micro', inconnu: 'le micro du téléphone (voulu)' };
  const montrerMicro = (nom) => { microNom = nom; lsEcrire('studio-micro-nom', nom); montrerRoute(); };
  async function microWeb() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) throw new Error('micro indisponible dans ce navigateur');
    const sans = { echoCancellation: false, noiseSuppression: false, autoGainControl: false, channelCount: 1 };
    const ouvrir = (id) => navigator.mediaDevices.getUserMedia({ audio: id ? { ...sans, deviceId: { exact: id } } : sans });
    const entrees = async () => { try { return await navigator.mediaDevices.enumerateDevices(); } catch (_) { return []; } };
    // les noms ne viennent qu'après l'accord : d'abord la liste ; sans noms, une première ouverture, puis le bon micro
    let choix = C.choisirMicroWeb(await entrees()), flux = choix ? await ouvrir(choix.deviceId).catch(() => null) : null;
    if (!flux) {
      flux = await ouvrir(null);
      choix = C.choisirMicroWeb(await entrees());
      const p = flux.getAudioTracks()[0], actuel = p && p.getSettings ? p.getSettings().deviceId : '';
      if (choix && choix.deviceId !== actuel) { flux.getTracks().forEach(t => t.stop()); flux = await ouvrir(choix.deviceId); }
    }
    const nom = (flux.getAudioTracks()[0] || {}).label || '';
    montrerMicro(nom || 'le micro du navigateur');
    return { genre: 'web', flux, avertir: C.CASQUE.test(nom) ? `⚠︎ Le navigateur n’offre que le micro du casque (« ${nom} ») : la voix sera en qualité téléphone.` : '' };
  }
  async function ouvrirMicro() {
    if (!App) return microWeb();
    let o = {};
    try { o = JSON.parse(App.studioMicroOuvrir()); } catch (_) {}
    if (!o.ok) throw new Error(o.erreur || 'le micro du téléphone ne s’ouvre pas');
    montrerMicro(NOMS_MICRO[o.micro] || NOMS_MICRO.inconnu);
    return { genre: 'appli', o, avertir: !o.micro_voulu ? '⚠︎ Le téléphone ne montre pas son micro : Android choisit.'
      : o.micro === 'bluetooth' ? '⚠︎ Android a pris le micro des écouteurs malgré la demande.' : '' };
  }
  // l'écart des horloges de l'appli et de la page : neuf allers-retours, le plus court
  function horlogeAppli() {
    const m = [];
    for (let k = 0; k < 9; k++) { const avant = performance.now(), horloge = Number(App.studioHorloge()), apres = performance.now(); m.push({ avant, horloge, apres }); }
    return C.decalageHorloge(m);
  }
  // l'enregistreur de l'appli : le son du micro du téléphone, numéroté et horodaté, recalé à la fin sur l'instant où T0 sortait au casque
  function enregistreurAppli(c, ouvert, T0, surNiveau) {
    const h = horlogeAppli(), morceaux = [], stamps = [], sorties = [];
    const repli = { ctx: c.currentTime, perf: performance.now(), sortie_ms: ((c.outputLatency || 0) + (c.baseLatency || 0)) * 1000 };
    let sr = ouvert.sr || 48000, micro = ouvert.micro, erreur = '';
    const tirer = () => {
      let o = null;
      try { o = JSON.parse(App.studioMicroLire()); } catch (_) {}
      if (o && o.ok) {
        sr = o.sr || sr;
        if (o.n > 0) { const x = C.pcmDe(o.b64); morceaux.push({ premier: o.premier, x }); if (surNiveau) surNiveau(crete(x)); }
        if (o.ts_ns > 0) stamps.push({ f: o.ts_f, ns: o.ts_ns, micro: !!o.ts_micro });
        if (o.micro && o.micro !== micro) { micro = o.micro; montrerMicro(NOMS_MICRO[micro] || NOMS_MICRO.inconnu); }
        if (o.erreur) erreur = o.erreur;
      }
      try { const t = c.getOutputTimestamp && c.getOutputTimestamp(); if (t && t.contextTime > 0 && t.performanceTime > 0) sorties.push({ ctx: t.contextTime, perf: t.performanceTime }); } catch (_) {}
    };
    const minuteur = setInterval(tirer, 80);
    return {
      // le retard que le navigateur annonce entre le temps de l'instru et le casque, à cet instant (pour le dire à papa)
      annonce() { const s = C.sortieA(c.currentTime, sorties, null); return s ? Math.round(s.perf - performance.now()) : null; },
      arreter() {
        clearInterval(minuteur); tirer();
        try { App.studioMicroFermer(); } catch (_) {}
        const r = h && C.aligner({ morceaux, stamps, sorties, repli, off: h.off, T0, sr });
        if (!r) throw new Error(erreur || 'le micro du téléphone n’a rien donné');
        return { x: r.x, sr, micro, cale: `${r.sortie}/${r.horodatage}` };
      }
    };
  }
  // l'enregistreur du navigateur : chaque morceau du micro daté sur l'horloge de l'instru ; seul ce qui suit T0 est gardé
  function enregistreur(c, flux, T0, surNiveau) {
    const src = c.createMediaStreamSource(flux), proc = c.createScriptProcessor(TAMPON, 1, 1), muet = c.createGain();
    muet.gain.value = 0;
    const morceaux = [];
    proc.onaudioprocess = (e) => {
      const d = e.inputBuffer.getChannelData(0), t = e.playbackTime;
      if (surNiveau) surNiveau(crete(d));
      if (t + d.length / c.sampleRate <= T0) return;
      morceaux.push(d.slice(Math.max(0, Math.round((T0 - t) * c.sampleRate))));
    };
    src.connect(proc); proc.connect(muet); muet.connect(c.destination);
    return { arreter() { proc.disconnect(); src.disconnect(); flux.getTracks().forEach(t => t.stop()); const n = morceaux.reduce((a, m) => a + m.length, 0), x = new Float32Array(n); let k = 0; for (const m of morceaux) { x.set(m, k); k += m.length; } return x; } };
  }
  // une capture, par l'appli ou par le navigateur : arreter() → { x, sr } où x[0] est l'instant T0 (avant le calage)
  function capter(c, m, T0, surNiveau) {
    if (m.genre === 'appli') return enregistreurAppli(c, m.o, T0, surNiveau);
    const r = enregistreur(c, m.flux, T0, surNiveau);
    return { annonce: () => null, arreter: () => ({ x: r.arreter(), sr: c.sampleRate, micro: microNom }) };
  }
  function clic(c, t, fort = 1) {
    const o = c.createOscillator(), g = c.createGain();
    o.frequency.value = 1500; o.type = 'square';
    g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(0.5 * fort, t + 0.002); g.gain.exponentialRampToValueAtTime(0.0001, t + 0.03);
    o.connect(g); g.connect(c.destination); o.start(t); o.stop(t + 0.04);
  }
  function enWav(x, sr) {
    const b = new ArrayBuffer(44 + x.length * 2), v = new DataView(b);
    const s = (o, t) => { for (let i = 0; i < t.length; i++) v.setUint8(o + i, t.charCodeAt(i)); };
    s(0, 'RIFF'); v.setUint32(4, 36 + x.length * 2, true); s(8, 'WAVE'); s(12, 'fmt '); v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
    v.setUint32(24, sr, true); v.setUint32(28, sr * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true); s(36, 'data'); v.setUint32(40, x.length * 2, true);
    for (let i = 0; i < x.length; i++) v.setInt16(44 + i * 2, Math.max(-1, Math.min(1, x[i])) * 32767, true);
    return new Blob([b], { type: 'audio/wav' });
  }

  /* ---------- le décalage, par sortie ----------
     Ce qu'on entend au casque arrive en retard (le Bluetooth : souvent 150 à 300 ms), et le micro a son propre retard. Dans l'appli,
     la prise est déjà recalée sur ce que le téléphone ANNONCE (l'horodatage du micro, le retard de sortie du navigateur) : le calage
     ne retire que ce qui reste. Dans un navigateur, il retire tout. Mesuré une fois par sortie (des écouteurs, le haut-parleur…),
     gardé par le cockpit, retiré de chaque prise au mix. */
  let route = { cle: App ? 'appli|inconnue' : 'web|défaut', nom: '', casque: false, avertir: '' };
  const NOMS_SORTIE = { haut_parleur: () => 'le haut-parleur du téléphone', bluetooth: (n) => `${n || 'des écouteurs'} (Bluetooth)`,
    bluetooth_appel: (n) => `${n || 'des écouteurs'} (Bluetooth, en mode appel ⚠︎)`, fil: (n) => n || 'un casque filaire', usb: (n) => `${n || 'un casque'} (USB)`,
    ecouteur_telephone: () => 'l’écouteur du téléphone', autre: (n) => n || 'une autre sortie' };
  async function lireRoute() {
    if (App) {
      let o = {};
      try { o = JSON.parse(App.studioSortie()); } catch (_) {}
      const g = NOMS_SORTIE[o.genre] ? o.genre : 'autre';
      route = { cle: `appli|${o.cle || 'inconnue'}`, nom: NOMS_SORTIE[g](o.nom), casque: g !== 'haut_parleur' && g !== 'ecouteur_telephone',
        avertir: o.sco || g === 'bluetooth_appel' || o.mode === 'communication' || o.mode === 'appel'
          ? '⚠︎ Le téléphone est en mode appel : arrête l’appel ou la conversation, sinon l’instru sort en qualité téléphone.' : '' };
    } else {
      let l = '';
      try { const s = (await navigator.mediaDevices.enumerateDevices()).filter(d => d.kind === 'audiooutput'); l = ((s.find(d => d.deviceId === 'default') || s[0] || {}).label || '').replace(/^(Par défaut|Default)\s*-\s*/i, ''); } catch (_) {}
      route = { cle: `web|${l.slice(0, 80) || 'défaut'}`, nom: l || 'la sortie du navigateur', casque: C.CASQUE.test(l), avertir: '' };
    }
    montrerCalage();
    return route;
  }
  const latence = () => Number($('latence').value) || 0;
  function montrerLatence(ms) { $('latence').value = String(Math.round(ms)); $('latenceVal').textContent = `${Math.round(ms) > 0 ? '+' : ''}${Math.round(ms)} ms`; }
  const calageActuel = () => (etat && etat.calages && etat.calages[route.cle]) || null;
  const METHODES = { boucle: 'mesuré écouteur contre le micro', taper: 'mesuré en tapant', main: 'réglé à la main' };
  function montrerRoute() {
    $('route').innerHTML = `🎧 Écoute : <b>${esc(route.nom || '…')}</b> · 🎤 Micro : <b>${esc(microNom || (App ? 'le micro du téléphone' : 'celui du navigateur'))}</b>`
      + (route.avertir ? `<br>${esc(route.avertir)}` : '');
  }
  let estimationWeb = null;
  function montrerCalage() {
    montrerRoute();
    $('calibClic').textContent = route.casque ? '🎧→🎤 Écouteur contre le micro (le plus juste)' : '🔊 Mesurer au haut-parleur';
    const k = calageActuel();
    if (!mesureEnCours) {
      if (k) {
        montrerLatence(k.ms);
        const total = App && Number.isFinite(k.annonce_ms) ? ` Retard de l’écoute : ~${Math.round(k.annonce_ms + k.ms)} ms (${Math.round(k.annonce_ms)} annoncés par le téléphone, déjà comptés).` : '';
        $('calibEtat').textContent = `${METHODES[k.methode] || k.methode}${k.date ? ` le ${date(k.date)}` : ''}`
          + `${Number.isFinite(k.ecart_ms) ? ` : ±${Math.round(k.ecart_ms)} ms, ${k.n}/${k.total}` : ''}${k.avance_ms ? `, ton avance (${Math.round(k.avance_ms)} ms) retirée` : ''}.${total}`;
      } else {
        const e = App ? 0 : estimationWeb;
        if (e === null) { $('latenceVal').textContent = '— ms'; } else montrerLatence(e);
        $('calibEtat').textContent = `Pas encore mesuré pour cette sortie : ${App ? 'seul ce que le téléphone annonce est compté' : 'l’estimation du navigateur sert en attendant'}. Mesure-le une fois.`;
      }
    }
    const tous = Object.entries((etat && etat.calages) || {});
    $('calages').innerHTML = tous.length ? 'Gardés : ' + tous.map(([cle, x]) => `<span class="g${cle === route.cle ? ' ok' : ''}">${esc(x.nom || cle.split('|').pop())} · ${Math.round(x.ms)} ms</span>`).join(' ') : '';
  }
  async function estimation() {
    const c = await contexte();
    return Math.round(((c.outputLatency || 0) + (c.baseLatency || 0) + 0.01 + TAMPON / c.sampleRate) * 1000);
  }
  async function garderCalage(corps) {
    const r = await poster('/api/studio/calage', { cle: route.cle, nom: route.nom, ...corps });
    if (etat) { etat.calages = r.calages; etat.avance = r.avance; }
    montrerCalage();
    return r.calage;
  }
  const attendre = (s) => new Promise(ok => setTimeout(ok, Math.max(0, s) * 1000));
  // une mesure : des clics par le chemin de l'instru, enregistrés par le chemin de la voix. boucle : le clic lui-même revient au micro
  // (le haut-parleur, ou l'écouteur collé au micro) ; taper : papa tape du doigt sur le téléphone en même temps que chaque clic entendu
  let mesureEnCours = false;
  async function mesurer(methode) {
    if (mesureEnCours || rec) return;
    const boucle = methode === 'boucle', boutons = [$('calibClic'), $('calibTaper'), $('rec')];
    mesureEnCours = true; boutons.forEach(b => { b.disabled = true; });
    let montre = 0;
    try {
      const c = await contexte(), avant = (await lireRoute()).cle, casque = route.casque;
      const N = boucle ? 8 : 16, IGNORER = boucle ? 0 : 4, PAS = boucle ? 0.6 : 0.8, ATTENTE = boucle && casque ? 4 : 2;
      $('calibEtat').textContent = boucle ? (casque ? 'Retire un écouteur et colle-le contre le bas du téléphone (le micro), volume fort. Les clics partent dans 4 s ; ne bouge plus.'
        : 'Silence… huit clics, ne bouge pas.') : 'Tape du doigt sur le téléphone (pas dans les mains), net, en même temps que chaque clic que tu entends (les 4 premiers pour te caler).';
      const m = await ouvrirMicro();
      const T1 = c.currentTime + ATTENTE, r = capter(c, m, T1 - 0.5, null);
      // un clic doux 1,5 s avant, hors de la mesure : le premier son peut faire sauter l'horodatage de la sortie (vu dans Chromium, ~25 ms)
      clic(c, T1 - 1.5, 0.15);
      for (let k = 0; k < N; k++) clic(c, T1 + k * PAS, boucle ? 1 : 0.7);
      if (!boucle) { $('taper').textContent = 'Écoute les clics…'; $('taper').hidden = false; }
      montre = setInterval(() => {
        const t = c.currentTime - T1;
        $('decompte').textContent = t < 0 ? String(Math.ceil(-t)) : '';
        if (t >= 0 && !boucle) { const k = Math.min(N, Math.floor(t / PAS) + 1); $('taper').textContent = k <= IGNORER ? `Cale-toi… ${k}/${IGNORER}` : `Tape ! ${k - IGNORER}/${N - IGNORER}`; }
      }, 80);
      await attendre(T1 - c.currentTime + N * PAS + 0.6);
      const annonce = r.annonce(), { x, sr, micro } = r.arreter();
      if ((await lireRoute()).cle !== avant) throw new Error('la sortie a changé pendant la mesure (l’écouteur retiré a renvoyé le son au téléphone ?) : essaie « Taper sur les clics »');
      const res = C.analyserClics(x, sr, { debut: 0.5, pas: PAS, n: N, ignorer: IGNORER, passeBas: boucle ? 0 : 500 });
      const j = C.jugerMesure(res, methode);
      if (!j.ok) throw new Error(`${j.raison}${boucle ? (casque ? ' : colle bien l’écouteur contre le micro du bas, volume à fond' : ' : monte le volume') : ' : recommence, en tapant net sur le téléphone'}`);
      mesureEnCours = false;
      const k = await garderCalage({ methode, ms: res.ms, ecart_ms: res.ecart_ms, n: res.n, total: res.total, annonce_ms: annonce, micro });
      dire(`Décalage gardé pour ${route.nom} : ${k ? Math.round(k.ms) : Math.round(res.ms)} ms.`);
    } catch (e) {
      mesureEnCours = false;
      if (App) try { App.studioMicroFermer(); } catch (_) {}
      $('calibEtat').textContent = `Mesure ratée : ${e.message}`;
    } finally {
      mesureEnCours = false; clearInterval(montre);
      $('taper').hidden = true; $('decompte').textContent = '';
      boutons.forEach(b => { b.disabled = false; });
      $('rec').disabled = !instruChoisie;
    }
  }

  /* ---------- la prise ---------- */
  async function enregistrer() {
    if (rec) return rec.finir();
    if (mesureEnCours) return;
    const f = instruChoisie;
    if (!f) return dire('Choisis d’abord une instru.');
    const bouton = $('rec'); bouton.disabled = true;
    try {
      const c = await contexte();
      dire('Chargement de l’instru…', 0);
      await lireRoute();
      const [tampon, m] = await Promise.all([tamponDe(f), ouvrirMicro()]);
      const kal = calageActuel(), cal = latence(), sortie = route;
      dire([m.avertir, route.avertir, kal ? '' : `Décalage pas encore mesuré pour ${route.nom} : mesure-le pour une prise calée.`].filter(Boolean).join(' '), 9000);
      const T0 = c.currentTime + 3.2;
      for (let k = 3; k >= 1; k--) clic(c, T0 - k, k === 3 ? 0.6 : 0.4);
      const src = c.createBufferSource(); src.buffer = tampon; src.connect(c.destination); src.start(T0);
      const r = capter(c, m, T0, (n) => { $('niveau').style.width = `${Math.min(100, n * 140)}%`; });
      rec = { finir: null };
      bouton.textContent = '■ Arrêter'; bouton.classList.add('actif'); bouton.disabled = false;
      const montre = setInterval(() => {
        const t = c.currentTime - T0;
        $('decompte').textContent = t < 0 ? String(Math.ceil(-t)) : '';
        $('temps').textContent = t < 0 ? 'Prêt…' : `● ${duree(t)} / ${duree(tampon.duration)}`;
      }, 100);
      let fini = false;
      rec.finir = async () => {
        if (fini) return; fini = true;
        clearInterval(montre); try { src.stop(); } catch (_) {}
        let prise;
        try { prise = r.arreter(); } catch (e) { prise = null; $('temps').textContent = `Prise perdue : ${e.message}`; }
        rec = null;
        bouton.textContent = '● Enregistrer'; bouton.classList.remove('actif'); $('decompte').textContent = ''; $('niveau').style.width = '0';
        if (!prise) return;
        const { x, sr, micro } = prise;
        if (x.length < sr) { $('temps').textContent = 'Prise trop courte, rien gardé.'; return; }
        $('temps').textContent = `Envoi de la prise (${duree(x.length / sr)})…`;
        try {
          const q = new URLSearchParams({ instru: f, latence: String(cal), cle: sortie.cle, sortie: sortie.nom, micro: micro || '', methode: kal ? kal.methode : 'estimation' });
          await poster(`/api/studio/prise?${q}`, enWav(x, sr), 'audio/wav');
          $('temps').textContent = `Prise gardée (${micro || 'micro'}, décalage ${cal} ms). Réécoute-la avec l’instru, puis ★ choisis la meilleure.`;
          charger();
        } catch (e) { $('temps').textContent = `Prise non envoyée : ${e.message}`; }
      };
      src.onended = () => rec && rec.finir && rec.finir();
    } catch (e) {
      rec = null; bouton.disabled = false; bouton.textContent = '● Enregistrer'; bouton.classList.remove('actif');
      if (App) try { App.studioMicroFermer(); } catch (_) {}
      dire(/Permission|NotAllowed/i.test(String(e && (e.name || e.message))) ? 'Micro refusé : autorise-le pour le cockpit.' : `Pas d’enregistrement : ${e.message}`);
    }
  }
  // une prise réécoutée avec son instru, calée de sa latence
  let ensemble = null;
  async function ecouterEnsemble(id) {
    if (ensemble) { ensemble.forEach(s => { try { s.stop(); } catch (_) {} }); ensemble = null; return; }
    const p = etat.prises.find(x => x.id === id);
    if (!p || !p.instru_f) return;
    try {
      const c = await contexte(), [i, v] = await Promise.all([tamponDe(p.instru_f), tamponDe(p.f)]);
      const t = c.currentTime + 0.15, lat = Math.max(0, (p.latence_ms || 0) / 1000);
      const a = c.createBufferSource(), b = c.createBufferSource(), g = c.createGain();
      a.buffer = i; b.buffer = v; g.gain.value = 1.6; a.connect(c.destination); b.connect(g); g.connect(c.destination);
      a.start(t); b.start(t, lat);
      ensemble = [a, b];
      b.onended = () => { if (ensemble && ensemble[1] === b) { try { a.stop(); } catch (_) {} ensemble = null; } };
      dire('▶︎ La prise avec l’instru (touche encore pour arrêter).');
    } catch (e) { dire(e.message); }
  }
  let instruJoue = null;
  async function ecouterInstru() {
    if (instruJoue) { try { instruJoue.stop(); } catch (_) {} instruJoue = null; $('ecouterInstru').textContent = '▶︎ Écouter l’instru'; return; }
    try {
      const c = await contexte(), s = c.createBufferSource(); s.buffer = await tamponDe(instruChoisie); s.connect(c.destination); s.start();
      instruJoue = s; $('ecouterInstru').textContent = '■ Arrêter l’instru';
      s.onended = () => { if (instruJoue === s) { instruJoue = null; $('ecouterInstru').textContent = '▶︎ Écouter l’instru'; } };
    } catch (e) { dire(e.message); }
  }

  /* ---------- les gestes ---------- */
  document.addEventListener('click', async (ev) => {
    const b = ev.target.closest('button');
    if (!b) return;
    const d = b.dataset;
    try {
      if (d.lire) return lire(b, d.lire);
      if (d.dl) return telecharger(d.dl);
      if (d.ecouter) return faireEcouter(d.ecouter, d.titre);
      if (d.instru) { b.disabled = true; await poster('/api/studio/instru/extraire', { f: d.instru }); dire('Demucs retire sa voix : l’instru arrive dans la liste.'); return charger(); }
      if (d.ensemble) return ecouterEnsemble(d.ensemble);
      if (d.choisir) { await poster('/api/studio/prise/choisir', { id: d.choisir }); return charger(); }
      if (d.caler) { await poster('/api/studio/prise/regler', { id: d.caler, latence_ms: latence() }); dire(`Calage de la prise : ${latence()} ms.`); return charger(); }
      if (d.effacer) { if (!confirm('Effacer cette prise ?')) return; await poster('/api/studio/prise/effacer', { id: d.effacer }); return charger(); }
      if (b.id === 'arreterEcoute') { await poster('/api/studio/ecouter/arreter', {}); return charger(); }
    } catch (e) { dire(e.message); b.disabled = false; }
  });
  $('rec').addEventListener('click', enregistrer);
  $('ecouterInstru').addEventListener('click', ecouterInstru);
  $('calibClic').addEventListener('click', () => mesurer('boucle'));
  $('calibTaper').addEventListener('click', () => mesurer('taper'));
  $('instru').addEventListener('change', () => { instruChoisie = $('instru').value; lsEcrire('studio-instru', instruChoisie); });
  $('latence').addEventListener('input', () => montrerLatence(latence()));
  $('latence').addEventListener('change', () => garderCalage({ methode: 'main', ms: latence() }).catch((e) => dire(`Pas gardé : ${e.message}`)));
  const curseur = (id, fmt) => { const m = () => { $(`${id}Val`).textContent = fmt(Number($(id).value)); }; $(id).addEventListener('input', m); m(); };
  curseur('voix', v => `${v > 0 ? '+' : ''}${v} dB`); curseur('reverb', v => `${v} %`); curseur('echo', v => `${v} %`);
  $('mixer').addEventListener('click', async () => {
    if (!priseChoisie) return;
    $('mixer').disabled = true;
    try {
      await poster('/api/studio/mixer', { prise: priseChoisie.id, autotune: $('autotune').checked, debruitage: $('debruitage').checked, voix_db: Number($('voix').value),
        reverb: Number($('reverb').value) / 100, echo: Number($('echo').value) / 100, titre: $('mixTitre').value });
      dire('Hakim mixe et masterise… (une à deux minutes)');
      charger();
    } catch (e) { dire(`Pas de mix : ${e.message}`); $('mixer').disabled = false; }
  });
  $('dEnvoyer').addEventListener('click', async () => {
    const style = $('dStyle').value.trim();
    if (!style) return dire('Un style, par exemple trap.');
    $('dEnvoyer').disabled = true;
    try {
      const r = await poster('/api/studio/instru/demander', { style, bpm: Number($('dBpm').value) || 0, duree_s: Number($('dDuree').value) || 60 });
      dire(`Hakim compose « ${r.titre || style} »… quelques minutes.`); $('demande').open = false; charger();
    } catch (e) { dire(`Refusé : ${e.message}`); } finally { $('dEnvoyer').disabled = false; }
  });
  async function envoyerFichier(input, chemin, apres) {
    const f = input.files && input.files[0];
    input.value = '';
    if (!f) return;
    if (f.size > 80 * 1024 * 1024) return dire('Trop lourd (80 Mo au plus).');
    dire(`Envoi de « ${f.name} »…`, 0);
    try { const r = await poster(`${chemin}?nom=${encodeURIComponent(f.name)}`, f, f.type || 'application/octet-stream'); apres(r, f); charger(); }
    catch (e) { dire(`Refusé : ${e.message}`); }
  }
  $('importInstru').addEventListener('change', () => envoyerFichier($('importInstru'), '/api/studio/importer', (r) => { instruChoisie = r.f; lsEcrire('studio-instru', r.f); dire('Instru importée.'); }));
  $('fichierEcoute').addEventListener('change', () => envoyerFichier($('fichierEcoute'), '/api/studio/ecouter/fichier', (r, f) => dire(`Hakim écoute « ${f.name} »…`)));

  // (10/11) la sortie où papa écoute, et son calage gardé ; dans un navigateur, l'estimation attend un premier geste (l'AudioContext)
  lireRoute();
  document.addEventListener('visibilitychange', () => { if (!document.hidden && !rec && !mesureEnCours) lireRoute(); });
  if (navigator.mediaDevices && navigator.mediaDevices.addEventListener) navigator.mediaDevices.addEventListener('devicechange', () => { if (!rec && !mesureEnCours) lireRoute(); });
  if (App) setInterval(() => { if (!document.hidden && !rec && !mesureEnCours) lireRoute(); }, 5000);
  else document.addEventListener('pointerdown', async function une() { document.removeEventListener('pointerdown', une); estimationWeb = await estimation(); montrerCalage(); }, { once: true });
  window.addEventListener('pagehide', () => { if (App) try { App.studioMicroFermer(); } catch (_) {} });
  // (13/11) le multipiste (studio-pistes.js) enregistre papa avec la même machinerie : le même micro, la même horloge, le même calage
  window.StudioAudio = { contexte, tamponDe, ouvrirMicro, capter, enWav, clic, lireRoute, route: () => route, latence, calageActuel, poster, dire, duree,
    occupe: () => !!rec || mesureEnCours, recharger: () => charger() };
  charger();
})();
