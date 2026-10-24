/* La vision de Jarvis (demande d'Ahmed, 2026-10-16 : « qu'il puisse me voir au travers de la caméra et
   analyser mon visage, mes mimiques »).
   - L'analyse tourne DANS LE NAVIGATEUR, sur le Mac (MediaPipe Face Landmarker, servi par le
     cockpit, aucun envoi) : ~8 images par seconde, 52 coefficients d'expression (sourire, sourcils,
     bouche, paupières) et l'orientation de la tête ;
   - elle en tire une expression lissée (souriant, rit, sourcils froncés, surpris, yeux fermés,
     regarde ailleurs, absent, neutre) que la page range dans le présent vécu, à la seconde ;
   - capturer() rend une photo JPEG de l'instant, jointe au message : Jarvis la regarde (Read) quand
     ton visage, tes gestes ou ce que tu lui montres comptent.
   Une expression n'est pas une émotion : Jarvis décrit ce qu'il voit et demande, il ne devine pas. */
(function (racine) {
  'use strict';
  const BASE = '/vendor/mediapipe';
  const PAS_MS = 120;

  function moyenne(bs, noms) {
    let s = 0; for (const n of noms) s += bs[n] || 0;
    return s / noms.length;
  }

  // Lacet et tangage (degrés) depuis la matrice de transformation du visage (colonne d'abord).
  function orientation(m) {
    if (!m) return { lacet: 0, tangage: 0 };
    const d = m.data || m;
    return { lacet: Math.atan2(d[8], d[10]) * 180 / Math.PI, tangage: Math.asin(Math.max(-1, Math.min(1, -d[9]))) * 180 / Math.PI };
  }

  // Relecture Opus (2026-10-16) : un rire plisse les yeux (le sourire passe avant les yeux fermés) ;
  // en conversation la bouche bouge sans cesse (la surprise ne s'appuie plus sur la mâchoire) ; les
  // valeurs sont relatives au visage neutre d'Ahmed, mesuré pendant les premières secondes.
  function classer(x) {
    if (!x.present) return 'absent';
    if (Math.abs(x.lacet) > 28 || Math.abs(x.tangage) > 24) return 'regarde ailleurs';
    if (x.sourire > 0.55 && x.bouche > 0.3) return 'rit';
    if (x.sourire > 0.38) return 'souriant';
    if (x.yeux > 0.5) return 'yeux fermés';
    if (x.surprise > 0.4) return 'surpris';
    if (x.froncement > 0.32) return 'sourcils froncés';
    return 'neutre';
  }

  // (24/10, idée de Hakim, accord d'Ahmed) o.face : « user » (avant, par défaut) ou « environment » (arrière, pour montrer
  // un objet ou un document) ; avec l'arrière, AUCUNE analyse de visage (ce n'est pas Ahmed qu'on filme)
  async function demarrer(o) {
    const face = o.face === 'environment' ? 'environment' : 'user';
    const flux = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: face }, audio: false });
    const video = o.video;
    video.srcObject = flux;
    video.muted = true;
    try { await video.play(); }
    catch (e) { flux.getTracks().forEach(p => p.stop()); video.srcObject = null; throw e; }   // jamais de caméra allumée orpheline
    let lm = null, delegue = 'aucune';
    // (24/10, Hakim : « personne dans le cadre » alors qu'Ahmed est bien visible) ce que l'analyse voit vraiment, pour le
    // diagnostic : images analysées, visages trouvés (points du visage), dont avec coefficients d'expression
    const stats = { images: 0, visages: 0, avec_expressions: 0 };
    if (face === 'user') try {
      const { FilesetResolver, FaceLandmarker } = await import(`${BASE}/vision_bundle.mjs`);
      const fichiers = await FilesetResolver.forVisionTasks(`${BASE}/wasm`);
      const options = (delegue) => ({ baseOptions: { modelAssetPath: `${BASE}/face_landmarker.task`, delegate: delegue },
        runningMode: 'VIDEO', numFaces: 1, outputFaceBlendshapes: true, outputFacialTransformationMatrixes: true });
      // (24/10, vision_etat du Fold : sur le GPU de la WebView, 7 visages trouvés sur 321 images, quand Android en trouvait
      // 61 sur 66) o.delegue = « CPU » pour commencer par le processeur ; le GPU reste le premier choix ailleurs
      const ordre = o.delegue === 'CPU' ? ['CPU', 'GPU'] : ['GPU', 'CPU'];
      try { lm = await FaceLandmarker.createFromOptions(fichiers, options(ordre[0])); delegue = ordre[0].toLowerCase(); }
      catch (_) { lm = await FaceLandmarker.createFromOptions(fichiers, options(ordre[1])); delegue = ordre[1].toLowerCase(); }
    } catch (e) {
      if (o.surErreur) o.surErreur(`analyse du visage indisponible : ${e.message || e}`);
    }
    let actif = true, dernier = 0, minuterie = null;
    const lisse = { sourire: 0, froncement: 0, surprise: 0, bouche: 0, yeux: 0, lacet: 0, tangage: 0, present: 0 };
    const neutre = { sourire: 0, froncement: 0, surprise: 0, yeux: 0 }, RELATIFS = Object.keys(neutre);
    let nNeutre = 0;                                        // visage de repos, appris sur ~30 images
    function image() {
      if (!actif) return;
      const t = performance.now();
      if (lm && video.readyState >= 2 && t - dernier >= PAS_MS) {
        dernier = t;
        let r = null;
        try { r = lm.detectForVideo(video, t); } catch (_) {}
        const bs = {};
        const cat = r && r.faceBlendshapes && r.faceBlendshapes[0];
        if (cat) for (const c of cat.categories) bs[c.categoryName] = c.score;
        // présent = des POINTS du visage trouvés (les coefficients d'expression peuvent manquer seuls, sur le GPU d'un
        // téléphone : ce n'était pas une absence)
        const present = (r && r.faceLandmarks && r.faceLandmarks.length) || cat ? 1 : 0;
        stats.images++; if (present) stats.visages++; if (cat) stats.avec_expressions++;
        const ori = orientation(r && r.facialTransformationMatrixes && r.facialTransformationMatrixes[0]);
        const brut = {
          present,
          sourire: moyenne(bs, ['mouthSmileLeft', 'mouthSmileRight']),
          froncement: moyenne(bs, ['browDownLeft', 'browDownRight']),
          surprise: (bs.browInnerUp || 0) * 0.5 + moyenne(bs, ['eyeWideLeft', 'eyeWideRight']) * 0.5,
          bouche: bs.jawOpen || 0,
          yeux: moyenne(bs, ['eyeBlinkLeft', 'eyeBlinkRight']),
          lacet: ori.lacet, tangage: ori.tangage,
        };
        for (const k in lisse) lisse[k] = lisse[k] * 0.7 + brut[k] * 0.3;     // ~0,35 s de lissage ; la page exige en plus 1,2 s stables
        if (present && nNeutre < 30) {                       // le repos d'Ahmed : moyenne des premières images
          nNeutre++;
          for (const k of RELATIFS) neutre[k] += (brut[k] - neutre[k]) / nNeutre;
        }
        const mesure = Object.assign({}, lisse, { present: lisse.present > 0.5 });
        for (const k of RELATIFS) mesure[k] = Math.max(0, lisse[k] - Math.min(neutre[k], 0.3));
        mesure.expression = classer(mesure);
        if (o.surMesure) o.surMesure(mesure);
      }
    }
    // requestAnimationFrame s'arrête quand l'onglet est caché : une minuterie continue de voir
    minuterie = setInterval(image, PAS_MS);

    return {
      capturer(largeur = 640) {
        const w = Math.min(largeur, video.videoWidth || largeur), h = Math.round(w * (video.videoHeight || 480) / (video.videoWidth || 640));
        const c = document.createElement('canvas');
        c.width = w; c.height = h;
        c.getContext('2d').drawImage(video, 0, 0, w, h);
        return new Promise(res => c.toBlob(res, 'image/jpeg', 0.82));
      },
      arreter() {
        actif = false;
        clearInterval(minuterie);
        try { if (lm) lm.close(); } catch (_) {}
        flux.getTracks().forEach(p => p.stop());
        video.srcObject = null;
      },
      get analyse() { return !!lm; },
      get delegue() { return delegue; },
      get stats() { return { ...stats }; },
      face,
    };
  }

  racine.Vision = { demarrer, classer };
})(window);
