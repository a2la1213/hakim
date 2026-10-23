/* Cockpit — PARLER À JARVIS (feuille de route JarvisXAnamnèse, étape 5 : le micro ponctuel).
   Un clic sur le micro : Ahmed parle, le micro se referme tout seul à la fin de la phrase, la
   transcription part à Hakim, la réponse s'affiche ÉCRITE au fil de l'eau, avec « écouter ».
   Cerveau : `claude -p` sur l'abonnement, avec la mémoire Anamnèse (route /api/jarvis).
   Voix : celles du système, une par langue (voix.js). Le mode Conversation viendra à l'étape 6. */
initNav('parler');

const $ = (id) => document.getElementById(id);
const CLE = 'jarvis.v1';
const NOMS_OUTILS = {
  memory_recall: 'souvenirs', memory_store: 'mémorise', memory_store_in: 'mémorise', memory_recent: 'souvenirs récents',
  reasoning_recall: 'raisonnements', facet_search: 'souvenirs', self_get: 'identité', self_append: 'identité',
  mood_get: 'humeur', affect_event: 'humeur', skill_list: 'compétences', skill_get: 'compétences',
  working_memory: 'mémoire de travail', rubric_tree: 'rubriques', landmark_add: 'repère', WebSearch: 'web',
};

/* ---------- état ---------- */
const etat = {
  session: null, messages: [], flux: null, micro: null, transcription: null, lectureDe: null, joints: [],
  reglages: { modele: 'opus', modeleConversation: 'sonnet', reconnaissance: 'navigateur', langue: 'auto', voix: 'neuronale', voixFr: '', voixAr: '',
    vitesse: 1.05, lectureAuto: false, patience: 3.5, scene: true, rapide: true, source: 'auto', volant: false, position: false, voixNeutre: false },
  sttLocal: false, ttsLocal: false,
  interieur: null, derniereActivite: Date.now(), dites: [],
  conversation: null, present: [], parleDepuis: 0, coupeParAhmed: false, vision: null,
};
function charger() {
  try {
    const s = JSON.parse(localStorage.getItem(CLE) || 'null');
    if (s) {
      etat.session = s.session || null;
      etat.messages = Array.isArray(s.messages) ? s.messages : [];
      Object.assign(etat.reglages, s.reglages || {});
      majConversation = Number(s.maj) || 0;
      debutConversation = Number(s.debut) || 0;
    }
  } catch (_) {}
  // Haiku écarté par Ahmed : un ancien réglage repasse à Sonnet ou Opus
  if (!['sonnet', 'opus', 'auto'].includes(etat.reglages.modele)) etat.reglages.modele = 'opus';
  if (!['sonnet', 'opus', 'auto'].includes(etat.reglages.modeleConversation)) etat.reglages.modeleConversation = 'sonnet';
  if (!['auto', 'abonnement', 'api', 'local'].includes(etat.reglages.source)) etat.reglages.source = 'auto';
  // Ahmed (2026-10-18) : par défaut, la langue est DÉTECTÉE parmi le français, l'arabe et l'anglais (plus
  // jamais l'islandais) ; l'ancien défaut « français » passe une fois à ce mode, son choix reste libre ensuite
  try {
    if (!localStorage.getItem(CLE + '.langues3')) {
      if (etat.reglages.langue === 'fr-FR') etat.reglages.langue = 'auto';
      localStorage.setItem(CLE + '.langues3', '1');
    }
  } catch (_) {}
}
// La conversation est PARTAGÉE entre tes appareils (ce Mac, ton téléphone) : le cockpit la garde aussi
// (demande d'Ahmed, 2026-10-17 : « que rien ne soit perdu et que tout soit complet sur mon smartphone »).
// Avant chaque message, la page reprend la version la plus récente ; si deux appareils ont écrit en même
// temps, le cockpit fusionne les deux par message (rien n'est écrasé).
// « Le contexte au max » (Ahmed, 2026-10-18) : 1000 messages gardés (ici et dans le cockpit), seule la fin
// est envoyée à chaque fois (les deux se fusionnent par message), et le fil n'en dessine que les derniers
// (« messages précédents » pour remonter) : le téléphone reste fluide.
const MESSAGES_MAX = 1000, MESSAGES_ENVOI = 150, FENETRE = 150;
let majConversation = 0, debutConversation = 0, envoiConversation = null;
function garderLocal() {
  const base = { session: etat.session, reglages: etat.reglages, maj: majConversation, debut: debutConversation };
  const msgs = etat.messages.filter(m => !m.enCours);
  for (const n of [MESSAGES_MAX, 300, 80]) {                    // le navigateur limite sa place (~5 Mo) : on réduit
    try { localStorage.setItem(CLE, JSON.stringify({ ...base, messages: msgs.slice(-n) })); return; } catch (_) {}
  }
}
function sauver() {
  garderLocal();
  clearTimeout(envoiConversation);
  envoiConversation = setTimeout(() => {
    const corps = JSON.stringify({ session: etat.session, messages: etat.messages.filter(m => !m.enCours).slice(-MESSAGES_ENVOI),
      base_ms: majConversation, debut_ms: debutConversation });
    fetch('/api/jarvis/conversation', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() }, body: corps })
      .then(r => r.ok ? r.json() : null)
      .then(o => {
        if (!o) return;
        majConversation = Number(o.maj_ms) || majConversation;
        if (o.fusion && Array.isArray(o.messages) && !etat.flux && !etat.messages.some(m => m.enCours)) {   // l'autre appareil avait écrit
          etat.session = o.session || null;
          etat.messages = o.messages;
          debutConversation = Number(o.debut_ms) || debutConversation;
          rendre();
        }
        garderLocal();
      }).catch(() => {});
  }, 600);
}
async function synchroniser() {
  if (etat.flux || lecteur.actif || (etat.conversation && etat.conversation.enAttente)) return;   // jamais au milieu d'une réponse
  try {
    const o = await (await fetch('/api/jarvis/conversation', { cache: 'no-store' })).json();
    if (o && !Number(o.maj_ms) && etat.messages.length) return sauver();      // le cockpit n'a rien encore : il prend celle-ci
    if (!o || !(Number(o.maj_ms) > majConversation) || !Array.isArray(o.messages) || etat.flux) return;
    // des messages d'ici que le cockpit n'a jamais vus (cet appareil n'avait pas encore partagé) : fusion, pas remplacement
    const vus = new Set(o.messages.map(m => m && m.id));
    const quand = (m) => Number(m.ts) || Number(m.id) || 0;
    if (etat.messages.some(m => !m.enCours && !vus.has(m.id) && quand(m) >= (Number(o.debut_ms) || 0))) return sauver();
    majConversation = Number(o.maj_ms);
    debutConversation = Number(o.debut_ms) || 0;
    etat.session = o.session || null;
    etat.messages = o.messages;
    garderLocal();
    rendre();
    await accuserReception();                              // ce qu'il a dit de lui-même pendant ton absence est vu
  } catch (_) {}
}

/* ---------- voix (synthèse) ---------- */
const synth = window.speechSynthesis || null;
let toutesVoix = [];
const voixPour = (langue) => {
  if (!toutesVoix.length && synth) toutesVoix = synth.getVoices();      // liste parfois chargée tard
  return Voix.choisirVoix(toutesVoix, langue, langue === 'ar' ? etat.reglages.voixAr : etat.reglages.voixFr);
};
// (2026-10-22, Ahmed) le débit suit aussi son émotion, modérément (×0,94 à ×1,04, réglé par le démon) ; ton réglage reste la base
// (2026-10-22, 16:10, Ahmed) « voix neutre » : ni le débit ni l'expressivité de son émotion
// (2026-10-23) les prononciations locales (son prénom écrit en arabe, dit à la française) : chargées une fois
fetch('/api/voix/prononciations', { cache: 'no-store' }).then(r => r.json()).then(d => Voix.definirPrononciations(d)).catch(() => {});
const vitesseVoix = () => (etat.reglages.vitesse || 1) * (etat.reglages.voixNeutre ? 1 : Math.max(0.92, Math.min(1.06, Number(etat.interieur && etat.interieur.voix_vitesse) || 1)));
const lecteurSysteme = synth ? Voix.creerLecteur(synth, window.SpeechSynthesisUtterance, voixPour, vitesseVoix) : null;

// Voix neuronale (Chatterbox, sur le Mac, étape 5 bis) : chaque morceau d'une seule langue est
// calculé par le cockpit (/api/voix/dire) puis joué ; on précharge les deux suivants. Le calcul
// va à peu près au rythme de la parole : la première phrase part seule, la suite est regroupée.
// Voix neuronale FLUIDE (demande d'Ahmed, 2026-10-16 : « il marque un temps entre chaque paragraphe ;
// je ne dois pas ressentir de coupure ; il pourrait parler au fur et à mesure qu'il écrit »).
// La synthèse coûte ~0,7 s fixes par morceau plus ~0,55 s par seconde de voix : un petit morceau
// suivi d'un gros laisse un trou. D'où un ordonnanceur qui raisonne en SECONDES D'AVANCE :
// - chaque morceau est taillé pour être prêt avant que la voix déjà programmée ne s'épuise
//   (l'avance grandit à chaque morceau : les morceaux aussi, jusqu'à ~400 caractères) ;
// - au tout début, la 1re phrase part seule (voix rapide) et, si la suivante ne pourra pas être prête
//   à temps, le départ est retardé juste assez (au plus 3 s) pour qu'il n'y ait plus de coupure ;
// - les vitesses sont apprises en direct (la machine peut être chargée) ;
// - lecture SANS TROU par Web Audio : chaque morceau est programmé à l'instant où finit le précédent.
// Hakim ne commence pas à parler pendant que tu parles (ou que ta phrase est transcrite) : relecture
// Opus du 2026-10-16 — sinon il parlait par-dessus ton tour et Whisper transcrivait son écho.
function jarvisPeutParler() {
  const c = etat.conversation;
  return !(c && ((c.capteur && c.capteur.enParole) || c.enAttente > 0));
}

function creerLecteurNeuronal() {
  const unites = [];                  // phrases (ou morceaux de phrase) en attente : { langue, texte }
  const lots = [];                    // envoyés à la synthèse, dans l'ordre : { langue, texte, t0, pret, erreur, ctl }
  const sources = new Set();
  let prochainDebut = 0, generation = 0, element = null, veille = null;
  // Pause (lot C, point 26, 2026-10-19) : ce qui n'a pas encore été dit, la phrase en cours comprise, est
  // gardé ; la reprise repart de cette phrase. Le texte qui arrive pendant la pause s'y ajoute.
  let pause = null, elementTexte = null;
  // coût fixe (s), coût par seconde de voix, caractères par seconde de voix : prudents au départ (la
  // machine swappe souvent), puis appris et gardés d'une session à l'autre dans ce navigateur
  const est = { fixe: 0.85, parSec: 0.75, cps: 15 };
  try { Object.assign(est, JSON.parse(localStorage.getItem('jarvis.voix.vitesses') || '{}')); } catch (_) {}
  const garder = () => { try { localStorage.setItem('jarvis.voix.vitesses', JSON.stringify(est)); } catch (_) {} };
  const fluide = () => actx && actx.state === 'running';
  const avance = () => (fluide() ? Math.max(0, prochainDebut - actx.currentTime) : 0);
  const prevoir = (n) => est.fixe + est.parSec * (n / est.cps);   // temps de synthèse prévu pour n caractères
  const L = {
    surFin: null, surSegment: null, fluxFini: true,
    appliquerSon() { if (element) element.muted = !!etat.sonCoupe; },
    dire(phrase) {
      if (pause) { pause.textes.push(...Voix.prononcable(phrase)); pause.fluxFini = false; return; }
      L.fluxFini = false;
      for (const seg of Voix.prononcable(phrase)) {
        // les phrases très longues sont coupées aux virgules : un morceau peut alors rester petit
        const parts = seg.texte.length > 160 ? seg.texte.split(/(?<=[,;:])\s+/) : [seg.texte];
        let cur = '';
        for (const pa of parts) { if (cur && cur.length + pa.length > 160) { unites.push({ langue: seg.langue, texte: cur }); cur = pa; } else cur = cur ? cur + ' ' + pa : pa; }
        if (cur) unites.push({ langue: seg.langue, texte: cur });
      }
      pomper();
    },
    finFlux() { if (pause) { pause.fluxFini = true; return; } L.fluxFini = true; pomper(); },
    // ce qui n'a pas encore été dit, la phrase en cours comprise (reprise du début), sans rien arrêter
    restant() {
      if (pause) return pause.textes.slice();
      const maintenant = fluide() ? actx.currentTime : 0;
      const restants = [];
      if (element && elementTexte) restants.push({ langue: 'fr', texte: elementTexte });
      for (const src of [...sources].sort((a, b) => a._debut - b._debut))     // en cours (repris du début) et à venir
        if (src._texte && src._fin > maintenant + 0.05) restants.push({ langue: src._langue, texte: src._texte });
      for (const x of lots) restants.push({ langue: x.langue, texte: x.texte });
      for (const u of unites) restants.push(u);
      return restants;
    },
    // met en pause ; rend vrai si quelque chose restait à dire
    pause() {
      if (pause || !L.actif) return false;
      const restants = L.restant();
      const fluxFini = L.fluxFini;
      L.arreter();
      pause = { textes: restants, fluxFini };
      return true;
    },
    reprendre() {
      if (!pause) return false;
      const p = pause; pause = null;
      L.fluxFini = false;
      unites.push(...p.textes);
      if (p.fluxFini) L.fluxFini = true;
      pomper();
      return true;
    },
    get enPause() { return !!pause; },
    arreter() {
      pause = null;
      generation++;
      for (const x of lots) if (x.ctl) x.ctl.abort();
      lots.length = 0; unites.length = 0;
      for (const src of sources) { try { src.stop(); } catch (_) {} }
      sources.clear();
      if (element) { element.pause(); URL.revokeObjectURL(element.src); element = null; }
      prochainDebut = 0; L.fluxFini = true;
      clearInterval(veille); veille = null;
    },
    get actif() { return unites.length > 0 || lots.length > 0 || sources.size > 0 || !!element; },
    get joue() { return sources.size > 0 || !!element; },
  };

  // Coupe un texte trop long pour le temps disponible : à une ponctuation, ou juste avant une conjonction
  // (là où l'on reprend son souffle), jamais au milieu d'un groupe de mots. Les mots ne changent pas.
  const COUPURES = /[,;:]\s+|\s+(?=(?:et|mais|donc|car|puis|alors|parce que|pour que|quand)\s)/gi;
  function couper(texte, max, min) {
    if (texte.length <= max) return null;
    let choix = null, m;
    COUPURES.lastIndex = 0;
    while ((m = COUPURES.exec(texte))) {
      const tete = texte.slice(0, m.index + (/^[,;:]/.test(m[0]) ? 1 : 0)).trim(), reste = texte.slice(m.index + m[0].length).trim();
      if (tete.length < min || reste.length < 12) continue;
      if (tete.length > max && choix) break;
      choix = [tete, reste];
      if (tete.length > max) break;                       // rien d'assez court : la première coupure possible
    }
    return choix;
  }

  // Le prochain lot : autant de phrases (même langue) que l'avance permet de synthétiser à temps.
  // Demande d'Ahmed (2026-10-17) : « qu'il commence à parler dès que la première phrase est écrite ».
  // - Au départ : la première phrase entière si elle est courte, sinon jusqu'à une virgule (35 à 90
  //   caractères) : la voix part tôt ET a de quoi tenir pendant que la suite se calcule ;
  // - ensuite, une phrase plus longue que ce que l'avance permet de calculer à temps est coupée à une
  //   virgule : le blanc éventuel tombe là où l'on respire, pas au milieu d'un paragraphe.
  function prochainLot() {
    const premier = !sources.size && !lots.length;
    const plafond = etat.conversation ? 160 : 400;
    const vitesse = vitesseVoix();
    // l'avance en secondes RÉELLES : ce qui est programmé (déjà à la vitesse) + ce qui est prêt (à diviser)
    const enAvance = avance() + lots.reduce((t, x) => t + (x.pret && x.pret.duration ? x.pret.duration : 0), 0) / vitesse;
    const budget = premier ? 0 : Math.min(plafond, est.cps * Math.max(0, (enAvance - est.fixe - 0.3) / est.parSec));
    const c = couper(unites[0].texte, premier ? 90 : Math.max(40, budget), premier ? 35 : 25);
    if (c) unites.splice(0, 1, { langue: unites[0].langue, texte: c[0] }, { langue: unites[0].langue, texte: c[1] });
    const u0 = unites[0];
    let texte = u0.texte, n = 1;
    while (n < unites.length && unites[n].langue === u0.langue && texte.length + unites[n].texte.length + 1 <= budget) {
      texte += ' ' + unites[n].texte; n++;
    }
    // (2026-10-22, les « incantations » d'Ahmed) un morceau très court envoyé seul fait divaguer la voix neuronale :
    // s'il en suit un de la même langue, il part avec lui, même au-delà du budget
    while (texte.length < 24 && n < unites.length && unites[n].langue === u0.langue) { texte += ' ' + unites[n].texte; n++; }
    unites.splice(0, n);
    return { langue: u0.langue, texte };
  }

  function lancer(x) {
    x.ctl = new AbortController();
    x.t0 = performance.now();
    const g = generation;
    fetch('/api/voix/dire', { method: 'POST', signal: x.ctl.signal,
      headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() },
      body: JSON.stringify({ texte: x.texte, langue: x.langue, emotion: etat.interieur && !etat.reglages.voixNeutre ? etat.interieur.expressivite : null }) })
      .then(r => r.ok ? r.arrayBuffer() : r.json().catch(() => ({})).then(o => Promise.reject(new Error(o.erreur || `voix ${r.status}`))))
      .then(ab => (fluide() ? actx.decodeAudioData(ab) : new Blob([ab], { type: 'audio/wav' })))
      .then(res => {
        if (g !== generation) return;
        x.pret = res;
        if (res.duration) {                                        // apprendre la vitesse réelle de la machine
          const G = (performance.now() - x.t0) / 1000;
          est.cps = 0.7 * est.cps + 0.3 * Math.min(25, Math.max(8, x.texte.length / res.duration));
          est.parSec = 0.7 * est.parSec + 0.3 * Math.min(1.5, Math.max(0.25, (G - est.fixe) / res.duration));
          garder();
        }
        pomper();
      })
      .catch(e => { if (g === generation && e.name !== 'AbortError') { x.erreur = e; pomper(); } });
  }

  function programmer(x, t) {
    const vitesse = vitesseVoix();
    const src = actx.createBufferSource();
    src.buffer = x.pret;
    src.playbackRate.value = vitesse;
    src.connect(analyseurVoix);
    src.start(t);
    prochainDebut = t + x.pret.duration / vitesse + 0.05;
    src._texte = x.texte; src._langue = x.langue; src._debut = t; src._fin = t + x.pret.duration / vitesse;
    sources.add(src);
    const g = generation;
    setTimeout(() => { if (g === generation && L.surSegment) L.surSegment(x.texte); }, Math.max(0, (t - actx.currentTime) * 1000));
    src.onended = () => { sources.delete(src); if (g === generation) pomper(); };
  }

  function pomper() {
    // 1. le processus voix ne reste jamais inactif quand du texte attend (une demande à la fois : on
    //    taille le lot en connaissant l'avance exacte du moment)
    if (unites.length && !lots.some(x => !x.pret && !x.erreur)) {
      const x = prochainLot();
      lots.push(x);
      lancer(x);
    }
    // 2. programmer, dans l'ordre, ce qui est prêt
    while (lots.length && (lots[0].pret || lots[0].erreur) && !element) {
      const x = lots[0];
      if (x.erreur) {
        lots.shift();
        humeur(`voix neuronale : ${x.erreur.message || x.erreur} — voix du Mac en secours`);
        if (lecteurSysteme) {                       // à la suite de ce qui est programmé, pas par-dessus
          const dans = fluide() ? Math.max(0, prochainDebut - actx.currentTime) : 0;
          const g = generation;
          setTimeout(() => { if (g === generation) lecteurSysteme.dire(x.texte); }, dans * 1000);
          if (fluide()) prochainDebut = Math.max(prochainDebut, actx.currentTime) + x.texte.length / est.cps / vitesseVoix() + 0.3;
        }
        continue;
      }
      if (x.pret instanceof Blob) { lots.shift(); jouerElement(x); break; }   // contexte audio pas encore autorisé
      if (!sources.size && avance() === 0 && !jarvisPeutParler()) break;   // on attend la fin de ton tour
      // (Avant le 2026-10-17, une machine lente attendait 8 s de voix d'avance, voire la fin de tout le
      // texte, avant de parler : c'est ce qu'Ahmed entendait. Le découpage aux virgules remplace l'attente.)
      let t = Math.max(actx.currentTime + 0.03, prochainDebut);
      if (!sources.size && avance() === 0) {
        // départ : si la suite (déjà lancée à l'étape 1) ne sera pas prête quand cette phrase finit,
        // retarder le départ juste assez — une attente au début plutôt qu'une coupure au milieu
        const y = lots.find(l => l !== x && !l.pret && !l.erreur);
        const pretDans = y ? (y.t0 + prevoir(y.texte.length) * 1000 - performance.now()) / 1000
          : (unites.length ? prevoir(unites[0].texte.length) : 0);
        const attente = pretDans - x.pret.duration / vitesseVoix() + 0.15;
        if (attente > 0) t += Math.min(0.5, attente);                 // au plus une demi-seconde : il parle tôt
      }
      lots.shift();
      programmer(x, t);
    }
    if (L.actif && !veille) veille = setInterval(pomper, 250);
    if (!L.actif) { clearInterval(veille); veille = null; if (L.surFin) L.surFin(); }
  }

  function jouerElement(x) {
    element = new Audio(URL.createObjectURL(x.pret));
    element.muted = !!etat.sonCoupe;
    elementTexte = x.texte;
    element.playbackRate = vitesseVoix();
    if (L.surSegment) L.surSegment(x.texte);
    const g = generation, fin = () => {
      if (g !== generation) return;
      URL.revokeObjectURL(element.src); element = null; pomper();
    };
    element.onended = fin; element.onerror = fin;
    // (2026-10-21) un lecteur bloqué par le navigateur (pas de geste récent, onglet en arrière-plan) : avant, le
    // morceau était sauté et les sous-titres défilaient en silence ; maintenant il attend un toucher et le dit
    element.play().catch((e) => {
      if (g !== generation) return;
      if (e && e.name === 'NotAllowedError') { sonBloque('lecteur'); return; }
      fin();
    });
  }
  L.debloquer = () => { if (element && element.paused) element.play().catch(() => {}); };
  return L;
}
// (2026-10-21) quand le navigateur bloque le son (contexte audio suspendu, lecteur refusé) : on le dit, et le
// prochain toucher le rend
let sonBloqueDepuis = 0;
function sonBloque(ou) {
  if (!sonBloqueDepuis) { sonBloqueDepuis = Date.now(); journalVoix('son_bloque', { ou, etat: actx ? actx.state : 'aucun' }); }
  humeur('le navigateur a coupé le son : touche l’écran pour entendre Hakim');
}
function debloquerSon() {
  if (!sonBloqueDepuis) return;
  journalVoix('son_rendu', { apres_ms: Date.now() - sonBloqueDepuis });
  sonBloqueDepuis = 0;
  lecteurNeuronal.debloquer();
  humeur();
}
// Le contexte audio (créé au premier geste d'Ahmed, règle des navigateurs) et l'analyseur de la voix.
let actx = null, analyseurVoix = null, gainSortie = null;
function contexteAudio() {
  try {
    if (!actx) {
      actx = new (window.AudioContext || window.webkitAudioContext)();
      analyseurVoix = actx.createAnalyser();
      analyseurVoix.fftSize = 256;
      analyseurVoix.smoothingTimeConstant = 0.55;
      // (2026-10-21) un volume juste avant la sortie : « couper le son » (widget de l'appli) laisse sa voix aller au
      // bout sans bruit, l'orbe pulse toujours
      gainSortie = actx.createGain();
      gainSortie.gain.value = etat.sonCoupe ? 0 : 1;
      analyseurVoix.connect(gainSortie);
      gainSortie.connect(actx.destination);
      // (2026-10-21) le contexte suspendu ou interrompu (écran verrouillé, casque Bluetooth qui bascule quand le
      // micro s'ouvre) : la voix programmée ne joue plus et ne finit jamais — on tente de le relancer, sinon on le dit
      actx.onstatechange = () => {
        journalVoix('contexte_audio', { etat: actx.state, parle: !!(lecteurNeuronal && lecteurNeuronal.actif) });
        if (actx.state !== 'running' && actx.state !== 'closed') {
          actx.resume().then(() => { if (actx.state === 'running') debloquerSon(); })
            .catch(() => {}).finally(() => { if (actx.state !== 'running' && lecteurNeuronal.actif) sonBloque('contexte'); });
        } else if (actx.state === 'running') debloquerSon();
      };
    }
    if (actx.state !== 'running' && actx.state !== 'closed') actx.resume().then(debloquerSon).catch(() => {});
    else debloquerSon();
  } catch (_) {}
}
document.addEventListener('pointerdown', contexteAudio);
document.addEventListener('keydown', contexteAudio);
// le niveau de SA voix à l'instant (pour que le micro reconnaisse son écho : conversation.js)
const tamponSortie = new Float32Array(256);
function niveauSortie() {
  if (!analyseurVoix || !lecteurNeuronal.joue) return 0;
  analyseurVoix.getFloatTimeDomainData(tamponSortie);
  let s = 0; for (let i = 0; i < tamponSortie.length; i++) s += tamponSortie[i] * tamponSortie[i];
  return Math.sqrt(s / tamponSortie.length);
}
const freq = new Uint8Array(128);
function niveauVoix() {
  if (!analyseurVoix || !lecteurNeuronal.joue) return null;
  analyseurVoix.getByteFrequencyData(freq);
  const moy = (a, b) => { let t = 0; for (let i = a; i < b; i++) t += freq[i]; return t / (b - a) / 255; };
  const g = moy(1, 5), m = moy(5, 17), a = moy(17, 48);              // ~0,2–0,9 kHz, ~0,9–3 kHz, ~3–9 kHz
  // Les octets de l'analyseur sont en décibels : la voix est « forte » en permanence. Calibré sur la vraie
  // voix de Hakim (2026-10-16 : graves 0,4–1, médiums 0,2–0,8, aigus 0,2–0,7) — plancher retiré, puis étiré.
  const etire = (x, plancher, plage) => Math.max(0, Math.min(1, (x - plancher) / plage));
  return { niveau: etire(0.5 * g + 0.3 * m + 0.2 * a, 0.25, 0.55), bandes: [etire(g, 0.3, 0.65), etire(m, 0.2, 0.6), etire(a, 0.2, 0.55)] };
}
const lecteurNeuronal = creerLecteurNeuronal();
// Un seul lecteur pour le reste de la page : la voix neuronale si elle est là, sinon celle du Mac.
const lecteur = {
  get impl() { return (etat.reglages.voix === 'neuronale' && etat.ttsLocal) || !lecteurSysteme ? lecteurNeuronal : lecteurSysteme; },
  dire(p) { this.impl.dire(p); },
  finFlux() { if (this.impl.finFlux) this.impl.finFlux(); },     // le texte est complet : vider la file
  arreter() { lecteurNeuronal.arreter(); if (lecteurSysteme) lecteurSysteme.arreter(); },
  get actif() { return lecteurNeuronal.actif || !!(lecteurSysteme && lecteurSysteme.actif); },
  // la voix du Mac ne sait pas reprendre : en pause, elle s'arrête
  pause() { if (this.impl === lecteurNeuronal) return lecteurNeuronal.pause(); this.arreter(); return false; },
  reprendre() { return lecteurNeuronal.reprendre(); },
  get enPause() { return lecteurNeuronal.enPause; },
};
const finLecture = () => { if (!lecteur.actif) { etat.lectureDe = null; etat.finVoixA = Date.now(); rendre(); humeur(); } };
lecteurNeuronal.surFin = finLecture;
if (lecteurSysteme) lecteurSysteme.surFin = finLecture;

