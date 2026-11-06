/* (06/11) la page Studio : ses sons, lui faire écouter, t'enregistrer (décompte, latence compensée), le mix par Hakim.
   L'enregistrement : un seul AudioContext pour l'instru et le micro ; chaque morceau du micro est daté sur la même horloge que l'instru
   (playbackTime), on garde ce qui suit le départ de l'instru (T0). Le retard qui reste (sortie du casque + entrée du micro + le tampon)
   est la LATENCE, mesurée une fois (clic ou en tapant) et retirée au mix. Le micro s'ouvre SANS effets (sans annulation d'écho) :
   c'est ce qui garde le son dans le casque Bluetooth (appli 1.83) et la voix intacte. */
(() => {
  const $ = (id) => document.getElementById(id);
  const H = () => ({ 'X-Jeton': window.jeton() });
  const TAMPON = 2048;
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
      + `<span>${esc(p.titre)}</span><span class="meta">${date(p.ts)} · ${duree(p.duree_s)} · calage ${Math.round(p.latence_ms || 0)} ms</span></div>`
      + `<div class="gestes"><button type="button" data-ensemble="${esc(p.id)}">▶︎ Avec l’instru</button><button type="button" data-lire="${esc(p.f)}">Voix seule</button>`
      + `<button type="button" data-choisir="${esc(p.id)}"${p.choisie ? ' disabled' : ''}>★ Choisir</button>`
      + `<button type="button" data-caler="${esc(p.id)}" title="Appliquer le calage du curseur à cette prise">⇆ Calage actuel</button>`
      + `<button type="button" data-effacer="${esc(p.id)}" aria-label="Effacer la prise">🗑</button></div></div>`).join('') : '<div class="vide">Aucune prise.</div>';
    $('mixer').disabled = !priseChoisie;
    $('mixPrise').textContent = priseChoisie ? `Prise choisie : ${priseChoisie.titre} (${duree(priseChoisie.duree_s)}, calage ${Math.round(priseChoisie.latence_ms || 0)} ms)` : 'Choisis une prise (★) au-dessus.';
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
  async function micro() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) throw new Error('micro indisponible dans ce navigateur');
    return navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false, channelCount: 1 } });
  }
  // l'enregistreur : chaque morceau du micro daté sur l'horloge de l'instru ; seul ce qui suit T0 est gardé
  function enregistreur(c, flux, T0, surNiveau) {
    const src = c.createMediaStreamSource(flux), proc = c.createScriptProcessor(TAMPON, 1, 1), muet = c.createGain();
    muet.gain.value = 0;
    const morceaux = [];
    proc.onaudioprocess = (e) => {
      const d = e.inputBuffer.getChannelData(0), t = e.playbackTime;
      let crete = 0; for (let i = 0; i < d.length; i += 4) crete = Math.max(crete, Math.abs(d[i]));
      if (surNiveau) surNiveau(crete);
      if (t + d.length / c.sampleRate <= T0) return;
      morceaux.push(d.slice(Math.max(0, Math.round((T0 - t) * c.sampleRate))));
    };
    src.connect(proc); proc.connect(muet); muet.connect(c.destination);
    return { arreter() { proc.disconnect(); src.disconnect(); flux.getTracks().forEach(t => t.stop()); const n = morceaux.reduce((a, m) => a + m.length, 0), x = new Float32Array(n); let k = 0; for (const m of morceaux) { x.set(m, k); k += m.length; } return x; } };
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

  /* ---------- la latence ---------- */
  const latence = () => Number($('latence').value) || 0;
  function montrerLatence(ms, source, garder = true) {
    $('latence').value = String(Math.round(ms)); $('latenceVal').textContent = `${Math.round(ms)} ms`;
    if (garder) lsEcrire('studio-latence', String(Math.round(ms)));
    if (source) { lsEcrire('studio-latence-source', source); $('calibEtat').textContent = `Calage : ${Math.round(ms)} ms (${source}).`; }
  }
  async function estimation() {
    const c = await contexte();
    return Math.round(((c.outputLatency || 0) + (c.baseLatency || 0) + 0.01 + TAMPON / c.sampleRate) * 1000);
  }
  // au clic : le haut-parleur (ou l'écouteur) près du micro ; huit clics, le retard de chacun jusqu'au micro, la médiane
  async function calibrerClic() {
    const b = $('calibClic'); b.disabled = true;
    try {
      const c = await contexte(), flux = await micro();
      $('calibEtat').textContent = 'Silence… huit clics, ne bouge pas.';
      const T0 = c.currentTime + 0.6, PAS = 0.6, N = 8;
      const r = enregistreur(c, flux, T0 - 0.3);
      for (let k = 0; k < N; k++) clic(c, T0 + k * PAS);
      await new Promise(ok => setTimeout(ok, (0.6 + N * PAS + 0.6) * 1000));
      const x = r.arreter(), sr = c.sampleRate, debut = Math.round(0.3 * sr);
      const bruit = Math.sqrt(x.subarray(0, debut).reduce((a, v) => a + v * v, 0) / Math.max(1, debut));
      const seuil = Math.max(0.02, bruit * 6), retards = [];
      for (let k = 0; k < N; k++) {
        const a = debut + Math.round(k * PAS * sr), z = Math.min(x.length, a + Math.round(0.5 * sr));
        for (let i = a; i < z; i++) if (Math.abs(x[i]) > seuil) { retards.push((i - a) / sr * 1000); break; }
      }
      if (retards.length < 5) throw new Error(`le micro n’a entendu que ${retards.length} clics sur 8 : rapproche le haut-parleur, ou essaie « Taper en rythme »`);
      retards.sort((p, q) => p - q);
      montrerLatence(retards[Math.floor(retards.length / 2)], `mesurée au clic, ${retards.length}/8`);
    } catch (e) { $('calibEtat').textContent = `Mesure ratée : ${e.message}`; }
    finally { b.disabled = false; }
  }
  // en tapant : huit clics dans le casque, tu tapes dessus ; ton retard de sortie, plus l'entrée estimée du micro
  async function calibrerTaper() {
    const c = await contexte(), b = $('taper'), PAS = 0.75, N = 10;
    let entree = 0.01;
    try { const f = await micro(); const s = f.getAudioTracks()[0].getSettings(); entree = Number(s.latency) || 0.01; f.getTracks().forEach(t => t.stop()); } catch (_) {}
    const T0 = c.currentTime + 1, frappes = [];
    for (let k = 0; k < N; k++) clic(c, T0 + k * PAS);
    b.hidden = false; $('calibEtat').textContent = 'Tape le bouton en même temps que chaque clic que tu entends (les deux premiers pour te caler).';
    const taper = () => frappes.push(c.currentTime);
    b.addEventListener('pointerdown', taper);
    await new Promise(ok => setTimeout(ok, (1 + N * PAS + 0.5) * 1000));
    b.removeEventListener('pointerdown', taper); b.hidden = true;
    const ecarts = frappes.map(t => { const k = Math.round((t - T0) / PAS); return k >= 2 && k < N ? (t - (T0 + k * PAS)) * 1000 : null; }).filter(v => v !== null && v > -150 && v < 600);
    if (ecarts.length < 4) { $('calibEtat').textContent = 'Pas assez de frappes : recommence.'; return; }
    ecarts.sort((p, q) => p - q);
    montrerLatence(Math.max(0, ecarts[Math.floor(ecarts.length / 2)] + (entree + TAMPON / c.sampleRate) * 1000), `en tapant, ${ecarts.length} frappes`);
  }

  /* ---------- la prise ---------- */
  async function enregistrer() {
    if (rec) return rec.finir();
    const f = instruChoisie;
    if (!f) return dire('Choisis d’abord une instru.');
    const bouton = $('rec'); bouton.disabled = true;
    try {
      const c = await contexte();
      dire('Chargement de l’instru…', 0);
      const [tampon, flux] = await Promise.all([tamponDe(f), micro()]);
      dire('', 1);
      const T0 = c.currentTime + 3.2;
      for (let k = 3; k >= 1; k--) clic(c, T0 - k, k === 3 ? 0.6 : 0.4);
      const src = c.createBufferSource(); src.buffer = tampon; src.connect(c.destination); src.start(T0);
      const r = enregistreur(c, flux, T0, (n) => { $('niveau').style.width = `${Math.min(100, n * 140)}%`; });
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
        const x = r.arreter(); rec = null;
        bouton.textContent = '● Enregistrer'; bouton.classList.remove('actif'); $('decompte').textContent = ''; $('niveau').style.width = '0';
        if (x.length < c.sampleRate) { $('temps').textContent = 'Prise trop courte, rien gardé.'; return; }
        $('temps').textContent = `Envoi de la prise (${duree(x.length / c.sampleRate)})…`;
        try {
          await poster(`/api/studio/prise?instru=${encodeURIComponent(f)}&latence=${latence()}`, enWav(x, c.sampleRate), 'audio/wav');
          $('temps').textContent = 'Prise gardée. Réécoute-la avec l’instru, puis ★ choisis la meilleure.';
          charger();
        } catch (e) { $('temps').textContent = `Prise non envoyée : ${e.message}`; }
      };
      src.onended = () => rec && rec.finir && rec.finir();
    } catch (e) {
      rec = null; bouton.disabled = false; bouton.textContent = '● Enregistrer'; bouton.classList.remove('actif');
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
  $('calibClic').addEventListener('click', calibrerClic);
  $('calibTaper').addEventListener('click', calibrerTaper);
  $('instru').addEventListener('change', () => { instruChoisie = $('instru').value; lsEcrire('studio-instru', instruChoisie); });
  $('latence').addEventListener('input', () => montrerLatence(latence(), 'réglée à la main'));
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

  // la latence gardée par appareil ; sinon l'estimation du navigateur
  const gardee = lsLire('studio-latence', null);
  if (gardee !== null) { montrerLatence(Number(gardee)); $('calibEtat').textContent = `Calage gardé : ${gardee} ms (${lsLire('studio-latence-source', 'mesuré')}).`; }
  else { $('latenceVal').textContent = '— ms'; $('calibEtat').textContent = 'Pas encore mesurée sur cet appareil : l’estimation du navigateur sert en attendant.';
    // l'estimation sans ouvrir d'AudioContext tout de suite (le navigateur l'exige après un geste) : au premier geste
    document.addEventListener('pointerdown', async function une() { document.removeEventListener('pointerdown', une); if (lsLire('studio-latence', null) === null) montrerLatence(await estimation(), null, false); }, { once: true }); }
  charger();
})();
