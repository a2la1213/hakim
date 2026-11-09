/* (09/11, Ahmed via Hakim, 18:53 à 19:36 : « tac tac » ; « un orchestrateur qui reprend l'ensemble et optimise toutes les vitesses, au lieu de
   réglages séparés » ; 21:20 : alléger le Mac, sa priorité numéro un) L'ORCHESTRATEUR : un seul chef pour tout ce qui se dispute le Mac et le
   forfait, au lieu que chaque fonction se serve elle-même.

   Mesuré le 09/11, de 18:30 à 19:30 (rapport : ~/AIOS/.wt/rapport-vitesse.md) :
   - 537 transcriptions dans l'heure, 17 s en médiane : la phrase de papa attendait derrière le son du téléphone, dans une file unique,
     même quand elle partait chez Azure (qui n'a pas besoin du GPU du Mac) ;
   - 1 276 appels de fond, dont 8 % ont abouti : 434 « weekly limit » (forfait épuisé) et 533 délais dépassés ;
   - le Mac brassait sa mémoire : swap 16,8 Go sur 17,4.

   Ce qu'il fait :
   1. file(nom) : la file d'une ressource à un seul calcul à la fois (la grande oreille) : papa d'abord, puis le téléphone, puis le reste ;
      un bloc du téléphone qui a trop attendu, ou de trop, est sauté (rendu null : l'appelant répond « rien »).
   2. la pression mémoire du Mac (kern.memorystatus_level, swap), lue toutes les 10 s : ok, tendu, critique.
   3. le forfait coupé : au premier « weekly limit » d'une voix, plus aucune voix sur le forfait jusqu'à sa remise à zéro (une sonde
      toutes les 10 min pour voir s'il est revenu ; une réponse réussie le rouvre).
   4. le tour de papa : de sa phrase jusqu'à ~25 s après, le travail de fond s'efface devant lui.
   5. admettre(etiquette) : le seul juge du travail de fond. Ses frères ne sont jamais refusés ici (ils ont leurs règles, et l'API).
   Il ne tue rien et ne lance rien : il dit oui ou non, et il le note (jarvis/orchestre.jsonl, une ligne par changement et par minute). */
'use strict';
const fs = require('fs');
const { execFile } = require('child_process');

const RANG = { papa: 0, telephone: 1, fond: 2 };

// une ressource qui ne fait qu'un calcul à la fois ; prendre(source) rend une fonction « libérer », ou null si le bloc a été sauté
function creerFile({ maintenant = Date.now, vieuxMs = 15000, garder = { telephone: 2 }, noter = null } = {}) {
  const attente = [];
  let occupe = false, seq = 0;
  const stats = { servis: 0, sautes: 0, attente_max_ms: 0 };
  const sauter = (a, raison) => { attente.splice(attente.indexOf(a), 1); stats.sautes++; if (noter) noter('saute', { source: a.source, raison, attente_ms: maintenant() - a.t }); a.resoudre(null); };
  function suivant() {
    const t = maintenant();
    for (const a of attente.slice()) if (a.rang > 0 && t - a.t > vieuxMs) sauter(a, 'trop_vieux');
    for (const [source, n] of Object.entries(garder)) {
      const l = attente.filter(a => a.source === source);
      for (const a of l.slice(0, Math.max(0, l.length - n))) sauter(a, 'de_trop');
    }
    if (occupe || !attente.length) return;
    attente.sort((a, b) => a.rang - b.rang || a.n - b.n);
    const a = attente.shift();
    occupe = true;
    stats.servis++; stats.attente_max_ms = Math.max(stats.attente_max_ms, t - a.t);
    let fini = false;
    a.resoudre(() => { if (fini) return; fini = true; occupe = false; suivant(); });
  }
  function prendre(source = 'papa') {
    return new Promise((resoudre) => {
      attente.push({ rang: RANG[source] === undefined ? RANG.fond : RANG[source], source, t: maintenant(), n: ++seq, resoudre });
      suivant();
    });
  }
  return { prendre, etat: () => ({ occupe, en_attente: attente.map(a => a.source), ...stats }) };
}