/* ---------- les orbes : la petite (en-tête) et la grande (scène, quand il parle ou écoute) ---------- */
const orbeTete = Orbe.creer($('orbe'), { reduit: REDUCED });
const orbeScene = Orbe.creer($('orbeScene'), { reduit: REDUCED });
function niveauCourant() {
  if (etat.conversation && etat.conversation.capteur && etat.conversation.capteur.enParole)
    return { niveau: etat.niveauMicro || 0, bandes: [etat.niveauMicro || 0, (etat.niveauMicro || 0) * 0.8, (etat.niveauMicro || 0) * 0.6] };
  if (etat.micro) return { niveau: etat.niveauMicro || 0, bandes: [etat.niveauMicro || 0, (etat.niveauMicro || 0) * 0.8, (etat.niveauMicro || 0) * 0.6] };
  return niveauVoix();
}
orbeTete.source(niveauCourant);
orbeScene.source(niveauCourant);
const pulser = (x) => { orbeTete.pulser(x); orbeScene.pulser(x); };
const sousTitre = (t) => { $('sousTitre').textContent = t || ''; };
/* Diagnostic de la voix (2026-10-21, Ahmed : « la pause s'active toute seule », « il lit mais je n'entends rien ») :
   les événements de la voix et du micro (coupure, écho reconnu, son bloqué, contexte audio, transcription trop
   lente, attente de ton tour) sont gardés ici et envoyés au cockpit (~/AIOS/jarvis/voix-diagnostic.jsonl), pour
   qu'un prochain bug se lise au lieu de se deviner. Que des nombres et des noms d'événements, jamais de texte. */
const journalVoixFile = [];
let journalVoixMinuteur = null;
const ANDROID = /Android/i.test(navigator.userAgent || '');
function envoyerJournalVoix() {
  const lot = journalVoixFile.splice(0);
  try { localStorage.removeItem('jarvis.journalVoix'); } catch (_) {}
  if (lot.length) fetch('/api/voix/journal', { method: 'POST', keepalive: true,
    headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() }, body: JSON.stringify(lot) }).catch(() => {});
}
function journalVoix(e, d) {
  journalVoixFile.push({ t: Date.now(), e, appareil: ANDROID ? 'telephone' : 'mac', ...(d || {}) });
  if (journalVoixFile.length > 100) journalVoixFile.splice(0, journalVoixFile.length - 100);
  // (2026-10-21) gardé aussi dans le navigateur : une page tuée en arrière-plan ne perd plus ses derniers événements
  try { localStorage.setItem('jarvis.journalVoix', JSON.stringify(journalVoixFile)); } catch (_) {}
  clearTimeout(journalVoixMinuteur);
  journalVoixMinuteur = setTimeout(envoyerJournalVoix, document.visibilityState === 'hidden' ? 0 : 3000);
}
try {                                             // ce qu'une page précédente n'a pas pu envoyer
  const reste = JSON.parse(localStorage.getItem('jarvis.journalVoix') || '[]');
  if (Array.isArray(reste) && reste.length) { journalVoixFile.push(...reste.slice(-100), { t: Date.now(), e: 'page_rechargee' }); setTimeout(envoyerJournalVoix, 2000); }
} catch (_) {}
// ce que sa voix vient de dire (2 min) : si « ta » phrase n'est que l'écho de la sienne, ce n'est pas toi
const paroleRecente = [];
function noterParole(texte) {
  const t = Date.now();
  paroleRecente.push({ t, mots: new Set(sansAccents(texte).split(' ').filter(m => m.length >= 3)), suite: sansAccents(texte).split(' ').filter(Boolean) });
  while (paroleRecente.length && t - paroleRecente[0].t > 120000) paroleRecente.shift();
}
/* (2026-10-22, vu par Hakim à 14:49 : téléphone plié, haut-parleur, sa phrase revenue mot pour mot dans ta transcription,
   collée à la tienne) les morceaux de SA voix dans ce que le micro a entendu : toute suite d'au moins 4 mots qu'il vient de
   dire (45 s) est retirée ; le reste est ce que tu as dit. Rend { texte, retire } (retire = nombre de mots enlevés). */
function retirerEcho(texte) {
  const mots = String(texte || '').split(/\s+/).filter(Boolean);
  const norm = mots.map(m => sansAccents(m));
  const suites = paroleRecente.filter(x => Date.now() - x.t < 45000 && x.suite).map(x => ' ' + x.suite.join(' ') + ' ');
  if (!suites.length || mots.length < 4) return { texte: String(texte || ''), retire: 0 };
  const garde = new Array(mots.length).fill(true);
  for (let i = 0; i < norm.length; i++) {
    let j = i + 4;                                       // la plus longue suite à partir de i qu'il a dite
    if (j > norm.length || !suites.some(s => s.includes(' ' + norm.slice(i, j).join(' ') + ' '))) continue;
    while (j < norm.length && suites.some(s => s.includes(' ' + norm.slice(i, j + 1).join(' ') + ' '))) j++;
    for (let k = i; k < j; k++) garde[k] = false;
    i = j - 1;
  }
  const reste = mots.filter((_, k) => garde[k]);
  return { texte: reste.join(' '), retire: mots.length - reste.length };
}
function estSonEcho(texte) {
  const mots = sansAccents(texte).split(' ').filter(m => m.length >= 3);
  if (mots.length < 2) return false;
  const recents = new Set(paroleRecente.filter(x => Date.now() - x.t < 45000).flatMap(x => [...x.mots]));
  return mots.filter(m => recents.has(m)).length / mots.length >= 0.7;
}
lecteurNeuronal.surSegment = (t) => {
  if (mesureTour && mesureTour.premier_texte && !mesureTour.premier_son) { mesureTour.premier_son = Date.now(); finMesureTour(); }
  noterParole(t); sousTitre(t);
};
if (lecteurSysteme) { lecteurSysteme.surSegment = (t) => { noterParole(t); sousTitre(t); }; lecteurSysteme.surMot = () => pulser(0.35); }
// (2026-10-21) « Conversation » depuis l'écran d'accueil (raccourci /parler?conversation=1) : la grande orbe s'ouvre,
// un toucher démarre la conversation (le navigateur exige un geste pour ouvrir le son et le micro)
etat.demarrerAuToucher = new URLSearchParams(location.search).get('conversation') === '1';
if (etat.demarrerAuToucher) { try { history.replaceState(null, '', '/parler'); } catch (_) {} }
$('scene').addEventListener('click', (e) => {
  if (etat.demarrerAuToucher && !etat.conversation) { etat.demarrerAuToucher = false; basculerConversation(); return; }
  if (e.target.id === 'stopScene') { arreterMicro(false); arreterTout(); majBoutonsPause(); rendre(); humeur(); return; }
  if (e.target.id === 'pauseScene') { if (lecteur.enPause) reprendreVoix(); else pauseVoix(); return; }
  if (e.target.id === 'finConversation') return;
  if (etat.micro) return arreterMicro(true);           // il t'écoute : un clic, c'est « j'ai fini »
  const c = etat.conversation;
  if (c && c.capteur && c.capteur.enParole) return c.capteur.finirTour();
  etat.sceneMasquee = true; scene(false);
});
function revenirOrbe() { if (!etat.conversation) return; etat.sceneMasquee = false; humeur(); }
$('orbeRetour').addEventListener('click', revenirOrbe);
document.addEventListener('keydown', (e) => { if (e.altKey && (e.code === 'KeyO')) { e.preventDefault(); revenirOrbe(); } });
function scene(visible) {
  $('vision').classList.toggle('sur-scene', visible);
  const s = $('scene');
  s.classList.toggle('visible', visible);
  s.setAttribute('aria-hidden', visible ? 'false' : 'true');
}

function remplirVoix() {
  if (!synth) { $('noteVoix').textContent = 'Ce navigateur ne sait pas parler (speechSynthesis absent).'; return; }
  toutesVoix = synth.getVoices();
  for (const [sel, langue, cle] of [[$('voixFr'), 'fr', 'voixFr'], [$('voixAr'), 'ar', 'voixAr']]) {
    const liste = toutesVoix.filter(v => (v.lang || '').toLowerCase().startsWith(langue));
    const auto = Voix.choisirVoix(toutesVoix, langue);
    sel.innerHTML = `<option value="">automatique${auto ? ' · ' + esc(auto.name) : ''}</option>`
      + liste.map(v => `<option value="${esc(v.name)}">${esc(v.name)} · ${esc(v.lang)}${v.localService === false ? ' · en ligne' : ''}</option>`).join('');
    sel.value = liste.some(v => v.name === etat.reglages[cle]) ? etat.reglages[cle] : '';
  }
  const sansArabe = !toutesVoix.some(v => (v.lang || '').toLowerCase().startsWith('ar'));
  $('noteVoix').textContent = sansArabe
    ? 'Aucune voix arabe installée : Réglages Système › Accessibilité › Contenu énoncé › Voix du système › Gérer les voix › Arabe (par ex. Majed). Les expressions arabes seront lues avec la voix française en attendant.'
    : 'Les passages en écriture arabe sont lus avec la voix arabe, le reste avec la voix française (étape 5 bis : une seule voix multilingue plus tard).';
}
if (synth) { remplirVoix(); synth.addEventListener('voiceschanged', remplirVoix); }

function lire(m) {
  if (!lecteur) return;
  lecteur.arreter();
  if (etat.lectureDe === m.id) { etat.lectureDe = null; rendre(); humeur(); return; }   // re-clic : arrêter
  const d = Voix.decoupeur();
  const phrases = d.ajouter(m.texte + '\n').concat(d.finir());
  if (!phrases.length) return;
  etat.lectureDe = m.id;
  phrases.forEach(p => lecteur.dire(p));
  lecteur.finFlux();
  rendre(); humeur();
}

/* ---------- affichage ---------- */
function humeur(texte) {
  const parle = !!(lecteur && lecteur.actif), pense = !!etat.flux;
  const ecoute = !!etat.micro || !!(etat.conversation && !parle && !pense);
  noterParoleJarvis(lecteurNeuronal.joue || !!(lecteurSysteme && lecteurSysteme.actif));
  const code = etat.interieur && etat.interieur.humeur_code;
  const coupe = !!(etat.conversation && etat.conversation.capteur && etat.conversation.capteur.estMuet);
  const mode = ecoute && !coupe ? 'ecoute' : (parle ? 'parle' : (pense ? 'pense' : 'repos'));
  for (const o of [orbeTete, orbeScene]) { o.humeur(code); o.mode(mode); }
  // la scène : pendant qu'il parle, qu'il t'écoute, ou qu'il réfléchit à une question dite à l'oral
  const voixEnJeu = ecoute || parle || (pense && etat.dernierOral) || !!etat.conversation;
  $('muet').hidden = $('muetScene').hidden = !(etat.conversation && etat.conversation.capteur);
  // la pause de SA voix aussi hors de l'écran de conversation (Ahmed, 2026-10-20) : tant que la conversation est
  // ouverte, ou qu'il parle / est en pause
  $('pause').hidden = !(etat.conversation || (lecteur && (lecteur.actif || lecteur.enPause)));
  $('finConversation').hidden = !etat.conversation;
  if (!voixEnJeu) { etat.sceneMasquee = false; if (!parle) sousTitre(''); }
  scene(!!((etat.reglages.scene && voixEnJeu && !etat.sceneMasquee) || etat.demarrerAuToucher));
  if (etat.demarrerAuToucher && !etat.conversation) sousTitre('touche l’orbe pour commencer la conversation');
  // (2026-10-21, Ahmed) la grande orbe masquée d'un toucher pendant une conversation : un bouton pour y revenir
  $('orbeRetour').hidden = !(etat.reglages.scene && etat.conversation && etat.sceneMasquee);
  if (ecoute && !$('sousTitre').textContent) sousTitre('je t’écoute…');
  // l'humeur seule (elle change rarement) : le lecteur d'écran n'est pas inondé ; l'ennui en infobulle
  const repos = etat.interieur && etat.interieur.humeur ? `humeur : ${etat.interieur.humeur}` : 'prêt · mémoire Anamnèse';
  if (etat.interieur) $('etat').title = `ennui ${String((etat.interieur.ennui || 0).toFixed(2)).replace('.', ',')}`;
  if (texte) $('etat').textContent = texte;
  else $('etat').textContent = ecoute ? 'je t’écoute…' : (pense ? 'réfléchit…' : (parle ? 'parle…' : repos));
  $('envoyer').hidden = pense;
  $('stop').hidden = !(pense || parle);
}

