/* (14/11, Ahmed : « un retour de voix au casque pendant que j'enregistre, avec des préréglages et de l'autotune comme je veux, de façon
   par défaut ») LE RETOUR CASQUE dans la page Studio : la voix de papa traitée au casque, la prise restant brute.
   - Mac (navigateur) : un AudioWorklet (studio-retour-worklet.js : la chaîne de studio-retour-dsp.js), le contexte audio de la page au plus
     bas (latencyHint 0), la sortie dirigée vers la carte son quand le micro est la carte ;
   - téléphone (appli 2.00 et plus) : le moteur natif de l'appli (AAudio, la même chaîne en C) : window.HakimApp.studioRetour* ;
   - jamais par Bluetooth (150 ms et plus), jamais par un haut-parleur (larsen) ;
   - les préréglages, « Mes réglages », et le réglage par défaut PARTAGÉ (le cockpit : /api/studio/retour) ;
   - la latence MESURÉE : un clic par la sortie du retour, rattrapé par son entrée (casque collé au micro) ; cible ≤ 15 ms (Mac), ≤ 25 ms
     (téléphone) ; au-dessus, la page le dit et propose le retour direct (le bouton MIX de la carte) ;
   - ce qu'il entend part avec la prise (pourPrise) : son autotune devient celui du mix. */