// « You've hit your weekly limit · resets 9pm (Europe/Zurich) » → l'instant de la remise (une minute de marge) ; inconnu : 30 min
const LIMITE_FORFAIT = /hit your (?:weekly |session |usage |5-hour |daily )?limit|usage limit reached|weekly limit/i;
function remiseDuForfait(texte, maintenant = Date.now()) {
  const m = /resets\s+(?:at\s+)?(?:[A-Za-zéû]{3,9}\.?\s+\d{1,2},?\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?/i.exec(String(texte || ''));
  if (!m) return maintenant + 30 * 60000;
  let h = Number(m[1]);
  if (m[3]) h = (h % 12) + (/pm/i.test(m[3]) ? 12 : 0);
  if (!(h >= 0 && h < 24)) return maintenant + 30 * 60000;
  const d = new Date(maintenant);
  d.setHours(h, Number(m[2] || 0), 0, 0);
  if (d.getTime() <= maintenant) d.setDate(d.getDate() + 1);
  return d.getTime() + 60000;
}

// ce que dit le Mac de sa mémoire : le pourcentage libre selon le noyau, et le swap utilisé
function lirePressionMac(cb) {
  execFile('/usr/sbin/sysctl', ['-n', 'kern.memorystatus_level', 'vm.swapusage'], { timeout: 3000 }, (e, so) => {
    if (e) return cb(null);
    const [niv, swap] = String(so || '').split('\n');
    const m = /total = ([\d.]+)M\s+used = ([\d.]+)M/.exec(swap || '');
    cb({ libre_pct: Number(niv), swap_total_mo: m ? Number(m[1]) : null, swap_utilise_mo: m ? Number(m[2]) : null });
  });
}
function niveauDe(p, seuils = {}) {
  const { critique = 20, tendu = 35, swapTenduMo = 12000 } = seuils;
  if (!p || !Number.isFinite(p.libre_pct)) return 'inconnu';
  if (p.libre_pct < critique) return 'critique';
  if (p.libre_pct < tendu || (Number.isFinite(p.swap_utilise_mo) && p.swap_utilise_mo > swapTenduMo)) return 'tendu';
  return 'ok';
}

// la classe d'un appel de fond, par son étiquette
function classeDe(etiquette) {
  const e = String(etiquette || '');
  if (/^frere_/.test(e)) return 'frere';
  if (/^piste_blanc/.test(e)) return 'fond';                     // ses « blancs » : garder ses voix chaudes
  if (/^(piste|ribosome)_entendu/.test(e)) return 'telephone';   // ce que joue le téléphone (ses pistes, son ribosome)
  return 'papa';                                                  // souffle, intégration, prétraitement, pistes, ribosome, choix…
}

function creer({ maintenant = Date.now, lirePression = lirePressionMac, journal = null, seuils = {}, tourPapaMs = 25000,
  sondeMs = 10 * 60000, forfaitLimite = () => false } = {}) {
  const etat = { pression: null, niveau: 'inconnu', coupe_jusqua: 0, coupe_raison: '', papa_jusqua: 0, sonde_a: 0 };
  const compte = { admis: 0, refuses: {} };
  const noter = (e, d = {}) => { if (journal) try { journal({ t: maintenant(), e, ...d }); } catch (_) {} };
  const files = {};

  function mesurer(cb) {
    lirePression((p) => {
      const avant = etat.niveau;
      etat.pression = p; etat.niveau = niveauDe(p, seuils);
      if (etat.niveau !== avant) noter('niveau', { de: avant, a: etat.niveau, ...(p || {}) });
      if (cb) cb(etat.niveau);
    });
  }
  const forfaitCoupe = (t = maintenant()) => etat.coupe_jusqua > t || !!forfaitLimite(t);
  const papaEnTour = (t = maintenant()) => etat.papa_jusqua > t;

  function admettre(etiquette) {
    const c = classeDe(etiquette), t = maintenant();
    const refuser = (raison) => { compte.refuses[raison] = (compte.refuses[raison] || 0) + 1; return { ok: false, raison, classe: c }; };
    if (c === 'frere') { compte.admis++; return { ok: true, classe: c }; }
    if (forfaitCoupe(t)) {
      if (t - etat.sonde_a < sondeMs) return refuser('forfait coupé');
      etat.sonde_a = t;                                            // une sonde : le forfait est peut-être revenu
      compte.admis++; return { ok: true, classe: c, sonde: true };
    }
    if (c === 'fond' && (etat.niveau === 'tendu' || etat.niveau === 'critique')) return refuser(`mémoire ${etat.niveau}`);
    if (c === 'fond' && papaEnTour(t)) return refuser('tour de papa');
    if (c === 'telephone' && etat.niveau === 'critique') return refuser('mémoire critique');
    if (c === 'telephone' && papaEnTour(t)) return refuser('tour de papa');
    compte.admis++;
    return { ok: true, classe: c };
  }

  // chaque appel fini (noterAppelLlm) : une limite du forfait le coupe ; une réponse réussie le rouvre
  function noterAppel(etiquette, erreur) {
    const t = maintenant();
    if (erreur && LIMITE_FORFAIT.test(String(erreur))) {
      const jusqua = remiseDuForfait(erreur, t);
      if (jusqua > etat.coupe_jusqua) { etat.coupe_jusqua = jusqua; etat.coupe_raison = String(erreur).slice(0, 80); etat.sonde_a = t;
        noter('forfait_coupe', { jusqua, etiquette: String(etiquette || '').slice(0, 40), erreur: etat.coupe_raison }); }
      return;
    }
    if (!erreur && etat.coupe_jusqua > t && classeDe(etiquette) !== 'frere') { etat.coupe_jusqua = 0; noter('forfait_rouvert', { etiquette: String(etiquette || '').slice(0, 40) }); }
  }

  function papaParle(t = maintenant()) { etat.papa_jusqua = Math.max(etat.papa_jusqua, t + tourPapaMs); }
  function file(nom, opts = {}) { if (!files[nom]) files[nom] = creerFile({ maintenant, ...opts, noter: (e, d) => noter(`${nom}_${e}`, d) }); return files[nom]; }
  function resume() {
    const fs_ = {}; for (const [k, f] of Object.entries(files)) fs_[k] = f.etat();
    return { niveau: etat.niveau, pression: etat.pression, forfait_coupe: forfaitCoupe(), coupe_jusqua: etat.coupe_jusqua || null,
      papa_en_tour: papaEnTour(), admis: compte.admis, refuses: { ...compte.refuses }, files: fs_ };
  }
  let minuteurs = [];
  function demarrer({ mesureMs = 10000, resumeMs = 60000 } = {}) {
    mesurer();
    minuteurs = [setInterval(() => mesurer(), mesureMs), setInterval(() => { noter('minute', resume()); compte.admis = 0; compte.refuses = {}; }, resumeMs)];
    for (const m of minuteurs) if (m.unref) m.unref();
    return api;
  }
  function arreter() { for (const m of minuteurs) clearInterval(m); minuteurs = []; }
  const api = { admettre, noterAppel, papaParle, file, mesurer, demarrer, arreter, resume, niveau: () => etat.niveau, forfaitCoupe, papaEnTour };
  return api;
}

// le journal : une ligne JSON par changement, et un résumé par minute (fichier 0600, borné à ~5 Mo : l'ancien est renommé)
function journalFichier(fichier, maxOctets = 5 << 20) {
  return (o) => {
    try { if (fs.statSync(fichier).size > maxOctets) fs.renameSync(fichier, `${fichier}.1`); } catch (_) {}
    fs.appendFileSync(fichier, JSON.stringify(o) + '\n', { mode: 0o600 });
  };
}

module.exports = { creer, creerFile, remiseDuForfait, niveauDe, classeDe, lirePressionMac, journalFichier, LIMITE_FORFAIT };