// Liens cliquables dans les réponses (sources web) ; le texte est DÉJÀ échappé : rien d'autre ne passe.
// Le markdown que Claude écrit malgré tout (vu le 18/10 : « **…** » affiché tel quel) : gras, italique, titres
function gras(html) {
  return html
    .replace(/\*\*([^*\n]+?)\*\*/g, '<strong>$1</strong>').replace(/__([^_\n]+?)__/g, '<strong>$1</strong>')
    .replace(/(^|[\s(])\*([^*\s][^*\n]*?)\*(?=[\s).,;:!?]|$)/g, '$1<em>$2</em>')
    .replace(/(^|\n)#{1,4}\s+([^\n]+)/g, '$1<strong>$2</strong>');
}
// « No response requested. » : la réponse vide de Claude (vu pendant un live le 18/10) n'est ni affichée ni dite
const NON_REPONSE = /^\s*no response requested\.?\s*$/i;

// Les formules de maths (2026-10-21, demande d'Ahmed) : dessinées par KaTeX, servi par le cockpit (aucun CDN) ;
// la version parlée [[voix: …]] est cachée (seule la voix la lit, voix.js). Sans KaTeX : le LaTeX brut, échappé.
function formule(tex, bloc) {
  try {
    if (window.katex) return katex.renderToString(tex, { displayMode: bloc, throwOnError: false, output: 'html',
      strict: 'ignore', trust: false, maxSize: 20, maxExpand: 200 });
  } catch (_) { /* rendu impossible : texte brut */ }
  return `<code>${esc(tex)}</code>`;
}
// Le code (2026-10-21, demande d'Ahmed) : un bloc ```langage … ``` s'affiche tel quel, en police fixe, avec un bouton
// qui copie EXACTEMENT le code (à coller au bon format) ; `code` dans la phrase aussi en police fixe. Le code est sorti
// du texte AVANT les formules, le gras et les liens : un $, une * ou une adresse dans du code restent du code.
function blocCode(langage, code) {
  return `<div class="bloc-code"><div class="entete-code"><span>${esc(langage || 'code')}</span>`
    + `<button data-copier-code="1" title="Copier ce code">📋 copier le code</button></div>`
    + `<pre><code>${esc(code)}</code></pre></div>`;
}
function texteRiche(texte) {
  texte = Voix.sansAffect(texte, true);              // (2026-10-23) la balise d'appréciation de Hakim n'est jamais affichée
  const rendus = [];
  const garder = (html, marque) => { rendus.push(html); return `${marque}${rendus.length - 1}\uE001`; };
  const t = String(texte || '')
    .replace(/```[ \t]*([\w+#.-]*)[^\n]*\n([\s\S]*?)\n?```/g, (_t, langage, code) => garder(blocCode(langage, code), '\uE002'))
    .replace(/`([^`\n]+)`/g, (_t, code) => garder(`<code>${esc(code)}</code>`, '\uE000'))
    .replace(Voix.FORMULE, (_t, _f, d1, d2, i1, i2) => {
    const bloc = d1 != null || d2 != null;
    return garder(formule(d1 ?? d2 ?? i1 ?? i2, bloc), bloc ? '\uE002' : '\uE000');
  }).replace(Voix.VOIX_SEULE, '')
    .replace(/[ \t]*\n?[ \t]*(\uE002\d+\uE001)[ \t]*\n?/g, '$1');    // une formule en bloc : pas de ligne vide autour
  return liens(gras(esc(t))).replace(/[\uE000\uE002](\d+)\uE001/g, (_m, i) => rendus[Number(i)] || '');
}

function liens(html) {
  return html
    .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
    .replace(/(^|[\s(])(https?:\/\/[^\s<)]+)/g, '$1<a href="$2" target="_blank" rel="noopener noreferrer">$2</a>');
}

function htmlMessage(m) {
  if (m.qui === 'u') return `<div class="m u" data-id="${esc(m.id)}">${m.oral ? '<span class="oral">À L’ORAL</span>' : ''}`
    + ((m.joints || []).length ? `<div class="pj">${m.joints.map(n => `<span>📎 ${esc(n)}</span>`).join('')}</div>` : '')
    + `<div class="txt">${esc(m.texte)}</div>`
    + (m.texte ? `<div class="pied"><button data-copier="${esc(m.id)}" title="Copier ce message">📋 copier</button></div>` : '') + '</div>';
  const outils = (m.outils || []).length
    ? `<div class="outils">${[...new Set(m.outils)].map(o => `<span class="badge muted">${esc(o)}</span>`).join('')}</div>` : '';
  const corps = m.texte && NON_REPONSE.test(m.texte) ? '<div class="attente">(il n’a rien répondu)</div>'
    : m.texte ? `<div class="txt">${texteRiche(m.texte)}</div>`
    : (m.enCours ? `<div class="attente">${m.outils && m.outils.length ? 'cherche…' : 'réfléchit…'}</div>` : '');
  const suite = m.attenteServeur ? '<div class="attente">la connexion s’est coupée : il termine sa réponse sur le Mac, elle s’affichera ici</div>' : '';
  const err = m.erreur ? `<div class="txt">${esc(m.erreur)}</div>` : '';
  const pieces = (m.pieces || []).filter(x => x && /^\d{8}-\d{6}-[0-9a-f]{6}$/.test(String(x.id))).map(x => {
    const image = /^(png|jpe?g|gif|webp)$/.test(String(x.type));
    return `<div class="piece">${image ? `<img data-apercu="${x.id}" alt="${esc(x.titre || x.nom)}">` : ''}`
      + `<button class="btn" data-piece="${x.id}" data-nom="${esc(x.nom)}">📎 ${esc(x.nom)} · ${tailleLisible(x.taille)}</button>`
      + `${x.titre ? `<span class="titre-piece">${esc(x.titre)}</span>` : ''}</div>`;
  }).join('');
  const pied = [];
  if (m.texte && !m.enCours && lecteur) pied.push(`<button data-lire="${esc(m.id)}">${etat.lectureDe === m.id ? '⏹ arrêter' : '🔊 écouter'}</button>`);
  if (m.texte && !m.enCours) pied.push(`<button data-copier="${esc(m.id)}" title="Copier ce message">📋 copier</button>`);
  if (m.coupe) pied.push('<span>coupé</span>');
  if (m.ms) pied.push(`<span>${(m.ms / 1000).toFixed(1).replace('.', ',')} s</span>`);
  if (m.modele) pied.push(`<span title="Choisi par le routeur : Sonnet pour discuter, Opus pour travailler">${m.modele === 'opus' ? 'Opus' : 'Sonnet'}</span>`);
  if (m.jetons) {
    const J = (k) => Number(m.jetons[k]) || 0;                  // (C-M3) toujours des nombres
    const lu = J('entree') + J('cache_lu') + J('cache_ecrit');
    const k = (n) => n >= 1000 ? `${(n / 1000).toFixed(n >= 10000 ? 0 : 1).replace('.', ',')} k` : String(n);
    pied.push(`<span title="Jetons de ce tour : ${J('entree')} neufs, ${J('cache_lu')} relus en cache, ${J('cache_ecrit')} mis en cache, ${J('sortie')} écrits par lui">${k(lu)} jetons${lu ? ` · ${Math.round(100 * J('cache_lu') / lu)} % en cache` : ''}</span>`);
  }
  if (m.source === 'api') pied.push('<span title="Forfait à sa limite : réponse par l\'API Claude (payée à l\'usage)">via l\'API</span>');
  if (m.source === 'local') pied.push('<span title="Forfait et API indisponibles : cerveau local, sans outils">cerveau local</span>');
  const etiquette = m.spontane ? `<span class="etiquette">${m.spontane === 'outreach' ? 'IL TE RELANCE' : m.spontane === 'resultat' ? 'DE LUI-MÊME · RÉSULTAT' : m.spontane === 'tache' ? 'TÂCHE DE FOND' : m.spontane === 'promotion' ? 'IL PROPOSE UNE MODIFICATION' : m.spontane === 'mission' ? 'MISSION POUR CLAUDE CODE' : m.spontane === 'ecriture' ? 'IL PROPOSE UNE ÉCRITURE' : m.spontane === 'regle' ? 'UNE RÈGLE TIRÉE DE SES ERREURS' : m.spontane === 'identite' ? 'SON IDENTITÉ · À TOI DE TRANCHER' : m.spontane === 'sortie' ? 'SORTIE À AUTORISER' : 'PENSÉE SPONTANÉE'} · ${new Date(m.ts).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}</span>` : '';
  return `<div class="m j${m.erreur ? ' err' : ''}${m.spontane ? ' spontane' : ''}" data-id="${esc(m.id)}">${etiquette}${outils}${m.spontane === 'mission' ? htmlMission(m.mission) : m.spontane === 'ecriture' ? htmlEcriture(m.ecriture) : m.spontane === 'regle' ? htmlRegle(m.regle) : m.spontane === 'identite' ? htmlIdentite(m.identite) : m.spontane === 'sortie' ? htmlSortie(m.sortie) : corps}${suite}${err}${pieces ? `<div class="pieces">${pieces}</div>` : ''}${pied.length ? `<div class="pied">${pied.join('')}</div>` : ''}</div>`;
}

/* Les pièces jointes de Hakim (2026-10-20) : récupérées avec le jeton, jamais ouvertes comme une page — une image
   en aperçu, le reste téléchargé (un blob « octet-stream » + download : rien ne s'exécute dans l'origine du cockpit). */
function tailleLisible(n) { return n < 1024 ? `${n} o` : n < 1048576 ? `${Math.round(n / 1024)} Ko` : `${(n / 1048576).toFixed(1).replace('.', ',')} Mo`; }
var apercus = new Map();
async function blobPiece(id) {
  const r = await fetch(`/api/pieces/${encodeURIComponent(id)}`, { headers: { 'X-Jeton': jeton() } });
  if (!r.ok) throw new Error(r.status === 403 ? 'jeton refusé : recharge la page' : `pièce indisponible (${r.status})`);
  return r.blob();
}
async function chargerApercus() {
  for (const img of document.querySelectorAll('img[data-apercu]:not([src])')) {
    const id = img.dataset.apercu;
    try {
      if (!apercus.has(id)) apercus.set(id, URL.createObjectURL(await blobPiece(id)));
      img.src = apercus.get(id);
    } catch (_) { img.remove(); }
  }
}
$('fil').addEventListener('click', async (e) => {
  const b = e.target.closest('[data-piece]');
  if (!b) return;
  try {
    const brut = await blobPiece(b.dataset.piece);
    if (window.HakimApp) {                         // l'appli Android : le fichier va dans Téléchargements
      const b64 = await new Promise((ok, ko) => { const r = new FileReader(); r.onload = () => ok(String(r.result).split(',')[1] || ''); r.onerror = ko; r.readAsDataURL(brut); });
      humeur(window.HakimApp.enregistrer(b64, b.dataset.nom || 'piece') || 'fichier enregistré dans Téléchargements');
      return;
    }
    const url = URL.createObjectURL(new Blob([brut], { type: 'application/octet-stream' }));
    const a = document.createElement('a');
    a.href = url; a.download = b.dataset.nom || 'piece'; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  } catch (err) { humeur(String(err.message || err)); }
});

// Pendant le flux, seul le message en cours est redessiné (le reste du fil reste sélectionnable).
function majMessage(m) {
  const fil = $('fil');
  const el = fil.querySelector(`[data-id="${esc(m.id)}"]`);
  if (!el) return rendre();
  const enBas = fil.scrollHeight - fil.scrollTop - fil.clientHeight < 80;
  el.outerHTML = htmlMessage(m);
  if (enBas) fil.scrollTop = fil.scrollHeight;
  if ((m.pieces || []).length) chargerApercus();
}

function rendre() {
  const fil = $('fil');
  const enBas = fil.scrollHeight - fil.scrollTop - fil.clientHeight < 80;
  if (!etat.messages.length) {
    fil.innerHTML = `<div class="vide">Appuie sur le <b>micro</b> et parle : le micro se referme tout seul quand tu as fini,
      et la réponse s'affiche ici, avec <b>écouter</b> pour l'entendre.<br>Hakim connaît ta mémoire Anamnèse et la complète.</div>`;
    return;
  }
  etat.fenetre = Math.max(etat.fenetre || FENETRE, FENETRE);
  const caches = Math.max(0, etat.messages.length - etat.fenetre);
  fil.innerHTML = (caches ? `<button class="btn plus" data-plus="1">messages précédents (${caches})</button>` : '')
    + etat.messages.slice(-etat.fenetre).map(htmlMessage).join('');
  if (enBas) fil.scrollTop = fil.scrollHeight;
  chargerApercus();
}
$('fil').addEventListener('click', (e) => {
  if (e.target.closest('[data-plus]')) {                        // remonter dans le fil, sans perdre sa place
    const fil = $('fil'), avant = fil.scrollHeight - fil.scrollTop;
    etat.fenetre = (etat.fenetre || FENETRE) + FENETRE;
    rendre();
    fil.scrollTop = fil.scrollHeight - avant;
    return;
  }
  const cc = e.target.closest('[data-copier-code]');
  if (cc) {                                                     // le code seul, exactement tel qu'écrit
    const code = cc.closest('.bloc-code')?.querySelector('pre code')?.textContent || '';
    copierTexte(code).then((ok) => {
      cc.textContent = ok ? '✓ copié' : 'copie impossible';
      setTimeout(() => { cc.textContent = '📋 copier le code'; }, 1500);
    });
    return;
  }
  const c = e.target.closest('[data-copier]');
  if (c) {
    const mc = etat.messages.find(x => String(x.id) === c.dataset.copier);
    if (mc) copierTexte((mc.texte || '').replace(Voix.VOIX_SEULE, '').replace(/[ \t]+\n/g, '\n')).then((ok) => {
      c.textContent = ok ? '✓ copié' : 'copie impossible';
      setTimeout(() => { c.textContent = '📋 copier'; }, 1500);
    });
    return;
  }
  const b = e.target.closest('[data-lire]');
  if (!b) return;
  const m = etat.messages.find(x => String(x.id) === b.dataset.lire);
  if (m) lire(m);
});
// Copier un message (Ahmed, 2026-10-20) : le presse-papiers du navigateur (page sûre : localhost ou https), sinon
// l'ancienne méthode par une zone de texte
async function copierTexte(t) {
  try { await navigator.clipboard.writeText(t); return true; } catch (_) {}
  try {
    const z = document.createElement('textarea');
    z.value = t; z.setAttribute('readonly', ''); z.style.position = 'fixed'; z.style.opacity = '0';
    document.body.appendChild(z); z.select();
    const ok = document.execCommand('copy'); z.remove(); return ok;
  } catch (_) { return false; }
}

/* ---------- cerveau : /api/jarvis, réponse en flux ---------- */
const nouvelId = () => Date.now() + Math.floor(Math.random() * 1000);

// Le présent vécu (demande d'Ahmed : « conscient de chaque seconde ») : qui a parlé, quand, combien de
// temps, les pauses, les coupures ; envoyé à chaque message, Hakim le perçoit à la seconde près.
function noterPresent(ev) {
  etat.present.push(ev);
  const limite = Date.now() - 10 * 60 * 1000;
  etat.present = etat.present.filter(x => (x.fin || x.t || 0) > limite).slice(-60);
}
function noterParoleJarvis(parle) {
  if (parle && !etat.parleDepuis) { etat.parleDepuis = Date.now(); etat.coupeParAhmed = false; }
  else if (!parle && etat.parleDepuis) {
    noterPresent({ e: 'jarvis', debut: etat.parleDepuis, fin: Date.now(), coupe: etat.coupeParAhmed });
    etat.parleDepuis = 0;
  }
}

let envoiPrepare = null;
async function envoyer(texte, oral, dejaRelance) {
  texte = (texte || '').trim();
  if (etat.joints.some(x => !x.chemin && !x.erreur)) { humeur('fichiers en cours d’envoi…'); return; }   // le texte reste
  if (!dejaRelance && texte) {
    // doublons (vu le 2026-10-20 à 00:06:00 : cinq fois le même message, réseau lent) : PENDANT que l'envoi se
    // prépare (synchronisation), le même texte est ignoré et la zone est déjà vidée ; ensuite, un « oui »
    // répété repart normalement
    if (envoiPrepare === texte) return;
    envoiPrepare = texte;
    if (!oral && $('q').value.trim() === texte) { $('q').value = ''; ajuster(); }
  }
  try { if (!dejaRelance) await synchroniser(); }         // tu as peut-être parlé depuis l'autre appareil
  finally { if (envoiPrepare === texte) envoiPrepare = null; }
  const joints = dejaRelance ? (dejaRelance.joints || []) : etat.joints.filter(x => x.chemin);
  if (!texte && joints.length) texte = joints.length > 1 ? 'Regarde ces fichiers.' : 'Regarde ce fichier.';
  if (!texte) return;
  activite();
  contexteAudio();
  etat.dernierOral = !!oral;
  const dites = etat.dites.splice(0);
  if (!dejaRelance) { etat.joints.forEach(x => x.url && URL.revokeObjectURL(x.url)); etat.joints = []; rendreJoints(); }
  arreterTout(true, { garder: true });
  $('q').value = ''; ajuster();
  const avant = etat.messages.filter(x => x.qui === 'u' && x.ts);
  const tPrecedent = etat.session && avant.length ? avant[avant.length - (dejaRelance ? 2 : 1)]?.ts : null;
  const tDebut = etat.session && avant.length ? avant[0].ts : null;
  if (!dejaRelance) etat.messages.push({ id: nouvelId(), qui: 'u', texte, oral: !!oral, ts: Date.now(), joints: joints.map(x => x.nom) });
  const m = { id: nouvelId(), qui: 'j', texte: '', outils: [], enCours: true };
  etat.messages.push(m);
  sauver();                                              // la question survit à une fermeture de page
  const ctl = new AbortController();
  etat.flux = ctl; etat.fluxId = String(m.id);
  widgetApp('reflechit');
  rendre(); humeur();
  const decoupe = Voix.decoupeur();
  const auto = (etat.reglages.lectureAuto || etat.conversation || etat.reglages.volant) && lecteur;
  if (auto) etat.decoupeFlux = decoupe;                  // (23/10) sa phrase en cours d'arrivée, si on le coupe
  const camera = etat.vision ? await photoCamera() : null;
  const presentEnvoye = etat.present.slice(-40);
  if (etat.vision && etat.vision.courant)                                  // l'expression en cours, encore ouverte
    presentEnvoye.push({ e: 'visage', debut: etat.vision.depuis, fin: Date.now(), expr: etat.vision.courant, encours: true });
  if (!oral && !dejaRelance) noterPresent({ e: 'ecrit', t: Date.now() });
  let fin = null;
  try {
    const r = await fetch('/api/jarvis', {
      method: 'POST', signal: ctl.signal,
      headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() },
      body: JSON.stringify({ texte, oral: !!oral, modele: etat.conversation ? etat.reglages.modeleConversation : etat.reglages.modele, source: etat.reglages.source || 'auto', session: etat.session,
        t_precedent: tPrecedent, t_debut: tDebut, fichiers: joints.map(x => x.chemin), pensees_dites: dites,
        conversation: !!etat.conversation, present: presentEnvoye, maintenant: Date.now(), camera,
        appareil: appareilPage(), volant: !!etat.reglages.volant, position: positionAEnvoyer(), ecran: imageEcran(), tour_id: String(m.id) }),
    });
    if (!r.ok) throw new Error(r.status === 403 ? 'jeton refusé : recharge la page (le cockpit a redémarré)' : `erreur ${r.status}`);
    const lecteurFlux = r.body.getReader();
    const dec = new TextDecoder();
    let tampon = '';
    for (;;) {
      const { value, done } = await lecteurFlux.read();
      if (done) break;
      tampon += dec.decode(value, { stream: true });
      let i;
      while ((i = tampon.indexOf('\n')) >= 0) {
        const ligne = tampon.slice(0, i); tampon = tampon.slice(i + 1);
        let o; try { o = JSON.parse(ligne); } catch (_) { continue; }
        if (o.t === 'texte') {
          if (mesureTour && !mesureTour.premier_texte && o.x.trim()) mesureTour.premier_texte = Date.now();
          m.texte += o.x;
          orbeTete.pulser(0.05);
          if (auto) decoupe.ajouter(o.x).forEach(p => { if (NON_REPONSE.test(p)) return; etat.lectureDe = m.id; lecteur.dire(p); });
          majMessage(m); humeur(m.texte.length < 2 ? undefined : 'répond…');
        } else if (o.t === 'outil') {
          // (2026-10-22, Ahmed : « une réponse parlée AVANT l'outil ») la phrase qu'il a écrite avant d'appeler un outil part
          // à la voix TOUT DE SUITE : sans espace après son point, le découpeur l'aurait gardée jusqu'au texte d'après
          if (auto && !m.coupe) decoupe.finir().forEach(p => { if (NON_REPONSE.test(p)) return; etat.lectureDe = m.id; lecteur.dire(p); });
          const nom = String(o.nom || '').replace(/^mcp__anamnese__/, '');
          m.outils.push(NOMS_OUTILS[nom] || nom);
          majMessage(m); humeur(nom === 'WebSearch' ? 'cherche sur le web…' : 'cherche dans sa mémoire…');
        } else if (o.t === 'debut') {
          if (o.modele) { m.modele = o.modele; majMessage(m); }        // le routeur a choisi (Sonnet ou Opus)
        } else if (o.t === 'source') {                        // le forfait à sa limite : l'API, puis le local
          m.source = o.source;
          humeur(o.source === 'api' ? 'forfait à sa limite : je réponds par l’API' : 'je réponds avec mon cerveau local (sans mes outils)');
          majMessage(m);
        } else if (o.t === 'piece' && o.piece && /^\d{8}-\d{6}-[0-9a-f]{6}$/.test(String(o.piece.id))) {
          if (!(m.pieces || []).some(x => x.id === o.piece.id)) { m.pieces = (m.pieces || []).concat([o.piece]); majMessage(m); }
        } else if (o.t === 'session') {
          if (etat.flux === ctl) { etat.session = o.id; sauver(); }   // un « stop » ne perd plus la conversation
        } else if (o.t === 'fin') fin = o;
      }
    }
  } catch (e) {
    if (e.name === 'AbortError') m.coupe = true;
    else if (!/jeton refusé|erreur \d/.test(String(e.message || ''))) {
      // (2026-10-21) la connexion coupée (page en arrière-plan, téléphone en veille, réseau) : sur le Mac il termine
      // sa réponse ; elle arrive ici dès que la page la retrouve dans la conversation partagée
      m.attenteServeur = true;                    // la synchronisation (toutes les 5 s, et au retour sur la page) la ramène
    } else { m.erreur = String(e.message || e); etat.dites.unshift(...dites); }   // à redire au prochain envoi
  }
  if (etat.flux === ctl) etat.flux = null;
  m.enCours = false;
  if (m.texte) m.texte = Voix.sansAffect(m.texte).trimEnd();     // la balise [[affect: …]] ne reste pas dans la conversation
  if (fin) {
    m.ms = fin.ms;
    if (fin.source && fin.source !== 'abonnement') m.source = fin.source;
    if (fin.coupe) m.coupe = true;
    if (fin.jetons) m.jetons = fin.jetons;
    if (fin.session && etat.flux === null) etat.session = fin.session;
    if (fin.erreur) {
      // conversation introuvable (session effacée) : on repart d'une nouvelle, une seule fois
      if (/No conversation found/i.test(fin.erreur) && !dejaRelance) {
        etat.messages.splice(etat.messages.indexOf(m), 1);
        etat.session = null;
        return envoyer(texte, oral, { joints });
      }
      m.erreur = fin.erreur;
    }
  }
  if (auto && !m.coupe) { decoupe.finir().forEach(p => { if (NON_REPONSE.test(p)) return; etat.lectureDe = m.id; lecteur.dire(p); }); lecteur.finFlux(); }
  if (!m.texte && !m.erreur && !m.coupe && !m.attenteServeur) m.erreur = 'réponse vide';
  widgetApp(etat.conversation ? 'conversation' : 'repos', m.texte);
  sauver(); rendre(); humeur();
}

// (2026-10-21) le widget de l'appli Android : ce que fait Hakim (« reflechit », « conversation », « repos ») et la fin de
// sa dernière réponse en aperçu (sans les marques de mise en forme)
function widgetApp(quoi, texte) {
  try {
    if (!window.HakimApp || !window.HakimApp.widget) return;
    let t = Voix.sansAffect(texte).replace(/```[\s\S]*?```/g, ' ').replace(/\$\$[\s\S]*?\$\$/g, ' ').replace(/[*_`#>|]+/g, '')
      .replace(/\s+/g, ' ').trim();
    if (t.length > 140) t = '…' + t.slice(-140);
    window.HakimApp.widget(quoi, t);
  } catch (_) {}
}

// (2026-10-22, Ahmed : « l'orbe du widget mouvante quand je parle ou que Hakim parle ») qui parle, envoyé au widget de
// l'appli quand ça change : « parle » (sa voix joue), « ahmed » (ta voix, gardée 0,8 s après ton dernier son), « repos » sinon
let orbeWidget = '', ahmedJusqua = 0;
setInterval(() => {
  try {
    if (!window.HakimApp || !window.HakimApp.orbe) return;
    const c = etat.conversation;
    if ((c && c.capteur && c.capteur.enParole) || (etat.micro && !c)) ahmedJusqua = Date.now() + 800;
    const joue = lecteurNeuronal.joue || !!(lecteurSysteme && lecteurSysteme.actif);
    // sa voix : la palette de son humeur (comme l'orbe de la page) ; la tienne : le rose violet ; personne (15:49) :
    // l'orbe au repos du widget, dans la palette de son humeur
    const humeurCode = (etat.interieur && etat.interieur.humeur_code) || 'calme';
    const mode = joue ? `parle:${humeurCode}` : Date.now() < ahmedJusqua ? 'ahmed' : `repos:${humeurCode}`;
    if (mode !== orbeWidget) { orbeWidget = mode; window.HakimApp.orbe(mode); }
  } catch (_) {}
}, 250);

