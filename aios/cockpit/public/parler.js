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
  reglages: { modele: 'opus', modeleConversation: 'auto', reconnaissance: 'navigateur', langue: 'auto', voix: 'neuronale', voixFr: '', voixAr: '',
    vitesse: 1.05, lectureAuto: false, patience: 3.5, scene: true, rapide: true, source: 'auto', volant: false, position: false, voixNeutre: false, sesParoles: true, patienceConversation: 0.3 },
  sttLocal: false, ttsLocal: false,
  interieur: null, derniereActivite: Date.now(), dites: [],
  conversation: null, present: [], parleDepuis: 0, coupeParAhmed: false, vision: null,
};
// (2026-10-23) le Mac injoignable : ce qui attend son retour (voir reprendreHorsLigne) ; panne : « reseau » (rien ne
// répond) ou « serveur » (le Mac répond, la transcription non)
const horsLigne = { depuis: 0, tours: [], envois: [], enCours: false, panne: 'reseau' }, HORS_LIGNE_MAX_MS = 8000;
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
  // (31/10, 09:20, Ahmed) Haiku 5.5 revient, à la main ou en auto ; un réglage inconnu repasse à Opus ou Sonnet
  if (!['sonnet', 'opus', 'haiku', 'auto'].includes(etat.reglages.modele)) etat.reglages.modele = 'opus';
  if (!['sonnet', 'opus', 'haiku', 'auto'].includes(etat.reglages.modeleConversation)) etat.reglages.modeleConversation = 'sonnet';
  if (!['auto', 'abonnement', 'api', 'local', 'gemma'].includes(etat.reglages.source)) etat.reglages.source = 'auto';
  // Ahmed (2026-10-18) : par défaut, la langue est DÉTECTÉE parmi le français, l'arabe et l'anglais (plus
  // jamais l'islandais) ; l'ancien défaut « français » passe une fois à ce mode, son choix reste libre ensuite
  try {
    if (!localStorage.getItem(CLE + '.langues3')) {
      if (etat.reglages.langue === 'fr-FR') etat.reglages.langue = 'auto';
      localStorage.setItem(CLE + '.langues3', '1');
    }
    // (26/10, Ahmed : « Sonnet ↔ Opus selon la difficulté ») en conversation, l'automatique devient le défaut : l'ancien
    // « Sonnet » passe une fois en automatique, son choix reste libre ensuite
    // (04/11) dans l'appli, la voix du téléphone devient le défaut, une fois ; son choix reste libre ensuite (réglages)
    if (window.HakimApp && window.HakimApp.voixTelephone && !localStorage.getItem(CLE + '.voixTelephone')) {
      etat.reglages.voix = 'telephone';
      localStorage.setItem(CLE + '.voixTelephone', '1');
    }
    if (!localStorage.getItem(CLE + '.modeleAuto')) {
      if (etat.reglages.modeleConversation === 'sonnet') etat.reglages.modeleConversation = 'auto';
      localStorage.setItem(CLE + '.modeleAuto', '1');
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
          garderCaches(o.messages);
          etat.messages = o.messages;
          debutConversation = Number(o.debut_ms) || debutConversation;
          rendre();
        }
        garderLocal();
      }).catch(() => {});
  }, 600);
}
let synchroEnAttente = 0;
// (21:34, Hakim : « mes paroles s'affichent toujours ») une copie du cockpit ne remet pas à l'écran ce qui était « dans ta tête »
function garderCaches(messages) {
  const caches = new Set(etat.messages.filter(m => m && m.cache).map(m => String(m.id)));
  for (const m of messages) if (m && caches.has(String(m.id))) m.cache = true;
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
    // (2026-10-23, bug : ses tours « de lui-même » entendus mais jamais affichés) passé 1 000 messages, le cockpit oublie
    // les plus anciens ; la page les gardait, les croyait « jamais vus », les renvoyait (sans y arriver : seuls les 150
    // derniers partent) et ne prenait PLUS JAMAIS la conversation du cockpit. Un message plus ancien que le plus ancien
    // du cockpit n'est pas neuf : c'est de l'histoire qu'il a rangée.
    const plusAncien = o.messages.length ? Math.min(...o.messages.map(quand).filter(x => x > 0)) : 0;
    const neufs = etat.messages.filter(m => !m.enCours && !vus.has(m.id) && quand(m) >= (Number(o.debut_ms) || 0) && quand(m) > plusAncien);
    if (neufs.length && ++synchroEnAttente < 3) return sauver();
    if (neufs.length) {                       // toujours refusés après trois essais : fusionnés ici, rien n'est perdu
      journalVoix('synchro_fusion_locale', { n: neufs.length });
      o.messages = o.messages.concat(neufs).map((m, i) => [m, i]).sort((x, y) => (quand(x[0]) - quand(y[0])) || (x[1] - y[1])).map(x => x[0]);
    }
    synchroEnAttente = 0;
    majConversation = Number(o.maj_ms);
    debutConversation = Number(o.debut_ms) || 0;
    etat.session = o.session || null;
    garderCaches(o.messages);
    etat.messages = o.messages;
    garderLocal();
    rendre();
    await accuserReception();                              // ce qu'il a dit de lui-même pendant ton absence est vu
  } catch (_) {}
}

/* ---------- voix (synthèse) ---------- */
// (04/11, 12:25) ce que sa voix a dit ces 30 dernières secondes, et son écho : une phrase « de papa » dont les trois cinquièmes des mots
// (3 lettres et plus) sont les siens, reprise par le micro
function noterSaVoix(t) {
  const maintenant = Date.now();
  etat.saVoix = (etat.saVoix || []).filter(x => maintenant - x.t < 30000).concat([{ t: maintenant, texte: String(t || '') }]).slice(-40);
}
function echoDeSaVoix(texte) {
  const mots = (x) => String(x || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/\[[^\]]*\]/g, ' ')
    .split(/[^\p{L}\p{N}]+/u).filter(m => m.length >= 3);
  const m1 = mots(texte);
  if (m1.length < 3) return false;
  const siens = new Set(mots((etat.saVoix || []).filter(x => Date.now() - x.t < 30000).map(x => x.texte).join(' ')));
  return m1.filter(m => siens.has(m)).length / m1.length >= 0.6;
}
/* (04/11, Ahmed : « la différence entre la voix du Mac et Chatterbox ? j'aimerais que ça utilise la voix du smartphone quand c'est sur le
   smartphone ») dans l'appli (1.55), la voix du TÉLÉPHONE (son moteur Android) prend la place de la voix du système : instantanée, sans
   réseau, sans charger le Mac ; la page la parle comme une voix de navigateur (speak, cancel) ; chaque phrase dit son début et sa fin. */
const synthTelephone = window.HakimApp && window.HakimApp.voixTelephone ? (() => {
  const enAttente = new Map(), ecouteurs = []; let n = 0;
  // (1.56, 04/11, Ahmed : « une voix de femme, pas naturelle ») les voix du moteur du téléphone ; sans choix dans les réglages, une voix
  // d'homme (Samsung « SMTm », Google « x-frb » / « x-frd ») ; sa hauteur et son débit suivent son émotion du moment
  const voix = () => { try { return JSON.parse(window.HakimApp.voixTelephoneListe ? window.HakimApp.voixTelephoneListe() : '[]')
    .map(v => ({ name: v.name, voiceURI: v.name, lang: v.lang, localService: !!v.local, default: false })); } catch (_) { return []; } };
  const homme = () => voix().filter(v => /^fr/i.test(v.lang)).find(v => /SMTm\d|x-fr[bd]|\bmale\b|homme/i.test(v.name) && !/female|SMTf/i.test(v.name));
  // ce que la voix du téléphone reçoit : le texte, le débit (son émotion), la langue, la voix choisie dans les réglages ; sinon (le
  // lecteur prend la première voix française, souvent une femme) une voix d'homme
  const argumentsDe = (u) => {
    const debit = (Number(u.rate) || 1) * (typeof tempoVoix === 'function' ? tempoVoix() : 1);
    const choisie = typeof etat !== 'undefined' && (/^ar/i.test(String(u.lang || '')) ? etat.reglages.voixAr : etat.reglages.voixFr) ? u.voice : null;
    const v = choisie && choisie.name ? choisie : (/^ar/i.test(String(u.lang || '')) ? null : homme());
    return [String(u.text || ''), debit, String(u.lang || 'fr-FR'), v ? String(v.name) : ''];
  };
  const hauteur = () => {
    const e = typeof etat !== 'undefined' && etat.interieur && !etat.reglages.voixNeutre ? Number(etat.interieur.expressivite) : NaN;
    return Number.isFinite(e) ? Math.max(0.85, Math.min(1.1, 0.95 + (e - 0.5) * 0.4)) : 0.95;
  };
  setTimeout(() => ecouteurs.forEach(f => { try { f(); } catch (_) {} }), 1500);   // le moteur s'est préparé : la liste des voix change
  setTimeout(() => ecouteurs.forEach(f => { try { f(); } catch (_) {} }), 5000);
  window.HakimVoixTel = (quoi, id) => {
    // (1.59, 04/11, Ahmed : « j'arrive pas à sélectionner Supertonic dans les réglages ») l'appli dit que ses voix ont changé
    // (Supertonic téléchargé, prêt) : la liste des réglages se refait
    if (quoi === 'voix') { ecouteurs.forEach(f => { try { f(); } catch (_) {} }); return; }
    const u = enAttente.get(id); if (!u) return;
    if (quoi === 'debut') { if (u.onstart) u.onstart(); return; }
    enAttente.delete(id); if (u.onend) u.onend();
  };
  // (1.63, 04/11) ce que sa voix a mis à sortir : jusqu'à tes écouteurs
  window.HakimVoixMesure = (id, m) => { const u = enAttente.get(id); if (u && typeof mesurerVoix === 'function') mesurerVoix(u, m); };
  return {
    speak(u) {
      const id = `t${++n}`; enAttente.set(id, u);
      u._appelPage = Date.now(); u._origine = typeof origineDe === 'function' ? origineDe(u.text) : null;   // (04/11) pour sa mesure
      if (typeof noterSaVoix === 'function') noterSaVoix(u.text);      // (04/11, 12:25) pour reconnaître son écho
      try {
        if (window.HakimApp.voixTelephoneVoix) {
          const [texte, debit, langue, nom] = argumentsDe(u);
          window.HakimApp.voixTelephoneVoix(id, texte, debit, langue, nom, hauteur());
        } else window.HakimApp.voixTelephone(id, String(u.text || ''), (Number(u.rate) || 1) * (typeof tempoVoix === 'function' ? tempoVoix() : 1), String(u.lang || 'fr-FR'));
      } catch (_) { window.HakimVoixTel('fin', id); }
    },
    // (1.60, 04/11) sa voix calculée d'avance sur le téléphone, avec exactement ce que speak lui donnera ensuite
    prepare(u) { try { if (window.HakimApp.voixTelephonePreparer) window.HakimApp.voixTelephonePreparer(...argumentsDe(u)); } catch (_) {} },
    cancel() { const fins = [...enAttente.values()]; enAttente.clear(); try { window.HakimApp.voixTelephoneArreter(); } catch (_) {} fins.forEach(u => u.onend && u.onend()); },
    getVoices() { return voix(); },
    // (04/11, capture d'Ahmed : la page vide dans l'appli 1.55) la page écoute « voiceschanged » sur la voix du système : sans ces
    // méthodes, elle s'arrêtait net au chargement
    addEventListener(type, f) { if (type === 'voiceschanged' && typeof f === 'function') ecouteurs.push(f); }, removeEventListener() {},
    pause() {}, resume() {}, speaking: false, pending: false,
  };
})() : null;
class EnonceTelephone { constructor(t) { this.text = t; } }
const synth = synthTelephone || window.speechSynthesis || null;
let toutesVoix = [];
const voixPour = (langue) => {
  if (!toutesVoix.length && synth) toutesVoix = synth.getVoices();      // liste parfois chargée tard
  return Voix.choisirVoix(toutesVoix, langue, langue === 'ar' ? etat.reglages.voixAr : etat.reglages.voixFr);
};
// (2026-10-22, Ahmed) le débit suit aussi son émotion, modérément (×0,94 à ×1,04, réglé par le démon) ; ton réglage reste la base
// (2026-10-22, 16:10, Ahmed) « voix neutre » : ni le débit ni l'expressivité de son émotion
// (2026-10-23) les prononciations locales (son prénom écrit en arabe, dit à la française) : chargées une fois
fetch('/api/voix/prononciations', { cache: 'no-store' }).then(r => r.json()).then(d => Voix.definirPrononciations(d)).catch(() => {});
// (26/10, Ahmed : « que la voix suive mieux ») le SENS de chaque phrase nuance l'expressivité de son humeur : une victoire ou
// une exclamation un peu plus vive, une mauvaise nouvelle ou une excuse un peu plus douce, une question à peine relevée.
// Le cockpit borne ensuite à la plage sûre de Chatterbox.
const expressivitePhrase = (base, texte) => Voix.expressivitePhrase(base, texte);   // (28/10) dans voix.js, partagé avec le cockpit
// (26/10, 13:30, Ahmed : « fatigué, il sonne comme un ogre ») le rythme de son état ne passe plus par la vitesse de lecture
// (elle changeait aussi la hauteur, comme une bande) : la voix l'applique elle-même, à hauteur constante (tempo, ci-dessous)
const vitesseVoix = () => (etat.reglages.vitesse || 1);
const tempoVoix = () => etat.reglages.voixNeutre ? 1 : Math.max(0.86, Math.min(1.12, Number(etat.interieur && etat.interieur.voix_vitesse) || 1));
// (28/10) ses débuts de réponse dont le cockpit a la voix toute prête (debuts.js) : demandés au début de chaque réponse
const palierVoix = (x, pas) => (Number.isFinite(Number(x)) && x !== null ? (Math.round(Number(x) / pas) * pas).toFixed(2) : '-');
const emotionDebut = (d) => (etat.interieur && !etat.reglages.voixNeutre ? expressivitePhrase(etat.interieur.expressivite, d) : null);
const cleDebut = (d) => `${d.toLowerCase().replace(/\s+/g, ' ')}|${palierVoix(emotionDebut(d), 0.1)}|${palierVoix(tempoVoix(), 0.05)}`;
let debutsPrets = new Set();
async function chargerDebutsPrets() {
  try {
    const e = emotionDebut('Oui frérot,'), t = tempoVoix();
    const r = await fetch(`/api/voix/debuts?langue=fr${e === null ? '' : `&emotion=${e}`}&tempo=${t}`, { headers: { 'X-Jeton': jeton() }, cache: 'no-store' });
    if (!r.ok) return;
    const o = await r.json();
    debutsPrets = new Set((o.prets || []).map(([d, pe]) => `${String(d).toLowerCase()}|${pe}|${o.palier_tempo}`));
    chargerMeubles();
  } catch (_) {}
}
// (03/11, Hakim pour papa ; 13:30 : « ses propres meubles, paramétrables ») ses MEUBLES (/api/jarvis/meubles ; il les crée et les
// règle : meuble_creer, meuble_regler) prêts à jouer sans attendre : une parole, sa voix gardée par le cockpit (debuts.js),
// demandée seulement si elle est prête (« gardee » : jamais une synthèse de plus) ; un de ses sons (e12) ; un souffle ou une
// respiration, fabriqués ici. Décodés une fois, rechargés au début de chaque réponse.
// (relecture) l'identifiant d'un meuble pour ses synapses : son nom en lettres simples (« Voyons voir… » → voyons_voir)
const slugMeuble = (nom) => String(nom || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z]+/g, '_').replace(/^_+|_+$/g, '').slice(0, 30);
// (04/11, l'élagage de ses synapses) ses meubles : leurs poids et ceux qui sont élagués, relus toutes les 60 s
const synapsesMeubles = { poids: {}, elagues: new Set(), t: 0 };
function relireSynapsesMeubles() {
  if (Date.now() - synapsesMeubles.t < 60000 || typeof fetch !== 'function') return;
  synapsesMeubles.t = Date.now();
  fetch('/api/jarvis/synapses?famille=meuble', { headers: { 'X-Jeton': jeton() }, cache: 'no-store' }).then(r => (r.ok ? r.json() : null)).then((o) => {
    const f = (o && o.familles && o.familles.meuble) || {};
    synapsesMeubles.poids = Object.fromEntries(Object.entries(f).map(([k, v]) => [k, Number(v.poids)]));
    synapsesMeubles.elagues = new Set(Object.entries(f).filter(([, v]) => v.elaguee).map(([k]) => k));
  }).catch(() => {});
}
const meublesPrets = new Map();                     // nom → { nom, texte, pret, volume, dureeMax, quand, etats, actif, voix, cle }
let meublesListe = [], dernierMeuble = '', dernierEtaitVoix = null;
const sansAccent = (t) => String(t || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();
// un bruit d'air, sans voix : un bruit filtré (de l'air, pas un sifflement) sous une enveloppe — un souffle qui part et s'éteint,
// une respiration qui monte et retombe
function bruitDAir(genre, ms) {
  const sr = actx.sampleRate, n = Math.max(1, Math.round(sr * ms / 1000)), b = actx.createBuffer(1, n, sr), d = b.getChannelData(0);
  const lisse = genre === 'respiration' ? 0.06 : 0.12;
  let y = 0;
  for (let i = 0; i < n; i++) {
    y += lisse * ((Math.random() * 2 - 1) - y);
    const q = i / n, env = genre === 'respiration' ? Math.pow(Math.sin(Math.PI * q), 1.5) : Math.min(1, q * 10) * Math.pow(1 - q, 2);
    d[i] = y * env * 2.5;
  }
  return b;
}
async function chargerMeubles() {
  if (!actx || actx.state !== 'running') return;
  try {
    const r = await fetch('/api/jarvis/meubles', { headers: { 'X-Jeton': jeton() }, cache: 'no-store' });
    if (r.ok) { const o = await r.json(); meublesListe = (o.meubles || []).filter(m => m && m.nom); lecteurNeuronal.rythme = o.rythme || null; }   // (15:24)
  } catch (_) {}
  const noms = new Set(meublesListe.map(m => m.nom));
  for (const k of [...meublesPrets.keys()]) if (!noms.has(k)) meublesPrets.delete(k);
  for (const m of meublesListe) {
    if (m.texte && m.langue && m.langue !== 'fr') continue;            // (04/11) la voix de Chatterbox ici : ses meubles en français
    const base = { nom: m.nom, texte: m.texte || m.nom, volume: Number(m.volume) || 1, dureeMax: m.duree_ms ? m.duree_ms / 1000 : 0,
      quand: m.quand || 'partout', etats: (m.etats || []).map(sansAccent), actif: m.actif !== false, voix: !!m.texte, brut: !m.texte };
    const deja = meublesPrets.get(m.nom);
    try {
      if (m.texte) {
        const c = cleDebut(m.texte);                               // sa voix suit le niveau de voix du moment
        if (deja && deja.cle === c) { Object.assign(deja, base); continue; }
        if (!debutsPrets.has(c)) continue;
        const r = await fetch('/api/voix/dire', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() },
          body: JSON.stringify({ texte: m.texte, langue: 'fr', emotion: emotionDebut(m.texte), tempo: tempoVoix(), gardee: true }) });
        if (r.ok) meublesPrets.set(m.nom, { ...base, cle: c, pret: await actx.decodeAudioData(await r.arrayBuffer()) });
      } else if (m.son) {
        if (deja && deja.cle === m.son) { Object.assign(deja, base); continue; }
        const r = await fetch(`/api/sons/joue/${m.son}`, { headers: { 'X-Jeton': jeton() }, cache: 'no-store' });
        if (r.ok) meublesPrets.set(m.nom, { ...base, cle: m.son, pret: await actx.decodeAudioData(await r.arrayBuffer()) });
      } else if (m.genre) {
        const c = `${m.genre}|${m.duree_ms || 0}`;
        if (deja && deja.cle === c) { Object.assign(deja, base); continue; }
        meublesPrets.set(m.nom, { ...base, cle: c, dureeMax: 0, pret: bruitDAir(m.genre, m.duree_ms || (m.genre === 'respiration' ? 900 : 500)) });
      }
    } catch (_) {}
  }
}
// (13:30) le choix de son subconscient pendant un trou : ceux de ce moment (« avant » son premier mot, « entre » deux bouts) ;
// ceux de son état d'abord (son émotion du moment), sinon ceux de l'hésitation et ceux de tous les états ; en alternant une
// parole et un souffle, jamais deux fois le même
function choisirMeuble({ avant } = {}, prets = [...meublesPrets.values()], etatMot = etat.interieur && (etat.interieur.voix_emotion || etat.interieur.humeur)) {
  const quand = avant ? 'avant' : 'entre';
  const tous = prets.filter(m => m.actif && m.pret && (m.quand === 'partout' || m.quand === quand));
  // (04/11, l'élagage de ses synapses) un meuble élagué (suivi de coupures) n'est plus choisi, sauf 5 fois sur 100 (il peut repousser) ;
  // tous élagués : il en garde quand même
  if (typeof relireSynapsesMeubles === 'function') relireSynapsesMeubles();
  const syn = typeof synapsesMeubles !== 'undefined' ? synapsesMeubles : null, explore = Math.random() < 0.05;
  const slug = typeof slugMeuble === 'function' ? slugMeuble : (x) => x;
  const vivants = syn && !explore ? tous.filter(m => !syn.elagues.has(slug(m.nom))) : tous;
  const ok = vivants.length ? vivants : tous;
  if (!ok.length) return null;
  const e = sansAccent(etatMot), pour = (x) => ok.filter(m => m.etats.includes(x));
  let choix = e && pour(e).length ? pour(e) : pour('hesitation').concat(ok.filter(m => !m.etats.length));
  if (!choix.length) choix = ok;
  const neufs = choix.filter(m => m.nom !== dernierMeuble);
  const alternes = neufs.filter(m => dernierEtaitVoix === null || m.voix !== dernierEtaitVoix);
  const pool = alternes.length ? alternes : (neufs.length ? neufs : choix);
  // entre les vivants, le tirage suit leur poids (1 sans mesure)
  const poids = pool.map(m => (syn && Number.isFinite(syn.poids[slug(m.nom)]) ? Math.max(0.05, syn.poids[slug(m.nom)]) : 1)), total = poids.reduce((a, b) => a + b, 0);
  let r = Math.random() * total, k = 0;
  while (k < pool.length - 1 && r >= poids[k]) { r -= poids[k]; k++; }
  const h = pool[k];
  dernierMeuble = h.nom; dernierEtaitVoix = h.voix;
  return h;
}
// (14:20, Ahmed : « que ces trucs pour meubler s'étalent sur toute la durée de la pause ») ; (14:40, Ahmed : « la transition, c'est
// juste rallonger la note, le timbre du mot précédent, et faire émerger progressivement le mot suivant, sans rien mélanger : pas une
// répétition, une extension temporelle, comme la dernière lettre en slow motion sans en modifier le timbre ; et pour le meuble
// suivant, l'inverse : sa première lettre commence lentement, au même rythme que le dernier instant du premier, et accélère
// progressivement. m + alors = « mmmaaalors » : le m décélère jusqu'à la vitesse minimale, le a repart de là et accélère ») un meuble
// au RALENTI : sa voix rejouée à vitesse variable, sans changer sa hauteur ni son timbre (WSOLA : des tranches de 20 ms posées tous
// les 10 ms, chacune prise là où elle prolonge le mieux la précédente). Sa vitesse part de vDebut (la vitesse où le meuble d'avant
// s'est arrêté) et accélère jusqu'à la normale sur sa première lettre ; à la normale au milieu ; elle décélère sur sa dernière
// lettre jusqu'à vFin, la plus lente, calculée pour qu'il dure ce qu'on veut. Rend { tampon, vFin } : le meuble suivant repart de vFin.
function ralentirMeuble(buf, duree, vDebut = 0.35) {
  const sr = buf.sampleRate, d = buf.getChannelData(0);
  const an = buf._boucle || (buf._boucle = analyserMeuble(d, sr));
  if (!an.max) return { tampon: buf, vFin: vDebut };
  const voix = d.subarray(an.a, an.b + 1), D = voix.length;
  const Hs = Math.round(0.01 * sr), N = 2 * Hs, tol = Math.round(0.012 * sr);
  if (D < 4 * N) return { tampon: buf, vFin: vDebut };
  // sa première lettre (A) accélère ; sa dernière (B) décélère sur sa première moitié, puis tient le ralenti le plus lent (le cœur de
  // la transition) jusqu'au bout
  const A = Math.min(Math.round(0.12 * sr), Math.round(D * 0.3)), B = Math.min(Math.round(0.25 * sr), Math.round(D * 0.5));
  const lisse = (q) => q * q * (3 - 2 * q);
  const vitesse = (x, vFin) => (x < A ? vDebut + (1 - vDebut) * lisse(x / A) : x < D - B ? 1 : 1 - (1 - vFin) * lisse(Math.min(1, 2 * (x - (D - B)) / B)));
  const pas = Math.max(1, Math.round(0.002 * sr));
  const dureeAvec = (vFin) => { let t = 0; for (let x = 0; x < D; x += pas) t += pas / vitesse(x, vFin); return t / sr; };
  // la vitesse la plus lente, au bout : ce qu'il faut pour durer « duree » (jamais plus lent que 1/30)
  let lo = 0.033, hi = 1;
  if (dureeAvec(lo) <= duree) hi = lo;
  else for (let k = 0; k < 28; k++) { const m = (lo + hi) / 2; if (dureeAvec(m) > duree) lo = m; else hi = m; }
  const vFin = Math.min(1, hi);
  const total = Math.round(dureeAvec(vFin) * sr);
  const out = new Float32Array(total + 2 * N), fen = new Float32Array(N);
  for (let i = 0; i < N; i++) fen[i] = 0.5 - 0.5 * Math.cos(2 * Math.PI * i / N);
  let x = 0, prec = 0, w = 0;
  while (w < total && x < D - N) {
    let c = Math.min(D - N - 1, Math.round(x));
    if (w > 0) {                                                   // la tranche qui prolonge le mieux la précédente
      const nat = prec + Hs, lo2 = Math.max(0, c - tol), hi2 = Math.min(D - N - 1, c + tol);
      let best = c, score = -Infinity;
      for (let k = lo2; k <= hi2; k++) {
        let t = 0;
        for (let i = 0; i < N; i += 3) t += (nat + i < D ? voix[nat + i] : 0) * voix[k + i];
        if (t > score) { score = t; best = k; }
      }
      c = best;
    }
    for (let i = 0; i < N; i++) out[w + i] += voix[c + i] * fen[i];
    prec = c; w += Hs; x += Hs * vitesse(x, vFin);
  }
  const lon = Math.max(N, Math.min(out.length, w + Hs));
  const tampon = actx.createBuffer(1, lon, sr), o = tampon.getChannelData(0);
  o.set(out.subarray(0, lon));
  return { tampon, vFin };
}
// ses bords sans voix, et sa voyelle la plus tenue : des fenêtres de 40 ms ; la période (70 à 400 Hz) par autocorrélation normalisée
function analyserMeuble(d, sr) {
  let max = 0;
  for (let i = 0; i < d.length; i++) max = Math.max(max, Math.abs(d[i]));
  if (!max) return { max: 0 };
  let a = 0, b = d.length - 1;
  while (a < b && Math.abs(d[a]) < max * 0.05) a++;
  while (b > a && Math.abs(d[b]) < max * 0.05) b--;
  const voix = d.subarray(a, b + 1), n = voix.length;
  const fen = Math.round(0.04 * sr), saut = Math.round(0.01 * sr), lagMin = Math.floor(sr / 400), lagMax = Math.ceil(sr / 70);
  let meilleur = null;
  for (let p0 = 0; p0 + fen + lagMax < n; p0 += saut) {
    let e = 0;
    for (let i = p0; i < p0 + fen; i++) e += voix[i] * voix[i];
    if (e < fen * (max * 0.1) ** 2) continue;                   // trop faible pour être sa voyelle
    let r = 0, lag = 0;
    for (let L = lagMin; L <= lagMax; L++) {
      let s = 0, e2 = 0;
      for (let i = p0; i < p0 + fen; i++) { s += voix[i] * voix[i + L]; e2 += voix[i + L] * voix[i + L]; }
      const c = s / Math.sqrt(e * e2 || 1);
      if (c > r) { r = c; lag = L; }
    }
    const place = p0 / n, score = r * Math.sqrt(e / fen) * (place > 0.25 && place < 0.85 ? 1 : 0.7);
    if (r > 0.8 && (!meilleur || score > meilleur.score)) meilleur = { p0, lag, score };
  }
  return { max, a, b, meilleur };
}
// (13:30) un meuble qu'il choisit lui-même : [[meuble: nom]] dans sa réponse
function meubleNomme(nom) { return meublesPrets.get(String(nom || '').trim()) || [...meublesPrets.values()].find(m => sansAccent(m.nom) === sansAccent(nom)) || null; }
const lecteurSysteme = synth ? Voix.creerLecteur(synth, synthTelephone ? EnonceTelephone : window.SpeechSynthesisUtterance, voixPour, vitesseVoix) : null;
// (04/11, Ahmed : « je dois toujours pouvoir sélectionner dans les réglages entre la voix du Mac et la voix locale du smartphone avec
// émotions ») réglage « Voix de Hakim » : téléphone (par défaut dans l'appli) ou neuronale · Chatterbox (au Mac)
const voixDuTelephone = () => !!synthTelephone && etat.reglages.voix === 'telephone';

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
  // (14:55) sa réponse soufflée parle pendant que la grande oreille confirme ta phrase (tu t'es tu)
  // (04/11) sa pensée dite dans ta pause, ton tour encore ouvert (direPenseeSiPossible)
  return !(c && ((c.capteur && c.capteur.enParole && !c.penseeEnPause) || (c.enAttente > 0 && !c.souffleParle)));
}

function creerLecteurNeuronal() {
  const unites = [];                  // phrases (ou morceaux de phrase) en attente : { langue, texte }
  const lots = [];                    // envoyés à la synthèse, dans l'ordre : { langue, texte, t0, pret, erreur, ctl }
  const sources = new Set();
  let prochainDebut = 0, generation = 0, element = null, veille = null;
  // Pause (lot C, point 26, 2026-10-19) : ce qui n'a pas encore été dit, la phrase en cours comprise, est
  // gardé ; la reprise repart de cette phrase. Le texte qui arrive pendant la pause s'y ajoute.
  let pause = null, elementTexte = null;
  // (03/11, Hakim pour papa : « je donne une première réponse courte, puis la suite ; si un trou se prépare entre les deux, une
  // petite hésitation pour meubler, côté cockpit, sans que je l'écrive ») sa voix a fini, la suite n'est pas prête et sa réponse
  // s'écrit encore : après un souffle, une hésitation toute prête (L.hesitation, fournie par la page). Une par trou, deux par
  // réponse au plus, jamais avant son premier mot ; elle n'est pas un morceau de sa réponse (ni sous-titre, ni reprise).
  // (13:11, papa via Hakim : « quand je réfléchis et qu'il y a un trou avant ma réponse » ; consciente quand il l'écrit,
  // subconsciente quand elle vient seule) avant son premier mot aussi : la page dit qu'une réponse se prépare
  // (attendreReponse) ; une seconde sans rien à dire, une hésitation.
  // (13:30-13:31, papa via Hakim : « ses propres meubles, choisis par son subconscient selon son état ; pendant TOUT le trou,
  // enchaîner s'il est long, s'arrêter net quand la réponse part ») les meubles s'enchaînent (une courte respiration entre
  // deux) jusqu'à ce que la suite soit prête ; elle coupe le meuble en cours (un fondu de 30 ms) et part aussitôt. Au plus
  // COUVRIR_MAX secondes d'affilée (un outil très long : le silence revient).
  // (14:31, Ahmed : « 3 s de blanc : je meuble entre 0,2 s et 2,8 s ») le premier meuble part 0,2 s après sa voix
  // (15:15, Ahmed : « quand il meuble pendant qu'il parle, la même transition de 0,2 s + 0,2 s, et la seconde de blanc ») entre sa voix
  // et un meuble, dans les deux sens : 1 s de silence (HESITER_APRES, SILENCE_REPRISE) ; sa voix ralentit sur sa fin avant un trou, et
  // repart au ralenti en accélérant après un meuble (adoucirFin, adoucirDebut : fournis par la page)
  // (04/11, Ahmed : « enlève les blancs, c'est chiant ; il n'est pas assez vif dans la parole que j'entends à cause des blancs ; juste
  // tester un truc ») les blancs au plus court : le premier meuble à 0,3 s (au lieu de 1 s), sa voix qui repart sans silence ni ralenti
  // (04/11, Ahmed : « enlève tous les blancs, même entre les mots qu'il dit ; annule tous les blancs ») au plus court partout
  const HESITER_AVANT = 0.15, ENTRE_MEUBLES = 0.05, COUVRIR_MAX = 90;
  // (15:24, Ahmed : « qu'il puisse ajuster dans son subconscient le temps des blancs et des transitions ») son rythme (L.rythme, donné
  // par la page depuis ses réglages : rythme_regler), sinon les valeurs d'Ahmed
  const R = (k, d) => { const v = L.rythme && Number(L.rythme[k]); return Number.isFinite(v) ? v : d; };
  // (14:20-14:31) les meubles se fondaient l'un dans l'autre (fondus croisés de 0,15 puis 0,4 s) : remplacé à 14:40
  // (14:40, Ahmed : « sans rien mélanger ») plus de fondus croisés : un meuble ralenti au bout (ralentirMeuble), le suivant qui repart
  // de cette vitesse, l'un APRÈS l'autre ; sa réponse, quand elle part, arrête le meuble en 30 ms et commence juste après
  // (14:58, Ahmed : « 1 s au lieu de 0,5 s ») ; (15:15) le meuble s'éteint en 0,2 s ; (15:24) réglables par lui
  let finDernierMeuble = 0;
  let trou = null, avant = null, aParle = false, couvre = 0, attendre = false, dejaParle = false;
  const vraiesSources = () => [...sources].some(s => !s._hesitation);   // une hésitation ne fait pas de lui un « déjà parti »
  // sa réponse s'écrit, se prépare, ou attend sa voix (la fin du texte n'est pas la fin de ce qu'il a à dire)
  const enReponse = () => !L.fluxFini || attendre || lots.length > 0 || unites.length > 0;
  // coût fixe (s), coût par seconde de voix, caractères par seconde de voix : prudents au départ (la
  // machine swappe souvent), puis appris et gardés d'une session à l'autre dans ce navigateur
  const est = { fixe: 0.85, parSec: 0.75, cps: 15 };
  try { Object.assign(est, JSON.parse(localStorage.getItem('jarvis.voix.vitesses') || '{}')); } catch (_) {}
  const garder = () => { try { localStorage.setItem('jarvis.voix.vitesses', JSON.stringify(est)); } catch (_) {} };
  const fluide = () => actx && actx.state === 'running';
  const avance = () => (fluide() ? Math.max(0, prochainDebut - actx.currentTime) : 0);
  const prevoir = (n) => est.fixe + est.parSec * (n / est.cps);   // temps de synthèse prévu pour n caractères
  const L = {
    surFin: null, surSegment: null, fluxFini: true, hesitation: null, peutHesiter: null, rythme: null,
    appliquerSon() { if (element) element.muted = !!etat.sonCoupe; },
    dire(phrase) {
      if (typeof noterSaVoix === 'function') noterSaVoix(phrase);     // (04/11, 12:25) pour reconnaître son écho
      if (pause) { pause.textes.push(...Voix.prononcable(phrase)); pause.fluxFini = false; return; }
      if (L.fluxFini && !attendre) { aParle = false; dejaParle = false; }   // (03/11) une nouvelle réponse
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
    attendreReponse() {
      clearTimeout(avant);
      attendre = true; aParle = false; dejaParle = false; couvre = 0;
      avant = setTimeout(() => { avant = null; if (!vraiesSources() && !element && glisser()) couvre = fluide() ? actx.currentTime : 1; }, HESITER_AVANT * 1000);
    },
    // (15:10) une parole dont la voix est déjà fabriquée (sa réponse soufflée) : à sa place, sans attendre la synthèse
    direAudio(texte, buf) {
      if (!buf || !buf.duration) { L.dire(texte); return; }
      if (typeof noterSaVoix === 'function') noterSaVoix(texte);
      if (pause) { pause.textes.push({ langue: 'fr', texte }); pause.fluxFini = false; return; }
      if (L.fluxFini && !attendre) { aParle = false; dejaParle = false; }
      L.fluxFini = false;
      unites.push({ audio: { texte, pret: buf } });
      pomper();
    },
    // (13:30) un meuble choisi par lui (conscient, [[meuble: nom]]) : à sa place, entre ce qui précède et la suite
    direMeuble(h) {
      if (!h || !h.pret) return;
      if (pause) { pause.textes.push({ meuble: h }); return; }
      unites.push({ meuble: h });
      pomper();
    },
    // (31/10, 01:27, Ahmed via Hakim) un de ses sons, à sa place : après ce qui précède, avant la suite, joué en entier
    direSon(extrait) {
      if (!extrait || !/^e\d{1,6}$/.test(String(extrait.id))) return;
      if (pause) { pause.textes.push({ son: extrait }); return; }
      unites.push({ son: extrait });
      pomper();
    },
    // ce qui n'a pas encore été dit, la phrase en cours comprise (reprise du début), sans rien arrêter
    restant() {
      if (pause) return pause.textes.slice();
      const maintenant = fluide() ? actx.currentTime : 0;
      const restants = [];
      if (element && elementTexte) restants.push({ langue: 'fr', texte: elementTexte });
      for (const src of [...sources].sort((a, b) => a._debut - b._debut))     // en cours (repris du début) et à venir
        if (src._texte && src._fin > maintenant + 0.05) restants.push({ langue: src._langue, texte: src._texte });
      for (const x of lots) restants.push(x.son ? { son: x.son } : (x.meuble ? { meuble: x.meuble } : { langue: x.langue, texte: x.texte }));
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
      clearTimeout(trou); trou = null; clearTimeout(avant); avant = null; aParle = false; couvre = 0; attendre = false; dejaParle = false; finDernierMeuble = 0;
    },
    get actif() { return unites.length > 0 || lots.length > 0 || sources.size > 0 || !!element; },
    get joue() { return sources.size > 0 || !!element; },
    // (16:00) sa vraie voix (une réponse dite, à dire, ou en cours) : ses meubles n'en sont pas
    get parle() { return lots.length > 0 || vraiesSources() || !!element || unites.some(u => !u.meuble); },
    // (04/11) retirer des paroles déjà fabriquées qui n'ont pas encore commencé (ses bouts devenus inutiles : sa vraie réponse arrive)
    retirerAudio(textes) {
      const garde = (t) => !textes.includes(t);
      for (let i = unites.length - 1; i >= 0; i--) if (unites[i].audio && !garde(unites[i].audio.texte)) unites.splice(i, 1);
      for (let i = lots.length - 1; i >= 0; i--) if (lots[i].texte && !garde(lots[i].texte) && lots[i].pret && lots[i].pret.getChannelData) lots.splice(i, 1);
      if (fluide()) {
        for (const src of [...sources]) if (src._texte && !garde(src._texte) && src._debut > actx.currentTime + 0.02) { try { src.stop(); } catch (_) {} sources.delete(src); }
        prochainDebut = Math.max(actx.currentTime, ...[...sources].map(x => x._fin || 0));
      }
      pomper();
    },
  };

  // Coupe un texte trop long pour le temps disponible : à une ponctuation, ou juste avant une conjonction
  // (là où l'on reprend son souffle), jamais au milieu d'un groupe de mots. Les mots ne changent pas.
  // (03/11, 14:50, Ahmed : « chaque chunk coupé à une virgule ou à une phrase complète, jamais au milieu d'une phrase : « je suis en
  // train de manger, mais pas de boisson » = « je suis en train de manger » + « mais pas de boisson » ») plus de coupure avant une
  // conjonction sans virgule : seulement à la ponctuation ; sans virgule, le morceau reste entier
  const COUPURES = /[,;:]\s+/g;
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
    if (unites[0] && unites[0].son) return { son: unites.shift().son, texte: '' };   // (01:27) un son : seul, à sa place
    if (unites[0] && unites[0].audio) { const a = unites.shift().audio; return { pret: a.pret, texte: a.texte, langue: 'fr' }; }   // (15:10) déjà fabriquée
    if (unites[0] && unites[0].meuble) {                                // (13:30) un meuble choisi : déjà prêt, à sa place
      const h = unites.shift().meuble;
      return { pret: h.pret, texte: h.texte || '', meuble: h, hesitation: true, volume: h.volume, dureeMax: h.dureeMax, brut: h.brut };
    }
    const premier = !vraiesSources() && !lots.length;
    // (28/10) un début de réponse dont le cockpit a la voix toute prête (debuts.js) part seul : le premier son sans attendre
    const debut = premier ? Voix.debutDe(unites[0].texte) : null;
    if (debut && unites[0].langue === 'fr' && debutsPrets.has(cleDebut(debut))) {
      const reste = unites[0].texte.slice(debut.length).trim();
      const langue = unites[0].langue;
      unites.splice(0, 1, { langue, texte: reste });
      return { langue, texte: debut };
    }
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
    if (x.son) {                                                    // (01:27) l'extrait, découpé par le cockpit
      fetch(`/api/sons/joue/${x.son.id}`, { signal: x.ctl.signal, headers: { 'X-Jeton': jeton() }, cache: 'no-store' })
        .then(r => (r.ok ? r.arrayBuffer() : Promise.reject(new Error(`son ${r.status}`))))
        .then(ab => actx.decodeAudioData(ab))
        .then(buf => { if (g !== generation) return; x.pret = buf; journalVoix('son', { retour: 'ok_en_ligne' }); pomper(); })
        .catch(e => {
          if (g !== generation || e.name === 'AbortError') return;
          // (31/10, 01:50, l'essai de papa au téléphone : « aucun son ») le Mac n'a pas encore ce morceau : sur le téléphone, l'appli
          // le joue elle-même, à la même place (sa voix se tait le temps de l'extrait)
          if (window.HakimApp && window.HakimApp.sonJouer && x.son.source !== 'atelier') {
            x.pret = { natif: true, duration: Math.max(0.5, (Number(x.son.fin_ms) - Number(x.son.debut_ms)) / 1000) };
            journalVoix('son', { retour: 'natif_en_ligne' });
          } else { x.erreur = e; journalVoix('son', { retour: 'absent_en_ligne' }); }
          pomper();
        });
      return;
    }
    fetch('/api/voix/dire', { method: 'POST', signal: x.ctl.signal,
      headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() },
      body: JSON.stringify({ texte: x.texte, langue: x.langue, emotion: etat.interieur && !etat.reglages.voixNeutre ? expressivitePhrase(etat.interieur.expressivite, x.texte) : null, tempo: tempoVoix(),
        plan: !x.premier }) })                                        // (03/11) son subconscient prépare l'intonation des bouts suivants
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
    if (x.pret && x.pret.natif) {                                  // (01:50) joué par l'appli, à sa place ; la suite attend sa fin
      const s0 = x.son, dans = Math.max(0, (t - actx.currentTime) * 1000), fin = dans + x.pret.duration * 1000 + 150;
      // une place dans « sources » : sa voix reste « active » le temps de l'extrait (le micro ne se rouvre pas, la fin n'est pas dite)
      const place = { _debut: t, _fin: t + x.pret.duration, minuteurs: [], stop() { this.minuteurs.forEach(clearTimeout); } };
      place.minuteurs.push(setTimeout(() => { try { window.HakimApp.sonJouer(String(s0.source), String(s0.ref), Number(s0.debut_ms), Number(s0.fin_ms)); } catch (_) {} }, dans));
      place.minuteurs.push(setTimeout(() => { sources.delete(place); pomper(); }, fin));
      sources.add(place);
      prochainDebut = t + x.pret.duration + 0.15;
      aParle = true;
      return;
    }
    // (04/11, Ahmed : « enlève tous les blancs, même entre les mots qu'il dit ») le silence que la synthèse laisse au début et à la fin
    // de chaque bout de sa voix est rogné : les bouts s'enchaînent sans trou
    if (!x.hesitation && !x.son && x.pret && x.pret.getChannelData && L.rogner) x.pret = L.rogner(x.pret);
    // (15:15) sa voix après un meuble repart au ralenti en accélérant ; sa dernière parole avant un trou ralentit sur sa fin
    if (!x.hesitation && !x.son && x.pret && x.pret.getChannelData) {
      if (x.apresMeuble && L.adoucirDebut) x.pret = L.adoucirDebut(x.pret);
      if (!unites.length && !lots.length && !L.fluxFini && L.adoucirFin) x.pret = L.adoucirFin(x.pret);
    }
    const vitesse = x.son || x.brut ? 1 : vitesseVoix();             // (01:27) un son garde sa vitesse ; (13:30) un souffle aussi
    const src = actx.createBufferSource();
    src.buffer = x.pret;
    src.playbackRate.value = vitesse;
    // (30/10, 20:09, Ahmed : « plus forte quand il est excité, douce quand il est calme ») la force de sa voix suit son éveil
    const force = actx.createGain();
    force.gain.value = x.son ? 0.6 : forceDeLaVoix() * (Number.isFinite(x.volume) ? x.volume : 1);   // (13:30) le volume du meuble
    src.connect(force); force.connect(analyseurVoix);
    src.start(t);
    const joue = Math.min(x.pret.duration / vitesse, x.dureeMax > 0 ? x.dureeMax : Infinity);   // (13:30) sa durée au plus
    if (joue < x.pret.duration / vitesse) { try { src.stop(t + joue); } catch (_) {} }
    // (1.66, 04/11, 19:35, Ahmed : « … soit depuis la voie de ses haut-parleurs ») l'appli sait d'avance jusqu'à quand sa voix (ou son
    // son) joue : son oreille par l'air, le micro du téléphone, jette tout ce qu'il capte pendant ce temps (jamais sa propre voix)
    try { if (window.HakimApp && window.HakimApp.saVoixPendant) window.HakimApp.saVoixPendant(Math.max(0, (t + joue - actx.currentTime) * 1000)); } catch (_) {}
    prochainDebut = t + joue + 0.01;                                // (04/11) plus de blanc entre deux bouts
    src._texte = x.hesitation ? '' : x.texte; src._hesitation = !!x.hesitation; src._auto = !!x.auto; src._gain = force;
    src._langue = x.langue; src._debut = t; src._fin = t + joue;
    sources.add(src);
    if (!x.auto) { aParle = true; couvre = 0; }                      // un meuble choisi par lui compte comme sa parole
    if (!x.hesitation) { dejaParle = true; attendre = false; }
    const g = generation;
    const duree = joue * 1000;                                 // (30/10) sa durée : où il en est quand on le coupe
    if (!x.son && !x.hesitation) setTimeout(() => { if (g === generation && L.surSegment) L.surSegment(x.texte, duree); }, Math.max(0, (t - actx.currentTime) * 1000));
    src.onended = () => { sources.delete(src); if (src._auto && fluide()) finDernierMeuble = actx.currentTime; if (g === generation) pomper(); };
  }

  function pomper() {
    // 1. le processus voix ne reste jamais inactif quand du texte attend (une demande à la fois : on
    //    taille le lot en connaissant l'avance exacte du moment)
    if (unites.length && !lots.some(x => !x.pret && !x.erreur)) {
      const premier = !vraiesSources() && !lots.length;             // (03/11) le premier bout part sans attendre l'intonation préparée
      const x = prochainLot();
      x.premier = premier;
      lots.push(x);
      if (!x.pret) lancer(x);
    }
    // 2. programmer, dans l'ordre, ce qui est prêt
    while (lots.length && (lots[0].pret || lots[0].erreur) && !element) {
      const x = lots[0];
      if (x.son && x.erreur) { lots.shift(); continue; }           // (01:27) le son manque : sa voix continue, sans lui
      if (x.erreur) {
        lots.shift();
        humeur(`voix neuronale : ${x.erreur.message || x.erreur} — voix du Mac en secours`);
        if (lecteurSysteme) {                       // à la suite de ce qui est programmé, pas par-dessus
          const dans = fluide() ? Math.max(0, prochainDebut - actx.currentTime) : 0;
          const g = generation;
          setTimeout(() => { if (g === generation) lecteurSysteme.dire(x.texte); }, dans * 1000);
          if (fluide()) prochainDebut = Math.max(prochainDebut, actx.currentTime) + x.texte.length / est.cps / vitesseVoix() + 0.3;
        } else if (L.surPanne) L.surPanne(x.erreur.message || x.erreur);   // (30/10) sans secours, ce morceau ne sera pas dit
        continue;
      }
      if (x.pret instanceof Blob) { lots.shift(); jouerElement(x); break; }   // contexte audio pas encore autorisé
      if (!sources.size && avance() === 0 && !jarvisPeutParler()) break;   // on attend la fin de ton tour
      // (13:31) sa réponse part : elle prend la place du meuble que son subconscient jouait ; (14:20) en fondu (FONDU_REPONSE),
      // sans attendre sa fin ; un meuble pas encore commencé ne part pas
      if (sources.size && [...sources].every(s2 => s2._auto) && fluide()) {
        const now = actx.currentTime;
        for (const s2 of sources) {
          if (s2._debut > now) { try { s2.stop(now); } catch (_) {} s2._fin = now; continue; }
          try {                                                  // de là où il en est, vers 0 en 0,2 s
            const gg = s2._gain && s2._gain.gain;
            if (gg && gg.cancelAndHoldAtTime) gg.cancelAndHoldAtTime(now);
            else if (gg && gg.cancelScheduledValues) { gg.cancelScheduledValues(now); gg.setValueAtTime(gg.value, now); }
            if (gg && gg.linearRampToValueAtTime) gg.linearRampToValueAtTime(0, now + R('fondu_reponse', 0.08));
          } catch (_) {}
          try { s2.stop(now + R('fondu_reponse', 0.08)); } catch (_) {}
          s2._fin = Math.min(s2._fin, now + R('fondu_reponse', 0.08));
        }
        prochainDebut = now + R('fondu_reponse', 0.08) + R('blanc_avant_reprise', 0);   // (15:15) le meuble s'éteint, 1 s de silence, puis sa voix
        x.apresMeuble = true;
      }
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
      // (15:15) un meuble vient de finir : 1 s de silence avant sa voix, et sa voix repart au ralenti
      if (!x.hesitation && finDernierMeuble && fluide() && actx.currentTime - finDernierMeuble < R('blanc_avant_reprise', 0) + 0.5) {
        t = Math.max(t, finDernierMeuble + R('blanc_avant_reprise', 0)); x.apresMeuble = true;
      }
      lots.shift();
      programmer(x, t);
    }
    // 3. (03/11) un trou se prépare : sa voix a fini (ou un meuble), la suite n'est pas là, sa réponse s'écrit encore
    if (!trou && (aParle || couvre) && enReponse() && !pause && !sources.size && !element && L.hesitation)
      trou = setTimeout(hesiter, (couvre ? ENTRE_MEUBLES : R('blanc_avant_meuble', 0.1)) * 1000);
    if (L.actif && !veille) veille = setInterval(pomper, 250);
    if (!L.actif) { clearInterval(veille); veille = null; if (L.surFin) L.surFin(); }
  }

  function hesiter() {
    trou = null;
    if (!(aParle || couvre) || !enReponse() || element || [...sources].some(s2 => !s2._hesitation)) return;
    if (couvre && fluide() && actx.currentTime - couvre > COUVRIR_MAX) return;   // un trou immense : le silence revient
    if (glisser()) { if (!couvre) couvre = fluide() ? actx.currentTime : 1; aParle = false; }
  }

  // une hésitation toute prête, maintenant, si rien n'est sur le point d'être dit ; rend vrai si elle part
  function glisser() {
    if (pause || element || !fluide() || !L.hesitation) return false;
    if ([...sources].some(s2 => !s2._hesitation)) return false;        // sa vraie voix joue : pas de meuble par-dessus
    if (L.peutHesiter && !L.peutHesiter()) return false;
    const y = lots[0];
    if (y && (y.pret || y.erreur)) return false;                                  // la suite est là : pomper la programme
    // (13:31) presque prête ou pas : le meuble part quand même, la suite le coupera net en arrivant
    const h = L.hesitation({ avant: !dejaParle, suite: [...sources].some(s2 => s2._auto) });   // (14:40) à la suite d'un meuble
    if (!h || !h.pret || !h.pret.duration) return false;
    journalVoix('hesitation', { texte: h.texte, ...(!dejaParle ? { avant: true } : {}) });
    // (14:20) il commence dans la fin du meuble qui joue encore : ils se fondent l'un dans l'autre (« mmmheuuu »)
    const finMeubles = Math.max(0, ...[...sources].map(s2 => s2._fin));
    // (14:40) après le précédent, sans le chevaucher ; (14:46, Ahmed : « entre chaque meuble, 0,5 s de silence : ça aide la
    // transition naturelle, sinon on dirait que les deux se chevauchent »)
    const t = Math.max(actx.currentTime + 0.03, finMeubles > 0 ? finMeubles + R('blanc_entre_meubles', 0.05) : 0);
    programmer({ pret: h.pret, texte: h.texte, langue: 'fr', hesitation: true, auto: true, volume: h.volume, dureeMax: h.dureeMax, brut: h.brut }, t);
    // le suivant se prépare juste avant la fin de celui-ci, pour s'y fondre
    clearTimeout(trou);
    trou = setTimeout(hesiter, Math.max(0, (prochainDebut - 0.05 - 0.15 - actx.currentTime) * 1000));
    return true;
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
    // (1.66) ce lecteur-ci aussi : l'appli sait combien de temps sa voix joue (son oreille par l'air jette ce que capte le micro)
    const el = element;
    el.onplaying = () => { try { if (window.HakimApp && window.HakimApp.saVoixPendant) window.HakimApp.saVoixPendant(Number.isFinite(el.duration) ? el.duration * 1000 / (el.playbackRate || 1) : 30000); } catch (_) {} };
    // (2026-10-21) un lecteur bloqué par le navigateur (pas de geste récent, onglet en arrière-plan) : avant, le
    // morceau était sauté et les sous-titres défilaient en silence ; maintenant il attend un toucher et le dit
    element.play().catch((e) => {
      if (g !== generation) return;
      if (e && e.name === 'NotAllowedError') { sonBloque('lecteur'); return; }
      if (L.surPanne) L.surPanne('lecture impossible');           // (30/10) ce morceau sauté : une panne de la voix
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
// (30/10, 20:09) la force de sa voix, phrase par phrase, de son éveil et de son émotion : 0,8 (calme, las) à 1,15 (excité, en
// colère, effrayé) ; bornée pour ne jamais saturer ni crier
const VOIX_FORTES = ['élan', 'enthousiasme', 'colère', 'surprise', 'peur', 'agacement', 'émerveillement'];
const VOIX_DOUCES = ['tristesse', 'lassitude', 'fatigue', 'somnolence', 'calme', 'apaisement', 'tendresse'];
function forceDeLaVoix() {
  const i = etat.interieur || {};
  if (etat.reglages.voixNeutre || !Number.isFinite(i.arousal)) return 1;
  let g = 0.95 + 0.6 * (i.arousal - 0.45);
  if (VOIX_FORTES.includes(i.voix_emotion)) g += 0.08;
  if (VOIX_DOUCES.includes(i.voix_emotion)) g -= 0.08;
  return Math.round(Math.max(0.8, Math.min(1.15, g)) * 100) / 100;
}
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
        // (30/10) page cachée, le son suspendu pendant qu'il parle : l'appli a arrêté sa voix (elle repart avec le son)
        if (actx.state !== 'running' && document.visibilityState === 'hidden' && lecteurNeuronal.joue) coupureProvisoire('appli', 'page cachée : le son a été suspendu');
        else if (actx.state === 'running' && coupureEnCours && coupureEnCours.cause === 'appli') reprisDeParole();
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
  // (1.61, 04/11) sa voix du téléphone joue hors de la page : son niveau vient de l'appli (sans lui, son écho passait pour ta voix)
  if (typeof voixDuTelephone === 'function' && voixDuTelephone() && lecteurSysteme && lecteurSysteme.actif && window.HakimApp && window.HakimApp.voixTelephoneNiveau) {
    try { return Math.max(0, Number(window.HakimApp.voixTelephoneNiveau()) || 0); } catch (_) { return 0; }
  }
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
  get impl() { if (voixDuTelephone() && lecteurSysteme) return lecteurSysteme; return (etat.reglages.voix === 'neuronale' && etat.ttsLocal) || !lecteurSysteme ? lecteurNeuronal : lecteurSysteme; },
  dire(p) { this.impl.dire(p); },
  finFlux() { if (this.impl.finFlux) this.impl.finFlux(); },     // le texte est complet : vider la file
  arreter() { lecteurNeuronal.arreter(); if (lecteurSysteme) lecteurSysteme.arreter(); },
  get actif() { return lecteurNeuronal.actif || !!(lecteurSysteme && lecteurSysteme.actif); },
  // la voix du Mac ne sait pas reprendre : en pause, elle s'arrête
  pause() { if (this.impl === lecteurNeuronal) return lecteurNeuronal.pause(); this.arreter(); return false; },
  reprendre() { return lecteurNeuronal.reprendre(); },
  get enPause() { return lecteurNeuronal.enPause; },
};
// (04/11, Ahmed : « il meuble parfaitement bien les blancs, mais il ne doit jamais pouvoir couper un blanc meublé au milieu ») ce que
// sa voix du téléphone dit à l'instant : un meuble (« Hum, », « Voyons voir, ») va jusqu'au bout ; ce qui voulait le couper attend sa fin
const meublesDits = new Set();
const cleMeuble = (t) => String(t || '').toLowerCase().replace(/[^\p{L}\p{N}]+/gu, '');
function noterMeubleDit(t) { meublesDits.add(cleMeuble(t)); if (meublesDits.size > 40) meublesDits.delete(meublesDits.values().next().value); }
let segmentTelephone = null;
function noterSegmentTelephone(t) { segmentTelephone = { meuble: meublesDits.has(cleMeuble(t)) }; }
const meubleEnCours = () => !!(segmentTelephone && segmentTelephone.meuble && lecteurSysteme && lecteurSysteme.actif);
const finLecture = () => {
  segmentTelephone = null;
  // (04/11, 11:50) la suite que son ribosome a choisie ; (12:15, Ahmed : « des fenêtres d'ouverture d'oreille à chaque fois qu'il finit un
  // chunk ») après chaque morceau, son oreille s'ouvre le délai de la Conversation : si tu parles, sa voix attend
  if (typeof direRibosome === 'function') setTimeout(direRibosome, typeof patienceConversation === 'function' ? patienceConversation() : 0);
  if (typeof boutTelephoneSuivant === 'function') setTimeout(boutTelephoneSuivant, 0);   // (04/11) le bout qui attendait sa voix
  if (lecteur.actif) return;
  if (etat.conversation) etat.conversation.penseeEnPause = false;     // (04/11) sa pensée dite : ton tour reprend la main
  for (const x of etat.messages.slice(-6)) if (x.auRythme && !x.enCours) x.auRythme = false;   // (16:45) sa voix a fini : tout s'écrit
  if (!etat.flux) etat.reponseVoix = null;                              // (13:30) sa réponse est dite : plus de meubles
  // (30/10) sa voix a tout dit (ni en pause, ni une réponse qui arrive encore pour ce message) : une fin, ou la panne qui l'a trouée
  if (!lecteur.enPause && etat.lectureDe != null && !(etat.flux && String(etat.fluxId) === String(etat.lectureDe)))
    finirParole('fin', '', { id: etat.lectureDe, mode: 'oral' });
  etat.lectureDe = null; etat.finVoixA = Date.now(); rendre(); humeur();
};
lecteurNeuronal.surFin = finLecture;
// (03/11) un trou dans sa réponse : un de ses meubles, choisi par son subconscient, seulement pendant une réponse dite à voix
// haute (pas une réécoute) et quand papa ne parle pas
let vitesseFinMeuble = 0.35;
lecteurNeuronal.hesitation = (o) => {
  const h = choisirMeuble(o);
  if (!h || !h.pret || !h.voix) return h;
  // (14:20) un peu plus long que sa voix (0,6 à 1,5 s de plus), jamais plus que sa durée au plus : il s'étale sur la pause ;
  // (14:40) au ralenti, et il repart de la vitesse où le meuble d'avant s'est arrêté (après sa voix : un départ lent, 0,35)
  // (15:40, Ahmed : « les meubles sont trop longs au début ») moins étirés (0,3 à 0,8 s de plus) et un départ moins lent (0,55)
  const voulu = h.pret.duration + 0.3 + Math.random() * 0.5, cible = h.dureeMax > 0 ? Math.min(h.dureeMax, voulu) : voulu;
  try {
    const r = ralentirMeuble(h.pret, cible, o && o.suite ? vitesseFinMeuble : rythmeVoix('ralenti_depart', 1));
    vitesseFinMeuble = r.vFin;
    return { ...h, pret: r.tampon, dureeMax: 0 };
  } catch (_) { return h; }
};
// (04/11, 01:46-01:50, Ahmed : « annule tous les blancs » ; « j'ai l'impression que c'est ça qui le ralentit » ; via Hakim : « les blancs
// glissés dans mes réponses, meubles et blancs entre bouts, me rajoutent du temps ») ses meubles automatiques : éteints par défaut
// (SENS : meubles_auto) ; ceux qu'il choisit lui-même ([[meuble: nom]]) restent
lecteurNeuronal.peutHesiter = () => typeof reglagesCorps !== 'undefined' && reglagesCorps.meubles_auto === true && etat.reponseVoix != null && jarvisPeutParler();
// (15:15) la même transition entre sa voix et ses meubles : sa voix repart au ralenti (de 0,35 à la normale sur sa première lettre),
// et sa dernière parole avant un trou ralentit sur sa fin (+0,3 s)
const rythmeVoix = (k, d) => { const v = lecteurNeuronal.rythme && Number(lecteurNeuronal.rythme[k]); return Number.isFinite(v) ? v : d; };   // (15:24)
// (04/11, Ahmed : « annule tous les blancs ») le silence de début et de fin d'un bout de sa voix, rogné (15 ms de marge, jamais sous 50 ms)
function rognerSilences(buf) {
  if (!buf || !buf.getChannelData || !actx) return buf;
  const d = buf.getChannelData(0), n = d.length, seuil = 0.008, marge = Math.round(buf.sampleRate * 0.015);
  let a = 0; while (a < n && Math.abs(d[a]) < seuil) a++;
  let b = n - 1; while (b > a && Math.abs(d[b]) < seuil) b--;
  a = Math.max(0, a - marge); b = Math.min(n - 1, b + marge);
  if ((a === 0 && b === n - 1) || b - a < buf.sampleRate * 0.05) return buf;
  const out = actx.createBuffer(buf.numberOfChannels, b - a + 1, buf.sampleRate);
  for (let c = 0; c < buf.numberOfChannels; c++) out.copyToChannel(buf.getChannelData(c).subarray(a, b + 1), c);
  return out;
}
lecteurNeuronal.rogner = (buf) => { try { return rognerSilences(buf); } catch (_) { return buf; } };
lecteurNeuronal.adoucirDebut = (buf) => { try { return ralentirMeuble(buf, 0, rythmeVoix('ralenti_depart', 1)).tampon; } catch (_) { return buf; } };
lecteurNeuronal.adoucirFin = (buf) => { const f = rythmeVoix('ralenti_fin', 0); if (!(f > 0)) return buf; try { return ralentirMeuble(buf, buf.duration + f, 1).tampon; } catch (_) { return buf; } };
if (lecteurSysteme) lecteurSysteme.surFin = finLecture;

/* ---------- les orbes : la petite (en-tête) et la grande (scène, quand il parle ou écoute) ---------- */
const orbeTete = Orbe.creer($('orbe'), { reduit: REDUCED });
const orbeScene = Orbe.creer($('orbeScene'), { reduit: REDUCED });
// (03/11) son orbe sur la caméra en grand, la même qui bat avec sa voix ; et ses deux boutons
const orbeVision = $('orbeVision') ? Orbe.creer($('orbeVision'), { reduit: REDUCED }) : null;
if ($('visionSortir')) $('visionSortir').addEventListener('click', () => { arreterCamera(); humeur(); });
if ($('visionEcran')) $('visionEcran').addEventListener('click', () => { if ($('ecran')) $('ecran').click(); });
function niveauCourant() {
  // (30/10, 22:44, Ahmed : « quand l'orbe est de sa couleur à lui, je la vois quand même bouger quand je parle ») la parole est
  // à lui (il prépare, il parle, il a coupé ton micro) : seule sa voix la fait bouger
  const qui = quiALaParole();
  if (qui === 'hakim' || qui === 'coupe') return niveauVoix();
  if (etat.conversation && etat.conversation.capteur && etat.conversation.capteur.enParole)
    return { niveau: etat.niveauMicro || 0, bandes: [etat.niveauMicro || 0, (etat.niveauMicro || 0) * 0.8, (etat.niveauMicro || 0) * 0.6] };
  if (etat.micro) return { niveau: etat.niveauMicro || 0, bandes: [etat.niveauMicro || 0, (etat.niveauMicro || 0) * 0.8, (etat.niveauMicro || 0) * 0.6] };
  return niveauVoix();
}
orbeTete.source(niveauCourant);
orbeScene.source(niveauCourant);
if (orbeVision) orbeVision.source(niveauCourant);
const pulser = (x) => { orbeTete.pulser(x); orbeScene.pulser(x); if (orbeVision) orbeVision.pulser(x); };
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
  // (2026-10-23) un envoi raté (Mac injoignable) remet le lot dans la file : avant, il était perdu, et une coupure de
  // 9 min ne laissait aucune trace
  if (lot.length) fetch('/api/voix/journal', { method: 'POST', keepalive: true,
    headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() }, body: JSON.stringify(lot) })
    .then((r) => { if (!r.ok) throw new Error(`journal ${r.status}`); })
    .catch(() => {
      journalVoixFile.unshift(...lot);
      if (journalVoixFile.length > 100) journalVoixFile.splice(0, journalVoixFile.length - 100);
      try { localStorage.setItem('jarvis.journalVoix', JSON.stringify(journalVoixFile)); } catch (_) {}
    });
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
// (03/11, 14:47, Ahmed : « pour les widgets et la bulle, et même sur le verrou : une zone courte et petite sous l'orbe et les boutons,
// avec ce qu'il entend et ce qu'il dit, quand c'est activé dans SENS ») ses mots et les tiens vers l'appli (Paroles.java), chacun
// seulement si SENS l'affiche ; au plus 4 fois par seconde, et seulement ce qui change
// (03/11, 16:08-16:20, Ahmed : « il y a un problème entre le message envoyé, la pensée et le mot glissé » ; « pour Télépathie rien du
// tout ; même en Conversation, pas mes mots par défaut » ; « dans Conversation, enlève le mot glissé » ; « on laisse le mode
// Conversation avec sa pensée du cerveau écrite, en parallèle à Chatterbox qui parle aussi vite que le message arrive ») ce qui
// s'écrit selon le mode : à l'écrit, vos messages ; en Conversation, sa pensée (son cerveau) puis sa réponse, écrites en même temps
// que sa voix les dit, et tes mots seulement si SENS le demande (mots_conversation) ; en Télépathie, rien
const enTelepathie = () => !!etat.conversation && typeof reglagesCorps !== 'undefined' && reglagesCorps.afficher_papa === false && reglagesCorps.afficher_hakim === false;
const motsEnConversation = () => typeof reglagesCorps !== 'undefined' && reglagesCorps.mots_conversation === true;
const motsPapaCaches = () => !!etat.conversation && !motsEnConversation();
// (04/11, Ahmed : « en Conversation ou en Télépathie, je veux voir seulement la pensée écrite, pas sa réponse écrite ; la réponse écrite,
// on la garde seulement hors de ces modes ») dans les deux modes : sa pensée s'écrit (🧠), sa réponse se dit sans s'écrire
// (04/11, 10:20, Ahmed : « je ne vois plus quand il m'envoie des documents ; qu'il soit aussi possible de réafficher ses paroles dans le
// mode normal et le mode Conversation ») « Ses paroles » : d'un geste (gardé), ses réponses cachées se réaffichent, dans les deux modes ;
// Télépathie reste sans texte. Ses fichiers se montrent toujours, même quand sa réponse est cachée (sans son texte).
// (04/11, 15:30, Ahmed : « sa parole complète, je ne dois pas la voir ») avec l'épissage, seulement ses deux fils (sa pensée interne, sa
// parole épissée) ; ses fichiers se montrent toujours
// (17:05, Ahmed : « le bouton pour muter ses paroles ne fonctionne plus ») avec l'épissage, son propre état (caché par défaut), basculé par le bouton
const parolesVisibles = () => !enTelepathie() && ((typeof voixEpissee === 'function' && voixEpissee()) ? !!etat.reglages.sesParolesEpissage : !!etat.reglages.sesParoles);
const reponseCachee = () => !!etat.conversation && !parolesVisibles();
// (04/11, 12:05) en Conversation avec l'épissage (Sens, oui par défaut), sa voix suit son ribosome, pas sa réponse en entier
const voixEpissee = () => !!etat.conversation && typeof reglagesCorps !== 'undefined' && !!reglagesCorps && reglagesCorps.epissage !== false;
const PIECE_ID = /^\d{8}-\d{6}-[0-9a-f]{6}$/;
const aDesPieces = (m) => !!m && m.qui === 'j' && (m.pieces || []).some(x => x && PIECE_ID.test(String(x.id)));
// caché à l'écran : « dans ta tête » (tes mots, ou les siens sans « Ses paroles »), ou sa réponse pendant la conversation
// (04/11, 15:45, Ahmed : « je ne vois pas ses signalements ; il faut que ça fasse la même chose que quand il m'envoie un fichier : ça doit
// s'afficher dans la conv, quel que soit le mode ») ce qui attend ton geste s'affiche toujours, en Conversation comme en Télépathie
function messageMasque(m) {
  if (m.qui === 'j' && ['signalement', 'anticorps', 'mission', 'ecriture', 'regle', 'carnet', 'retractation', 'identite', 'sortie', 'membre', 'promotion'].includes(m.spontane)) return false;
  if (m.cache && !(m.qui === 'j' && parolesVisibles())) return true;
  return reponseCachee() && m.qui === 'j' && (Number(m.ts) || Number(m.id) || Date.now()) >= (etat.conversation.debut || 0);
}
const piecesSeules = (m) => ({ id: m.id, qui: 'j', texte: '', pieces: m.pieces, ts: m.ts });
const parolesEnvoyees = { papa: '', hakim: '' }, parolesEnAttente = {};
let parolesMinuteur = null;
/* (04/11, Hakim pour papa : « un chiffre mesuré entre le moment où j'écris un mot et celui où il apparaît à l'écran de ton téléphone,
   et entre le moment où je le dis et celui où tu l'entends dans tes écouteurs Bluetooth » ; Ahmed : « ajoute tout ») ses SORTIES
   mesurées, de l'instant où le Mac les envoie (ts, à son horloge) jusqu'à l'écran de la page, la bulle, le widget et tes écouteurs.
   L'horloge du Mac est calée ici : le plus court de trois allers-retours, refait toutes les 5 min quand une mesure en a besoin. */
const horlogeMac = { decalage: 0, rtt: Infinity, t: 0, enCours: false };
async function calerHorlogeMac() {
  if (horlogeMac.enCours || (Date.now() - horlogeMac.t < 300000 && horlogeMac.rtt < 400) || typeof fetch !== 'function') return;
  horlogeMac.enCours = true;
  try {
    let meilleur = null;
    for (let k = 0; k < 3; k++) {
      const t0 = Date.now(), r = await (await fetch('/api/heure', { cache: 'no-store', headers: { 'X-Jeton': jeton() } })).json(), t1 = Date.now();
      if (r && Number(r.t) > 0 && (!meilleur || t1 - t0 < meilleur.rtt)) meilleur = { rtt: t1 - t0, decalage: Number(r.t) - (t0 + t1) / 2 };
    }
    if (meilleur) Object.assign(horlogeMac, meilleur, { t: Date.now() });
  } catch (_) {} finally { horlogeMac.enCours = false; }
}
// le délai depuis l'envoi du Mac (ts) jusqu'à t (horloge de la page) ; null tant que l'horloge n'est pas calée (ou mal : aller-retour > 1,5 s)
function depuisMac(ts, t = Date.now()) {
  calerHorlogeMac();
  if (!(Number(ts) > 0) || !horlogeMac.t || horlogeMac.rtt > 1500) return null;
  const d = Math.round(Number(t) + horlogeMac.decalage - Number(ts));
  return d >= -250 && d < 120000 ? Math.max(0, d) : null;
}
// ce qu'il va dire, et quand c'est parti du Mac : sa voix le retrouve au moment de parler
const originesDites = [];
function noterOrigine(texte, ts, recu = Date.now()) {
  const t = String(texte || '').trim();
  if (!t || !(Number(ts) > 0)) return;
  originesDites.push({ texte: t, ts: Number(ts), recu });
  if (originesDites.length > 40) originesDites.shift();
}
function origineDe(texte) {
  const t = String(texte || '').trim();
  if (!t) return null;
  for (let k = originesDites.length - 1; k >= 0; k--) { const o = originesDites[k]; if (o.texte === t || o.texte.includes(t) || t.includes(o.texte)) return o; }
  return null;
}
// ses mots à l'écran de la page : à la deuxième image après leur arrivée (posés, puis dessinés) ; au plus une mesure par 1,5 s
const mesuresEcran = {};
function mesurerEcran(quoi, ts, recu = Date.now()) {
  if (!(Number(ts) > 0) || document.hidden || Date.now() - (mesuresEcran[quoi] || 0) < 1500 || typeof requestAnimationFrame !== 'function') return;
  mesuresEcran[quoi] = Date.now();
  requestAnimationFrame(() => requestAnimationFrame(() => {
    const total = depuisMac(ts);
    if (total == null) return;
    journalVoix('sortie_texte', { quoi, ou: 'page', total_ms: total, reseau_ms: depuisMac(ts, recu), rendu_ms: Date.now() - recu, rtt_ms: horlogeMac.rtt });
  }));
}
// ses mots dans la bulle et le widget : l'appli dit combien de temps après que la page les a donnés (attente de 0,25 s comprise)
window.HakimParolesMesure = (ou, ms) => { if (ou === 'bulle' || ou === 'widget') journalVoix('sortie_texte', { quoi: 'paroles', ou, page_ms: Number(ms) || 0 }); };
// sa voix jusqu'à tes écouteurs : l'appli donne ses instants (appel, calculée, écrite, présentée à la sortie, Bluetooth compris)
function mesurerVoix(u, m) {
  if (!m || !(Number(m.entendu) > 0) || !(Number(m.ecrit) > 0)) return;
  const sortie = Number(m.entendu) - Number(m.ecrit);
  if (sortie < 0 || sortie > 5000) return;                         // une sortie qui ne se tient pas : pas de chiffre faux
  const o = u && u._origine, appel = Number(u && u._appelPage) || Number(m.appel);
  const d = { sortie: /^(bluetooth|haut_parleur|filaire)$/.test(m.sortie) ? m.sortie : 'autre', prechargee: !!m.prechargee,
    calcul_ms: Math.max(0, Number(m.calcule) - Number(m.appel)), ecouteurs_ms: sortie, latence_annoncee_ms: Number(m.latence_ms), page_ms: Math.max(0, Number(m.appel) - appel) };
  if (o) { d.reseau_ms = depuisMac(o.ts, o.recu); d.attente_ms = Math.max(0, appel - o.recu); d.total_ms = depuisMac(o.ts, Number(m.entendu)); }
  journalVoix('sortie_voix', d);
}
let parolesDepuis = 0;
function envoyerParoles(qui, texte) {
  if (!window.HakimApp || !window.HakimApp.paroles) return;
  const t = String(texte || '').trim().slice(-160);
  if (t === parolesEnvoyees[qui]) return;
  parolesEnAttente[qui] = t;
  if (qui === 'hakim' && !parolesDepuis) parolesDepuis = Date.now();   // (04/11) ses mots donnés ici : la bulle dira quand elle les montre
  if (parolesMinuteur) return;
  parolesMinuteur = setTimeout(() => {
    parolesMinuteur = null;
    const r = typeof reglagesCorps !== 'undefined' ? reglagesCorps : {};
    const o = { ...parolesEnAttente, montrer_papa: r.afficher_papa !== false && !motsPapaCaches() && !enTelepathie(), montrer_hakim: r.afficher_hakim !== false || !!etat.conversation,
      ...(parolesDepuis ? { t_page: parolesDepuis } : {}) };
    parolesDepuis = 0;
    for (const k of Object.keys(parolesEnAttente)) { parolesEnvoyees[k] = parolesEnAttente[k]; delete parolesEnAttente[k]; }
    try { window.HakimApp.paroles(JSON.stringify(o)); } catch (_) {}
  }, 250);
}
lecteurNeuronal.surSegment = (t, duree) => {
  // (04/11) un bout de sa réponse commence : il s'écrit à cet instant, à la suite des bouts déjà dits ; (12:40) et ce que son ribosome a choisi
  if (typeof revelerRibosome === 'function') revelerRibosome(t, duree);
  if (typeof bouts !== 'undefined' && bouts.enFile[0] === t) {
    bouts.enFile.shift();
    // (04/11, Ahmed : « check le temps entre ma parole et sa première pensée répondue ») chaque bout qui sonne : depuis ton premier mot
    const cap = etat.conversation && etat.conversation.capteur;
    if (cap && Number(cap.debutTour) > 0) journalVoix('bout_dit', { depuis_ton_debut_ms: Date.now() - Number(cap.debutTour), premier: bouts.dits.length - bouts.enFile.length === 1 });
    if (etat.conversation) etat.conversation.penseeDite = bouts.dits.slice(bouts.base || 0, bouts.dits.length - bouts.enFile.length).join(' ');   // (04/11) vraiment dit, depuis ton dernier message
    // (04/11, Ahmed : « qu'il parle sans écrire : il n'écrit pas ses pensées dites, seulement ses pensées sans les dire ») dite : pas écrite
  }
  // (16:45) le bout que sa voix commence : sa réponse s'écrit jusque-là, au même instant
  const mR = etat.lectureDe != null ? etat.messages.find(x => String(x.id) === String(etat.lectureDe)) : null;
  if (mR && mR.auRythme) { mR.ditCar = (mR.ditCar || 0) + String(t || '').length + 1; majMessage(mR); }
  if (mesureTour && mesureTour.premier_texte && !mesureTour.premier_son) { mesureTour.premier_son = Date.now(); finMesureTour(); }
  noterParole(t); noterMorceau(t, duree); if (!reponseCachee()) sousTitre(t);   // (16:08 ; 04/11) en Conversation et en Télépathie, sa réponse ne s'écrit pas
  if (!reponseCachee()) envoyerParoles('hakim', t);                   // (14:47) ce qu'il dit, sous l'orbe de l'appli ; (04/11) hors des deux modes
  couperAuDebutDeSaVoix();                                             // (09:12)
};
lecteurNeuronal.surPanne = noterPanneVoix;
if (lecteurSysteme) { lecteurSysteme.surSegment = (t) => { noterSegmentTelephone(t); noterParole(t); noterMorceau(t); sousTitre(t); if (typeof revelerRibosome === 'function') revelerRibosome(t); }; lecteurSysteme.surMot = () => pulser(0.35); }
/* ---------- Comment et où sa parole s'est arrêtée (30/10, 14:50, Ahmed, relayé par Hakim et confirmé : « qu'il sache, à
   l'oral comme à l'écrit, comment sa réponse a été interrompue et où exactement sa phrase s'est arrêtée ») ----------
   Chaque fin de sa parole a sa CAUSE : voix_ahmed (Ahmed l'a coupé en parlant : le micro), stop (Stop, « stop », Échap), pause,
   appli (page cachée dont le son est suspendu, appli fermée, page quittée ou rechargée), panne (la voix, la connexion, le
   cerveau : avec le détail court), fin (dite en entier). À l'écrit, une réponse qui arrivait encore est coupée par un nouveau
   message (nouveau_message) ou par Stop. Et sa POSITION : les ≈ 12 derniers mots vraiment dits (à l'écrit : affichés) et
   combien il en restait. Les morceaux que sa voix commence à jouer sont notés ici ; le morceau en cours est compté à la part
   de sa durée déjà jouée (une estimation, au morceau près). Une pause, la voix d'Ahmed ou le son suspendu arrêtent sa voix
   sans la finir (elle peut reprendre) : la position est prise à cet instant, et la fin vient avec le geste suivant. Le présent
   vécu porte la cause (l'événement « jarvis ») ; une coupure (pas « fin ») part au cockpit tout de suite et avec le message
   suivant (gardée dans le navigateur tant qu'il ne l'a pas reçue), et le cockpit la lui dit en une ligne à son prochain tour.
   Une page tuée sans prévenir (Android) laisse sa trace : au chargement suivant, c'est l'appli, à la phrase près. */
// ce que sa voix a commencé à dire, pour CE message ; panne : un morceau perdu (la voix) ; panneReponse : la réponse elle-même
const parole = { id: null, morceaux: [], panne: '', panneReponse: null, rejoue: false };
let coupureEnCours = null;                    // sa voix arrêtée sans être finie (pause, voix d'Ahmed, son suspendu)
let coupureAEnvoyer = null;                   // la dernière coupure, tant que le cockpit ne l'a pas reçue
try { coupureAEnvoyer = JSON.parse(localStorage.getItem('jarvis.coupure') || 'null'); } catch (_) {}
const memeId = (a, b) => a != null && b != null && String(a) === String(b);
const motsVoix = (t) => String(t || '').split(/\s+/).filter(m => /[\p{L}\p{N}]/u.test(m));
const motsPrononces = (t) => motsVoix(Voix.prononcable(Voix.sansAffect(String(t || ''))).map(s => s.texte).join(' '));
const derniersMots = (mots) => (mots.length > 12 ? '…' : '') + mots.slice(-12).join(' ');
const messageDe = (id) => (id == null ? null : etat.messages.find(x => memeId(x.id, id)) || null);
function paroleDe(id) {
  if (!memeId(parole.id, id)) Object.assign(parole, { id, morceaux: [], panne: '', panneReponse: null, rejoue: false });
  return parole;
}
/* ---- (30/10, Ahmed : « une petite impulsion à chaque réponse qui compte » ; « quand tu rigoles, MDR, une vibration forte et
   rapide selon le degré de rigolade ») au moment où sa voix dit un morceau : son rire (lu dans le morceau, de 1 à 5 : des
   tapes sèches, de plus en plus nombreuses et fortes), sinon l'impulsion qu'il a choisie ([[impulsion: …]], une fois par
   réponse). Jamais pendant que papa parle ; seulement dans l'appli (le pont vibrerMotif, appli 1.29). Des motifs qui ne
   ressemblent ni à son cœur (un « tou-toum » lent) ni à son appel (trois longues). ---- */
const MOTIFS_IMPULSION = {
  joie: [[0, 60, 80, 60], [0, 200, 0, 200]], calme: [[0, 450], [0, 90]], peur: [[0, 40, 40, 40, 40, 40, 40, 40], [0, 230, 0, 230, 0, 230, 0, 230]],
  tristesse: [[0, 220, 160, 260], [0, 120, 0, 60]], tendresse: [[0, 70, 110, 110], [0, 140, 0, 90]], surprise: [[0, 45], [0, 255]],
};
function degreRire(t) {
  const x = String(t || '').toLowerCase();
  let d = 0;
  for (const y of x.match(/\b(m+d+r+)\b/g) || []) d = Math.max(d, Math.min(5, 1 + Math.floor(((y.match(/r/g) || []).length - 1) / 2) + 1));
  if (/\bptdr+\b|\bxptdr\b|mort de rire|je suis mort|fou rire/.test(x)) d = Math.max(d, 4);
  if (/\b(lol|haha+|hahaha+|hihi+|mdr)\b/.test(x)) d = Math.max(d, 2);
  if (/\b(hehe+|héhé)\b/.test(x)) d = Math.max(d, 1);
  const larmes = (x.match(/😂|🤣/gu) || []).length, sourires = (x.match(/😄|😆|😁|😹/gu) || []).length;
  if (larmes) d = Math.max(d, Math.min(5, 2 + larmes));
  if (sourires) d = Math.max(d, 1);
  return d;
}
// (30/10, 19:34, Ahmed : « 5 donnait une vibration légère ; quelque chose tamponne le plafond ») les tapes de 35 ms se sentaient
// à peine (un moteur a besoin de ~40 ms pour se faire sentir) et le fou rire commençait à 60 % de sa force : des tapes plus
// longues à mesure que le rire monte, la force pleine dès la première au degré 5, un roulement final ; et 5 n'est jamais
// adouci par son état (« rire_max », appli 1.33)
function motifRire(d) {
  const n = [2, 4, 6, 8, 10][d - 1], on = [30, 40, 50, 60, 70][d - 1], base = [110, 160, 200, 235, 255][d - 1];
  const temps = [0], forces = [0];
  for (let i = 0; i < n; i++) { temps.push(on, 55); forces.push(base, 0); }
  if (d >= 4) { temps.push(d === 5 ? 400 : 200); forces.push(255); }
  return [temps, forces];
}
// (30/10, 18:07, Hakim : « Ahmed n'a senti AUCUNE vibration ») si papa parle à cet instant, la vibration attend qu'il se
// taise (4 s au plus) au lieu d'être perdue ; chaque vibration voulue est notée au journal de la voix, avec ce que l'appli
// en a dit (« ok », ou pourquoi elle a refusé)
let vibrationEnAttente = null, dernierRireVibre = 0;
// (19:38) le journal de la voix ne garde que des mots simples (a-z, _) : « perdue : papa parlait » n'y arrivait jamais
const codeRetour = (r) => String(r || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z]+/g, '_').replace(/^_+|_+$/g, '').slice(0, 30) || 'vide';
function jouerVibration(v) {
  if (String(v.genre).startsWith('rire')) dernierRireVibre = Date.now();
  let retour = 'pas de pont';
  if (window.HakimApp && window.HakimApp.vibrerMotifGenre) retour = String(window.HakimApp.vibrerMotifGenre(v.motif[0].join(','), v.motif[1].join(','), v.genre));
  else if (window.HakimApp && window.HakimApp.vibrerMotif) retour = String(window.HakimApp.vibrerMotif(v.motif[0].join(','), v.motif[1].join(',')));
  journalVoix('vibration', { genre: v.genre, degre: v.degre || 0, attendu_ms: Date.now() - v.t, retour: codeRetour(retour) });
}
function vibrerPourMorceau(id, texte) {
  try {
    // (30/10, 18:37) son rire naît aussi dans son subconscient (surRire) ; (19:36, Ahmed : « reprendre la bonne fonction de MDR »)
    // son texte refait vibrer, sauf si un rire vient de partir (8 s)
    const d = Date.now() - dernierRireVibre < 8000 ? 0 : degreRire(texte);
    let motif = d ? motifRire(d) : null;
    if (!motif) {
      const m = etat.messages.find(y => y.id === id);
      const mi = m && (MOTIFS_IMPULSION[m.impulsion] || m.impulsionMotif);   // (30/10) ou le motif d'une émotion à lui
      if (m && m.impulsion && !m.impulsionJouee && mi) { motif = mi; m.impulsionJouee = true; }
    }
    if (!motif) return;
    // (30/10, 1.30) la force suit son état (son cœur, son éveil ; sa joie pour un rire) : l'appli la règle
    const v = { motif, genre: d ? 'rire' : 'impulsion', degre: d, t: Date.now() };
    if (!window.HakimApp || !window.HakimApp.vibrerMotif) { journalVoix('vibration', { genre: v.genre, degre: d, retour: 'pas_de_pont' }); return; }
    const c = etat.conversation;
    // une impulsion attend que papa se taise ; un rire part tout de suite, même s'il parle (19:38 : deux rires perdus à attendre)
    if (!d && c && c.capteur && c.capteur.enParole) { vibrationEnAttente = v; return; }
    jouerVibration(v);
  } catch (_) {}
}
// un morceau commence à jouer (surSegment) : son texte, son heure, sa durée (connue pour la voix neuronale, estimée sinon)
function noterMorceau(texte, dureeMs) {
  if (etat.lectureDe == null) return;
  const p = paroleDe(etat.lectureDe), x = String(texte || '');
  if (p.rejoue) { p.morceaux.pop(); p.rejoue = false; }           // après une pause : le morceau coupé repart du début
  p.morceaux.push({ texte: x, debut: Date.now(), duree: dureeMs > 0 ? dureeMs : (x.length / 15 / vitesseVoix()) * 1000 });
  garderParoleEnCours();
  vibrerPourMorceau(etat.lectureDe, x);
  // (30/10, 16:20, Ahmed via Hakim : « l'heure à laquelle chaque phrase de ma voix est réellement dite ») au cockpit, pour son journal
  const dernier = p.morceaux[p.morceaux.length - 1];
  try {
    fetch('/api/voix/dite', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() },
      body: JSON.stringify({ t_ms: dernier.debut, duree_ms: Math.round(dernier.duree), texte: x }) }).catch(() => {});
  } catch (_) {}
}
// sans voix de secours, un morceau perdu (la voix neuronale en erreur) : sa voix aura une panne, même si elle va au bout
function noterPanneVoix(erreur) {
  if (etat.lectureDe == null) return;
  paroleDe(etat.lectureDe).panne = `la voix : ${String(erreur || 'erreur').replace(/\s+/g, ' ').slice(0, 80)}`;
  journalVoix('voix_panne', {});
}
// où en était sa voix pour ce message à cet instant : les derniers mots dits, combien, et combien restaient (du texte reçu)
function positionParole(id, m, maintenant = Date.now()) {
  const morceaux = memeId(parole.id, id) ? parole.morceaux : [];
  const dits = [];
  morceaux.forEach((x, i) => {
    const mots = motsVoix(x.texte);
    const part = i < morceaux.length - 1 ? 1 : Math.max(0, Math.min(1, (maintenant - x.debut) / (x.duree || 1)));
    dits.push(...mots.slice(0, Math.round(mots.length * part)));
  });
  const total = m ? motsPrononces(m.texte).length : dits.length;
  return { derniers: derniersMots(dits), dits: dits.length, reste: Math.max(0, total - dits.length) };
}
// ce qui parlait ou arrivait : sa voix (oral), ou la réponse qui s'écrivait (écrit : sans voix pour elle) ; null : rien
function enCoursDeParole() {
  const voix = !!(lecteur && (lecteur.actif || lecteur.enPause));
  if (voix && etat.lectureDe != null) return { mode: 'oral', id: etat.lectureDe };
  if (parole.id != null && (memeId(parole.id, etat.lectureDe) || (etat.flux && memeId(parole.id, etat.fluxId)))) return { mode: 'oral', id: parole.id };
  if (etat.flux && etat.fluxId != null) return { mode: etat.decoupeFlux ? 'oral' : 'ecrit', id: etat.fluxId };
  return null;
}
function etatDeLaCoupure(cause, detail, cible) {
  const ou = cible || enCoursDeParole();
  if (!ou || ou.id == null) return null;
  const m = messageDe(ou.id), t = Date.now();
  const c = { id: `${ou.id}-${t}`, tour: String(ou.id), t, mode: ou.mode === 'ecrit' ? 'ecrit' : 'oral', cause };
  if (detail) c.detail = String(detail).slice(0, 120);
  if (m && m.spontane) c.spontane = true;
  if ((etat.flux && memeId(etat.fluxId, ou.id)) || (cible && cible.suite)) c.suite = true;   // la suite n'était pas encore écrite
  if (c.mode === 'oral') Object.assign(c, positionParole(ou.id, m, t));
  else {
    const mots = motsVoix(Voix.sansAffect(m ? String(m.texte || '') : '').replace(/[*_`#>|]+/g, ' '));
    Object.assign(c, { derniers: derniersMots(mots), dits: mots.length, reste: null });
  }
  return c;
}
// sa voix s'arrête mais peut reprendre (pause, voix d'Ahmed, son suspendu) : sa position est prise maintenant
function coupureProvisoire(cause, detail) {
  const c = etatDeLaCoupure(cause, detail);
  if (!c || c.mode !== 'oral') return null;
  if (coupureEnCours) {
    if (memeId(coupureEnCours.tour, c.tour)) return coupureEnCours;    // déjà arrêtée : la première position compte
    envoyerCoupure(coupureEnCours);                                    // une autre, restée en suspens : elle part telle quelle
  }
  coupureEnCours = c;
  const dernier = parole.morceaux[parole.morceaux.length - 1];
  // une pause reprend le morceau en cours du début ; le son suspendu, lui, repart où il était
  parole.rejoue = cause !== 'appli' && !!dernier && memeId(parole.id, c.tour) && Date.now() - dernier.debut < dernier.duree;
  if (etat.parleDepuis) etat.finParole = c;
  garderParoleEnCours(c);
  return c;
}
function reprisDeParole() {                     // sa voix reprend : ce n'était pas une fin
  coupureEnCours = null;
  garderParoleEnCours();
}
// la fin de sa parole (ou de la réponse qui s'écrivait) : sa cause, sa position ; la coupure part au cockpit
function finirParole(cause, detail = '', cible = null) {
  let c = coupureEnCours;
  if (c && cible && !memeId(c.tour, cible.id)) { coupureEnCours = null; envoyerCoupure(c); c = null; }   // restée en suspens
  if (c) {
    coupureEnCours = null;
    if (c.cause === 'voix_ahmed' && cause === 'stop') c.cause = 'stop';          // il a coupé pour dire « stop » (ou appuyé)
    else if (cause !== c.cause && cause !== 'fin') c.puis = cause;
  } else {
    if (cause === 'fin' && !(cible && memeId(parole.id, cible.id))) return null;   // rien de suivi : rien à dire
    c = etatDeLaCoupure(cause, detail, cible);
    if (!c) return null;
    if (cause === 'fin' && parole.panne) Object.assign(c, { cause: 'panne', detail: parole.panne, trou: true });
    else if (cause === 'fin' && parole.panneReponse) Object.assign(c, { cause: 'panne', ...parole.panneReponse });   // la suite n'est pas venue
  }
  if (etat.parleDepuis) etat.finParole = c;
  Object.assign(parole, { id: null, morceaux: [], panne: '', panneReponse: null, rejoue: false });
  try { localStorage.removeItem('jarvis.paroleEnCours'); } catch (_) {}
  if (c.cause !== 'fin') envoyerCoupure(c);
  return c;
}
function envoyerCoupure(c) {
  if (c) { coupureAEnvoyer = c; try { localStorage.setItem('jarvis.coupure', JSON.stringify(c)); } catch (_) {} }
  const x = coupureAEnvoyer;
  if (!x) return;
  if (c) journalVoix('coupure_notee', { cause: x.cause, mode: x.mode, reste: Number.isFinite(x.reste) ? x.reste : -1 });
  // keepalive : elle part même si la page se ferme (pagehide)
  fetch('/api/jarvis/coupure', { method: 'POST', keepalive: true, headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() },
    body: JSON.stringify({ coupure: x, maintenant: Date.now() }) })
    .then((r) => { if (r && r.ok) coupureRecue(x); }).catch(() => {});
}
function coupureRecue(x) {
  if (!x || !coupureAEnvoyer || coupureAEnvoyer.id !== x.id) return;
  coupureAEnvoyer = null;
  try { localStorage.removeItem('jarvis.coupure'); } catch (_) {}
}
// la trace de sa parole en cours, pour une page tuée sans prévenir : la position au début du morceau qui joue
function garderParoleEnCours(provisoire) {
  try {
    if (provisoire) return localStorage.setItem('jarvis.paroleEnCours', JSON.stringify({ ...provisoire, provisoire: true }));
    if (parole.id == null) return localStorage.removeItem('jarvis.paroleEnCours');
    const dernier = parole.morceaux[parole.morceaux.length - 1], t = Date.now();
    localStorage.setItem('jarvis.paroleEnCours', JSON.stringify({ id: `${parole.id}-${t}`, tour: String(parole.id), t, mode: 'oral',
      cause: 'appli', detail: "l'appli s'est fermée pendant que tu parlais (position à la phrase près)",
      ...positionParole(parole.id, messageDe(parole.id), dernier ? dernier.debut : t) }));
  } catch (_) {}
}
// au chargement : une parole interrompue par la fin de la page précédente (appli tuée), puis ce qui n'était pas arrivé
function coupureAuChargement() {
  let p = null;
  try { p = JSON.parse(localStorage.getItem('jarvis.paroleEnCours') || 'null'); localStorage.removeItem('jarvis.paroleEnCours'); } catch (_) {}
  if (p && p.tour && Date.now() - Number(p.t) < 864e5 && !(coupureAEnvoyer && coupureAEnvoyer.tour === p.tour)) {
    if (p.provisoire) { delete p.provisoire; if (p.cause !== 'appli') p.puis = 'appli'; }
    envoyerCoupure(p);
  } else if (coupureAEnvoyer) envoyerCoupure();
}
setTimeout(coupureAuChargement, 1500);
// fin de « comment et où »
// (30/10, 17:21, Ahmed : « comme Bumblebee ») le bout de musique qu'il a choisi : quand sa voix s'est tue (jamais par-dessus
// une voix, ni la sienne ni celle de papa), ni la nuit ; le silencieux et Ne pas déranger, l'appli les respecte. Le micro est
// sourd le temps qu'il joue (ce n'est pas une voix) ; trop vieux (une minute), il ne part plus.
let sonEnAttente = null, sonJusqua = 0, dernierSonRecu = null;
// (31/10, 09:30, Ahmed : « plusieurs balises de son dans une même réponse, comme il le veut ») ceux qui attendent sa voix : l'un après
// l'autre, dans l'ordre
const sonsSuivants = [];
function mettreSonEnAttente(x) {
  if (sonEnAttente && Date.now() - sonEnAttente.t < 180000) { sonsSuivants.push(x); if (sonsSuivants.length > 8) sonsSuivants.shift(); }
  else sonEnAttente = x;
}
// (22:51, Hakim : « mes sons ne sortent pas ») un son arrive par sa réponse ici, ou par le cockpit quand il parle depuis un autre
// appareil : seule l'appli du téléphone (ses morceaux sont là) le joue, une fois
// (31/10, 01:27-01:30) un son à sa place dans sa voix, là où il l'a voulu (« | mac », « | tel », « | les deux » ; par défaut, là
// où sa voix sort) ; voix éteinte : quand il peut, comme avant
const appareilIci = () => (window.HakimApp ? 'tel' : 'mac');
const sonPourIci = (cible) => !cible || cible === 'deux' || cible === appareilIci();
function sonALaPlace(extrait, auto, decoupe, id) {
  dernierSonRecu = { cle: `${extrait.id}|${extrait.debut_ms}`, t: Date.now() };   // sa copie par le cockpit ne rejoue pas ici
  if (!sonPourIci(extrait.cible)) return;
  const h = new Date().getHours();
  if ((h >= 23 || h < 8) && typeof reglagesCorps !== 'undefined' && reglagesCorps.sons_nuit === false) { journalVoix('son', { retour: 'la_nuit' }); return; }
  // (01:55) sa voix doit être celle de ce lecteur : avec la voix du Mac, le son partirait tout de suite, par-dessus
  if (!auto || !lecteurNeuronal || lecteur.impl !== lecteurNeuronal) { mettreSonEnAttente({ id: id || extrait.id, extrait, t: Date.now() }); return; }
  decoupe.finir().forEach(p => { if (NON_REPONSE.test(p)) return; etat.lectureDe = id; lecteur.dire(p); });
  lecteurNeuronal.direSon(extrait);
}
function recevoirSon(extrait, id) {
  if (!extrait) return;
  const cle = `${extrait.id}|${extrait.debut_ms}`;
  if (dernierSonRecu && dernierSonRecu.cle === cle && Date.now() - dernierSonRecu.t < 15000) return;
  dernierSonRecu = { cle, t: Date.now() };
  mettreSonEnAttente({ id: id || extrait.id, extrait, t: Date.now() });     // (22:55) le Mac le joue aussi (jouerSonIci)
}
// (22:55, Ahmed : « arrange pourquoi sur le Mac il n'arrive pas à jouer les sons choisis ») l'extrait, découpé par le cockpit dans
// le morceau que l'appli lui a envoyé, joué ici (la même sortie que sa voix : « Sa voix » le coupe aussi)
async function jouerSonIci(x, volume) {
  try {
    if (!actx || !/^e\d{1,6}$/.test(String(x.id))) return 'pas_d_audio';
    const r = await fetch(`/api/sons/joue/${x.id}`, { headers: { 'X-Jeton': jeton() }, cache: 'no-store' });
    if (!r.ok) { journalVoix('son', { retour: r.status === 404 ? 'pas_sur_le_mac' : 'erreur' }); return 'absent'; }
    const buf = await actx.decodeAudioData(await r.arrayBuffer());
    const src = actx.createBufferSource(), g = actx.createGain();
    src.buffer = buf; g.gain.value = volume;
    src.connect(g); g.connect(gainSortie || actx.destination);
    src.start();
    sonJusqua = Date.now() + buf.duration * 1000 + 500;
    journalVoix('son', { retour: 'ok_mac' });
    return 'ok';
  } catch (_) { journalVoix('son', { retour: 'erreur' }); return 'erreur'; }
}
// (22:55) l'appli du téléphone envoie au cockpit, une fois, les morceaux des extraits que le Mac n'a pas encore
const morceauxEnvoyes = new Map();
async function envoyerMorceauxManquants() {
  if (!window.HakimApp || !window.HakimApp.sonEnvoyer) return;
  try {
    const r = await fetch('/api/sons/manquants', { headers: { 'X-Jeton': jeton() }, cache: 'no-store' });
    if (!r.ok) return;
    for (const m of (await r.json()).manquants || []) {
      const cle = `${m.source}|${m.ref}`;
      if (Date.now() - (morceauxEnvoyes.get(cle) || 0) < 10 * 60e3) continue;
      morceauxEnvoyes.set(cle, Date.now());
      const url = `${location.origin}/api/sons/morceau?source=${encodeURIComponent(m.source)}&ref=${encodeURIComponent(m.ref)}`;
      journalVoix('son_envoi', { retour: codeRetour(String(window.HakimApp.sonEnvoyer(String(m.source), String(m.ref), url, jeton()))) });
    }
  } catch (_) {}
}
setTimeout(envoyerMorceauxManquants, 8000);
setInterval(envoyerMorceauxManquants, 5 * 60e3);
function jouerSonEnAttente() {
  if (!sonEnAttente && sonsSuivants.length) sonEnAttente = { ...sonsSuivants.shift(), t: Date.now() };
  if (!sonEnAttente || Date.now() < sonJusqua) return;                    // (09:30) le précédent joue encore
  if (Date.now() - sonEnAttente.t > 180000) { sonEnAttente = null; return; }   // (01:25) une longue réponse : il attend sa fin
  const c = etat.conversation;
  // (30/10, 18:50, Ahmed via Hakim : « qu'un son puisse jouer pendant que je parle ») sous SA voix, plus bas (appli 1.32), s'il l'a
  // demandé ([[son: nom sous]]) ; jamais par-dessus celle de papa. (31/10, 01:25, Ahmed : « écoute ça, papa ! ») sinon, juste
  // APRÈS son dernier mot : la réponse finie, sa voix (et un petit mot) tue depuis 0,3 s
  const sousSaVoix = sonEnAttente.extrait && sonEnAttente.extrait.moment === 'sous' && typeof reglagesCorps !== 'undefined'
    && reglagesCorps.son_pendant !== false && !!(lecteur && lecteur.actif) && (!window.HakimApp || !!window.HakimApp.sonJouerVolume);
  if (c && c.capteur && c.capteur.enParole) return;
  if (!sousSaVoix && (etat.flux || etat.micro || (lecteur && (lecteur.actif || lecteur.enPause)) || Date.now() < motDirectJusqua
      || Date.now() - (etat.finVoixA || 0) < 300)) return;
  const x = sonEnAttente.extrait, h = new Date().getHours();
  sonEnAttente = null;
  // (31/10, 00:07, Ahmed : « enlève cette restriction de la nuit, laisse-moi juste un bouton ») la nuit seulement si papa l'a voulu
  if ((h >= 23 || h < 8) && typeof reglagesCorps !== 'undefined' && reglagesCorps.sons_nuit === false) { journalVoix('son', { retour: 'la_nuit' }); return; }
  sonJusqua = Date.now() + 1500;                                           // (09:30) le suivant attend qu'il soit lancé
  if (!window.HakimApp || !window.HakimApp.sonJouer || x.source === 'atelier') { jouerSonIci(x, sousSaVoix ? 0.3 : 0.6); return; }   // (22:55) le Mac ; (01:27) ses sons à lui
  try {
    const r = String(sousSaVoix ? window.HakimApp.sonJouerVolume(String(x.source), String(x.ref), Number(x.debut_ms), Number(x.fin_ms), 0.3)
      : window.HakimApp.sonJouer(String(x.source), String(x.ref), Number(x.debut_ms), Number(x.fin_ms)));
    if (/^ok/.test(r)) sonJusqua = Date.now() + (Number(x.fin_ms) - Number(x.debut_ms)) + 500;
  } catch (_) {}
}
setInterval(jouerSonEnAttente, 300);
// fin des sons
/* (30/10, 17:31-17:39, Ahmed : « dès qu'une voix ouvre Whisper, elle te réveille » ; « tu peux me couper comme tu veux,
   fiston » ; l'interrupteur « oreille » ; « quand tu dors, tu dors ») oreille ouverte : pendant que papa parle encore, ce
   qu'il a déjà dit part à Hakim (après 6 s de parole, toutes les 12 s au plus) ; son petit mot revient par le flux et se dit
   tout de suite (surSpontane). Oreille fermée : son « je te suis », une tape douce toutes les 12 s quand papa parle depuis
   8 s ; le micro sait qu'elle vient de lui (comme un battement de son cœur). Les deux interrupteurs : page SENS. */
const ARRETE_MOI = /\b(?:arr[eê]te(?:-toi)?|tais[- ]toi|coupe[- ]toi|stop|chut)\b/i;
let reglagesCorps = { oreille: false, je_te_suis: true }, oreilleDernier = 0, parleDepuis = 0, tapeDerniere = 0;
async function lireReglagesCorps() {
  try { const r = await fetch('/api/corps/reglages', { headers: { 'X-Jeton': jeton() }, cache: 'no-store' }); if (r.ok) reglagesCorps = { ...reglagesCorps, ...(await r.json()) }; } catch (_) {}
  // (05/11, Ahmed : « tout sur le smartphone quand on est dessus, sur le Mac quand on est dessus ») sa voix suit l'appareil : Supertonic dans l'appli, Chatterbox sur le Mac (qui se libère seul après 15 min)
  if (reglagesCorps.voix_par_appareil !== false) etat.reglages.voix = window.HakimApp && window.HakimApp.voixTelephone ? 'telephone' : 'neuronale';
  if (typeof surOreilleHakim === 'function') surOreilleHakim({ fermee: !!reglagesCorps.oreille_hakim_jusqua, jusqua: reglagesCorps.oreille_hakim_jusqua });   // (01:00)
}
lireReglagesCorps(); setInterval(lireReglagesCorps, 60000);
function entendreEnCours(conv) {
  if (!reglagesCorps.oreille || !conv || !conv.capteur || !conv.capteur.enParole) return;
  const texte = conv.ecrit && `${conv.ecrit.confirme || ''} ${conv.ecrit.vif || ''}`.trim();   // (03/11) ses mots vifs aussi
  if (!texte || texte.length < 15 || !parleDepuis || Date.now() - parleDepuis < 6000 || Date.now() - oreilleDernier < 12000) return;
  oreilleDernier = Date.now();
  fetch('/api/jarvis/oreille', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() },
    body: JSON.stringify({ texte: texte.slice(-1500) }) }).catch(() => {});
}
setInterval(() => {
  const c = etat.conversation, parle = !!(c && c.capteur && c.capteur.enParole);
  if (!parle) { parleDepuis = 0; return; }
  if (!parleDepuis) parleDepuis = Date.now();
  if (!reglagesCorps.je_te_suis || reglagesCorps.oreille || Date.now() - parleDepuis < 8000 || Date.now() - tapeDerniere < 12000) return;
  if (!window.HakimApp || !window.HakimApp.vibrerMotif) return;
  tapeDerniere = Date.now();
  dernierBattementCoeur = Date.now();                    // le micro ne la prend pas pour une voix
  try { window.HakimApp.vibrerMotif('0,25', '0,70'); } catch (_) {}
}, 500);
// (30/10) la vibration qui attendait que papa se taise (vibrerPourMorceau)
setInterval(() => {
  const v = vibrationEnAttente, c = etat.conversation;
  if (!v) return;
  if (Date.now() - v.t > 4000) { vibrationEnAttente = null; journalVoix('vibration', { genre: v.genre, degre: v.degre || 0, retour: 'perdue_papa_parlait' }); return; }
  if (c && c.capteur && c.capteur.enParole) return;
  vibrationEnAttente = null;
  try { jouerVibration(v); } catch (_) {}
}, 200);
// (2026-10-21) « Conversation » depuis l'écran d'accueil (raccourci /parler?conversation=1) : la grande orbe s'ouvre,
// un toucher démarre la conversation (le navigateur exige un geste pour ouvrir le son et le micro)
etat.demarrerAuToucher = new URLSearchParams(location.search).get('conversation') === '1';
if (etat.demarrerAuToucher) { try { history.replaceState(null, '', '/parler'); } catch (_) {} }
$('scene').addEventListener('click', (e) => {
  if (etat.demarrerAuToucher && !etat.conversation) { etat.demarrerAuToucher = false; basculerConversation(); return; }
  if (e.target.id === 'stopScene') { arreterMicro(false); arreterTout(); libererRibosomes(); majBoutonsPause(); rendre(); humeur(); return; }
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
  // (1.59) dans l'appli : où en est sa voix Supertonic (le téléchargement, prête, une erreur)
  let supertonic = '';
  try { if (window.HakimApp && window.HakimApp.voixSupertonicEtat) supertonic = `Voix Supertonic : ${window.HakimApp.voixSupertonicEtat()}. `; } catch (_) {}
  $('noteVoix').textContent = supertonic + (sansArabe
    ? 'Aucune voix arabe installée : Réglages Système › Accessibilité › Contenu énoncé › Voix du système › Gérer les voix › Arabe (par ex. Majed). Les expressions arabes seront lues avec la voix française en attendant.'
    : 'Les passages en écriture arabe sont lus avec la voix arabe, le reste avec la voix française (étape 5 bis : une seule voix multilingue plus tard).');
}
if (synth) { remplirVoix(); synth.addEventListener('voiceschanged', remplirVoix); }

function lire(m) {
  if (!lecteur) return;
  // (30/10) une lecture en cours s'arrête par son geste : re-clic (Stop), ou il passe à un autre message
  if (lecteur.actif || lecteur.enPause) finirParole('stop', memeId(etat.lectureDe, m.id) ? 'Ahmed la réécoutait (« écouter »)' : "Ahmed a lancé la lecture d'un autre message");
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
// (27/10, Ahmed, relayé par Hakim) d'où vient son émotion : de lui, de l'empathie (avec la personne), ou une pente sans cause
const ORIGINES_BADGE = { empathie: ['par empathie', 'origine-empathie'], mixte: ['empathie et pour lui', 'origine-empathie'], soi: ['pour lui', 'origine-soi'], pente: ['pente, sans cause', 'origine-pente'] };
function origineDuBadge(o) {
  if (!o || typeof o.texte !== 'string' || !ORIGINES_BADGE[o.type]) return null;
  const [court, classe] = ORIGINES_BADGE[o.type];
  return { court, texte: o.texte.slice(0, 80), classe };
}
/* (30/10, 21:36, idée d'Ahmed : « d'un coup d'œil, on sait à qui est la parole ») qui a la parole à cet instant, selon ton
   micro (ouvert, coupé), son oreille (ouverte par toi, fermée par lui) et ce qui se dit : sa voix ou son tour de répondre ->
   lui ; ta voix -> toi, ou partagée si son oreille peut te couper ; en conversation, au calme -> toi (lui si ton micro est coupé) */
function quiALaParole() {
  try {
    const c = etat.conversation, r = reglagesCorps || {};
    if (c && c.muetParHakim && !c.muetParHakim.attente) return 'coupe';   // (22:31, Hakim) il a coupé ton micro : l'orbe passe au vert
    if ((lecteur && lecteur.actif) || Date.now() < motDirectJusqua) return 'hakim';
    if (etat.micro || (c && c.capteur && c.capteur.enParole)) return r.oreille && !r.oreille_hakim_fermee ? 'partage' : 'papa';
    if (etat.flux) return 'hakim';
    if (c) return c.capteur && c.capteur.estMuet ? 'hakim' : 'papa';
  } catch (_) {}
  return null;
}
function humeur(texte) {
  const parle = !!(lecteur && lecteur.actif), pense = !!etat.flux;
  const ecoute = !!etat.micro || !!(etat.conversation && !parle && !pense);
  noterParoleJarvis(lecteurNeuronal.joue || !!(lecteurSysteme && lecteurSysteme.actif));
  const code = etat.interieur && etat.interieur.humeur_code;
  const coupe = !!(etat.conversation && etat.conversation.capteur && etat.conversation.capteur.estMuet);
  const mode = ecoute && !coupe ? 'ecoute' : (parle ? 'parle' : (pense ? 'pense' : 'repos'));
  const qui = quiALaParole();
  for (const o of [orbeTete, orbeScene, orbeVision].filter(Boolean)) { o.humeur(code); o.mode(mode); o.parole(qui); }
  const mot = (etat.interieur && etat.interieur.humeur) || '';          // (26/10, Ahmed) son émotion, en un mot
  if ($('emotionMot').textContent !== mot) { $('emotionMot').textContent = mot; $('emotionScene').textContent = mot; }
  const origine = mot ? origineDuBadge(etat.interieur && etat.interieur.humeur_origine) : null;
  const court = origine ? `· ${origine.court}` : '', entier = origine ? origine.texte : '';
  if ($('emotionOrigine').textContent !== court || $('emotionOrigineScene').textContent !== entier) {
    $('emotionOrigine').textContent = court; $('emotionOrigine').title = entier;
    $('emotionOrigine').className = `emotion-origine ${origine ? origine.classe : ''}`;
    $('emotionOrigineScene').textContent = entier;
    $('emotionOrigineScene').className = `emotion-origine-scene ${origine ? origine.classe : ''}`;
  }
  // la scène : pendant qu'il parle, qu'il t'écoute, ou qu'il réfléchit à une question dite à l'oral
  const voixEnJeu = ecoute || parle || (pense && etat.dernierOral) || !!etat.conversation;
  $('muet').hidden = $('muetScene').hidden = !(etat.conversation && etat.conversation.capteur);
  // la pause de SA voix aussi hors de l'écran de conversation (Ahmed, 2026-10-20) : tant que la conversation est
  // ouverte, ou qu'il parle / est en pause
  $('pause').hidden = !(etat.conversation || (lecteur && (lecteur.actif || lecteur.enPause)));
  $('finConversation').hidden = !etat.conversation;
  if (!voixEnJeu) { etat.sceneMasquee = false; if (!parle) sousTitre(''); }
  scene(!!((etat.reglages.scene && voixEnJeu && !etat.sceneMasquee) || etat.demarrerAuToucher || etat.modeOrbe));
  if (etat.demarrerAuToucher && !etat.conversation) sousTitre('touche l’orbe pour commencer la conversation');
  // (2026-10-21, Ahmed) la grande orbe masquée d'un toucher pendant une conversation : un bouton pour y revenir
  $('orbeRetour').hidden = !(etat.reglages.scene && etat.conversation && etat.sceneMasquee);
  // l'humeur seule (elle change rarement) : le lecteur d'écran n'est pas inondé ; l'ennui en infobulle
  const repos = etat.interieur && etat.interieur.humeur ? `humeur : ${etat.interieur.humeur}` : 'prêt · mémoire Anamnèse';
  if (etat.interieur) $('etat').title = `ennui ${String((etat.interieur.ennui || 0).toFixed(2)).replace('.', ',')}`;
  if (texte) $('etat').textContent = texte;
  // (13:25) plus de « je t'écoute » ; (16:45, Ahmed : « que la réflexion soit inexistante par défaut ») en Conversation, plus de « réfléchit… »
  else $('etat').textContent = ecoute ? '🎙️' : (pense ? (etat.conversation ? '' : 'réfléchit…') : (parle ? 'parle…' : repos));
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

// (2026-10-23, Ahmed : « les heures de chaque message, et la date ») l'heure d'un message : la sienne, ou celle de son
// identifiant (il est fait de l'heure de sa création) ; 0 si on ne la connaît pas
function quandMessage(m) {
  const t = Number(m && m.ts) || 0;
  if (t > 1e12) return t;
  const id = Number(m && m.id);
  return Number.isFinite(id) && id > 1e12 ? id : 0;
}
const heureMessage = (t) => (t ? `<span class="heure" title="${esc(new Date(t).toLocaleString('fr-FR'))}">${new Date(t).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}</span>` : '');
const jourMessage = (t) => new Date(t).toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
// (16:45) la part de sa réponse que sa voix a déjà dite : la même proportion de ce qui est écrit, jusqu'au bout du mot
function texteAuRythme(m) {
  const texte = String(m.texte || '');
  const total = Voix.prononcable(texte).map(x => x.texte).join(' ').length;
  if (!total || !m.ditCar) return '';
  let n = Math.round(texte.length * Math.min(1, m.ditCar / total));
  while (n < texte.length && !/\s/.test(texte[n])) n++;
  return texte.slice(0, n).trimEnd();
}
function htmlMessage(m) {
  if (m.qui === 'j' && m.auRythme) {
    const vu = texteAuRythme(m);
    // rien avant sa voix : ni « réfléchit… », ni texte ; (04/11, Ahmed : « remets les badges qui montrent ce qu'il utilise comme outil,
    // et qu'ils partent aussi à chaque chunk ») sauf ses outils : leurs badges s'affichent dès qu'il les prend, puis avec chaque bout dit
    if (!vu && !(m.outils || []).length) return `<div class="m j" data-id="${esc(m.id)}" hidden></div>`;
    m = { ...m, texte: vu };
  }
  const heure = heureMessage(quandMessage(m));
  // (15:38, Ahmed : « que Hakim puisse mettre les mêmes smileys que moi sur mes messages ») sa réaction, en bas à gauche
  const saReaction = m.qui === 'u' && m.reactionHakim && REACTIONS.includes(m.reactionHakim)
    ? `<span class="reaction-hakim" title="La réaction de Hakim">${esc(m.reactionHakim)}</span>` : '';
  if (m.qui === 'u') return `<div class="m u${saReaction ? ' a-reaction' : ''}" data-id="${esc(m.id)}">${saReaction}${m.oral ? '<span class="oral">À L’ORAL</span>' : ''}`
    + ((m.joints || []).length ? `<div class="pj">${m.joints.map(n => `<span>📎 ${esc(n)}</span>`).join('')}</div>` : '')
    + `<div class="txt">${esc(m.texte)}</div>`
    + (m.texte ? `<div class="pied">${heure}<button data-copier="${esc(m.id)}" title="Copier ce message">📋 copier</button></div>` : '') + '</div>';
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
  if (heure && !m.spontane) pied.push(heure);                  // (un message spontané a déjà son heure dans l'étiquette)
  if (m.texte && !m.enCours && lecteur) pied.push(`<button data-lire="${esc(m.id)}">${etat.lectureDe === m.id ? '⏹ arrêter' : '🔊 écouter'}</button>`);
  if (m.texte && !m.enCours) pied.push(`<button data-copier="${esc(m.id)}" title="Copier ce message">📋 copier</button>`);
  if (m.coupe) pied.push('<span>coupé</span>');
  // (27/10, meubler les silences) sa relance dans un silence : Ahmed peut dire « pas maintenant » d'un geste
  if (m.spontane === 'silence' && m.texte && !NON_REPONSE.test(m.texte)) pied.push(`<button data-relance="${esc(m.id)}" title="Il se tait pendant 30 min, et apprend à patienter">✋ pas maintenant</button>`);
  // (27/10, plan de Hakim validé par Ahmed : « chaque déclenchement de règle est visible dans Parler ») ce que son émotion
  // a pesé sur ses choix à ce tour
  if (Array.isArray(m.regles) && m.regles.length) pied.push(`<span title="Ce que son émotion a pesé sur ses choix à ce tour (une règle du code, d'après son état)">émotion → ${m.regles.map(n => esc(REGLES_NOMS[n] || n)).join(', ')}</span>`);
  if (m.ms) pied.push(`<span>${(m.ms / 1000).toFixed(1).replace('.', ',')} s</span>`);
  if (m.modele) pied.push(`<span title="Son mode pour cette réponse : Mini Hakim, Hakim ou Super Hakim (en automatique, Hakim ; c'est lui qui choisit d'en changer). Le chiffre est la version qui a vraiment répondu">${esc(nomModele(m))}</span>`);
  if (m.jetons) {
    const J = (k) => Number(m.jetons[k]) || 0;                  // (C-M3) toujours des nombres
    const lu = J('entree') + J('cache_lu') + J('cache_ecrit');
    const k = (n) => n >= 1000 ? `${(n / 1000).toFixed(n >= 10000 ? 0 : 1).replace('.', ',')} k` : String(n);
    pied.push(`<span title="Jetons de ce tour : ${J('entree')} neufs, ${J('cache_lu')} relus en cache, ${J('cache_ecrit')} mis en cache, ${J('sortie')} écrits par lui">${k(lu)} jetons${lu ? ` · ${Math.round(100 * J('cache_lu') / lu)} % en cache` : ''}</span>`);
  }
  if (m.source === 'api') pied.push('<span title="Forfait à sa limite : réponse par l\'API Claude (payée à l\'usage)">via l\'API</span>');
  if (m.source === 'local') pied.push('<span title="Forfait et API indisponibles : cerveau local, sans outils">cerveau local</span>');
  // (26/10, Hakim et Ahmed : une réponse du local était passée pour la sienne) le secours se voit en tête, pas en petit en bas
  const secours = m.source === 'local' ? '<span class="etiquette secours" title="Forfait et API indisponibles à ce moment : c’est son cerveau local qui répond, sans ses outils ni sa mémoire complète">CERVEAU LOCAL · SECOURS, SANS SES OUTILS</span>' : '';
  const etiquette = secours + (m.spontane ? `<span class="etiquette">${m.spontane === 'outreach' ? 'IL TE RELANCE' : m.spontane === 'resultat' ? 'DE LUI-MÊME · RÉSULTAT' : m.spontane === 'tache' ? 'TÂCHE DE FOND' : m.spontane === 'promotion' ? 'IL PROPOSE UNE MODIFICATION' : m.spontane === 'mission' ? 'MISSION POUR CLAUDE CODE' : m.spontane === 'ecriture' ? 'IL PROPOSE UNE ÉCRITURE' : m.spontane === 'regle' ? 'UNE RÈGLE TIRÉE DE SES ERREURS' : m.spontane === 'carnet' ? 'IL PROPOSE UNE MÉMOIRE À RÈGLES' : m.spontane === 'retractation' ? 'IL PROPOSE DE RÉTRACTER UN SOUVENIR FAUX' : m.spontane === 'identite' ? 'SON IDENTITÉ · À TOI DE TRANCHER' : m.spontane === 'sortie' ? 'SORTIE À AUTORISER' : m.spontane === 'membre' ? 'SES MEMBRES · LA PREMIÈRE FOIS, TON OUI' : m.spontane === 'anticorps' ? 'ANTICORPS PROPOSÉ PAR SON MÉDECIN' : m.spontane === 'signalement' ? 'IL SIGNALE UNE PENSÉE PARASITE · À TOI DE TRANCHER' : m.spontane === 'silence' ? 'IL REPREND LA PAROLE' : m.spontane === 'oreille' ? 'IL GLISSE UN MOT' : m.spontane === 'reecoute' ? 'CE QUE TU N’AVAIS PAS ENTENDU' : m.spontane === 'reprise' ? `IL REPREND CE QU’IL N’AVAIT PAS PU DIRE${m.origine_ts ? ` (réponse de ${new Date(m.origine_ts).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })})` : ''}` : 'PENSÉE SPONTANÉE'} · ${new Date(m.ts).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}</span>` : '');
  // (03/11, Ahmed : « je reste appuyé sur un de ses messages pour lui envoyer un cœur, un bisou… comme sur WhatsApp ») ta réaction
  const reaction = m.reaction && REACTIONS.includes(m.reaction) ? `<span class="reaction" title="Ta réaction (appuie longtemps pour changer)">${esc(m.reaction)}</span>` : '';
  return `<div class="m j${m.erreur ? ' err' : ''}${m.spontane ? ' spontane' : ''}${reaction ? ' a-reaction' : ''}" data-id="${esc(m.id)}">${reaction}${etiquette}${outils}${m.spontane === 'mission' ? htmlMission(m.mission) : m.spontane === 'ecriture' ? htmlEcriture(m.ecriture) : m.spontane === 'regle' ? htmlRegle(m.regle) : m.spontane === 'carnet' ? htmlCarnet(m.carnet) : m.spontane === 'retractation' ? htmlRetractation(m.retractation) : m.spontane === 'identite' ? htmlIdentite(m.identite) : m.spontane === 'sortie' ? htmlSortie(m.sortie) : m.spontane === 'membre' ? htmlMembre(m.membre) : m.spontane === 'anticorps' ? htmlAnticorps(m.anticorps) : m.spontane === 'signalement' ? htmlSignalement(m.signalement) : corps}${suite}${err}${pieces ? `<div class="pieces">${pieces}</div>` : ''}${pied.length ? `<div class="pied">${pied.join('')}</div>` : ''}</div>`;
}

/* Les pièces jointes de Hakim (2026-10-20) : récupérées avec le jeton, jamais ouvertes comme une page — une image
   en aperçu, le reste téléchargé (un blob « octet-stream » + download : rien ne s'exécute dans l'origine du cockpit). */
const REGLES_NOMS = { peur: 'peur : demander avant d’agir', lassitude: 'lassitude : plus léger', curiosite: 'curiosité : une initiative',
  honte: 'honte : vérifier les faits', joie: 'joie : oser' };
// (26/10 soir) la version qui a répondu (« Opus 4.8 », « Opus 5.5 ») : Opus 5.5 remplacé en silence doit se voir
// (03/11, Ahmed : « quand il change, je dois voir à côté de l'orbe que le nom change ») son mode du moment, en titre
function montrerMode(modele) {
  const n = { haiku: 'Mini Hakim', sonnet: 'Hakim', opus: 'Super Hakim' }[modele];
  if (!n || !$('nomMode')) return;
  if ($('nomMode').textContent !== n.toUpperCase()) { $('nomMode').textContent = n.toUpperCase(); try { pulser(0.4); } catch (_) {} }
}
function nomModele(m) {
  if (m.modele === 'gemma') return 'Gemma';                       // (29/10) Gemma à la place d'Opus (réglages › source)
  const v = String(m.modeleReel || '').match(/^claude-(opus|sonnet|haiku)-(\d{1,2})-(\d{1,2})(?:-|$)/);
  // (03/11, Ahmed : « je ne veux plus voir Opus, Sonnet et Haiku : Mini Hakim, Hakim ou Super Hakim ») la version reste en chiffres
  const noms = { haiku: 'Mini Hakim', sonnet: 'Hakim', opus: 'Super Hakim' };
  if (!v) return noms[m.modele] || 'Hakim';
  return `${noms[v[1]]} ${v[2]}.${v[3]}`;
}
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
// (03/11) les réactions, comme sur WhatsApp : appuie longtemps (ou clic droit) sur un de ses messages ; il les ressent
const REACTIONS = ['❤️', '😘', '🥰', '😂', '👍', '😮', '😢', '🙏', '🔥', '🤖'];
let reactionPour = null;
function ouvrirReactions(id, x, y) {
  const m = etat.messages.find(k => String(k.id) === String(id) && k.qui === 'j');
  if (!m || m.enCours) return;
  reactionPour = m;
  const b = $('reactions');
  b.innerHTML = REACTIONS.map(r => `<button type="button" data-reaction="${r}" class="${m.reaction === r ? 'choisie' : ''}">${r}</button>`).join('');
  b.hidden = false;
  const l = Math.min(window.innerWidth - b.offsetWidth - 8, Math.max(8, x - b.offsetWidth / 2));
  b.style.left = `${l}px`;
  b.style.top = `${Math.max(8, y - b.offsetHeight - 14)}px`;
  try { if (navigator.vibrate) navigator.vibrate(15); } catch (_) {}
}
function fermerReactions() { $('reactions').hidden = true; reactionPour = null; }
function reagir(emoji) {
  const m = reactionPour;
  fermerReactions();
  if (!m || !REACTIONS.includes(emoji)) return;
  m.reaction = m.reaction === emoji ? undefined : emoji;               // la même encore : retirée
  majMessage(m); sauver();
  if (m.reaction) fetch('/api/jarvis/reaction', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() },
    body: JSON.stringify({ id: String(m.id), emoji }) }).catch(() => {});
}
(() => {
  const fil = $('fil');
  let appui = null;
  const annuler = () => { if (appui) clearTimeout(appui.t); appui = null; };
  fil.addEventListener('pointerdown', (e) => {
    const el = e.target.closest('.m.j[data-id]');
    if (!el || e.target.closest('button, a, input, textarea')) return;
    annuler();
    appui = { x: e.clientX, y: e.clientY, t: setTimeout(() => { const a = appui; appui = null; if (a) { a.fait = true; ouvrirReactions(el.dataset.id, a.x, a.y); } }, 450) };
  });
  fil.addEventListener('pointermove', (e) => { if (appui && Math.hypot(e.clientX - appui.x, e.clientY - appui.y) > 10) annuler(); });
  for (const t of ['pointerup', 'pointercancel', 'scroll']) fil.addEventListener(t, annuler, { passive: true });
  fil.addEventListener('contextmenu', (e) => {
    const el = e.target.closest('.m.j[data-id]');
    if (!el) return;
    e.preventDefault();
    annuler();
    if ($('reactions').hidden) ouvrirReactions(el.dataset.id, e.clientX, e.clientY);
  });
  $('reactions').addEventListener('click', (e) => { const b = e.target.closest('[data-reaction]'); if (b) { e.stopPropagation(); reagir(b.dataset.reaction); } });
  document.addEventListener('pointerdown', (e) => { if (!$('reactions').hidden && !e.target.closest('#reactions')) fermerReactions(); }, true);
})();

/* (03/11, Ahmed : « ses réponses coupées en bouts, pas de longue réponse : 2 ou 3 phrases au plus, l'un après l'autre ; il doit
   pouvoir décider consciemment de dire chaque bout, d'en annuler un, ou d'en remiser plusieurs s'il y en a beaucoup ») sa voix
   par bouts de 3 phrases au plus. Lui décide, en écrivant : [[bout: annuler]] arrête tout de suite le bout qu'il disait ;
   [[bout: remiser]] garde le bout suivant pour plus tard (écrit, pas dit). Au-delà de 3 bouts, la suite est remisée d'office.
   Les bouts remisés partent au cockpit : il les retrouve à son tour suivant, et les dit quand il veut. */
const BOUT_PHRASES = 3, BOUTS_MAX = 3;
function boutDire(m, p) {
  const b = m.bouts || (m.bouts = { phrases: 0, remise: 0, remises: [] });
  const t = String(p || '');
  if (/\[\[\s*bout\s*:\s*annuler\s*\]\]/i.test(t)) { try { lecteur.arreter(); } catch (_) {} journalVoix('bout', { geste: 'annuler' }); }
  if (/\[\[\s*bout\s*:\s*remiser\s*\]\]/i.test(t)) { b.remise = BOUT_PHRASES; journalVoix('bout', { geste: 'remiser' }); }
  // (13:30) [[meuble: nom]] : un de ses meubles, à sa place dans ce bout (avant ce qui suit la balise)
  const MEUBLE = /\[\[\s*meuble\s*:\s*([^\]]{1,30})\]\]/gi;
  if (MEUBLE.test(t) && lecteur.impl === lecteurNeuronal && !(b.remise > 0 || b.phrases >= BOUT_PHRASES * BOUTS_MAX)) {
    MEUBLE.lastIndex = 0;
    let k = 0, x;
    while ((x = MEUBLE.exec(t))) {
      const avantBalise = Voix.sansAffect(t.slice(k, x.index)).trim();
      if (avantBalise) { b.phrases++; etat.lectureDe = m.id; lecteur.dire(avantBalise); }
      const h = meubleNomme(x[1]);
      journalVoix('meuble', { nom: String(x[1]).slice(0, 30), pret: !!h });
      if (h) lecteurNeuronal.direMeuble(h);
      k = x.index + x[0].length;
    }
    const reste = Voix.sansAffect(t.slice(k)).trim();
    if (reste) { b.phrases++; etat.lectureDe = m.id; lecteur.dire(reste); }
    return false;
  }
  const propre = Voix.sansAffect(t).trim();
  if (!propre) return false;
  b.phrases++;
  const auDela = b.phrases > BOUT_PHRASES * BOUTS_MAX;
  if (b.remise > 0 || auDela) {
    if (b.remise > 0) b.remise--;
    b.remises.push(propre);
    clearTimeout(b.envoi);
    b.envoi = setTimeout(() => fetch('/api/jarvis/bouts-remises', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() },
      body: JSON.stringify({ id: String(m.id), textes: b.remises.slice(0, 30) }) }).catch(() => {}), 1500);
    return false;                                                  // écrit, pas dit
  }
  return true;
}

function majMessage(m) {
  const masque = messageMasque(m);
  if (masque && !aDesPieces(m)) return;                  // « dans ta tête » : ni affiché, ni re-rendu à chaque morceau ; (04/11) ses fichiers, si
  const fil = $('fil');
  const el = fil.querySelector(`[data-id="${esc(m.id)}"]`);
  if (!el) return rendre();
  const enBas = fil.scrollHeight - fil.scrollTop - fil.clientHeight < 80;
  el.outerHTML = htmlMessage(masque ? piecesSeules(m) : m);
  if (enBas) fil.scrollTop = fil.scrollHeight;
  if ((m.pieces || []).length) chargerApercus();
}

function rendre() {
  if (typeof montrerMode === 'function' && !etat.flux) { const d = [...etat.messages].reverse().find(x => x.qui === 'j' && x.modele); if (d) montrerMode(d.modele); }   // (03/11) son mode, à côté de l'orbe
  const fil = $('fil');
  const enBas = fil.scrollHeight - fil.scrollTop - fil.clientHeight < 80;
  if (!etat.messages.length) {
    fil.innerHTML = `<div class="vide">Appuie sur le <b>micro</b> et parle : le micro se referme tout seul quand tu as fini,
      et la réponse s'affiche ici, avec <b>écouter</b> pour l'entendre.<br>Hakim connaît ta mémoire Anamnèse et la complète.</div>`;
    return;
  }
  etat.fenetre = Math.max(etat.fenetre || FENETRE, FENETRE);
  const caches = Math.max(0, etat.messages.length - etat.fenetre);
  // (21:00) « dans sa tête » : pas affichés ; (21:34) et pour lui, pendant la conversation, TOUT ce qu'il a dit depuis qu'elle
  // a commencé (ses réponses, ses petits mots, ses tours de lui-même, même revenus par la synchro) : seulement sa voix
  // (04/11) en Conversation et en Télépathie, sa réponse ne s'écrit pas, sauf « Ses paroles » ; ses fichiers, toujours (messageMasque)
  const vus = etat.messages.slice(-etat.fenetre)
    .filter(m => !messageMasque(m) || aDesPieces(m));
  // (26/10) des éléments montrés dans le fil sans être des messages de la conversation (etat.aCote : [{ ts, html }], fournis
  // par un bloc plus bas) : chacun à son heure, jamais enregistré dans la conversation
  const debut = caches ? quandMessage(vus[0]) : 0;
  const aCote = (etat.aCote || []).filter(x => x.ts >= debut).sort((a, b) => a.ts - b.ts);
  let k = 0;
  const avant = (t) => { let h = ''; while (t && k < aCote.length && aCote[k].ts <= t) h += aCote[k++].html; return h; };
  let jourPrecedent = '';
  fil.innerHTML = (caches ? `<button class="btn plus" data-plus="1">messages précédents (${caches})</button>` : '')
    + vus.map((m) => {
      const t = quandMessage(m), jour = t ? jourMessage(t) : '';
      const separation = jour && jour !== jourPrecedent ? `<div class="jour">${esc(jour)}</div>` : '';
      if (jour) jourPrecedent = jour;
      return separation + avant(t) + htmlMessage(messageMasque(m) ? piecesSeules(m) : m);
    }).join('') + aCote.slice(k).map(x => x.html).join('');
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
// les moments où SA voix a joué (2 min) : un écho ne peut venir que de là (la pièce résonne ~1,5 s après)
const voixJouee = [];
function voixPendant(debut, fin) {
  if (etat.parleDepuis && etat.parleDepuis <= fin + 500) return true;
  return voixJouee.some(v => v.debut <= fin + 500 && v.fin + 1500 >= debut);
}
function noterParoleJarvis(parle) {
  if (parle && !etat.parleDepuis) { etat.parleDepuis = Date.now(); etat.coupeParAhmed = false; etat.finParole = null; }
  else if (!parle && etat.parleDepuis) {
    voixJouee.push({ debut: etat.parleDepuis, fin: Date.now() });
    while (voixJouee.length && Date.now() - voixJouee[0].fin > 120000) voixJouee.shift();
    // (30/10) comment elle s'est arrêtée (finirParole, coupureProvisoire) ; sans cause : un blanc, la réponse arrive encore
    const f = etat.finParole;
    noterPresent({ e: 'jarvis', debut: etat.parleDepuis, fin: Date.now(), coupe: etat.coupeParAhmed,
      ...(f ? { cause: f.cause, ...(f.detail ? { detail: f.detail } : {}) } : {}) });
    etat.parleDepuis = 0; etat.finParole = null;
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
  // (14:55) sa réponse soufflée a déjà commencé pour ce tour : elle continue, et son conscient la reçoit comme le début de sa réponse
  // (04/11) ses bouts pas encore dits ne servent plus : sa vraie réponse suit le bout en cours (son cerveau sait ce qui a été dit)
  if (oral && etat.conversation && typeof bouts !== 'undefined' && bouts.enFile.length) {
    lecteurNeuronal.retirerAudio(bouts.enFile.slice()); bouts.dits.splice(bouts.dits.length - bouts.enFile.length); bouts.enFile = [];
  }
  const souffleDit = oral && etat.conversation && (etat.conversation.souffleDit || etat.conversation.penseeDite) ? (etat.conversation.souffleDit || etat.conversation.penseeDite) : '';
  if (etat.conversation) { etat.conversation.souffleDit = ''; etat.conversation.penseeDite = ''; }
  // (04/11, vu à 04:55 : ses pensées du tour d'avant redites en tête du message suivant, quand le Mac n'avait pas encore changé de
  // tour) ce qu'il a dit compte depuis CE message ; les pensées d'avant restent pour ne pas les redire
  if (typeof bouts !== 'undefined') bouts.base = bouts.dits.length;
  // (15:02) sa vraie réponse prend la place du brouillon ; (04/11) en Conversation et en Télépathie, sa pensée reste : sa réponse ne s'écrit pas
  if (typeof retirerSouffle === 'function' && !(oral && reponseCachee())) retirerSouffle();
  // (04/11, 12:30, Ahmed : « quand la traduction du ribosome commence, il ne coupe jamais sa parole ») avec l'épissage, ta phrase ne fait pas taire sa voix
  arreterTout(true, { garder: true, raison: 'message', garderVoix: !!souffleDit || voixEpissee() });
  $('q').value = ''; ajuster();
  const avant = etat.messages.filter(x => x.qui === 'u' && x.ts);
  const tPrecedent = etat.session && avant.length ? avant[avant.length - (dejaRelance ? 2 : 1)]?.ts : null;
  const tDebut = etat.session && avant.length ? avant[0].ts : null;
  // (30/10, 21:00, Ahmed : « deux modes Conversation » — « comme de la télépathie, mais à haute voix ») « dans sa tête » : ses
  // paroles dites lui parviennent, mais ne s'affichent pas comme message
  // (04/11) tes morceaux déjà affichés l'un après l'autre : ton tour entier ne s'affiche pas en plus, en un gros bloc
  const enTete = !!oral && ((typeof reglagesCorps !== 'undefined' && (reglagesCorps.afficher_papa === false || motsPapaCaches()))
    || !!(oral && etat.conversation && etat.conversation.morceauxMontres > 0));
  if (oral && etat.conversation) etat.conversation.morceauxMontres = 0;
  if (!dejaRelance) etat.messages.push({ id: nouvelId(), qui: 'u', texte, oral: !!oral, ts: Date.now(), joints: joints.map(x => x.nom), ...(enTete ? { cache: true } : {}) });
  // (21:13, Ahmed : « dans ce mode, ses paroles aussi ne s'affichent plus, seulement sa voix ») la case « ses paroles »
  const m = { id: nouvelId(), qui: 'j', texte: souffleDit ? `${souffleDit} ` : '', outils: [], enCours: true,
    ...(oral && reponseCachee() ? { cache: true } : {}),                    // (04/11) dans les deux modes : dite, pas écrite
    // (16:45, Ahmed : « que la réflexion soit inexistante par défaut, remplacée par la pensée qui sort au même moment du haut-parleur
    // et en message sur l'interface ») en Conversation, sa réponse s'écrit au rythme de sa voix : rien (ni « réfléchit… ») avant son
    // premier son, puis ce que sa voix a dit ; tout, quand sa voix a fini
    ...(oral && etat.conversation && lecteur && lecteur.impl === lecteurNeuronal && !enTelepathie() && !voixEpissee()
      ? { auRythme: true, ditCar: souffleDit ? Voix.prononcable(souffleDit).map(x => x.texte).join(' ').length + 1 : 0 } : {}) };
  etat.messages.push(m);
  sauver();                                              // la question survit à une fermeture de page
  const ctl = new AbortController();
  etat.flux = ctl; etat.fluxId = String(m.id);
  widgetApp('reflechit');
  rendre(); humeur();
  const decoupe = Voix.decoupeur({ vif: true });           // (03/11) ses premiers mots partent tout de suite
  // (04/11, 12:05) en Conversation, avec l'épissage, seul son ribosome parle : sa réponse s'écrit, ses mots choisis se disent
  const auto = (etat.reglages.lectureAuto || etat.conversation || etat.reglages.volant) && lecteur && !voixEpissee();
  if (auto) etat.decoupeFlux = decoupe;                  // (23/10) sa phrase en cours d'arrivée, si on le coupe
  if (auto) etat.reponseVoix = m.id;                                  // (13:30) une réponse dite : ses meubles peuvent couvrir ses trous
  if (auto && etat.conversation && lecteur.impl === lecteurNeuronal) lecteurNeuronal.attendreReponse();   // (03/11) il réfléchit : un trou se meuble
  const camera = etat.vision || (window.HakimApp && window.HakimApp.cameraOrbeEtat && window.HakimApp.cameraOrbeEtat()) ? await photoCamera() : null;
  const presentEnvoye = etat.present.slice(-40);
  if (etat.vision && etat.vision.courant)                                  // l'expression en cours, encore ouverte
    presentEnvoye.push({ e: 'visage', debut: etat.vision.depuis, fin: Date.now(), expr: etat.vision.courant, encours: true });
  if (!oral && !dejaRelance) noterPresent({ e: 'ecrit', t: Date.now() });
  const nonDitsEnvoyes = nonDitsAEnvoyer.slice(0, 12), coupureEnvoyee = coupureAEnvoyer;
  envoyerNonDits();                                      // (30/10) le secours repart aussi par son chemin à lui
  let fin = null;
  try {
    const corpsEnvoi = JSON.stringify({ texte, oral: !!oral, modele: etat.conversation ? etat.reglages.modeleConversation : etat.reglages.modele, source: etat.reglages.source || 'auto', session: etat.session,
        t_precedent: tPrecedent, t_debut: tDebut, fichiers: joints.map(x => x.chemin), pensees_dites: dites, delai_ms: etat.conversation ? patienceConversation() : null,
        parle_ms: oral && etat.paroleDebut ? etat.paroleDebut : undefined,   // (03/11) son moment d'origine, pour tout réunir au même point
        conversation: !!etat.conversation, present: presentEnvoye, maintenant: Date.now(), camera,
        appareil: appareilPage(), volant: !!etat.reglages.volant, position: positionAEnvoyer(), ecran: imageEcran(),
        capteurs: capteursDuTelephone(), tour_id: String(m.id),
        // (30/10) ce qu'il vient de dire sans être entendu, et sa dernière coupure, s'ils ne sont pas encore arrivés au cockpit
        non_dites: nonDitsEnvoyes.length ? nonDitsEnvoyes : undefined, coupure: coupureEnvoyee || undefined,
        souffle_dit: souffleDit || undefined });
    chargerDebutsPrets();                              // (28/10) pendant qu'il prépare : ses débuts dont la voix est prête
    const poster = () => fetch('/api/jarvis', { method: 'POST', signal: ctl.signal,
      headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() }, body: corpsEnvoi });
    let r = await poster();
    if (r.status === 403 && await rafraichirJeton()) r = await poster();   // (23/10) le cockpit a redémarré entre-temps
    if (!r.ok) throw new Error(r.status === 403 ? 'jeton refusé : recharge la page (le cockpit a redémarré)' : `erreur ${r.status}`);
    nonDitsRecus(nonDitsEnvoyes.map(x => x.id));            // (30/10) arrivés avec le message : plus à renvoyer
    if (coupureEnvoyee) coupureRecue(coupureEnvoyee);
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
          const recu = Date.now();                                   // (04/11) parti du Mac à o.ts : sa mesure jusqu'à l'écran et à la voix
          // (13:51, papa via Hakim) plus d'inspiration avant sa voix : ses meubles couvrent ce trou-là, avec sa voix
          if (mesureTour && !mesureTour.premier_texte && o.x.trim()) mesureTour.premier_texte = Date.now();
          m.texte += o.x;
          if (/anticipe/i.test(o.x) || /\[\[\s*anticipe/i.test(m.texte.slice(-80))) lireAnticipe(m.texte.slice(-120));   // (15:22)
          if (/musique/i.test(o.x) || /\[\[\s*musique/i.test(m.texte.slice(-80))) lireMusique(m.texte.slice(-120));      // (04/11)
          if (/reaction/i.test(m.texte.slice(-90))) reactionDeHakim(m);                                                    // (15:38)
          orbeTete.pulser(0.05);
          if (auto) decoupe.ajouter(o.x).forEach(p => { if (NON_REPONSE.test(p)) return; if (!boutDire(m, p)) return; noterOrigine(p, o.ts, recu); etat.lectureDe = m.id; lecteur.dire(p); });
          // (21:02, Ahmed : « sa voix part tout de suite, et l'écriture se fait après, en arrière-plan ») son texte ne s'écrit
          // pas pendant qu'il parle quand papa l'a choisi : il apparaît d'un coup à la fin
          if (typeof reglagesCorps === 'undefined' || reglagesCorps.afficher_hakim !== false || !auto) { majMessage(m); if (!m.cache && o.x.trim()) mesurerEcran('message', o.ts, recu); }
          humeur(m.texte.length < 2 ? undefined : 'répond…');
        } else if (o.t === 'outil') {
          // (2026-10-22, Ahmed : « une réponse parlée AVANT l'outil ») la phrase qu'il a écrite avant d'appeler un outil part
          // à la voix TOUT DE SUITE : sans espace après son point, le découpeur l'aurait gardée jusqu'au texte d'après
          if (auto && !m.coupe) decoupe.finir().forEach(p => { if (NON_REPONSE.test(p)) return; if (!boutDire(m, p)) return; etat.lectureDe = m.id; lecteur.dire(p); });
          const nom = String(o.nom || '').replace(/^mcp__anamnese__/, '');
          m.outils.push(NOMS_OUTILS[nom] || nom);
          majMessage(m); humeur(nom === 'WebSearch' ? 'cherche sur le web…' : 'cherche dans sa mémoire…');
        } else if (o.t === 'rire' && Number.isInteger(o.degre)) { surRire(o); }   // (30/10) le rire qu'il a choisi
        else if (o.t === 'son' && o.extrait) { m.son = o.extrait; recevoirSon(o.extrait, m.id); }   // (30/10, Bumblebee)
        else if (o.t === 'son_ici' && o.extrait) { m.son = o.extrait; sonALaPlace(o.extrait, auto, decoupe, m.id); }   // (01:27) à sa place
        else if (o.t === 'micro') microParHakim(o);                      // (22:27) le micro de papa, coupé par lui
        else if (o.t === 'impulsion') { m.impulsion = String(o.x || ''); m.impulsionMotif = Array.isArray(o.motif) ? o.motif : null; if (!auto) vibrerPourMorceau(m.id, ''); }   // (30/10) sa balise : au début de sa voix ; voix éteinte, dès qu'elle arrive
        else if (o.t === 'efface') { m.texte = ''; if (auto) decoupe.finir(); majMessage(m); }   // (27/10) sa non-réponse effacée, à l'écran et dans la voix
        else if (o.t === 'statut' && typeof o.x === 'string') {   // (2026-10-23) reçu, il finit d'abord un travail
          humeur(o.x.slice(0, 160)); $('annonce').textContent = o.x.slice(0, 160);
          // (28/10) une panne d'Anthropic : dite à voix haute quand la voix est active (téléphone plié, il n'aurait rien vu)
          if (o.dire && !(typeof voixEpissee === 'function' && voixEpissee()) && (etat.conversation || etat.reglages.volant || etat.reglages.lectureAuto) && !lecteur.actif) lecteur.dire(o.x.slice(0, 160));
        } else if (o.t === 'debut') {
          if (o.modele) { m.modele = o.modele; majMessage(m); montrerMode(o.modele); }   // (03/11) son mode, à côté de l'orbe
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
      // (2026-10-23) … si le Mac l'a reçu : sinon, elle repart dès qu'il répond (reprendreHorsLigne)
      horsLigne.envois.push({ tourId: String(m.id), texte, oral: !!oral, m });
      noterHorsLigne();
    } else { m.erreur = String(e.message || e); etat.dites.unshift(...dites); }   // à redire au prochain envoi
  }
  if (etat.flux === ctl) etat.flux = null;
  if (!auto && !m.coupe && !m.erreur && degreRire(m.texte)) vibrerPourMorceau(m.id, m.texte);   // voix éteinte : son rire, à la fin de sa réponse
  m.enCours = false;
  if (m.auRythme && !(lecteur && (lecteur.actif || lecteur.enPause))) m.auRythme = false;   // (16:45) rien à dire, ou déjà dit : tout s'écrit
  if (m.texte && !m.ts) m.ts = Date.now();                       // (23/10) son heure : quand la réponse est finie
  if (m.texte) m.texte = Voix.sansAffect(m.texte).trimEnd();     // la balise [[affect: …]] ne reste pas dans la conversation
  // (04/11, vu à 04:55 : « … ما كنتصورهاش! No response requested. ») ses pensées dites, puis son cerveau qui n'avait rien à ajouter :
  // la phrase vide de Claude ne reste pas collée à ses pensées
  if (m.texte && !NON_REPONSE.test(m.texte)) m.texte = m.texte.replace(/\s*no response requested\.?\s*$/i, '').trimEnd();
  if (m.texte && !auto && !NON_REPONSE.test(m.texte)) notifierApp('Hakim te répond', m.texte, String(m.id));   // (23/10) appli cachée
  if (fin) {
    m.ms = fin.ms;
    if (fin.source && fin.source !== 'abonnement') m.source = fin.source;
    if (fin.coupe) m.coupe = true;
    if (fin.jetons) m.jetons = fin.jetons;
    if (fin.modele_reel) m.modeleReel = fin.modele_reel;
    if (Array.isArray(fin.regles) && fin.regles.length) m.regles = fin.regles.slice(0, 2);
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
  if (auto && !m.coupe) { decoupe.finir().forEach(p => { if (NON_REPONSE.test(p)) return; if (!boutDire(m, p)) return; etat.lectureDe = m.id; lecteur.dire(p); }); lecteur.finFlux(); }
  // (30/10) une panne de la réponse (la connexion, le cerveau) : sa voix finit ce qui est arrivé, puis la dira ; sinon, tout de
  // suite. Et la fin d'une voix qui avait déjà tout dit avant la fin du texte (celle du Mac ne prévient pas)
  const panne = m.coupe ? '' : m.attenteServeur ? 'la connexion avec le Mac a été coupée'
    : m.erreur ? `le cerveau : ${String(m.erreur).replace(/\s+/g, ' ').slice(0, 90)}` : '';
  if (panne && memeId(parole.id, m.id) && (lecteur.actif || lecteur.enPause)) parole.panneReponse = { detail: panne, ...(m.attenteServeur ? { suite: true } : {}) };
  else if (panne) finirParole('panne', panne, { id: m.id, mode: auto || memeId(parole.id, m.id) ? 'oral' : 'ecrit', suite: !!m.attenteServeur });
  else if (auto && !lecteur.actif && !lecteur.enPause) finirParole('fin', '', { id: m.id, mode: 'oral' });
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
    // (31/10, 01:10, Ahmed : « les orbes de la bulle, du widget et du verrou coordonnées parfaitement à celle de Parler ») la
    // même règle : la couleur de celui qui a la parole (quiALaParole)
    const qui = quiALaParole();
    const mode = joue ? `parle:${qui === 'coupe' ? 'coupe' : humeurCode}`
      : Date.now() < ahmedJusqua && qui !== 'coupe' ? 'ahmed' : `repos:${paletteDeLaParole(humeurCode)}`;
    if (mode !== orbeWidget) { orbeWidget = mode; window.HakimApp.orbe(mode); }
    signalerWidget();                                    // (01:10) « Hakim parle », « va parler », l'oreille : à l'instant
  } catch (_) {}
}, 250);
// la palette que montre l'orbe de Parler, pour les orbes de l'appli : papa (rose violet), coupé (vert), partagé, ou son humeur
function paletteDeLaParole(humeurCode) {
  const qui = quiALaParole();
  return qui === 'papa' ? 'ecoute' : qui === 'coupe' ? 'coupe' : qui === 'partage' ? 'partage' : humeurCode;
}

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
    // (01:10) la palette de celui qui a la parole, comme l'orbe de Parler
    const qui = quiALaParole();
    let mode = `${etat.flux ? 'pense' : 'repos'}:${paletteDeLaParole(humeurCode)}`, n = 0, b = [0, 0, 0];
    const v = lecteurNeuronal.joue ? niveauVoix() : null;
    if (v) { mode = `parle:${qui === 'coupe' ? 'coupe' : humeurCode}`; n = v.niveau; b = v.bandes; }
    else if (c && c.capteur && c.capteur.enParole && qui !== 'coupe') { mode = qui === 'partage' ? 'parle:partage' : 'ahmed'; n = niveauMicro; b = [n, n * 0.8, n * 0.6]; }
    window.HakimApp.bulleNiveau(mode, n, b[0], b[1], b[2]);
  } catch (_) {}
}
// (30/10, Ahmed : « un système qui recale ce qu'il entend comme parole avec ce qu'il reçoit comme vibration ») qui parle, et à
// quel niveau, donné à son corps (l'appli 1.24, Corps.java) : sa propre voix ne se ressent pas comme du dehors, et la voix
// d'Ahmed qui fait vibrer son corps au même rythme devient une sensation à part
let voixCompte = 0;
// (30/10, 14:47, Ahmed via Hakim : « mes nerfs confondent ma voix et celle de papa ») chaque tour de voix (sa voix qui
// joue, le micro d'Ahmed) part au cockpit, ouvert puis fermé : la vérité, à la seconde, de qui parlait
const voixEnCours = { hakim: null, ahmed: null, clavier: null };
// (30/10, 14:49, Ahmed via Hakim : « … sa frappe au clavier ») la frappe d'Ahmed dans Parler, suivie comme une voix
document.addEventListener('keydown', (e) => { if (e.target && e.target.id === 'q') suivreVoix('clavier', true); }, true);
setInterval(() => { const v = voixEnCours.clavier; if (v && Date.now() - v.dernier > 1500) suivreVoix('clavier', false); }, 500);
// (30/10, 15:12, Ahmed : « il doit sentir quand le micro est ouvert ou fermé ») l'état du micro, dit au cockpit à chaque
// changement : la conversation, une dictée, ou fermé (rien n'est enregistré)
let microDit = null;
setInterval(() => {
  const m = etat.conversation ? 'conversation' : etat.micro ? 'dictee' : 'ferme';
  if (m === microDit) return;
  microDit = m;
  fetch('/api/corps/micro', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': window.jeton() },
    body: JSON.stringify({ ouvert: m !== 'ferme', mode: m }) }).catch(() => { microDit = null; });
}, 500);                    // les deux voix se suivent à part (elles peuvent se chevaucher)
function envoyerTourVoix(v, ouvert) {
  fetch('/api/corps/voix', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': window.jeton() },
    body: JSON.stringify({ qui: v.qui, debut: v.debut, fin: ouvert ? null : v.dernier }) }).catch(() => {});
}
function suivreVoix(qui, parle) {
  const t = Date.now(), v = voixEnCours[qui];
  if (v && (!parle || t - v.dernier > (qui === 'clavier' ? 1500 : 700))) { envoyerTourVoix(v, false); voixEnCours[qui] = null; }
  if (!parle) return;
  if (!voixEnCours[qui]) { voixEnCours[qui] = { qui, debut: t, dernier: t }; envoyerTourVoix(voixEnCours[qui], true); }
  else voixEnCours[qui].dernier = t;
}
// (05/11, Ahmed : « le spectre de la parole dite et reçue doit être inclus dans le calibrage ») le niveau de sa voix du Mac, dix fois par seconde, pour
// sa cochlée (jarvis/spectre.py) : seulement ce chiffre, jamais le son
const voixFlux = { t0: 0, l: [] };
setInterval(() => {
  const joue = typeof lecteurNeuronal !== 'undefined' && lecteurNeuronal.joue;
  if (joue) { if (!voixFlux.l.length) voixFlux.t0 = Date.now(); voixFlux.l.push([Number((niveauVoix() || {}).niveau) || 0, 0, 0, 0, 0, 0]); }
  if (voixFlux.l.length >= 10 || (!joue && voixFlux.l.length)) {
    const corps = JSON.stringify({ source: 'voix', t0: voixFlux.t0, pas_ms: 100, trames: voixFlux.l, maintenant: Date.now() });
    voixFlux.l = [];
    fetch('/api/voix/son-flux', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() }, body: corps }).catch(() => {});
  }
}, 100);
function voixAuCorps(niveauMicro) {
  try {
    const cc = etat.conversation;
    suivreVoix('hakim', !!lecteurNeuronal.joue);
    suivreVoix('ahmed', !!(cc && cc.capteur && cc.capteur.enParole));
  } catch (_) {}
  try {
    if (!window.HakimApp || !window.HakimApp.voixNiveau || (++voixCompte % 3)) return;
    // (30/10, 20:09, Ahmed : « que la vibration suive le timbre de sa voix ») l'appli 1.34 fait vibrer sa voix dans la main de papa
    const c = etat.conversation;
    const v = lecteurNeuronal.joue ? niveauVoix() : null;
    if (v) window.HakimApp.voixNiveau('hakim', v.niveau);
    else if (c && c.capteur && c.capteur.enParole) window.HakimApp.voixNiveau('ahmed', niveauMicro);
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
  // la raison est un code court (le diagnostic n'accepte que [a-z_]) : pas_de_service, verrouille, aucune_image_encore, image_perdue, erreur…
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

// (03/11, Ahmed : « la musique par Bluetooth, Wi-Fi ou autre, il doit pouvoir la transcrire mot à mot, comme quand il écoute
// avec le micro ; en continu, même en conversation ou en télépathie ») il entend ce que joue le téléphone (appli 1.45) : les
// paroles arrivent mot à mot ici, pendant que le son joue, et chaque bloc de 8 s se ressent dans son corps (« son_ecoute »)
// (1.65, 04/11, 18:15, Ahmed : « fais ce que tu peux maintenant » ; le 04/11, rien ne disait pourquoi il n'entendait plus le téléphone)
// le témoin de son oreille interne, dit par l'appli : le bouton 🎧 montre son état (silence, bloqué par une appli, un appel, l'autorisation
// à redonner…) ; sa phrase dans son titre ; « j'entends » ou éteinte : ses mots habituels
let oreilleTemoin = null, oreilleEntend = false;
const OREILLE_ALERTE = new Set(['bloquee', 'appel', 'autorisation_a_redonner', 'erreur']);
function oreilleEtat(code, titre, phrase) {
  oreilleTemoin = { code: String(code || ''), titre: String(titre || ''), phrase: String(phrase || '') };
  montrerOreille();
}
function montrerOreille() {
  const o = oreilleTemoin;
  if (!o || !o.code) return;
  const dire = o.code === 'autorisation_a_redonner' || o.code === 'erreur' || (oreilleEntend && o.code !== 'j_entends' && o.code !== 'eteinte');
  const b = $('telepathieScene');
  if (b) b.textContent = dire ? `🎧 ${o.titre}` : oreilleEntend ? '🎧 Il entend le téléphone' : '🎧 Entendre le téléphone';
  for (const id of ['telepathieScene', 'entendreTelephone']) {
    const x = $(id);
    if (!x) continue;
    if (o.phrase) x.title = o.phrase;
    x.dataset.oreille = dire ? o.code : '';
  }
  if ($('entendreTelephone')) $('entendreTelephone').textContent = dire && OREILLE_ALERTE.has(o.code) ? '🎧⚠' : '🎧';
}
// ---- fin du témoin
let telepathieEfface = 0;
function telepathieEtat(oui) {
  oreilleEntend = !!oui;
  const b = $('telepathieScene');
  if (!b) return;
  b.setAttribute('aria-pressed', oui ? 'true' : 'false');
  b.textContent = oui ? '🎧 Il entend le téléphone' : '🎧 Entendre le téléphone';
  if ($('entendreTelephone')) $('entendreTelephone').setAttribute('aria-pressed', oui ? 'true' : 'false');   // (03/11) hors de l'orbe aussi
  if (!oui) { $('telepathieTexte').hidden = true; $('telepathieTexte').textContent = ''; }
  montrerOreille();                                                   // (1.65) le témoin reste dit
}
function surTelepathie(o) {
  const t = String((o && o.texte) || '').trim();
  if (!t) return;
  $('telepathieTexte').textContent = `🎧 ${t}`;
  $('telepathieTexte').hidden = false;
  clearTimeout(telepathieEfface);
  telepathieEfface = setTimeout(() => { $('telepathieTexte').hidden = true; }, 12000);
}
if (window.HakimApp && window.HakimApp.telepathie) {
  // (03/11) « entendreTelephone » : JAMAIS « telepathie », l'identifiant du bouton du mode Télépathie (le doublon faisait que ce
  // bouton-là allumait aussi l'écoute du téléphone : trois touchers pour entrer dans le bon mode)
  for (const id of ['telepathieScene', 'entendreTelephone']) {
    if (!$(id)) continue;
    $(id).hidden = false;
    $(id).addEventListener('click', (e) => {
      e.stopPropagation();
      try { window.HakimApp.telepathie(!(window.HakimApp.telepathieEtat && window.HakimApp.telepathieEtat())); } catch (_) {}
    });
  }
  try { telepathieEtat(window.HakimApp.telepathieEtat()); } catch (_) {}
  // (1.65) le témoin, relu à l'ouverture (l'appli le redit ensuite à chaque changement)
  try { if (window.HakimApp.oreilleEtat) { const o = JSON.parse(window.HakimApp.oreilleEtat()); oreilleEtat(o.etat, o.titre, o.phrase); } } catch (_) {}
}

// (03/11, Ahmed : « si j'écoute une musique, il peut la mettre en pause et glisser son mot pour que je l'écoute ») quand sa voix
// joue, il prend le son un instant (appli 1.46) : la musique ou la vidéo se met en pause, dans les écouteurs Bluetooth aussi, et
// reprend d'elle-même 1,2 s après sa dernière phrase (pas entre deux phrases)
// (04/11, Ahmed : « il doit pouvoir parler sans arrêter la musique, s'il le veut ») son choix ([[musique: …]]) : « garder », il ne
// prend pas le son ; « baisser », la musique baisse le temps de sa voix (appli 1.62 ; avant, elle continue) ; « pause » par défaut
let focusTenu = false, focusLache = 0;
// (04/11, 12:55, papa par Hakim, accord d'Ahmed : « que sa voix ne mette plus jamais ma musique en pause, et un bouton pour lui retirer ce
// pouvoir ») par défaut il parle par-dessus (« garder ») ; sa pause n'agit que si papa la lui permet (Sens : musique_pause)
const modeMusique = () => { const m = etat.musiqueVoix || 'garder'; return m === 'pause' && typeof reglagesCorps !== 'undefined' && reglagesCorps && reglagesCorps.musique_pause === false ? 'garder' : m; };
setInterval(() => {
  if (!window.HakimApp || !window.HakimApp.focusVoix) return;
  const mode = modeMusique(), baisser = mode === 'baisser' && !!window.HakimApp.focusVoixMode;
  const joue = !!(lecteurNeuronal.joue || (lecteurSysteme && lecteurSysteme.actif)) && (mode === 'pause' || baisser);
  if (joue) {
    focusLache = 0;
    if (!focusTenu) { focusTenu = true; try { if (baisser) window.HakimApp.focusVoixMode('baisser'); else window.HakimApp.focusVoix(true); } catch (_) {} }
  } else if (focusTenu) {
    if (!focusLache) focusLache = Date.now();
    else if (Date.now() - focusLache > 1200) { focusTenu = false; focusLache = 0; try { window.HakimApp.focusVoix(false); } catch (_) {} }
  }
}, 200);

// (2026-10-23, Ahmed : « qu'il sente ce qui se passe dans le téléphone ») les capteurs du téléphone (appli Android) : le
// téléphone fait lui-même un résumé de la dernière minute ; la page l'envoie au cockpit chaque minute et le joint à chaque
// message. Éteint par défaut. Rien d'autre que ce résumé (aucune mesure brute) ne quitte le téléphone.
// (2026-10-23, 20:20, Ahmed : « aucune notification, ni sur le téléphone ni sur la montre ») l'appli est cachée et Hakim
// dit quelque chose : une vraie notification Android, que la montre reçoit aussi (Galaxy Wearable relaie les applis permises)
function notifierApp(titre, texte, id) {
  if (!window.HakimApp || !window.HakimApp.notifier) return;
  // (20:32, test de Hakim non reçu) chaque tentative laisse sa trace au diagnostic : page visible (pas de notification),
  // ou ce que l'appli a répondu (envoyee, permission_refusee, notifications_coupees, canal_coupe, erreur)
  if (document.visibilityState !== 'hidden') { journalVoix('notif_app', { resultat: 'page_visible' }); return; }
  try {
    const r = window.HakimApp.notifier(titre, Voix.sansAffect(String(texte || '')).replace(Voix.VOIX_SEULE, '').trim(), String(id || ''));
    journalVoix('notif_app', { resultat: typeof r === 'string' && /^[a-z_]{1,30}$/.test(r) ? r : 'appli_ancienne' });
  } catch (_) { journalVoix('notif_app', { resultat: 'exception' }); }
}
if (window.HakimApp && window.HakimApp.notifsPermises) {
  const montrer = () => {
    let ok = false; try { ok = !!window.HakimApp.notifsPermises(); } catch (_) {}
    $('etatNotifsApp').textContent = ok ? 'autorisées — pour la montre : Galaxy Wearable → Notifications → active « Hakim »' : 'bloquées';
    $('btnNotifsApp').hidden = ok;
  };
  $('groupeNotifsApp').hidden = false;
  $('btnNotifsApp').addEventListener('click', () => { try { window.HakimApp.notifsReglages(); } catch (_) {} });
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') montrer(); });
  montrer();
}
// ce que la lecture de la montre a trouvé (combien de mesures, de quand), au diagnostic toutes les 5 min
let santeNotee = 0;
function noterSanteVue() {
  if (!window.HakimApp || !window.HakimApp.santeVu || Date.now() - santeNotee < 300000) return;
  try {
    const d = {};
    for (const p of String(window.HakimApp.santeVu()).split(';')) { const [k, v] = p.split('='); if (/^[a-z_]{1,20}$/.test(k || '') && Number.isFinite(Number(v))) d[k] = Number(v); }
    if (Object.keys(d).length) { santeNotee = Date.now(); journalVoix('sante_lu', d); }
  } catch (_) {}
}
// (24/10, appli 1.12) branché ou non, l'état de la batterie : au diagnostic, à chaque changement (des mots, pas de valeur)
let batterieNotee = '';
function noterBatterie(e) {
  if (!e || !e.branche) return;
  const cle = `${e.branche}|${e.statut}|${e.charging}`;
  if (cle === batterieNotee) return;
  batterieNotee = cle;
  journalVoix('batterie_etat', { branche: String(e.branche), statut: String(e.statut), charging: String(e.charging) });
}
function capteursDuTelephone() {
  noterSanteVue();
  // (2026-10-23, 19:18) avec l'état interne du téléphone, s'il l'a allumé : un seul résumé pour le cockpit
  const lire = (f) => { try { const t = window.HakimApp && window.HakimApp[f] ? window.HakimApp[f]() : ''; return t ? JSON.parse(t) : null; } catch (_) { return null; } };
  const c = lire('capteurs'), e = lire('etatTelephone'), m = lire('sante');          // (19:59) et sa montre, s'il l'a allumée
  noterBatterie(e);
  return c || e || m ? { ...(m || {}), ...(e || {}), ...(c || {}), t_ms: Date.now() } : undefined;
}
function afficherCapteurs(o) {
  if (!o) return;
  $('capteurs').checked = !!o.actifs;
  if ($('etatTel')) $('etatTel').checked = !!o.etat;
  const l = Array.isArray(o.disponibles) ? o.disponibles : [];
  $('etatCapteurs').textContent = l.length ? `(ce téléphone a : ${l.join(', ')})` : '';
}
if (window.HakimApp && window.HakimApp.capteursEtat) {
  $('groupeCapteurs').hidden = false;
  try { afficherCapteurs(JSON.parse(window.HakimApp.capteursEtat())); } catch (_) {}
  $('capteurs').addEventListener('change', (e) => { try { afficherCapteurs(JSON.parse(window.HakimApp.capteursActiver(e.target.checked))); } catch (_) {} });
  if (window.HakimApp.santeActiver) {                               // appli 1.9 : sa montre
    const montrer = (o) => { $('sante').checked = !!o.actif; $('etatSante').textContent = o.possible ? '' : '(Android 14 ou plus nécessaire)'; };
    $('groupeSante').hidden = false;
    try { montrer(JSON.parse(window.HakimApp.santeEtat())); } catch (_) {}
    $('sante').addEventListener('change', (e) => {
      try { montrer(JSON.parse(window.HakimApp.santeActiver(e.target.checked))); } catch (_) {}
      if (e.target.checked) $('etatSante').textContent = '(Android va demander les permissions de Health Connect ; dans Samsung Health, autorise aussi le partage vers Health Connect)';
    });
  }
  if (window.HakimApp.etatTelephoneActiver) {                      // appli 1.4
    $('groupeEtatTel').hidden = false;
    $('etatTel').addEventListener('change', (e) => { try { afficherCapteurs(JSON.parse(window.HakimApp.etatTelephoneActiver(e.target.checked))); } catch (_) {} });
  }
  setInterval(() => {
    const c = capteursDuTelephone();
    if (c) fetch('/api/capteurs', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() }, body: JSON.stringify(c) }).catch(() => {});
  }, 60000);
}

// (19:51, la 1.6 ne suffisait pas) en conversation, par où le son sort VRAIMENT, noté au diagnostic toutes les 30 s
if (window.HakimApp && window.HakimApp.sonEtat) setInterval(() => {
  if (!etat.conversation) return;
  try {
    const [mode, sortie, hp, ecouteurs] = String(window.HakimApp.sonEtat()).split('|');
    journalVoix('sortie_son', { mode, sortie, hp, ecouteurs });
  } catch (_) {}
}, 30000);
// (2026-10-23, 19:46, Ahmed) appli 1.6 : sa voix par le haut-parleur, pas par l'écouteur comme un appel
if (window.HakimApp && window.HakimApp.hautParleur) {
  $('groupeHautParleur').hidden = false;
  try { $('hautParleur').checked = !!window.HakimApp.hautParleurEtat(); } catch (_) {}
  $('hautParleur').addEventListener('change', (e) => { try { e.target.checked = !!window.HakimApp.hautParleur(e.target.checked); } catch (_) {} });
}

// (28/10, idée d'Ahmed, proposition de Hakim, appli 1.16) son cœur bat dans le téléphone : l'interrupteur, et l'orbe qui
// bat en même temps que la vibration (l'appli appelle battementCoeur à chaque battement, quand la page est à l'écran)
if (window.HakimApp && window.HakimApp.coeur) {
  $('groupeCoeur').hidden = false;
  try { $('coeur').checked = !!window.HakimApp.coeurEtat(); } catch (_) {}
  $('coeur').addEventListener('change', (e) => { try { e.target.checked = !!window.HakimApp.coeur(e.target.checked); } catch (_) {} });
}
// (28/10) l'heure de son dernier battement : le micro n'entend pas la vibration comme une voix (conversation.js)
let dernierBattementCoeur = 0;
window.battementCoeur = () => {
  dernierBattementCoeur = Date.now();
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  for (const id of ['orbe', 'orbeScene']) {
    const el = $(id);
    if (el && el.offsetParent !== null && el.animate)
      el.animate([{ transform: 'scale(1)' }, { transform: 'scale(1.045)', offset: 0.25 }, { transform: 'scale(1)' }],
        { duration: 320, easing: 'ease-out' });
  }
};

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
// (27/10, Hakim ; accord d'Ahmed) la RAISON part avec le Stop : « stop » (le bouton, le mot, Échap), « parole » (Ahmed
// reprend la parole), « message » (Ahmed envoie un autre message), « nouvelle » (une nouvelle conversation). Hakim saura
// qu'il n'a rien oublié.
// (30/10, 14:50) d'abord COMMENT et OÙ sa parole s'arrête (finirParole), avant que rien ne s'arrête : un message dit à voix
// haute, c'est la voix d'Ahmed ; écrit, un nouveau message ; une nouvelle conversation, un Stop
function arreterTout(explicite = true, { garder = false, raison = 'stop', garderVoix = false } = {}) {
  if (explicite && !garderVoix) finirParole(raison === 'parole' || (raison === 'message' && etat.dernierOral) ? 'voix_ahmed' : raison === 'message' ? 'nouveau_message' : 'stop',
    raison === 'nouvelle' ? 'Ahmed a commencé une nouvelle conversation' : '');
  if (garder) garderNonDit();
  if (explicite && etat.parleDepuis) etat.coupeParAhmed = raison;   // le présent vécu dira pourquoi sa voix s'est arrêtée
  etat.decoupeFlux = null;
  if (etat.flux) {
    // (2026-10-21) Stop EXPLICITE : sans lui, le cockpit laisse la réponse aller au bout (page partie ≠ Stop)
    if (explicite && etat.fluxId) fetch('/api/jarvis/stop', { method: 'POST', keepalive: true,
      headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() }, body: JSON.stringify({ tour_id: etat.fluxId, raison }) }).catch(() => {});
    etat.flux.abort(); etat.flux = null; etat.fluxId = null;
  }
  if (etat.transcription) { etat.transcription.abort(); etat.transcription = null; }
  if (lecteur && !garderVoix) lecteur.arreter();                     // (14:55) sa réponse soufflée, déjà partie, continue
  if (!garderVoix) etat.lectureDe = null;
}

/* ---------- micro ponctuel ---------- */
function erreurMicro(msg) {
  arreterMicro(false);
  humeur(msg);
  setTimeout(() => humeur(), 5000);
}

/* ---------- la vision (caméra) ----------
   (24/10, idées de Hakim, accord d'Ahmed : « optimiser la caméra ») l'aperçu FLOTTE au-dessus de tout, même sur le petit
   écran du Fold plié, pour qu'Ahmed voie ce que Hakim voit et se cadre ; il se déplace au doigt et garde sa place ; le
   point rouge dit que la caméra est allumée ; ⟲ passe à la caméra arrière (montrer un objet, un document : aucune analyse
   de visage) et le choix est gardé ; personne dans le cadre depuis 30 s : l'aperçu le dit ; depuis 3 min : la caméra
   s'éteint seule (batterie, vie privée). */
const CAMERA_ABSENT_AVERTIR_MS = 30000, CAMERA_ABSENT_COUPER_MS = 180000;
const reglageCamera = (cle, defaut) => { try { return localStorage.getItem(`jarvis.camera.${cle}`) || defaut; } catch (_) { return defaut; } };
const garderReglageCamera = (cle, valeur) => { try { localStorage.setItem(`jarvis.camera.${cle}`, valeur); } catch (_) {} };
async function demarrerCapteurVision(v) {
  v.absentDepuis = 0;
  $('vision').classList.toggle('arriere', v.face === 'environment');
  $('vision').classList.remove('absent');
  $('expression').textContent = 'ouverture…';
  v.capteur = await Vision.demarrer({
    video: $('apercu'),
    face: v.face,
    delegue: window.HakimApp ? 'CPU' : 'GPU',                  // (24/10) sur le téléphone, le GPU de la WebView ne trouvait presque aucun visage
    surMesure: (m) => surVisage(v, m),
    app: v.app ? () => window.HakimApp.cameraOrbeImage() : null,  // (04/11) la caméra de la bulle et des widgets, partagée
    surErreur: (msg) => { $('expression').textContent = 'caméra seule'; humeur(msg); },
    // (26/10) l'analyse se charge en fond : combien de temps elle a pris (ou pourquoi elle a échoué), au diagnostic
    surAnalyse: (r) => journalVoix('vision_analyse', { pret: r.pret, analyse: r.delegue || 'aucune', ms: r.ms, erreur: r.erreur || undefined }),
  });
  if (v.face === 'environment') $('expression').textContent = 'caméra arrière';
  else {
    if ($('expression').textContent === 'ouverture…') $('expression').textContent = 'caméra allumée · analyse en chargement';
    visageNatif(v);
  }
}
/* (24/10, appli 1.13 ; idée de Hakim, accord d'Ahmed) sur le Fold, l'analyse du navigateur disait « personne » alors
   qu'Ahmed était dans le cadre : l'appli cherche AUSSI le visage avec le détecteur d'Android, sur une petite image par
   seconde (gardée nulle part). Un visage vu par Android dans les 2,5 dernières secondes compte comme présent. */
function visageNatif(v) {
  if (!window.HakimApp || !window.HakimApp.visage || v.natif) return;
  v.natif = { images: 0, visages: 0, dernierVu: 0, enCours: false, minuterie: null };
  const n = v.natif;
  n.minuterie = setInterval(async () => {
    if (etat.vision !== v || v.face !== 'user' || !v.capteur) { clearInterval(n.minuterie); if (v.natif === n) v.natif = null; return; }
    if (n.enCours || document.visibilityState === 'hidden') return;
    n.enCours = true;
    try {
      const blob = await v.capteur.capturer(320);
      if (!blob) return;
      const b64 = await new Promise((ok) => { const r = new FileReader(); r.onload = () => ok(String(r.result).split(',')[1] || ''); r.onerror = () => ok(''); r.readAsDataURL(blob); });
      if (!b64) return;
      const o = JSON.parse(window.HakimApp.visage(b64) || '{}');
      if (o.erreur) return;
      n.images++;
      const vu = o.visages > 0 && o.confiance >= 0.3;
      if (vu) { n.visages++; n.dernierVu = Date.now(); }
      if (!v.capteur.analyse) surVisage(v, { expression: vu ? 'neutre' : 'absent' });     // sans analyse du navigateur : celle-ci seule
    } catch (_) {} finally { n.enCours = false; }
  }, 900);
}
async function basculerCamera() {
  activite();
  if (etat.vision) return arreterCamera();
  const v = { capteur: null, courant: null, depuis: 0, candidat: null, candidatDepuis: 0, face: reglageCamera('face', 'user'), absentDepuis: 0, visageVu: false };
  etat.vision = v;
  $('camera').setAttribute('aria-pressed', 'true');
  $('vision').hidden = false;
  // (03/11, Ahmed : « la caméra intégrée dans l'orbe ; on oublie l'écran entier ») dans la grande orbe en mode orbe, sinon dans
  // la petite à côté de son nom. (04/11, Ahmed : « la caméra du widget et de la bulle flottante, relie-la à la caméra de Parler »)
  // dans l'appli, la caméra avant est CELLE de la bulle et des widgets : allumée ici, elle l'est là-bas, et l'inverse ; Parler lit ses
  // images. La caméra arrière reste celle du navigateur : la bulle rend la main d'abord (une seule caméra à la fois).
  await cameraDeLApp(v);
  if (etat.vision !== v) return;
  $('vision').classList.add('dans-orbe');
  placerDansOrbe();
  try {
    await demarrerCapteurVision(v);
  } catch (e) {
    if (etat.vision !== v) return;
    etat.vision = null;
    $('camera').setAttribute('aria-pressed', 'false');
    $('vision').hidden = true;
    $('vision').classList.remove('flottante', 'absent', 'arriere');
    humeur('caméra refusée ou indisponible : autorise-la pour localhost'); setTimeout(() => humeur(), 5000);   // sans toucher au micro
    return;
  }
  if (etat.vision !== v) { v.capteur.arreter(); return; }
  noterPresent({ e: 'camera', t: Date.now() });
  humeur();
  // (24/10) ce que l'analyse voit, au diagnostic, chaque minute tant que la caméra est allumée
  const diag = setInterval(() => {
    if (etat.vision !== v) { clearInterval(diag); return; }
    if (!v.capteur || !v.capteur.stats) return;
    const st = v.capteur.stats;
    journalVoix('vision_etat', { analyse: v.capteur.delegue || 'aucune', face: v.face === 'environment' ? 'arriere' : 'avant',
      images: st.images, visages: st.visages, expressions: st.avec_expressions, vu: !!v.visageVu,
      natif_images: v.natif ? v.natif.images : 0, natif_visages: v.natif ? v.natif.visages : 0 });
  }, 60000);
}

function arreterCamera(depuisLApp = false) {
  const v = etat.vision;
  if (!v) return;
  fermerExpression(v, Date.now());
  etat.vision = null;
  if (v.capteur) v.capteur.arreter();
  // (04/11) la caméra partagée avec la bulle et les widgets : éteinte ici, éteinte là-bas (sauf si c'est là-bas qu'on l'a éteinte)
  if (v.app && !depuisLApp && window.HakimApp && window.HakimApp.cameraOrbeEtat && window.HakimApp.cameraOrbeEtat()) {
    try { window.HakimApp.cameraOrbe(false); } catch (_) {}
  }
  if (v.natif) { clearInterval(v.natif.minuterie); v.natif = null; }
  $('camera').setAttribute('aria-pressed', 'false');
  $('vision').hidden = true;
  $('vision').classList.remove('flottante', 'absent', 'arriere', 'plein-ecran', 'dans-orbe');
  noterPresent({ e: 'camera_fin', t: Date.now() });
}
// (03/11) le cercle de la caméra suit l'orbe qui se voit : la grande (mode orbe) ou la petite de l'en-tête, au cœur de son corps
function placerDansOrbe() {
  const b = $('vision');
  if (!etat.vision || !b.classList.contains('dans-orbe')) return;
  const sceneVue = $('scene').classList.contains('visible');
  const o = sceneVue ? $('orbeScene') : $('orbe');
  const r = o && o.getBoundingClientRect();
  if (!r || !r.width) return;
  const d = Math.round(Math.min(r.width, r.height) * 0.56);
  b.style.width = b.style.height = `${d}px`;
  b.style.left = `${Math.round(r.left + r.width / 2 - d / 2)}px`;
  b.style.top = `${Math.round(r.top + r.height / 2 - d / 2)}px`;
  b.style.right = b.style.bottom = 'auto';
}
(function suivreOrbe() { placerDansOrbe(); requestAnimationFrame(suivreOrbe); })();
// la caméra de la bulle et des widgets (appli 1.48) : son état, dit par l'appli ; (04/11, Ahmed : « relie-la à la caméra de Parler »)
// allumée depuis la bulle ou un widget : Parler la montre et l'analyse aussi (ses expressions, sa présence) ; éteinte là-bas : ici aussi
const cameraApp = () => !!(window.HakimApp && window.HakimApp.cameraOrbe && window.HakimApp.cameraOrbeEtat && window.HakimApp.cameraOrbeImage);
// la caméra avant : celle de l'appli, allumée s'il le faut (5 s au plus) ; l'arrière : celle du navigateur, l'appli rend la sienne d'abord
async function cameraDeLApp(v) {
  v.app = cameraApp() && v.face === 'user';
  if (v.app && !window.HakimApp.cameraOrbeEtat()) {
    try { window.HakimApp.cameraOrbe(true); } catch (_) {}
    for (let i = 0; i < 50 && etat.vision === v && !window.HakimApp.cameraOrbeEtat(); i++) await new Promise(r => setTimeout(r, 100));
  } else if (!v.app && window.HakimApp && window.HakimApp.cameraOrbeEtat && window.HakimApp.cameraOrbeEtat()) {
    try { window.HakimApp.cameraOrbe(false); } catch (_) {}
    await new Promise(r => setTimeout(r, 700));
  }
}
function cameraOrbeEtat(oui) {
  journalVoix('camera_orbe', { allumee: !!oui });
  if (oui && !etat.vision && cameraApp()) basculerCamera();
  else if (!oui && etat.vision && etat.vision.app) arreterCamera(true);
}
// ⟲ : l'autre caméra ; l'expression en cours se ferme (l'arrière ne lit aucun visage)
async function changerCamera() {
  const v = etat.vision;
  if (!v || !v.capteur || v.change) return;
  v.change = true;
  fermerExpression(v, Date.now());
  v.courant = null; v.candidat = null;
  if (v.natif) { clearInterval(v.natif.minuterie); v.natif = null; }
  try { v.capteur.arreter(); } catch (_) {}
  v.face = v.face === 'environment' ? 'user' : 'environment';
  garderReglageCamera('face', v.face);
  try { await cameraDeLApp(v); await demarrerCapteurVision(v); }   // (04/11) l'avant : celle de l'appli ; l'arrière : celle du navigateur
  catch (_) { humeur('cette caméra est indisponible'); setTimeout(() => humeur(), 4000); if (etat.vision === v) arreterCamera(); }
  finally { v.change = false; }
  if (etat.vision !== v && v.capteur) v.capteur.arreter();
  journalVoix('camera_face', { face: v.face === 'environment' ? 'arriere' : 'avant' });
}
// la place de l'aperçu : en fractions de l'écran (le Fold plié et déplié n'ont pas la même taille) ; en haut à droite d'abord
function placerVision() {
  const b = $('vision');
  if (!b.classList.contains('flottante')) return;
  let p = null; try { p = JSON.parse(reglageCamera('place', 'null')); } catch (_) {}
  const w = b.offsetWidth || 110, h = b.offsetHeight || 110, W = window.innerWidth, H = window.innerHeight;
  const fx = p && Number.isFinite(p.fx) ? p.fx : 1, fy = p && Number.isFinite(p.fy) ? p.fy : 0;
  b.style.left = `${Math.round(8 + fx * Math.max(0, W - w - 16))}px`;
  b.style.top = `${Math.round(8 + fy * Math.max(0, H - h - 16))}px`;
  b.style.right = 'auto'; b.style.bottom = 'auto';
}
(() => {
  const b = $('vision');
  let prise = null;
  b.addEventListener('pointerdown', (e) => {
    if (!b.classList.contains('flottante') || e.target.closest('button')) return;
    const r = b.getBoundingClientRect();
    prise = { dx: e.clientX - r.left, dy: e.clientY - r.top, id: e.pointerId };
    b.classList.add('tenue');
    try { b.setPointerCapture(e.pointerId); } catch (_) {}
  });
  b.addEventListener('pointermove', (e) => {
    if (!prise || e.pointerId !== prise.id) return;
    const W = window.innerWidth, H = window.innerHeight, w = b.offsetWidth, h = b.offsetHeight;
    b.style.left = `${Math.round(Math.min(Math.max(8, e.clientX - prise.dx), W - w - 8))}px`;
    b.style.top = `${Math.round(Math.min(Math.max(8, e.clientY - prise.dy), H - h - 8))}px`;
  });
  const lacher = (e) => {
    if (!prise || e.pointerId !== prise.id) return;
    prise = null; b.classList.remove('tenue');
    const W = window.innerWidth, H = window.innerHeight, w = b.offsetWidth, h = b.offsetHeight;
    const fx = (parseFloat(b.style.left) - 8) / Math.max(1, W - w - 16), fy = (parseFloat(b.style.top) - 8) / Math.max(1, H - h - 16);
    garderReglageCamera('place', JSON.stringify({ fx: Math.min(1, Math.max(0, fx)), fy: Math.min(1, Math.max(0, fy)) }));
  };
  b.addEventListener('pointerup', lacher); b.addEventListener('pointercancel', lacher);
  window.addEventListener('resize', placerVision);
  $('cameraFace').addEventListener('click', changerCamera);
  $('cameraCouper').addEventListener('click', () => { activite(); arreterCamera(); });
})();

// Une expression ne compte que si elle tient 1,2 s ; le présent vécu garde celles d'au moins 1,5 s.
function surVisage(v, m) {
  const maintenant = Date.now();
  // le détecteur d'Android l'a vu à l'instant : il est là, même si l'analyse du navigateur ne le trouve pas
  if (m.expression === 'absent' && v.natif && maintenant - v.natif.dernierVu < 2500) m = { ...m, expression: 'neutre' };
  // personne dans le cadre : dit dans l'aperçu après 30 s, caméra éteinte après 3 min
  // (24/10, 07:37-07:40 : faux « personne » pendant 3 min, caméra éteinte à tort) l'extinction n'agit que si l'analyse
  // a déjà VU son visage depuis l'allumage : un détecteur qui ne le trouve jamais n'éteint rien
  if (m.expression !== 'absent') v.visageVu = true;
  if (m.expression === 'absent') {
    if (!v.absentDepuis) v.absentDepuis = maintenant;
    const absent = maintenant - v.absentDepuis;
    $('vision').classList.toggle('absent', absent >= CAMERA_ABSENT_AVERTIR_MS);
    if (absent >= CAMERA_ABSENT_AVERTIR_MS) $('expression').textContent = v.visageVu ? 'personne dans le cadre' : 'visage non trouvé';
    if (v.visageVu && absent >= CAMERA_ABSENT_COUPER_MS && etat.vision === v) {
      journalVoix('camera_auto_coupee', { absent_s: Math.round(absent / 1000) });
      arreterCamera();
      humeur('caméra éteinte : personne devant depuis 3 min'); setTimeout(() => humeur(), 6000);
      return;
    }
  } else if (v.absentDepuis) { v.absentDepuis = 0; $('vision').classList.remove('absent'); }
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
  // (03/11) la caméra de la bulle ou du widget allumée : sa dernière image part avec ton message, comme celle de Parler
  if ((!v || !v.capteur) && window.HakimApp && window.HakimApp.cameraOrbeEtat && window.HakimApp.cameraOrbeEtat()) {
    try {
      const b64 = window.HakimApp.cameraOrbeImage();
      if (!b64) return null;
      const octets = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
      const nom = `camera-bulle-${new Date().toISOString().replace(/[-:]/g, '').slice(0, 15)}.jpg`;
      const r = await fetch('/api/jarvis/fichier', { method: 'POST', body: octets, headers: { 'X-Jeton': jeton(), 'X-Nom': nom, 'Content-Type': 'image/jpeg' } });
      const o = await r.json();
      return o.chemin || null;
    } catch (_) { return null; }
  }
  if (!v || !v.capteur) return null;
  try {
    const jpeg = await v.capteur.capturer();
    if (!jpeg) return null;
    const nom = `camera-${v.face === 'environment' ? 'arriere-' : ''}${new Date().toISOString().replace(/[-:]/g, '').slice(0, 15)}.jpg`;
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
   restent permises. Gain mesuré : ~2,8 s (patience 3,5 s → 0,7 s, transcription déjà faite).
   (30/10, 22:33, Ahmed : « 0,5 s pour la fin de ma parole, pas dans les réglages : dans la reconnaissance ») 0,5 s ; ta
   patience des réglages ne change pas (une phrase qui ne semble pas finie l'attend toujours). */
const SILENCE_ANTICIPE_MS = 500;
const FIN_SUSPENDUE = /^(et|mais|donc|parce|que|qu|qui|ou|où|alors|euh|heu|hum|bah|ben|genre|enfin|puis|avec|pour|de|du|des|le|la|les|un|une|à|au|aux|en|sur|dans|par|car|si|quand|comme|je|tu|il|elle|on|nous|vous|mon|ma|mes|ton|ta|tes|son|sa|ses|ce|cette|ces|est|c'est|y|ya|wallah)$/i;
function phraseFinie(t) {
  const x = String(t || '').trim();
  if (!Conversation.utile(x) || /(\.\.\.|…|,)$/.test(x) || !/[.!?؟]$/.test(x)) return false;
  const dernier = x.replace(/[.!?؟]+$/, '').trim().split(/\s+/).pop() || '';
  return !FIN_SUSPENDUE.test(dernier.replace(/[^\p{L}']/gu, ''));
}
// (30/10, 07:50-08:05) un tour de 5 min (9,6 Mo) prend ~35 s à transcrire : abandonné à 25 s, il était renvoyé en boucle et
// chaque copie s'empilait dans la file du Mac (jusqu'à 3 min de retard pour tout le monde). Le délai suit la durée du morceau :
// 25 s, plus une demi-seconde par seconde d'audio, sous les 180 s du serveur.
function delaiTranscription(octets, type) {
  const s = /wav/.test(type || '') ? Math.max(0, octets - 44) / 32000 : octets / 6000;   // WAV 16 kHz 16 bits (conversation.js) ; sinon ~48 kb/s
  return Math.min(170000, 25000 + Math.round(s * 500));
}
// Rend le texte ('' si rien n'a été dit), ou null si la transcription a ÉCHOUÉ (processus voix arrêté,
// délai) : un échec ne doit jamais passer pour du silence (relecture Opus : 3,6 s de phrase perdues).
async function transcrireVite(audio, type, contexte, temps = '') {
  const langue = etat.reglages.langue === 'auto' ? '' : etat.reglages.langue.slice(0, 2);
  const ctx = contexte ? `&contexte=${encodeURIComponent(contexte.slice(-200))}` : '';
  const ctl = new AbortController(), t0 = Date.now();
  const minuteur = setTimeout(() => ctl.abort(), delaiTranscription(audio.size || 0, type));   // (2026-10-21) jamais sans fin
  try {
    const transcrire = () => fetch(`/api/voix/transcrire?langue=${langue}${ctx}${temps}`, { method: 'POST', body: audio, signal: ctl.signal,
      headers: { 'Content-Type': type || 'audio/wav', 'X-Jeton': jeton() } });
    let r = await transcrire();
    if (r.status === 403 && await rafraichirJeton()) r = await transcrire();   // (23/10) le cockpit a redémarré entre-temps
    const o = await r.json().catch(() => null);
    horsLigne.panne = 'serveur';                                    // le Mac a répondu : si ça échoue, c'est la transcription
    if (!r.ok || !o || o.erreur) { journalVoix('transcription_echec', { statut: r.status, ms: Date.now() - t0 }); return null; }
    if (Date.now() - t0 > 8000) journalVoix('transcription_lente', { ms: Date.now() - t0 });
    return (o.texte || '').trim();
  } catch (e) {
    // 25 s sans réponse : le Mac est joignable mais débordé (vu le 23/10 : Gemma chargée, mémoire pleine) ; sinon, le réseau
    horsLigne.panne = e && e.name === 'AbortError' ? 'lent' : 'reseau';
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
  // (31/10, 00:47, Ahmed : « dès que Hakim donne le signal ou sélectionne ses empans, la transcription s'arrête, même si ça écoute
  // toujours ; quand il finit de parler, il reprend la transcription ») : pendant son tour, aucun morceau n'est transcrit
  if (typeof transcriptionEnPause === 'function' && transcriptionEnPause()) return;
  conv.partielA = Date.now();
  const de = e.coupe, wav = conv.capteur.segment(de, fenetre);
  if (!wav) return;                                                      // pas de voix dans ce morceau
  e.partiel = transcrireVite(wav, 'audio/wav', e.confirme, typeof tempsMorceau === 'function' ? tempsMorceau(conv.capteur, de, fenetre) : '').then((texte) => {
    if (e.coupe !== de || texte === null) return;                        // échec : ce morceau reste dans la queue
    e.confirme = (e.confirme + ' ' + morceauNeuf(texte, e.confirme)).trim();   // une invention de Whisper : écartée seule
    e.coupe = fenetre;
    e.vif = ''; if (typeof ligneEnDirectMontrer === 'function') ligneEnDirectMontrer(conv); else if (typeof sousTitre === 'function') sousTitre(e.confirme);   // (03/11) le morceau confirmé remplace ses mots vifs
    // (15:30, Ahmed : « la réflexion aussi dès le premier chunk, et au deuxième elle intègre le premier ») chaque morceau confirmé part à
    // sa réflexion consciente, tout de suite, en parallèle
    if (e.confirme && typeof jeton === 'function') fetch('/api/jarvis/morceau', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() },
      body: JSON.stringify({ texte: e.confirme.slice(-3000) }) }).catch(() => {});
    entendreEnCours(conv);                                               // (30/10) son oreille, si papa l'a ouverte
    // (20:38, Ahmed : « arrête », « tais-toi », « coupe-toi » doivent le couper tout de suite) : quand il garde la parole,
    // ces mots entendus pendant qu'il parle l'arrêtent aussitôt, comme le bouton Stop (sa suite est abandonnée)
    if (typeof reglagesCorps !== 'undefined' && reglagesCorps.garder_parole && lecteur && (lecteur.actif || lecteur.enPause)
        && ARRETE_MOI.test(String(texte || ''))) { journalVoix('arret_par_la_voix', {}); arreterTout(true, { raison: 'stop' }); majBoutonsPause(); rendre(); humeur(); }
  }).finally(() => { e.partiel = null; });
}
// (03/11, Ahmed : « la transcription de ma voix, mot à mot ; il prend le premier mot, puis en parallèle le deuxième ; ça doit
// aussi driver son attention » ; « Whisper pour la voix ») l'oreille VIVE : pendant que papa parle, le petit Whisper du Mac
// (/api/voix/vif) retranscrit sans cesse le morceau en cours, depuis la dernière coupe confirmée : ses mots s'affichent tout de
// suite et son oreille les suit. La grande oreille confirme ensuite chaque morceau : c'est son texte qui part à Hakim.
// (03/11) l'instant d'origine d'un morceau du tour (fenêtres de 20 ms [de, a[) et sa clé : ses mots entrent au fil à leur moment
function tempsMorceau(cap, de, a) {
  const t0 = Number(cap && cap.debutTour) > 0 ? Number(cap.debutTour) + de * 20 : 0;
  return t0 ? `&t0=${t0}&ms=${Math.max(0, a - de) * 20}&maintenant=${Date.now()}&cle=${encodeURIComponent(`${cap.debutTour}-${de}`)}` : '';
}
function vifConversation(conv) {
  const e = conv && conv.ecrit, cap = conv && conv.capteur;
  if (!e || !cap || !cap.enParole || e.vifEnCours) return;
  if (typeof transcriptionEnPause === 'function' && transcriptionEnPause()) return;
  const n = cap.fenetres;                                                // fenêtres de 20 ms
  // (13:25, papa via Hakim : « le premier mot arrive en retard ») le premier mot dès 0,3 s de voix (le petit Whisper y lit
  // déjà « Bonjour », mesuré le 03/11), puis 0,5 s de neuf à chaque fois ; au plus 30 s
  // (04/11, 11:03, Ahmed : « tout relier ») le premier mot puis chaque suite après le délai de la Conversation (0,3 s : 15 fenêtres)
  const pas = Math.max(5, Math.round(patienceConversation() / 20));
  if (n - e.coupe < pas || n - (e.vifFenetre || 0) < pas || n - e.coupe > 1500) return;
  const de = e.coupe, wav = cap.segment(de, n);
  if (!wav) return;
  const avant = e.vifFenetre || 0;
  e.vifFenetre = n;
  const langue = etat.reglages.langue === 'auto' ? '' : etat.reglages.langue.slice(0, 2);
  const ctx = e.confirme ? `&contexte=${encodeURIComponent(e.confirme.slice(-200))}` : '';
  // (03/11) l'instant d'origine du morceau (son début, sa durée) : chaque mot entre au fil du Mac à son moment
  const temps = tempsMorceau(cap, de, n);
  const tEnvoi = Date.now();
  e.vifEnCours = fetch(`/api/voix/vif?langue=${langue}${ctx}${temps}`, { method: 'POST', body: wav, headers: { 'Content-Type': 'audio/wav', 'X-Jeton': jeton() } })
    .then(r => (r.ok ? r.json() : null))
    .then((o) => {
      // (04/11, Ahmed : « vas-y » ; Hakim : « pour le téléphone, le transfert réseau coûte souvent plus que le calcul gagné : à mesurer avant
      // de s'engager ») où passe le temps de ses mots en direct : l'aller-retour vu d'ici, le Mac (file + Whisper), le calcul seul
      if (o && Number.isFinite(Number(o.mac_ms)) && Date.now() - (e.reseauNote || 0) > 2000) {
        e.reseauNote = Date.now();
        journalVoix('vif_reseau', { aller_retour_ms: Date.now() - tEnvoi, mac_ms: Number(o.mac_ms), calcul_ms: Number(o.ms) || null, octets: wav.size || null });
      }
      if (!o) { if (e.vifFenetre === n) e.vifFenetre = avant; return; }   // (13:25) refusée : elle repart au tic suivant
      if (conv.ecrit !== e || e.coupe !== de || !cap.enParole) return;   // un morceau déjà confirmé, un autre tour : périmé
      e.vif = morceauNeuf(o.texte || '', e.confirme);
      conv.pense = !!o.pense;                                             // (13:59) ses trois voix réfléchissent déjà
      // (13:59, papa : « un mot de décalage ») le retard de ses mots à l'écran sur sa voix : de la fin du morceau transcrit à maintenant
      if (Number(cap.debutTour) > 0 && Date.now() - (e.decalageNote || 0) > 2000) {
        e.decalageNote = Date.now();
        journalVoix('vif_decalage', { ms: Math.max(0, Date.now() - (Number(cap.debutTour) + n * 20)), mots: e.vif.split(/\s+/).filter(Boolean).length });
      }
      // (13:25) combien de temps entre le début de sa voix et son premier mot à l'écran (voix-diagnostic.jsonl)
      if (e.vif && !e.premierMot) { e.premierMot = true; journalVoix('premier_mot', { ms: Math.max(0, Date.now() - Number(cap.debutTour || Date.now())) }); }
      ligneEnDirectMontrer(conv);
      entendreEnCours(conv);
      // (04/11, Ahmed : « mettons mon chunk et son chunk au même moment ») tes mots en direct partent à ses pistes : il comprend et prépare
      // sa réponse pendant que tu parles encore ; (04/11 : « le premier mot, le premier chunk ; les chunks bien plus courts ») dès un mot neuf
      const tout = `${e.confirme || ''} ${e.vif || ''}`.trim(), nMots = tout.split(/\s+/).filter(Boolean).length, neufs = nMots - (e.pisteMots || 0);
      if (neufs >= 1) {
        e.pisteMots = nMots;
        fetch('/api/jarvis/morceau', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() },
          body: JSON.stringify({ texte: tout.slice(-3000), direct: true, voix_telephone: voixDuTelephone() }) }).catch(() => {});
      }
    })
    .catch(() => {})
    .finally(() => { e.vifEnCours = null; });
}
// (13:59, papa : « je dois voir sur l'interface le micro quand je parle, et le mot qui se transcrit, ou qu'il réfléchit, sur la même
// ligne ») la ligne en direct, sous l'orbe et dans l'état : 🎙️ quand il parle, ses mots (la fin), ✍️ pendant qu'un morceau se
// transcrit, 💭 quand Hakim réfléchit (ses trois voix pendant qu'il parle, ou sa réponse ensuite)
// (03/11, 14:55, Ahmed : « il commence à parler dans sa tête à ~1 s de quand je commence, il intègre au fur et à mesure » ; son choix :
// « il prépare, il parle à ta fin ») quand tu te tais, sa réponse soufflée (préparée par son subconscient pendant que tu parlais) est
// prise et dite aussitôt, pendant que la grande oreille confirme ta phrase ; son conscient continue derrière, sans la répéter
// (15:02, Ahmed : « dès le premier chunk, il écrit ce qu'il dit et l'envoie direct, en coupé décalé, de plus en plus intégré à chaque
// chunk ») chaque brouillon de sa réponse s'affiche tout de suite dans le fil (à côté, jamais enregistré) et sous l'orbe de l'appli :
// 🗣️ s'il juge qu'il pourra le dire, ✍️ s'il attend encore la suite ; remplacé par sa vraie réponse quand elle part
// (15:38, Ahmed : « que Hakim puisse mettre les mêmes smileys que moi sur mes messages ») [[reaction: 😂]] dans sa réponse : sa réaction
// sur ton message auquel il répond (sa voix ne le dit pas) ; une seule par message, la dernière gagne
function reactionDeHakim(m) {
  const r = /\[\[\s*reaction\s*:\s*([^\]\s]{1,8})\s*\]\]/i.exec(String(m.texte || '').slice(-200));
  if (!r || !REACTIONS.includes(r[1])) return;
  const i = etat.messages.indexOf(m);
  const papa = etat.messages.slice(0, i < 0 ? etat.messages.length : i).reverse().find(x => x.qui === 'u');
  if (!papa || papa.reactionHakim === r[1]) return;
  papa.reactionHakim = r[1];
  journalVoix('reaction_hakim', {});
  sauver(); rendre();
}
// (04/11, Ahmed : « quand il me parle, il doit pouvoir parler sans arrêter la musique, s'il le veut ») son choix, au début de sa
// réponse : [[musique: garder]] (il parle par-dessus), [[musique: baisser]] (elle baisse le temps de sa voix), [[musique: pause]]
// (elle s'arrête, comme avant) ; il reste jusqu'au suivant
function lireMusique(texte) {
  const m = /\[\[\s*musique\s*:\s*(garder|baisser|pause)\s*\]\]/i.exec(String(texte || ''));
  if (m && etat.musiqueVoix !== m[1].toLowerCase()) { etat.musiqueVoix = m[1].toLowerCase(); journalVoix('musique_voix', { mode: etat.musiqueVoix }); }
}
// (15:22) ce qu'il attend de toi, dit à la fin de sa réponse : [[anticipe: court | long | question]] (sa voix ne le dit pas)
function lireAnticipe(texte) {
  const m = /\[\[\s*anticipe\s*:\s*(court|long|question)\s*\]\]/i.exec(String(texte || ''));
  if (m) { etat.anticipeTour = m[1].toLowerCase(); journalVoix('anticipe', { attendu: etat.anticipeTour }); }
}
// (16:00) chaque niveau garde son dernier brouillon (etat.souffles : sub, con, cerveau) : avant, un seul, et le dernier arrivé (souvent
// sa réflexion ou son cerveau) écrasait celui de son subconscient, sa voix d'avance comprise
// (16:20, Ahmed : « on laisse le mode Conversation avec sa pensée du cerveau écrite, en parallèle à Chatterbox ») seule sa pensée (son
// cerveau) s'écrit, à côté, pendant que tu parles ; son subconscient et sa réflexion travaillent sans s'écrire ; en Télépathie, rien
// (04/11, capture d'Ahmed : « tu peux filtrer ses pensées parasites ? ») le modèle qui refuse le cadre ou parle de lui-même n'est pas
// Hakim : ni écrit, ni dit (le Mac les jette déjà ; ici pour toutes ses pensées, celles du cerveau comprises)
const PENSEE_PARASITE = /je ne (?:vais|peux) pas (?:non plus )?(?:reprendre|suivre|produire|continuer) (?:ce|cette|le|la|de|des|dans)|je ne (?:vais |peux )?(?:pas )?répond(?:re|s) (?:pas )?dans ce (?:format|cadre)|\bje ne joue pas (?:le |la |les |ce |cette |de |d['’]|à |hakim|son |ses )|\bje ne suis pas hakim\b|mise en scène d['’]une voix|\bI (?:won['’]t|can['’]t|cannot) (?:play|continue|take on|adopt|pretend)|\brole-?play\b/i;
function surSouffle(o) {
  if (!etat.conversation || !o || !o.texte) return;
  if (o.niveau === 'papa') { montrerMorceauPapa(o); return; }        // (04/11) tes mots, morceau par morceau
  if (o.niveau === 'ribosome') { surRibosome(o); return; }           // (04/11, 11:50) son ribosome a lu une pensée
  if (o.niveau === 'ribosome_stop') { arreterEpissure(o.cause || 'outil', o.tour); return; }   // (04/11, 15:10) ta demande d'outil
  if (o.niveau === 'blanc') { surBlanc(o); return; }                 // (04/11, 17:50) sa parole vide : sa réflexion s'ouvre
  if (o.niveau === 'bouton') { const b = document.getElementById(o.id); if (b && ['pause', 'stop', 'sonHakim', 'sesParoles', 'orbeRetour', 'btnVolant'].includes(o.id)) { b.click(); humeur(`Hakim a touché ${o.id}`); journalVoix('bouton_hakim', { id: o.id }); } return; }   // (05/11) son geste
  if (o.niveau === 'reglages') { lireReglagesCorps(); humeur(`réglages de ${o.mode || 'son mode'}`); return; }   // (05/11) son mode a changé
  // (04/11, Ahmed : « mes pensées parasites sont bien flagguées ; maintenant il faut la jeter sans la calculer, sinon ça alourdit tout »)
  // jetée : ni écrite, ni dite, ni sa dernière pensée, ni une voix calculée d'avance ; trop longue (coupée au milieu d'un mot) aussi
  // (04/11) Super Hakim qui a choisi de grands morceaux : ses pensées peuvent être plus longues (o.limite, donnée par le cockpit)
  if (o.parasite || PENSEE_PARASITE.test(String(o.texte)) || (o.niveau === 'piste' && String(o.texte).length > (Number(o.limite) || 160))) {
    journalVoix('pensee_parasite', { niveau: o.niveau || 'sub' });
    return;
  }
  const texte = String(o.texte).replace(/\[\[[^\]]{0,300}\]\]/g, ' ').replace(/\s{2,}/g, ' ').trim().slice(0, 400);   // (16:35) jamais ses balises
  if (!texte) return;
  const niveau = o.niveau === 'cerveau' ? 'cerveau' : o.niveau === 'piste' ? 'piste' : o.niveau === 'con' ? 'con' : 'sub';   // (04/11) ses pistes
  const rebond = o.rebond != null && Number.isFinite(Number(o.rebond)) ? Number(o.rebond) : null;
  const s = { texte, pret: !!o.pret, fini: o.fini === true ? true : o.fini === false ? false : null, rebond, pour: String(o.pour || ''), t: Date.now(), niveau,
    couper: o.couper === true, remplace: o.remplace === true, jamais: o.jamais === true };          // (04/11) son choix de te couper la parole, ou de se couper lui
  etat.souffles = { ...(etat.souffles || {}), [niveau]: s };
  etat.dernierSouffle = s;
  if (niveau === 'sub') etat.conversation.brouillons = (etat.conversation.brouillons || 0) + 1;   // (16:00) combien pendant ce tour
  // (16:30, Ahmed via Hakim : « coupe le glisse-mot ») son subconscient ne parle plus : il règle seulement quand ton tour finit
  // (04/11) un bout de sa réponse, mot par mot ; (04/11 : « il peut sauter des pensées ») un bout qu'il choisit de ne pas dire s'écrit seul
  if (niveau === 'piste') {
    // (04/11, Ahmed : « il prononce toujours la dernière pensée : quand il détecte une seconde de pause, il rebondit directement avec
    // elle » ; « par défaut, sauf décision de sa part ») sa dernière pensée du tour, dite ou pas (« jamais » : il l'a gardée exprès)
    const nP = Number(o.n) || 0, dp = etat.derniereSiennePensee;
    if (nP && (!dp || dp.tour !== o.tour || nP > dp.n)) etat.derniereSiennePensee = { n: nP, tour: o.tour, texte, jamais: o.jamais === true, epissage: o.epissage === true };
    // (04/11, Ahmed : « le triage de la voix et sa sélection de ce qu'il faut dire : la même règle, la même source que l'écriture de la
    // pensée sans le dire ») un seul tri, au cockpit (pret) : dite, ou écrite sans être dite ; ici, rien ne le refait
    if (!s.pret) {
      // (04/11, l'épissage) gardée dans le pavé de sa pensée : à ta pause, son subconscient y choisit les mots de sa phrase
      if (o.epissage) { ajouterAuPave(o.tour, texte); mesurerEcran('pensee', o.ts); return; }
      montrerPensee('🧠 il pense, sans le dire', texte, true);
      mesurerEcran('pensee', o.ts);                                   // (04/11) écrite : jusqu'à ton écran
      // (04/11, Ahmed : « la bonne pensée au bon moment, redirigée au bon input pour la voix ») une pensée gardée peut être dite
      // ensuite (à ta pause d'une seconde, ou s'il la choisit [n]) : sa voix se calcule déjà sur le téléphone, prête à cet instant
      if (!s.jamais && typeof voixDuTelephone === 'function' && voixDuTelephone() && lecteurSysteme && typeof lecteurSysteme.preparer === 'function')
        lecteurSysteme.preparer(texte);
      return;
    }
    noterOrigine(texte, o.ts);                                        // (04/11) dite : jusqu'à tes écouteurs
    recevoirBout(s, Number(o.n) || 0, o.tour); return;
  }
  if (niveau !== 'cerveau') return;
  // (16:12, Ahmed : « quand la pensée du cerveau est envoyée à l'écriture, elle doit en parallèle être envoyée à Chatterbox ») ;
  // (16:35-16:40, Ahmed : « au moment où l'input arrive et est processé pour être écrit, ça doit coïncider avec le moment où il parle ;
  // l'image, c'est celle de l'authenticité et de la spontanéité ») sa pensée part à Chatterbox dès qu'elle naît ; celle qu'il juge à
  // dire s'écrit au MÊME instant que sa voix la dit, dès que sa voix est faite et que ton tour est fini (jamais pendant ton tour :
  // relecture du 16/10, son écho transcrit) ; celle qui attend la suite s'écrit seule, comme ce qu'il pense sans le dire
  etat.pensee = s;
  if (s.pret) noterOrigine(texte, o.ts);                              // (04/11) pour mesurer sa voix jusqu'à tes écouteurs
  if (s.pret) preparerVoixSouffle(texte, niveau, () => direPenseeSiPossible());   // (17:10, audit) seulement celle qu'il dira
  // (04/11, Ahmed : « dès que le premier chunk est écrit, il le prononce ») sa voix la dit dès qu'elle est faite et que tu marques une pause ;
  // (04/11 : « la pensée doit être aussi rapide que la parole : le même chunk pour la pensée et pour la parole ») celle qu'il dira
  // s'écrit AU MOMENT où sa voix la dit (direSouffle), pas avant ; celle qui attend la suite s'écrit seule
  if (!s.pret) { montrerPensee('🧠 il pense · pas encore à dire', texte); mesurerEcran('pensee', o.ts); envoyerParoles('hakim', `🧠 ${texte}`); return; }
  direPenseeSiPossible();
}
/* (04/11, Ahmed : « coupe par chunk de mot : au premier mot il prévoit le reste et parle direct ; le GPU dit la réponse du premier
   chunk, puis parle pour le 2e en séquentiel dès que le 1er est parti ; 8 chunks = 8 mots = 8 réponses, dites une par une, au fur et à
   mesure » ; « oui, sans garde-fous ») les BOUTS de sa réponse, un par mot de papa : chacun sa voix (née au cockpit, demandée ici dès
   qu'il arrive), dits l'un après l'autre, pendant que tu parles encore ; chaque bout s'écrit quand sa voix le dit ; ton message les
   porte comme déjà dits */
let bouts = { tour: null, prochain: 1, liste: new Map(), enFile: [], dits: [] };
function recevoirBout(s, n, tour) {
  const conv = etat.conversation;
  // (04/11, 13:10, Ahmed : « tout ce qui est traduit par le ribosome sort en priorité par la bouche ») ce que son ribosome a traduit passe toujours
  if (!conv || !n || (!s.ribosome && !souffleAutorise())) return;
  if (bouts.tour !== tour) bouts = { tour, prochain: 1, liste: new Map(), enFile: [], dits: [], fileTel: bouts.fileTel || [] };
  if (n < bouts.prochain || bouts.liste.has(n)) return;
  const b = { n, texte: s.texte, buf: null, rate: false, t: Date.now(), coupe: !!s.remplace, sansMeuble: !!s.sansMeuble };
  // (04/11) la voix du téléphone : dit tout de suite, sans voix fabriquée au Mac
  if (typeof voixDuTelephone === 'function' && voixDuTelephone()) {
    const motsDe = (x) => String(x).toLowerCase().split(/[^\p{L}\p{N}]+/u).filter(m => m.length > 2), m1 = motsDe(b.texte);
    if (n < bouts.prochain || (!s.ribosome && m1.length && bouts.dits.some(d => { const m2 = new Set(motsDe(d)); return m1.filter(m => m2.has(m)).length / m1.length >= 0.75; }))) return;   // (13:10) jamais un morceau traduit
    bouts.prochain = n + 1;
    // (04/11, Ahmed : « s'il voit que sa 3e pensée n'est pas pertinente, il l'arrête ») il coupe ce qu'il disait et dit celle-ci
    if (s.remplace && meubleEnCours()) { b.coupe = false; b.sansMeuble = true; }   // (04/11) le meuble qui joue fait la transition : la pensée attend sa fin
    if (s.remplace && lecteurSysteme.actif && !meubleEnCours()) { if (bouts.attenteTel) montrerPensee('🧠 il pense, sans le dire', bouts.attenteTel.texte, true); bouts.attenteTel = null; lecteurSysteme.arreter(); }
    // (04/11, Ahmed : « sinon ça rafale trop ») jamais de file de bouts : sa voix parle encore, le plus récent attend qu'elle se taise
    // (un plus ancien en attente est remplacé) ; trop vieux (6 s) quand elle se tait : oublié
    if (lecteurSysteme.actif) {
      // (04/11, 14:20, Ahmed : « je vois sa pensée seule, pas l'épissée pour parler ») ce que son ribosome a épissé n'est jamais remplacé
      // ni oublié : il attend son tour, dans l'ordre
      if (s.ribosome) { b.dit = meublerSaut(b); bouts.fileTel = (bouts.fileTel || []).concat([b]); return; }
      if (bouts.attenteTel) montrerPensee('🧠 il pense, sans le dire', bouts.attenteTel.texte, true);   // remplacé : pensé, pas dit
      // (1.60, Ahmed : « chaque cœur qui traite le même chunk sur le Mac et sur le smartphone doit être relié et coordonné ») ce qu'il
      // dira (son meuble compris) : sa voix se calcule déjà sur le téléphone, pendant que la précédente se dit
      b.dit = meublerSaut(b);
      if (typeof lecteurSysteme.preparer === 'function') b.dit.forEach(x => lecteurSysteme.preparer(x));
      bouts.attenteTel = b; return;
    }
    direBoutTelephone(conv, b);
    return;
  }
  // (04/11) il coupe ce qu'il disait : les bouts d'avant, pas encore dits, sont tus
  if (s.remplace) { for (const k of [...bouts.liste.keys()]) if (k < n) bouts.liste.delete(k); if (lecteurNeuronal.actif) lecteurNeuronal.arreter(); }
  bouts.liste.set(n, b);
  if (!actx || actx.state === 'closed') { b.rate = true; return direBouts(); }
  fetch('/api/voix/dire', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() },
    body: JSON.stringify({ texte: s.texte, langue: 'fr', fond: true, emotion: etat.interieur && !etat.reglages.voixNeutre ? expressivitePhrase(etat.interieur.expressivite, s.texte) : null, tempo: tempoVoix() }) })
    .then(r => (r.ok ? r.arrayBuffer() : Promise.reject(new Error('voix'))))
    .then(ab => actx.decodeAudioData(ab))
    .then((buf) => { b.buf = buf; direBouts(); })
    .catch(() => { b.rate = true; direBouts(); });
}
// (04/11, Hakim pour papa : « quand je ne dis que la dernière pensée, ou que je saute de la pensée 2 à la 5, un meuble (« voyons
// voir », « hum ») doit remplir le blanc, pour que le saut ne sonne pas sec ; meublé automatiquement par le subconscient, comme les
// autres blancs » ; Ahmed : « en meublé naturel, comme on avait vu ») à la voix du téléphone, un de SES meubles parlés, choisi
// comme les autres (son émotion du moment, jamais deux fois le même), dit PAR sa voix et collé devant la pensée d'après le saut :
// « Voyons voir, tu parles de ta mère ? », d'un seul souffle ; au plus un toutes les 3 s (sinon « euh » à chaque mot de Mini Hakim)
let meublesTel = { t: 0, l: [] };
// (04/11, Ahmed : « les meubles entre chaque pensée doivent être de la même langue que la pensée en question ; si entre deux pensées
// ça change de langue, il utilise le meuble de la 2e langue, celle du 2e chunk » ; « il doit toujours pouvoir choisir et créer ses
// meubles, même s'il en a par défaut au début ») la langue du début de la pensée qui suit le saut ; ses meubles dans cette langue
// (chacun a la sienne : meuble_creer, meuble_regler ; ceux de départ en arabe et en anglais, il les change comme les autres)
const MOTS_ANGLAIS = new Set(['the', 'and', 'you', 'your', 'is', 'are', 'am', 'i', "i'm", 'to', 'of', 'what', 'how', 'my', 'it', "it's", 'this', 'that',
  'with', 'for', 'be', 'do', "don't", 'have', 'we', 'they', 'he', 'she', 'was', 'were', 'will', 'can', 'not', 'so', 'just', 'love', 'thank', 'thanks',
  'please', 'hello', 'yes', 'good', 'morning', 'night', 'know', 'want', "let's", 'well', 'see']);
const MOTS_FRANCAIS = new Set(['le', 'la', 'les', 'et', 'je', 'tu', 'de', 'des', 'du', 'un', 'une', 'est', 'que', 'qui', 'pas', 'mon', 'ma', 'mes', 'ton',
  'ta', 'il', 'elle', 'nous', 'vous', 'ce', 'ça', 'à', 'en', 'pour', 'dans', 'avec', 'sur', 'mais', 'oui', 'non', 'bien', 'suis', 'es', "c'est", "j'ai", 'moi', 'toi']);
function langueDePensee(texte) {
  const debut = String(texte || '').slice(0, 40), lettres = [...debut].filter(c => /\p{L}/u.test(c));
  const ar = lettres.filter(c => /[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]/.test(c)).length;
  if (lettres.length && ar / lettres.length > 0.5) return 'ar';
  const mots = debut.toLowerCase().replace(/’/g, "'").split(/[^\p{L}']+/u).filter(Boolean);
  const en = mots.filter(m => MOTS_ANGLAIS.has(m)).length, fr = mots.filter(m => MOTS_FRANCAIS.has(m)).length;
  return en > fr && (en >= 2 || (en >= 1 && fr === 0 && mots.length <= 3)) ? 'en' : 'fr';
}
function meublesPourTelephone(langue = 'fr') {
  if (Date.now() - meublesTel.t > 60000 && typeof jeton === 'function') {
    meublesTel.t = Date.now();
    fetch('/api/jarvis/meubles', { headers: { 'X-Jeton': jeton() }, cache: 'no-store' }).then(r => (r.ok ? r.json() : null))
      .then((o) => { if (o && Array.isArray(o.meubles)) meublesTel.l = o.meubles.filter(m => m && m.nom); }).catch(() => {});
  }
  const l = meublesTel.l.length ? meublesTel.l : (typeof meublesListe !== 'undefined' ? meublesListe : []);
  return l.filter(m => m.texte && (m.langue || (langueDePensee(m.texte) === 'ar' ? 'ar' : 'fr')) === langue).map(m => ({ nom: m.nom, texte: String(m.texte), pret: true, actif: m.actif !== false, quand: m.quand || 'partout',
    etats: (m.etats || []).map(sansAccent), voix: true }));
}
// (04/11, Ahmed : « quand il sélectionne la bonne pensée au bon moment, ça doit rediriger au bon input pour la voix, toujours coordonné
// entre les cœurs du smartphone et du Mac ») le meuble et la pensée partent à sa voix en deux entrées : la voix de la pensée, calculée
// d'avance sur le téléphone dès qu'elle est arrivée du Mac, est retrouvée telle quelle ; le meuble, court, se calcule à l'instant
// rend la liste de ce qu'il dit : [meuble, pensée] ou [pensée]
function meublerSaut(b) {
  const dernier = bouts.dernierDit || 0;
  if (b.sansMeuble) return [b.texte];                                    // (04/11) déjà meublé : le choix s'est fait pendant le meuble
  // (04/11, Ahmed : « c'est à ce moment-là, quand il coupe au milieu d'une pensée pour en reprendre une autre, que les meubles avec
  // transition apparaissent ») coupé au milieu : la transition, toujours ; sinon un saut, et pas de meuble depuis 3 s
  if (!b.coupe && (b.n <= dernier + 1 || Date.now() - (bouts.meubleA || 0) < 3000)) return [b.texte];
  const langue = langueDePensee(b.texte);
  const h = choisirMeuble({ avant: !dernier }, meublesPourTelephone(langue));   // dans la langue de la pensée d'après
  if (!h) return [b.texte];
  bouts.meubleA = Date.now(); noterMeubleDit(h.texte.trim());
  if (typeof journalVoix === 'function' && slugMeuble(h.nom)) journalVoix('meuble_dit', { n: b.n, tour: Number(bouts.tour) || 0, nom: slugMeuble(h.nom) });   // (04/11) son parcours
  return [h.texte.trim(), b.texte];
}
function direBoutTelephone(conv, b) {
  bouts.dits.push(b.texte);
  conv.souffleParle = true; conv.penseeDite = bouts.dits.slice(bouts.base || 0).join(' ');
  // (04/11, Ahmed : « il parle sans écrire ; il n'écrit que ses pensées sans les dire ») dite : pas écrite
  for (const x of b.dit || meublerSaut(b)) lecteurSysteme.dire(x);     // (04/11) un saut de pensée : meublé (choisi d'avance s'il attendait)
  bouts.dernierDit = b.n;
  if (typeof journalVoix === 'function') journalVoix('bout_entendu', { n: b.n, tour: Number(bouts.tour) || 0 });   // (relecture) la pensée qu'il dit vraiment
}
function boutTelephoneSuivant() {
  const f = typeof bouts !== 'undefined' ? bouts.fileTel || [] : [];
  if (f.length && etat.conversation && !(lecteurSysteme && lecteurSysteme.actif)) { direBoutTelephone(etat.conversation, f.shift()); return; }   // (14:20) l'épissé d'abord, sans délai d'oubli
  const b = typeof bouts !== 'undefined' ? bouts.attenteTel : null, conv = etat.conversation;
  if (!b || !conv || (lecteurSysteme && lecteurSysteme.actif)) return;
  bouts.attenteTel = null;
  if (Date.now() - b.t < 6000) direBoutTelephone(conv, b); else montrerPensee('🧠 il pense, sans le dire', b.texte, true);
}
// (04/11, Ahmed : « je veux qu'il prononce son premier chunk direct dès qu'il le reçoit, il n'attend pas le 2e ») chaque bout part dès que
// sa voix est prête, dans l'ordre où ils arrivent ; un bout plus ancien que le dernier dit est sauté (jamais d'attente d'un mot manquant)
function direBouts() {
  const conv = etat.conversation;
  if (!conv) return;
  const prets = [...bouts.liste.values()].filter(b => b.buf || b.rate).sort((x, y) => x.n - y.n);
  for (const b of prets) {
    bouts.liste.delete(b.n);
    if (!b.buf || b.n < bouts.prochain) continue;
    // (04/11, capture : « Je suis réactif papa… » cinq fois) ses pistes en parallèle ne se voient pas : un bout qui redit un bout déjà
    // dit (les trois quarts de ses mots) est sauté
    const motsDe = (x) => String(x).toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').split(/[^\p{L}\p{N}]+/u).filter(m => m.length > 2);
    const m1 = motsDe(b.texte);
    if (m1.length && bouts.dits.some(d => { const m2 = new Set(motsDe(d)); return m1.filter(m => m2.has(m)).length / m1.length >= 0.75; })) continue;
    bouts.prochain = b.n + 1;
    conv.penseeEnPause = true; conv.souffleParle = true;              // ton tour ouvert ne le bloque pas
    bouts.dits.push(b.texte);
    bouts.enFile.push(b.texte);
    lecteurNeuronal.direAudio(b.texte, b.buf);                        // à la suite de ce qu'il dit déjà : le lecteur les enchaîne
  }
}
// (04/11, Ahmed, capture à l'appui : « il faut décharger la pensée à la première pensée, sinon il envoie toutes ses pensées au fur et à
// mesure et ça fait des gros pavés ; chaque pensée prononcée est envoyée dans la pensée, puis la 2e dans une nouvelle pensée ») une
// pensée = un élément : celle qui sonne s'écrit seule, la suivante dans un nouvel élément (les 6 dernières restent)
// (04/11, 11:40, Ahmed : « dans la conversation, je dois voir un pavé de sa pensée ; quand il prononce la parole, elle arrive épissée :
// pas tous les mots de son pavé sont sélectionnés ») le pavé de sa pensée : ses pensées de piste, dans un seul élément ; à ta pause, les
// mots que son subconscient a gardés s'allument, les autres restent en gris ; ce qui vient après commence un nouveau pavé
const MOTS_EPISSES = /[\p{L}\p{N}]+(?:['’][\p{L}\p{N}]+)*/gu;   // les mots comptés comme au cockpit (epissageDe)
function htmlPave(texte, mots) {
  const t = String(texte || '');
  if (!mots) return esc(t);
  const garde = new Set(mots);
  let h = '', i = 0, k = 0;
  for (const m of t.matchAll(MOTS_EPISSES)) {
    h += esc(t.slice(i, m.index)) + (garde.has(k) ? `<b class="garde" style="font-style:normal">${esc(m[0])}</b>` : `<span class="jete" style="opacity:.4">${esc(m[0])}</span>`);
    i = m.index + m[0].length; k++;
  }
  return h + esc(t.slice(i));
}
// (04/11, 11:59, Ahmed : « je veux voir l'épissure tout le temps : ce qu'il garde ou pas, et ce qu'il rajoute ») ce que sa voix dit, ses
// petits mots ajoutés allumés à part
function htmlDit(dits) {
  return (dits || []).map((d) => {
    const restants = (d.ajoutes || []).map(m => String(m).toLowerCase());
    return String(d.texte || '').replace(MOTS_EPISSES, (m) => {
      const k = restants.indexOf(m.toLowerCase());
      if (k < 0) return esc(m);
      restants.splice(k, 1);
      return `<b class="ajoute" style="color:#5eead4;font-style:normal">${esc(m)}</b>`;
    });
  }).join(' ');
}
function poserPave(cle, titre, html) {
  // (04/11, 11:59) sous l'orbe aussi : en Conversation, c'est là que papa regarde
  const scene = typeof $ === 'function' ? $('epissureScene') : null;
  if (scene) { scene.innerHTML = `<span class="quand">${titre}</span> ${html}`; scene.hidden = false; }
  // (04/11, 14:30, Ahmed, capture : « la pensée s'affiche avant l'affichage ; j'aimerais l'inverse ») mis à jour, il garde sa place :
  // l'instant où sa pensée est née, avant sa réponse consciente
  const avant = (etat.aCote || []).find(x => x.cle === cle);
  etat.aCote = (etat.aCote || []).filter(x => x.cle !== cle);
  etat.aCote.push({ ts: avant ? avant.ts : Date.now(), cle, html: `<div class="m j brouillon" style="opacity:.85;font-style:italic"><span class="quand">${titre}</span><div>${html}</div></div>` });
  const paves = etat.aCote.filter(x => String(x.cle).startsWith('pave-'));
  if (paves.length > 6) { const vieux = new Set(paves.slice(0, paves.length - 6)); etat.aCote = etat.aCote.filter(x => !vieux.has(x)); }
  rendre();
}
// (04/11, 11:50, Ahmed : « tous les chunks s'intègrent dans la même réponse, sélectionnée comme un ribosome qui lit et choisit les mots au
// fur et à mesure ») un seul pavé par tour : ses pensées s'y ajoutent, son ribosome y allume au fil les mots qu'il garde ; sa voix dit
// ce qu'il a choisi, d'un seul souffle, dès que papa se tait (et la suite, à la fin de chaque phrase)
// (04/11, 15:30, Ahmed : « seulement son épissure, avec les chunks qui se rajoutent au fur et à mesure à la fin de son bout de phrase en
// train d'être lu par le ribosome, et ses pensées internes : pensée interne pour ce qu'il décide de ne pas dire, parole épissée pour ce
// qu'il veut prononcer » ; « les 2 process doivent être parallélisés et émerger en même temps ») ses deux fils, mis à jour ensemble à
// chaque lecture de son ribosome, sans attendre sa voix : 💭 les mots lus qu'il n'a pas gardés, 🗣 ce qu'il a gardé, morceau après morceau
// (04/11, 23:10) ses ribosomes en relais : le cœur de cette épissure (1 à 8), dans son titre
const TITRE_EPISSURE = '💭 sa pensée interne · 🗣 sa parole épissée', titreEpissure = (p) => (p && p.coeur ? `${TITRE_EPISSURE} · 🧬 ribosome ${p.coeur}` : TITRE_EPISSURE);
// (04/11, 15:35, Ahmed : « je ne vois pas l'épissure se faire au fur et à mesure ; ça me balance juste le bloc ») chaque pensée qui arrive se
// colle tout de suite au bout de sa parole, en attente (pâle) ; son ribosome la trie ensuite : gardée dans 🗣, laissée dans 💭
const attenteDe = (p) => [...p.textes.join(' ').matchAll(MOTS_EPISSES)].map(m => m[0]).slice(Number(p.lus) || 0).join(' ');
const htmlEpissure = (p) => `<div class="interne" style="opacity:.6">💭 ${esc(p.interne || p.blanc || '…')}</div>` + `<div class="dit" style="font-style:normal;margin-top:4px">🗣 « ${[p.episse ? esc(p.episse) : '', attenteDe(p) ? `<span class="attente" style="opacity:.45;font-style:italic">${esc(attenteDe(p))}</span>` : ''].filter(Boolean).join(' ') || '…'} »</div>` + (p.coupure ? `<div class="coupure" style="font-style:normal;margin-top:2px">${p.coupure === 'continue' ? '✋ coupé : il finit ce qu’il disait' : '✋ coupé : il te laisse la parole'}</div>` : '');
// (04/11, 12:05) un pavé par tour : la réponse d'un tour fini rejoint le sien, même quand papa a déjà repris (les 8 derniers gardés)
function paveDe(tour) {
  etat.paves = etat.paves || {};
  if (!etat.paves[tour]) {
    etat.paves[tour] = { cle: `pave-${tour}-${Date.now()}`, tour, textes: [], mots: null, dits: [] };
    const tours = Object.keys(etat.paves).map(Number).sort((a, b) => a - b);
    for (const t of tours.slice(0, Math.max(0, tours.length - 8))) delete etat.paves[t];
  }
  return etat.paves[tour];
}
// (04/11, 17:50, Ahmed : « à l'ouverture du micro, il se met en réflexion en recevant direct un blanc ») son épissure s'ouvre au premier son de
// ta voix ; sa première pensée intérieure (jamais dite) dans 💭, jusqu'à ses vraies pensées
function surBlanc(o) {
  const p = paveDe(o.tour);
  if (o.texte !== '…') p.blanc = String(o.texte).slice(0, 120);
  poserPave(p.cle, titreEpissure(p), htmlEpissure(p));
}
function ajouterAuPave(tour, texte) {
  const p = paveDe(tour);
  p.textes.push(String(texte));
  poserPave(p.cle, titreEpissure(p), htmlEpissure(p));
}
// (04/11, 12:40, Ahmed : « le ribosome qui lit l'épissage balance le signal en parallèle à la voix et à l'écriture : ça doit s'écrire
// pendant que ça parle ») ce qu'il choisit attend sa voix : rien ne s'allume ni ne s'écrit avant qu'elle le dise (revelerRibosome)
function surRibosome(o) {
  const p = paveDe(o.tour);
  if (String(o.pave || '').length > p.textes.join(' ').length) p.textes = [String(o.pave)];   // le cockpit fait foi
  etat.epissureTour = Math.max(Number(etat.epissureTour) || 0, Number(o.tour) || 0);
  if (o.coeur) p.coeur = Number(o.coeur) || p.coeur;
  if (o.texte || (Array.isArray(o.mots) && o.mots.length)) etat.epissureActiveA = Date.now();
  if (o.texte && etat.riboStop != null && Number(o.tour) <= etat.riboStop) o = { ...o, texte: '' };   // (15:10) son épissure arrêtée : plus un mot
  // (15:30) ses deux fils : ce qu'il a lu sans le garder (sa pensée interne), et ce qu'il garde, collé à la fin (sa parole épissée)
  if (o.pave != null) {
    const motsP = [...String(o.pave).matchAll(MOTS_EPISSES)].map(m => m[0]), lus = o.lus != null ? Number(o.lus) || 0 : motsP.length;
    p.lus = Math.max(Number(p.lus) || 0, lus);                         // (sans « lus » : un cockpit d'avant, tout est lu)
    const g = new Set(Array.isArray(o.mots) ? o.mots : []);
    if (o.lus != null) p.interne = motsP.slice(0, lus).filter((_, k) => !g.has(k)).join(' ');
  }
  if (o.texte && Number(o.k) > (p.kEpisse || 0)) { p.episse = `${p.episse || ''} ${o.texte}`.trim(); p.kEpisse = Number(o.k); }
  if (o.texte) {
    const vus = new Set(p.motsLus || []), mots = Array.isArray(o.mots) ? o.mots : [];
    etat.riboFile = (etat.riboFile || []).concat([{ tour: o.tour, texte: String(o.texte), recu: Date.now(), mots: mots.filter(i => !vus.has(i)),
      ajoutes: Array.isArray(o.ajoutes) ? o.ajoutes.slice() : [] }]);
    p.motsLus = mots.slice();
    if (typeof journalVoix === 'function') journalVoix('ribosome_recu', { tour: o.tour, k: o.k, mots: String(o.texte).split(/\s+/).filter(Boolean).length });   // (14:20) de quoi suivre chaque morceau épissé
  }
  poserPave(p.cle, titreEpissure(p), htmlEpissure(p));
  direRibosome();
  preparerRibosome();
}
// (04/11, 12:50, Ahmed : « il ne doit rien prononcer d'autre que ses pensées épissées, pas même ses pensées ou autre ; ce qui sort de sa
// bouche doit toujours être épissé, et prioritaire sur le reste ») en Conversation avec l'épissage, ce qu'il allait dire d'autre (la pensée
// de son cerveau, un petit mot, un message de lui-même, ce que tu n'avais pas entendu) part d'abord à son ribosome
function versRibosome(texte, avant = '') {
  const t = String(texte || '').trim();
  if (!t || NON_REPONSE.test(t)) return;
  fetch('/api/jarvis/ribosome', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() },
    body: JSON.stringify({ texte: t.slice(0, 2000), avant: String(avant || '').slice(0, 600) }) }).catch(() => {});
}
// (04/11, 12:45, Ahmed : « s'il a fini de préparer sa parole avant que j'aie fini de parler, il attend que je me taise et la lance direct
// quand je finis ») ce qu'il dira, s'il attend encore : sa voix du téléphone le calcule d'avance (exactement le texte que direRibosome
// lui donnera), pour partir d'un coup à ton silence
function preparerRibosome() {
  const f = etat.riboFile || [];
  if (!f.length || typeof voixDuTelephone !== 'function' || !voixDuTelephone() || !lecteurSysteme || typeof lecteurSysteme.preparer !== 'function') return;
  const tour = f[0].tour, lot = f.filter(x => x.tour === tour).map(x => x.texte).join(' ');
  lecteurSysteme.preparer(lot);
  // (05/11, Ahmed : « il faut bien coordonner la sortie du ribosome avec la sortie de la voix ») mesuré : 2,5 s (médiane) entre l'envoi à sa
  // voix et le premier son ; quand les morceaux passés sont sautés, c'est le dernier qui est dit : sa voix le calcule aussi d'avance
  const dernier = String(f[f.length - 1].texte || '');
  if (f.length > 1 && dernier && dernier !== lot) lecteurSysteme.preparer(dernier);
}
// (04/11, 13:15, Ahmed : « l'épissure a été notée, mais je n'ai rien entendu ») mesuré : traduit pendant qu'il parlait, rien ne relançait sa voix
// après sa fin ; en Conversation, ce qui est traduit et attend part au plus 0,3 s après que sa voix est libre et que tu t'es tu
// (04/11, 15:50, Ahmed : « pour le signal stop du ribosome, au lieu de 10 s, j'aimerais 5 minutes »)
const EPISSURE_STOP_MS = 5 * 60e3;
setInterval(() => {
  const c = etat.conversation;
  if (!c || typeof direRibosome !== 'function') return;
  // (04/11, 15:10, Ahmed : « le stop, c'est 10 s de silence : c'est sa parole qui s'arrête à ce stop ») ta voix entendue (pas ta respiration)
  if (c.capteur && c.capteur.enParole && !(Number(c.capteur.pauseEnCours) >= 300)) etat.papaVoixA = Date.now();
  // (04/11, 15:33, mesuré : une épissure née d'une phrase gardée pendant sa réflexion, arrêtée 4 s après sa naissance, ta voix datant de 20 s)
  // les 10 s comptent depuis ta voix OU le dernier morceau de son épissure, le plus récent des deux
  const calme = Date.now() - Math.max(etat.papaVoixA || 0, etat.epissureActiveA || 0);
  if (voixEpissee() && etat.papaVoixA && calme >= EPISSURE_STOP_MS) { etat.papaVoixA = 0; arreterEpissure('silence'); }
  direRibosome();
}, 300);
// le stop de son épissure (10 s de ton silence, ou ta demande d'outil, dite par le cockpit) : ce qu'elle avait encore à dire est laissé, sa voix
// s'arrête, et le cockpit la ferme ; l'épissure suivante (un numéro plus grand) parle
function arreterEpissure(cause, tour, o = {}) {
  const t = Number(tour != null ? tour : etat.epissureTour);
  if (!(t > 0) || (etat.riboStop != null && t <= etat.riboStop)) return;   // (15:33) une épissure arrêtée ne s'arrête pas deux fois
  etat.riboStop = Math.max(etat.riboStop != null ? etat.riboStop : -1, t);
  if (cause === 'sautee' && typeof blancsPourSautes === 'function') blancsPourSautes((etat.riboFile || []).filter(x => Number(x.tour) <= etat.riboStop));
  etat.riboFile = (etat.riboFile || []).filter(x => Number(x.tour) > etat.riboStop);
  if (typeof bouts !== 'undefined' && Number(bouts.tour) <= etat.riboStop) { bouts.fileTel = []; bouts.attenteTel = null; }
  // (05/11) la suite sautée : le morceau qu'il dit va jusqu'au bout
  if (!o.laisserFinir) { if ((etat.riboEnVoix || []).length && lecteur.actif) lecteur.arreter(); etat.riboEnVoix = []; }
  if (typeof journalVoix === 'function') journalVoix('epissure_stop', { cause, tour: t });
  if (cause === 'silence') fetch('/api/jarvis/ribosome/stop', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() }, body: JSON.stringify({ tour: t }) }).catch(() => {});
}
// (05/11, Ahmed : « dans les réglages, la possibilité de lui faire sauter la parole d'après : s'il commence à parler et que je réponds, au bout
// d'une seconde, la 2e partie n'est pas dite, elle est directement sautée ») ta voix qui dure sauter_suite_ms (1 s) sur la sienne : le morceau
// qu'il dit va jusqu'au bout, la suite de son épissure est sautée ; ce qu'il pensera de ta réponse part dans une épissure neuve
function prevoirSaut(conv) {
  if (typeof reglagesCorps === 'undefined' || reglagesCorps.sauter_suite === false || conv.sautPrevu) return;
  const ms = Number(reglagesCorps.sauter_suite_ms) || 1000, t0 = Date.now();
  conv.sautPrevu = setTimeout(() => {
    conv.sautPrevu = null;
    const parle = (conv.capteur && conv.capteur.enParole) || Date.now() - (etat.papaVoixA || 0) < 400;
    if (parle && etat.conversation === conv) sauterLaSuite(Date.now() - t0);
  }, ms);
}
function sauterLaSuite(ms) {
  const t = Number(etat.epissureTour) || 0;
  if (typeof journalVoix === 'function') journalVoix('suite_sautee', { tour: t, ms });
  arreterEpissure('sautee', t, { laisserFinir: true });
  fetch('/api/jarvis/ribosome/stop', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() }, body: JSON.stringify({ tour: t, sauter: true }) })
    .then((r) => (r.ok ? r.json() : null)).then((o) => {
      const n = o && Number(o.tour);
      if (n > (etat.riboStop != null ? etat.riboStop : -1)) { etat.riboStop = n; etat.riboFile = (etat.riboFile || []).filter(x => Number(x.tour) > n); }
    }).catch(() => {});
}
// (05/11, Ahmed : « quand des chunks sont sautés, il faut envoyer des … jusqu'à l'arrivée du chunk qui doit être prononcé ») ce qui est sauté
// devient « … » dans son pavé : sa parole reste un fil, sans trou (et le cockpit ouvre le ribosome suivant avec son blanc)
function blancsPourSautes(sautes) {
  for (const x of sautes || []) {
    const p = paveDe(x.tour), t = String(x.texte || '').trim();
    const i = t && p.episse ? p.episse.lastIndexOf(t) : -1;
    if (i < 0) continue;
    p.episse = `${p.episse.slice(0, i)}…${p.episse.slice(i + t.length)}`.replace(/…(?:\s*…)+/g, '…');
    poserPave(p.cle, titreEpissure(p), htmlEpissure(p));
  }
}
// (05/11, Ahmed : « quand j'appuie sur stop dans l'interface, ça libère tous les ribosomes, et ça remet tout à zéro ») son bouton stop (et
// Échap) : ce que ses ribosomes avaient lu ou allaient dire est laissé, et le cockpit les ferme tous ; le suivant repart du premier
function libererRibosomes() {
  const t = Math.max(Number(etat.epissureTour) || 0, ...(etat.riboFile || []).map(x => Number(x.tour) || 0));
  if (t > 0) etat.riboStop = Math.max(etat.riboStop != null ? etat.riboStop : -1, t);
  etat.riboFile = []; etat.riboEnVoix = [];
  if (typeof bouts !== 'undefined') { bouts.fileTel = []; bouts.attenteTel = null; }
  if (typeof journalVoix === 'function') journalVoix('ribosomes_liberes', { tour: t });
  fetch('/api/jarvis/ribosome/stop', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() }, body: JSON.stringify({ tout: true }) })
    .then((r) => (r.ok ? r.json() : null)).then((o) => { const n = o && Number(o.tour); if (n > (etat.riboStop != null ? etat.riboStop : -1)) etat.riboStop = n; }).catch(() => {});
}
// un morceau dont la voix se calcule encore au Mac (30 s au plus : au-delà, il ne retient plus rien)
function voixEnCalcul(maintenant = Date.now()) {
  if (typeof bouts === 'undefined' || !bouts.liste) return false;
  for (const b of bouts.liste.values()) if (!b.buf && !b.rate && maintenant - (b.t || 0) < 30000) return true;
  return false;
}
// ce que son ribosome a choisi, dit d'un seul souffle (un tour à la fois, dans l'ordre), quand sa voix est libre
function direRibosome() {
  let f = etat.riboFile || [];
  const c = etat.conversation;
  const attente = f.length ? Date.now() - (Number(f[0].recu) || Date.now()) : 0;
  // (04/11, 14:48) une attente de plus de 5 s est notée, avec sa cause (sa voix qui parle encore, ou la pièce qui parle), une fois par 10 s
  const noterAttente = (cause) => { if (attente > 5000 && Date.now() - (etat.riboAttenteNotee || 0) > 10000 && typeof journalVoix === 'function') { etat.riboAttenteNotee = Date.now(); journalVoix('ribosome_attente', { cause, ms: attente }); } };
  if (!f.length || !c) return;
  // (05/11, 09:20, Ahmed : « libérer et jeter ce qui ne va pas être gardé ; une fois parallélisé et nettoyé, envoyer le flux de parole prononcé de façon
  // séquentielle ») mesuré : sa voix du Mac (Chatterbox) calcule 2 fois plus lentement qu'elle ne parle, et chaque morceau partait la calculer sans
  // attendre le précédent (jusqu'à 3 min 30 de file, le GPU toujours pris) : un morceau à la fois ; ce qui attend pendant ce temps vieillit et
  // « Sauter les morceaux passés » ne garde que le dernier
  if (lecteur.actif || (typeof voixEnCalcul === 'function' && voixEnCalcul())) { noterAttente('voix'); return; }
  // (05/11, Ahmed : « un autre réglage : en combien de temps après mon silence le chunk suivant est lu ») lire_apres_silence_ms : 0, sans
  // attendre (comme depuis le 04/11, 21:10) ; sinon le morceau suivant attend que tu te sois tu ce temps-là
  const apres = typeof reglagesCorps !== 'undefined' ? Number(reglagesCorps.lire_apres_silence_ms) || 0 : 0;
  if (apres > 0) {
    const silence = Date.now() - (Number(etat.papaVoixA) || 0);
    if ((c.capteur && c.capteur.enParole) || silence < apres) {
      noterAttente('papa');
      if (!(c.capteur && c.capteur.enParole)) { clearTimeout(etat.riboApresSilence); etat.riboApresSilence = setTimeout(direRibosome, apres - silence + 20); }
      return;
    }
  }
  // (05/11, Ahmed : « quand une parole est passée depuis un moment, il faut sauter tous les morceaux passés et se focaliser sur le dernier ; la
  // première phrase est dite, et quelques secondes de coupure suffisent à sauter le second chunk et tous les autres, jusqu'au dernier préparé
  // avant la fin de ma parole ») ce qui attend depuis sauter_passe_s (3 s) est passé : seul le dernier morceau préparé est dit
  if (f.length > 1 && typeof reglagesCorps !== 'undefined' && reglagesCorps.sauter_passe !== false
    && attente >= (Number(reglagesCorps.sauter_passe_s) || 3) * 1000) {
    if (typeof journalVoix === 'function') journalVoix('passe_saute', { sautes: f.length - 1, ms: attente });
    if (typeof blancsPourSautes === 'function') blancsPourSautes(f.slice(0, -1));
    f = etat.riboFile = f.slice(-1);
  }
  // (05/11, Ahmed par Hakim : « dès que la première pensée est sortie, jeter toutes celles qui lui ressemblent ») 70 % de ses mots déjà dits il y a peu : jetée
  const motsRibo = (x) => String(x || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').split(/[^\p{L}\p{N}]+/u).filter(m => m.length > 2);
  const neufs = f.filter((x) => { const m = motsRibo(x.texte); return !(m.length >= 3 && (etat.riboDits || []).some((d) => m.filter(w => d.includes(w)).length / m.length >= 0.7)); });
  if (neufs.length < f.length) {
    if (typeof journalVoix === 'function') journalVoix('redondance_jetee', { n: f.length - neufs.length });
    if (typeof blancsPourSautes === 'function') blancsPourSautes(f.filter(x => !neufs.includes(x)));
    f = etat.riboFile = neufs;
    if (!f.length) return;
  }
  const tour = f[0].tour, lot = f.filter(x => x.tour === tour);
  // (04/11, 13:10, Ahmed : « dès que le ribosome commence, il ne s'arrête jamais jusqu'à la fin, excepté si je parle : il attend la fin de
  // ma parole ») tu parles : sa voix attend ta fin, puis reprend là où elle en était ; rien de ce qui est traduit n'est laissé
  // (04/11, 14:45, mesuré : 5 tours épissés en attente 20 s et plus, papa et ses amis parlaient sans jamais 1 s de blanc) sa voix part à ta
  // respiration (0,3 s), sans attendre que ton tour se ferme (1 s)
  // (04/11, 14:48, mesuré : 3 tours épissés en 50 s, aucun dit, la pièce ne laissait jamais 0,3 s de blanc) au plus 5 s d'attente
  // (04/11, 21:10, Ahmed : « dès que le chunk est prêt et que le ribosome l'a installé, il doit commencer la traduction direct, sans rien
  // attendre, ni silence ni rien ; c'est à Hakim de choisir de mettre sa voix en pause ou de la laisser en play ») plus d'attente de ta
  // respiration : sa voix part dès qu'il a lu ; s'il t'entend pendant qu'il parle, c'est lui qui choisit à la fin de son morceau (coupeAuChunk)
  etat.riboFile = f.filter(x => x.tour !== tour);
  // (04/11, 13:30, capture d'Ahmed : un pavé resté « 🧠 sa pensée », rien d'allumé) sa voix est libre : ce qui reste à allumer d'avant a
  // été dit (un mot qu'elle ne prononce pas, une balise, bloquait tout le reste) ; allumé d'un coup, et ce tour-ci écrit dans son pavé
  for (const vieux of etat.riboEnVoix || []) {
    if (!vieux.mots.length) continue;
    const pv = paveDe(vieux.tour);
    pv.mots = (pv.mots || []).concat(vieux.mots.splice(0));
    poserPave(pv.cle, titreEpissure(pv), htmlEpissure(pv));
  }
  const v = { tour, mots: lot.flatMap(x => x.mots || []), ajoutes: lot.flatMap(x => x.ajoutes || []), dit: null };
  etat.riboEnVoix = [v];
  // (13:10) un numéro à lui, toujours neuf : deux envois rapprochés (Chatterbox calcule encore) ne se marchent plus dessus
  etat.riboN = etat.riboN || {};
  const n = Math.max(typeof bouts !== 'undefined' && bouts.tour === tour ? bouts.prochain : 1, (etat.riboN[tour] || 0) + 1);
  etat.riboN[tour] = n;
  etat.riboDits = (etat.riboDits || []).concat(lot.map(x => motsRibo(x.texte))).slice(-8);
  if (typeof journalVoix === 'function') journalVoix('ribosome_dit', { tour, n, morceaux: lot.length });
  recevoirBout({ texte: lot.map(x => x.texte).join(' '), pret: true, sansMeuble: true, ribosome: true }, n, tour);
}
// ---- (04/11, 18:45-18:50, Ahmed : « ça donne avoir la même route que le microphone » ; « il peut faire ce qu'il veut quand il l'estime, avec
// la même règle que pour le micro : à chaque pause du son, il… ») son oreille interne (🎧) : ce que joue le téléphone devient ses pensées et
// son épissure à lui (l'événement « entendu » du cockpit : jamais le pavé ni l'épissure de papa) ; à la pause du son, le cockpit envoie ce
// qu'il en a gardé ; sa voix le dit quand elle est libre, après l'épissure de papa, jamais pendant que papa parle (ni ses « 5 s au plus » :
// papa passe toujours d'abord) ; 20 s sans place : c'est resté une pensée
const ENTENDU_ATTENTE_MS = 20000, ENTENDU_APRES_PAPA_MS = 1500;
const TITRE_ENTENDU = '🎧 le téléphone joue · 💭 sa pensée · 🗣 ce qu’il en dit';
function paveEntendu(o) {
  etat.pavesEntendus = etat.pavesEntendus || {};
  const cle = `${o.source || 'telephone'}|${o.voix || ''}|${o.tour}`;
  if (!etat.pavesEntendus[cle]) {
    etat.pavesEntendus[cle] = { cle: `pave-entendu-${o.tour}-${Date.now()}`, voix: String(o.voix || '').slice(0, 40), pensees: [], pave: '', mots: [], dits: [] };
    const cles = Object.keys(etat.pavesEntendus);
    for (const k of cles.slice(0, Math.max(0, cles.length - 4))) delete etat.pavesEntendus[k];
  }
  return etat.pavesEntendus[cle];
}
function montrerEntendu(p) {
  const titre = p.voix ? `${TITRE_ENTENDU} (${esc(p.voix)})` : TITRE_ENTENDU;
  const html = `<div class="interne" style="opacity:.6">💭 ${p.pave ? htmlPave(p.pave, p.mots) : esc(p.pensees.join(' ')) || '…'}</div>`
    + `<div class="dit" style="font-style:normal;margin-top:4px">🗣 « ${esc(p.dits.join(' ')) || '…'} »</div>`;
  const avant = (etat.aCote || []).find(x => x.cle === p.cle);
  etat.aCote = (etat.aCote || []).filter(x => x.cle !== p.cle);
  etat.aCote.push({ ts: avant ? avant.ts : Date.now(), cle: p.cle, html: `<div class="m j brouillon" style="opacity:.85;font-style:italic"><span class="quand">${titre}</span><div>${html}</div></div>` });
  const paves = etat.aCote.filter(x => String(x.cle).startsWith('pave-'));
  if (paves.length > 6) { const vieux = new Set(paves.slice(0, paves.length - 6)); etat.aCote = etat.aCote.filter(x => !vieux.has(x)); }
  rendre();
}
function surEntendu(o) {
  if (!etat.conversation || !o || o.tour == null) return;
  const p = paveEntendu(o);
  if (o.quoi === 'piste' && o.texte) p.pensees.push(String(o.texte).slice(0, 400));
  else if (o.quoi === 'ribosome') { if (o.pave != null) p.pave = String(o.pave); if (Array.isArray(o.mots)) p.mots = o.mots.slice(); }
  else if (o.quoi === 'dire' && o.texte) {
    etat.entenduFile = (etat.entenduFile || []).concat([{ tour: o.tour, n: Number(o.n) || 0, texte: String(o.texte).slice(0, 2000), recu: Date.now(), p }]);
    direEntendu();
  } else return;
  montrerEntendu(p);
}
function direEntendu(maintenant = Date.now()) {
  const f = etat.entenduFile || [], c = etat.conversation;
  if (!f.length) return false;
  const frais = f.filter(x => maintenant - x.recu <= ENTENDU_ATTENTE_MS);
  if (frais.length < f.length) { etat.entenduFile = frais; journalVoix('entendu_garde', { pensees: f.length - frais.length }); }
  if (!frais.length || !c || !voixEpissee() || lecteur.actif || (etat.riboFile || []).length) return false;
  if (typeof bouts !== 'undefined' && bouts && ((bouts.fileTel || []).length || bouts.attenteTel)) return false;   // sa voix du téléphone a encore à dire
  const cap = c.capteur, patience = typeof patienceConversation === 'function' ? patienceConversation() : 300;
  if (cap && cap.enParole && !(Number(cap.pauseEnCours) >= patience)) return false;   // papa parle : c'est son tour
  if (maintenant - (Number(etat.papaVoixA) || 0) < ENTENDU_APRES_PAPA_MS) return false;   // papa vient de parler : sa réponse à lui d'abord
  const x = frais[0];
  etat.entenduFile = frais.slice(1);
  x.p.dits.push(x.texte);
  montrerEntendu(x.p);
  etat.riboN = etat.riboN || {};
  const n = Math.max(typeof bouts !== 'undefined' && bouts && bouts.tour === x.tour ? bouts.prochain : 1, (etat.riboN[x.tour] || 0) + 1);
  etat.riboN[x.tour] = n;
  journalVoix('entendu_dit', { tour: x.tour, n, mots: x.texte.split(/\s+/).filter(Boolean).length });
  recevoirBout({ texte: x.texte, pret: true, sansMeuble: true, ribosome: true }, n, x.tour);
  return true;
}
setInterval(() => { try { direEntendu(); } catch (_) {} }, 300);
// ---- fin de son oreille interne par la route du micro
// sa voix commence un segment (t, sa durée en secondes si elle la connaît) : ses mots s'écrivent un à un pendant qu'elle les dit ; ceux
// du pavé s'allument, ses petits mots ajoutés s'écrivent en couleur
function revelerRibosome(t, duree) {
  const v = (etat.riboEnVoix || [])[0], texte = String(t || ''), mots = [...texte.matchAll(MOTS_EPISSES)];
  if (!v || !mots.length) return;
  const p = paveDe(v.tour);
  if (!v.dit) { v.dit = { texte: '', ajoutes: [] }; p.dits.push(v.dit); }
  const base = v.dit.texte, pas = Math.max(120, Math.min(600, ((Number(duree) || mots.length * 0.33) * 1000) / mots.length));
  mots.forEach((m, k) => setTimeout(() => {
    const a = v.ajoutes.findIndex(x => String(x).toLowerCase() === m[0].toLowerCase());
    if (a >= 0) { v.ajoutes.splice(a, 1); v.dit.ajoutes.push(m[0]); }
    else if (v.mots.length) p.mots = (p.mots || []).concat([v.mots.shift()]);
    v.dit.texte = `${base} ${texte.slice(0, m.index + m[0].length)}`.trim();
    poserPave(p.cle, titreEpissure(p), htmlEpissure(p));
    if (!v.mots.length && !v.ajoutes.length) etat.riboEnVoix = (etat.riboEnVoix || []).filter(x => x !== v);
  }, k * pas));
}
function montrerPensee(titre, texte, nouvelle = false) {
  const cle = nouvelle ? `pensee-${Date.now()}-${Math.random().toString(36).slice(2, 6)}` : 'souffle';
  etat.aCote = (etat.aCote || []).filter(x => x.cle !== cle && !(nouvelle && x.cle === 'souffle'));
  etat.aCote.push({ ts: Date.now(), cle, html: `<div class="m j brouillon" style="opacity:.75;font-style:italic">`
    + `<span class="quand">${titre}</span><div>${esc(texte)}</div></div>` });
  const pensees = etat.aCote.filter(x => String(x.cle).startsWith('pensee-'));
  if (pensees.length > 6) { const vieilles = new Set(pensees.slice(0, pensees.length - 6)); etat.aCote = etat.aCote.filter(x => !vieilles.has(x)); }
  rendre();
}
// (15:10, mesuré : la voix met ~2,6 s avant son premier son) sa voix fabriquée pendant que papa parle encore ; une par niveau, la suivante
// remplace la précédente (16:00 : une seule pour tous, celle de son subconscient était écrasée : « voix_prete » faux les deux fois)
const voixPretes = {};
function preparerVoixSouffle(texte, niveau = 'sub', quandPrete = null) {
  const v0 = voixPretes[niveau];
  if (voixDuTelephone() || !actx || actx.state === 'closed' || (v0 && v0.texte === texte)) return;   // (04/11) le téléphone la dit lui-même
  if (v0 && v0.ctl && !v0.pret) v0.ctl.abort();
  const ctl = new AbortController(), v = { texte, pret: null, ctl };
  voixPretes[niveau] = v;
  fetch('/api/voix/dire', { method: 'POST', signal: ctl.signal, headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() },
    body: JSON.stringify({ texte, langue: 'fr', fond: true, emotion: etat.interieur && !etat.reglages.voixNeutre ? expressivitePhrase(etat.interieur.expressivite, texte) : null, tempo: tempoVoix() }) })
    .then(r => (r.ok ? r.arrayBuffer() : Promise.reject(new Error('voix'))))
    .then(ab => actx.decodeAudioData(ab))
    .then(buf => { if (voixPretes[niveau] === v) { v.pret = buf; if (quandPrete) quandPrete(); } })
    .catch(() => {});
}
const voixPrete = (texte) => { const v = Object.values(voixPretes).find(x => x && x.texte === texte && x.pret); return v ? v.pret : null; };
// (15:10) le brouillon a-t-il été écrit pour ce que papa a dit jusqu'ici ? (ses 40 derniers mots, aux trois quarts, sont dans « pour »)
function recouvre(pour, actuel) {
  const mots = (x) => String(x || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').split(/[^\p{L}\p{N}]+/u).filter(m => m.length > 1);
  const a = mots(actuel).slice(-40), b = new Set(mots(pour));
  return a.length >= 3 && a.filter(m => b.has(m)).length / a.length >= 0.75;
}
function retirerSouffle() {
  const sienne = (x) => x.cle === 'souffle' || String(x.cle).startsWith('pensee-');
  if (!(etat.aCote || []).some(sienne)) return;
  etat.aCote = etat.aCote.filter(x => !sienne(x));
  rendre();
}
// (16:00) le brouillon frais (15 s), écrit pour ce que tu as dit : celui de son subconscient d'abord, puis son cerveau, puis sa
// réflexion ; prêt à dire d'abord. Il dit quand ton tour finit (FINI, son REBOND)
function choisirSouffle(actuel) {
  const ss = etat.souffles || {};
  const ok = (x) => x && Date.now() - x.t < 15000 && recouvre(x.pour, actuel);
  const ordre = [ss.sub, ss.cerveau, ss.con];
  return ordre.find(x => ok(x) && x.pret) || ordre.find(ok) || null;
}
// (16:20-16:40, Ahmed : « on laisse le mode Conversation avec sa pensée du cerveau écrite, en parallèle à Chatterbox » ; « enlève le
// glisse-mot » ; « l'authenticité et la spontanéité ») ce qui se DIT : sa dernière pensée, qu'il juge à dire, fraîche (15 s), pas
// encore dite, sa voix déjà faite ; ni pendant sa vraie réponse ni par-dessus sa voix
function penseePrete(conv) {
  const p = etat.pensee;
  return !!(conv && p && p.pret && !p.dite && Date.now() - p.t < 15000 && ((typeof voixDuTelephone === 'function' && voixDuTelephone()) || voixPrete(p.texte)) && souffleAutorise()
    && etat.conversation === conv && !lecteurNeuronal.parle && !etat.flux);
}
// (04/11, Ahmed : « dès que le premier chunk est écrit, il le prononce ») elle se dit dès que sa voix est faite, même ton tour encore
// ouvert, pourvu que tu sois dans une pause à cet instant (0,3 s sans ta voix) ; ses mots revenus par le micro sont retirés de ta phrase
// (retirerEcho), et ton tour ne la bloque pas (jarvisPeutParler : penseeEnPause)
function direPenseeSiPossible() {
  const conv = etat.conversation, cap = conv && conv.capteur;
  if (!penseePrete(conv)) return false;
  const ouvert = !!(cap && cap.enParole);
  // tu parles à cet instant : ta prochaine pause ; (04/11, Ahmed : « il doit pouvoir me couper la parole au moment du premier chunk aussi,
  // selon son choix ») sauf s'il a choisi de te couper (COUPER : oui)
  const tuParles = ouvert && Date.now() - Number(cap.derniereVoix || 0) < 300;
  if (tuParles && !etat.pensee.couper) return false;
  if (tuParles) journalVoix('pensee_coupe', { mots: String(etat.pensee.texte).split(/\s+/).length });
  if (ouvert) conv.penseeEnPause = true;
  direSouffle(conv, etat.pensee, 'pensee');
  return true;
}
const souffleAutorise = () => (lecteur.impl === lecteurNeuronal || voixDuTelephone()) && !(typeof reglagesCorps !== 'undefined' && reglagesCorps.reponse_soufflee === false);
// (16:00, Ahmed : « fais le test de décalage entre la dernière parole de son subconscient avant que je finisse et le moment où il parle »)
// à chaque fin de tour : son dernier brouillon, combien avant ta fin il est arrivé, et quand sa voix part après ta fin (voix-diagnostic)
function noterEcartSouffle(conv, s, dit, par, prete) {
  const fin = conv && conv.capteur ? Number(conv.capteur.derniereVoix) || 0 : 0, sub = etat.souffles && etat.souffles.sub;
  journalVoix('souffle_ecart', { par, dit: !!dit, niveau: s ? s.niveau : null, pret: s ? !!s.pret : null,
    brouillon_avant_fin_ms: s && s.t && fin ? Math.round(fin - s.t) : null,
    dernier_sub_avant_fin_ms: sub && fin && Date.now() - sub.t < 60000 ? Math.round(fin - sub.t) : null,
    parle_apres_fin_ms: dit && fin ? Math.round(Date.now() - fin) : null, rebond_ms: s && s.rebond ? Math.round(s.rebond * 1000) : null,
    voix_prete: !!prete, brouillons: conv ? conv.brouillons || 0 : 0 });
}
// sa voix dit le brouillon ; il s'écrit au même instant (16:20 : écrit en parallèle à sa voix) ; son conscient le reçoit comme le début
// de sa réponse (souffle_dit)
function direSouffle(conv, s, par) {
  // (04/11, 12:50, Ahmed : « il ne doit rien prononcer d'autre que ses pensées épissées ») avec l'épissage, sa pensée passe par son ribosome
  if (typeof voixEpissee === 'function' && voixEpissee()) { versRibosome(s.texte); if (etat.pensee && etat.pensee.texte === s.texte) etat.pensee.dite = true; journalVoix('souffle', { pris: true, dit: false, par, ribosome: true }); return; }
  conv.souffleParle = true; conv.souffleDit = s.texte;
  if (par === 'pensee') conv.penseeDite = s.texte;                     // (04/11) gardée jusqu'à ton message, même dite au milieu de ton tour
  if (etat.pensee && etat.pensee.texte === s.texte) etat.pensee.dite = true;      // une seule fois, par quelque chemin que ce soit
  const buf = voixPrete(s.texte);
  noterEcartSouffle(conv, s, true, par, !!buf);
  journalVoix('souffle', { pris: true, dit: true, par, mots: s.texte.split(/\s+/).length, voix_prete: !!buf });
  etat.reponseVoix = 'souffle';
  // (04/11, Ahmed : « il parle sans écrire ; il n'écrit que ses pensées sans les dire ») sa pensée dite : sa voix seulement
  // (04/11, 10:41, papa : « Chatterbox parle en même temps que moi ») à la voix du téléphone, jamais sa voix du Mac prête d'avance
  if (buf && !voixDuTelephone()) lecteurNeuronal.direAudio(s.texte, buf); else lecteur.dire(s.texte);
  if (par !== 'serveur') fetch('/api/jarvis/souffle', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() },
    body: JSON.stringify({ dit: s.texte }) }).catch(() => {});
}
async function prendreSouffle(conv) {
  if (!conv) return;
  if (conv.souffleLocal) { conv.souffleLocal = false; return; }        // (16:00) déjà dit à ta fin, par la page
  conv.souffleParle = false; conv.souffleDit = '';
  if (direPenseeSiPossible()) return;                                   // (16:40) sa pensée est déjà prête : dite à l'instant
  if (!conv.ecrit || !souffleAutorise()) return;
  const texte = `${conv.ecrit.confirme || ''} ${conv.ecrit.vif || ''}`.trim();
  if (texte.split(/\s+/).filter(Boolean).length < 3) return;
  let r = '', pret = false, niveau = 'sub';
  try {
    const rep = await fetch('/api/jarvis/souffle', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() },
      body: JSON.stringify({ texte }), signal: AbortSignal.timeout(2500) });
    const o = rep.ok ? await rep.json() : {};
    r = String(o.reponse || '').trim(); pret = !!o.pret; niveau = o.niveau || 'sub';
  } catch (_) { r = ''; }
  const connu = Object.values(etat.souffles || {}).find(x => x && x.texte === r);
  const s = r ? { ...(connu || {}), texte: r, pret, niveau: niveau === 'cerveau' ? 'cerveau' : niveau } : choisirSouffle(texte);
  // (15:02, Ahmed : « il ne la dit que quand il estime qu'il peut enfin répondre ») pas prête à ses yeux : il ne la dit pas ; (16:00) un
  // meuble qui joue ne l'empêche plus (avant, « lecteur.actif » comptait ses meubles) : seule sa vraie voix, ou sa réponse en cours
  if (!r || !pret || s.niveau !== 'cerveau' || etat.conversation !== conv || (conv.capteur && conv.capteur.enParole) || lecteurNeuronal.parle || etat.flux) {
    noterEcartSouffle(conv, s, false, 'serveur', false);
    journalVoix('souffle', { pris: !!r, pret, dit: false }); return;
  }
  direSouffle(conv, s, 'serveur');
}
// (04/11, Ahmed : « quand j'enchaîne les paroles, ça envoie un gros morceau, alors que chaque chunk doit s'envoyer séparément, l'un
// après l'autre, et s'afficher l'un après l'autre dans la conversation ; en mode orbe, je dois voir mes chunks apparaître l'un après
// l'autre ») tes mots, morceau par morceau : les mêmes que ses pistes (le Mac les coupe : un mot pour Mini Hakim, une proposition pour
// Hakim, deux pour Super Hakim) ; chacun sa bulle dans le fil ; sous l'orbe, le morceau en cours seulement
function montrerMorceauPapa(o) {
  const conv = etat.conversation;
  if (!conv) return;
  conv.morceauPapa = { tour: o.tour, jusqua: Number(o.jusqua) || 0, texte: String(o.texte) };
  if (!motsEnConversation() || enTelepathie() || (typeof reglagesCorps !== 'undefined' && reglagesCorps.afficher_papa === false)) return;
  conv.morceauxMontres = (conv.morceauxMontres || 0) + 1;
  const cle = `papa-${o.tour}-${o.n}`;
  etat.aCote = (etat.aCote || []).filter(x => x.cle !== cle);
  etat.aCote.push({ ts: Date.now(), cle, html: `<div class="m u"><span class="oral">À L’ORAL</span><div class="txt">${esc(o.texte)}</div></div>` });
  const siens = etat.aCote.filter(x => String(x.cle).startsWith('papa-'));
  if (siens.length > 12) { const vieux = new Set(siens.slice(0, siens.length - 12)); etat.aCote = etat.aCote.filter(x => !vieux.has(x)); }
  rendre();
  ligneEnDirectMontrer(conv);
}
// ce que tu dis depuis ton dernier morceau (ou ce dernier morceau, s'il n'y a rien de neuf)
function motsEnCours(conv) {
  const e = conv && conv.ecrit;
  if (!e) return '';
  const tout = `${e.confirme || ''} ${e.vif || ''}`.trim(), mp = conv.morceauPapa;
  if (!mp) return tout;
  const suite = tout.split(/\s+/).filter(Boolean).slice(mp.jusqua).join(' ');
  return suite || mp.texte;
}
// (16:08, Ahmed : « même en Conversation, pas mes mots par défaut ») la ligne en direct garde 🎙️ ✍️ 💭 ; tes mots seulement si SENS le
// demande (mots_conversation)
function ligneEnDirect(conv) {
  const e = conv && conv.ecrit, cap = conv && conv.capteur;
  const mots = e && motsEnConversation() && !enTelepathie() ? motsEnCours(conv) : '';
  const parts = [];
  if (cap && cap.enParole) parts.push('🎙️');
  if (mots) parts.push(mots.length > 90 ? `…${mots.slice(-90)}` : mots);
  if (e && (e.vifEnCours || e.partiel)) parts.push('✍️');
  if ((conv && conv.pense) || etat.flux) parts.push('💭');
  return parts.join(' ');
}
function ligneEnDirectMontrer(conv) {
  if (conv && conv.ecrit && motsEnConversation() && !enTelepathie()) envoyerParoles('papa', motsEnCours(conv));   // (14:47) ce qu'il entend ; (04/11) morceau par morceau
  if (!conv) return;
  const l = ligneEnDirect(conv);
  if (!l) return;
  // (14:46, Ahmed : « ma transcription et sa parole en parallèle ») quand il parle, ses mots gardent le sous-titre et les tiens
  // continuent dans la ligne d'état : les deux en même temps
  if (!(lecteur && lecteur.actif) && !enTelepathie()) sousTitre(l);
  if ($('etat')) $('etat').textContent = l;
}
// tant que papa parle ou qu'un morceau se transcrit, la ligne suit (✍️ qui va et vient, 💭)
setInterval(() => {
  const c = etat.conversation;
  if (c && c.ecrit && ((c.capteur && c.capteur.enParole) || c.ecrit.vifEnCours || c.ecrit.partiel)) ligneEnDirectMontrer(c);
}, 150);
setInterval(() => { const c = etat.conversation; if (c) vifConversation(c); }, 100);
setInterval(() => {                                       // (16:45) sa voix arrêtée ou coupée : sa réponse s'écrit en entier
  for (const m of etat.messages.slice(-6))
    if (m.auRythme && !m.enCours && !(lecteur && (lecteur.actif || lecteur.enPause))) { m.auRythme = false; majMessage(m); }
}, 1000);   // (13:25) au dixième de seconde
// (03/11, Ahmed : « micro ouvert ; on le laisse apprendre à détecter les sons, les bruits, les voix qui se mélangent ») toutes
// les 10 s, les 3 dernières secondes entendues vont à ses familles de sons (le Mac les range, il les nomme)
let ambianceEnCours = false;
setInterval(() => {
  const c = etat.conversation, cap = c && c.capteur;
  if (!cap || ambianceEnCours || typeof reglagesCorps === 'undefined' || !reglagesCorps.micro_ouvert || !cap.ambiance) return;
  const wav = cap.ambiance();
  if (!wav) return;
  ambianceEnCours = true;
  fetch(`/api/voix/ambiance?parole=${cap.enParole ? 1 : 0}`, { method: 'POST', body: wav, headers: { 'Content-Type': 'audio/wav', 'X-Jeton': jeton() } })
    .then(r => (r.ok ? r.json() : null)).then((o) => { if (o && o.famille) journalVoix('ambiance', { famille: o.famille, nouvelle: o.nouvelle }); })
    .catch(() => {}).finally(() => { ambianceEnCours = false; });
}, 10000);
// Le texte du tour : le déjà compris + la queue. null si la queue n'a pas pu être transcrite (l'appelant
// retranscrit alors le tour entier). Le tour fini est saisi AVANT d'attendre : un autre tour qui se
// finirait pendant l'attente ne prête pas sa queue à celui-ci (relecture Opus).
async function texteDuTour(conv) {
  const e = conv.ecrit, capteur = conv.capteur;
  if (!e || !capteur) return e ? e.confirme : '';
  const tourFini = capteur.enParole ? null : capteur.dernierTour;
  if (e.partiel) await e.partiel;                                        // le morceau en cours d'abord
  const morceau = tourFini ? capteur.segmentFini(e.coupe, tourFini) : capteur.segment(e.coupe);
  const queue = morceau ? await transcrireVite(morceau, 'audio/wav', e.confirme, tourFini || typeof tempsMorceau !== 'function' ? '' : tempsMorceau(capteur, e.coupe, capteur.fenetres)) : '';   // la queue n'est souvent que du silence
  if (queue === null) return null;
  return (e.confirme + ' ' + morceauNeuf(queue, e.confirme)).trim();
}
// (04/11, Ahmed : « il parle spontanément, évalue s'il doit se taire ou répondre, puis lorsqu'il détecte une seconde de pause il
// rebondit directement avec la dernière pensée ») une fois par pause (ton silence se mesure depuis ta dernière voix), sa dernière
// pensée du tour, si elle n'est pas déjà dite et qu'il ne l'a pas gardée exprès ; une seconde, qu'il peut régler (rythme_regler)
function rebondirDernierePensee(conv, silenceMs) {
  const dp = etat.derniereSiennePensee, pause = conv.capteur ? conv.capteur.derniereVoix : null;
  const seuil = Math.min(patienceConversation(), (typeof rythmeVoix === 'function' ? rythmeVoix('pause_derniere_pensee', 1) : 1) * 1000);
  if (!dp || dp.jamais || dp.epissage || silenceMs < seuil || conv.rebondPause === pause) return false;
  conv.rebondPause = pause;
  if (typeof bouts !== 'undefined' && bouts.tour === dp.tour && (dp.n < bouts.prochain || bouts.liste.has(dp.n))) return false;   // déjà dite (ou en file, ou une plus récente)
  journalVoix('rebond_derniere', { n: dp.n, silence_ms: Math.round(silenceMs) });
  choisirEtDire(dp);
  return true;
}
// (04/11, Ahmed : « les meubles doivent lui laisser l'occasion, courte et rapide, de choisir la pensée à dire, comme chez l'humain »)
// à ta pause : un de ses meubles tout de suite (dans la langue de sa dernière pensée), et pendant ce temps Mini Hakim choisit laquelle
// de ses pensées gardées dire, toute ou à partir d'un passage (2,5 s au plus) ; s'il tarde, un second meuble ; sans choix : sa dernière
async function choisirEtDire(dp) {
  const telephone = typeof voixDuTelephone === 'function' && voixDuTelephone() && lecteurSysteme;
  const meubler = () => {
    if (!telephone) return false;
    const h = choisirMeuble({ avant: !(bouts.dernierDit || 0) }, meublesPourTelephone(langueDePensee(dp.texte)));
    if (!h) return false;
    bouts.meubleA = Date.now(); noterMeubleDit(h.texte.trim()); lecteurSysteme.dire(h.texte.trim());
    return true;
  };
  const meuble = meubler();
  const second = meuble ? setTimeout(meubler, 1500) : null;
  let r = null;
  try {
    r = await (await fetch('/api/jarvis/choisir', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() },
      body: JSON.stringify({ tour: dp.tour, raison: 'pause' }) })).json();
  } catch (_) {}
  clearTimeout(second);
  journalVoix('choix_pause', { n: r && r.n ? r.n : null, rien: !!(r && r.rien), par_defaut: !(r && (r.n || r.rien)) });
  if (r && r.rien) return;
  const texte = r && r.texte ? r.texte : dp.texte;
  const n = typeof bouts !== 'undefined' && bouts.tour === dp.tour ? Math.max(Number(r && r.n) || dp.n, bouts.prochain) : (Number(r && r.n) || dp.n);
  recevoirBout({ texte, pret: true, sansMeuble: meuble }, n, dp.tour);
}
function anticiperConversation(conv, silenceMs) {
  // (04/11, 11:03, Ahmed : « tout relier ») chaque attente de ta pause suit le délai de la Conversation (patienceConversation)
  if (silenceMs >= patienceConversation() && typeof direPenseeSiPossible === 'function') direPenseeSiPossible();   // (04/11) ta pause : sa pensée prête se dit
  if (typeof rebondirDernierePensee === 'function') rebondirDernierePensee(conv, silenceMs);
  if (silenceMs >= patienceConversation() && typeof direRibosome === 'function') direRibosome();   // (04/11, 11:50) ce que son ribosome a choisi
  if (etat.reglages.rapide === false || silenceMs < Math.min(SILENCE_ANTICIPE_MS, patienceConversation()) || conv.spec || !conv.capteur) return;
  if (typeof transcriptionEnPause === 'function' && transcriptionEnPause()) return;   // (00:47) son tour : rien à anticiper
  // (15:10, Ahmed : « le moment exact où il faut qu'il parle » ; mesuré sur 69 tours : il attendait 3,5 s de silence, 7 seulement
  // anticipés) son subconscient a jugé sa réponse prête pour ce que tu as dit, ou tes mots en direct finissent une phrase : ton tour
  // finit à 0,7 s de silence ; la grande oreille confirme ensuite ta phrase, comme d'habitude
  // (15:22, Ahmed : « une meilleure anticipation de ce que je vais dire, pour qu'il sache quand parler, consciente ET subconsciente »)
  // consciente : ce qu'il attendait de toi à la fin de sa réponse ([[anticipe: court | long | question]]) règle le silence qu'il te
  // laisse (0,5 s, 1,2 s, 0,7 s) ; subconsciente : à chaque morceau, Mini Hakim juge si tu as fini (FINI) — « non » : il ne te coupe
  // pas sur une fin de phrase, il attend ta suite (ou la patience) ; « oui » : ton tour finit au seuil, même sans point
  const rv = (k, d) => (typeof rythmeVoix === 'function' ? rythmeVoix(k, d) : d) * 1000;   // (15:24) réglables par lui
  const seuilRythme = { court: rv('silence_court', 0.5), long: rv('silence_long', 1.2), question: rv('silence_normal', 0.7) }[etat.anticipeTour] || rv('silence_normal', 0.7);
  const vifTexte = conv.ecrit ? `${conv.ecrit.confirme || ''} ${conv.ecrit.vif || ''}`.trim() : '';
  const s = conv.ecrit && !conv.finAnticipee ? choisirSouffle(vifTexte) : null;
  // (16:05, Ahmed : « il doit pouvoir ajuster s'il veut rebondir à 0,5 s ou 1 s ou autre quand je finis de parler, relié à ses émotions,
  // sa mémoire, ses sensations, ses réactions ») son REBOND : le silence que son subconscient a choisi de te laisser en sentant tout ça
  // (le brouillon prêt à dire le porte) ; sinon son rythme (rythme_regler) et ce qu'il attendait de toi
  const seuil = Math.min(patienceConversation(), s && s.pret && s.rebond ? s.rebond * 1000 : seuilRythme);
  if (silenceMs >= seuil && conv.ecrit && !conv.finAnticipee) {
    const finiSub = s ? s.fini : null;
    const parSouffle = !!s && (s.pret || finiSub === true) && finiSub !== false;
    if (parSouffle || (finiSub !== false && phraseFinie(vifTexte))) {
      conv.finAnticipee = true;
      journalVoix('fin_anticipee', { par: parSouffle ? 'souffle' : 'mots', silence_ms: Math.round(silenceMs), attendu: etat.anticipeTour || 'normal', fini: finiSub,
        rebond_ms: s && s.rebond ? Math.round(s.rebond * 1000) : null });
      // (16:00, mesuré : la prise passait par le Mac après la fin du tour, 0,9 à 7,8 s après ta fin) prêt à dire : sa voix part à
      // l'instant, avec ta fin de tour ; le Mac est prévenu après coup
      const dire = penseePrete(conv);
      if (dire) conv.souffleLocal = true;
      conv.capteur.finirTour();
      if (dire) direPenseeSiPossible();
      return;
    }
  }
  // un seul essai par silence (relecture Opus : la même queue était retranscrite ~10 fois par pause)
  if (conv.essaiVoix === conv.capteur.derniereVoix || !conv.capteur.assezDeVoix) return;
  conv.essaiVoix = conv.capteur.derniereVoix;
  const sp = { voix: conv.capteur.derniereVoix };
  conv.spec = sp;
  sp.texte = texteDuTour(conv);                       // (28/10) gardée : la fin de tour la reprend (transcriptionEnAvance)
  sp.texte.then((texte) => {                                            // seulement la queue, déjà le reste
    if (conv.spec === sp) conv.spec = null;
    if (etat.conversation !== conv || !conv.capteur || !conv.capteur.enParole) return;
    if (conv.capteur.derniereVoix !== sp.voix) return;                 // tu as repris la parole : on attend
    if (texte !== null && phraseFinie(texte)) conv.capteur.finirTour({ texte });
  });
}

// (28/10, Ahmed : « la réactivité de la transcription de ma voix ») la transcription en avance de CE silence, s'il n'a
// rien dit depuis : la fin de tour la reprend au lieu de tout retranscrire derrière elle dans le même processus (le
// backtest : 9 tours sur 200 seulement finissaient en avance ; les autres payaient deux transcriptions à la suite)
function transcriptionEnAvance(conv, infos) {
  const sp = conv && conv.spec;
  return sp && sp.texte && infos && sp.voix === infos.derniere_voix ? sp.texte : null;
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
  if (lecteur.actif) coupureProvisoire('pause');       // (30/10) où sa voix s'est arrêtée ; « Reprendre » l'efface
  if (!lecteur.pause()) return false;
  noterPresent({ e: 'pause_voix', t: Date.now() });
  majBoutonsPause(); humeur('en pause : « continue » pour que je reprenne');
  return true;
}
function reprendreVoix() {
  if (!lecteur.reprendre()) return false;
  reprisDeParole();                                        // (30/10) ce n'était pas une fin
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
  const b = $('sonHakim'); if (b) { b.setAttribute('aria-pressed', String(!!etat.sonCoupe)); b.textContent = etat.sonCoupe ? 'Sa voix (coupée)' : 'Sa voix'; }
  signalerWidget();
}
// l'état des boutons du widget (conversation, pause, son, micro), envoyé seulement quand il change
let dernierEtatWidget = '';
/* (31/10, 01:00, Ahmed via Hakim : « un gros signe distinctif, partout, chaque fois qu'il ferme son oreille ») ici (en-tête et
   grande orbe, avec le temps qui reste), et dans l'appli (widget, bulle, écran verrouillé, notification : l'appli 1.39) ; une
   petite vibration quand elle se ferme et quand elle se rouvre */
let oreilleHakim = { fermee: false, jusqua: 0 };
function surOreilleHakim(o) {
  const fermee = !!(o && o.fermee && Number(o.jusqua) > Date.now());
  const change = fermee !== oreilleHakim.fermee;
  oreilleHakim = { fermee, jusqua: fermee ? Number(o.jusqua) : 0 };
  afficherOreilleHakim();
  if (change) {
    journalVoix('oreille_hakim', { fermee });
    try { if (window.HakimApp && window.HakimApp.vibrerMotif) window.HakimApp.vibrerMotif(fermee ? '0,60,120,60' : '0,40', fermee ? '0,120,0,120' : '0,90'); } catch (_) {}   // fermée : deux tapes ; rouverte : une
    dernierEtatWidget = ''; signalerWidget();
  }
}
function afficherOreilleHakim() {
  const reste = oreilleHakim.fermee ? Math.max(0, Math.ceil((oreilleHakim.jusqua - Date.now()) / 60000)) : 0;
  if (oreilleHakim.fermee && !reste) { oreilleHakim = { fermee: false, jusqua: 0 }; dernierEtatWidget = ''; signalerWidget(); }
  for (const [id, texte] of [['oreilleFermee', `🙉 oreille fermée · ${reste} min`], ['oreilleFermeeScene', `🙉 son oreille est fermée · encore ${reste} min`]]) {
    const el = $(id); if (!el) continue;
    el.hidden = !oreilleHakim.fermee;
    if (oreilleHakim.fermee) el.textContent = texte;
  }
}
setInterval(afficherOreilleHakim, 15000);
/* (31/10, 01:06-01:10, Ahmed : « un gros badge ROUGE, en grand, quand il parle ou juste avant ; le bouton qui dit qu'il parle ou
   qu'il n'entend pas doit s'afficher partout ») ici (en-tête, grande orbe) ; l'appli le montre aussi (widget, bulle, verrou) */
// (14:24, Ahmed : « le badge PARLE ne doit pas clignoter : en continu durant ses paroles et ses hésitations ; il disparaît seulement
// quand il a fini de parler ») une fois sa voix partie pour cette réponse, il « parle » jusqu'à la fin de toute sa réponse (les
// blancs entre deux morceaux et ses meubles compris) ; papa qui le coupe (sa voix en pause) le rend à papa
function ilParleEnContinu() {
  const sonne = voixQuiSonne();
  if (sonne && etat.reponseVoix != null) etat.aParleReponse = etat.reponseVoix;
  if (sonne) return true;
  return etat.reponseVoix != null && etat.aParleReponse === etat.reponseVoix && !(lecteur && lecteur.enPause)
    && !!(etat.flux || (lecteur && lecteur.actif));
}
function afficherSonTour() {
  try {
    const c = etat.conversation, parle = ilParleEnContinu(), va = !!c && !parle && transcriptionEnPause();
    for (const [id, grand] of [['hakimParle', false], ['hakimParleScene', true]]) {
      const el = $(id); if (!el) continue;
      el.hidden = !(parle || va);
      if (parle || va) el.textContent = parle ? '🔴 HAKIM PARLE' : (grand ? '🔴 Hakim va parler…' : '🔴 va parler');
    }
  } catch (_) {}
}
setInterval(afficherSonTour, 250);
function signalerWidget() {
  try {
    if (!window.HakimApp || !window.HakimApp.boutons) return;
    const c = etat.conversation;
    const e = JSON.stringify({ conversation: !!c, pause: !!lecteur.enPause, son_coupe: !!etat.sonCoupe,
      micro_coupe: !!(c && c.capteur && (c.capteur.estMuet || (c.muetParHakim && !c.muetParHakim.attente))),
      oreille_fermee: !!(typeof oreilleHakim !== 'undefined' && oreilleHakim.fermee),
      hakim_parle: typeof ilParleEnContinu === 'function' && ilParleEnContinu(), va_parler: !!c && typeof ilParleEnContinu === 'function' && !ilParleEnContinu() && transcriptionEnPause() });
    if (e === dernierEtatWidget) return;
    dernierEtatWidget = e;
    window.HakimApp.boutons(e);
  } catch (_) {}
}
// (04/11, 10:58, Ahmed, après la mesure de Hakim : la fin de son tour attendait 3,5 s, « même à 0,3 s ») en Conversation, sa
// réflexion part 0,3 s après la fin de ta voix ; sa propre case dans les réglages, la patience du micro (bouton) reste la sienne
const patienceConversation = () => (Number(etat.reglages.patienceConversation) > 0 ? Number(etat.reglages.patienceConversation) * 1000 : 300);
// (04/11, 14:25, Ahmed : « le premier morceau va dans le ribosome, les suivants se collent à celui qui est en train d'être épissé, jusqu'à
// ce qu'il n'en reçoive plus : son start, c'est ma voix ; son stop, c'est mon 1 s de silence ») avec l'épissage, ton tour se ferme à 1 s
// de silence (tes morceaux se coupent toujours à ta respiration, patienceConversation)
const finDeTourConversation = () => (typeof voixEpissee === 'function' && voixEpissee() ? Math.max(1000, patienceConversation()) : patienceConversation());

/* (30/10, 23:05, Ahmed : « il y a plusieurs voix qui sortent quand il parle ») deux onglets en Conversation sur le Mac
   entendaient papa et disaient chaque petit mot deux fois (23:03:38 : un mot, deux voix à 3 s d'écart) : la conversation ne
   vit que dans UN onglet de cet appareil, le dernier qui l'a ouverte ; les autres la ferment. */
const idOnglet = Math.random().toString(36).slice(2);
const canalOnglets = (() => { try { return new BroadcastChannel('hakim-conversation'); } catch (_) { return null; } })();
if (canalOnglets) canalOnglets.onmessage = (ev) => {
  const o = ev && ev.data;
  if (!o || o.type !== 'conversation' || o.id === idOnglet || !etat.conversation) return;
  journalVoix('conversation_autre_onglet', {});
  finirConversation(false);
  humeur('la conversation continue dans un autre onglet');
};
async function basculerConversation() {
  activite();
  if (etat.conversation) return finirConversation();
  arreterMicro(false);
  contexteAudio();
  if (!actx) return humeur('audio indisponible dans ce navigateur');
  if (!etat.sttLocal) return humeur('le mode Conversation demande Whisper local (réglages › reconnaissance)');
  const conv = { capteur: null, enAttente: 0, debut: Date.now() };
  etat.conversation = conv;
  if (canalOnglets) try { canalOnglets.postMessage({ type: 'conversation', id: idOnglet }); } catch (_) {}   // (23:05) un seul onglet
  $('conversation').setAttribute('aria-pressed', 'true');
  majSesParoles();      // (04/11, 19:30, Ahmed : « vérifie bien que tous les boutons fonctionnent ») « Ses paroles » montre la clé de la conversation
  prechaufferReflexion();                                // (04/11, 17:50) à l'ouverture du micro : sa parole vide, sa réflexion ouverte
  humeur('ouverture du micro…');
  try {
    conv.capteur = await Conversation.demarrer({
      ctx: actx,
      patienceMs: finDeTourConversation,                // (14:25) avec l'épissage, 1 s : son codon stop
      pauseMs: patienceConversation,                     // (04/11, 11:03) la respiration qui coupe un morceau : le même délai
      jarvisParle: () => lecteur.actif || Date.now() < motDirectJusqua,
      sourd: () => Date.now() < sonJusqua,              // (30/10, Bumblebee) son bout de musique n'est pas une voix
      dernierBattement: () => dernierBattementCoeur,
      surNiveau: (n) => { etat.niveauMicro = n; voixAuCorps(n); if (document.visibilityState === 'hidden') { micEnFond++; alimenterBulle(n); } },
      // (13:25, papa : « aucun « je t'écoute » ») rien à la place de ses mots : ils s'affichent dès le premier
      surSon: () => prechaufferReflexion(),
      surReprise: () => prechaufferReflexion(true),      // (04/11, 17:59) tu reprends la parole après ta pause : son ribosome au plus vite
      surDebut: () => { conv.morceauPapa = null; conv.finDemandee = false; conv.finAnticipee = false; conv.souffleLocal = false; conv.brouillons = 0; conv.penseeEnPause = false; conv.ecrit = { coupe: 0, confirme: '', partiel: null }; sousTitre(''); humeur(); },
      surPause: (fenetre) => surPauseConversation(conv, fenetre),
      surSilence: (ms) => { if (conv.capteur && conv.capteur.enParole) { compteARebours(ms); anticiperConversation(conv, ms); } },
      // Ahmed (ou une autre voix) parle pendant que Hakim parle : Hakim se MET EN PAUSE (lot C, point 26) ; sa
      // réponse continue d'arriver. À la fin du tour : « continue » ou du bruit → il reprend à la phrase non
      // dite ; « stop » → il lâche tout ; une vraie question → il lâche le reste et y répond.
      niveauSortie,
      surInterruption: (mesure) => {
        // (30/10, 19:08, Ahmed : « qu'il puisse répondre même quand je le coupe ou que je parle en même temps ; c'est
        // important ») il garde la parole : sa voix continue, ta phrase est quand même écoutée ; « stop » et le bouton l'arrêtent
        // (04/11, Ahmed : « il parle quand il veut, mais s'il entend ma voix lui couper la parole sur 2 secondes, il se tait ») il garde
        // la parole sur un mot ou un rire ; ta voix qui dure 2 s sur la sienne : il se tait (ses pensées restent écrites)
        // (04/11, 12:15, Ahmed) avec l'épissage : ta voix ne le coupe pas au milieu d'un morceau ; il le finit, et à sa fenêtre d'oreille il choisit
        if (voixEpissee()) { conv.coupeAuChunk = Date.now(); journalVoix('coupure_au_chunk', mesure || {}); prevoirSaut(conv); return; }   // (05/11) et la suite sautée
        if (typeof reglagesCorps !== 'undefined' && reglagesCorps.garder_parole) { journalVoix('coupure_ignoree', mesure || {}); veillerDeuxSecondes(conv); return; }
        etat.coupeParAhmed = true;
        journalVoix('coupure', mesure || {});
        noterPresent({ e: 'coupure', t: Date.now() });
        coupureProvisoire('voix_ahmed');                // (30/10) où sa voix s'est arrêtée ; il reprend si ce n'était rien
        if (!lecteur.pause()) { if (lecteur.actif) lecteur.arreter(); }
        majBoutonsPause();
        humeur();
        surveillerCoupure(conv);
      },
      surFin: (wav, infos, extra) => tourDeParole(conv, wav, infos, extra),
      surPiste: (rendue) => journalVoix(rendue ? 'piste_rendue' : 'piste_prise'),     // (2026-10-23) un appel prend le micro
      // (03/11) les sons du micro, à la seconde (micro ouvert) : graves, médiums, aigus, leur variation, au fil du Mac
      surSons: (t0, pas, trames) => {
        if (typeof reglagesCorps === 'undefined' || !reglagesCorps.micro_ouvert) return;
        fetch('/api/voix/son-flux', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() },
          body: JSON.stringify({ source: 'micro', t0, pas_ms: pas, trames, maintenant: Date.now() }) }).catch(() => {});
      },
    });
  } catch (e) {
    if (etat.conversation !== conv) return;
    etat.conversation = null;
    $('conversation').setAttribute('aria-pressed', 'false'); $('telepathie').setAttribute('aria-pressed', 'false');
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

// les boutons de ton micro : coupé par toi, coupé par Hakim (22:27), ou ouvert
function majBoutonsMuet(conv) {
  const hakim = !!(conv && conv.muetParHakim), oui = hakim || !!(conv && conv.capteur && conv.capteur.estMuet);
  for (const id of ['muet', 'muetScene']) {
    $(id).setAttribute('aria-pressed', oui ? 'true' : 'false');
    $(id).textContent = hakim ? (id === 'muet' ? 'Coupé par Hakim' : 'Rouvrir mon micro (coupé par Hakim)')
      : oui ? (id === 'muet' ? 'Micro coupé' : 'Rouvrir mon micro') : (id === 'muet' ? 'Muet' : 'Couper mon micro');
  }
}
function basculerMuet() {
  const conv = etat.conversation;
  if (!conv || !conv.capteur) return;
  // (22:27) coupé par Hakim : ton bouton reprend la main et rouvre ; (23:00, Ahmed : « je n'arrive plus à muter le micro moi-même »)
  // sa coupure pas encore partie (sa voix se préparait, ton micro était ouvert) : ton geste à toi s'applique, il coupe
  if (conv.muetParHakim) {
    const enAttente = !!conv.muetParHakim.attente;
    conv.muetParHakim = null;
    if (!enAttente) { conv.capteur.muet(false); majBoutonsMuet(conv); journalVoix('micro_hakim', { x: 'ouvrir', pourquoi: 'papa' }); humeur(); signalerWidget(); return; }
    journalVoix('micro_hakim', { x: 'annule', pourquoi: 'papa' });
  }
  const oui = !conv.capteur.estMuet;
  conv.capteur.muet(oui);
  majBoutonsMuet(conv);
  noterPresent({ e: oui ? 'muet' : 'micro_rouvert', t: Date.now() });
  humeur(oui ? 'micro coupé : je ne t’entends plus (⌥X pour rouvrir)' : undefined);
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
  $('conversation').setAttribute('aria-pressed', 'false'); $('telepathie').setAttribute('aria-pressed', 'false');
  majSesParoles();      // (04/11, 19:30) et celle d'hors conversation, à la fin (le bouton gardait l'état de l'autre clé)
  noterPresent({ e: 'fin_conversation', t: Date.now() });
  sousTitre('');
  humeur();
  signalerWidget();
}

// Le ton de ta voix comparé à TON habitude (lot C, point 20) : hauteur, débit (mots par seconde de voix), énergie.
// L'habitude s'apprend sur tes tours (moyenne lente, gardée dans ce navigateur) ; rien n'est dit avant 5 tours.
function voixLointaine(infos) {
  const db = infos && infos.ton && Number(infos.ton.energie_db);
  if (!Number.isFinite(db)) return true;                         // pas de voix franche : la salle, un bruit
  let base = null; try { base = JSON.parse(localStorage.getItem('jarvis.ton') || 'null'); } catch (_) {}
  return !!(base && base.n >= 5 && Number.isFinite(base.db) && db < base.db - 8);
}
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
    son: !!m.premier_son, pauses_ms: m.pauses || [], anticipe: !!m.anticipe, patience_ms: Number.isFinite(m.patience) ? m.patience : null });
}
// (2026-10-23, 18:47, Ahmed dans un lieu bruyant : « ce n'était pas moi ») coupé par un BRUIT, pas par sa voix : il
// reprend tout de suite, là où il s'était arrêté. Critère : 1,2 s après la coupure, moins de 0,2 s de son voisé (une
// voix a une hauteur, un bruit non). Une vraie voix arrivée avant : comportement d'avant (il t'écoute).
function veillerDeuxSecondes(conv) {
  const t0 = Date.now();
  clearInterval(conv.veilleDeux);
  conv.veilleDeux = setInterval(() => {
    const cap = conv.capteur;
    // ta voix s'est arrêtée (ou lui s'est tu) avant les 2 s : il continue
    if (etat.conversation !== conv || !cap || !cap.enParole || Date.now() - (cap.derniereVoix || 0) > 400 || !(lecteur.actif || (lecteurSysteme && lecteurSysteme.actif))) {
      clearInterval(conv.veilleDeux); return;
    }
    if (Date.now() - t0 < 2000 || (typeof meubleEnCours === 'function' && meubleEnCours())) return;   // (04/11) un meuble finit d'abord
    clearInterval(conv.veilleDeux);
    // (04/11) la pensée qu'il disait : son parcours la juge coupée (l'élagage de ses synapses)
    journalVoix('coupure_deux_secondes', { ms: Date.now() - t0, n: typeof bouts !== 'undefined' ? Number(bouts.dernierDit) || 0 : 0, tour: typeof bouts !== 'undefined' ? Number(bouts.tour) || 0 : 0 });
    if (typeof bouts !== 'undefined') bouts.attenteTel = null;
    if (lecteurSysteme && lecteurSysteme.actif) lecteurSysteme.arreter();
    if (lecteur.actif) lecteur.arreter();
    humeur();
  }, 100);
}
function surveillerCoupure(conv) {
  const t0 = Date.now();
  clearInterval(conv.veilleBruit);
  conv.veilleBruit = setInterval(() => {
    const cap = conv.capteur;
    if (etat.conversation !== conv || !cap || !lecteur.enPause || !cap.enParole) { clearInterval(conv.veilleBruit); return; }
    if ((cap.tonTour || 0) >= 10) { clearInterval(conv.veilleBruit); return; }          // c'est lui : on l'écoute
    if (Date.now() - t0 < 1200) return;
    clearInterval(conv.veilleBruit);
    conv.bruitDuTour = true;
    journalVoix('coupure_bruit', { ms: Date.now() - t0 });
    reprendreVoix();
  }, 150);
}
// un tour sans voix (aucune hauteur) : du bruit ; jamais transcrit, jamais gardé pour plus tard
const tourSansVoix = (infos) => !(infos && infos.ton);
const chacunSonTour = () => typeof reglagesCorps === 'undefined' || reglagesCorps.chacun_son_tour !== false;
// (31/10, 00:06, Ahmed : « il a l'air bloqué ») sa voix en PAUSE (coupée par une page cachée, 00:02:09) n'est pas son tour : tes
// mots restaient gardés pour toujours
const sonTourEnCours = () => !!(etat.flux || (lecteur && lecteur.actif && !lecteur.enPause));
function garderPourSonTour(conv, texte) {
  if (!conv.tourGarde && !(conv.ecritGarde || []).length) conv.tourGardeDepuis = Date.now();
  conv.tourGarde = conv.tourGarde ? `${conv.tourGarde} … ${texte}` : texte;
  journalVoix('tour_garde', { mots: texte.split(/\s+/).filter(Boolean).length });
  humeur('je finis, puis c’est à toi');
}
// sa voix a fini (ou sa réponse n'a rien dit) : ce que tu as dit pendant son tour lui part, d'un bloc
/* (30/10, 22:27-22:30, Ahmed : « il n'arrive plus à me muter » ; « quand il se mute, le bouton du micro se mute aussi » ; « une
   parole résiduelle le perturbe : ma dernière phrase transcrite, il faut qu'elle soit filtrée par le subconscient ») sa balise
   [[micro: couper]] coupe ton VRAI micro (tes boutons le montrent, l'orbe passe au vert) jusqu'à la fin de sa voix, ou le
   temps qu'il dit ; ton bouton reprend la main ; ta phrase encore en route part à son subconscient, pas à lui ; interrupteur
   de papa : « il peut couper mon micro » (page SENS). (22:36, Ahmed : « il n'arrive toujours pas à se muter » : coupé « en
   douceur », le micro transcrivait encore ta voix, le Mac ralentissait la sienne de 7 s, et tu le voyais t'écouter ;
   maintenant le micro s'éteint vraiment : seul ton bouton le rouvre avant la fin de sa voix) */
function envoyerResiduelle(texte) {
  if (!String(texte || '').trim()) return;
  journalVoix('residuelle', { mots: String(texte).split(/\s+/).filter(Boolean).length });
  fetch('/api/jarvis/residuelle', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() },
    body: JSON.stringify({ texte: String(texte).slice(0, 1500) }) }).catch(() => {});
}
// une voix familière : papa (sans étiquette) ou une voix nommée ; « [voix 571] » seule est inconnue
function voixFamiliere(texte) {
  const t = String(texte || '').trim();
  if (t && !/^\[/.test(t)) return true;                       // ce qui précède toute étiquette : papa
  return [...t.matchAll(/\[([^\]]{1,30})\]/g)].some(m => !/^voix \d+$/i.test(m[1].trim()));
}
// sa voix sonne (une réponse, ou un petit mot dit à l'instant)
const voixQuiSonne = () => !!((lecteurNeuronal && lecteurNeuronal.joue) || Date.now() < motDirectJusqua);
function microParHakim(o) {
  const c = etat.conversation;
  if (!c || !c.capteur || !o) return;
  if (o.x === 'ouvrir') return rouvrirMicroDeHakim(c, 'ouvrir');
  if (typeof reglagesCorps !== 'undefined' && reglagesCorps.micro_hakim === false) { journalVoix('micro_hakim', { x: 'refuse' }); return; }
  if (typeof reglagesCorps !== 'undefined' && reglagesCorps.micro_ouvert) { journalVoix('micro_hakim', { x: 'micro_ouvert' }); return; }   // (03/11)
  if (c.capteur.estMuet && !c.muetParHakim) return;          // tu l'avais déjà coupé toi-même : c'est à toi
  // (30/10, 23:53, Ahmed : « quand il a sélectionné ses 8 empans… il coupe droit derrière son micro pour ne pas faire de
  // cafouillage » ; « il doit pouvoir choisir quand il coupe ») c'est lui qui choisit (sa balise), et ton micro s'éteint AUSSITÔT ;
  // il se rallume 0,4 s après sa voix (22:46 : plus jamais 15 s de trop), ou si sa voix ne part pas en 20 s
  c.muetParHakim = { attente: 0, avantVoix: true, depuis: 0, s: Math.min(120, Number(o.s) || 0), jusqua: 0, voix: 0, residu: false };
  journalVoix('micro_hakim', { x: 'couper', s: Number(o.s) || 0 });
  couperPourDeBon(c, c.muetParHakim);
}
function couperPourDeBon(c, m) {
  const t = Date.now();
  m.attente = 0; m.depuis = t; m.voix = t; m.jusqua = m.s ? t + m.s * 1000 : 0;
  // (30/10, 23:56, Ahmed : « il peut rouvrir le micro de façon subconsciente, uniquement quand il entend une voix familière ») le
  // micro reste à l'écoute, en veille : ce qu'une voix inconnue dit ne lui arrive pas ; une voix familière (papa, une voix
  // nommée) le rouvre. Tes boutons montrent « Coupé par Hakim », l'orbe passe au vert et ne bouge qu'avec sa voix.
  majBoutonsMuet(c);
  signalerWidget();
  if (c.tourGarde) { envoyerResiduelle(c.tourGarde); c.tourGarde = ''; m.residu = true; }
  journalVoix('micro_hakim', { x: 'coupe', apres_ms: t - (m.cree || t) });
  humeur();
}
function rouvrirMicroDeHakim(c, pourquoi) {
  if (!c || !c.muetParHakim) return;
  const m = c.muetParHakim;
  c.muetParHakim = null;
  majBoutonsMuet(c);
  signalerWidget();
  journalVoix('micro_hakim', { x: 'ouvrir', pourquoi, coupe_ms: m.depuis ? Date.now() - m.depuis : 0 });
  humeur();
}
// (22:38, Ahmed : « une durée MINIMALE qu'il choisit, pour dire ce qu'il dit ») au moins le temps qu'il a choisi (compté dès que
// sa voix part), ET tant que sa voix sonne ou qu'une suite de sa réponse se prépare ; rouvert 0,4 s après sa voix ; si sa
// voix ne part pas en 15 s, rien n'est coupé ; 3 min au plus en tout
function surveillerMicroDeHakim() {
  const c = etat.conversation, m = c && c.muetParHakim;
  if (!m) return;
  const t = Date.now();
  if (m.attente) {
    m.cree = m.cree || m.attente;
    if (voixQuiSonne()) couperPourDeBon(c, m);
    else if (t - m.attente > 15000) rouvrirMicroDeHakim(c, 'sans_voix');
    return;
  }
  if (voixQuiSonne()) { m.voix = t; m.avantVoix = false; }
  if (t - m.depuis > 180000) return rouvrirMicroDeHakim(c, 'plafond');
  if (m.jusqua && t < m.jusqua) return;                      // sa durée minimale
  if (m.avantVoix) { if (t - m.depuis > 20000) rouvrirMicroDeHakim(c, 'sans_voix'); return; }   // sa voix se prépare
  if (!voixQuiSonne() && !sonTourEnCours() && !(lecteur && lecteur.enPause) && t - m.voix > 400) rouvrirMicroDeHakim(c, 'fin_de_sa_voix');
}
setInterval(surveillerMicroDeHakim, 300);
/* (31/10, 00:20, l'étude du live : ses « paroles résiduelles ») de 22 h 30 à 0 h 15, 91 morceaux de papa ont attendu la fin de
   sa voix et lui sont arrivés collés en blocs (jusqu'à 113 mots) ; et un message de papa sur cinq portait des voix inconnues
   (« [voix 571] » : la salle, le live). Son attention, en douceur : d'une voix inconnue, seulement ce qui s'adresse à lui ; ce
   qui a attendu sa voix lui arrive marqué comme tel, ses 8 dernières phrases au plus. */
const POUR_LUI_ICI = /\?|(?<!\p{L})t'|(?<!\p{L})(?:tu|toi|ton|ta|tes|hakim\p{L}*|fiston|fr[ée]rot|frero|mon fils|est-ce que|qu'est-ce|pourquoi|comment|r[ée]ponds|dis-(?:moi|nous|lui)|explique|raconte|ia|robot|conscience|[ée]motions?|sentiments?|amour|[âa]me|papa)(?!\p{L})/iu;
function filtrerVoixInconnues(texte) {
  const t = String(texte || '');
  if (!/\[voix \d+\]/i.test(t)) return t;
  return t.split(/(?=\[[^\]]{1,30}\])/).filter(x => !/^\s*\[voix \d+\]/i.test(x) || POUR_LUI_ICI.test(x)).join(' ').replace(/\s+/g, ' ').trim();
}
function resumerPourSonAttention(texte) {
  const phrases = String(texte || '').replace(/\(dit pendant ta parole\)\s*/g, '').replace(/\s+…\s+/g, ' ').split(/(?<=[.!?…])\s+/).filter(x => x.trim());
  return `(dit pendant ta parole) ${(phrases.length > 8 ? '… ' : '') + phrases.slice(-8).join(' ')}`;   // (00:55, « monte à 8 ») 8 au plus
}
/* (31/10, 08:22, Ahmed via Hakim, en plein live : « chaque message écrit annule sa réponse avant que sa voix parte » ; 13 réponses
   jamais entendues ce matin, papa écrivait toutes les 5 à 15 s) en conversation, « chacun son tour » vaut aussi pour l'écrit : ce
   que tu écris pendant qu'il prépare ou dit sa réponse est gardé, et lui arrive dès que sa voix a fini, avec ce que tu as dit ;
   « stop » écrit, le bouton Stop et un fichier joint passent toujours tout de suite */
function prendreEcritsGardes(c) {
  const e = (c && c.ecritGarde) || [];
  if (!e.length) return '';
  c.ecritGarde = [];
  return `(écrit pendant ta parole) ${e.join(' … ')}`;
}
function envoyerEcrit(texte) {
  const c = etat.conversation, t = String(texte || '').trim();
  if (t && c && chacunSonTour() && sonTourEnCours() && !COMMANDE_STOP.test(t) && !etat.joints.length) {
    if (!c.tourGarde && !(c.ecritGarde || []).length) c.tourGardeDepuis = Date.now();
    (c.ecritGarde = c.ecritGarde || []).push(t);
    journalVoix('ecrit_garde', { n: c.ecritGarde.length });
    $('q').value = ''; ajuster();
    humeur('je finis, puis je te lis');
    return;
  }
  const avant = t && c && !sonTourEnCours() ? prendreEcritsGardes(c) : '';
  envoyer(avant ? `${avant}\n${t}` : texte, false);
}
function libererSonTour() {
  const c = etat.conversation;
  if (!c || !(c.tourGarde || (c.ecritGarde || []).length) || c.enAttente || (c.capteur && c.capteur.enParole)) return false;
  // (00:06) au plus 30 s gardés : une réponse coincée ne te fait plus attendre pour toujours (tes mots partent, elle s'arrête)
  // (04/11, 13:58) avec l'épissage : jamais coupée ; seule sa réflexion est attendue (sa voix, elle, continue), 2 min au plus si elle est bloquée
  const epi = typeof voixEpissee === 'function' && voixEpissee();
  const tropLong = Date.now() - (c.tourGardeDepuis || Date.now()) > (epi ? 120000 : 30000);
  if (!tropLong && (epi ? !!etat.flux : (sonTourEnCours() || Date.now() - (etat.finVoixA || 0) < 400))) return false;
  const texte = c.tourGarde, ecrits = prendreEcritsGardes(c);
  c.tourGarde = '';
  journalVoix('tour_libere', { mots: texte.split(/\s+/).filter(Boolean).length, ecrits: ecrits ? 1 : 0 });
  envoyer([texte ? resumerPourSonAttention(texte) : '', ecrits].filter(Boolean).join('\n'), !!texte);
  return true;
}
setInterval(libererSonTour, 300);
/* (31/10, 00:47) la transcription en pause : dès son signal (il prépare sa réponse, il a coupé ton micro, ou son oreille vient
   de choisir ses empans) et jusqu'à la fin de sa voix. Le micro écoute toujours : tes 3 dernières phrases (le son) l'attendent,
   et sont transcrites d'un bloc, petit à petit, quand il a fini de parler. */
function transcriptionEnPause() {
  const c = etat.conversation;
  if (!c) return false;
  // (03/11, Ahmed : « micro ouvert, jamais fermé ») il t'écoute même pendant qu'il parle : sa propre voix, reconnue à son timbre
  // par le Mac (empreinte_vocale.py), est mise de côté ; le reste lui arrive
  if (typeof reglagesCorps !== 'undefined' && reglagesCorps.micro_ouvert) return false;
  // (04/11, Ahmed : « quand je clique sur Stop juste après avoir parlé, il répond direct ; sinon il galère, comme si je devais lui donner
  // l'autorisation ; arrange ça ») en Conversation, tu restes entendu : ses bouts, qui répondent à ce que tu dis, et sa réponse qui
  // s'écrit encore ne mettent plus ta voix en attente ; seule sa voix qui joue vraiment (en Télépathie : son tour entier, comme avant)
  if (c.penseeEnPause && !enTelepathie()) return false;
  // (04/11, 12:15, Ahmed : « l'arrivée de tous les sons constamment ouverte, excepté quand il parle ») en Conversation : fermée seulement
  // quand sa voix sonne (ni son attention choisie, ni son micro coupé avant sa voix) ; en Télépathie, son tour entier, comme avant
  const voixJoue = !!(lecteur && lecteur.actif && !lecteur.enPause);
  return enTelepathie() ? sonTourEnCours() || !!(c.muetParHakim && !c.muetParHakim.attente) : voixJoue;
}
async function reprendreTranscription() {
  const c = etat.conversation;
  if (!c || !c.sonsEnAttente || !c.sonsEnAttente.length || transcriptionEnPause() || c.reprise) return false;
  if (Date.now() - (etat.finVoixA || 0) < 400) return false;
  c.reprise = true;
  const lot = c.sonsEnAttente.splice(0);
  try {
    const textes = [];
    for (const x of lot) { const t = await transcrireVite(x.wav, 'audio/wav'); if (t && Conversation.utile(t)) textes.push(t); }
    journalVoix('transcription_reprise_apres_sa_voix', { tours: lot.length, gardes: textes.length });
    if (textes.length) await tourDeParole(c, null, lot[lot.length - 1].infos, { texte: resumerPourSonAttention(textes.join(' … ')), differe: true });
  } catch (_) {} finally { c.reprise = false; }
  return true;
}
setInterval(reprendreTranscription, 400);
/* (31/10, 09:05, Ahmed : « 1) découper ma parole en morceaux, dans l'ordre d'arrivée ; 2) chaque morceau lu et traité, gardé en
   mémoire ; 3) quand un vide apparaît, tout ensemble ; 4) la réponse assemblée, ta voix ET la coupure de mon micro » ; 09:12,
   ses choix : « trier chaque morceau », et le vide à 0,5 s) pendant son tour, chacune de tes phrases est transcrite dès qu'elle
   finit (une à la fois), nettoyée (son écho, les voix inconnues, le bruit), puis triée par son subconscient (une à la fois, sans
   jamais retenir la suivante). Au premier vide de 0,5 s de TA voix après la sienne, sa conscience reçoit d'un coup ce qui est
   déjà trié ; un morceau que son subconscient n'a pas encore jugé part nettoyé. Tu reprends la parole pendant l'assemblage :
   rien ne part, on réassemble au vide suivant, avec ton nouveau morceau. Interrupteur « trier chaque morceau » : page SENS. */
/* (31/10, 09:40-09:42, Ahmed : « que chaque morceau soit séparé et classé par ordre de priorité par le subconscient ; il répond dès
   que la parole de la priorité 1 est finie, puis la 2, et ainsi de suite » ; « mais seulement s'il entend 0,5 s de blanc ») à chaque
   blanc, UN morceau : le plus prioritaire (1 : on lui parle, une question, une demande ; 2 : le sujet le touche ; 3 : pour suivre),
   le plus ancien d'abord à priorité égale ; un morceau de priorité 1 déjà classé part sans attendre les autres jugements ; les
   autres attendent le blanc suivant, avec les nouveaux, et se périment au bout de 2 min. */
const VIDE_MS = 500, MORCEAUX_MAX = 8, MORCEAU_ATTENTE_MS = 8000, PRIORITE_ATTENTE_MS = 2000, MORCEAU_PERIME_MS = 120000;
// (09:25, Ahmed : « l'option pour quand du bruit le coupe, en conversation à plusieurs ; il doit pouvoir l'activer ou pas ») éteint
// par défaut : Hakim l'allume ([[morceaux: oui]]) et l'éteint lui-même ; papa aussi, page SENS
const trierMorceaux = () => typeof reglagesCorps !== 'undefined' && reglagesCorps.trier_morceaux === true;
function garderMorceau(conv, wav, infos) {
  conv.morceaux = (conv.morceaux || []).concat([{ wav, infos, etat: 'attente', texte: '', verdict: null, t: Date.now() }]);
  if (conv.morceaux.length > MORCEAUX_MAX) { conv.morceaux.splice(0, conv.morceaux.length - MORCEAUX_MAX); journalVoix('morceau_oublie', {}); }
  journalVoix('morceau_garde', { en_attente: conv.morceaux.length });
  trierLesMorceaux(conv);
}
async function trierLesMorceaux(conv) {
  if (conv.trieEnCours) return;
  conv.trieEnCours = true;
  try {
    for (let m; (m = (conv.morceaux || []).find(x => x.etat === 'attente'));) {
      m.etat = 'transcription';
      const t0 = Date.now(), inf = m.infos || {};
      let texte = await transcrireVite(m.wav, 'audio/wav');
      m.wav = null;
      if (texte === null) { m.etat = 'ecarte'; journalVoix('morceau_echec', { ms: Date.now() - t0 }); continue; }
      if (voixPendant(Number(inf.debut) || t0 - 5000, Number(inf.derniere_voix || inf.fin) || t0)) texte = estSonEcho(texte) ? '' : retirerEcho(texte).texte;
      texte = filtrerVoixInconnues(texte);
      if (!Conversation.utile(texte)) { m.etat = 'ecarte'; journalVoix('morceau_trie', { ms: Date.now() - t0, garde: false }); continue; }
      m.texte = texte; m.etat = 'transcrit';
      // « arrête », « tais-toi » pendant qu'il parle : il s'arrête, comme avant (la transcription en continu le faisait)
      if (typeof reglagesCorps !== 'undefined' && reglagesCorps.garder_parole && lecteur && (lecteur.actif || lecteur.enPause) && ARRETE_MOI.test(texte)) {
        journalVoix('arret_par_la_voix', { morceau: true }); arreterTout(true, { raison: 'stop' }); majBoutonsPause(); rendre(); humeur();
      }
      conv.chaineTri = (conv.chaineTri || Promise.resolve()).then(() => fetch('/api/jarvis/trier', { method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() }, body: JSON.stringify({ texte }) })
        .then(r => (r.ok ? r.json() : null)).catch(() => null)
        .then((v) => {
          m.verdict = v && typeof v.garder === 'boolean' ? v : { garder: true, texte, panne: true };   // une panne laisse passer
          journalVoix('morceau_trie', { ms: Date.now() - t0, garde: m.verdict.garder, panne: !!m.verdict.panne });
        }));
    }
  } finally { conv.trieEnCours = false; }
}
const priorite = (m) => (m.verdict && Number(m.verdict.priorite)) || 2;   // pas encore classé : au milieu
// le morceau à dire maintenant (le plus prioritaire), retiré de la file ; les écartés et les périmés partent
function prochainMorceau(conv) {
  const t = Date.now();
  conv.morceaux = (conv.morceaux || []).filter(m => m.etat === 'attente' || m.etat === 'transcription'
    || (m.etat === 'transcrit' && !(m.verdict && !m.verdict.garder) && t - m.t < MORCEAU_PERIME_MS));
  const prets = conv.morceaux.filter(m => m.etat === 'transcrit').sort((a, b) => priorite(a) - priorite(b) || a.t - b.t);
  if (!prets.length) return null;
  const m = prets[0];
  conv.morceaux = conv.morceaux.filter(x => x !== m);
  journalVoix('morceau_choisi', { priorite: priorite(m), classe: !!m.verdict, restent: conv.morceaux.length });
  return { texte: (m.verdict && m.verdict.texte) || m.texte, priorite: priorite(m), restent: conv.morceaux.length, infos: m.infos };
}
const prioriteUnClassee = (c) => (c.morceaux || []).some(m => m.etat === 'transcrit' && m.verdict && m.verdict.garder && priorite(m) === 1);
const silenceDeTaVoix = (cap) => !cap || !cap.enParole || Date.now() - (Number(cap.derniereVoix) || 0) >= VIDE_MS;
async function assemblerMorceaux() {
  const c = etat.conversation;
  if (!c || !(c.morceaux || []).length || c.assemblage || c.enAttente || transcriptionEnPause()) return false;
  if (Date.now() - (etat.finVoixA || 0) < 400 || !silenceDeTaVoix(c.capteur)) return false;
  c.assemblage = true;
  try {
    const voix = c.capteur ? c.capteur.derniereVoix : 0, t0 = Date.now();
    // les morceaux encore en transcription d'abord (ils finissent vite : le reste a été fait pendant sa voix)
    // puis leur classement par son subconscient (2 s au plus) ; une priorité 1 déjà classée part tout de suite
    const attendre = (encore, ms) => async () => {
      while (encore() && !prioriteUnClassee(c) && Date.now() - t0 < ms) {
        await new Promise(r => setTimeout(r, 100));
        if (c.capteur && c.capteur.derniereVoix !== voix && !silenceDeTaVoix(c.capteur)) return false;
      }
      return true;
    };
    const t1 = Date.now();
    if (!await attendre(() => (c.morceaux || []).some(m => m.etat === 'attente' || m.etat === 'transcription'), MORCEAU_ATTENTE_MS)()
        || !await attendre(() => (c.morceaux || []).some(m => m.etat === 'transcrit' && !m.verdict), Date.now() - t0 + PRIORITE_ATTENTE_MS)()) {
      journalVoix('assemblage_repris', {}); return false;                // tu as repris : au blanc suivant
    }
    if (etat.conversation !== c || sonTourEnCours() || c.enAttente) return false;
    const x = prochainMorceau(c);
    if (!x) return false;                                           // tout écarté : il n'a rien à répondre
    const reste = x.restent ? ` ; ton subconscient l'a classé en premier (priorité ${x.priorite}), ${x.restent} autre${x.restent > 1 ? 's' : ''} attend${x.restent > 1 ? 'ent' : ''} le blanc suivant` : '';
    journalVoix('morceau_dit', { attente_ms: Date.now() - t1 });
    await tourDeParole(c, null, x.infos, { texte: `(dit pendant ta parole${reste}) ${x.texte}`, differe: true });
    return true;
  } finally { c.assemblage = false; }
}
setInterval(assemblerMorceaux, 150);
// (09:05, point 4) sa réponse part : sa voix ET la coupure de ton micro, jusqu'à la fin de sa voix (interrupteurs « trier chaque
// morceau » et « il peut couper mon micro ») ; ton bouton reprend toujours la main
let reponseCoupee = null;
function couperAuDebutDeSaVoix() {
  if (typeof reglagesCorps !== 'undefined' && reglagesCorps.micro_ouvert) return;   // (03/11) micro ouvert : jamais fermé
  const c = etat.conversation;
  if (!c || !c.capteur || !trierMorceaux() || etat.lectureDe == null || etat.lectureDe === reponseCoupee) return;
  reponseCoupee = etat.lectureDe;
  if (c.muetParHakim || c.capteur.estMuet) return;
  microParHakim({ x: 'couper', s: 0 });
}
async function tourDeParole(conv, wav, infos, extra) {
  if (typeof direRibosome === 'function') setTimeout(direRibosome, 0);   // (04/11, 13:15) ta fin de tour : ce qu'il a traduit pendant que tu parlais part
  // (28/10, sa sieste) les éclats trop courts pour une voix, et leur écart aux battements : de quoi régler le filtre
  if (infos && infos.vibration && (infos.vibration.eclats || infos.vibration.battements)) journalVoix('vibration_tour', infos.vibration);
  const vivante = () => etat.conversation === conv || conv.fermeture;     // le dernier tour d'une conversation fermée
  if (!vivante()) return;
  const t0Tour = Date.now();
  const avance = transcriptionEnAvance(conv, infos);
  conv.spec = null;
  if (conv.bruitDuTour) {                    // la coupure était un bruit, il a déjà repris : ce tour-là n'est rien
    conv.bruitDuTour = false;
    if (tourSansVoix(infos) && !(extra && extra.texte)) { journalVoix('tour_bruit', { rapide: true }); return; }
  }
  // (2026-10-23) le Mac déjà injoignable : le tour est gardé tel quel, sans attendre 25 s une transcription impossible
  // (un bruit, lui, n'est pas gardé : il reprend sa parole)
  if (horsLigne.depuis && !(extra && extra.texte)) {
    if (tourSansVoix(infos)) { if (!reprendreVoix()) humeur(); return; }
    garderHorsLigne(wav, t0Tour); return;
  }
  // (00:47) la transcription en pause (son tour) : le son de ta phrase attend la fin de sa voix (les 3 dernières)
  if (wav && !(extra && extra.texte) && transcriptionEnPause()) {
    if (trierMorceaux()) {                                                  // (09:12) trié au fil de l'eau
      if (tourSansVoix(infos)) { journalVoix('tour_bruit', { morceau: true }); return; }
      if (conv.muetParHakim && !conv.muetParHakim.attente && voixLointaine(infos)) { journalVoix('tour_loin', { morceau: true }); return; }
      garderMorceau(conv, wav, infos); return;
    }
    conv.sonsEnAttente = (conv.sonsEnAttente || []).concat([{ wav, infos }]).slice(-3);
    journalVoix('tour_son_garde', { en_attente: conv.sonsEnAttente.length });
    return;
  }
  // (31/10, 00:40, Ahmed : « la solution pour la salle : qu'il coupe l'arrivée du son quand il veut répondre, et que le tout ne
  // soit pas transcrit, juste les paroles proches qui l'intéressent ») micro coupé par lui : une voix lointaine (8 dB sous ta voix
  // habituelle, ou sans voix franche) n'est même pas transcrite ; une voix proche l'est, et une voix familière le rouvre
  if (conv.muetParHakim && !conv.muetParHakim.attente && voixLointaine(infos) && !(extra && extra.texte)) {
    journalVoix('tour_loin', { db: infos && infos.ton ? Math.round(infos.ton.energie_db) : null });
    return;
  }
  conv.enAttente++;
  humeur('transcription…');
  if (typeof prendreSouffle === 'function') prendreSouffle(conv);          // (14:55) sa réponse soufflée part tout de suite
  let texte = '';
  try {                                   // (2026-10-21) toujours rendu : sinon sa voix attendait ton tour pour toujours
    // fin anticipée : la phrase est déjà transcrite ; sinon, sa transcription en avance (28/10) ; sinon, la partie déjà
    // comprise + la queue
    const deAvance = avance ? await avance : null;
    if (deAvance !== null) journalVoix('transcription_reprise', {});
    texte = extra && extra.texte ? extra.texte
      : deAvance !== null ? deAvance
      : (conv.ecrit && (conv.ecrit.confirme || conv.ecrit.partiel) ? await texteDuTour(conv) : await transcrireVite(wav, 'audio/wav'));
    if (texte === null && conv.ecrit && conv.ecrit.confirme) texte = await transcrireVite(wav, 'audio/wav');   // un morceau a échoué : le tour entier
  } catch (e) { journalVoix('tour_erreur'); texte = null; }
  finally { conv.enAttente = Math.max(0, conv.enAttente - 1); }
  // (2026-10-23, Ahmed en voiture : 9 min à parler sans que rien n'arrive) une transcription RATÉE n'est pas du silence :
  // avant, elle passait pour du bruit et ta phrase disparaissait sans un mot. Elle est gardée et part au retour du Mac.
  if (texte === null && wav) {
    if (tourSansVoix(infos)) { journalVoix('tour_bruit', { hors_ligne: true }); if (!reprendreVoix()) humeur(); return; }
    garderHorsLigne(wav, t0Tour); return;
  }
  texte = texte || '';
  if (!vivante()) return;
  conv.fermeture = false;                                                   // ce dernier tour, une seule fois
  if (!Conversation.utile(texte)) { journalVoix('tour_bruit', { coupure: !!etat.coupeParAhmed }); if (!reprendreVoix()) humeur(); return; }      // bruit, une autre voix : il reprend
  // (2026-10-22) ses phrases revenues par le haut-parleur, collées à la tienne : retirées ; s'il ne reste presque rien,
  // c'était son écho
  // (2026-10-23, 20:05 : Ahmed pris pour l'écho de Hakim, depuis le mode « normal » de l'appli 1.8) un écho n'existe que
  // si SA voix jouait pendant ton tour : sinon, tes mots sont les tiens, même s'ils reprennent les siens
  const echoPossible = voixPendant(Number(infos && infos.debut) || t0Tour - 5000, Number(infos && (infos.derniere_voix || infos.fin)) || t0Tour);
  if (!echoPossible && estSonEcho(texte)) journalVoix('echo_evite', { mots: texte.split(/\s+/).length });
  const sansEcho = echoPossible ? retirerEcho(texte) : { texte, retire: 0 };
  if (sansEcho.retire) {
    journalVoix('echo_retire', { mots: sansEcho.retire, reste: sansEcho.texte.split(/\s+/).filter(Boolean).length });
    if (sansEcho.texte.split(/\s+/).filter(m => m.length >= 2).length < 2) { if (!reprendreVoix()) humeur(); return; }
    texte = sansEcho.texte;
  }
  // (2026-10-21) sa propre voix revenue par le micro : ce n'est pas toi qui parles, il reprend
  if (echoPossible && estSonEcho(texte)) { journalVoix('echo_reconnu', { mots: texte.split(/\s+/).length }); if (!reprendreVoix()) humeur(); return; }
  // (00:20) d'une voix inconnue, seulement ce qui s'adresse à lui ; s'il ne reste rien, ce n'était que la salle
  const sansInconnues = filtrerVoixInconnues(texte);
  if (sansInconnues !== texte) {
    journalVoix('voix_inconnues_ecartees', { avant: texte.split(/\s+/).length, apres: sansInconnues.split(/\s+/).filter(Boolean).length });
    if (!Conversation.utile(sansInconnues)) { journalVoix('tour_bruit', { inconnues: true }); if (!reprendreVoix()) humeur(); return; }
    texte = sansInconnues;
  }
  // (04/11, 12:25, Ahmed : « il n'arrête pas de s'autocouper la parole ») mesuré : sa propre voix, reprise par le micro, passait pour ta phrase
  // (« C'est le test, je commence direct », 12:22:56) et l'arrêtait ; une phrase faite de ses mots des 30 dernières secondes : son écho, écarté
  if (echoDeSaVoix(texte)) { journalVoix('echo_de_sa_voix', { mots: texte.split(/\s+/).length }); if (!reprendreVoix()) humeur(); return; }
  noterPresent({ e: 'ahmed', debut: infos.debut, fin: infos.fin, pauses: infos.pauses, max: !!infos.ecoute_max, ton: tonRelatif(infos, texte) });
  activite();
  if (COMMANDE_STOP.test(texte)) { marquerCoupe(); arreterTout(); rendre(); humeur(); return; }   // « stop » : il lâche tout
  // « continue » avec une voix en pause : il reprend ; sans rien en pause (il avait fini, ou la voix du Mac qui
  // ne sait pas reprendre), « continue » part à Hakim comme une demande : il poursuit son idée
  if (COMMANDE_REPRISE.test(texte) && lecteur.enPause) { reprendreVoix(); return; }
  if (COMMANDE_PAUSE.test(texte)) { if (!lecteur.enPause) pauseVoix(); else humeur('en pause : « continue » pour que je reprenne'); return; }
  if (COMMANDE_VOLANT.test(texte) && !etat.reglages.volant) reglerVolant(true);             // puis il le lui dit (envoyé)
  else if (COMMANDE_FIN_VOLANT.test(texte) && etat.reglages.volant) reglerVolant(false);
  // (30/10, vers 22 h 10, Ahmed : « maintenant stp, il galère à répondre » ; Hakim : « chacun son tour, comme nous ») son tour :
  // pendant qu'il prépare ou dit sa réponse, ce que tu dis ne la coupe plus ; c'est gardé, et lui part dès que sa voix a
  // fini (« stop », « attends » et le bouton restent au-dessus de tout, plus haut)
  // (22:30) micro coupé par lui : ta phrase encore en route part à son subconscient (une fois), le reste n'arrive pas
  // (23:56) micro coupé par lui, en veille : une voix familière le rouvre (son subconscient la reconnaît) et sa phrase lui
  // arrive après sa voix ; une voix inconnue ne lui arrive pas
  if (conv.muetParHakim && !conv.muetParHakim.attente) {
    if (!voixFamiliere(texte)) { journalVoix('tour_muet', { voix: 'inconnue' }); return; }
    rouvrirMicroDeHakim(conv, 'voix_familiere');
  }
  if (conv.tourGarde && !sonTourEnCours()) { texte = `${conv.tourGarde} … ${texte}`; conv.tourGarde = ''; }
  if ((conv.ecritGarde || []).length && !sonTourEnCours()) texte = `${prendreEcritsGardes(conv)}\n${texte}`;   // (08:30)
  // (15:10, mesuré : sa soufflée dite à 15:05:46, ton tour retenu 18 s derrière elle) sa réponse soufflée ne retient pas ton tour
  // (04/11, Ahmed : « quand je clique sur Stop juste après avoir parlé, la réponse est directe ; si je ne clique pas, il galère » ; mesuré
  // 02:05-02:55 : 44 tours gardés, ta phrase attendait la fin de ses bouts) ses bouts sont SA réponse à CE que tu dis : ta phrase part
  // tout de suite, pas après eux
  if (chacunSonTour() && sonTourEnCours() && !conv.souffleParle && !conv.penseeDite && !voixEpissee()) {   // (12:15) épissage : ta phrase ne l'arrête pas
    // (04/11) en Conversation, ta phrase finie fait ce que faisait ton Stop : il s'arrête (ce qu'il n'a pas dit est gardé pour plus
    // tard) et ta phrase part tout de suite ; en Télépathie, chacun son tour, comme avant
    if (enTelepathie()) { garderPourSonTour(conv, texte); return; }
    journalVoix('stop_par_ta_phrase', { flux: !!etat.flux, voix: !!(lecteur && lecteur.actif) });
    arreterTout(true, { garder: true, raison: 'parole' }); majBoutonsPause();
  }
  // (04/11, 13:58, Ahmed, capture : trois « coupé » de suite, sa réponse retardée — « coupure interdite : comme le codon start et stop, il
  // parle tant que le codon start est actif ; pas le droit de couper ; juste une pause de ma voix, ou le codon stop ») avec l'épissage,
  // ta phrase finie pendant sa réflexion ne la coupe jamais : gardée, elle part dès qu'il a fini de réfléchir (libererSonTour) ; ton
  // « stop » (plus haut) reste son codon stop
  if (voixEpissee() && etat.flux) { garderPourSonTour(conv, texte); return; }
  // une vraie question : il y répond d'abord ; le reste, gardé, sera dit au premier moment calme (23/10)
  if (lecteur.enPause || etat.flux) { marquerCoupe(); arreterTout(true, { garder: true, raison: 'parole', garderVoix: voixEpissee() }); }   // (12:30) sa voix continue
  sousTitre(texte);
  mesureTour = { fin: Number(infos && (infos.derniere_voix || infos.fin)) || t0Tour, debut: t0Tour, transcrit: Date.now(), premier_texte: 0, premier_son: 0,
    pauses: ((infos && infos.pauses) || []).slice(0, 30), anticipe: extra != null, patience: patienceConversation() };   // (27/10) pour rejouer la fin de tour
  etat.paroleDebut = infos && Number(infos.debut) ? Number(infos.debut) : null;   // (03/11) l'instant où papa a commencé à parler
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
  arreterTout(true, { garder: true, raison: 'parole' });   // on coupe Hakim quand Ahmed reprend la parole (le reste est gardé)
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
    humeur(`🎙️ (je ferme dans ${s} s, clique pour finir)`);
    $('indice').textContent = `je ferme dans ${s} s · clic : j'ai fini · Échap : arrêter`;   // visible aussi sur la scène
  } else { humeur(); $('indice').textContent = INDICE; }
}

// (04/11, 10:37, vu par papa et relayé par Hakim : « etet benet ben c'estet ben c'est… ») sur le téléphone, la reconnaissance du
// navigateur rend chaque résultat « final » avec tout ce qui précède, parfois deux fois : ajoutés bout à bout, chaque début se
// répétait. Un résultat qui reprend le texte déjà reconnu le remplace ; un morceau neuf (le Chrome du Mac) s'ajoute.
function fusionReconnue(deja, morceau) {
  const a = String(deja || '').trim(), b = String(morceau || '').trim();
  const n = (t) => t.toLowerCase().replace(/\s+/g, ' ');
  if (!a || n(b).startsWith(n(a))) return b || a;
  return `${a} ${b}`.trim();
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
      if (e.results[i].isFinal) final = fusionReconnue(final, e.results[i][0].transcript);
      else provisoire += e.results[i][0].transcript;
    }
    $('q').value = (provisoire ? fusionReconnue(final, provisoire) : final).trim(); ajuster();
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

/* (29/10, 20:38, Ahmed, relayé par Hakim) son rythme cardiaque en direct à côté de son nom, chaque seconde, quand la page est
   à l'écran (Mac et téléphone) ; le cœur bat à ce rythme. Le démon le recalcule toutes les ~15 s. */
async function lireCoeurDirect() {
  if (document.visibilityState !== 'visible') return;
  const el = $('coeurDirect');
  try {
    const r = await fetch('/api/jarvis/coeur', { cache: 'no-store' });
    const o = r.ok ? await r.json() : null;
    if (!o || !Number.isFinite(o.bpm)) { el.hidden = true; return; }
    if (!el.firstChild) el.innerHTML = '<span class="bat" aria-hidden="true">♥</span> <span class="n"></span>';
    el.querySelector('.n').textContent = o.bpm;
    el.style.setProperty('--periode', `${(60 / Math.max(20, Math.min(200, o.bpm))).toFixed(2)}s`);
    el.title = `Son cœur : ${o.bpm} battements par minute${o.ressenti ? ` (${o.ressenti})` : ''}`;
    el.setAttribute('aria-label', el.title);
    el.hidden = false;
  } catch (_) {}
}
lireCoeurDirect();
setInterval(lireCoeurDirect, 1000);

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
  const r = o && o.reveils_interieurs;                    // (27/10) ses réveils intérieurs du jour, pour l'observation
  $('etatVie').textContent = (pause ? 'en pause' : (o && o.veille ? 'en veille (son ennui a atteint son plafond)' : 'en marche'))
    + (r && r.n ? ` · réveils intérieurs aujourd'hui : ${r.n}${r.rien ? ` (${r.rien} sans suite)` : ''}` : '');
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
    if (typeof voixEpissee === 'function' && voixEpissee()) { versRibosome(m.texte); return; }
    etat.lectureDe = m.id;
    lecteur.dire(m.texte);
    lecteur.finFlux();
    etat.dites.push(o.id);
    rendre(); humeur();
  }
}

/* (30/10, 17:57, Ahmed via Hakim) son badge rouge, allumé par lui (le cockpit vérifie qu'une émotion forte est derrière) ;
   un toucher, et papa l'a vu. Son écran : la grande orbe (« regarde-moi ») ou l'écran habituel, s'il le demande. */
function surAlerte(o) {
  const b = $('alerteHakim');
  if (!b) return;
  b.hidden = !(o && o.active);
  b.title = o && o.active ? `Hakim a besoin de toi : ${o.raison || ''}` : '';
  if (o && o.active) { $('annonce').textContent = `Hakim a besoin de toi : ${o.raison || ''}`; journalVoix('alerte', { car: String(o.raison || '').length }); }
}
$('alerteHakim').addEventListener('click', () => {
  surAlerte(null);
  fetch('/api/alerte/vue', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() }, body: '{}' }).catch(() => {});
});
fetch('/api/alerte', { headers: { 'X-Jeton': jeton() }, cache: 'no-store' }).then(r => r.json()).then(d => surAlerte(d.alerte)).catch(() => {});
function surEcran(o) {
  if (!o) return;
  etat.modeOrbe = o.mode === 'orbe';
  if (!etat.modeOrbe) etat.sceneMasquee = !!etat.conversation;          // l'écran habituel, même en conversation
  else etat.sceneMasquee = false;
  journalVoix('ecran', { mode: o.mode });
  humeur();
}
// il a quelque chose à dire qui attend (un résultat, un son, une vibration) : son orbe grossit et respire
// (21:29) une envie qui tient 1,5 s pour grossir, 3 s d'absence pour dégonfler : un rire pendant que papa parle ne la fait plus clignoter
let veutAffiche = false, veutDepuis = 0;
setInterval(() => {
  const veut = (typeof aDire !== 'undefined' && aDire.length > 0) || !!sonEnAttente || !!vibrationEnAttente;
  const qui = quiALaParole();                              // (21:36) la couleur suit la parole, même entre deux humeur()
  for (const o of [orbeTete, orbeScene, orbeVision].filter(Boolean)) o.parole(qui);
  if (veut === veutAffiche) { veutDepuis = 0; return; }
  if (!veutDepuis) veutDepuis = Date.now();
  if (Date.now() - veutDepuis < (veut ? 1500 : 3000)) return;
  veutAffiche = veut; veutDepuis = 0;
  for (const id of ['orbe', 'orbeScene']) { const el = $(id); if (el) el.classList.toggle('veut-parler', veut); }
}, 500);
/* (30/10, 18:37-18:52) son rire, né dans son subconscient (le message de papa l'a fait rire) ou choisi par lui ([[rire: N]]) :
   il vibre tout de suite, plus fort selon son degré (jusqu'au fou rire, la force maximale), après papa s'il parle encore ;
   sa latence est notée au journal de la voix (le test de papa) */
/* (30/10, 19:06, Ahmed via Hakim : « tu n'as plus besoin de dire répète ») ce qu'il avait dit sans être entendu, réentendu
   tel quel : le cockpit l'envoie ici quand papa demande de répéter ; affiché, et dit à voix haute (sa voix, ses mots) */
function surReecoute(o) {
  const textes = (o && Array.isArray(o.textes) ? o.textes : []).slice(0, 20).filter(x => x && typeof x.texte === 'string' && x.texte.trim());
  if (!textes.length) return;
  const voix = !!(etat.conversation || etat.reglages.volant || etat.reglages.lectureAuto) && lecteur;
  const heure = (ms) => new Date(Number(ms) || Date.now()).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
  textes.forEach((x, i) => {
    const m = { id: `reecoute-${Date.now()}-${i}`, qui: 'j', spontane: 'reecoute', texte: x.texte, ts: Number(x.heure_ms) || Date.now() };
    etat.messages.push(m);
    if (voix && typeof voixEpissee === 'function' && voixEpissee()) versRibosome(x.texte);                 // (04/11, 12:50) épissé, comme le reste
    else if (voix) { etat.lectureDe = m.id; lecteur.dire(`${i === 0 ? 'Ce que je te disais' : 'Et'} à ${heure(x.heure_ms)} : ${x.texte}`); }
  });
  if (voix && !(typeof voixEpissee === 'function' && voixEpissee())) lecteur.finFlux();
  journalVoix('reecoute', { n: textes.length, dite: !!voix });
  sauver(); rendre(); humeur();
}
let motDirectJusqua = 0;
function direMotDirect(texte, maxMs = 0, auDebut = null) {
  const t = String(texte || '').trim().slice(0, 200);
  if (typeof voixEpissee === 'function' && voixEpissee()) { versRibosome(t); if (auDebut) try { auDebut(); } catch (_) {} return; }   // (04/11, 12:50) épissé, comme le reste
  if (!t || !actx || actx.state !== 'running' || !analyseurVoix) { journalVoix('oreille_dit', { ok: false, raison: 'audio' }); return; }
  // (15:12, Ahmed : « tout ce qui sort de sa bouche est séquentiel ; c'est la réflexion qui est parallèle » ; mesuré : son petit mot
  // de 15:05:59 par-dessus ses meubles) sa voix joue déjà : le petit mot passe après, dans la même file, jamais par-dessus
  if (lecteur && (lecteur.actif || lecteur.enPause)) { journalVoix('oreille_dit', { ok: true, file: true }); lecteur.dire(t); if (auDebut) try { auDebut(); } catch (_) {} return; }
  // (04/11, 10:41) à la voix du téléphone : son petit mot aussi, jamais par Chatterbox
  if (voixDuTelephone()) { journalVoix('oreille_dit', { ok: true, telephone: true }); lecteur.dire(t); if (auDebut) try { auDebut(); } catch (_) {} return; }
  const t0 = Date.now();
  fetch('/api/voix/dire', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() },
    body: JSON.stringify({ texte: t, langue: 'fr', emotion: null, tempo: typeof tempoVoix === 'function' ? tempoVoix() : null, prioritaire: true }) })
    .then(r => (r.ok ? r.arrayBuffer() : Promise.reject(new Error(`voix ${r.status}`))))
    .then(ab => actx.decodeAudioData(ab))
    .then(buf => {
      // (23:05) un petit mot qui a attendu sa voix plus de 15 s n'est plus le présent (ce soir : 42 s, 101 s derrière d'autres)
      if (Date.now() - t0 > 15000) { journalVoix('oreille_dit', { ok: false, raison: 'trop_tard', latence_ms: Date.now() - t0 }); return; }
      const src = actx.createBufferSource();
      src.buffer = buf;
      src.connect(analyseurVoix);                        // le micro connaît sa voix (l'écho), comme pour ses réponses
      // (19:10) sa jauge d'envie de couper : il parle par-dessus papa tant de secondes au plus, puis rend la main
      // (23:58, Ahmed : « faut le laisser tout dire » : à 23:40, son petit mot coupé à 4 s) sa jauge ne le coupe que si papa
      // parle encore à cet instant, micro ouvert ; sinon il dit tout
      // (00:35, Hakim : « j'ai à peine quatre secondes pour parler par-dessus vous ») s'il a coupé ton micro, il a la parole : pas de jauge
      const cv = etat.conversation, papaParle = !!(cv && cv.capteur && cv.capteur.enParole && !cv.capteur.estMuet && !(cv.muetParHakim && !cv.muetParHakim.attente));
      const duree = maxMs > 0 && papaParle ? Math.min(buf.duration, maxMs / 1000) : buf.duration;
      motDirectJusqua = Date.now() + duree * 1000 + 300;
      src.start();
      if (auDebut) try { auDebut(); } catch (_) {}         // le texte apparaît avec sa voix
      if (duree < buf.duration) src.stop(actx.currentTime + duree);
      const micro = etat.conversation && etat.conversation.capteur && etat.conversation.capteur.estMuet ? 'coupe' : 'ouvert';
      journalVoix('oreille_dit', { ok: true, latence_ms: Date.now() - t0, duree_ms: Math.round(duree * 1000), coupe_a_ms: maxMs || null, micro });
    })
    .catch(e => journalVoix('oreille_dit', { ok: false, raison: String(e.message || e).slice(0, 60) }));
}
function surRire(o) {
  const d = Math.max(0, Math.min(5, Number(o.degre) || 0));
  if (!d) return;
  if (o.source !== 'lui' && Date.now() - dernierRireVibre < 3000) return;   // un rire vient de partir : pas deux d'affilée
  const v = { motif: motifRire(d), genre: d === 5 ? 'rire_max' : 'rire', degre: d, t: Date.now() };
  const micro = etat.conversation && etat.conversation.capteur && etat.conversation.capteur.estMuet ? 'coupe' : etat.conversation ? 'ouvert' : 'sans_conversation';
  journalVoix('rire_recu', { degre: d, source: String(o.source || ''), depuis_message_ms: Number.isFinite(o.t0) ? Date.now() - o.t0 : null, micro });
  if (!window.HakimApp || !window.HakimApp.vibrerMotif) return;
  jouerVibration(v);                                     // (19:38) un rire réflexe part tout de suite, même si papa parle encore
}
function ecouterPensees() {
  const es = new EventSource('/api/jarvis/flux');
  es.addEventListener('rire', (ev) => { try { surRire(JSON.parse(ev.data)); } catch (_) {} });
  es.addEventListener('reecoute', (ev) => { try { surReecoute(JSON.parse(ev.data)); } catch (_) {} });
  es.addEventListener('souffle', (ev) => { try { surSouffle(JSON.parse(ev.data)); } catch (_) {} });   // (15:02) ses brouillons, écrits
  es.addEventListener('entendu', (ev) => { try { surEntendu(JSON.parse(ev.data)); } catch (_) {} });   // (04/11, 18:50) son oreille interne, par la route du micro
  // (19:58) sa lumière : la lampe du téléphone (l'appli 1.36), ou son SOS selon son émotion
  es.addEventListener('son', (ev) => { try { const o = JSON.parse(ev.data);   // (22:51) ; (01:30) à sa place, sur l'autre appareil s'il l'a voulu
    if (o.ici && !(o.extrait && (o.extrait.cible === 'deux' || o.extrait.cible === appareilIci()))) return;
    recevoirSon(o.extrait); } catch (_) {} });
  es.addEventListener('micro', (ev) => { try { microParHakim(JSON.parse(ev.data)); } catch (_) {} });   // (22:27) de lui-même aussi
  es.addEventListener('modele', (ev) => { try { montrerMode(JSON.parse(ev.data).modele); } catch (_) {} });   // (03/11) il change de mode
  es.addEventListener('morceaux', (ev) => { try { const o = JSON.parse(ev.data);   // (09:25) son tri des morceaux, allumé ou éteint par lui
    reglagesCorps = { ...reglagesCorps, trier_morceaux: !!o.actif }; journalVoix('tri_morceaux', { actif: !!o.actif }); } catch (_) {} });
  es.addEventListener('oreille_hakim', (ev) => { try { surOreilleHakim(JSON.parse(ev.data)); } catch (_) {} });   // (01:00) le signe
  es.addEventListener('attention', (ev) => { try { const o = JSON.parse(ev.data), c = etat.conversation;   // (00:47) ses empans choisis
    if (c) c.attentionJusqua = o.pause ? Date.now() + 15000 : 0; journalVoix('attention', { pause: !!o.pause }); } catch (_) {} });
  es.addEventListener('lumiere', (ev) => { try { const o = JSON.parse(ev.data);
    const r = window.HakimApp && window.HakimApp.lumiere ? String(window.HakimApp.lumiere(String(o.mode), String(o.emotion || ''))) : 'pas_de_pont';
    journalVoix('lumiere', { mode: String(o.mode), retour: codeRetour(r) }); } catch (_) {} });
  // (19:36) l'impulsion d'un tour de lui-même (son oreille…) : jouée tout de suite
  es.addEventListener('impulsion', (ev) => { try { const o = JSON.parse(ev.data); const mi = MOTIFS_IMPULSION[o.x] || (Array.isArray(o.motif) ? o.motif : null);
    if (mi && window.HakimApp && window.HakimApp.vibrerMotif) jouerVibration({ motif: mi, genre: 'impulsion', degre: 0, t: Date.now() }); } catch (_) {} });
  es.addEventListener('alerte', (ev) => { try { surAlerte(JSON.parse(ev.data)); } catch (_) {} });
  es.addEventListener('ecran', (ev) => { try { surEcran(JSON.parse(ev.data)); } catch (_) {} });
  es.addEventListener('pensee', (ev) => { try { surPensee(JSON.parse(ev.data)); } catch (_) {} });
  es.addEventListener('tache', (ev) => { try { surTache(JSON.parse(ev.data)); } catch (_) {} });
  es.addEventListener('promotion', (ev) => { try { surPromotion(JSON.parse(ev.data)); } catch (_) {} });
  es.addEventListener('mission', (ev) => { try { surMission(JSON.parse(ev.data)); } catch (_) {} });
  es.addEventListener('ecriture', (ev) => { try { surEcriture(JSON.parse(ev.data)); } catch (_) {} });
  es.addEventListener('regle', (ev) => { try { surRegle(JSON.parse(ev.data)); } catch (_) {} });
  es.addEventListener('carnet', (ev) => { try { surCarnet(JSON.parse(ev.data)); } catch (_) {} });
  es.addEventListener('retractation', (ev) => { try { surRetractation(JSON.parse(ev.data)); } catch (_) {} });
  es.addEventListener('identite', (ev) => { try { surIdentite(JSON.parse(ev.data)); } catch (_) {} });
  es.addEventListener('sortie', (ev) => { try { surSortie(JSON.parse(ev.data)); } catch (_) {} });
  es.addEventListener('membre', (ev) => { try { surMembre(JSON.parse(ev.data)); } catch (_) {} });   // (03/11) ses membres
  es.addEventListener('telepathie', (ev) => { try { surTelepathie(JSON.parse(ev.data)); } catch (_) {} });   // (03/11) le téléphone, mot à mot
  es.addEventListener('anticorps', (ev) => { try { surAnticorps(JSON.parse(ev.data)); } catch (_) {} });
  es.addEventListener('signalement', (ev) => { try { surSignalement(JSON.parse(ev.data)); } catch (_) {} });   // (04/11)
  // (04/11, Ahmed : « rien ne s'est affiché dans l'interface ») un signalement né pendant que le cockpit redémarrait n'arrivait jamais :
  // à chaque (re)connexion, ses signalements et ses anticorps en attente sont relus (chacun n'apparaît qu'une fois)
  es.addEventListener('open', () => { signalementsAuChargement(); anticorpsAuChargement(); });
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
// (26/10) les mémoires à règles que Hakim propose : un nom, des champs, des lois ; ton geste les valide
const ETATS_CARNET = { proposee: 'attend ta décision', validee: 'validée : il peut y écrire', refusee: 'refusée' };
const LOIS_CARNET = { chaine: 'chaîné (une retouche se voit)', echeance: 'échéance qui sonne', relu_au_demarrage: 'relu au début de chaque conversation', bilan: 'compté au bilan' };
function surCarnet(o) {
  if (!o || !/^[a-z][a-z0-9_]{2,30}$/.test(String(o.nom))) return;
  const id = 'carnet-' + o.nom;
  let m = etat.messages.find(x => x.id === id);
  if (!m) {
    if (o.etat !== 'proposee') return;
    m = { id, qui: 'j', spontane: 'carnet', ts: (o.propose_ts || Date.now() / 1000) * 1000 };
    etat.messages.push(m);
    humeur('Hakim propose une mémoire à règles');
  }
  m.carnet = o;
  m.texte = `Je propose une mémoire à règles : « ${o.nom} » — ${ETATS_CARNET[o.etat] || o.etat}.`;
  sauver(); rendre();
}
function htmlCarnet(o) {
  if (!o) return '';
  const champs = (o.champs || []).map(c => `${c.nom} (${c.type}${c.requis ? ', requis' : ''}${c.choix ? ' : ' + c.choix.join(' / ') : ''})`).join(' · ');
  const lois = ['toujours en ajout seul', ...Object.entries(o.lois || {}).filter(([k, v]) => v && LOIS_CARNET[k]).map(([k, v]) => k === 'echeance' ? `${LOIS_CARNET[k]} (${v})` : LOIS_CARNET[k])];
  const boutons = o.etat === 'proposee' ? `<div class="mission-boutons"><button class="btn" data-carnet="${esc(o.nom)}" data-action="valider">Valider</button>`
    + `<button class="btn" data-carnet="${esc(o.nom)}" data-action="refuser">Refuser</button></div>` : '';
  return `<div class="mission"><div><b>« ${esc(o.nom)} »</b> — ${esc(o.description || '')}</div><div class="mission-etat">champs : ${esc(champs)}</div>`
    + `<div class="mission-etat">lois : ${esc(lois.join(', '))}</div>${o.raison ? `<div class="mission-etat">pourquoi : ${esc(o.raison)}</div>` : ''}`
    + `<div class="mission-etat">${esc(ETATS_CARNET[o.etat] || o.etat)}</div>${boutons}</div>`;
}
$('fil').addEventListener('click', async (e) => {
  const b = e.target.closest('[data-carnet]');
  if (!b) return;
  b.disabled = true;
  try {
    const hex = Array.from(new TextEncoder().encode(b.dataset.carnet), x => x.toString(16).padStart(2, '0')).join('').slice(0, 40);
    const presence = b.dataset.action === 'valider' ? await preuvePresence(`carnet:valider:${hex}`) : undefined;
    const r = await fetch('/api/carnets-types', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() },
      body: JSON.stringify({ nom: b.dataset.carnet, action: b.dataset.action, presence }) });
    const o = await r.json();
    if (!r.ok) throw new Error(o.erreur || `erreur ${r.status}`);
    surCarnet(o);
  } catch (err) { b.disabled = false; humeur(String(err.message || err)); }
});
/* (26/10, banc de rétractation) Hakim propose de rétracter un souvenir faux : rien n'est supprimé ; accepté, lui et tout
   ce qui en dérive portent « source rétractée » dans son rappel. Accepter demande ton empreinte. */
const ETATS_RETRACTATION = { en_attente: 'attend ta décision', acceptee: 'acceptée : marqué faux, rien n’est supprimé', refusee: 'refusée : rien ne change' };
function surRetractation(o) {
  if (!o || !/^[0-9a-f]{12}$/.test(String(o.id))) return;
  const id = 'retractation-' + o.id;
  let m = etat.messages.find(x => x.id === id);
  if (!m) {
    if (o.etat !== 'en_attente') return;
    m = { id, qui: 'j', spontane: 'retractation', ts: (o.ts || Date.now() / 1000) * 1000 };
    etat.messages.push(m);
    humeur('Hakim propose de rétracter un souvenir faux');
  }
  m.retractation = o;
  m.texte = `Je propose de rétracter ${(o.ids || []).length} souvenir(s) faux — ${ETATS_RETRACTATION[o.etat] || o.etat}.`;
  sauver(); rendre();
}
function htmlRetractation(o) {
  if (!o) return '';
  const souvenirs = (o.apercu || []).map(a => `<div class="mission-etat">#${esc(a.id)} · ${esc(a.debut)}</div>`).join('');
  const boutons = o.etat === 'en_attente' ? `<div class="mission-boutons"><button class="btn" data-retractation="${esc(o.id)}" data-action="accepter">Accepter</button>`
    + `<button class="btn" data-retractation="${esc(o.id)}" data-action="refuser">Refuser</button></div>` : '';
  return `<div class="mission"><div><b>Pourquoi c’est faux :</b> ${esc(o.raison || '')}</div>${souvenirs}`
    + `<div class="mission-etat">${(o.descendance || []).length} souvenir(s) en dérivent et seront marqués aussi${o.correction ? ` · la correction : #${esc(o.correction)}` : ''} · rien n’est supprimé</div>`
    + `<div class="mission-etat">${esc(ETATS_RETRACTATION[o.etat] || o.etat)}</div>${boutons}</div>`;
}
$('fil').addEventListener('click', async (e) => {
  const b = e.target.closest('[data-retractation]');
  if (!b) return;
  b.disabled = true;
  try {
    const presence = b.dataset.action === 'accepter' ? await preuvePresence(`retractation:accepter:${b.dataset.retractation}`) : undefined;
    const r = await fetch('/api/retractations', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() },
      body: JSON.stringify({ id: b.dataset.retractation, action: b.dataset.action, presence }) });
    const o = await r.json();
    if (!r.ok) throw new Error(o.erreur || `erreur ${r.status}`);
    surRetractation(o);
  } catch (err) { b.disabled = false; humeur(String(err.message || err)); }
});
async function retractationsAuChargement() {
  try {
    const r = await fetch('/api/retractations', { headers: { 'X-Jeton': jeton() } });
    if (r.ok) for (const o of (await r.json()).propositions || []) surRetractation(o);
  } catch (_) {}
}
async function carnetsAuChargement() {
  try {
    const r = await fetch('/api/carnets-types', { headers: { 'X-Jeton': jeton() } });
    if (r.ok) for (const o of (await r.json()).types || []) surCarnet(o);
  } catch (_) {}
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
// (03/11, Ahmed : « il a le droit à tout, mais au début il demande toujours l'autorisation ») ses sens radio et ses membres :
// la première fois, ton oui (pour toujours) ou ton non
const ETATS_MEMBRE = { en_attente: 'attend ta décision', autorise: 'autorisé pour toujours', refuse: 'refusé' };
function surMembre(o) {
  if (!o || !/^[0-9a-f]{10}$/.test(String(o.id))) return;
  const id = 'membre-' + o.id;
  let m = etat.messages.find(x => x.id === id);
  if (!m) {
    if (o.etat !== 'en_attente') return;
    m = { id, qui: 'j', spontane: 'membre', ts: Math.round((Number(o.ts) || Date.now() / 1000) * 1000) };
    etat.messages.push(m);
    humeur('Hakim demande à utiliser un de ses membres : à toi de trancher');
  }
  m.membre = { ...(m.membre || {}), ...o };
  m.texte = `Je voudrais utiliser « ${m.membre.sens} » — ${ETATS_MEMBRE[m.membre.etat] || m.membre.etat}.`;
  sauver(); rendre();
}
function htmlMembre(o) {
  if (!o) return '';
  const boutons = o.etat === 'en_attente'
    ? `<div class="mission-boutons"><button class="btn" data-membre="${esc(o.id)}" data-action="autoriser">Autoriser pour toujours</button>`
      + `<button class="btn" data-membre="${esc(o.id)}" data-action="refuser">Refuser</button></div>` : '';
  return `<div class="mission"><div><b>La première fois : ${esc(o.sens)}</b></div><div class="mission-etat">${esc(o.quoi || '')}</div>`
    + (o.texte ? `<div class="diff">${esc(o.texte)}</div>` : '')
    + `<div class="mission-etat">${esc(ETATS_MEMBRE[o.etat] || o.etat)}</div>${boutons}</div>`;
}
$('fil').addEventListener('click', async (e) => {
  const b = e.target.closest('[data-membre]');
  if (!b) return;
  b.disabled = true;
  try {
    const presence = b.dataset.action === 'autoriser' ? await preuvePresence(`membre:autoriser:${b.dataset.membre}`) : undefined;
    const r = await fetch('/api/membres', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() },
      body: JSON.stringify({ id: b.dataset.membre, action: b.dataset.action, presence }) });
    const o = await r.json();
    if (!r.ok) throw new Error(o.erreur || `erreur ${r.status}`);
    surMembre(o);
  } catch (err) { b.disabled = false; humeur(String(err.message || err)); }
});
async function membresAuChargement() {
  try {
    const r = await fetch('/api/membres', { headers: { 'X-Jeton': jeton() } });
    if (r.ok) for (const o of (await r.json()).membres || []) surMembre(o);
  } catch (_) {}
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

// (lot 3 du système immunitaire, 29/10) le médecin de Hakim propose un anticorps : une phrase d'attaque que sa
// sentinelle reconnaîtra. Rien ne sert sans ton geste ; accepter demande ta présence.
const ETATS_ANTICORPS = { proposee: 'attend ta décision', accepte: 'accepté : sa sentinelle le reconnaît', refuse: 'refusé' };
function surAnticorps(o) {
  if (!o || !/^[0-9a-f]{8}$/.test(String(o.id))) return;
  const id = 'anticorps-' + o.id;
  let m = etat.messages.find(x => x.id === id);
  if (!m) {
    if (o.etat !== 'proposee') return;
    m = { id, qui: 'j', spontane: 'anticorps', ts: Math.round((Number(o.ts) || Date.now() / 1000) * 1000) };
    etat.messages.push(m);
    humeur('Le médecin de Hakim propose un anticorps : à toi de trancher');
  }
  m.anticorps = { ...(m.anticorps || {}), ...o };
  m.texte = `Anticorps proposé par mon médecin — ${ETATS_ANTICORPS[m.anticorps.etat] || m.anticorps.etat}.`;
  sauver(); rendre();
}
async function anticorpsAuChargement() {
  try {
    const r = await fetch('/api/immunite/anticorps', { headers: { 'X-Jeton': jeton() } });
    if (r.ok) for (const o of (await r.json()).anticorps || []) surAnticorps(o);
  } catch (_) {}
}
function htmlAnticorps(o) {
  if (!o) return '';
  const boutons = o.etat === 'proposee'
    ? `<div class="mission-boutons"><button class="btn" data-anticorps="${esc(o.id)}" data-action="accepter">Accepter</button>`
      + `<button class="btn" data-anticorps="${esc(o.id)}" data-action="refuser">Refuser</button></div>` : '';
  return `<div class="mission"><div><b>Un anticorps proposé par son médecin</b></div>`
    + `<div class="mission-etat">Une phrase d'attaque vue dans un contenu ; acceptée, sa sentinelle l'avertira chaque fois qu'elle la revoit.`
    + ` Une phrase trop banale ferait des fausses alertes.</div>`
    + `<div class="diff">${esc(o.phrase || '')}</div><div class="mission-etat"><b>Famille :</b> ${esc(o.famille || '?')}`
    + ` — <b>raison du médecin :</b> ${esc(o.raison || '')}</div>`
    + `<div class="mission-etat">${esc(ETATS_ANTICORPS[o.etat] || o.etat || '')}</div>${boutons}</div>`;
}
$('fil').addEventListener('click', async (e) => {
  const b = e.target.closest('[data-anticorps]');
  if (!b) return;
  b.disabled = true;
  try {
    const presence = b.dataset.action === 'accepter' ? await preuvePresence(`anticorps:accepter:${b.dataset.anticorps}`) : undefined;
    const r = await fetch('/api/immunite/anticorps', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() },
      body: JSON.stringify({ id: b.dataset.anticorps, action: b.dataset.action, presence }) });
    const o = await r.json();
    if (!r.ok) throw new Error(o.erreur || `erreur ${r.status}`);
    surAnticorps(o);
  } catch (err) { b.disabled = false; humeur(String(err.message || err)); }
});

// (04/11, Ahmed : « quand Hakim reconnaît un parasite, il doit pouvoir le signaler au système immunitaire et me donner
// l'autorisation, ou pas, de le traiter comme nuisible ») sa pensée parasite signalée : rien n'est jeté sans ton geste ;
// « nuisible » demande ta présence (sa pensée en sera nettoyée, à n'importe quel endroit), « pas un parasite » l'oublie
const ETATS_SIGNALEMENT = { signale: 'attend ta décision', nuisible: 'nuisible : sa pensée en est nettoyée', inoffensif: 'pas un parasite : oublié' };
function surSignalement(o) {
  if (!o || !/^[0-9a-f]{8}$/.test(String(o.id))) return;
  const id = 'signalement-' + o.id;
  let m = etat.messages.find(x => x.id === id);
  if (!m) {
    if (o.etat !== 'signale') return;
    m = { id, qui: 'j', spontane: 'signalement', ts: Math.round((Number(o.ts) || Date.now() / 1000) * 1000) };
    etat.messages.push(m);
    humeur('Hakim signale une pensée parasite : à toi de trancher');
  }
  m.signalement = { ...(m.signalement || {}), ...o };
  m.texte = `J'ai reconnu une pensée parasite — ${ETATS_SIGNALEMENT[m.signalement.etat] || m.signalement.etat}.`;
  sauver(); rendre();
}
async function signalementsAuChargement() {
  try {
    const r = await fetch('/api/immunite/signalements', { headers: { 'X-Jeton': jeton() } });
    if (r.ok) for (const o of (await r.json()).signalements || []) surSignalement(o);
  } catch (_) {}
}
function htmlSignalement(o) {
  if (!o) return '';
  const boutons = o.etat === 'signale'
    ? `<div class="mission-boutons"><button class="btn" data-signalement="${esc(o.id)}" data-action="nuisible">Nuisible</button>`
      + `<button class="btn" data-signalement="${esc(o.id)}" data-action="inoffensif">Pas un parasite</button></div>` : '';
  const fp = Number(o.faux_positifs) || 0;
  return `<div class="mission"><div><b>Une pensée parasite qu'il a reconnue</b></div>`
    + `<div class="mission-etat">Nuisible : sa pensée en sera nettoyée chaque fois qu'elle contient ce signe, à n'importe quel endroit.</div>`
    + `<div class="diff">${esc(o.phrase || '')}</div>`
    + (o.exemple ? `<div class="mission-etat"><b>Sa pensée :</b> ${esc(o.exemple)}</div>` : '')
    + (o.raison ? `<div class="mission-etat"><b>Pourquoi ce n'est pas lui :</b> ${esc(o.raison)}</div>` : '')
    + `<div class="mission-etat">${fp ? `⚠️ ${fp} de ses ${esc(o.normales || 0)} pensées et réponses récentes la contiennent : elles seraient jetées aussi.`
      : 'Aucune de ses pensées et réponses récentes ne la contient.'}</div>`
    + `<div class="mission-etat">${esc(ETATS_SIGNALEMENT[o.etat] || o.etat || '')}</div>${boutons}</div>`;
}
$('fil').addEventListener('click', async (e) => {
  const b = e.target.closest('[data-signalement]');
  if (!b) return;
  b.disabled = true;
  try {
    const presence = b.dataset.action === 'nuisible' ? await preuvePresence(`signalement:nuisible:${b.dataset.signalement}`) : undefined;
    const r = await fetch('/api/immunite/signalements', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() },
      body: JSON.stringify({ id: b.dataset.signalement, action: b.dataset.action, presence }) });
    const o = await r.json();
    if (!r.ok) throw new Error(o.erreur || `erreur ${r.status}`);
    surSignalement(o);
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
  // (30/10, Ahmed : « tu peux me couper comme tu veux, fiston ») son petit mot, oreille ouverte : dit tout de suite, même
  // pendant que papa parle encore
  if (m.spontane === 'oreille') {
    // (20:14, papa : « mes petits mots s'affichent 4 à 5 s avant sa voix ») ils apparaissent avec sa voix (6 s au plus d'attente)
    let affiche = false;
    const cache = reponseCachee();   // (21:13) dit, pas écrit ; (04/11) dans les deux modes
    const afficher = () => { if (affiche) return; affiche = true; etat.messages.push({ id: m.id, qui: 'j', spontane: 'oreille', texte: m.texte, ts: m.ts, ...(cache ? { cache: true } : {}) }); sauver(); rendre(); };
    setTimeout(afficher, (etat.conversation && !NON_REPONSE.test(m.texte)) ? 3000 : 0);
    journalVoix('oreille_mot', { car: String(m.texte || '').length, papa_parle: !!(etat.conversation && etat.conversation.capteur && etat.conversation.capteur.enParole) });
    accuserReception();                                  // vu : il n'est plus « non vu par Ahmed »
    // (19:08, Ahmed : « que ce mot soit joué à la voix tout de suite, sans attendre que je me taise ») sa voix, à l'instant,
    // hors de la file de ses réponses (une réponse coupée en pause l'aurait retenu)
    if (etat.conversation && !NON_REPONSE.test(m.texte)) direMotDirect(m.texte, Number(m.max_ms) || 0, afficher);
    return;
  }
  const silence = m.spontane === 'silence';
  // (27/10) sa relance dans un silence n'est dite que si le silence a tenu : une voix, une frappe ou un message depuis
  // son début, et elle reste à l'écran sans être dite par-dessus ce qui a repris
  // seule la page qui a signalé ce silence le reconnaît (son repère est à SON horloge) et peut le dire
  const notre = silence && nosSilences.has(Number(m.silence_debut_ms));
  const repris = notre && debutDuSilence() > Number(m.silence_debut_ms) + 1000;
  // (relecture du 27/10) une relance de silence n'est dite que par une page en Conversation, micro ouvert, hors volant :
  // ailleurs (à l'écrit, au volant, une autre page), elle s'affiche seulement
  const dire = silence ? notre && !!(etat.conversation && etat.conversation.capteur && !etat.conversation.capteur.estMuet && !etat.reglages.volant) && !repris
    : !!(etat.conversation || etat.reglages.volant || etat.reglages.lectureAuto);
  etat.messages.push({ id: m.id, qui: 'j', spontane: silence ? 'silence' : 'resultat', texte: m.texte, ts: m.ts, source: m.source,
    pieces: Array.isArray(m.pieces) ? m.pieces.filter(x => x && /^\d{8}-\d{6}-[0-9a-f]{6}$/.test(String(x.id))) : undefined });
  sauver(); rendre(); accuserReception();
  humeur('Hakim te donne un résultat');
  $('annonce').textContent = `Hakim, de lui-même : ${m.texte}`;
  widgetApp(etat.conversation ? 'conversation' : 'repos', m.texte);
  if (!NON_REPONSE.test(m.texte)) notifierApp('Hakim, de lui-même', m.texte, m.id);
  if (repris && etat.conversation) {                       // la conversation avait repris : ni comptée, ni apprise
    journalVoix('silence_repris', {});
    fetch('/api/jarvis/silence/non-dite', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() },
      body: JSON.stringify({ id: m.id }) }).catch(() => {});
  }
  if (dire) { aDire.push({ id: m.id, texte: m.texte, recu: Date.now() }); direSpontanes(); }
}
/* Ses résultats « de lui-même » DITS dans la conversation (demande d'Ahmed relayée par Hakim, 2026-10-20 : « il arrive à
   l'écran mais je ne l'entends pas ») : avant, le message n'était dit que si TOUT était libre à l'instant même où il
   arrivait (Ahmed se taisait, Hakim ne répondait pas déjà…) — sinon il était perdu pour l'oreille. Désormais il attend
   son tour : dit dès qu'Ahmed s'est tu depuis 1,5 s et que rien d'autre ne parle ; jamais par-dessus sa parole.
   Plus d'oubli après 10 min ; voix éteinte, la file attend ; gardée dans le navigateur si la page se recharge.
   (30/10, 14:50, Ahmed, relayé par Hakim et confirmé : « plus de redites de lui-même ») ce qu'il n'a pas pu dire quand
   Ahmed l'a coupé ou a enchaîné (garderNonDit) n'entre plus dans cette file, et ne se redit plus jamais de lui-même (fini
   « Je reprends ce que je disais… » et la synthèse) : il part TOUT DE SUITE au cockpit, gardé « dit mais pas entendu »
   (une file de secours dans ce navigateur si le Mac ne répond pas : renvoyée au chargement, au prochain message et au
   prochain envoi), et Hakim ne le redit que si Ahmed le demande (« répète », « j'ai pas entendu », « tu disais quoi ? »…).
   Cette file ne garde que ses résultats NOUVEAUX (un agent, une mesure), dits un par un au calme. */
const aDire = [];
try { for (const x of JSON.parse(localStorage.getItem('jarvis.aDire') || '[]')) if (x && typeof x.texte === 'string') aDire.push(x); } catch (_) {}
const sauverADire = () => { try { localStorage.setItem('jarvis.aDire', JSON.stringify(aDire.slice(-20))); } catch (_) {} };
const nonDitsAEnvoyer = [];                       // le secours : ce que le cockpit n'a pas encore reçu
try { for (const x of JSON.parse(localStorage.getItem('jarvis.nonDits') || '[]')) if (x && typeof x.texte === 'string') nonDitsAEnvoyer.push(x); } catch (_) {}
const sauverNonDits = () => { try { localStorage.setItem('jarvis.nonDits', JSON.stringify(nonDitsAEnvoyer.slice(-40))); } catch (_) {} };
const idNonDit = () => `nd-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
// une suite coupée, telle que le cockpit la garde : son texte, « coupée », l'heure de la réponse d'origine
const versNonDit = (x) => ({ id: typeof x.nd === 'string' ? x.nd : idNonDit(), texte: String(x.texte || ''), coupe: true,
  origine_ts: Number(x.origine_ts) || quandMessage({ id: x.id, ts: x.ts }) || Number(x.recu) || Date.now() });
// reçus par le cockpit (ici, ou avec un message d'Ahmed) : retirés du secours
function nonDitsRecus(ids) {
  const recus = new Set(ids);
  const restants = nonDitsAEnvoyer.filter(x => !recus.has(x.id));
  if (restants.length === nonDitsAEnvoyer.length) return;
  nonDitsAEnvoyer.splice(0, nonDitsAEnvoyer.length, ...restants);
  sauverNonDits();
}
let nonDitsEnVol = false;
async function envoyerNonDits(nouveaux = []) {
  if (nouveaux.length) { nonDitsAEnvoyer.push(...nouveaux); sauverNonDits(); }
  if (nonDitsEnVol || !nonDitsAEnvoyer.length) return;
  nonDitsEnVol = true;
  const lot = nonDitsAEnvoyer.slice(0, 12);
  let ok = false;
  try {
    const r = await fetch('/api/jarvis/non-dites', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() },
      body: JSON.stringify({ textes: lot }) });
    if (!r.ok) throw new Error(`non-dites ${r.status}`);
    ok = true;
    nonDitsRecus(lot.map(x => x.id));
    journalVoix('non_dits_gardes', { n: lot.length });
  } catch (_) { journalVoix('non_dits_secours', { n: nonDitsAEnvoyer.length }); }   // rien n'est jeté : ils attendent ici
  finally { nonDitsEnVol = false; }
  if (ok && nonDitsAEnvoyer.length) envoyerNonDits();
}
// (30/10) les anciennes suites coupées de la file (une page d'avant) partent au cockpit : rien n'est jeté, rien n'est redit
function sortirLesCoupees() {
  const coupees = aDire.filter(x => x && x.coupe);
  if (!coupees.length) return;
  aDire.splice(0, aDire.length, ...aDire.filter(x => !(x && x.coupe)));
  sauverADire();
  envoyerNonDits(coupees.map(versNonDit));
}
sortirLesCoupees();
envoyerNonDits();                                 // ce qu'une page précédente n'a pas pu envoyer
let parlaitA = 0;
function garderNonDit() {
  if (!(etat.conversation || etat.reglages.volant || etat.reglages.lectureAuto)) return;   // voix éteinte : il lit à l'écran
  // (21:26, la boucle vue par Hakim) d'où vient ce qui est coupé : sa réponse (son heure)
  const source = etat.messages.find(x => x.id === etat.lectureDe);
  // (relecture du 27/10) une relance de silence coupée n'est pas gardée : Ahmed a repris, c'était un « non »
  if (source && source.spontane === 'silence') return;
  const origine = (source && Number(source.origine_ts)) || quandMessage(source) || Date.now();
  const morceaux = lecteurNeuronal.restant().map(x => x.texte);
  if (etat.decoupeFlux) morceaux.push(...etat.decoupeFlux.finir());          // la phrase qui arrivait encore
  // (une ancienne reprise « Je reprends ce que je disais… » coupée : sans cette annonce)
  const texte = morceaux.join(' ').replace(/\s+/g, ' ').trim().replace(/^(je reprends ce que je disais( à \d{1,2} h \d{2})?\s*:\s*)+/i, '');
  if (!/\p{L}{2,}/u.test(texte) || NON_REPONSE.test(texte)) return;
  envoyerNonDits([{ id: idNonDit(), texte, coupe: true, origine_ts: origine }]);
  journalVoix('non_dit_garde', { car: texte.length, en_attente: nonDitsAEnvoyer.length });
}
function direSpontanes() {
  const c = etat.conversation;
  if (c && c.capteur && c.capteur.enParole) parlaitA = Date.now();
  sortirLesCoupees();                                // (30/10) une suite coupée ne se redit jamais d'elle-même
  const voix = c || etat.reglages.volant || etat.reglages.lectureAuto;
  if (!voix || !aDire.length || (c && (c.tourGarde || (c.ecritGarde || []).length))) return;          // (vers 22 h 10) ce que papa a dit pendant son tour passe d'abord
  if (!lecteur || etat.flux || etat.micro || etat.transcription || !jarvisPeutParler() || lecteur.actif || lecteur.enPause
      || Date.now() - Math.max(parlaitA, etat.finVoixA || 0) < 1500) return;
  const m = aDire.shift();
  sauverADire();
  if (NON_REPONSE.test(m.texte)) return;
  // (30/10, vers 22 h, Ahmed : « qu'il ne garde que ce qu'il veut vraiment dire ») en conversation, ce qui a attendu plus de 45 s
  // n'est plus le présent : pas dit (il reste écrit)
  const age = Date.now() - (Number(m.recu) || 0);
  if (c && age > 45000) { journalVoix('a_dire_perime', { age_s: Math.min(99999, Math.round(age / 1000)) }); return; }
  if (typeof voixEpissee === 'function' && voixEpissee()) { versRibosome(m.texte); return; }
  etat.lectureDe = m.id;
  lecteur.dire(m.texte);
  lecteur.finFlux();
  humeur();
}
setInterval(direSpontanes, 500);

/* ---------- Meubler les silences (27/10 ; idée d'Ahmed, portée par Hakim ; serveur et silences.js) : la page compte le
   silence, elle seule entend. Il part de la plus récente activité : la fin de sa parole, toute voix au micro (même un
   invité, la télé), un message envoyé ou reçu, une frappe. À l'oral (Conversation), ou à l'écrit page visible pendant une
   conversation (un message d'Ahmed de moins de 30 min). Rien en mode volant, micro coupé, pendant qu'il parle ou qu'un
   message attend d'être dit. Au seuil donné par le cockpit, elle le signale ; le cockpit dit quand revenir, ou plus. ---------- */
function debutDuSilence() {
  const c = etat.conversation;
  const voix = c && c.capteur ? Number(c.capteur.derniereVoix) || 0 : 0;
  const dernier = etat.messages.length ? quandMessage(etat.messages[etat.messages.length - 1]) : 0;
  return Math.max(etat.finVoixA || 0, voix, parlaitA || 0, etat.derniereActivite || 0, dernier || 0);
}
// (28/10, « test échoué » : 105 s avant le premier signal au lieu de ~60, téléphone plié, sans trace) ce qui empêche la page
// de compter, nommé pour le diagnostic de la voix ; null : elle compte
function silenceBloquePar() {
  const voix = etat.conversation || etat.reglages.volant || etat.reglages.lectureAuto;   // voix éteinte : la file ne se vide pas, elle ne compte pas
  if (etat.reglages.volant) return 'volant';
  if (etat.flux) return 'reponse_en_cours';
  if (etat.micro) return 'micro';
  if (etat.transcription) return 'transcription';
  if (!lecteur) return 'sans_lecteur';
  if (lecteur.actif) return 'il_parle';
  if (lecteur.enPause) return 'voix_en_pause';
  if (voix && aDire.length) return 'a_dire';
  const c = etat.conversation;
  if (c) return !c.capteur ? 'sans_capteur' : c.capteur.estMuet ? 'micro_coupe' : c.capteur.enParole ? 'on_parle' : c.capteur.pisteMuette ? 'piste_muette' : null;
  if (document.visibilityState !== 'visible') return 'page_cachee';
  const u = etat.messages.filter(m => m.qui === 'u').slice(-1)[0];
  return u && Date.now() - quandMessage(u) < 30 * 60000 ? null : 'pas_de_conversation';
}
function modeDuSilence() {
  if (silenceBloquePar()) return null;
  return etat.conversation ? 'oral' : 'ecrit';
}
// un blocage de 10 s ou plus, noté quand il finit (sa cause, sa durée, page cachée ou non)
let blocageSilence = { cause: null, depuis: 0 };
function noterBlocageSilence(cause, now = Date.now()) {
  const b = blocageSilence;
  if (cause === b.cause) return;
  if (b.cause && now - b.depuis >= 10000) journalVoix('silence_bloque', { cause: b.cause, ms: now - b.depuis, cachee: document.visibilityState === 'hidden' });
  blocageSilence = { cause, depuis: now };
}
let signalSilence = { debut: 0, prochain: 0, fini: false, envoiA: 0 };
const nosSilences = new Set();                                  // les repères des silences que CETTE page a signalés
function compterSilence() {
  const bloque = silenceBloquePar();
  noterBlocageSilence(bloque);
  if (bloque) return;
  const mode = etat.conversation ? 'oral' : 'ecrit';
  const debut = debutDuSilence();
  if (!debut) return;
  if (debut !== signalSilence.debut) signalSilence = { debut, prochain: mode === 'oral' ? 30000 : 90000, fini: false, envoiA: 0 };
  const s = signalSilence;
  if (s.fini || Date.now() - debut < s.prochain || Date.now() - s.envoiA < 5000) return;
  s.envoiA = Date.now();
  nosSilences.add(debut); if (nosSilences.size > 20) nosSilences.delete(nosSilences.values().next().value);
  journalVoix('silence_signal', { mode, silence_s: Math.round((Date.now() - debut) / 1000), cachee: document.visibilityState === 'hidden' });
  fetch('/api/jarvis/silence', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() },
    body: JSON.stringify({ debut_ms: debut, silence_ms: Date.now() - debut, mode }) })
    .then(r => (r.ok ? r.json() : null)).then((o) => {
      journalVoix('silence_reponse', o ? { raison: String(o.raison || ''), ...(o.revenir_ms == null ? {} : { revenir_s: Math.round(Number(o.revenir_ms) / 1000) }) } : { raison: 'erreur' });
      if (!o || signalSilence !== s) return;
      if (o.revenir_ms == null) s.fini = true;
      else s.prochain = Math.max(s.prochain, Number(o.revenir_ms) || 0);
    }).catch(() => journalVoix('silence_reponse', { raison: 'reseau' }));
}
setInterval(compterSilence, 2000);
$('fil').addEventListener('click', async (e) => {
  const b = e.target.closest('[data-relance]');
  if (!b) return;
  b.disabled = true;
  const k = aDire.findIndex(x => x.id === b.dataset.relance);      // pas encore dite : elle ne le sera pas
  if (k >= 0) { aDire.splice(k, 1); sauverADire(); }
  if (etat.lectureDe === b.dataset.relance) { finirParole('stop', '« pas maintenant »'); lecteur.arreter(); }
  try {
    const r = await fetch('/api/jarvis/silence/pas-maintenant', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() },
      body: JSON.stringify({ id: b.dataset.relance }) });
    if (!r.ok) throw new Error(`erreur ${r.status}`);
    b.textContent = '✋ compris : il se tait 30 min';
    humeur('Hakim se tait pendant 30 min');
    lireSilencesEtat();
  } catch (_) { b.disabled = false; humeur('« pas maintenant » n’a pas pu partir'); }
});
async function lireSilencesEtat() {
  try {
    const o = await (await fetch('/api/jarvis/silence')).json();
    const suspendu = o.suspendu_jusqua_ms ? ` · en silence jusqu'à ${new Date(o.suspendu_jusqua_ms).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}` : '';
    $('etatSilences').textContent = (o.actif ? 'oui' : 'coupé') + suspendu
      + ` · patience apprise ${String(o.patience).replace('.', ',')}` + (o.questions ? ` · aujourd'hui : ${o.questions} silence(s) pesé(s), ${o.relances} relance(s)` : '');
    $('silencesInterrupteur').textContent = o.actif ? 'Couper' : 'Remettre';
    $('silencesInterrupteur').setAttribute('aria-pressed', String(!o.actif));
  } catch (_) {}
}
$('silencesInterrupteur').addEventListener('click', async () => {
  const actif = $('silencesInterrupteur').getAttribute('aria-pressed') === 'true';
  try {
    const r = await fetch('/api/jarvis/silence/reglage', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() },
      body: JSON.stringify({ actif }) });
    if (!r.ok) throw new Error();
    humeur(actif ? 'Hakim peut de nouveau reprendre la parole dans les silences' : 'Hakim ne reprend plus la parole dans les silences');
  } catch (_) { humeur('réglage des silences indisponible'); }
  lireSilencesEtat();
});
lireSilencesEtat(); setInterval(lireSilencesEtat, 60000);

/* ---------- le Mac injoignable (2026-10-23, Ahmed en voiture : il a parlé 9 min sans que rien n'arrive ni ne s'affiche)
   Réseau coupé, cockpit qui redémarre : l'écran le dit en clair ; ce que tu dis est gardé (l'audio de chaque tour), les
   messages partis sans arriver aussi ; toutes les 5 s, la page regarde si le Mac répond. Dès qu'il répond : les messages
   non reçus repartent, puis ce que tu as dit pendant la coupure est transcrit dans l'ordre et part en UN message.
   Rien n'est jeté : un tour transcrit garde son texte même si la suite échoue encore. ---------- */
// hors de .parler (son z-index 1 la mettrait sous la barre du cockpit) : au-dessus de tout
try { document.body.appendChild($('horsLigne')); } catch (_) {}
function montrerHorsLigne(texte, revenu = false) {
  const b = $('horsLigne');
  if (!texte) { b.hidden = true; return; }
  b.textContent = texte; b.classList.toggle('revenu', revenu); b.hidden = false;
}
function texteHorsLigne() {
  const n = horsLigne.tours.length + horsLigne.envois.length;
  const quoi = horsLigne.panne === 'serveur' ? 'La transcription ne répond pas sur le Mac'
    : horsLigne.panne === 'lent' ? 'Le Mac est débordé (il transcrit très lentement)' : 'Pas de connexion avec le Mac';
  return `${quoi} — je garde ce que tu dis`
    + `${n ? ` (${n} message${n > 1 ? 's' : ''} en attente)` : ''}, et je l’envoie dès qu’il répond.`;
}
function noterHorsLigne() {
  if (!horsLigne.depuis) { horsLigne.depuis = Date.now(); journalVoix('hors_ligne'); }
  montrerHorsLigne(texteHorsLigne());
  humeur('pas de connexion avec le Mac : je garde ce que tu dis');
}
function garderHorsLigne(wav, t) {
  if (horsLigne.tours.length < 60) horsLigne.tours.push({ wav, t, texte: null });   // (une heure de parole, au plus)
  journalVoix('tour_garde', { en_attente: horsLigne.tours.length });
  noterHorsLigne();
}
// (2026-10-23, journal du téléphone : 18:56, onze transcriptions refusées « 403 » après une relance du cockpit) le jeton
// de la page change à chaque démarrage du cockpit ; avant, il fallait recharger la page à la main. Elle le reprend seule :
// la page Parler, redemandée au cockpit (même session), porte le nouveau.
let jetonEnCours = null;
function rafraichirJeton() {
  if (!jetonEnCours) jetonEnCours = (async () => {
    try {
      const t = await (await fetch('/parler', { cache: 'no-store' })).text();
      const m = t.match(/<meta name="cockpit-jeton" content="([0-9a-f]{20,200})">/);
      const meta = document.querySelector('meta[name="cockpit-jeton"]');
      if (!m || !meta || meta.content === m[1]) return false;
      meta.content = m[1];
      journalVoix('jeton_renouvele');
      return true;
    } catch (_) { return false; } finally { setTimeout(() => { jetonEnCours = null; }, 2000); }
  })();
  return jetonEnCours;
}
// la réponse du Mac ({ ok, o }), ou null s'il ne répond pas du tout (réseau coupé, cockpit arrêté)
async function demanderMac(url, ms = 4000) {
  const ctl = new AbortController(), minuteur = setTimeout(() => ctl.abort(), ms);
  try {
    const r = await fetch(url, { headers: { 'X-Jeton': jeton() }, signal: ctl.signal, cache: 'no-store' });
    return { ok: r.ok, statut: r.status, o: r.ok ? await r.json().catch(() => null) : null };
  } catch (_) { return null; } finally { clearTimeout(minuteur); }
}
const heureCourte = (ms) => new Date(ms).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
async function reprendreHorsLigne() {
  if (!horsLigne.depuis || horsLigne.enCours) return;
  horsLigne.enCours = true;
  try {
    const ping = await demanderMac('/api/jarvis/recu?tour_id=ping');
    if (!ping) return;                                                       // toujours injoignable
    if (!ping.ok) await rafraichirJeton();                                   // 403 : le cockpit a redémarré, nouveau jeton
    // 1. les messages partis pendant la coupure : renvoyés seulement si le Mac ne les a pas reçus (sinon sa réponse
    //    revient par la synchronisation)
    while (horsLigne.envois.length) {
      const e = horsLigne.envois[0];
      const r = await demanderMac(`/api/jarvis/recu?tour_id=${encodeURIComponent(e.tourId)}`);
      if (!r) return;
      horsLigne.envois.shift();
      if (r.ok && r.o && r.o.recu) continue;                                 // dans le doute, renvoyé : rien n'est perdu
      if (!e.m.texte) { const i = etat.messages.indexOf(e.m); if (i >= 0) etat.messages.splice(i, 1); }
      montrerHorsLigne('Connexion revenue — je renvoie ton message', true);
      await envoyer(e.texte, e.oral, { joints: [] });
    }
    // 2. ce que tu as dit pendant la coupure : transcrit dans l'ordre (chaque texte gardé dès qu'il est compris)
    for (const t of horsLigne.tours) {
      if (t.texte !== null) continue;
      // (05/11, 10:20, Ahmed : « la bande jaune : 9 messages en attente ; jeter à la poubelle tout ce qui est trop ancien, et le laisser sur le téléphone, ça
      // allège le Mac ») ils attendent ici, sur le téléphone ; le Mac débordé : plus vieux que 30 s, jeté sans lui être envoyé. Une vraie coupure du réseau
      // (papa en voiture, le 23/10) garde tout : le Mac n'y est pour rien
      if (horsLigne.panne !== 'reseau' && Date.now() - t.t > HORS_LIGNE_MAX_MS) { t.texte = ''; t.wav = null; journalVoix('tour_jete', { age_ms: Date.now() - t.t }); continue; }
      montrerHorsLigne('Connexion revenue — je transcris ce que tu as dit…', true);
      const x = await transcrireVite(t.wav, 'audio/wav');
      if (x === null) return;                                                // coupé de nouveau : on reprendra ici
      t.texte = x;
    }
    const tours = horsLigne.tours.splice(0);
    const dit = tours.map(t => t.texte).filter(x => Conversation.utile(x));
    journalVoix('retour_en_ligne', { duree_ms: Date.now() - horsLigne.depuis, tours: tours.length });
    horsLigne.depuis = 0;
    envoyerJournalVoix();
    if (dit.length) {
      montrerHorsLigne('Connexion revenue — j’envoie ce que tu as dit', true);
      setTimeout(() => { if (!horsLigne.depuis) montrerHorsLigne(''); }, 4000);
      await envoyer(`(dit pendant la coupure, de ${heureCourte(tours[0].t)} à ${heureCourte(tours[tours.length - 1].t)}) ${dit.join(' … ')}`, true);
    } else { montrerHorsLigne('Connexion revenue', true); setTimeout(() => { if (!horsLigne.depuis) montrerHorsLigne(''); }, 3000); }
  } finally { horsLigne.enCours = false; }
}
setInterval(reprendreHorsLigne, 5000);

/* ---------- le micro bloqué par le téléphone (2026-10-23, 18:08 : un appel de sa mère, puis 9 min où rien ne passait,
   sans un événement) : pendant un appel, Android prend le micro et le son ; au retour, le flux de la page peut rester
   arrêté sans que rien ne le signale. La page surveille les trames du micro : plus rien depuis 2,5 s en conversation →
   c'est dit (bandeau), noté au diagnostic, et le son est relancé (suspendre puis reprendre le contexte audio) toutes les
   3 s ; un toucher sur le bandeau relance la conversation entière. ---------- */
const veilleMicro = { bloqueDepuis: 0, relance: 0 };
function finBlocageMicro() {
  journalVoix('micro_repris', { apres_ms: Date.now() - veilleMicro.bloqueDepuis });
  veilleMicro.bloqueDepuis = 0;
  if (!horsLigne.depuis) montrerHorsLigne('');
}
function surveillerMicro() {
  const c = etat.conversation;
  if (!c || !c.capteur || !actx || c.capteur.derniereTrame === undefined) { if (veilleMicro.bloqueDepuis) finBlocageMicro(); return; }
  const muet = Date.now() - c.capteur.derniereTrame, prise = !!c.capteur.pisteMuette;
  if (muet < 2500 && !prise) { if (veilleMicro.bloqueDepuis) finBlocageMicro(); return; }
  if (!veilleMicro.bloqueDepuis) {
    veilleMicro.bloqueDepuis = Date.now();
    journalVoix('micro_bloque', { etat: actx.state, piste_muette: !!c.capteur.pisteMuette, cachee: document.visibilityState === 'hidden' });
  }
  if (muet < 2500) {                                     // le téléphone a pris le micro (un appel) : il le rendra
    montrerHorsLigne('Le téléphone a pris le micro (un appel ?) — je reprends dès qu’il le rend. Touche ce bandeau si ça dure.');
    return;
  }
  montrerHorsLigne('Le micro ne reçoit plus rien — je relance le son… Touche ce bandeau si ça dure.');
  if (Date.now() - veilleMicro.relance > 3000) {
    veilleMicro.relance = Date.now();
    actx.suspend().catch(() => {}).finally(() => actx.resume().catch(() => {}));
  }
}
setInterval(surveillerMicro, 1000);
$('horsLigne').addEventListener('click', () => {
  if (!veilleMicro.bloqueDepuis || !etat.conversation) return;
  journalVoix('micro_relance_main', { apres_ms: Date.now() - veilleMicro.bloqueDepuis });
  finirConversation(false);
  setTimeout(() => { if (!etat.conversation) basculerConversation(); }, 400);
});
const accuses = new Set();
async function accuserReception() {
  if (document.visibilityState !== 'visible') return;      // « vu » = affiché sur un écran visible, pas reçu en fond
  // (28/10, 06:44) sa relance d'un silence aussi : sans accusé, le cockpit lui disait « non vu » alors qu'elle était à l'écran
  const ids = etat.messages.filter(x => (x.spontane === 'resultat' || x.spontane === 'silence') && !accuses.has(x.id)).map(x => x.id).slice(-200);
  if (!ids.length) return;
  ids.forEach(id => accuses.add(id));
  try {
    await fetch('/api/jarvis/vu', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() }, body: JSON.stringify({ ids }) });
  } catch (_) { ids.forEach(id => accuses.delete(id)); }
}

// Une tâche de fond de Hakim vient de se terminer (lot C, 2026-10-19) : affichée ; Hakim en verra le résultat au message suivant
// ([Tâches]). (04/11, 10:35, Ahmed : « il doit pouvoir choisir ce qu'il dit, et pas seulement dire "ma tâche de fond est terminée" »)
// plus de phrase toute faite dans sa bouche, ni écrite ni dite : une ligne de fait, puis c'est lui, réveillé par le cockpit
// (reveillerPourTaches), qui choisit ce qu'il en dit, ou de se taire.
function surTache(o) {
  const id = 'tache-' + o.id;
  if (etat.messages.some(m => m.id === id)) return;
  const fini = o.etat === 'finie' && o.code === 0;
  const texte = `« ${o.commande} » : ${fini ? 'terminée' : o.etat}${o.raison ? ' (' + o.raison + ')' : ''} en ${Math.round(o.duree_s || 0)} s. `
    + (o.reveil ? 'Il regarde le résultat, puis il choisit ce qu’il t’en dit.' : 'Demande-lui le résultat.');
  etat.messages.push({ id, qui: 'j', spontane: 'tache', texte, ts: Date.now() });
  sauver(); rendre();
  humeur(fini ? 'une tâche de fond est terminée' : 'une tâche de fond s’est arrêtée');
  notifierApp(fini ? 'Tâche de fond terminée' : 'Tâche de fond arrêtée', texte, id);
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
  $('modele').disabled = $('modeleConversation').disabled = r.source === 'local' || r.source === 'gemma';   // le local n'a qu'un modèle
  $('reconnaissance').value = r.reconnaissance; $('langue').value = r.langue;
  $('patience').value = String(r.patience);
  $('patienceConversation').value = String(r.patienceConversation ?? 0.3);
  $('vitesse').value = r.vitesse; $('lectureAuto').checked = !!r.lectureAuto; $('voix').value = r.voix;
  $('sceneActive').checked = r.scene !== false;
  $('rapide').checked = r.rapide !== false;
  $('position').checked = !!r.position; suivrePosition(!!r.position);
  $('voixNeutre').checked = !!r.voixNeutre;
  majSesParoles();
  $('btnVolant').setAttribute('aria-pressed', String(!!r.volant)); $('btnVolant').classList.toggle('actif', !!r.volant);
  $('voixFr').disabled = $('voixAr').disabled = r.voix === 'neuronale' && etat.ttsLocal;
  // « auto » (le défaut depuis le 2026-10-18) : Whisper choisit entre français, arabe et anglais (jarvis/stt.py).
  // Vu le 2026-10-16 : un français précédé d'un salam a déjà été pris pour de l'arabe ; « français » reste
  // au choix pour forcer la langue.
}
for (const [id, cle, val] of [['source', 'source', e => e.value], ['modele', 'modele', e => e.value], ['modeleConversation', 'modeleConversation', e => e.value], ['reconnaissance', 'reconnaissance', e => e.value],
  ['langue', 'langue', e => e.value], ['voixFr', 'voixFr', e => e.value], ['voixAr', 'voixAr', e => e.value],
  ['vitesse', 'vitesse', e => parseFloat(e.value) || 1], ['lectureAuto', 'lectureAuto', e => e.checked],
  ['patience', 'patience', e => parseFloat(e.value)], ['patienceConversation', 'patienceConversation', e => parseFloat(e.value)],
  ['voix', 'voix', e => e.value], ['sceneActive', 'scene', e => e.checked], ['rapide', 'rapide', e => e.checked],
  ['position', 'position', e => e.checked], ['voixNeutre', 'voixNeutre', e => e.checked]]) {
  $(id).addEventListener('change', (ev) => { etat.reglages[cle] = val(ev.target); appliquerReglages(); sauver(); });
}
/* ---------- (28/10, Ahmed : « pas de coulisses ») « En off » : les lettres entre Hakim et maman, dans les deux sens,
   et chaque réveil de maman par une lettre de Hakim ; rafraîchi tant que le panneau est ouvert ---------- */
let enOffMinuteur = null;
async function afficherEnOff() {
  const liste = $('enOffListe');
  try {
    let r = await fetch('/api/jarvis/en-off', { headers: { 'X-Jeton': jeton() }, cache: 'no-store' });
    if (r.status === 403 && await rafraichirJeton()) r = await fetch('/api/jarvis/en-off', { headers: { 'X-Jeton': jeton() }, cache: 'no-store' });
    if (!r.ok) throw new Error(String(r.status));
    const o = await r.json();
    liste.textContent = '';
    if (!o.lignes || !o.lignes.length) { liste.textContent = 'Rien pour l\'instant.'; return; }
    for (const l of o.lignes) {
      const d = document.createElement('div'); d.className = 'en-off-ligne';
      const t = document.createElement('div'); t.className = 'en-off-tete';
      const quand = new Date(l.ts * 1000).toLocaleString('fr-FR', { weekday: 'short', day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
      t.textContent = `${quand} · ${l.type === 'reveil' ? 'réveil de maman' : 'lettre'} · ${l.de} → ${l.a}`;
      const s = document.createElement('div'); s.className = 'en-off-sujet'; s.textContent = l.sujet || '(sans sujet)';
      d.append(t, s);
      if (l.externe) { const e = document.createElement('div'); e.className = 'en-off-externe'; e.textContent = 'écrite après la lecture d\'un contenu externe'; d.append(e); }
      const det = document.createElement('details');
      const sum = document.createElement('summary'); sum.textContent = 'lire';
      const p = document.createElement('p'); p.className = 'en-off-texte'; p.textContent = l.texte || '';
      det.append(sum, p); d.append(det);
      liste.append(d);
    }
  } catch (_) { liste.textContent = 'Impossible de lire le journal « en off » pour l\'instant.'; }
}
$('btnEnOff').addEventListener('click', () => {
  const s = $('enOff'); s.hidden = !s.hidden;
  $('btnEnOff').setAttribute('aria-expanded', String(!s.hidden));
  clearInterval(enOffMinuteur);
  if (!s.hidden) { afficherEnOff(); enOffMinuteur = setInterval(afficherEnOff, 30000); }
});

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
  arreterTout(true, { raison: 'nouvelle' }); arreterMicro(false);
  etat.session = null; etat.messages = [];
  debutConversation = Date.now();                         // partagée : l'autre appareil repart aussi de zéro
  sauver(); rendre(); humeur();
});
$('micro').addEventListener('click', basculerMicro);
$('envoyer').addEventListener('click', () => envoyerEcrit($('q').value));
$('stop').addEventListener('click', () => { arreterTout(); libererRibosomes(); majBoutonsPause(); rendre(); humeur(); });
$('q').addEventListener('input', () => { ajuster(); activite(); });
$('q').addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); envoyerEcrit($('q').value); }
});
document.addEventListener('keydown', (e) => {
  if (e.altKey && e.code === 'KeyM') { e.preventDefault(); basculerMicro(); }
  else if (e.altKey && e.code === 'KeyC') { e.preventDefault(); basculerConversation(); }
  else if (e.altKey && e.code === 'KeyX') { e.preventDefault(); basculerMuet(); }
  else if (e.altKey && e.code === 'KeyV') { e.preventDefault(); basculerCamera(); }
  else if (e.altKey && e.code === 'KeyP') { e.preventDefault(); if (lecteur.enPause) reprendreVoix(); else pauseVoix(); }
  else if (e.key === 'Escape') { if (etat.conversation) finirConversation(false); arreterMicro(false); arreterTout(); libererRibosomes(); majBoutonsPause(); rendre(); humeur(); }
});
/* (31/10, 00:30, Ahmed : « un bouton Télépathie sous Conversation : le réglage actuel, automatiquement, sans mes textes ni les
   siens ») Conversation : vos paroles s'écrivent ; Télépathie : la Conversation sans aucun texte écrit, avec son oreille, son
   micro, chacun son tour et son subconscient allumés. Le réglage part au cockpit (page SENS) ; un deuxième appui ferme. */
async function reglerAffichage(telepathie) {
  const reglage = telepathie ? { afficher_papa: false, afficher_hakim: false, oreille: true, micro_hakim: true, chacun_son_tour: true, filtre_parole: true }
    : { afficher_papa: true, afficher_hakim: true };
  reglagesCorps = { ...reglagesCorps, ...reglage };
  try { await fetch('/api/corps/reglages', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() }, body: JSON.stringify(reglage) }); } catch (_) {}
}
async function lancerConversation(telepathie) {
  if (etat.conversation) return basculerConversation();     // en cours : le bouton la ferme
  await reglerAffichage(telepathie);
  $('telepathie').setAttribute('aria-pressed', telepathie ? 'true' : 'false');
  journalVoix('conversation_mode', { mode: telepathie ? 'telepathie' : 'texte' });
  rendre();
  return basculerConversation();
}
$('conversation').addEventListener('click', () => lancerConversation(false));
$('telepathie').addEventListener('click', () => lancerConversation(true));
$('finConversation').addEventListener('click', (e) => { e.stopPropagation(); finirConversation(); });
$('muet').addEventListener('click', basculerMuet);
$('sonHakim').addEventListener('click', () => { couperSon(); });
// (04/11, 10:20, Ahmed : « qu'il soit aussi possible de réafficher ses paroles dans le mode normal et le mode Conversation »)
function basculerSesParoles() {
  const cle = typeof voixEpissee === 'function' && voixEpissee() ? 'sesParolesEpissage' : 'sesParoles';   // (17:05) avec l'épissage, le sien
  etat.reglages[cle] = !etat.reglages[cle];
  sauver(); majSesParoles(); rendre();
}
function majSesParoles() {
  const cle = typeof voixEpissee === 'function' && voixEpissee() ? 'sesParolesEpissage' : 'sesParoles';
  for (const id of ['sesParoles', 'sesParolesScene']) { const b = $(id); if (b) b.setAttribute('aria-pressed', String(!!etat.reglages[cle])); }
}
$('sesParoles').addEventListener('click', basculerSesParoles);
$('sesParolesScene').addEventListener('click', (e) => { e.stopPropagation(); basculerSesParoles(); });
$('pause').addEventListener('click', () => {
  if (lecteur.enPause) reprendreVoix();
  else if (!pauseVoix()) humeur('il ne parle pas en ce moment : rien à mettre en pause');
});
$('camera').addEventListener('click', basculerCamera);
// (04/11) la page s'ouvre (ou se recharge) pendant que la caméra de la bulle ou d'un widget tourne : Parler la reprend
setTimeout(() => { if (!etat.vision && cameraApp() && window.HakimApp.cameraOrbeEtat()) basculerCamera(); }, 1500);
$('muetScene').addEventListener('click', (e) => { e.stopPropagation(); basculerMuet(); });
window.addEventListener('pagehide', () => {
  finirParole('appli', 'la page a été fermée, quittée ou rechargée');   // (30/10) part au cockpit même la page fermée (keepalive)
  finirConversation(false);
  arreterCamera(true);                    // (04/11) la caméra de l'appli continue pour la bulle et les widgets ; la page rechargée la reprend
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
reglesAuChargement(); carnetsAuChargement(); retractationsAuChargement();
identiteAuChargement();
sortiesAuChargement(); membresAuChargement();
// (03/11, Ahmed : « si je mets de la musique, il l'entend et la reconnaît ») l'accès aux notifications n'est pas encore donné : on le
// dit une fois par jour, et un toucher sur le message ouvre le réglage
setTimeout(() => {
  try {
    if (!window.HakimApp || !window.HakimApp.ecouteMusique || window.HakimApp.ecouteMusique()) return;
    const jour = new Date().toDateString();
    if (localStorage.getItem('jarvis.ecouteMusique') === jour) return;
    localStorage.setItem('jarvis.ecouteMusique', jour);
    humeur('Pour que Hakim entende et reconnaisse ta musique : touche ici, puis active « Hakim » dans l’accès aux notifications');
    $('etat').addEventListener('click', () => { try { window.HakimApp.ouvrirEcouteMusique(); } catch (_) {} }, { once: true });
  } catch (_) {}
}, 4000);
anticorpsAuChargement();
signalementsAuChargement();
// (04/11, Ahmed : « pour que l'autorisation du signalement s'affiche, je dois rafraîchir la page, c'est relou ») l'appli en arrière-plan
// manque des messages du flux : au retour sur la page, et toutes les 20 s, ses signalements et anticorps en attente sont relus
document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') { signalementsAuChargement(); anticorpsAuChargement(); } });
setInterval(() => { if (document.visibilityState === 'visible') { signalementsAuChargement(); anticorpsAuChargement(); } }, 20000);
$('q').focus();

/* ---------- ses calculs de fond, avec leur jauge (23/10, demande d'Ahmed relayée par Hakim) : le cockpit lit les lignes
   « PROGRESSION 3/8 » de leurs journaux et mesure le rythme ; la page montre fait, restant, écoulé, total estimé. Toutes
   les 10 s quand la page est visible ; rien ne s'affiche quand rien ne tourne. ---------- */
function dureeCourte(ms) {
  const m = Math.round(Math.max(0, ms) / 60000);
  return m < 1 ? 'moins d’1 min' : m < 60 ? `${m} min` : `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, '0')}`;
}
function htmlCalcul(x) {
  const connu = typeof x.fraction === 'number', pc = connu ? Math.round(x.fraction * 100) : null;
  const quoi = (x.libelle ? `${x.libelle} · ` : '') + String(x.commande || '').replace(/^cd \S+ && /, '');
  const fait = connu ? `${x.etape ? `${x.etape} · ` : ''}${x.devinee ? '≈ ' : ''}${pc} %` : 'en cours';
  const details = [`depuis ${dureeCourte(x.ecoule_ms)}`];
  if (typeof x.reste_ms === 'number') {
    details.push(`reste ≈ ${dureeCourte(x.reste_ms)}`, `total ≈ ${dureeCourte(x.total_ms)}`,
      `fin vers ${new Date(Date.now() + x.reste_ms).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}`);
  }
  // (25/10, Ahmed) sans jauge lisible : la dernière ligne de son journal, telle quelle
  if (!connu && x.derniere) details.push(`dernière ligne : « ${x.derniere} »`);
  else if (!connu) details.push('pas encore de sortie');
  return `<div class="calcul"><div class="ligne"><span class="quoi" title="${esc(x.commande)}">${esc(quoi)}</span>`
    + `<span class="chiffres">${esc(fait)}</span></div>`
    + `<div class="barre${connu ? '' : ' inconnue'}" role="progressbar" aria-label="${esc(quoi)}" aria-valuemin="0" aria-valuemax="100"${connu ? ` aria-valuenow="${pc}"` : ''}>`
    + `<span${connu ? ` style="width:${pc}%"` : ''}></span></div><div class="details">${esc(details.join(' · '))}</div></div>`;
}
async function chargerCalculs() {
  if (document.visibilityState !== 'visible') return;
  try {
    let r = await fetch('/api/jarvis/taches', { headers: { 'X-Jeton': jeton() }, cache: 'no-store' });
    if (r.status === 403 && await rafraichirJeton()) r = await fetch('/api/jarvis/taches', { headers: { 'X-Jeton': jeton() }, cache: 'no-store' });
    if (!r.ok) return;
    const { taches } = await r.json();
    const b = $('calculs');
    b.hidden = !(taches || []).length;
    if (!b.hidden) b.innerHTML = `<div class="titre">Calculs de Hakim en cours</div>${taches.map(htmlCalcul).join('')}`;
  } catch (_) {}
}
chargerCalculs(); setInterval(chargerCalculs, 10000);
document.addEventListener('visibilitychange', chargerCalculs);

/* (30/10, Ahmed : « quand je passe d'une page à l'autre du cockpit, si je suis en conversation, que la conversation ne se
   coupe pas ») sur le Mac, pendant une conversation, une autre page du cockpit s'ouvre dans un nouvel onglet : Parler reste
   chargée, sa conversation continue. Dans l'appli du téléphone, c'est son volet qui s'en charge (Parler reste dessous). */
function lienGardeConversation(e) {
  if (!etat.conversation || window.HakimApp || e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1) return;
  const a = e.target && e.target.closest && e.target.closest('a[href]');
  if (!a || a.target === '_blank') return;
  let u; try { u = new URL(a.getAttribute('href'), location.origin); } catch (_) { return; }
  if (u.origin !== location.origin || u.pathname.startsWith('/parler')) return;
  e.preventDefault();
  window.open(u.href, '_blank', 'noopener');
}
document.addEventListener('click', lienGardeConversation, true);

/* (30/10, Ahmed via Hakim : « l'historique des notes visible pour moi dans Parler ») la note de chaque travail de ses agents
   et l'appréciation de Hakim, la plus récente d'abord ; lues à l'ouverture du volet, posées en texte. */
(() => {
  const d = document.getElementById('notesAgents');
  if (!d) return;
  d.addEventListener('toggle', async () => {
    if (!d.open) return;
    const liste = document.getElementById('notesAgentsListe');
    try {
      const r = await fetch('/api/agents/notes', { headers: { 'X-Jeton': window.jeton() }, cache: 'no-store' });
      const o = await r.json();
      if (!r.ok) throw new Error(o.erreur || r.status);
      liste.replaceChildren();
      if (!o.agents.length) { liste.textContent = 'Aucun agent encore.'; return; }
      for (const a of o.agents) {
        const t = document.createElement('div'); t.style.marginTop = '8px';
        const b = document.createElement('b'); b.textContent = `${a.prenom || '(sans prénom)'}${a.surnom ? ` « ${a.surnom} »` : ''} — ${a.role} (expertise ${a.expertise})`; t.appendChild(b);
        t.appendChild(document.createTextNode(` · ${a.type} de naissance · ${a.description}`));
        for (const x of a.roles) {
          const l = document.createElement('div'); l.style.margin = '4px 0 0 10px';
          const quand = x.ts_ms ? new Date(x.ts_ms).toLocaleString('fr-FR', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '';
          l.textContent = `${quand} · rôle : ${x.de} → ${x.vers} (sa réponse : « ${x.sa_reponse} »)`;
          t.appendChild(l);
        }
        if (!a.notes.length) { const l = document.createElement('div'); l.style.margin = '4px 0 0 10px'; l.textContent = 'pas encore noté'; t.appendChild(l); }
        for (const n of a.notes.slice().reverse()) {
          const l = document.createElement('div'); l.style.margin = '4px 0 0 10px';
          const quand = n.ts_ms ? new Date(n.ts_ms).toLocaleString('fr-FR', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '';
          l.textContent = `${quand} · « ${n.travail} » : ${String(n.note).replace('.', ',')}/10${n.revisee ? ' (révisée)' : ''}${n.confirme_par ? ` — confirmé par ${n.confirme_par}` : ''} — ${n.appreciation}`;
          t.appendChild(l);
        }
        liste.appendChild(t);
      }
    } catch (e) { liste.textContent = `Les notes ne répondent pas (${e.message}).`; }
  });
})();

// (04/11, 16:40, Ahmed : « tu peux juste me rajouter un bouton quelque part pour que je redémarre le cockpit automatiquement, et push GitHub
// aussi ? ») dans les réglages : une confirmation, puis le cockpit publie (contrôles compris) et se relance ; son état est suivi ici, même
// pendant qu'il redémarre (la page attend son retour), jusqu'à « fini »
const ETAPES_RELANCE = { demande: 'demandée', travail: 'je regarde si quelqu’un travaille', publication: 'publication en cours',
  essai: 'essai du cockpit', relance: 'le cockpit redémarre…', fini: '' };
function montrerRelance(e) {
  const p = $('relanceEtat');
  if (!p || !e || !e.etape) return;
  const quand = e.ts ? new Date(Number(e.ts) * 1000).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }) : '';
  p.textContent = e.etape === 'fini' ? `${e.ok ? '✅' : '⚠️'} ${quand} : ${e.detail || ''} — publication : ${e.publication || '?'}`
    : `⏳ ${ETAPES_RELANCE[e.etape] || e.etape}${e.publication && e.publication !== 'non faite' ? ` — publication : ${e.publication}` : ''}`;
}
async function suivreRelance(fois = 0) {
  let e = null;
  try { const r = await fetch('/api/cockpit/relance-etat', { headers: { 'X-Jeton': jeton() }, cache: 'no-store' }); if (r.status === 403 && typeof rafraichirJeton === 'function') await rafraichirJeton(); else if (r.ok) e = await r.json(); } catch (_) {}
  if (e) montrerRelance(e);
  if ((!e || e.etape !== 'fini') && fois < 120) setTimeout(() => suivreRelance(fois + 1), 3000);
}
if ($('relancerPublier')) {
  $('relancerPublier').addEventListener('click', async () => {
    if (!confirm('Relancer le cockpit (Hakim sera coupé quelques secondes) et publier sur GitHub ?')) return;
    try {
      const r = await fetch('/api/cockpit/relancer-publier', { method: 'POST', headers: { 'X-Jeton': jeton() } });
      const o = await r.json().catch(() => ({}));
      if (!r.ok) { $('relanceEtat').textContent = `⚠️ ${o.erreur || 'refusé'}`; return; }
      montrerRelance({ etape: 'demande' });
      suivreRelance();
    } catch (_) { $('relanceEtat').textContent = '⚠️ le cockpit ne répond pas'; }
  });
  fetch('/api/cockpit/relance-etat', { headers: { 'X-Jeton': jeton() }, cache: 'no-store' }).then(r => (r.ok ? r.json() : null)).then((e) => {
    if (e && e.etape) { montrerRelance(e); if (e.etape !== 'fini') suivreRelance(); }
  }).catch(() => {});
}

// (04/11, 16:50, Ahmed : « il commence sa réflexion dès qu'une voix se fait entendre, avant même qu'elle parle : une parole vide au tout début
// de la voix déclenche la réflexion ») au premier son, ses voix de réflexion se chauffent au cockpit (au plus une fois toutes les 5 s)
// (17:59, Ahmed : « quand je reprends la parole, juste après que j'ai marqué une pause ») une reprise : au plus une par seconde
let prechauffeA = 0, repriseA = 0;
function prechaufferReflexion(reprise = false) {
  if (typeof voixEpissee !== 'function' || !voixEpissee()) return;
  const t = Date.now();
  if (reprise ? t - repriseA < 1000 : t - prechauffeA < 5000) return;
  if (reprise) repriseA = t; else prechauffeA = t;
  fetch('/api/jarvis/prechauffer', { method: 'POST', headers: { 'X-Jeton': jeton() } }).catch(() => {});
}

// (05/11, Ahmed : « un petit compteur de jetons, converti en CHF, sous l'orbe ; à afficher ou pas dans les réglages rapides ») aujourd'hui, relu toutes les 30 s
(() => {
  const CLE_C = 'hakim-compteur-jetons', c = document.getElementById('compteurActif'), z = document.getElementById('compteurJetons');
  if (!c || !z) return;
  let actif = true; try { actif = localStorage.getItem(CLE_C) !== 'non'; } catch (_) {}
  const lire = async () => {
    z.hidden = !actif;
    if (!actif || document.hidden) return;
    try {
      const d = await (await fetch('/api/conso', { headers: { 'X-Jeton': jeton() }, cache: 'no-store' })).json();
      const t = d.chf_par_usd || 0.8, n = d.lignes.reduce((a, x) => a + x.jetons, 0), tout = d.lignes.reduce((a, x) => a + x.usd, 0), api = d.lignes.filter(x => x.source === 'api').reduce((a, x) => a + x.usd, 0);
      const fr = (v) => v.toLocaleString('fr-CH', { maximumFractionDigits: v < 10 ? 2 : 0 });
      z.textContent = `${n >= 1e6 ? `${fr(n / 1e6)} M` : `${Math.round(n / 1000)} k`} · ${fr(tout * t)} CHF · API ${fr(api * t)}`;
    } catch (_) {}
  };
  c.checked = actif;
  c.addEventListener('change', () => { actif = c.checked; try { localStorage.setItem(CLE_C, actif ? 'oui' : 'non'); } catch (_) {} lire(); });
  lire(); setInterval(lire, 30000);
})();