(() => {
  const $ = (id) => document.getElementById(id);
  const A = () => window.StudioAudio;
  const D = window.RetourDSP, C = window.StudioCalage;
  const H = () => ({ 'X-Jeton': window.jeton() });
  const App = window.HakimApp && typeof window.HakimApp.studioMicroOuvrir === 'function' ? window.HakimApp : null;
  const Natif = App && typeof App.studioRetourAllumer === 'function' ? App : null;
  const lsLire = (k, d) => { try { const v = localStorage.getItem(k); return v === null ? d : v; } catch (_) { return d; } };
  const lsEcrire = (k, v) => { try { localStorage.setItem(k, v); } catch (_) {} };
  const CIBLE_MS = App ? 25 : 15;
  // une sortie Bluetooth (jamais de retour logiciel : 150 ms et plus) ; les haut-parleurs (le retour y ferait un larsen)
  const BLUETOOTH = /bluetooth|airpods|\bbuds\b|galaxy buds|beats|bose|wh-1000|wf-1000|jbl|soundcore|powerbeats|jabra|\bbt\b|hands[- ]?free|mains[- ]libres/i;
  const HAUT_PARLEURS = /haut-parleur|speaker|built-?in output|sortie int[ée]gr[ée]e/i;
  const TONS = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
  const NOMS_TONS = { C: 'Do', 'C#': 'Do#', D: 'Ré', 'D#': 'Ré#', E: 'Mi', F: 'Fa', 'F#': 'Fa#', G: 'Sol', 'G#': 'Sol#', A: 'La', 'A#': 'La#', B: 'Si' };
  const nomTon = (t) => { const m = String(t || '').match(/^([A-G]#?)\s+(major|minor)$/); return m ? `${NOMS_TONS[m[1]]} ${m[2] === 'minor' ? 'mineur' : 'majeur'}` : ''; };

  const s = { reglages: D.preset(D.DEFAUT), defaut: null, mesures: {}, allume: false, moteur: null, contexte: { genre: '', tonalite: '', diap_cents: 0, tempo: 0, f: '' },
    tonAuto: '', diapAuto: 0, dernier: null, minuteur: 0, mesure: false };

  /* ---------- les réglages ---------- */
  function vecteur() { return D.vecteur(s.reglages, { tempo: s.contexte.tempo, diap_cents: s.contexte.diap_cents, tonalite: tonaliteVue() }); }
  const tonaliteVue = () => (s.reglages.autotune.tonalite === 'chromatique' ? '' : s.reglages.autotune.tonalite || s.contexte.tonalite || '');
  function envoyer() {
    const v = vecteur();
    if (s.moteur && s.moteur.node) s.moteur.node.port.postMessage({ vecteur: v });
    if (s.moteur && s.moteur.natif) try { Natif.studioRetourRegler(JSON.stringify(v)); } catch (_) {}
  }
  function choisirPreset(nom) {
    s.reglages = nom === 'perso' && s.defaut ? D.borner({ ...s.defaut, preset: 'perso' }) : D.preset(nom);
    afficher(); envoyer();
  }
  function changer(f) {                                   // un réglage touché à la main : « Mes réglages » (perso)
    f(s.reglages);
    s.reglages = D.borner({ ...s.reglages, preset: 'perso' });
    afficher(); envoyer();
  }
  function afficher() {
    const r = s.reglages, a = r.autotune;
    $('rtPreset').innerHTML = Object.entries(D.PRESETS).map(([k, p]) => `<option value="${k}"${r.preset === k ? ' selected' : ''}>${esc(p.nom)}</option>`).join('')
      + `<option value="perso"${r.preset === 'perso' ? ' selected' : ''}>Mes réglages${s.defaut ? '' : ' (pas encore gardés)'}</option>`;
    $('rtAt').value = a.niveau;
    const auto = s.contexte.tonalite ? `auto : ${nomTon(s.contexte.tonalite) || s.contexte.tonalite} (${s.contexte.genre === 'projet' ? 'le projet' : 'l’instru'})` : 'auto (l’instru ou le projet)';
    $('rtTon').innerHTML = `<option value="">${esc(auto)}</option><option value="chromatique">les 12 demi-tons</option>`
      + TONS.flatMap(t => ['minor', 'major'].map(m => `<option value="${t} ${m}">${nomTon(`${t} ${m}`)}</option>`)).join('');
    $('rtTon').value = a.tonalite || '';
    const P = D.NIVEAUX[a.niveau];
    $('rtVitesse').value = a.vitesse_ms === null ? (P ? P.retune_ms : '') : a.vitesse_ms;
    $('rtForce').value = a.force === null ? (P ? Math.round(P.force * 100) : '') : Math.round(a.force * 100);
    $('rtVitesse').disabled = $('rtForce').disabled = $('rtTon').disabled = !a.niveau;
    $('rtVolume').value = String(r.volume_db); $('rtVolumeVal').textContent = `${r.volume_db > 0 ? '+' : ''}${r.volume_db} dB`;
    for (const e of document.querySelectorAll('[data-rt]')) {
      const [g, k] = e.dataset.rt.split('.'), v = k ? r[g][k] : r[g];
      if (e.type === 'checkbox') e.checked = !!v; else e.value = String(v);
    }
    const niv = D.niveauMix(r);
    $('rtMixDit').textContent = niv ? `Au mix : autotune ${niv === 'fort' ? 'fort' : 'léger'}${tonaliteVue() ? `, ${nomTon(tonaliteVue()) || tonaliteVue()}` : ''}${a.force !== null || a.vitesse_ms !== null ? ' (le niveau du mix le plus proche de tes réglages)' : ''}.`
      : 'Au mix : sans autotune (comme au casque).';
    $('rtDefaut').textContent = s.defaut ? `Ton réglage par défaut : ${D.PRESETS[s.defaut.preset] ? D.PRESETS[s.defaut.preset].nom : 'Mes réglages'}, partagé par le téléphone et le Mac.` : 'Pas encore de réglage par défaut : « Rap propre » en attendant.';
    montrerLatence();
  }

  /* ---------- où ça sort, et pourquoi on refuse ---------- */
  function refus(route) {
    const nom = (route && route.nom) || '';
    if (App) {
      const g = String((route && route.cle) || '').replace(/^appli\|/, '').split(':')[0];
      if (g === 'bluetooth' || g === 'bluetooth_appel') return `Ta sortie est Bluetooth (${nom}) : 150 ms et plus de retard, le retour logiciel est refusé. Branche ton casque sur la carte son.`;
      if (g === 'haut_parleur' || g === 'ecouteur_telephone') return 'Le son sort par le haut-parleur du téléphone : le retour ferait un larsen. Branche un casque (sur la carte son).';
      return '';
    }
    if (BLUETOOTH.test(nom)) return `Ta sortie est Bluetooth (« ${nom} ») : 150 ms et plus de retard, le retour logiciel est refusé. Branche ton casque sur la carte son.`;
    if (HAUT_PARLEURS.test(nom) && !C.CASQUE.test(nom)) return `Le son sort par « ${nom} » : le retour ferait un larsen. Branche un casque (sur la carte son).`;
    return '';
  }
  // dans le navigateur : quand le micro est la carte, la sortie aussi (son casque y est branché), jamais les haut-parleurs du Mac
  async function sortieVersCarte(c, m) {
    if (!m.carte || typeof c.setSinkId !== 'function') return;
    let l = [];
    try { l = (await navigator.mediaDevices.enumerateDevices()).filter(d => d.kind === 'audiooutput' && d.deviceId && d.deviceId !== 'default' && d.deviceId !== 'communications'); } catch (_) {}
    const base = (t) => String(t || '').replace(/\s*\([0-9a-f]{4}:[0-9a-f]{4}\)\s*$/i, '').replace(/^(Par défaut|Default)\s*-\s*/i, '').trim().toLowerCase();
    const voulu = l.find(d => base(d.label) === base(m.nom)) || l.find(d => C.estInterface(d.label) && !C.CASQUE.test(d.label));
    if (voulu && c.sinkId !== voulu.deviceId) { try { await c.setSinkId(voulu.deviceId); } catch (_) {} }
  }

  /* ---------- allumer, éteindre ---------- */
  let modules = null;
  function chargerModules(c) {
    if (!modules || modules.c !== c) modules = { c, p: (async () => {
      for (const f of ['/studio-calage.js', '/studio-retour-dsp.js', '/studio-retour-worklet.js']) await c.audioWorklet.addModule(f);
    })() };
    return modules.p;
  }
  async function allumer() {
    if (s.allume || s.attente) return;
    const a = A();
    if (!a) return;
    if (App && !Natif) return dire('Le retour casque demande l’appli 2.00 : mets-la à jour.');
    if (a.occupe()) return dire('Pas pendant une prise ou une mesure : allume le retour avant.');
    s.attente = true; $('rtAllumer').disabled = true;
    try {
      if (Natif) {
        const route = await a.lireRoute(), non = refus(route);
        if (non) throw new Error(non);
        let o = {};
        try { o = JSON.parse(Natif.studioRetourAllumer(JSON.stringify(vecteur()))); } catch (_) {}
        if (!o.ok) throw new Error(o.erreur || 'le retour ne s’ouvre pas');
        s.moteur = { natif: true, o };
      } else {
        const c = await a.contexte();
        if (!c.audioWorklet || typeof AudioWorkletNode === 'undefined') throw new Error('ce navigateur n’a pas d’AudioWorklet (essaie Chrome)');
        const m = await a.ouvrirMicro();
        await sortieVersCarte(c, m);
        const route = await a.lireRoute(), non = refus(route);
        if (non) { m.flux.getTracks().forEach(t => t.stop()); throw new Error(non); }
        await chargerModules(c);
        const node = new AudioWorkletNode(c, 'retour-voix', { numberOfInputs: 1, numberOfOutputs: 1, outputChannelCount: [2], channelCount: 2,
          channelCountMode: 'explicit', channelInterpretation: 'discrete', processorOptions: { vecteur: vecteur(), canal: Number(lsLire('studio-canal', '0')) || 0 } });
        const src = c.createMediaStreamSource(m.flux);
        src.connect(node); node.connect(c.destination);
        node.port.onmessage = (e) => recu(e.data || {});
        s.moteur = { node, src, flux: m.flux, m };
      }
      s.allume = true; lsEcrire('studio-retour-allume', '1');
      $('rtAllumer').textContent = '🎧 Retour allumé (toucher pour éteindre)'; $('rtAllumer').setAttribute('aria-pressed', 'true'); $('rtAllumer').classList.add('actif');
      $('rtEtat').textContent = 'Ta voix est dans le casque. Tourne le MIX de la carte à fond vers DAW.';
      if (s.moteur.natif) s.minuteur = setInterval(lireNatif, 150);
      montrerLatence();
    } catch (e) {
      eteindre(true);
      $('rtEtat').textContent = `Retour éteint : ${e.message}`;
    } finally { s.attente = false; $('rtAllumer').disabled = false; }
  }
  function eteindre(silence) {
    const m = s.moteur;
    s.moteur = null; s.allume = false; clearInterval(s.minuteur);
    if (m && m.node) { try { m.node.port.postMessage({ arreter: true }); m.src.disconnect(); m.node.disconnect(); } catch (_) {} try { m.flux.getTracks().forEach(t => t.stop()); } catch (_) {} }
    if (m && m.natif) try { Natif.studioRetourEteindre(); } catch (_) {}
    if (!silence) lsEcrire('studio-retour-allume', '0');
    $('rtAllumer').textContent = '🎧 Allumer le retour'; $('rtAllumer').setAttribute('aria-pressed', 'false'); $('rtAllumer').classList.remove('actif');
    $('rtNiveau').style.width = '0';
    if (!silence) $('rtEtat').textContent = 'Retour éteint.';
  }
  // ce que dit la chaîne toutes les ~100 ms : le niveau, la hauteur, la correction, la latence de l'algorithme, l'entrée de la carte
  function recu(m) {
    if (m.mesure) return finirMesure(m.mesure);
    if (!m.etat) return;
    s.dernier = m;
    $('rtNiveau').style.width = `${Math.min(100, (m.niveau || 0) * 140)}%`;
    if (s.mesure || Date.now() < (s.garderMessage || 0)) return;        // le résultat d'une mesure reste lisible 8 s
    const e = m.etat, l = m.latence || {};
    const at = s.reglages.autotune.niveau;
    $('rtEtat').textContent = `Ta voix est dans le casque${m.canaux > 1 && m.canal > 0 ? ` (entrée ${m.canal} de la carte)` : ''}.`
      + (at ? (e.voise ? ` Note ${nomNote(e.note)}, correction ${Math.round(e.correction_cents)} cents.` : ' (Autotune prêt.)') : '')
      + ` Autotune : +${(l.moyenne_ms || 0).toFixed(1)} ms.`;
  }
  const nomNote = (n) => (Number.isFinite(n) ? `${['do', 'do#', 'ré', 'ré#', 'mi', 'fa', 'fa#', 'sol', 'sol#', 'la', 'la#', 'si'][((n % 12) + 12) % 12]}${Math.floor(n / 12) - 1}` : '—');
  function lireNatif() {
    let o = null;
    try { o = JSON.parse(Natif.studioRetourEtat()); } catch (_) {}
    if (!o) return;
    if (o.mesure) { try { o.mesure.x = C.pcmDe(o.mesure.b64); } catch (_) { o.mesure = null; } }
    if (o.mesure && o.mesure.x) { finirMesure(o.mesure); return; }
    if (o.erreur || !o.allume) { eteindre(true); $('rtEtat').textContent = `Retour coupé${o.erreur ? ` : ${o.erreur}` : ' (l’appli l’a fermé)'}`; return; }
    recu({ etat: { voise: !!o.voise, note: o.note, correction_cents: o.correction_cents || 0 }, latence: { moyenne_ms: o.algo_ms || 0 }, niveau: o.niveau || 0, canal: o.canal || 0, canaux: o.canaux || 0 });
  }

  /* ---------- la latence, mesurée ---------- */
  const cleSortie = () => (A() ? A().route().cle : '');
  function montrerLatence() {
    const k = s.mesures[cleSortie()], el = $('rtLatence');
    const algo = s.reglages.autotune.niveau && s.dernier ? (s.dernier.latence || {}).moyenne_ms || 0 : 0;
    if (!k) { el.innerHTML = `Pas encore mesurée pour cette sortie (cible : ${CIBLE_MS} ms au plus). Mesure-la une fois.`; return; }
    const tot = k.ms + algo, ok = tot <= CIBLE_MS;
    el.innerHTML = `<b>retour : ${Math.round(tot)} ms ${ok ? '✓' : '✗'}</b> (${esc(k.nom || 'cette sortie')}${algo ? `, dont autotune ~${algo.toFixed(1)} ms` : ''}, ±${Math.round(k.ecart_ms || 0)} ms)`
      + (ok ? '' : `<br>⚠︎ Au-dessus de ${CIBLE_MS} ms, tu risques de rapper en retard sur ta propre voix. Pour rapper sur le temps : éteins le retour logiciel et prends le retour direct de la carte (le bouton MIX vers INPUT, sans effet).${App ? '' : ' Plus tard, un petit assistant natif CoreAudio sur le Mac pourrait descendre plus bas.'}`);
  }
  async function mesurer() {
    if (!s.allume) await allumer();
    if (!s.allume || s.mesure) return;
    s.mesure = true; $('rtMesurer').disabled = true;
    $('rtEtat').textContent = 'Mesure : retire le casque de tes oreilles, colle un écouteur contre le micro, et ne bouge plus (huit clics)…';
    const n = 8, pas = 0.3;
    try {
      if (s.moteur.natif) { const o = JSON.parse(Natif.studioRetourMesurer(JSON.stringify({ n, pas, fort: 0.3 })) || '{}'); if (o.ok === false) throw new Error(o.erreur || 'mesure refusée'); }
      else s.moteur.node.port.postMessage({ mesure: { n, pas, fort: 0.3 } });
      s.mesureFin = setTimeout(() => { if (s.mesure) { s.mesure = false; $('rtMesurer').disabled = false; $('rtEtat').textContent = 'Mesure ratée : rien n’est revenu.'; } }, (0.5 + n * pas + 3) * 1000);
    } catch (e) { s.mesure = false; $('rtMesurer').disabled = false; $('rtEtat').textContent = `Mesure ratée : ${e.message}`; }
  }
  async function finirMesure(m) {
    clearTimeout(s.mesureFin);
    s.mesure = false; $('rtMesurer').disabled = false;
    const r = C.analyserClics(m.x, m.sr, { debut: m.debut, pas: m.pas, n: m.n, ignorer: 0 }), j = C.jugerMesure(r, 'boucle');
    s.garderMessage = Date.now() + 8000;
    if (!j.ok) { $('rtEtat').textContent = `Mesure ratée : ${j.raison} : colle bien l’écouteur contre le micro, volume moyen.`; return; }
    const route = A().route();
    try {
      const rep = await fetch('/api/studio/retour/mesure', { method: 'POST', headers: { ...H(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ cle: route.cle, nom: route.nom, ms: r.ms, ecart_ms: r.ecart_ms, n: r.n, total: r.total, plateforme: App ? 'appli' : 'web' }) });
      const o = await rep.json().catch(() => ({}));
      if (o.mesures) s.mesures = o.mesures;
    } catch (_) { s.mesures[route.cle] = { ms: r.ms, ecart_ms: r.ecart_ms, n: r.n, total: r.total, nom: route.nom }; }
    $('rtEtat').textContent = `Mesuré : ${r.ms} ms entre la sortie et le micro (${r.n}/${r.total} clics, ±${r.ecart_ms} ms). Remets ton casque.`;
    montrerLatence();
  }

  /* ---------- le contexte (la tonalité et le tempo du morceau), la prise ---------- */
  async function contexte(o) {
    const deja = o.genre === 'instru' && o.f && s.contexte.f === o.f && s.contexte.tonalite ? s.contexte : null;   // la même instru : déjà trouvée
    s.contexte = { genre: o.genre || '', tonalite: o.tonalite || (deja ? deja.tonalite : ''), diap_cents: Number(o.diap_cents) || (deja ? deja.diap_cents : 0),
      tempo: Number(o.tempo) || 0, f: o.f || '' };
    if (o.genre === 'instru' && o.f && !o.tonalite && !deja) {
      const f = o.f;
      try {
        const r = await fetch(`/api/studio/tonalite?f=${encodeURIComponent(f)}`, { headers: H() }), x = await r.json().catch(() => ({}));
        if (x.ok && s.contexte.f === f) { s.contexte.tonalite = x.tonalite || ''; s.contexte.diap_cents = Number(x.diap_cents) || 0; }
      } catch (_) {}
    }
    afficher(); envoyer();
  }
  /** Ce qui part avec une prise (son .json : retour) : '' quand le retour est éteint. */
  function pourPrise() {
    if (!s.allume) return '';
    const k = s.mesures[cleSortie()];
    return JSON.stringify({ allume: true, preset: s.reglages.preset, reglages: s.reglages, niveau_mix: D.niveauMix(s.reglages), tonalite: tonaliteVue(),
      diap_cents: s.contexte.diap_cents, latence_ms: k ? k.ms : null, algo_ms: s.dernier ? (s.dernier.latence || {}).moyenne_ms : null,
      plateforme: App ? 'appli' : 'web', garder_autotune: $('rtGarderAt').checked });
  }
  const dire = (t) => (A() ? A().dire(t, 9000) : null);

  /* ---------- les gestes ---------- */
  $('rtAllumer').addEventListener('click', () => {
    if (s.allume && A() && A().occupe()) return dire('Pas pendant une prise : le retour reste allumé jusqu’à la fin.');
    return s.allume ? eteindre() : allumer();
  });
  $('rtPreset').addEventListener('change', () => choisirPreset($('rtPreset').value));
  $('rtAt').addEventListener('change', () => changer(r => { r.autotune = { ...r.autotune, niveau: $('rtAt').value, vitesse_ms: null, force: null }; }));
  $('rtTon').addEventListener('change', () => changer(r => { r.autotune.tonalite = $('rtTon').value; }));
  $('rtVitesse').addEventListener('change', () => changer(r => { r.autotune.vitesse_ms = $('rtVitesse').value === '' ? null : Number($('rtVitesse').value); }));
  $('rtForce').addEventListener('change', () => changer(r => { r.autotune.force = $('rtForce').value === '' ? null : Number($('rtForce').value) / 100; }));
  $('rtVolume').addEventListener('input', () => { $('rtVolumeVal').textContent = `${Number($('rtVolume').value) > 0 ? '+' : ''}${$('rtVolume').value} dB`; s.reglages.volume_db = Number($('rtVolume').value); envoyer(); });
  $('rtVolume').addEventListener('change', () => changer(r => { r.volume_db = Number($('rtVolume').value); }));
  $('rtAvance').addEventListener('change', (ev) => {
    const e = ev.target.closest('[data-rt]'); if (!e) return;
    const [g, k] = e.dataset.rt.split('.');
    const v = e.type === 'checkbox' ? e.checked : e.tagName === 'SELECT' ? (e.value === 'true' ? true : e.value === 'false' ? false : e.value) : Number(e.value);
    changer(r => { if (k) r[g] = { ...r[g], [k]: v }; else r[g] = v; });
  });
  $('rtGarder').addEventListener('click', async () => {
    $('rtGarder').disabled = true;
    try {
      const r = await fetch('/api/studio/retour/defaut', { method: 'POST', headers: { ...H(), 'Content-Type': 'application/json' }, body: JSON.stringify({ reglages: s.reglages, par: App ? 'telephone' : 'mac' }) });
      const o = await r.json().catch(() => ({}));
      if (!r.ok || !o.ok) throw new Error(o.erreur || `erreur ${r.status}`);
      s.defaut = o.defaut; afficher(); dire('Gardé : chaque prise repart sur ce réglage, sur le téléphone comme sur le Mac.');
    } catch (e) { dire(`Pas gardé : ${e.message}`); } finally { $('rtGarder').disabled = false; }
  });
  $('rtMesurer').addEventListener('click', mesurer);
  window.addEventListener('pagehide', () => eteindre(true));

  // au chargement : le réglage par défaut (partagé), les latences mesurées
  (async () => {
    try {
      const r = await fetch('/api/studio/retour', { headers: H() }), o = await r.json().catch(() => ({}));
      if (o.ok) { s.defaut = o.defaut || null; s.mesures = o.mesures || {}; if (s.defaut) s.reglages = D.borner({ ...s.defaut, preset: s.defaut.preset || 'perso' }); }
    } catch (_) {}
    afficher();
    const a = A();
    if (a && a.instru && a.instru()) contexte(a.contexteInstru(a.instru()));
  })();
  afficher();
  window.StudioRetour = { contexte, pourPrise, allume: () => s.allume, reglages: () => s.reglages, _s: s, refus, BLUETOOTH, HAUT_PARLEURS };
})();