// (2026-10-22, Ahmed) la bulle flottante de l'appli Android : l'orbe vivante de Parler par-dessus les autres applis. Quand
// l'appli est cachée, la page lui envoie le vrai niveau des voix, au rythme du micro (une fenêtre sur trois, ~16 par
// seconde : ces messages de l'audio continuent page cachée, quand les minuteurs, eux, sont ralentis).
let bulleCompte = 0;
function alimenterBulle(niveauMicro) {
  try {
    if (!window.HakimApp || !window.HakimApp.bulleNiveau || (++bulleCompte % 3)) return;
    const c = etat.conversation;
    // personne ne parle : la palette de son humeur, comme l'orbe de la page au repos (15:55, Ahmed)
    const humeurCode = (etat.interieur && etat.interieur.humeur_code) || 'calme';
    // (16:10) il réfléchit (sa réponse est demandée, pas encore dite) : « pense », l'orbe tourne plus vite, comme dans Parler
    let mode = `${etat.flux ? 'pense' : 'repos'}:${humeurCode}`, n = 0, b = [0, 0, 0];
    const v = lecteurNeuronal.joue ? niveauVoix() : null;
    if (v) { mode = `parle:${humeurCode}`; n = v.niveau; b = v.bandes; }
    else if (c && c.capteur && c.capteur.enParole) { mode = 'ahmed'; n = niveauMicro; b = [n, n * 0.8, n * 0.6]; }
    window.HakimApp.bulleNiveau(mode, n, b[0], b[1], b[2]);
  } catch (_) {}
}
function afficherBulle(o) {
  if (!o) return;
  $('bulle').checked = !!o.active;
  $('bulleToujours').checked = !!o.toujours;
  $('orbeVerrou').checked = o.verrou !== false;
  $('etatBulle').textContent = (o.active || o.verrou) && !o.permise ? '(donne la permission « afficher par-dessus les autres applications » dans l’écran qui s’ouvre, puis reviens)' : '';
}
if (window.HakimApp && window.HakimApp.bulle) {
  $('groupeBulle').hidden = false;
  try { afficherBulle(JSON.parse(window.HakimApp.bulleEtat())); } catch (_) {}
  $('bulle').addEventListener('change', (e) => { try { afficherBulle(JSON.parse(window.HakimApp.bulle(e.target.checked))); } catch (_) {} });
}
// (2026-10-22, 15:45, Ahmed ; conception de Hakim) « Regarde l'écran » (appli Android) : Hakim voit l'écran du téléphone,
// quelle que soit l'appli ; une image (réduite) part avec chacun de tes messages tant que c'est allumé. Android demande ton
// accord à chaque fois ; l'appli dit quand ça commence ou s'arrête (ecranEtat), aussi quand Android l'arrête lui-même.
etat.ecran = false;
function ecranEtat(oui) {
  oui = !!oui;
  const change = oui !== etat.ecran;
  etat.ecran = oui;
  for (const id of ['ecran', 'ecranScene']) $(id).setAttribute('aria-pressed', oui ? 'true' : 'false');
  $('ecran').textContent = oui ? '👁 Écran' : 'Écran';
  $('ecranScene').textContent = oui ? '👁 Hakim regarde ton écran' : 'Regarde l’écran';
  if (change) humeur(oui ? 'Hakim regarde ton écran : une image part avec chacun de tes messages' : 'Hakim ne regarde plus ton écran');
}
// (16:15, bug : Hakim ne recevait rien) l'état est relu dans l'appli au moment d'envoyer (un ecranEtat(true) perdu ne
// coupe plus l'image), et chaque envoi écran allumé laisse une trace au diagnostic (taille, raison) — jamais l'image
function imageEcran() {
  if (!window.HakimApp || !window.HakimApp.ecranImage) return undefined;
  let actif = etat.ecran;
  try { if (!actif && window.HakimApp.ecranEtat && window.HakimApp.ecranEtat()) { actif = true; ecranEtat(true); } } catch (_) {}
  if (!actif) return undefined;
  let d = '', raison = '';
  try { d = window.HakimApp.ecranImage() || ''; } catch (_) { raison = 'exception'; }
  // la raison est un code court (le diagnostic n'accepte que [a-z_]) : pas_de_service, verrouille, pas_d_image, erreur…
  if (!d && !raison) try { raison = window.HakimApp.ecranRaison ? String(window.HakimApp.ecranRaison()) : 'image_vide'; } catch (_) {}
  journalVoix('ecran', { taille: d.length, raison: raison || undefined });
  return d ? { data: d } : undefined;
}
if (window.HakimApp && window.HakimApp.ecran) {
  for (const id of ['ecran', 'ecranScene']) {
    $(id).hidden = false;
    $(id).addEventListener('click', (e) => { e.stopPropagation(); try { window.HakimApp.ecran(!etat.ecran); } catch (_) {} });
  }
  try { ecranEtat(window.HakimApp.ecranEtat()); } catch (_) {}
}

// (2026-10-22, 15:28) appli 0.8 : la bulle aussi hors conversation, et l'orbe sur l'écran de verrouillage
if (window.HakimApp && window.HakimApp.bulleOption) {
  $('groupeBulleToujours').hidden = false;
  $('groupeOrbeVerrou').hidden = false;
  for (const [id, nom] of [['bulleToujours', 'toujours'], ['orbeVerrou', 'verrou']])
    $(id).addEventListener('change', (e) => { try { afficherBulle(JSON.parse(window.HakimApp.bulleOption(nom, e.target.checked))); } catch (_) {} });
}

// « coupé » s'affiche sous la réponse qu'il n'a pas pu finir de dire
function marquerCoupe() {
  if (!lecteur.actif && !lecteur.enPause && !etat.flux) return;
  const lu = etat.messages.find(m => m.id === etat.lectureDe) || [...etat.messages].reverse().find(m => m.qui === 'j');
  if (lu) { lu.coupe = true; sauver(); rendre(); }
}
// (2026-10-23, Ahmed : « rien n'est jamais jeté ») garder : Ahmed reprend la parole ou envoie un autre message — ce que
// Hakim n'a pas pu dire part dans la file d'attente (aDire) et sera dit au premier moment calme. Un « stop » explicite
// (le mot, le bouton, Échap) ne garde rien : c'est Ahmed qui le veut.
function arreterTout(explicite = true, { garder = false } = {}) {
  if (garder) garderNonDit();
  etat.decoupeFlux = null;
  if (etat.flux) {
    // (2026-10-21) Stop EXPLICITE : sans lui, le cockpit laisse la réponse aller au bout (page partie ≠ Stop)
    if (explicite && etat.fluxId) fetch('/api/jarvis/stop', { method: 'POST', keepalive: true,
      headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() }, body: JSON.stringify({ tour_id: etat.fluxId }) }).catch(() => {});
    etat.flux.abort(); etat.flux = null; etat.fluxId = null;
  }
  if (etat.transcription) { etat.transcription.abort(); etat.transcription = null; }
  if (lecteur) lecteur.arreter();
  etat.lectureDe = null;
}

/* ---------- micro ponctuel ---------- */
function erreurMicro(msg) {
  arreterMicro(false);
  humeur(msg);
  setTimeout(() => humeur(), 5000);
}

/* ---------- la vision (caméra) ---------- */
async function basculerCamera() {
  activite();
  if (etat.vision) return arreterCamera();
  const v = { capteur: null, courant: null, depuis: 0, candidat: null, candidatDepuis: 0 };
  etat.vision = v;
  $('camera').setAttribute('aria-pressed', 'true');
  $('vision').hidden = false;
  $('expression').textContent = 'ouverture…';
  try {
    v.capteur = await Vision.demarrer({
      video: $('apercu'),
      surMesure: (m) => surVisage(v, m),
      surErreur: (msg) => { $('expression').textContent = 'caméra seule'; humeur(msg); },
    });
  } catch (e) {
    if (etat.vision !== v) return;
    etat.vision = null;
    $('camera').setAttribute('aria-pressed', 'false');
    $('vision').hidden = true;
    humeur('caméra refusée ou indisponible : autorise-la pour localhost'); setTimeout(() => humeur(), 5000);   // sans toucher au micro
    return;
  }
  if (etat.vision !== v) { v.capteur.arreter(); return; }
  noterPresent({ e: 'camera', t: Date.now() });
  humeur();
}

function arreterCamera() {
  const v = etat.vision;
  if (!v) return;
  fermerExpression(v, Date.now());
  etat.vision = null;
  if (v.capteur) v.capteur.arreter();
  $('camera').setAttribute('aria-pressed', 'false');
  $('vision').hidden = true;
  noterPresent({ e: 'camera_fin', t: Date.now() });
}

// Une expression ne compte que si elle tient 1,2 s ; le présent vécu garde celles d'au moins 1,5 s.
function surVisage(v, m) {
  const maintenant = Date.now();
  if (m.expression !== v.candidat) { v.candidat = m.expression; v.candidatDepuis = maintenant; }
  if (v.candidat !== v.courant && maintenant - v.candidatDepuis >= 1200) {
    fermerExpression(v, v.candidatDepuis);
    v.courant = v.candidat; v.depuis = v.candidatDepuis;
    $('expression').textContent = v.courant;
  }
}
function fermerExpression(v, fin) {
  if (v.courant && v.courant !== 'neutre' && fin - v.depuis >= 1500)
    noterPresent({ e: 'visage', debut: v.depuis, fin, expr: v.courant });
}

async function photoCamera() {
  const v = etat.vision;
  if (!v || !v.capteur) return null;
  try {
    const jpeg = await v.capteur.capturer();
    if (!jpeg) return null;
    const nom = `camera-${new Date().toISOString().replace(/[-:]/g, '').slice(0, 15)}.jpg`;
    const r = await fetch('/api/jarvis/fichier', { method: 'POST', body: jpeg,
      headers: { 'X-Jeton': jeton(), 'X-Nom': nom, 'Content-Type': 'image/jpeg' } });
    const o = await r.json();
    return o.chemin || null;
  } catch (_) { return null; }
}

/* ---------- fin de phrase anticipée (demande d'Ahmed : « répondre plus vite quand je finis de parler ») ----
   Dès 0,7 s de silence, ta phrase est transcrite EN AVANCE. Si tu n'as pas repris la parole et qu'elle
   semble finie (ponctuation finale, pas de « et », « mais », « euh »… à la fin), le tour se clôt tout
   de suite au lieu d'attendre toute la patience ; sinon on attend, comme avant : les hésitations
   restent permises. Gain mesuré : ~2,8 s (patience 3,5 s → 0,7 s, transcription déjà faite). */
