/* Mode Conversation de Jarvis (feuille de route, étape 6) : écoute continue, tours de parole
   détectés à la voix, coupure dès qu'Ahmed reprend la parole pendant que Jarvis parle.
   - Le micro passe par le navigateur, AVEC annulation d'écho (getUserMedia echoCancellation) :
     c'est la raison de la révision d'architecture de l'étape 5 ;
   - un AudioWorklet reçoit le son brut ; un détecteur de voix (énergie, plancher de bruit adaptatif)
     découpe les tours, avec 500 ms de pré-écoute pour ne pas manger le début des mots ;
   - pendant que Jarvis parle, le seuil monte au-dessus de l'écho résiduel estimé, et il faut 300 ms
     de voix tenue : alors seulement c'est Ahmed qui le coupe (pas Jarvis qui s'entend) ;
   - chaque tour devient un WAV 16 kHz (Whisper local), avec ses pauses mesurées (hésitations). */
(function (racine) {
  'use strict';
  // le processeur s'arrête (rend false) quand la page lui envoie « stop » : pas de nœud fantôme
  const CODE_CAPTEUR = "class C extends AudioWorkletProcessor { constructor() { super(); this.fini = false; "
    + "this.port.onmessage = () => { this.fini = true; }; } process(e) { if (this.fini) return false; "
    + "const c = e[0] && e[0][0]; if (c) this.port.postMessage(c.slice(0)); return true; } } "
    + "registerProcessor('capteur-jarvis', C);";
  const FENETRE_MS = 20, PREECOUTE_MS = 500, PAROLE_MAX_MS = 5 * 60 * 1000;
  // (28/10, Ahmed : « filtrer la vibration du cœur dans le micro ») le battement vibre ~160 ms (30 ms fort, 110 ms de pause,
  // 22 ms doux, appli Coeur.java) et le téléphone posé sur une table résonne un peu : 250 ms après chaque battement
  const VIBRATION_MS = 250;
  const enVibration = (maintenant, battement) => battement > 0 && maintenant >= battement && maintenant - battement <= VIBRATION_MS;
  // (28/10, sa sieste de 17:20 à 23:00, téléphone posé) le masque n'a pas tenu : des tours de 1 à 5 min, 12 hésitations
  // de 1,6-1,7 s chacun, au rythme de son cœur (35 bpm). Mesuré sur ces hésitations : ~70 ms « forts » par battement.
  // Pendant un tour, seule une voix qui TIENT 160 ms relance la patience (des creux de 40 ms au plus, une syllabe hachée) ;
  // un éclat plus court reste une pause, quel que soit le moment où la page apprend le battement.
  const COURSE_MS = 160, CREUX_MAX = 2;
  const mediane = (xs) => { const s = xs.slice().sort((a, b) => a - b); return s.length ? s[s.length >> 1] : 0; };

  function encoderWav(f32, taux) {
    const n = f32.length, tampon = new ArrayBuffer(44 + 2 * n), v = new DataView(tampon);
    const ecrire = (o, s) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
    ecrire(0, 'RIFF'); v.setUint32(4, 36 + 2 * n, true); ecrire(8, 'WAVE'); ecrire(12, 'fmt ');
    v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true); v.setUint32(24, taux, true);
    v.setUint32(28, 2 * taux, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true); ecrire(36, 'data');
    v.setUint32(40, 2 * n, true);
    for (let i = 0; i < n; i++) { const x = Math.max(-1, Math.min(1, f32[i])); v.setInt16(44 + 2 * i, x < 0 ? x * 0x8000 : x * 0x7fff, true); }
    return new Blob([tampon], { type: 'audio/wav' });
  }

  // La hauteur de la voix sur une fenêtre de 20 ms (autocorrélation à 12 kHz, 70 à 400 Hz) ; null si la
  // fenêtre n'est pas assez périodique (souffle, consonne). Lot C, point 20 : un INDICE, pas une émotion.
  function hauteur(f, taux) {
    const d = Math.max(1, Math.round(taux / 12000)), sr = taux / d, n = Math.floor(f.length / d);
    const x = new Float32Array(n);
    for (let i = 0; i < n; i++) { let s = 0; for (let k = 0; k < d; k++) s += f[i * d + k]; x[i] = s / d; }
    let r0 = 0; for (let i = 0; i < n; i++) r0 += x[i] * x[i];
    if (r0 <= 0) return null;
    const lmin = Math.floor(sr / 400), lmax = Math.min(n - 2, Math.ceil(sr / 70));
    let meilleur = 0, lag = 0;
    for (let l = lmin; l <= lmax; l++) {
      let r = 0; for (let i = 0; i + l < n; i++) r += x[i] * x[i + l];
      r /= r0 * (n - l) / n;
      if (r > meilleur) { meilleur = r; lag = l; }
    }
    return meilleur > 0.5 && lag ? sr / lag : null;
  }

  function reechantillonner(f32, de, vers) {
    if (de === vers) return f32;
    const r = de / vers, n = Math.floor(f32.length / r), out = new Float32Array(n);
    for (let i = 0; i < n; i++) {                     // moyenne sur la fenêtre : un filtre passe-bas suffisant ici
      const a = Math.floor(i * r), b = Math.min(f32.length, Math.floor((i + 1) * r));
      let s = 0; for (let k = a; k < b; k++) s += f32[k];
      out[i] = s / Math.max(1, b - a);
    }
    return out;
  }

  async function demarrer(o) {
    const flux = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
    const ctx = o.ctx;
    const url = URL.createObjectURL(new Blob([CODE_CAPTEUR], { type: 'application/javascript' }));
    let src, noeud;
    try {
      await ctx.audioWorklet.addModule(url);
      src = ctx.createMediaStreamSource(flux);
      noeud = new AudioWorkletNode(ctx, 'capteur-jarvis');
    } catch (e) {                                           // le micro ne reste jamais allumé sur une erreur
      flux.getTracks().forEach(p => p.stop());
      URL.revokeObjectURL(url);
      throw e;
    }
    const muet = ctx.createGain(); muet.gain.value = 0;     // tiré par la destination, sans rien jouer
    src.connect(noeud); noeud.connect(muet); muet.connect(ctx.destination);
    const taux = ctx.sampleRate, parFenetre = Math.round(taux * FENETRE_MS / 1000);
    const preecoute = [];                                   // fenêtres récentes, hors parole
    let fenetre = new Float32Array(parFenetre), remplis = 0;
    let bruit = 0.01, initFenetres = 0, echo = 0, jarvisDepuis = 0, enveloppe = 0, gainEcho = 0.2;
    let etatV = 'attente', tenue = 0, tour = [], debut = 0, derniereVoix = 0, voixMs = 0, pauseEnCours = 0, pauses = [];
    let energies = [], hauteurs = [];                       // le ton du tour (indices)
    // la voix en cours pendant un tour : sa longueur forte, ses creux, la pause qui la précédait, son ton en attente
    let course = 0, creux = 0, courseDebut = 0, pauseAvant = 0, tenueVoix = false, tonCourse = [];
    // la mesure des éclats (les sons trop courts pour une voix) et des avis de battement, entre deux tours
    let eclats = [], avis = [], avisVu = 0, tenueDebut = 0;
    const fortes = [];                                      // les 15 dernières fenêtres : fortes ou non
    let precedent = [];
    let actif = true, micCoupe = false;
    // (2026-10-23, Ahmed : un appel de sa mère, puis 9 min où rien ne passait) la dernière trame reçue du micro (un flux
    // bloqué par le téléphone ne se voit pas autrement : plus aucune trame, aucun événement), et la piste prise par le
    // système (un appel) : la page s'en sert pour le dire et relancer le son
    let derniereTrame = Date.now(), pisteMuette = false;
    const piste = flux.getAudioTracks()[0];
    if (piste) {
      piste.addEventListener('mute', () => { pisteMuette = true; if (o.surPiste) o.surPiste(false); });
      piste.addEventListener('unmute', () => { pisteMuette = false; if (o.surPiste) o.surPiste(true); });
    }

    function assembler(morceaux) {
      let n = 0; for (const m of morceaux) n += m.length;
      const tout = new Float32Array(n); let k = 0;
      for (const m of morceaux) { tout.set(m, k); k += m.length; }
      return encoderWav(reechantillonner(tout, taux, 16000), 16000);
    }

    // Fenêtres où l'on entend une voix (et pas seulement le souffle) : un morceau sans voix n'est
    // jamais envoyé à Whisper, qui sur du silence invente (« Sous-titres réalisés par… ») — et ce
    // faux texte collé à ta phrase la ferait jeter entière comme bruit.
    function voisees(morceaux) {
      const s = Math.max(0.012, bruit * 3.2);
      let n = 0;
      for (const m of morceaux) { let e = 0; for (let i = 0; i < m.length; i++) e += m[i] * m[i]; if (Math.sqrt(e / m.length) > s) n++; }
      return n;
    }
    const avecVoix = (m) => (voisees(m) >= 5 ? assembler(m) : null);   // 0,1 s de voix au moins

    function finTour(extra) {
      const duree = Date.now() - debut;
      const morceaux = tour; tour = []; etatV = 'attente'; tenue = 0; course = 0; creux = 0; tenueVoix = false; tonCourse = [];
      precedent = morceaux;                               // gardé : sa queue est transcrite après coup
      const h = hauteurs.slice().sort((a, b) => a - b), en = energies;
      energies = []; hauteurs = [];
      if (voixMs < 350) return;                           // un claquement, un souffle : pas un tour
      const ton = h.length >= 10 && en.length ? { f0: h[h.length >> 1], energie_db: 20 * Math.log10(en.reduce((a, b) => a + b, 0) / en.length) } : null;
      // (27/10, Hakim) arrêté par la limite des 5 min, pas par un silence : la parole continuait peut-être
      o.surFin(assembler(morceaux), { debut, fin: Date.now(), derniere_voix: derniereVoix, duree_ms: duree, voix_ms: voixMs, pauses: pauses.slice(), ton,
        ecoute_max: duree >= PAROLE_MAX_MS, vibration: mesureVibration() }, extra);
    }

    // Les éclats depuis le tour précédent : leur longueur, et leur écart à l'avis de battement le plus proche (négatif :
    // le son a commencé avant que la page le sache). Ce qui règlera le filtre sur le vrai téléphone.
    function noterEclat(debutEclat, ms) { if (eclats.length < 60) eclats.push({ debut: debutEclat, ms }); }
    function mesureVibration() {
      const decal = eclats.map(e => avis.reduce((m, a) => (Math.abs(e.debut - a) < Math.abs(m) ? e.debut - a : m), Infinity))
        .filter(Number.isFinite);
      const m = { eclats: eclats.length, battements: avis.length, eclat_med: mediane(eclats.map(e => e.ms)),
        eclat_max: Math.max(0, ...eclats.map(e => e.ms)), decal_med: mediane(decal), decal_min: decal.length ? Math.min(...decal) : 0,
        decal_max: decal.length ? Math.max(...decal) : 0, avant_avis: decal.filter(d => d < 0).length };
      eclats = []; avis = [];
      return m;
    }

    function analyser(f) {
      if (micCoupe) { if (o.surNiveau) o.surNiveau(0); return; }   // micro coupé : rien n'est écouté ni analysé
      let s = 0; for (let i = 0; i < f.length; i++) s += f[i] * f[i];
      const rms = Math.sqrt(s / f.length), maintenant = Date.now();
      const jarvis = !!o.jarvisParle();
      // pendant la vibration de son cœur : ce n'est pas une voix (ni début de tour, ni voix qui prolonge le tour)
      const battement = o.dernierBattement ? o.dernierBattement() : 0;
      if (battement && battement !== avisVu) { avisVu = battement; if (avis.length < 120) avis.push(battement); }
      const vibre = enVibration(maintenant, battement);
      if (jarvis && !jarvisDepuis) { jarvisDepuis = maintenant; echo = Math.max(echo * 0.5, bruit); }
      if (!jarvis) jarvisDepuis = 0;
      if (initFenetres < 15) { bruit = Math.max(0.002, initFenetres ? Math.min(bruit, rms) : rms); initFenetres++; }
      const seuil = Math.max(0.012, bruit * 3.2);
      // (2026-10-21, Ahmed : « la pause s'active toute seule ») l'écho suit SA voix à l'instant : l'enveloppe de ce
      // qu'il dit (descente ~250 ms, le temps que l'écho de la pièce s'éteigne) × le gain du chemin haut-parleur → micro,
      // appris quand il parle seul. Une syllabe forte de sa voix ne passe plus pour toi qui le coupes.
      const sortie = o.niveauSortie ? o.niveauSortie() : 0;
      enveloppe = Math.max(sortie, enveloppe * 0.93);
      const echoInstant = gainEcho * enveloppe;
      // pendant que Jarvis parle : au-dessus de l'écho résiduel, et jamais dans ses 400 premières ms
      const seuilBarge = Math.max(seuil * 2.5, echo * 2.4, echoInstant * 3);
      if (jarvis && etatV === 'attente' && enveloppe > 0.02 && rms < seuilBarge)
        gainEcho = Math.min(1, Math.max(0.005, gainEcho * 0.98 + 0.02 * (rms / enveloppe)));
      if (o.surNiveau) o.surNiveau(Math.min(1, rms * 7));
      if (etatV === 'attente') {
        if (jarvis) { if (rms < seuilBarge) echo = echo * 0.97 + rms * 0.03; }   // l'écho appris hors des moments forts
        else if (!vibre) bruit = Math.max(0.002, bruit * 0.985 + Math.min(rms, seuil) * 0.015);
        const fort = !vibre && (jarvis ? (rms > seuilBarge && maintenant - jarvisDepuis > 400) : rms > seuil);
        // « stop » a des creux (t, p) : 12 fenêtres fortes sur 15 suffisent pour couper Jarvis (relecture Opus)
        fortes.push(fort); if (fortes.length > 15) fortes.shift();
        const nFortes = fortes.reduce((n, x) => n + (x ? 1 : 0), 0);
        if (fort && !tenue) tenueDebut = maintenant;
        if (!fort && tenue) noterEclat(tenueDebut, tenue);       // trop court pour commencer un tour : un éclat
        tenue = fort ? tenue + FENETRE_MS : 0;
        preecoute.push(f.slice(0)); if (preecoute.length > PREECOUTE_MS / FENETRE_MS) preecoute.shift();
        if (jarvis ? nFortes >= 12 : tenue >= 120) {
          if (jarvis && o.surInterruption) o.surInterruption({ rms: +rms.toFixed(4), seuil: +seuilBarge.toFixed(4),
            echo: +echo.toFixed(4), echo_instant: +echoInstant.toFixed(4), gain: +gainEcho.toFixed(3) });
          etatV = 'parole'; debut = maintenant - PREECOUTE_MS; derniereVoix = maintenant; voixMs = Math.max(tenue, nFortes * FENETRE_MS);
          pauses = []; pauseEnCours = 0; fortes.length = 0; energies = []; hauteurs = [];
          course = tenue || FENETRE_MS; creux = 0; tenueVoix = true; tonCourse = [];   // ce qui a commencé le tour est une voix
          tour = preecoute.splice(0);
          if (o.surDebut) o.surDebut();
        }
        return;
      }
      tour.push(f.slice(0));
      // si Jarvis parle pendant le tour, son écho ne doit pas prolonger le tour d'Ahmed
      const forte = !vibre && rms > (jarvis ? seuilBarge : seuil);
      if (forte) {
        if (!course) { courseDebut = maintenant; pauseAvant = pauseEnCours; tonCourse = []; }
        course += FENETRE_MS; creux = 0;
        if (!jarvis) tonCourse.push([rms, hauteur(f, taux)]);
        if (!tenueVoix && course >= COURSE_MS) {              // elle tient : c'est une voix, depuis son début
          tenueVoix = true;
          if (pauseAvant >= 600) pauses.push(pauseAvant);     // une hésitation : une pause de plus de 0,6 s
          voixMs += course - FENETRE_MS;
        }
      } else if (course && ++creux > CREUX_MAX) {             // le son s'arrête : trop court pour une voix, c'était un éclat
        if (!tenueVoix) noterEclat(courseDebut, course);
        course = 0; creux = 0; tenueVoix = false; tonCourse = [];
      }
      if (forte && tenueVoix) {
        pauseEnCours = 0; derniereVoix = maintenant; voixMs += FENETRE_MS;
        for (const [r, f0] of tonCourse) { energies.push(r); if (f0) hauteurs.push(f0); }
        tonCourse = [];
      } else {
        pauseEnCours += FENETRE_MS;
        // une respiration de 0,4 s : un bon endroit pour couper et transcrire PENDANT que tu parles
        if (pauseEnCours === 400 && o.surPause) o.surPause(tour.length - 20);
      }
      if (o.surSilence) o.surSilence(maintenant - derniereVoix);
      // (un son en cours, peut-être le début d'un mot, n'est pas coupé par la patience : il a 160 ms pour tenir)
      if ((!course && maintenant - derniereVoix > o.patienceMs()) || maintenant - debut > PAROLE_MAX_MS) finTour();
    }

    noeud.port.onmessage = (ev) => {
      if (!actif) return;
      derniereTrame = Date.now();
      const x = ev.data;
      let i = 0;
      while (i < x.length) {
        const n = Math.min(parFenetre - remplis, x.length - i);
        fenetre.set(x.subarray(i, i + n), remplis); remplis += n; i += n;
        if (remplis === parFenetre) { analyser(fenetre); fenetre = new Float32Array(parFenetre); remplis = 0; }
      }
    };

    return {
      // « j'ai fini » : clôt le tour en cours tout de suite (clic sur la scène, ou fin anticipée avec
      // le texte déjà transcrit dans extra)
      finirTour(extra) { if (etatV === 'parole') finTour(extra); },
      get derniereVoix() { return derniereVoix; },
      // un morceau du tour en cours (fenêtres de 20 ms [de, a[) : transcrit pendant que tu parles ;
      // null s'il n'y a pas de voix dedans (rien à transcrire)
      segment(de, a) { return avecVoix(tour.slice(de, a === undefined ? tour.length : a)); },
      segmentFini(de, tourFini = precedent) { return avecVoix(tourFini.slice(de)); },   // la queue du tour qui vient de finir
      get dernierTour() { return precedent; },                        // à saisir avant d'attendre (un nouveau tour le remplace)
      get assezDeVoix() { return etatV === 'parole' && voixMs >= 350; },
      get fenetres() { return tour.length; },
      arreter() {
        actif = false;
        try { noeud.port.postMessage('stop'); noeud.port.onmessage = null; src.disconnect(); noeud.disconnect(); muet.disconnect(); } catch (_) {}
        flux.getTracks().forEach(p => p.stop());
        URL.revokeObjectURL(url);
      },
      get enParole() { return etatV === 'parole'; },
      get derniereTrame() { return derniereTrame; },
      get tonTour() { return hauteurs.length; },          // (2026-10-23) les trames voisées du tour : une voix, pas un bruit
      get pisteMuette() { return pisteMuette; },
      // Couper le micro sans quitter la conversation (demande d'Ahmed) : la piste est désactivée,
      // le navigateur n'envoie plus rien. (Ahmed, 2026-10-20 : « si je coupe le micro pendant que je parle, rien
      // n'est envoyé ») un tour EN COURS n'est plus abandonné : ce qui a été dit jusque-là part à Hakim.
      muet(oui) {
        if (oui && etatV === 'parole') finTour();
        micCoupe = !!oui;
        flux.getAudioTracks().forEach(p => { p.enabled = !micCoupe; });
        if (micCoupe) { tour = []; etatV = 'attente'; tenue = 0; course = 0; creux = 0; tenueVoix = false; tonCourse = []; preecoute.length = 0; }
      },
      get estMuet() { return micCoupe; },
    };
  }

  // Whisper invente des phrases sur le bruit ou le silence (« Sous-titres réalisés par… ») : écartées.
  const HALLUCINATIONS = /sous-?titr|amara\.org|merci d'avoir regard|abonnez-vous|merci de votre attention|^[\s.…!?,-]*$/i;
  function utile(texte) {
    const t = String(texte || '').trim();
    return t.replace(/[^\p{L}]/gu, '').length >= 2 && !HALLUCINATIONS.test(t);
  }

  racine.Conversation = { demarrer, encoderWav, reechantillonner, utile, hauteur, enVibration };
})(window);