const SILENCE_ANTICIPE_MS = 700;
const FIN_SUSPENDUE = /^(et|mais|donc|parce|que|qu|qui|ou|où|alors|euh|heu|hum|bah|ben|genre|enfin|puis|avec|pour|de|du|des|le|la|les|un|une|à|au|aux|en|sur|dans|par|car|si|quand|comme|je|tu|il|elle|on|nous|vous|mon|ma|mes|ton|ta|tes|son|sa|ses|ce|cette|ces|est|c'est|y|ya|wallah)$/i;
function phraseFinie(t) {
  const x = String(t || '').trim();
  if (!Conversation.utile(x) || /(\.\.\.|…|,)$/.test(x) || !/[.!?؟]$/.test(x)) return false;
  const dernier = x.replace(/[.!?؟]+$/, '').trim().split(/\s+/).pop() || '';
  return !FIN_SUSPENDUE.test(dernier.replace(/[^\p{L}']/gu, ''));
}
// Rend le texte ('' si rien n'a été dit), ou null si la transcription a ÉCHOUÉ (processus voix arrêté,
// délai) : un échec ne doit jamais passer pour du silence (relecture Opus : 3,6 s de phrase perdues).
async function transcrireVite(audio, type, contexte) {
  const langue = etat.reglages.langue === 'auto' ? '' : etat.reglages.langue.slice(0, 2);
  const ctx = contexte ? `&contexte=${encodeURIComponent(contexte.slice(-200))}` : '';
  const ctl = new AbortController(), t0 = Date.now();
  const minuteur = setTimeout(() => ctl.abort(), 25000);         // (2026-10-21) jamais d'attente sans fin
  try {
    const r = await fetch(`/api/voix/transcrire?langue=${langue}${ctx}`, { method: 'POST', body: audio, signal: ctl.signal,
      headers: { 'Content-Type': type || 'audio/wav', 'X-Jeton': jeton() } });
    const o = await r.json().catch(() => null);
    if (!r.ok || !o || o.erreur) { journalVoix('transcription_echec', { statut: r.status, ms: Date.now() - t0 }); return null; }
    if (Date.now() - t0 > 8000) journalVoix('transcription_lente', { ms: Date.now() - t0 });
    return (o.texte || '').trim();
  } catch (e) {
    journalVoix(e && e.name === 'AbortError' ? 'transcription_trop_longue' : 'transcription_erreur', { ms: Date.now() - t0 });
    return null;
  } finally { clearTimeout(minuteur); }
}
// Whisper, amorcé par ce qu'il a déjà compris, le répète parfois sur un morceau presque muet : un
// morceau déjà contenu dans le texte compris est écarté (ainsi que ses inventions sur le silence).
const sansAccents = (x) => String(x || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^\p{L}\p{N}]+/gu, ' ').trim();
function morceauNeuf(texte, deja) {
  if (!Conversation.utile(texte)) return '';
  const t = sansAccents(texte);
  return t.length >= 8 && sansAccents(deja).includes(t) ? '' : texte;
}
// Transcription EN CONTINU (demande d'Ahmed) : à chaque respiration, si plus de 3 s ont été dites depuis
// le dernier morceau, ce morceau est transcrit pendant que tu continues ; à la fin, il ne reste que la
// queue de ta phrase à transcrire (et le texte déjà compris sert de contexte à Whisper).
// L'état est PAR TOUR (conv.ecrit, neuf à chaque début de parole) : un morceau qui revient après que tu
// as repris la parole ne se mélange jamais à ta phrase suivante.
function surPauseConversation(conv, fenetre) {
  const e = conv.ecrit;
  if (!conv.capteur || !e || e.partiel || fenetre - e.coupe < 150) return;
  const de = e.coupe, wav = conv.capteur.segment(de, fenetre);
  if (!wav) return;                                                      // pas de voix dans ce morceau
  e.partiel = transcrireVite(wav, 'audio/wav', e.confirme).then((texte) => {
    if (e.coupe !== de || texte === null) return;                        // échec : ce morceau reste dans la queue
    e.confirme = (e.confirme + ' ' + morceauNeuf(texte, e.confirme)).trim();   // une invention de Whisper : écartée seule
    e.coupe = fenetre;
  }).finally(() => { e.partiel = null; });
}
// Le texte du tour : le déjà compris + la queue. null si la queue n'a pas pu être transcrite (l'appelant
// retranscrit alors le tour entier). Le tour fini est saisi AVANT d'attendre : un autre tour qui se
// finirait pendant l'attente ne prête pas sa queue à celui-ci (relecture Opus).
async function texteDuTour(conv) {
  const e = conv.ecrit, capteur = conv.capteur;
  if (!e || !capteur) return e ? e.confirme : '';
  const tourFini = capteur.enParole ? null : capteur.dernierTour;
  if (e.partiel) await e.partiel;                                        // le morceau en cours d'abord
  const morceau = tourFini ? capteur.segmentFini(e.coupe, tourFini) : capteur.segment(e.coupe);
  const queue = morceau ? await transcrireVite(morceau, 'audio/wav', e.confirme) : '';   // la queue n'est souvent que du silence
  if (queue === null) return null;
  return (e.confirme + ' ' + morceauNeuf(queue, e.confirme)).trim();
}
function anticiperConversation(conv, silenceMs) {
  if (etat.reglages.rapide === false || silenceMs < SILENCE_ANTICIPE_MS || conv.spec || !conv.capteur) return;
  // un seul essai par silence (relecture Opus : la même queue était retranscrite ~10 fois par pause)
  if (conv.essaiVoix === conv.capteur.derniereVoix || !conv.capteur.assezDeVoix) return;
  conv.essaiVoix = conv.capteur.derniereVoix;
  const sp = { voix: conv.capteur.derniereVoix };
  conv.spec = sp;
  texteDuTour(conv).then((texte) => {                                   // seulement la queue, déjà le reste
    if (conv.spec === sp) conv.spec = null;
    if (etat.conversation !== conv || !conv.capteur || !conv.capteur.enParole) return;
    if (conv.capteur.derniereVoix !== sp.voix) return;                 // tu as repris la parole : on attend
    if (texte !== null && phraseFinie(texte)) conv.capteur.finirTour({ texte });
  });
}

/* ---------- mode Conversation (étape 6) ---------- */
// Ancrées sur toute la phrase (relecture Opus : « …à la fin de la conversation d'hier » fermait tout).
const NOM = '(jarvis|hakim|hakou|hakimou)';
const COMMANDE_STOP = new RegExp(`^\\s*(${NOM}[\\s,.!]*)?(stop|arr[êe]te(-toi)?|tais-toi|chut)([\\s,.!]*(${NOM}))?[\\s.!]*$`, 'i');
const COMMANDE_FIN = new RegExp(`^\\s*(${NOM}[\\s,.!]*)?(fin de (la )?conversation|on arr[êe]te (la conversation|là)|au revoir( ${NOM})?|bonne nuit( ${NOM})?)[\\s.!]*$`, 'i');
// Pause et reprise de sa voix (lot C, point 26) : il garde ce qu'il n'a pas dit et reprend à cette phrase
const COMMANDE_PAUSE = new RegExp(`^\\s*(${NOM}[\\s,.!]*)?(pause|attends?|une (petite )?seconde|deux secondes|une minute|minute)([\\s,.!]*(${NOM}|stp|s'il te plaît))?[\\s.!]*$`, 'i');
const COMMANDE_VOLANT = new RegExp(`^\\s*(${NOM}[\\s,.!]*)?(mode (volant|voiture)|je (conduis|suis au volant))([\\s,.!]*(${NOM}))?[\\s.!]*$`, 'i');
const COMMANDE_FIN_VOLANT = new RegExp(`^\\s*(${NOM}[\\s,.!]*)?(fin du mode (volant|voiture)|je (ne conduis plus|suis arrivée?))([\\s,.!]*(${NOM}))?[\\s.!]*$`, 'i');
const COMMANDE_REPRISE = new RegExp(`^\\s*((c'est bon|ok|vas-y|vas y|allez)[\\s,.!]*)?(${NOM}[\\s,.!]*)?(reprends|continue|poursuis|vas-y|vas y|je t'?écoute|c'est bon)([\\s,.!]*(${NOM}))?[\\s.!]*$`, 'i');
function pauseVoix() {
  if (!lecteur.pause()) return false;
  noterPresent({ e: 'pause_voix', t: Date.now() });
  majBoutonsPause(); humeur('en pause : « continue » pour que je reprenne');
  return true;
}
function reprendreVoix() {
  if (!lecteur.reprendre()) return false;
  noterPresent({ e: 'reprise_voix', t: Date.now() });
  majBoutonsPause(); humeur();
  return true;
}
function majBoutonsPause() {
  const p = lecteur.enPause;
  for (const id of ['pauseScene', 'pause']) { const b = $(id); if (b) { b.textContent = p ? 'Reprendre' : 'Pause'; b.setAttribute('aria-pressed', String(p)); } }
  signalerWidget();
}
// (2026-10-21) couper / rendre le son de Hakim (bouton « haut-parleur » du widget de l'appli Android)
function couperSon(oui = !etat.sonCoupe) {
  etat.sonCoupe = !!oui;
  if (gainSortie) gainSortie.gain.value = etat.sonCoupe ? 0 : 1;
  lecteurNeuronal.appliquerSon();
  humeur(etat.sonCoupe ? 'son coupé : je continue sans bruit' : 'son rétabli');
  signalerWidget();
}
// l'état des boutons du widget (conversation, pause, son, micro), envoyé seulement quand il change
let dernierEtatWidget = '';
function signalerWidget() {
  try {
    if (!window.HakimApp || !window.HakimApp.boutons) return;
    const c = etat.conversation;
    const e = JSON.stringify({ conversation: !!c, pause: !!lecteur.enPause, son_coupe: !!etat.sonCoupe,
      micro_coupe: !!(c && c.capteur && c.capteur.estMuet) });
    if (e === dernierEtatWidget) return;
    dernierEtatWidget = e;
    window.HakimApp.boutons(e);
  } catch (_) {}
}
const patienceConversation = () => (Number.isFinite(patienceMs()) ? patienceMs() : 3500);   // « jamais » : pas en conversation

async function basculerConversation() {
  activite();
  if (etat.conversation) return finirConversation();
  arreterMicro(false);
  contexteAudio();
  if (!actx) return humeur('audio indisponible dans ce navigateur');
  if (!etat.sttLocal) return humeur('le mode Conversation demande Whisper local (réglages › reconnaissance)');
  const conv = { capteur: null, enAttente: 0 };
  etat.conversation = conv;
  $('conversation').setAttribute('aria-pressed', 'true');
  humeur('ouverture du micro…');
  try {
    conv.capteur = await Conversation.demarrer({
      ctx: actx,
      patienceMs: patienceConversation,
      jarvisParle: () => lecteur.actif,
      surNiveau: (n) => { etat.niveauMicro = n; if (document.visibilityState === 'hidden') { micEnFond++; alimenterBulle(n); } },
      surDebut: () => { conv.finDemandee = false; conv.ecrit = { coupe: 0, confirme: '', partiel: null }; sousTitre('…'); humeur('je t’écoute…'); },
      surPause: (fenetre) => surPauseConversation(conv, fenetre),
      surSilence: (ms) => { if (conv.capteur && conv.capteur.enParole) { compteARebours(ms); anticiperConversation(conv, ms); } },
      // Ahmed (ou une autre voix) parle pendant que Hakim parle : Hakim se MET EN PAUSE (lot C, point 26) ; sa
      // réponse continue d'arriver. À la fin du tour : « continue » ou du bruit → il reprend à la phrase non
      // dite ; « stop » → il lâche tout ; une vraie question → il lâche le reste et y répond.
      niveauSortie,
      surInterruption: (mesure) => {
        etat.coupeParAhmed = true;
        journalVoix('coupure', mesure || {});
        noterPresent({ e: 'coupure', t: Date.now() });
        if (!lecteur.pause()) { if (lecteur.actif) lecteur.arreter(); }
        majBoutonsPause();
        humeur('je t’écoute…');
      },
      surFin: (wav, infos, extra) => tourDeParole(conv, wav, infos, extra),
    });
  } catch (e) {
    if (etat.conversation !== conv) return;
    etat.conversation = null;
    $('conversation').setAttribute('aria-pressed', 'false');
    humeur('micro refusé ou indisponible : autorise-le pour localhost'); setTimeout(() => humeur(), 5000);
    return;
  }
  if (etat.conversation !== conv) { conv.capteur.arreter(); return; }    // arrêtée pendant l'ouverture
  noterPresent({ e: 'debut_conversation', t: Date.now() });
  sessionMedia(true);
  garderEcranAllume(true);
  try { if (window.HakimApp) window.HakimApp.conversation(true); } catch (_) {}   // l'appli Android : micro gardé écran éteint
  signalerWidget();
  signalerPresence();                              // tout de suite : le subconscient se met en pause
  rendre(); humeur();
}

function basculerMuet() {
  const conv = etat.conversation;
  if (!conv || !conv.capteur) return;
  const oui = !conv.capteur.estMuet;
  conv.capteur.muet(oui);
  for (const id of ['muet', 'muetScene']) {
    $(id).setAttribute('aria-pressed', oui ? 'true' : 'false');
    $(id).textContent = oui ? (id === 'muet' ? 'Micro coupé' : 'Rouvrir mon micro') : (id === 'muet' ? 'Muet' : 'Couper mon micro');
  }
  noterPresent({ e: oui ? 'muet' : 'micro_rouvert', t: Date.now() });
  humeur(oui ? 'micro coupé : je ne t’entends plus (⌥X pour rouvrir)' : 'je t’écoute…');
  signalerWidget();
}

// garderLeTour (Ahmed, 2026-10-20) : fermer la conversation PENDANT qu'on parle (bouton du micro, « Fin ») envoie
// quand même ce qui a été dit jusque-là ; Échap et la fermeture de la page, eux, abandonnent le tour.
/* La conversation en ARRIÈRE-PLAN (2026-10-21, Ahmed : « continuer à converser quand je quitte la page ») : rien ne
   la coupe quand la page passe derrière (autre appli, écran éteint) ; une session média (la notification du
   téléphone, avec Muet et Terminer) dit au navigateur qu'une conversation est en cours et l'aide à garder la page en
   vie. Ce que le navigateur permet vraiment (micro et voix en arrière-plan) se lit dans le diagnostic de la voix :
   combien de morceaux de micro sont arrivés pendant que la page était cachée. Navigateur fermé : impossible. */
let micEnFond = 0, cacheeDepuis = 0, verrouEcran = null;
async function garderEcranAllume(oui) {
  try {
    if (!oui) { if (verrouEcran) await verrouEcran.release(); verrouEcran = null; return; }
    if ('wakeLock' in navigator && document.visibilityState === 'visible' && !verrouEcran) {
      verrouEcran = await navigator.wakeLock.request('screen');
      verrouEcran.addEventListener('release', () => { verrouEcran = null; });
    }
  } catch (_) { verrouEcran = null; }
}
function sessionMedia(active) {
  if (!('mediaSession' in navigator)) return;
  try {
    if (!active) { navigator.mediaSession.playbackState = 'none'; return; }
    navigator.mediaSession.metadata = new MediaMetadata({ title: 'Conversation avec Hakim', artist: 'Hakim',
      artwork: [{ src: '/icone-192.png', sizes: '192x192', type: 'image/png' }, { src: '/icone-512.png', sizes: '512x512', type: 'image/png' }] });
    navigator.mediaSession.playbackState = 'playing';
    const muet = (veut) => { const c = etat.conversation; if (c && c.capteur && c.capteur.estMuet !== veut) basculerMuet(); };
    navigator.mediaSession.setActionHandler('pause', () => { muet(true); navigator.mediaSession.playbackState = 'paused'; });
    navigator.mediaSession.setActionHandler('play', () => { muet(false); navigator.mediaSession.playbackState = 'playing'; });
    navigator.mediaSession.setActionHandler('stop', () => finirConversation(true));
  } catch (_) {}
}
document.addEventListener('visibilitychange', () => {
  if (!etat.conversation) return;
  if (document.visibilityState === 'hidden') { cacheeDepuis = Date.now(); micEnFond = 0; journalVoix('conversation_cachee', { audio: actx ? actx.state : 'aucun' }); }
  else {
    if (cacheeDepuis) journalVoix('conversation_revenue', { cachee_ms: Date.now() - cacheeDepuis, micro_morceaux: micEnFond, audio: actx ? actx.state : 'aucun' });
    cacheeDepuis = 0;
    contexteAudio();
    garderEcranAllume(true);                       // le verrou d'écran tombe quand la page se cache : on le reprend
  }
});
function finirConversation(garderLeTour = true) {
  const conv = etat.conversation;
  if (!conv) return;
  sessionMedia(false);
  garderEcranAllume(false);
  try { if (window.HakimApp) window.HakimApp.conversation(false); } catch (_) {}
  if (garderLeTour && conv.capteur && conv.capteur.enParole) { conv.fermeture = true; conv.capteur.finirTour(); }
  etat.conversation = null;
  if (conv.capteur) conv.capteur.arreter();
  etat.niveauMicro = 0;
  for (const id of ['muet', 'muetScene']) $(id).setAttribute('aria-pressed', 'false');
  $('muet').textContent = 'Muet'; $('muetScene').textContent = 'Couper mon micro';
  $('conversation').setAttribute('aria-pressed', 'false');
  noterPresent({ e: 'fin_conversation', t: Date.now() });
  sousTitre('');
  humeur();
  signalerWidget();
}

// Le ton de ta voix comparé à TON habitude (lot C, point 20) : hauteur, débit (mots par seconde de voix), énergie.
// L'habitude s'apprend sur tes tours (moyenne lente, gardée dans ce navigateur) ; rien n'est dit avant 5 tours.
function tonRelatif(infos, texte) {
  const t = infos && infos.ton;
  const mots = String(texte || '').trim().split(/\s+/).filter(Boolean).length;
  if (!t || !infos.voix_ms || mots < 3) return null;
  const mesure = { f0: t.f0, db: t.energie_db, debit: mots / (infos.voix_ms / 1000) };
  let base = null; try { base = JSON.parse(localStorage.getItem('jarvis.ton') || 'null'); } catch (_) {}
  const rel = base && base.n >= 5 ? { hauteur: (mesure.f0 - base.f0) / base.f0, debit: (mesure.debit - base.debit) / base.debit,
    energie: mesure.db - base.db } : null;
  const a = base ? Math.max(0.1, 1 / (base.n + 1)) : 1;
  base = base || { f0: mesure.f0, db: mesure.db, debit: mesure.debit, n: 0 };
  for (const k of ['f0', 'db', 'debit']) base[k] += a * (mesure[k] - base[k]);
  base.n += 1;
  try { localStorage.setItem('jarvis.ton', JSON.stringify(base)); } catch (_) {}
  return rel;
}

// (2026-10-22, la « voix rapide » : mesurer avant de toucher) où passe le temps d'un tour oral, de la fin de ta parole à
// son premier son : attente de la fin de tour, transcription, premier mot de Hakim, voix. Au journal de diagnostic.
let mesureTour = null;
function finMesureTour() {
  const m = mesureTour;
  mesureTour = null;
  if (!m || !m.premier_texte) return;
  const ms = (a, b) => (a && b ? Math.max(0, Math.round(a - b)) : -1);
  journalVoix('tour_temps', { attente_fin_tour_ms: ms(m.debut, m.fin), transcription_ms: ms(m.transcrit, m.debut),
    premier_mot_ms: ms(m.premier_texte, m.transcrit), voix_ms: ms(m.premier_son, m.premier_texte), total_ms: ms(m.premier_son || m.premier_texte, m.fin),
    son: !!m.premier_son });
}
async function tourDeParole(conv, wav, infos, extra) {
  const vivante = () => etat.conversation === conv || conv.fermeture;     // le dernier tour d'une conversation fermée
  if (!vivante()) return;
  const t0Tour = Date.now();
  conv.spec = null;
  conv.enAttente++;
  humeur('transcription…');
  let texte = '';
  try {                                   // (2026-10-21) toujours rendu : sinon sa voix attendait ton tour pour toujours
    // fin anticipée : la phrase est déjà transcrite ; sinon, la partie déjà comprise + la queue
    texte = extra && extra.texte ? extra.texte
      : (conv.ecrit && (conv.ecrit.confirme || conv.ecrit.partiel) ? await texteDuTour(conv) : await transcrireVite(wav, 'audio/wav'));
    if (texte === null && conv.ecrit && conv.ecrit.confirme) texte = await transcrireVite(wav, 'audio/wav');   // un morceau a échoué : le tour entier
  } catch (e) { journalVoix('tour_erreur'); texte = ''; }
  finally { conv.enAttente = Math.max(0, conv.enAttente - 1); }
  texte = texte || '';
  if (!vivante()) return;
  conv.fermeture = false;                                                   // ce dernier tour, une seule fois
  if (!Conversation.utile(texte)) { journalVoix('tour_bruit', { coupure: !!etat.coupeParAhmed }); if (!reprendreVoix()) humeur(); return; }      // bruit, une autre voix : il reprend
  // (2026-10-22) ses phrases revenues par le haut-parleur, collées à la tienne : retirées ; s'il ne reste presque rien,
  // c'était son écho
  const sansEcho = retirerEcho(texte);
  if (sansEcho.retire) {
    journalVoix('echo_retire', { mots: sansEcho.retire, reste: sansEcho.texte.split(/\s+/).filter(Boolean).length });
    if (sansEcho.texte.split(/\s+/).filter(m => m.length >= 2).length < 2) { if (!reprendreVoix()) humeur(); return; }
    texte = sansEcho.texte;
  }
  // (2026-10-21) sa propre voix revenue par le micro : ce n'est pas toi qui parles, il reprend
  if (estSonEcho(texte)) { journalVoix('echo_reconnu', { mots: texte.split(/\s+/).length }); if (!reprendreVoix()) humeur(); return; }
  noterPresent({ e: 'ahmed', debut: infos.debut, fin: infos.fin, pauses: infos.pauses, ton: tonRelatif(infos, texte) });
  activite();
  if (COMMANDE_STOP.test(texte)) { marquerCoupe(); arreterTout(); rendre(); humeur(); return; }   // « stop » : il lâche tout
  // « continue » avec une voix en pause : il reprend ; sans rien en pause (il avait fini, ou la voix du Mac qui
  // ne sait pas reprendre), « continue » part à Hakim comme une demande : il poursuit son idée
  if (COMMANDE_REPRISE.test(texte) && lecteur.enPause) { reprendreVoix(); return; }
  if (COMMANDE_PAUSE.test(texte)) { if (!lecteur.enPause) pauseVoix(); else humeur('en pause : « continue » pour que je reprenne'); return; }
  if (COMMANDE_VOLANT.test(texte) && !etat.reglages.volant) reglerVolant(true);             // puis il le lui dit (envoyé)
  else if (COMMANDE_FIN_VOLANT.test(texte) && etat.reglages.volant) reglerVolant(false);
  // une vraie question : il y répond d'abord ; le reste, gardé, sera dit au premier moment calme (23/10)
  if (lecteur.enPause || etat.flux) { marquerCoupe(); arreterTout(true, { garder: true }); }
  sousTitre(texte);
  mesureTour = { fin: Number(infos && (infos.derniere_voix || infos.fin)) || t0Tour, debut: t0Tour, transcrit: Date.now(), premier_texte: 0, premier_son: 0 };
  await envoyer(texte, true);
  if (mesureTour && mesureTour.premier_texte) setTimeout(() => { if (mesureTour && !mesureTour.premier_son) finMesureTour(); }, 20000);
  if (COMMANDE_FIN.test(texte)) {                                         // il répond au revoir, puis on ferme
    conv.finDemandee = true;
    const attendre = () => {
      if (etat.conversation !== conv || !conv.finDemandee) return;          // tu as repris la parole : on reste
      if (lecteur.actif || etat.flux) setTimeout(attendre, 300); else finirConversation();
    };
    attendre();
  }
}

function basculerMicro() {
  if (etat.conversation) return finirConversation();      // le micro ponctuel et la conversation ne se mêlent pas
  activite();
  if (etat.transcription) return;                        // transcription en cours : micro verrouillé
  if (etat.micro) return etat.micro.attente ? undefined : arreterMicro(true);   // re-clic : « j'ai fini »
  arreterTout(true, { garder: true });                   // on coupe Hakim quand Ahmed reprend la parole (le reste est gardé)
  if (etat.reglages.reconnaissance === 'locale' && etat.sttLocal) return ecouterLocal();
  return ecouterNavigateur();
}

function arreterMicro(envoyerLeTexte) {
  const mic = etat.micro;
  if (!mic) return;
  if (mic.attente) { etat.micro = null; etatMicro(false); return; }
  mic.envoyer = envoyerLeTexte;
  mic.arreter();
}

function etatMicro(actif) {
  $('micro').setAttribute('aria-pressed', actif ? 'true' : 'false');
  if (!actif) { $('micro').style.transform = ''; etat.niveauMicro = 0; sousTitre(''); $('indice').textContent = INDICE; }
  humeur();
}

// Reconnaissance du navigateur : rien à installer (Chrome l'envoie aux serveurs de Google,
// Safari à ceux d'Apple). Une seule langue à la fois : le mélange passera par Whisper.
// Patience du micro (demande d'Ahmed, 2026-10-16 : « on réfléchit, on hésite pendant qu'on parle ») :
// le micro ne se ferme qu'après `patience` secondes de silence APRÈS avoir parlé ; 0 = jamais (re-clic).
const patienceMs = () => (Number(etat.reglages.patience) > 0 ? Number(etat.reglages.patience) * 1000 : Infinity);
const RIEN_ENTENDU_MS = 12000;            // aucune parole du tout : on referme
const PAROLE_MAX_MS = 5 * 60 * 1000;      // un long développement passe, au-delà on referme

const INDICE = "clic : masquer (ou « j'ai fini » quand il t'écoute) · Échap : arrêter";
let dernierCompte = '';
function compteARebours(silenceMs) {
  const cle = silenceMs > 900 ? String(Math.ceil((patienceMs() - silenceMs) / 1000)) : '-';
  if (cle === dernierCompte) return;                     // au plus une mise à jour par seconde affichée
  dernierCompte = cle;
  const reste = patienceMs() - silenceMs;
  if (silenceMs > 900 && Number.isFinite(reste)) {
    const s = Math.max(1, Math.ceil(reste / 1000));
    humeur(`je t’écoute… (je ferme dans ${s} s, clique pour finir)`);
    $('indice').textContent = `je ferme dans ${s} s · clic : j'ai fini · Échap : arrêter`;   // visible aussi sur la scène
  } else { humeur('je t’écoute…'); $('indice').textContent = INDICE; }
}

function ecouterNavigateur() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) return erreurMicro('reconnaissance vocale absente de ce navigateur : essaie Chrome ou Safari');
  const r = new SR();
  r.lang = etat.reglages.langue === 'auto' ? 'fr-FR' : etat.reglages.langue;
  r.interimResults = true;
  r.continuous = true;                    // sinon Chrome coupe au premier petit silence
  let final = '', dernierMot = 0, minuteur = null;
  const debut = performance.now();
  const mic = { envoyer: true, arreter: () => { clearInterval(minuteur); try { r.stop(); } catch (_) {} } };
  etat.micro = mic;
  minuteur = setInterval(() => {         // notre propre patience : silence depuis le dernier mot reconnu
    const t = performance.now();
    if (!dernierMot) { if (t - debut > RIEN_ENTENDU_MS) mic.arreter(); return; }
    compteARebours(t - dernierMot);
    if (t - dernierMot > patienceMs() || t - debut > PAROLE_MAX_MS) mic.arreter();
  }, 250);
  r.onresult = (e) => {
    dernierMot = performance.now();
    let provisoire = '';
    for (let i = e.resultIndex; i < e.results.length; i++) {
      if (e.results[i].isFinal) final += e.results[i][0].transcript;
      else provisoire += e.results[i][0].transcript;
    }
    $('q').value = (final + provisoire).trim(); ajuster();
    sousTitre($('q').value); pulser(0.3);
  };
  r.onerror = (e) => {
    const msg = { 'not-allowed': 'micro refusé : autorise-le pour localhost dans le navigateur',
      'no-speech': 'je n’ai rien entendu', network: 'reconnaissance du navigateur injoignable (réseau)',
      'audio-capture': 'aucun micro trouvé' }[e.error] || `micro : ${e.error}`;
    mic.erreur = msg;
  };
  r.onend = () => {
    clearInterval(minuteur);
    if (etat.micro === mic) etat.micro = null;
    etatMicro(false);
    if (mic.erreur) return erreurMicro(mic.erreur);
    const t = (final || $('q').value).trim();
    if (t && mic.envoyer) envoyer(t, true);
  };
  try { r.start(); } catch (e) { etat.micro = null; return erreurMicro(`micro : ${e.message || e}`); }
  etatMicro(true);
}

// Reconnaissance locale (Whisper, hors ligne, mélange de langues) : on enregistre, on détecte la
// fin de la parole (silence après avoir parlé), puis le serveur transcrit.
async function ecouterLocal() {
  const attente = { attente: true, arreter: () => {} };   // posé AVANT l'autorisation : un double clic n'ouvre pas deux micros
  etat.micro = attente;
  let flux, ctx, enreg;
  try {
    flux = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
  } catch (e) { etat.micro = null; return erreurMicro('micro refusé : autorise-le pour localhost dans le navigateur'); }
  if (etat.micro !== attente) { flux.getTracks().forEach(p => p.stop()); return; }   // annulé pendant l'autorisation
  try {
    ctx = new (window.AudioContext || window.webkitAudioContext)();
    enreg = new MediaRecorder(flux);
  } catch (e) {
    flux.getTracks().forEach(p => p.stop());
    if (ctx) ctx.close().catch(() => {});
    etat.micro = null;
    return erreurMicro(`micro : ${e.message || e}`);
  }
  const analyseur = ctx.createAnalyser();
  analyseur.fftSize = 1024;
  ctx.createMediaStreamSource(flux).connect(analyseur);
  const morceaux = [];
  enreg.ondataavailable = (e) => { if (e.data && e.data.size) morceaux.push(e.data); };
  const buf = new Float32Array(analyseur.fftSize);
  const t0 = performance.now();
  let bruit = 0, nBruit = 0, aParle = false, dernierSon = t0, minuterie = null;
  const mic = { envoyer: true, arreter: () => { if (enreg.state !== 'inactive') enreg.stop(); } };
  etat.micro = mic;
  minuterie = setInterval(() => {
    analyseur.getFloatTimeDomainData(buf);
    let s = 0; for (const x of buf) s += x * x;
    const rms = Math.sqrt(s / buf.length);
    const t = performance.now();
    if (t - t0 < 300) { bruit += rms; nBruit++; return; }                 // bruit de fond
    const seuil = Math.max(0.012, 3 * (bruit / Math.max(1, nBruit)));
    if (rms > seuil) { aParle = true; dernierSon = t; }
    const echelle = 1 + Math.min(0.25, rms * 4);
    $('micro').style.transform = `scale(${echelle})`;
    etat.niveauMicro = Math.min(1, rms * 7);                      // la grande orbe suit ta voix
    if (aParle) compteARebours(t - dernierSon);
    if (aParle && etat.reglages.rapide !== false && t - dernierSon >= SILENCE_ANTICIPE_MS && !mic.spec && morceaux.length
        && mic.essai !== dernierSon) {                            // un seul essai par silence
      mic.essai = dernierSon;
      const sp = { son: dernierSon };
      mic.spec = sp;
      transcrireVite(new Blob(morceaux, { type: enreg.mimeType || 'audio/webm' }), enreg.mimeType || 'audio/webm').then((texte) => {
        if (mic.spec === sp) mic.spec = null;
        if (etat.micro !== mic || dernierSon !== sp.son || !phraseFinie(texte)) return;   // reprise de parole, ou phrase en suspens
        mic.texteAnticipe = texte;
        mic.arreter();
      });
    }
    if ((aParle && t - dernierSon > patienceMs()) || (!aParle && t - t0 > RIEN_ENTENDU_MS) || t - t0 > PAROLE_MAX_MS) mic.arreter();
  }, 50);
  enreg.onstop = async () => {
    clearInterval(minuterie);
    flux.getTracks().forEach(p => p.stop());
    ctx.close().catch(() => {});
    if (etat.micro === mic) etat.micro = null;
    etatMicro(false);
    if (!mic.envoyer) return;
    if (mic.texteAnticipe) { envoyer(mic.texteAnticipe, true); return; }   // déjà transcrite pendant le silence
    if (!aParle) return erreurMicro('je n’ai rien entendu');
    const audio = new Blob(morceaux, { type: enreg.mimeType || 'audio/webm' });
    const ctl = new AbortController();                   // Stop ou Échap annulent la transcription
    etat.transcription = ctl;
    $('micro').classList.add('occupe');
    $('micro').disabled = true;
    humeur('transcription…');
    try {
      const langue = etat.reglages.langue === 'auto' ? '' : etat.reglages.langue.slice(0, 2);
      const r = await fetch(`/api/voix/transcrire?langue=${langue}`, { method: 'POST', body: audio, signal: ctl.signal,
        headers: { 'Content-Type': audio.type, 'X-Jeton': jeton() } });
      if (r.status === 403) throw new Error('jeton refusé : recharge la page (le cockpit a redémarré)');
      const o = await r.json().catch(() => ({ erreur: `réponse illisible (${r.status})` }));
      if (o.erreur) throw new Error(o.erreur);
      finTranscription(ctl);
      if (o.texte) envoyer(o.texte, true); else erreurMicro('je n’ai rien compris');
    } catch (e) {
      finTranscription(ctl);
      if (e.name !== 'AbortError') erreurMicro(`transcription : ${e.message || e}`);
      else humeur();
    }
  };
  try { enreg.start(250); } catch (e) { mic.arreter = () => {}; enreg.onstop = null; clearInterval(minuterie);
    flux.getTracks().forEach(p => p.stop()); ctx.close().catch(() => {}); etat.micro = null;
    return erreurMicro(`micro : ${e.message || e}`); }
  etatMicro(true);
}

function finTranscription(ctl) {
  if (etat.transcription === ctl) etat.transcription = null;
  $('micro').classList.remove('occupe');
  $('micro').disabled = false;
}

/* ---------- la vie intérieure : humeur, pensées spontanées, présence ---------- */
function activite() { etat.derniereActivite = Date.now(); }

async function lireInterieur() {
  try {
    const o = await (await fetch('/api/jarvis/interieur')).json();
    afficherVie(o);
    if (o && o.humeur) { etat.interieur = o; if (!etat.flux && !etat.micro && !lecteur.actif) humeur(); }
  } catch (_) {}
}

/* L'interrupteur de sa vie intérieure (proposé par Hakim, validé par Ahmed le 2026-10-17) : pause, reprise,
   remise à zéro — ennui, humeur, pensées, occupations, journal du temps ; jamais sa mémoire. */
function afficherVie(o) {
  const pause = !!(o && o.pause);
  $('etatVie').textContent = pause ? 'en pause' : (o && o.veille ? 'en veille (son ennui a atteint son plafond)' : 'en marche');
  $('vieInterrupteur').textContent = pause ? 'Remettre en marche' : 'Mettre en pause';
  $('vieInterrupteur').setAttribute('aria-pressed', String(pause));
}
async function reglerVie(action) {
  try {
    const r = await fetch('/api/jarvis/interieur/interrupteur', { method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() }, body: JSON.stringify({ action }) });
    const o = await r.json().catch(() => ({}));
    if (!r.ok) return humeur(o.erreur || 'interrupteur indisponible');
    afficherVie({ pause: o.pause });
    humeur({ arret: 'sa vie intérieure est en pause', marche: 'sa vie intérieure reprend',
      zero: 'sa vie intérieure repart de zéro (dans 15 s au plus)' }[action]);
  } catch (_) { humeur('interrupteur indisponible'); }
}
$('vieInterrupteur').addEventListener('click', () => reglerVie($('vieInterrupteur').getAttribute('aria-pressed') === 'true' ? 'marche' : 'arret'));
$('vieZero').addEventListener('click', () => {
  if (confirm("Remettre la vie intérieure de Hakim à zéro ?\nSon ennui et son temps ressenti repartent de zéro, son humeur revient à sa base, son journal du temps est archivé. Sa mémoire n'est pas touchée.")) reglerVie('zero');
});

function signalerPresence() {
  fetch('/api/jarvis/presence', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() },
    // en Conversation, le serveur préchauffe le cerveau de cette conversation, avec son modèle
    body: JSON.stringify({ visible: document.visibilityState === 'visible', conversation: !!etat.conversation,
      modele: etat.reglages.modeleConversation, source: etat.reglages.source || 'auto', session: etat.session }) }).catch(() => {});
}

// Une pensée du démon arrive : affichée, et dite à voix haute si Ahmed est là et que le silence
// dure (décision d'Ahmed, 2026-10-16) : page visible, rien en cours depuis 2 min, de 8 h à 23 h.
function surPensee(o) {
  const id = 'p' + o.id;
  if (etat.messages.some(m => m.id === id)) return;
  const m = { id, qui: 'j', spontane: o.role, texte: o.texte, ts: o.ts * 1000, episode: o.id };
  etat.messages.push(m);
  sauver(); rendre();
  $('annonce').textContent = `${o.role === 'outreach' ? 'Hakim te relance' : 'Pensée spontanée de Hakim'} : ${o.texte}`;
  const h = new Date().getHours();
  const silence = Date.now() - etat.derniereActivite > 120000;
  // une relance qui suit sa pensée se met à la suite de la lecture (elle n'était jamais dite)
  const enCoursSpontane = etat.messages.some(x => x.id === etat.lectureDe && x.spontane);
  if (document.visibilityState === 'visible' && silence && h >= 7                  // la nuit du démon : 0 h – 7 h
      && !etat.flux && !etat.micro && !etat.transcription && jarvisPeutParler() && (!lecteur.actif || enCoursSpontane)) {
    etat.lectureDe = m.id;
    lecteur.dire(m.texte);
    lecteur.finFlux();
    etat.dites.push(o.id);
    rendre(); humeur();
  }
}

function ecouterPensees() {
  const es = new EventSource('/api/jarvis/flux');
  es.addEventListener('pensee', (ev) => { try { surPensee(JSON.parse(ev.data)); } catch (_) {} });
  es.addEventListener('tache', (ev) => { try { surTache(JSON.parse(ev.data)); } catch (_) {} });
  es.addEventListener('promotion', (ev) => { try { surPromotion(JSON.parse(ev.data)); } catch (_) {} });
  es.addEventListener('mission', (ev) => { try { surMission(JSON.parse(ev.data)); } catch (_) {} });
  es.addEventListener('ecriture', (ev) => { try { surEcriture(JSON.parse(ev.data)); } catch (_) {} });
  es.addEventListener('regle', (ev) => { try { surRegle(JSON.parse(ev.data)); } catch (_) {} });
  es.addEventListener('identite', (ev) => { try { surIdentite(JSON.parse(ev.data)); } catch (_) {} });
  es.addEventListener('sortie', (ev) => { try { surSortie(JSON.parse(ev.data)); } catch (_) {} });
  es.addEventListener('spontane', (ev) => { try { surSpontane(JSON.parse(ev.data)); } catch (_) {} });
  es.addEventListener('courrier', (ev) => {
    try { const o = JSON.parse(ev.data); humeur(`Hakim a écrit à Claude Code : « ${o.sujet} »`); $('annonce').textContent = `Hakim a écrit à Claude Code : ${o.sujet}`; } catch (_) {}
  });
}

// Les missions que Hakim confie à Claude Code (2026-10-20) : une carte dans le fil, Ahmed accepte ou refuse ; la
// carte suit la mission (en cours, finie, compte rendu). Rien ne part sans son geste.
const ETATS_MISSION = { proposee: 'attend ton accord', refusee: 'refusée', 'en cours': 'Claude Code y travaille…', acceptee: 'acceptée',
  finie: 'finie', erreur: 'en erreur', arretee: 'arrêtée (une heure dépassée)', interrompue: 'interrompue (cockpit redémarré)', invalide: 'refusée par le cockpit' };
function surMission(o) {
  if (!o || !/^\d{8}-\d{6}-[0-9a-f]{4}$/.test(String(o.id))) return;
  const id = 'mission-' + o.id;
  let m = etat.messages.find(x => x.id === id);
  if (!m) {
    if (o.etat !== 'proposee' && o.etat !== 'en cours') return;              // l'arriéré tranché ne revient pas
    m = { id, qui: 'j', spontane: 'mission', ts: o.recu || Date.now() };
    etat.messages.push(m);
    humeur('Hakim propose une mission à Claude Code');
  }
  m.mission = o;
  m.texte = `Je propose une mission à Claude Code : « ${o.titre} » — ${ETATS_MISSION[o.etat] || o.etat}.`;
  sauver(); rendre();
}
async function missionsAuChargement() {
  try {
    const r = await fetch('/api/missions', { headers: { 'X-Jeton': jeton() } });
    if (r.ok) for (const o of (await r.json()).missions || []) surMission(o);
  } catch (_) {}
}
function htmlMission(o) {
  if (!o) return '';
  const droits = o.ecriture ? '<b>avec écriture</b> dans ce dossier' : 'lecture seule';
  const boutons = o.etat === 'proposee'
    ? `<div class="mission-boutons"><button class="btn" data-mission="${esc(o.id)}" data-action="accepter" data-empreinte="${esc(o.empreinte || '')}">Accepter</button>`
      + `<button class="btn" data-mission="${esc(o.id)}" data-action="refuser">Refuser</button></div>` : '';
  return `<div class="mission"><div><b>${esc(o.titre)}</b> · ${esc(o.projet)} · ${droits} · ${esc(o.modele)}</div>`
    + `<div class="mission-etat">${esc(ETATS_MISSION[o.etat] || o.etat)}${o.raison ? ' — ' + esc(o.raison) : ''}</div>`
    + `<details${o.ecriture && o.etat === 'proposee' ? ' open' : ''}><summary>la consigne de Hakim</summary><div class="txt">${esc(o.consigne || '')}</div></details>`
    + (o.resume ? `<details open><summary>compte rendu de Claude Code</summary><div class="txt">${liens(gras(esc(o.resume)))}</div></details>` : '')
    + (o.session ? `<div class="mission-session">reprendre : claude --resume ${esc(o.session)}</div>` : '') + boutons + '</div>';
}
$('fil').addEventListener('click', async (e) => {
  const b = e.target.closest('[data-mission]');
  if (!b) return;
  b.disabled = true;
  try {
    const presence = b.dataset.action === 'accepter' ? await preuvePresence(`mission:accepter:${b.dataset.mission}`) : undefined;
    const r = await fetch('/api/missions', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() },
      body: JSON.stringify({ id: b.dataset.mission, action: b.dataset.action, empreinte: b.dataset.empreinte || '', presence }) });
    const o = await r.json();
    if (!r.ok) throw new Error(o.erreur || `erreur ${r.status}`);
    surMission(o);
  } catch (err) { b.disabled = false; humeur(String(err.message || err)); }
});

// Les règles tirées de ses erreurs, niveau 2 (2026-10-22) : tu acceptes ou refuses une à une ; acceptée, elle entre dans
// ses règles de session après deux nuits témoins ; « Retirer » l'en sort.
const ETATS_REGLE = { proposee: 'attend ta décision', acceptee: 'acceptée', refusee: 'refusée', retiree: 'retirée' };
function surRegle(o) {
  if (!o || !/^R-[0-9a-f]{6}$/.test(String(o.id))) return;
  const id = 'regle-' + o.id;
  let m = etat.messages.find(x => x.id === id);
  if (!m) {
    if (o.etat !== 'proposee') return;
    m = { id, qui: 'j', spontane: 'regle', ts: o.recu || Date.now() };
    etat.messages.push(m);
    humeur('Hakim propose une règle tirée de ses erreurs');
  }
  m.regle = o;
  m.texte = `Je propose une règle tirée de mes erreurs : « ${o.regle} » — ${ETATS_REGLE[o.etat] || o.etat}.`;
  sauver(); rendre();
}
async function reglesAuChargement() {
  try {
    const r = await fetch('/api/regles', { headers: { 'X-Jeton': jeton() } });
    if (r.ok) for (const o of (await r.json()).regles || []) surRegle(o);
  } catch (_) {}
}
function htmlRegle(o) {
  if (!o) return '';
  const vigueur = o.etat === 'acceptee' && o.en_vigueur_ts ? (o.en_vigueur_ts > Date.now()
    ? ` — en vigueur le ${new Date(o.en_vigueur_ts).toLocaleString('fr-FR', { weekday: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' })}, après deux nuits témoins`
    : ' — en vigueur dans ses règles de session') : '';
  const boutons = o.etat === 'proposee'
    ? `<div class="mission-boutons"><button class="btn" data-regle="${esc(o.id)}" data-action="accepter">Accepter</button>`
      + `<button class="btn" data-regle="${esc(o.id)}" data-action="refuser">Refuser</button></div>`
    : o.etat === 'acceptee' ? `<div class="mission-boutons"><button class="btn" data-regle="${esc(o.id)}" data-action="retirer">Retirer</button></div>` : '';
  return `<div class="mission"><div><b>« ${esc(o.regle)} »</b></div><div class="mission-etat">${esc(o.groupe || '')}${o.cause ? ' : ' + esc(o.cause) : ''}</div>`
    + `<div class="mission-etat">${esc(ETATS_REGLE[o.etat] || o.etat)}${esc(vigueur)}</div>`
    + `<details><summary>ses sources (${(o.sources || []).length} erreurs)</summary><div class="txt">${esc((o.sources_texte || o.sources || []).join('\n'))}</div></details>` + boutons + '</div>';
}
$('fil').addEventListener('click', async (e) => {
  const b = e.target.closest('[data-regle]');
  if (!b) return;
  b.disabled = true;
  try {
    const presence = b.dataset.action === 'accepter' ? await preuvePresence(`regle:accepter:${b.dataset.regle.replace(/^R-/, '')}`) : undefined;
    const r = await fetch('/api/regles', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() },
      body: JSON.stringify({ id: b.dataset.regle, action: b.dataset.action, presence }) });
    const o = await r.json();
    if (!r.ok) throw new Error(o.erreur || `erreur ${r.status}`);
    surRegle(o);
  } catch (err) { b.disabled = false; humeur(String(err.message || err)); }
});

// Les écritures de Hakim dans tes projets (2026-10-22) : une proposition précise (ce qui est remplacé, par quoi, pourquoi) ;
// rien ne s'écrit sans ton geste ; appliquée, c'est un commit à part, qu'« Annuler » défait par un git revert.
const ETATS_ECRITURE = { proposee: 'attend ton geste', refusee: 'refusée : rien n’a été écrit', appliquee: 'appliquée', annulee: 'annulée (git revert)',
  invalide: 'refusée par le cockpit' };
function surEcriture(o) {
  if (!o || !/^E-\d{8}-\d{6}-[0-9a-f]{4}$/.test(String(o.id))) return;
  const id = 'ecriture-' + o.id;
  let m = etat.messages.find(x => x.id === id);
  if (!m) {
    if (o.etat !== 'proposee') return;
    m = { id, qui: 'j', spontane: 'ecriture', ts: o.recu || Date.now() };
    etat.messages.push(m);
    humeur('Hakim propose une écriture dans un de tes projets');
  }
  m.ecriture = o;
  m.texte = `Je propose une écriture dans ${o.fichier} (${o.projet}) : ${o.raison} — ${ETATS_ECRITURE[o.etat] || o.etat}.`;
  sauver(); rendre();
}
async function ecrituresAuChargement() {
  try {
    const r = await fetch('/api/ecritures', { headers: { 'X-Jeton': jeton() } });
    if (r.ok) for (const o of (await r.json()).ecritures || []) surEcriture(o);
  } catch (_) {}
}
function htmlEcriture(o) {
  if (!o) return '';
  const boutons = o.etat === 'proposee'
    ? `<div class="mission-boutons"><button class="btn" data-ecriture="${esc(o.id)}" data-action="appliquer" data-empreinte="${esc(o.empreinte || '')}">Appliquer</button>`
      + `<button class="btn" data-ecriture="${esc(o.id)}" data-action="refuser">Refuser</button></div>`
    : o.etat === 'appliquee' ? `<div class="mission-boutons"><button class="btn" data-ecriture="${esc(o.id)}" data-action="annuler">Annuler (git revert)</button></div>` : '';
  return `<div class="mission"><div><b>${esc(o.fichier)}</b> · ${esc(o.projet)}</div><div class="mission-etat">${esc(o.raison || '')}</div>`
    + `<div class="mission-etat">${esc(ETATS_ECRITURE[o.etat] || o.etat)}${o.commit ? ' — commit ' + esc(o.commit) : ''}${o.raison_refus ? ' — ' + esc(o.raison_refus) : ''}</div>`
    + `<details open><summary>ce qui change</summary>${o.ancien ? `<div class="txt"><b>avant :</b>\n${esc(o.ancien)}</div>` : '<div class="txt"><b>un fichier neuf</b></div>'}`
    + `<div class="txt"><b>après :</b>\n${esc(o.nouveau)}</div></details>` + boutons + '</div>';
}
$('fil').addEventListener('click', async (e) => {
  const b = e.target.closest('[data-ecriture]');
  if (!b) return;
  b.disabled = true;
  try {
    const presence = b.dataset.action !== 'refuser' ? await preuvePresence(`ecriture:${b.dataset.action}:${b.dataset.ecriture.replace(/^E-/, '')}`) : undefined;
    const r = await fetch('/api/ecritures', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() },
      body: JSON.stringify({ id: b.dataset.ecriture, action: b.dataset.action, empreinte: b.dataset.empreinte || '', presence }) });
    const o = await r.json();
    if (!r.ok) throw new Error(o.erreur || `erreur ${r.status}`);
    surEcriture(o);
  } catch (err) { b.disabled = false; humeur(String(err.message || err)); }
});

// Son identité (X1, 2026-10-20) : la nuit, le rêve, une session PROPOSENT ; Ahmed voit la différence et tranche.
const ETATS_IDENTITE = { en_attente: 'attend ta décision', acceptee: 'acceptée : elle fait partie de lui', refusee: 'refusée : rien n’a changé' };
function surIdentite(o) {
  if (!o || !/^\d{9,11}-[0-9a-f]{6}$/.test(String(o.id))) return;
  const id = 'identite-' + o.id;
  let m = etat.messages.find(x => x.id === id);
  if (!m) {
    if (o.etat !== 'en_attente') return;
    m = { id, qui: 'j', spontane: 'identite', ts: Math.round((Number(o.ts) || Date.now() / 1000) * 1000) };
    etat.messages.push(m);
    humeur('Une proposition pour son identité attend ta décision');
  }
  m.identite = { ...(m.identite || {}), ...o };
  m.texte = m.identite.sorte === 'coeur' ? `Proposition d'un nouveau cœur d'identité (${m.identite.origine}) — ${ETATS_IDENTITE[m.identite.etat] || m.identite.etat}.`
    : `Proposition pour mon identité (${m.identite.origine}) : « ${m.identite.texte} » — ${ETATS_IDENTITE[m.identite.etat] || m.identite.etat}.`;
  sauver(); rendre();
}
async function identiteAuChargement() {
  try {
    const r = await fetch('/api/identite', { headers: { 'X-Jeton': jeton() } });
    if (r.ok) for (const o of (await r.json()).propositions || []) surIdentite(o);
  } catch (_) {}
}
function htmlIdentite(o) {
  if (!o) return '';
  const boutons = o.etat === 'en_attente'
    ? `<div class="mission-boutons"><button class="btn" data-identite="${esc(o.id)}" data-action="accepter">Accepter</button>`
      + `<button class="btn" data-identite="${esc(o.id)}" data-action="refuser">Refuser</button></div>` : '';
  let corps;
  if (o.sorte === 'coeur') {                       // la différence, ligne à ligne : ce qui part (−) et ce qui arrive (+)
    const a = String(o.avant || '').split('\n'), b = String(o.texte || '').split('\n');
    const diff = a.filter(l => l.trim() && !b.includes(l)).map(l => `<div class="moins">− ${esc(l)}</div>`)
      .concat(b.filter(l => l.trim() && !a.includes(l)).map(l => `<div class="plus">+ ${esc(l)}</div>`)).join('');
    corps = `<div><b>Nouveau cœur d'identité</b> · proposé par ${esc(o.origine)}</div><div class="diff">${diff || '(aucune différence de ligne)'}</div>`
      + `<details><summary>le cœur proposé en entier</summary><div class="txt">${esc(o.texte)}</div></details>`;
  } else corps = `<div><b>Une phrase pour son identité</b> · proposée par ${esc(o.origine)}</div><div class="diff"><div class="plus">+ ${esc(o.texte)}</div></div>`;
  return `<div class="mission">${corps}<div class="mission-etat">${esc(ETATS_IDENTITE[o.etat] || o.etat)}</div>${boutons}</div>`;
}
$('fil').addEventListener('click', async (e) => {
  const b = e.target.closest('[data-identite]');
  if (!b) return;
  b.disabled = true;
  try {
    const presence = b.dataset.action === 'accepter' ? await preuvePresence(`identite:accepter:${b.dataset.identite}`) : undefined;
    const r = await fetch('/api/identite', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() },
      body: JSON.stringify({ id: b.dataset.identite, action: b.dataset.action, presence }) });
    const o = await r.json();
    if (!r.ok) throw new Error(o.erreur || `erreur ${r.status}`);
    surIdentite(o);
  } catch (err) { b.disabled = false; humeur(String(err.message || err)); }
});

// La règle de sortie (H1b) : après la lecture d'un de ses fichiers, une adresse qui peut porter des données vers un
// site inconnu attend son geste. Autorisée : cette adresse exacte, une fois, dans les 15 minutes.
const ETATS_SORTIE = { en_attente: 'attend ta décision', autorisee: 'autorisée une fois (15 min)', refusee: 'refusée' };
function surSortie(o) {
  if (!o || !/^[0-9a-f]{10}$/.test(String(o.id))) return;
  const id = 'sortie-' + o.id;
  let m = etat.messages.find(x => x.id === id);
  if (!m) {
    if (o.etat !== 'en_attente') return;
    m = { id, qui: 'j', spontane: 'sortie', ts: Math.round((Number(o.ts) || Date.now() / 1000) * 1000) };
    etat.messages.push(m);
    humeur('Hakim demande à ouvrir une adresse : à toi de trancher');
  }
  m.sortie = { ...(m.sortie || {}), ...o };
  m.texte = `Je voudrais ouvrir ${m.sortie.url} — ${ETATS_SORTIE[m.sortie.etat] || m.sortie.etat}.`;
  sauver(); rendre();
}
async function sortiesAuChargement() {
  try {
    const r = await fetch('/api/sorties', { headers: { 'X-Jeton': jeton() } });
    if (r.ok) for (const o of (await r.json()).sorties || []) surSortie(o);
  } catch (_) {}
}
function htmlSortie(o) {
  if (!o) return '';
  const boutons = o.etat === 'en_attente'
    ? `<div class="mission-boutons"><button class="btn" data-sortie="${esc(o.id)}" data-action="autoriser">Autoriser une fois</button>`
      + `<button class="btn" data-sortie="${esc(o.id)}" data-action="refuser">Refuser</button></div>` : '';
  return `<div class="mission"><div><b>Une adresse après la lecture d'un de tes fichiers</b></div>`
    + `<div class="mission-etat"><b>Qui la demande :</b> ${esc(o.qui || 'Hakim')}</div>`
    + `<div class="diff">${esc(o.url)}</div><div class="mission-etat"><b>Pourquoi elle est bloquée :</b> ${esc(o.raison || '')}</div>`
    + `<div class="mission-etat"><b>Si tu autorises :</b> ${esc(o.duree || 'une seule fois, dans les 15 minutes')} — ${esc(ETATS_SORTIE[o.etat] || o.etat)}</div>${boutons}</div>`;
}
$('fil').addEventListener('click', async (e) => {
  const b = e.target.closest('[data-sortie]');
  if (!b) return;
  b.disabled = true;
  try {
    const presence = b.dataset.action === 'autoriser' ? await preuvePresence(`sortie:autoriser:${b.dataset.sortie}`) : undefined;
    const r = await fetch('/api/sorties', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() },
      body: JSON.stringify({ id: b.dataset.sortie, action: b.dataset.action, presence }) });
    const o = await r.json();
    if (!r.ok) throw new Error(o.erreur || `erreur ${r.status}`);
    surSortie(o);
  } catch (err) { b.disabled = false; humeur(String(err.message || err)); }
});

// Hakim propose de changer son propre code (lot H, point 30) : affiché ; rien n'est appliqué sans Ahmed
function surPromotion(o) {
  const id = 'promotion-' + o.id;
  if (etat.messages.some(m => m.id === id)) return;
  const texte = `Je propose une modification de mon code (« ${o.id} ») : ${o.resume} — ${o.fichiers} fichier(s), tests ${o.tests_ok ? 'réussis' : 'EN ÉCHEC'}`
    + (o.coeur && o.coeur.length ? `, touche au cœur (${o.coeur.join(', ')})` : '') + '. Rien n’est appliqué sans ton accord : demande à Claude Code de l’appliquer si tu es d’accord.';
  etat.messages.push({ id, qui: 'j', spontane: 'promotion', texte, ts: Date.now() });
  sauver(); rendre(); humeur('Hakim propose une modification de son code');
}

// Hakim parle de lui-même (point 1 de la demande du 2026-10-20) : un agent ou une commande de fond a fini, il en
// dit le résultat. Affiché ; dit à voix haute si la voix est active (conversation, volant, lecture auto) ; et
// l'accusé de réception part au cockpit (un message jamais affiché est signalé à Hakim).
function surSpontane(m) {
  if (!m || !m.id || etat.messages.some(x => x.id === m.id)) return;
  etat.messages.push({ id: m.id, qui: 'j', spontane: 'resultat', texte: m.texte, ts: m.ts, source: m.source,
    pieces: Array.isArray(m.pieces) ? m.pieces.filter(x => x && /^\d{8}-\d{6}-[0-9a-f]{6}$/.test(String(x.id))) : undefined });
  sauver(); rendre(); accuserReception();
  humeur('Hakim te donne un résultat');
  $('annonce').textContent = `Hakim, de lui-même : ${m.texte}`;
  widgetApp(etat.conversation ? 'conversation' : 'repos', m.texte);
  if (etat.conversation || etat.reglages.volant || etat.reglages.lectureAuto) { aDire.push({ id: m.id, texte: m.texte, recu: Date.now() }); direSpontanes(); }
}
/* Ses résultats « de lui-même » DITS dans la conversation (demande d'Ahmed relayée par Hakim, 2026-10-20 : « il arrive à
   l'écran mais je ne l'entends pas ») : avant, le message n'était dit que si TOUT était libre à l'instant même où il
   arrivait (Ahmed se taisait, Hakim ne répondait pas déjà…) — sinon il était perdu pour l'oreille. Désormais il attend
   son tour : dit dès qu'Ahmed s'est tu depuis 1,5 s et que rien d'autre ne parle ; jamais par-dessus sa parole.
   (2026-10-23, Ahmed : « rien n'est jamais jeté ») la même file garde aussi ce qu'il n'a pas pu dire quand Ahmed l'a
   coupé ou a enchaîné (garderNonDit) : dit au premier moment calme (3 s sans voix, ni la sienne ni celle d'Ahmed ; micro
   coupé, c'est le silence) ; plus de deux en attente : Hakim en fait une synthèse et la dit en entier (synthetiser).
   Plus d'oubli après 10 min ; voix éteinte, la file attend ; gardée dans le navigateur si la page se recharge. */
const aDire = [];
try { for (const x of JSON.parse(localStorage.getItem('jarvis.aDire') || '[]')) if (x && typeof x.texte === 'string') aDire.push(x); } catch (_) {}
const sauverADire = () => { try { localStorage.setItem('jarvis.aDire', JSON.stringify(aDire.slice(-20))); } catch (_) {} };
let parlaitA = 0;
function garderNonDit() {
  if (!(etat.conversation || etat.reglages.volant || etat.reglages.lectureAuto)) return;   // voix éteinte : il lit à l'écran
  const morceaux = lecteurNeuronal.restant().map(x => x.texte);
  if (etat.decoupeFlux) morceaux.push(...etat.decoupeFlux.finir());          // la phrase qui arrivait encore
  // (une reprise coupée à son tour ne redit pas « Je reprends… » deux fois)
  const texte = morceaux.join(' ').replace(/\s+/g, ' ').trim().replace(/^(je reprends ce que je disais\s*:\s*)+/i, '');
  if (!/\p{L}{2,}/u.test(texte) || NON_REPONSE.test(texte)) return;
  aDire.push({ id: etat.lectureDe || `nondit-${Date.now()}`, texte, recu: Date.now(), coupe: true });
  sauverADire();
  journalVoix('non_dit_garde', { car: texte.length, en_attente: aDire.length });
}
let synthese = { enCours: false, reessaiA: 0 };
async function synthetiser() {
  if (synthese.enCours || Date.now() < synthese.reessaiA) return;
  synthese.enCours = true;
  const lot = aDire.splice(0);
  sauverADire();
  try {
    const r = await fetch('/api/jarvis/non-dites', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() },
      body: JSON.stringify({ textes: lot.map(x => ({ texte: x.texte, coupe: !!x.coupe })) }) });
    if (!r.ok) throw new Error(`non-dites ${r.status}`);
    journalVoix('non_dits_synthese', { n: lot.length });
    humeur('Hakim rassemble ce qu’il n’a pas pu te dire…');
  } catch (_) {
    aDire.unshift(...lot); sauverADire();               // rien n'est jeté : au prochain moment calme, dans 30 s au plus tôt
    synthese.reessaiA = Date.now() + 30000;
  } finally { synthese.enCours = false; }
}
function direSpontanes() {
  const c = etat.conversation;
  if (c && c.capteur && c.capteur.enParole) parlaitA = Date.now();
  const voix = c || etat.reglages.volant || etat.reglages.lectureAuto;
  if (!voix || !aDire.length) return;
  const calme = aDire.some(x => x.coupe) ? 3000 : 1500;
  if (!lecteur || etat.flux || etat.micro || etat.transcription || !jarvisPeutParler() || lecteur.actif || lecteur.enPause
      || Date.now() - Math.max(parlaitA, etat.finVoixA || 0) < calme) return;
  if (aDire.length > 2) { synthetiser(); return; }
  const m = aDire.shift();
  sauverADire();
  if (NON_REPONSE.test(m.texte)) return;
  etat.lectureDe = m.id;
  lecteur.dire(m.coupe ? `Je reprends ce que je disais : ${m.texte}` : m.texte); lecteur.finFlux();
  humeur();
}
setInterval(direSpontanes, 500);
const accuses = new Set();
async function accuserReception() {
  if (document.visibilityState !== 'visible') return;      // « vu » = affiché sur un écran visible, pas reçu en fond
  const ids = etat.messages.filter(x => x.spontane === 'resultat' && !accuses.has(x.id)).map(x => x.id).slice(-200);
  if (!ids.length) return;
  ids.forEach(id => accuses.add(id));
  try {
    await fetch('/api/jarvis/vu', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() }, body: JSON.stringify({ ids }) });
  } catch (_) { ids.forEach(id => accuses.delete(id)); }
}

// Une tâche de fond de Hakim vient de se terminer (lot C, 2026-10-19) : affichée, et dite en une phrase si
// rien d'autre ne parle ; Hakim en verra le résultat au message suivant ([Tâches]).
function surTache(o) {
  const id = 'tache-' + o.id;
  if (etat.messages.some(m => m.id === id)) return;
  const fini = o.etat === 'finie' && o.code === 0;
  const texte = `Tâche de fond ${fini ? 'terminée' : o.etat}${o.raison ? ' (' + o.raison + ')' : ''} : « ${o.commande} » en ${Math.round(o.duree_s || 0)} s. `
    + (o.reveil ? 'Je regarde le résultat et je te le dis.' : 'Demande-moi le résultat.');
  etat.messages.push({ id, qui: 'j', spontane: 'tache', texte, ts: Date.now() });
  sauver(); rendre();
  humeur(fini ? 'une tâche de fond est terminée' : 'une tâche de fond s’est arrêtée');
  if (!etat.flux && !lecteur.actif && jarvisPeutParler()) { lecteur.dire(fini ? 'Ma tâche de fond est terminée.' : 'Ma tâche de fond s’est arrêtée.'); lecteur.finFlux(); }
}

/* ---------- pièces jointes : bouton, glisser-déposer, coller ---------- */
function rendreJoints() {
  const z = $('joints');
  z.hidden = !etat.joints.length;
  z.innerHTML = etat.joints.map((x, i) => `<span class="joint${x.erreur ? ' erreur' : (x.chemin ? '' : ' envoi')}" title="${esc(x.erreur || x.nom)}">`
    + (x.url ? `<img src="${x.url}" alt="">` : '📎') + `<span>${esc(x.nom)}${x.chemin || x.erreur ? '' : ' …'}</span>`
    + `<button data-retirer="${i}" aria-label="Retirer ${esc(x.nom)}">×</button></span>`).join('');
}
$('joints').addEventListener('click', (e) => {
  const b = e.target.closest('[data-retirer]');
  if (!b) return;
  const [x] = etat.joints.splice(Number(b.dataset.retirer), 1);
  if (x && x.url) URL.revokeObjectURL(x.url);
  rendreJoints();
});
async function joindre(liste) {
  for (const f of Array.from(liste || [])) {
    const x = { nom: f.name || 'collé.png', chemin: null, erreur: null, url: /^image\//.test(f.type) ? URL.createObjectURL(f) : null };
    etat.joints.push(x);
    rendreJoints();
    try {
      const r = await fetch('/api/jarvis/fichier', { method: 'POST', body: f,
        headers: { 'X-Jeton': jeton(), 'X-Nom': encodeURIComponent(x.nom), 'Content-Type': f.type || 'application/octet-stream' } });
      const o = await r.json().catch(() => ({ erreur: `réponse illisible (${r.status})` }));
      if (o.erreur) throw new Error(o.erreur);
      x.chemin = o.chemin;
    } catch (e) { x.erreur = String(e.message || e); }
    rendreJoints();
  }
}
$('joindre').addEventListener('click', () => $('choix').click());
$('choix').addEventListener('change', (e) => { joindre(e.target.files); e.target.value = ''; });
document.addEventListener('dragover', (e) => { if ([...(e.dataTransfer?.types || [])].includes('Files')) { e.preventDefault(); document.body.classList.add('depot'); } });
document.addEventListener('dragleave', (e) => { if (!e.relatedTarget) document.body.classList.remove('depot'); });
document.addEventListener('drop', (e) => {
  if (!e.dataTransfer?.files?.length) return;
  e.preventDefault(); document.body.classList.remove('depot');
  joindre(e.dataTransfer.files);
});
$('q').addEventListener('paste', (e) => {
  const f = [...(e.clipboardData?.files || [])];
  if (f.length) { e.preventDefault(); joindre(f); }
});

/* ---------- saisie, réglages, raccourcis ---------- */
function ajuster() {          // hauteur au contenu (+2 : les bordures), défilement seulement au-delà de 180 px
  const q = $('q');
  q.style.height = 'auto';
  q.style.height = Math.min(180, q.scrollHeight + 2) + 'px';
  q.style.overflowY = q.scrollHeight + 2 > 180 ? 'auto' : 'hidden';
}

function appliquerReglages() {
  const r = etat.reglages;
  $('modele').value = r.modele; $('modeleConversation').value = r.modeleConversation || 'sonnet';
  $('source').value = r.source || 'auto';
  $('modele').disabled = $('modeleConversation').disabled = r.source === 'local';      // le local n'a qu'un modèle
  $('reconnaissance').value = r.reconnaissance; $('langue').value = r.langue;
  $('patience').value = String(r.patience);
  $('vitesse').value = r.vitesse; $('lectureAuto').checked = !!r.lectureAuto; $('voix').value = r.voix;
  $('sceneActive').checked = r.scene !== false;
  $('rapide').checked = r.rapide !== false;
  $('position').checked = !!r.position; suivrePosition(!!r.position);
  $('voixNeutre').checked = !!r.voixNeutre;
  $('btnVolant').setAttribute('aria-pressed', String(!!r.volant)); $('btnVolant').classList.toggle('actif', !!r.volant);
  $('voixFr').disabled = $('voixAr').disabled = r.voix === 'neuronale' && etat.ttsLocal;
  // « auto » (le défaut depuis le 2026-10-18) : Whisper choisit entre français, arabe et anglais (jarvis/stt.py).
  // Vu le 2026-10-16 : un français précédé d'un salam a déjà été pris pour de l'arabe ; « français » reste
  // au choix pour forcer la langue.
}
for (const [id, cle, val] of [['source', 'source', e => e.value], ['modele', 'modele', e => e.value], ['modeleConversation', 'modeleConversation', e => e.value], ['reconnaissance', 'reconnaissance', e => e.value],
  ['langue', 'langue', e => e.value], ['voixFr', 'voixFr', e => e.value], ['voixAr', 'voixAr', e => e.value],
  ['vitesse', 'vitesse', e => parseFloat(e.value) || 1], ['lectureAuto', 'lectureAuto', e => e.checked],
  ['patience', 'patience', e => parseFloat(e.value)],
  ['voix', 'voix', e => e.value], ['sceneActive', 'scene', e => e.checked], ['rapide', 'rapide', e => e.checked],
  ['position', 'position', e => e.checked], ['voixNeutre', 'voixNeutre', e => e.checked]]) {
  $(id).addEventListener('change', (ev) => { etat.reglages[cle] = val(ev.target); appliquerReglages(); sauver(); });
}
$('btnReglages').addEventListener('click', () => {
  const s = $('reglages'); s.hidden = !s.hidden;
  $('btnReglages').setAttribute('aria-expanded', String(!s.hidden));
  if (!s.hidden) { afficherVerrou(); afficherJetons(); afficherNotifs(); afficherEmpreinte(); afficherPromesses();
    try { if (window.HakimApp && window.HakimApp.bulleEtat) afficherBulle(JSON.parse(window.HakimApp.bulleEtat())); } catch (_) {} }
});

/* ---------- la position (accord d'Ahmed, 2026-10-22) : éteinte par défaut, coupable à tout moment. Arrondie à trois
   décimales (une centaine de mètres), gardée dans la mémoire de la page seulement (jamais dans le stockage du
   navigateur), jointe à chaque message tant que la mesure a moins de 15 min. ---------- */
// (2026-10-22, bug d'Ahmed sous Samsung Internet : rien n'arrivait) l'heure de la mesure est celle de la PAGE (certains
// navigateurs Android datent la mesure sur une autre horloge, et elle passait pour périmée) ; une première mesure tout de
// suite, puis le suivi ; sans réponse, un nouvel essai au GPS ; un état clair, erreurs comprises, ici et dans la barre.
let suiviPosition = null, dernierePosition = null, positionEnvoyee = 0;
const ERREURS_POSITION = {
  1: 'refusée : autorise la position pour ce site (le cadenas à côté de l’adresse) et pour le navigateur lui-même (Réglages Android → Applications → le navigateur → Autorisations → Position)',
  2: 'indisponible : active la localisation du téléphone',
  3: 'pas de réponse du téléphone : nouvel essai avec le GPS',
};
const hhmm = (ms) => new Date(ms).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
// (2026-10-22) l'état de la position va aussi au journal de diagnostic (jamais les coordonnées) : pour lire le bug au lieu
// de le deviner quand le téléphone ne répond pas
const NAVIGATEUR = /SamsungBrowser/i.test(navigator.userAgent || '') ? 'samsung' : /Chrome/i.test(navigator.userAgent || '') ? 'chrome' : 'autre';
function diagPosition(etatPos, d) { try { journalVoix('position', { etat: etatPos, navigateur: NAVIGATEUR, securise: !!window.isSecureContext, ...(d || {}) }); } catch (_) {} }
function montrerPosition(t, alerte) {
  const el = $('etatPosition');
  if (el) el.textContent = `(${t})`;
  if (alerte) humeur(`position ${t}`);
}
function etatPosition() {
  if (!dernierePosition) return;
  montrerPosition(`active : reçue à ${hhmm(dernierePosition.t_ms)}, à ${dernierePosition.precision_m} m près`
    + (positionEnvoyee ? ` · envoyée à Hakim à ${hhmm(positionEnvoyee)}` : ' · partira avec ton prochain message'));
}
function suivrePosition(actif) {
  if (!actif) {
    if (suiviPosition !== null && navigator.geolocation) navigator.geolocation.clearWatch(suiviPosition);
    suiviPosition = null; dernierePosition = null; positionEnvoyee = 0;
    montrerPosition('éteinte');
    return;
  }
  if (suiviPosition !== null) return;
  if (!window.isSecureContext) { montrerPosition('impossible ici : la position exige une adresse en https', true); diagPosition('non_securise'); return; }
  if (!navigator.geolocation) { montrerPosition('ce navigateur ne donne pas de position', true); return; }
  montrerPosition('demandée au téléphone…');
  diagPosition('demandee', { api: !!navigator.geolocation });
  const recue = (p) => {
    if (!dernierePosition) diagPosition('recue', { precision: Math.round(p.coords.accuracy || 0) });
    dernierePosition = { lat: Math.round(p.coords.latitude * 1000) / 1000, lon: Math.round(p.coords.longitude * 1000) / 1000,
      precision_m: Math.round(p.coords.accuracy || 0), t_ms: Date.now() };
    etatPosition();
  };
  let gps = false;
  const erreur = (e) => {
    diagPosition('erreur', { code: Number(e && e.code) || 0 });
    if (dernierePosition && e.code === 3) return;                  // une mesure récente suffit : pas d'alarme
    montrerPosition(ERREURS_POSITION[e.code] || `erreur ${e.code}`, true);
    if ((e.code === 2 || e.code === 3) && !gps) {
      gps = true;
      if (suiviPosition !== null) navigator.geolocation.clearWatch(suiviPosition);
      suiviPosition = navigator.geolocation.watchPosition(recue, (e2) => montrerPosition(ERREURS_POSITION[e2.code === 3 ? 2 : e2.code] || `erreur ${e2.code}`, true),
        { enableHighAccuracy: true, maximumAge: 120000, timeout: 60000 });
    }
  };
  suiviPosition = navigator.geolocation.watchPosition(recue, erreur, { enableHighAccuracy: false, maximumAge: 120000, timeout: 30000 });
  navigator.geolocation.getCurrentPosition(recue, erreur, { enableHighAccuracy: false, maximumAge: 300000, timeout: 20000 });
}
// (Ahmed, 2026-10-22 : « mettre à jour sa position chaque minute, sans attendre un message ») : tant que la case est
// cochée et la page visible, une mesure par minute (précision moyenne, pour la batterie), envoyée au cockpit qui ne
// garde que la DERNIÈRE, en mémoire seulement. Page cachée ou écran éteint : Android suspend la position et les minuteurs.
setInterval(() => {
  if (!etat.reglages.position || suiviPosition === null || document.visibilityState !== 'visible' || !navigator.geolocation) return;
  navigator.geolocation.getCurrentPosition((p) => {
    dernierePosition = { lat: Math.round(p.coords.latitude * 1000) / 1000, lon: Math.round(p.coords.longitude * 1000) / 1000,
      precision_m: Math.round(p.coords.accuracy || 0), t_ms: Date.now() };
    fetch('/api/position', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() }, body: JSON.stringify(dernierePosition) })
      .then(r => { if (r.ok) { positionEnvoyee = Date.now(); etatPosition(); } }).catch(() => {});
  }, () => {}, { enableHighAccuracy: false, maximumAge: 55000, timeout: 20000 });
}, 60000);
function positionAEnvoyer() {
  if (!etat.reglages.position) return null;
  if (!dernierePosition || Date.now() - dernierePosition.t_ms > 15 * 60000) {
    humeur(dernierePosition ? 'position trop ancienne : pas envoyée (le téléphone ne la renouvelle pas)' : 'position pas encore reçue du téléphone : pas envoyée');
    return null;
  }
  if (!positionEnvoyee) { humeur(`position envoyée à Hakim (à ${dernierePosition.precision_m} m près)`); diagPosition('envoyee'); }
  positionEnvoyee = Date.now();
  etatPosition();
  return dernierePosition;
}

/* ---------- l'appareil (lot B, point 19) et le mode volant (point 27) ---------- */
// Sur le Galaxy Z Fold : plié, l'écran extérieur est étroit (≈ 410 px CSS) ; déplié, ≈ 750 px et plus.
function appareilPage() {
  const android = /Android/i.test(navigator.userAgent || '');
  return { android, plie: android ? Math.min(screen.width, screen.height) < 600 : null };
}
function reglerVolant(actif) {
  etat.reglages.volant = !!actif; sauver();
  $('btnVolant').setAttribute('aria-pressed', String(!!actif));
  $('btnVolant').classList.toggle('actif', !!actif);
  humeur(actif ? 'mode volant : je te réponds à voix haute, court' : 'mode volant terminé');
}
$('btnVolant').addEventListener('click', () => reglerVolant(!etat.reglages.volant));
/* ---------- les promesses de Hakim (2026-10-22) : visibles et effaçables par Ahmed ---------- */
async function afficherPromesses() {
  const ul = $('promesses');
  let o; try { o = await (await fetch('/api/promesses', { cache: 'no-store' })).json(); } catch (_) { return; }
  const l = (o && o.promesses) || [];
  ul.textContent = '';
  if (!l.length) { ul.textContent = 'aucune pour le moment'; return; }
  const quand = (ms) => new Intl.DateTimeFormat('fr-FR', { weekday: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(ms));
  const mot = { attente: 'attend', tenue: 'tenue', manquee: 'manquée', effacee: 'effacée' };
  for (const p of l.sort((a, b) => a.t_ms - b.t_ms)) {
    const li = document.createElement('li');
    li.textContent = `${quand(p.t_ms)} · ${mot[p.etat] || p.etat} · ${p.raison} `;
    if (p.etat === 'attente') {
      const b = document.createElement('button');
      b.className = 'btn'; b.type = 'button'; b.textContent = 'Effacer';
      b.addEventListener('click', async () => {
        try { await fetch('/api/promesses/effacer', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() }, body: JSON.stringify({ id: p.id }) }); } catch (_) {}
        afficherPromesses();
      });
      li.appendChild(b);
    }
    ul.appendChild(li);
  }
}

async function afficherJetons() {
  let b; try { b = await (await fetch('/api/jarvis/jetons', { cache: 'no-store' })).json(); } catch (_) { return; }
  if (!b || !b.tours) { $('jetonsJour').textContent = "Jetons aujourd'hui : aucun tour mesuré."; return; }
  const k = (n) => `${Math.round(n / 1000).toLocaleString('fr-FR')} k`;
  const usd = (x) => `${x.toFixed(2).replace('.', ',')} $`;
  $('jetonsJour').textContent = `Jetons aujourd'hui (${b.tours} tours) : ${k(b.cache_lu)} relus en cache (${b.part_cache} %), `
    + `${k(b.cache_ecrit)} mis en cache, ${k(b.entree)} neufs, ${k(b.sortie)} écrits — API payée : ${usd(b.cout_api_usd)} ; `
    + `forfait : l'équivalent de ${usd(b.cout_forfait_equiv_usd)} au tarif de l'API.`;
}

/* ---------- l'empreinte vocale (point 18, 2026-10-20) ---------- */
async function afficherEmpreinte(apres) {
  let o; try { o = await (await fetch('/api/voix/empreinte', apres ? { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() }, body: JSON.stringify(apres) } : { cache: 'no-store' })).json(); } catch (_) { return; }
  $('etatEmpreinte').textContent = o.apprentissage ? `j'apprends : parle-moi normalement (encore ${o.apprentissage} phrase${o.apprentissage > 1 ? 's' : ''})`
    : o.echantillons >= 2 ? `apprise (${o.echantillons} échantillons)${o.derniere ? ` · dernière phrase : ${o.derniere.verdict === 'ahmed' ? "c'est toi" : o.derniere.verdict === 'doute' ? 'incertain' : "pas ta voix"} (${o.derniere.score})` : ''}`
    : 'pas encore apprise';
  // l'avancement de la calibration, par appareil et par registre (demande d'Ahmed, 2026-10-20)
  const regs = o.registres || {};
  const ligne = (app) => REGISTRES.map(([id]) => `${id} ${regs[`${id}-${app}`] ? '✓' + (regs[`${id}-${app}`] > 1 ? '×' + regs[`${id}-${app}`] : '') : '–'}`).join(' · ');
  if ($('avancementCalib')) $('avancementCalib').textContent = `Mac : ${ligne('mac')} — téléphone : ${ligne('telephone')}`;
}
async function reinitialiserVoix(portee, question) {
  if (!confirm(question)) return;
  try {
    const r = await fetch('/api/voix/empreinte', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() },
      body: JSON.stringify({ action: 'reinitialiser', portee }) });
    const o = await r.json();
    if (!r.ok || o.erreur) throw new Error(o.erreur || `erreur ${r.status}`);
    calibration = null;
    humeur(`réinitialisé : ${o.avant} → ${o.apres} échantillons (l'ancienne empreinte est sauvegardée)`);
  } catch (e) { humeur(`réinitialisation impossible : ${e.message || e}`); }
  afficherEmpreinte();
}
$('empreinteReinitTout').addEventListener('click', () => reinitialiserVoix('tout',
  'Effacer TOUTE l’empreinte de ta voix ? (l’ancienne est sauvegardée ; Hakim ne te reconnaîtra plus jusqu’au prochain apprentissage)'));
$('empreinteReinitCalib').addEventListener('click', () => {
  const ici = appareilPage().android ? 'telephone' : 'mac';
  const seulement = confirm(`Réinitialiser la calibration de CET appareil seulement (${ici === 'mac' ? 'le Mac' : 'le téléphone'}) ?\n\nOK : cet appareil seulement · Annuler : choisir « tous les appareils »`);
  if (seulement) return reinitialiserVoix(`calibration-${ici}`, 'Confirmer : effacer la calibration de cet appareil ? (sauvegardée avant)');
  return reinitialiserVoix('calibration', 'Effacer la calibration de TOUS les appareils ? (sauvegardée avant)');
});
$('empreinteApprendre').addEventListener('click', async () => {
  await afficherEmpreinte({ phrases: 6 });
  humeur('parle-moi normalement : j’apprends ta voix sur tes 6 prochaines phrases (au micro)');
});
/* La calibration par registres (demande d'Ahmed relayée par Hakim, 2026-10-20 : reconnu à 0,04-0,47 quand il parlait
   plus aigu ou plus vite depuis son téléphone) : une phrase (3 s au moins) dans chacun des six registres ; l'empreinte
   les garde séparément et reconnaît une phrase par le registre qui lui ressemble le plus. Sur le Mac, puis sur le
   téléphone (ses micros changent la voix). */
const REGISTRES = [
  ['normal', 'Normal : parle-moi 5 secondes comme d’habitude'],
  ['vite', 'Vite : raconte-moi un truc en parlant vite'],
  ['aigu', 'Aigu : comme quand tu es surpris ou enthousiaste'],
  ['bas', 'Bas : doucement, comme fatigué'],
  ['fort', 'Fort : comme si tu parlais à quelqu’un au loin'],
  ['bruit', 'Avec du bruit autour (télé, musique, rue) : parle normalement'],
];
let calibration = null;
async function etapeCalibration() {
  if (!calibration) return;
  if (calibration.i >= REGISTRES.length) {
    calibration = null;
    await afficherEmpreinte();
    return humeur(appareilPage().android ? 'calibration finie sur le téléphone' : 'calibration finie sur le Mac : refais-la depuis le téléphone');
  }
  const [id, consigne] = REGISTRES[calibration.i];
  const registre = `${id}-${appareilPage().android ? 'telephone' : 'mac'}`;
  let avant = 0; try { avant = ((await (await fetch('/api/voix/empreinte', { cache: 'no-store' })).json()).registres || {})[registre] || 0; } catch (_) {}
  Object.assign(calibration, { registre, avant });
  await afficherEmpreinte({ phrases: 1, registre });
  $('etatEmpreinte').textContent = `calibration ${calibration.i + 1}/${REGISTRES.length} — ${consigne} (appuie sur le micro, 3 secondes au moins)`;
  humeur(consigne);
}
$('empreinteCalibrer').addEventListener('click', async () => {
  if (calibration) { calibration = null; await afficherEmpreinte({ phrases: 0 }); return humeur('calibration arrêtée'); }
  calibration = { i: 0 };
  $('empreinteCalibrer').textContent = 'Arrêter la calibration';
  await etapeCalibration();
});
setInterval(async () => {                                   // l'échantillon est appris : registre suivant
  if (!calibration) { if ($('empreinteCalibrer').textContent !== 'Calibrer (6 registres)') $('empreinteCalibrer').textContent = 'Calibrer (6 registres)'; return; }
  let o; try { o = await (await fetch('/api/voix/empreinte', { cache: 'no-store' })).json(); } catch (_) { return; }
  if (!calibration || !calibration.registre) return;
  // avancé seulement quand CET échantillon est appris (le registre a gagné un échantillon) ; si l'écoute a expiré
  // sans rien apprendre (10 min), la même étape est relancée
  if (((o.registres || {})[calibration.registre] || 0) > calibration.avant) { calibration.i++; calibration.registre = null; await etapeCalibration(); }
  else if (o.apprentissage === 0) { calibration.registre = null; await etapeCalibration(); }
}, 1500);

/* ---------- les notifications (Web Push, 2026-10-20) : ses relances et les résultats de ses agents ---------- */
const deb64uOctets = (s) => Uint8Array.from(atob(s.replace(/-/g, '+').replace(/_/g, '/') + '==='.slice((s.length + 3) % 4)), (c) => c.charCodeAt(0));
const b64uOctets = (buf) => btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
// La preuve de présence (audit du cockpit, C-H1) : une empreinte FRAÎCHE pour un geste sensible, liée à ce geste.
// Sur le téléphone : sa passkey ; sur le Mac : Touch ID s'il est activé (sinon rien n'est demandé, comme avant).
function presenceParAppli(defi, action) {
  return new Promise((ok, ko) => {
    window.__presenceApp = (r) => {
      window.__presenceApp = null;
      if (r && r.signature) ok({ app: r.app, defi, signature: r.signature });
      else ko(new Error((r && r.erreur) || 'empreinte annulée ou non reconnue : rien n’a été fait'));
    };
    try { window.HakimApp.presence(defi, action); } catch (e) { window.__presenceApp = null; ko(e); }
  });
}
async function preuvePresence(action) {
  const r = await fetch('/api/presence/options', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() },
    body: JSON.stringify({ action }) });
  const o = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(o.erreur || `erreur ${r.status}`);
  if (o.aucune) return undefined;
  humeur('pose ton doigt : ce geste demande ton empreinte');
  // (2026-10-21) dans l'appli Android, la page n'a pas accès aux passkeys : l'appli demande l'empreinte et signe le défi
  if (window.HakimApp && window.HakimApp.presence) return presenceParAppli(o.challenge, action);
  let cred;
  try {
    cred = await navigator.credentials.get({ publicKey: { challenge: deb64uOctets(o.challenge), rpId: o.rpId, userVerification: 'required',
      timeout: o.timeout, allowCredentials: o.allowCredentials.map((c) => ({ type: 'public-key', id: deb64uOctets(c.id) })) } });
  } catch (e) { throw new Error(e.name === 'NotAllowedError' ? 'empreinte annulée ou non reconnue : rien n’a été fait' : e.message); }
  return { id: b64uOctets(cred.rawId), clientDataJSON: b64uOctets(cred.response.clientDataJSON),
    authenticatorData: b64uOctets(cred.response.authenticatorData), signature: b64uOctets(cred.response.signature) };
}
async function notifsPost(corps) {
  const r = await fetch('/api/notifications', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() }, body: JSON.stringify(corps) });
  const o = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(o.erreur || `erreur ${r.status}`);
  return o;
}
async function afficherNotifs() {
  const ok = 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
  if (!ok) { $('etatNotifs').textContent = 'ce navigateur ne sait pas (prends Chrome à jour)'; $('notifsActiver').hidden = true; return; }
  let abo = null;
  try { const reg = await navigator.serviceWorker.getRegistration('/'); abo = reg && await reg.pushManager.getSubscription(); } catch (_) {}
  $('etatNotifs').textContent = Notification.permission === 'denied' ? 'refusées dans le navigateur (réglages du site → notifications)'
    : abo ? 'actives sur cet appareil' : 'pas encore activées ici';
  $('notifsActiver').hidden = !!abo; $('notifsTester').hidden = !abo;
}
$('notifsActiver').addEventListener('click', async () => {
  try {
    if (await Notification.requestPermission() !== 'granted') throw new Error('permission refusée');
    const reg = await navigator.serviceWorker.register('/sw.js', { scope: '/' });
    await navigator.serviceWorker.ready;
    const { cle } = await (await fetch('/api/notifications', { cache: 'no-store' })).json();
    const abo = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: deb64uOctets(cle) });
    const android = /Android/i.test(navigator.userAgent || '');
    const presence = await preuvePresence('notifications:abonner');
    await notifsPost({ action: 'abonner', abonnement: abo.toJSON(), appareil: android ? 'téléphone' : 'Mac', presence });
    humeur('notifications activées'); afficherNotifs();
  } catch (e) { humeur(`notifications : ${e.message}`); afficherNotifs(); }
});
$('notifsRetirer').addEventListener('click', async () => {
  if (!confirm('Retirer les notifications de TOUS les appareils (par exemple un téléphone perdu) ?')) return;
  try { await notifsPost({ action: 'tout_retirer' }); humeur('notifications retirées de tous les appareils'); afficherNotifs(); } catch (e) { humeur(e.message); }
});
$('notifsTester').addEventListener('click', async () => {
  try { const o = await notifsPost({ action: 'tester' }); humeur(`notification envoyée (${(o.resultats || []).join(', ')})`); }
  catch (e) { humeur(e.message); }
});
if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(() => {});   // installable

/* ---------- le verrou d'empreinte du téléphone (lot A, point 16) ---------- */
async function afficherVerrou() {
  let st; try { st = await (await fetch('/api/verrou', { cache: 'no-store' })).json(); } catch (_) { return; }
  const cles = st.cles || [];
  $('etatVerrou').textContent = st.illisible ? 'fichier du verrou illisible : accès à distance FERMÉ — réassocie un téléphone'
    : !st.actif ? 'aucun téléphone associé : l’accès à distance est fermé tant qu’aucun n’est associé'
    : `actif · ${cles.length} téléphone${cles.length > 1 ? 's' : ''} (${cles.map((c) => c.nom).join(', ')})`;
  $('verrouCode').hidden = st.distant; $('verrouOublier').hidden = st.distant || !st.actif;
  $('verrouAssocierIci').hidden = !st.distant || st.actif; $('verrouFermer').hidden = !st.distant || !st.actif;
  $('groupeTouchId').hidden = st.distant;
  if (!st.distant) {
    const ici = location.hostname === 'localhost';
    $('etatTouchId').textContent = st.touch_id_mac ? 'actif : chaque geste sensible demande ton doigt'
      : ici ? 'pas activé (le jeton de la page suffit, comme avant)' : 'ouvre Hakim sur http://localhost pour l’activer';
    $('touchIdActiver').hidden = st.touch_id_mac || !ici || !window.PublicKeyCredential; $('touchIdRetirer').hidden = !st.touch_id_mac;
  }
}
// L'interrupteur des hormones de Hakim (affect v2, décision d'Ahmed du 2026-10-21) : revenir à la v1 d'un geste
async function afficherHormones() {
  try {
    const o = await (await fetch('/api/hormones', { headers: { 'X-Jeton': jeton() } })).json();
    if (!o.version) throw new Error(o.erreur || '?');
    $('etatHormones').textContent = (o.version === 'v2' ? 'v2 — 13 hormones reliées entre elles' : 'v1 — 9 hormones indépendantes')
      + (o.coincee ? ` · ⚠ ${o.coincee.texte}` : '');
    $('hormonesBasculer').hidden = false;
    $('hormonesBasculer').textContent = o.version === 'v2' ? 'Revenir à la v1' : 'Passer à la v2';
    $('hormonesBasculer').dataset.vers = o.version === 'v2' ? 'v1' : 'v2';
  } catch (e) { $('etatHormones').textContent = `indisponible (${e.message})`; }
}
$('hormonesBasculer').addEventListener('click', async () => {
  const vers = $('hormonesBasculer').dataset.vers;
  if (!confirm(vers === 'v2' ? 'Passer Hakim aux hormones v2 (reliées entre elles) ?' : 'Revenir aux hormones v1 ?')) return;
  try {
    const r = await fetch('/api/hormones', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() }, body: JSON.stringify({ version: vers }) });
    const o = await r.json();
    if (!r.ok) throw new Error(o.erreur || `erreur ${r.status}`);
    humeur(`hormones de Hakim : ${o.version}`); afficherHormones();
  } catch (e) { humeur(e.message); }
});
afficherHormones();
$('touchIdActiver').addEventListener('click', async () => {
  try {
    const o = await verrouPoster('/api/verrou/mac/options');
    const cred = await navigator.credentials.create({ publicKey: {
      challenge: deb64uOctets(o.challenge), rp: o.rp, timeout: o.timeout, attestation: o.attestation,
      user: { id: deb64uOctets(o.user.id), name: o.user.name, displayName: o.user.displayName },
      pubKeyCredParams: o.pubKeyCredParams, authenticatorSelection: o.authenticatorSelection } });
    await verrouPoster('/api/verrou/mac/associer', { reponse: { clientDataJSON: b64uOctets(cred.response.clientDataJSON),
      attestationObject: b64uOctets(cred.response.attestationObject) } });
    humeur('Touch ID activé : les gestes sensibles demanderont ton doigt'); afficherVerrou();
  } catch (e) { humeur(e.name === 'NotAllowedError' ? 'Touch ID annulé' : e.message); }
});
$('touchIdRetirer').addEventListener('click', async () => {
  if (!confirm('Retirer Touch ID ? Sur le Mac, le jeton de la page suffira de nouveau pour les gestes sensibles.')) return;
  try { await verrouPoster('/api/verrou/mac/oublier'); afficherVerrou(); } catch (e) { humeur(e.message); }
});
const ACTIONS_VERROU = { '/api/verrou/code': 'verrou:code', '/api/verrou/oublier': 'verrou:oublier', '/api/verrou/mac/oublier': 'verrou:oublier-mac' };
async function verrouPoster(route, corps = {}) {
  if (ACTIONS_VERROU[route]) corps = { ...corps, presence: await preuvePresence(ACTIONS_VERROU[route]) };
  const r = await fetch(route, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() }, body: JSON.stringify(corps) });
  const o = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(o.erreur || `erreur ${r.status}`);
  return o;
}
$('verrouCode').addEventListener('click', async () => {
  try {
    const o = await verrouPoster('/api/verrou/code');
    $('etatVerrou').textContent = `code ${o.code.slice(0, 3)} ${o.code.slice(3)} — sur le téléphone, ouvre ${o.adresse || 'l’adresse Tailscale'} et tape-le (10 min, une seule fois)`;
  } catch (e) { humeur(e.message); }
});
$('verrouOublier').addEventListener('click', async () => {
  if (!confirm("Oublier tous les téléphones associés ?\nLe téléphone redevient protégé par le compte Tailscale seul, jusqu'à une nouvelle association.")) return;
  try { await verrouPoster('/api/verrou/oublier'); afficherVerrou(); } catch (e) { humeur(e.message); }
});
$('verrouFermer').addEventListener('click', async () => {
  try { await verrouPoster('/api/verrou/verrouiller'); location.reload(); } catch (e) { humeur(e.message); }
});
$('nouvelle').addEventListener('click', () => {
  arreterTout(); arreterMicro(false);
  etat.session = null; etat.messages = [];
  debutConversation = Date.now();                         // partagée : l'autre appareil repart aussi de zéro
  sauver(); rendre(); humeur();
});
$('micro').addEventListener('click', basculerMicro);
$('envoyer').addEventListener('click', () => envoyer($('q').value, false));
$('stop').addEventListener('click', () => { arreterTout(); majBoutonsPause(); rendre(); humeur(); });
$('q').addEventListener('input', () => { ajuster(); activite(); });
$('q').addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); envoyer($('q').value, false); }
});
document.addEventListener('keydown', (e) => {
  if (e.altKey && e.code === 'KeyM') { e.preventDefault(); basculerMicro(); }
  else if (e.altKey && e.code === 'KeyC') { e.preventDefault(); basculerConversation(); }
  else if (e.altKey && e.code === 'KeyX') { e.preventDefault(); basculerMuet(); }
  else if (e.altKey && e.code === 'KeyV') { e.preventDefault(); basculerCamera(); }
  else if (e.altKey && e.code === 'KeyP') { e.preventDefault(); if (lecteur.enPause) reprendreVoix(); else pauseVoix(); }
  else if (e.key === 'Escape') { if (etat.conversation) finirConversation(false); arreterMicro(false); arreterTout(); majBoutonsPause(); rendre(); humeur(); }
});
$('conversation').addEventListener('click', basculerConversation);
$('finConversation').addEventListener('click', (e) => { e.stopPropagation(); finirConversation(); });
$('muet').addEventListener('click', basculerMuet);
$('pause').addEventListener('click', () => {
  if (lecteur.enPause) reprendreVoix();
  else if (!pauseVoix()) humeur('il ne parle pas en ce moment : rien à mettre en pause');
});
$('camera').addEventListener('click', basculerCamera);
$('muetScene').addEventListener('click', (e) => { e.stopPropagation(); basculerMuet(); });
window.addEventListener('pagehide', () => {
  finirConversation(false);
  arreterCamera();
  // (2026-10-21) la page se ferme : la réponse en cours continue sur le Mac et l'attendra dans la conversation
  for (const m of etat.messages) if (m.enCours) { m.enCours = false; m.attenteServeur = true; }
  sauver();
  arreterTout(false); arreterMicro(false);
});

function afficherSecours(o) {
  const api = (o && o.api) || {}, ab = (o && o.abonnement) || {};
  $('etatCle').textContent = (o && o.api_panne) ? `API en panne : ${o.api_panne} (le cerveau local prend le relais)`
    : api.fin ? `clé enregistrée (…${api.fin})` : api.trousseau ? 'clé du trousseau (anamnese-anthropic-api) branchée'
    : api.cle ? 'clé branchée' : 'aucune clé : sans elle, le secours passe directement au cerveau local';
  const f = ab.info && ab.info.fenetres;
  const pct = (x) => (x && Number.isFinite(x.utilization) ? Math.round(x.utilization * 100) + ' %' : '?');
  const quand = (t) => new Date(t * 1000).toLocaleString('fr-FR', { weekday: 'short', hour: '2-digit', minute: '2-digit' });
  $('etatForfait').textContent = ab.limite_jusqua
    ? `forfait à sa limite jusqu'à ${quand(ab.limite_jusqua / 1000)} : Hakim passe par ${api.cle ? "l'API" : 'son cerveau local'}`
    : (f ? `forfait : ${pct(f.five_hour)} des 5 h, ${pct(f.seven_day)} de la semaine${f.seven_day && f.seven_day.resetsAt ? ' (remise à zéro ' + quand(f.seven_day.resetsAt) + ')' : ''}` : '');
}
async function enregistrerCle(cle) {
  try {
    let presence;
    try { presence = await preuvePresence('cle-api'); } catch (e) { return humeur(e.message); }
    const r = await fetch('/api/jarvis/cle-api', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() },
      body: JSON.stringify({ cle, presence }) });
    const o = await r.json().catch(() => ({}));
    if (!r.ok) return humeur(o.erreur || 'clé refusée');
    $('cleApi').value = '';
    afficherSecours({ api: o });
    humeur(o.cle ? 'clé API enregistrée : le secours est prêt' : 'clé API effacée');
    verifierServeur();
  } catch (_) { humeur('clé impossible à enregistrer'); }
}
$('enregistrerCle').addEventListener('click', () => enregistrerCle($('cleApi').value.trim()));
$('effacerCle').addEventListener('click', () => { if (confirm('Effacer la clé API de secours ?')) enregistrerCle(''); });

async function verifierServeur() {
  try {
    const o = await (await fetch('/api/jarvis/etat')).json();
    afficherSecours(o);
    etat.sttLocal = !!o.stt_local;
    etat.ttsLocal = !!o.tts_local;
    const optVoix = $('voix').querySelector('option[value=neuronale]');
    optVoix.disabled = !etat.ttsLocal;
    if (!etat.ttsLocal) optVoix.textContent = 'neuronale · pas encore installée';
    const opt = $('reconnaissance').querySelector('option[value=locale]');
    opt.disabled = !etat.sttLocal;
    opt.textContent = etat.sttLocal ? 'locale · Whisper (hors ligne)' : 'locale · Whisper (pas encore installée)';
    if (!etat.sttLocal && etat.reglages.reconnaissance === 'locale') etat.reglages.reconnaissance = 'navigateur';
    if (etat.sttLocal && !localStorage.getItem(CLE + '.choixStt')) {          // première fois : préférer le local
      etat.reglages.reconnaissance = 'locale';
      try { localStorage.setItem(CLE + '.choixStt', '1'); } catch (_) {}
    }
    appliquerReglages();
  } catch (_) {}
}

/* ---------- démarrage ---------- */
charger();
appliquerReglages();
if (window.top !== window) {
  $('bandeau').hidden = false;
  $('bandeau').textContent = 'Dans le panneau de VS Code, le micro est bloqué : ouvre http://localhost:4317/parler dans Chrome ou Safari pour parler à Hakim.';
}
rendre(); humeur();
verifierServeur();
lireInterieur(); setInterval(lireInterieur, 30000);
synchroniser(); setInterval(() => { if (document.visibilityState === 'visible') synchroniser(); }, 5000);
document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') { synchroniser(); accuserReception(); } });
signalerPresence(); setInterval(signalerPresence, 15000);
document.addEventListener('visibilitychange', signalerPresence);
ecouterPensees();
missionsAuChargement();
ecrituresAuChargement();
reglesAuChargement();
identiteAuChargement();
sortiesAuChargement();
$('q').focus();
