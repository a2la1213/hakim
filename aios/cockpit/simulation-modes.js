#!/usr/bin/env node
'use strict';
/* (09/11, Ahmed : « essayer en simulation toutes les variations de paramètres des trois modes et trouver les réglages optimaux ;
   tous du tac au tac : Super Hakim complet, Hakim équilibré, Mini Hakim le strict minimum ») simulation SANS aucun appel à Claude.

   Elle rejoue la vraie parole de papa (ses tours, à leurs instants, dans fil-stimuli-long.jsonl) dans un modèle à événements de la
   chaîne de sa parole, tel que le code la fait AVEC les interrupteurs du moment (corps-reglages.json), et des délais tirés des
   journaux réels (pistes.jsonl, voix-diagnostic.jsonl, voix-dite.jsonl, conversation.json, jetons.jsonl). Lecture seule : rien n'est
   écrit dans ~/AIOS/jarvis.

   Ce que chaque réglage fait vraiment, lu dans le code (server.js, public/parler.js, public/conversation.js) :
   - chunk_papa_ms : le blanc qui coupe un morceau de ta parole (conversation.js, pauseMs). Ton tour se ferme à 1 s de silence
     (finDeTourConversation : max(1000, patience)) : à 1000 et plus, aucun morceau n'est coupé pendant ta parole, tout ton tour est
     transcrit à la fin (texteDuTour) ; en dessous, les morceaux sont transcrits pendant que tu parles et seule la queue reste à la fin.
   - choix_ms (vitesse « éclair ») : l'attente de ses lecteurs ; sous 600 ms, pas de lecteur (direct). Le premier paquet d'une épissure
     est toujours direct (premiere_directe), sa réponse écrite aussi (reponse_directe).
   - plafond_mots × relais_pct / 100 : le seuil du relais (relais_ribosomes ≥ 2) ; plafond_mots, plafond_paquets, plafond_silence_s
     ne ferment plus rien quand parole_libre est allumé (ribosomeAuPlafond).
   - stringence : la consigne de ses lecteurs ; sans lecture aboutie, sans effet.
   - lire_apres_silence_ms : sans effet quand te_couper est allumé (direRibosome) ; sauter_suite_ms : sans effet quand coupe_net est
     allumé (surInterruption) ou sauter_suite éteint ; sauter_passe_s : agit aussi en parole liée depuis le 10/11 (direRibosome, sauterAuDernier).

   Usage : node simulation-modes.js [--reps 12] [--json] */
const fs = require('fs'), os = require('os'), path = require('path');
const J = process.env.JARVIS || path.join(os.homedir(), 'AIOS', 'jarvis');
const args = process.argv.slice(2), opt = (k, d) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : d; };
const REPS = Number(opt('--reps', 12)), JSON_OUT = args.includes('--json');

// ---------- lecture des journaux ----------
const lignes = (f) => { try { return fs.readFileSync(path.join(J, f), 'utf8').split('\n').filter(Boolean).map((l) => { try { return JSON.parse(l); } catch (_) { return null; } }).filter(Boolean); } catch (_) { return []; } };
const lire = (f, d) => { try { return JSON.parse(fs.readFileSync(path.join(J, f), 'utf8')); } catch (_) { return d; } };
const med = (v) => { const s = v.filter(Number.isFinite).sort((a, b) => a - b); return s.length ? s[Math.floor(s.length / 2)] : NaN; };
const pct = (v, p) => { const s = v.filter(Number.isFinite).sort((a, b) => a - b); return s.length ? s[Math.min(s.length - 1, Math.floor(s.length * p))] : NaN; };
const mots = (t) => String(t || '').split(/\s+/).filter((w) => /[\p{L}\p{N}]/u.test(w)).length;

function donnees() {
  const corps = lire('corps-reglages.json', {}), fil = lignes('fil-stimuli-long.jsonl'), diag = lignes('voix-diagnostic.jsonl');
  // la parole de papa : ses segments (un par battement b, mots placés dans le segment), les doublons de transcription fusionnés
  const seg = new Map();
  for (const d of fil) if (d.s === 'papa') { const s = seg.get(d.b) || { a: Infinity, b: 0, n: 0 }; s.a = Math.min(s.a, d.t); s.b = Math.max(s.b, d.t); s.n++; seg.set(d.b, s); }
  const S = [...seg.values()].map((s) => ({ a: s.a, b: s.b + 250, n: s.n })).sort((x, y) => x.a - y.a), fus = [];
  for (const s of S) { const p = fus[fus.length - 1]; if (p && s.a <= p.b) { p.b = Math.max(p.b, s.b); p.n = Math.max(p.n, s.n); } else fus.push({ ...s }); }
  // son débit (mots par seconde) : sur ses segments d'au moins 5 mots (les plus courts sont souvent la musique ou la pièce)
  const debit = med(fus.filter((s) => s.n >= 5 && s.b - s.a > 800).map((s) => s.n / ((s.b - s.a) / 1000))) || 2.6;
  // ses tours : SES messages oraux de la soirée (conversation.json), ce qui est vraiment arrivé à Hakim ; leur fin de parole se lit
  // dans tour_temps quand il y en a un (envoi = fin + attente de fin de tour + transcription), sinon : envoi − 1 s − la transcription
  // médiane ; leur durée : ses mots à son débit
  const tt = diag.filter((e) => e.e === 'tour_temps');
  const conv0 = lire('conversation.json', {}).messages || [], de = fus.length ? fus[0].a : 0, a0 = fus.length ? fus[fus.length - 1].b + 60000 : 0;
  const oraux = conv0.filter((m) => m.qui === 'u' && m.oral && Number(m.ts) >= de && Number(m.ts) <= a0);
  const transMed = med(tt.map((e) => e.transcription_ms)) || 6000, tours = [], pairs = [];
  for (const m of oraux) {
    const n = mots(String(m.texte).replace(/\(dit pendant ta parole\)/g, '')); if (!n) continue;
    const e = tt.find((x) => Math.abs((x.t - x.total_ms + x.attente_fin_tour_ms + x.transcription_ms) - m.ts) < 3000);
    const fin = e ? e.t - e.total_ms : m.ts - 1000 - transMed, duree = n / debit * 1000;
    tours.push({ debut: fin - duree, fin, mots: n, pendant: /dit pendant ta parole/.test(m.texte), mesure: !!e });
    if (e && e.transcription_ms > 0) pairs.push([duree / 1000, e.transcription_ms]);
  }
  tours.sort((x, y) => x.debut - y.debut);
  for (let i = 0; i < tours.length; i++) tours[i].suivant = i + 1 < tours.length ? Math.max(tours[i].fin, tours[i + 1].debut) : tours[i].fin + 60000;
  // ses voix vivantes (Haiku) quand elles ont répondu : délai, part des « dire : oui », longueur de ce qu'elles diraient
  const pistes = lignes('pistes.jsonl'), vivOk = pistes.filter((d) => d.morceau != null && !d.erreur && Number.isFinite(d.ms));
  const dire = vivOk.map((d) => String(d.dire || '')), oui = dire.filter((x) => /^oui/i.test(x));
  const riboPapa = pistes.filter((d) => d.ribosome != null && d.vitesse_ms != null && !d.source);
  // la transcription de fin de tour selon la longueur de ton tour (Theil-Sen : robuste aux transcriptions bloquées de 25 à 80 s)
  let a = 1500, b = 500, ajuste = false;
  if (pairs.length >= 8) {
    const pentes = [];
    for (let i = 0; i < pairs.length; i++) for (let k = i + 1; k < pairs.length; k++) if (Math.abs(pairs[k][0] - pairs[i][0]) > 0.5) pentes.push((pairs[k][1] - pairs[i][1]) / (pairs[k][0] - pairs[i][0]));
    b = Math.max(100, med(pentes)); a = Math.max(800, med(pairs.map((p) => p[1] - b * p[0]))); ajuste = true;
  }
  // sa réponse écrite : longueur dite par cerveau (conversation.json), vitesse relative des cerveaux (jetons.jsonl)
  const conv = (lire('conversation.json', {}).messages || []).filter((m) => m.qui === 'j');
  const ditMots = { haiku: [], sonnet: [], opus: [] };
  for (const m of conv) if (ditMots[m.modele] && Number(m.ditMots) > 0) ditMots[m.modele].push(Number(m.ditMots));
  const jet = { haiku: [], sonnet: [], opus: [] };
  for (const d of lignes('jetons.jsonl')) if (jet[d.modele] && d.ms && !d.autonome && d.categories && d.categories.message) jet[d.modele].push(d.ms);
  const vitesse = { haiku: med(jet.haiku) / med(jet.sonnet), sonnet: 1, opus: med(jet.opus) / med(jet.sonnet) };
  // sa voix : mots par seconde (voix-dite.jsonl) ; texte → son (tour_temps, voix_ms)
  const vd = lignes('voix-dite.jsonl').filter((d) => d.duree_ms > 500).slice(-3000).map((d) => mots(d.texte) / (d.duree_ms / 1000)).filter((x) => x > 0.5 && x < 8);
  return {
    corps, tours, pairs, transcription: { a, b, ajuste }, debit, fus,
    vivant: vivOk.map((d) => d.ms), vivantN: vivOk.length, pDire: dire.length ? oui.length / dire.length : 0.4,
    motsPensee: oui.map((x) => mots((/«([^»]*)»/.exec(x) || [])[1] || '')).filter((n) => n > 0),
    ribo: { n: riboPapa.length, panne: riboPapa.filter((d) => d.choisi === 'panne').length, direct: riboPapa.filter((d) => d.choisi === 'direct').length,
      lus: riboPapa.filter((d) => d.choisi !== 'panne' && d.choisi !== 'direct').length, vitesses: [...new Set(riboPapa.map((d) => d.vitesse_ms))] },
    azure: diag.filter((e) => e.e === 'transcription_azure').map((e) => e.ms),
    premierMot: tt.map((e) => e.premier_mot_ms).filter((x) => x > 0), voixMs: tt.map((e) => e.voix_ms).filter((x) => x > 0),
    tt, ditMots, vitesse, motsSeconde: med(vd) || 3.7,
    evts: Object.fromEntries(['coupe_net', 'te_coupe', 'coupure_au_chunk', 'suite_sautee', 'passe_saute', 'ribosome_attente', 'fond_ignore'].map((k) => [k, diag.filter((e) => e.e === k).length])),
    diagDe: diag.length ? diag[0].t : 0, diagA: diag.length ? diag[diag.length - 1].t : 0,
    hakimVoix: lignes('voix-dite.jsonl').filter((d) => fus.length && d.t_ms >= fus[0].a - 1000 && d.t_ms <= fus[fus.length - 1].b + 30000),
  };
}

// ---------- hasard reproductible (mêmes tirages pour chaque réglage : on compare des réglages, pas des chances) ----------
function rng(seed) { let a = seed >>> 0; return () => { a = (a + 0x6D2B79F5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
const tirer = (r, v) => v[Math.floor(r() * v.length)];
// ses lecteurs : la part des paquets lus à x ms, mesurée le 04/11 sur 681 paquets (commentaire de vitesseMaxMesuree, server.js) ;
// ce soir, plus rien à re-mesurer : à 600 ms, aucune lecture n'aboutit
const LECTEURS_CDF = [[600, 0], [1000, 0.16], [1200, 0.42], [1600, 0.73], [2000, 0.87], [3000, 0.93]];
function delaiLecteur(r) {
  const u = r(); if (u > 0.93) return Infinity;
  for (let i = 1; i < LECTEURS_CDF.length; i++) { const [x0, p0] = LECTEURS_CDF[i - 1], [x1, p1] = LECTEURS_CDF[i]; if (u <= p1) return Math.max(601, x0 + (x1 - x0) * (u - p0) / (p1 - p0)); }   // jamais à 600 ms ou moins (mesuré)
  return 3000;
}
// HYPOTHÈSES (plausibles, pas mesurées ce soir) : la part de « rien » et des mots gardés par ses lecteurs selon la stringence
const RIEN = { 1: 0.05, 2: 0.2, 3: 0.4, 4: 0.6, 5: 0.8 }, GARDE = { 1: 1, 2: 0.8, 3: 0.6, 4: 0.45, 5: 0.3 };
// HYPOTHÈSE : les blancs de ta voix à l'intérieur d'un tour (ceux de moins de 1 s ne sont pas dans les journaux : tes mots y sont
// placés à intervalles réguliers) ; taux de blancs ≥ x ms par seconde de parole : 0,35 × e^(−(x−200)/300) (× 0,5 ou × 2 en sensibilité)
const blancsParSeconde = (x, k = 1) => k * 0.35 * Math.exp(-(Math.max(200, x) - 200) / 300);

// ---------- un tour de papa, avec un réglage et un mode ----------
const MODES = { 'Mini Hakim': 'haiku', 'Hakim': 'sonnet', 'Super Hakim': 'opus' };
function morceauxDe(modele, n) {   // ses voix vivantes par morceau de ta parole (morceauxPour) : un mot, une proposition, trois (pistes-reglage)
  return modele === 'haiku' ? Math.max(1, Math.round(n * 0.6)) : modele === 'sonnet' ? Math.max(1, Math.ceil(n / 5)) : Math.max(1, Math.ceil(n / 14));
}
function simulerTour(D, tour, mode, g, seed, kBlancs) {
  const modele = MODES[mode], c = D.corps;
  const R = { pause: rng(seed * 7 + 1), viv: rng(seed * 7 + 2), lec: rng(seed * 7 + 3), voix: rng(seed * 7 + 4), rep: rng(seed * 7 + 5), dire: rng(seed * 7 + 6) };
  const T0 = tour.debut, Tf = tour.fin, dur = (Tf - T0) / 1000, mps = Math.max(1, tour.mots / Math.max(0.3, dur));
  const transcrire = (s) => D.transcription.a + D.transcription.b * s;
  const out = { appels: 0, items: [] };
  // 1. tes morceaux : coupés pendant ta parole seulement sous 1 s (le tour se ferme avant)
  const coupes = [];
  if (g.chunk_papa_ms < 1000 && dur > 0.6) {
    const n = Math.round(blancsParSeconde(g.chunk_papa_ms, kBlancs) * dur * 1.0 + (R.pause() - 0.5));
    for (let i = 0; i < Math.max(0, n); i++) coupes.push(T0 + 300 + R.pause() * Math.max(0, Tf - T0 - 600));
    coupes.sort((a, b) => a - b);
  }
  // chaque morceau : transcrit (un à la fois) puis ses voix vivantes ; la queue à la fin du tour
  let libre = T0, dernier = T0, confirme = T0;
  const morceaux = [];
  for (const x of coupes) {
    const emis = x + g.chunk_papa_ms, debut = Math.max(emis, libre);
    if (debut > Tf + 1000) break;
    const pret = debut + tirer(R.pause, D.azure.length ? D.azure : [2500]);
    libre = pret; morceaux.push({ pret, mots: Math.max(1, Math.round((x - dernier) / 1000 * mps)), queue: false }); dernier = x; confirme = Math.max(confirme, x);
  }
  const finTour = Tf + 1000, queueS = Math.max(0.3, (Tf - (coupes.length ? confirme : T0)) / 1000);
  const transFin = Math.max(finTour, libre) + transcrire(queueS);
  morceaux.push({ pret: transFin, mots: Math.max(1, Math.round(queueS * mps)), queue: true });
  // 2. ses pensées (voix vivantes Haiku, 8 en même temps, 3 en Super Hakim)
  const places = modele === 'opus' ? 3 : 8, enCours = [];
  const pensees = [];
  for (const m of morceaux) {
    const k = morceauxDe(modele, m.mots);
    for (let i = 0; i < k; i++) {
      enCours.sort((a, b) => a - b);
      const debut = enCours.length >= places ? Math.max(m.pret, enCours.shift()) : m.pret;
      const fin = debut + tirer(R.viv, D.vivant); enCours.push(fin); out.appels++;
      if (R.dire() < D.pDire) pensees.push({ t: fin, mots: tirer(R.dire, D.motsPensee.length ? D.motsPensee : [8]), complet: m.queue });
    }
  }
  pensees.sort((a, b) => a.t - b.t);
  // 3. son ribosome : premier paquet direct, les suivants lus (choix_ms) puis dans le tunnel ; relais au seuil
  const seuil = g.relais_ribosomes >= 2 && g.relais_pct < 100 ? Math.ceil(g.plafond_mots * g.relais_pct / 100) : Infinity;
  let rib = { k: 0, motsDits: 0, relais: false }, ribLibre = 0, tunnel = [], tunnelT = 0;
  const sorties = [];
  const viderTunnel = (t) => {
    if (!tunnel.length) return;
    let garde = tunnel;
    if (tunnel.length > 2 && c.tunnel !== false) { out.appels++; const lu = delaiLecteur(R.lec); t += Math.min(Number.isFinite(lu) ? lu : 3000, 3000); garde = tunnel.slice(0, 2).concat([tunnel[tunnel.length - 1]]); out.sautesTunnel = (out.sautesTunnel || 0) + tunnel.length - garde.length; }
    for (const x of garde) sorties.push({ ...x, t });
    tunnel = [];
  };
  for (const p of pensees) {
    const debut = Math.max(p.t, ribLibre);
    const premier = rib.k === 0 && !rib.relais;
    let t = debut, motsGardes = p.mots, trie = false;
    if (!premier && g.choix_ms >= 600) {
      out.appels += c.tournesol ? 1 : 2;
      const lu = delaiLecteur(R.lec);
      if (lu <= g.choix_ms) { t = debut + lu; trie = true; if (R.lec() < RIEN[g.stringence]) motsGardes = 0; else motsGardes = Math.max(1, Math.round(p.mots * GARDE[g.stringence])); }
      else t = debut + g.choix_ms;
    }
    ribLibre = t; rib.k++;
    if (motsGardes > 0) {
      const x = { t, mots: motsGardes, complet: p.complet, trie };
      if (premier || c.tunnel === false) sorties.push(x);
      else { if (tunnel.length && t - tunnelT > 1500) viderTunnel(tunnelT + 1500); tunnel.push(x); tunnelT = t; }
      rib.motsDits += motsGardes;
    }
    if (rib.motsDits >= seuil) { viderTunnel(Math.max(t, tunnelT) + 1500); rib = { k: 0, motsDits: 0, relais: true }; out.appels++; out.relais = (out.relais || 0) + 1; }
  }
  viderTunnel(tunnelT + 1500);
  // 4. sa réponse écrite : dès ta phrase transcrite, son premier mot (mesuré, Hakim ; Mini et Super à la vitesse relative de leur cerveau)
  out.appels++;
  const pm = tirer(R.rep, D.premierMot) * (D.vitesse[modele] || 1);
  const motsRep = tirer(R.rep, D.ditMots[modele].length ? D.ditMots[modele] : [20]);
  sorties.push({ t: transFin + pm, mots: motsRep, complet: true, reponse: true, trie: false });
  sorties.sort((a, b) => a.t - b.t);
  // 5. sa voix : une à la fois (parole liée : la suivante se calcule pendant que l'autre parle) ; ta voix sur la sienne le coupe net
  let finVoix = 0, coupeNet = false;
  const r = { coupures: 0, sautes: out.sautesTunnel || 0, premier: null, motsDits: 0, motsComplets: 0, motsTries: 0, horsDelai: 0 };
  for (const s of sorties) {
    let debut = Math.max(s.t + tirer(R.voix, D.voixMs), finVoix);
    if (coupeNet && debut < Tf) debut = Tf + 300;                  // coupé net : il se tait tant que tu parles
    if (debut >= tour.suivant) { r.horsDelai++; continue; }        // tu as repris la parole avant : plus à temps (et coupé net)
    const dureeMs = s.mots / D.motsSeconde * 1000;
    if (debut < Tf && debut >= T0) {                               // il parle pendant ton tour : il te coupe ; ta voix le coupe net
      r.coupures++; coupeNet = true; r.sautes += 1; finVoix = debut + 400; continue;
    }
    const fin = Math.min(debut + dureeMs, tour.suivant);
    if (r.premier == null && debut >= Tf) r.premier = debut - Tf;
    const dits = Math.round(s.mots * (fin - debut) / Math.max(1, dureeMs));
    if (fin < debut + dureeMs) r.sautes += 1;                      // coupé par ton tour suivant
    r.motsDits += dits; if (s.complet) r.motsComplets += dits; if (s.trie || s.reponse) r.motsTries += dits;
    finVoix = fin;
  }
  r.appels = out.appels; r.relais = out.relais || 0;
  return r;
}

// ---------- la grille ----------
function grille() {
  const l = [];
  for (const choix_ms of [0, 500, 600, 1200, 1600, 2000])
    for (const chunk_papa_ms of [400, 600, 800, 1100])
      for (const [plafond_mots, relais_pct, relais_ribosomes] of [[20, 20, 4], [50, 20, 6], [100, 20, 8], [50, 50, 6], [100, 50, 8], [50, 100, 1], [100, 100, 1]])
        for (const stringence of choix_ms >= 600 ? [1, 2, 3, 4] : [2]) l.push({ choix_ms, chunk_papa_ms, plafond_mots, relais_pct, relais_ribosomes, stringence });
  return l;
}
function evaluer(D, mode, g, kBlancs = 1) {
  const acc = { premier: [], repondu: 0, n: 0, coupures: 0, sautes: 0, appels: 0, mots: 0, complets: 0, tries: 0, relais: 0, horsDelai: 0 };
  D.tours.forEach((tour, i) => {
    for (let k = 0; k < REPS; k++) {
      const r = simulerTour(D, tour, mode, g, (i + 1) * 1000 + k, kBlancs);
      acc.n++; if (r.premier != null) { acc.repondu++; acc.premier.push(r.premier); }
      acc.coupures += r.coupures; acc.sautes += r.sautes; acc.appels += r.appels; acc.mots += r.motsDits; acc.complets += r.motsComplets; acc.tries += r.motsTries; acc.relais += r.relais; acc.horsDelai += r.horsDelai;
    }
  });
  return { premier_s: med(acc.premier) / 1000, premier_p90_s: pct(acc.premier, 0.9) / 1000, repondu: acc.repondu / acc.n,
    coupures: acc.coupures / acc.n, sautes: acc.sautes / acc.n, appels: acc.appels / acc.n, mots: acc.mots / acc.n,
    justesse: acc.mots ? acc.complets / acc.mots : 0, tries: acc.mots ? acc.tries / acc.mots : 0, relais: acc.relais / acc.n };
}
// les critères de papa en un score (plus petit = mieux) ; les poids sont un choix, dits dans le rapport
const POIDS = {
  'Mini Hakim': { premier: 1, coupures: 8, sautes: 1, appels: 0.15, justesse: 2, mots: 0.03 },    // le strict minimum : peu de mots, peu d'appels
  'Hakim': { premier: 1, coupures: 6, sautes: 1, appels: 0.08, justesse: 4, mots: 0 },             // équilibré
  'Super Hakim': { premier: 1, coupures: 5, sautes: 1.5, appels: 0.03, justesse: 6, mots: -0.01 }, // complet : plus de mots, rien de sauté
};
const score = (m, x) => { const p = POIDS[m]; return p.premier * x.premier_s + 4 * (1 - x.repondu) + p.coupures * x.coupures + p.sautes * x.sautes + p.appels * x.appels - p.justesse * x.justesse + p.mots * x.mots; };

function actuels(mode, profils) {
  const p = (profils || []).find((x) => x && x.nom === mode) || {}, r = p.ribosome || {}, c = p.corps || {};
  return { choix_ms: r.choix_ms, chunk_papa_ms: c.chunk_papa_ms, plafond_mots: r.plafond_mots, relais_pct: r.relais_pct, relais_ribosomes: r.relais_ribosomes, stringence: r.stringence };
}

function main() {
  const D = donnees();
  const f = (x, n = 1) => (Number.isFinite(x) ? x.toFixed(n) : '?');
  const log = (...a) => { if (!JSON_OUT) console.log(...a); };
  log(`Données (lecture seule, ${J}) :`);
  log(`  tours de papa rejoués : ${D.tours.length} (${new Date(D.tours[0].debut).toLocaleTimeString('fr-CH')}–${new Date(D.tours[D.tours.length - 1].fin).toLocaleTimeString('fr-CH')}), durée médiane ${f(med(D.tours.map((t) => (t.fin - t.debut) / 1000)))} s`);
  log(`  voix vivantes abouties : ${D.vivantN}, délai médian ${f(med(D.vivant) / 1000)} s (p90 ${f(pct(D.vivant, 0.9) / 1000)} s), « dire : oui » ${f(D.pDire * 100, 0)} %`);
  log(`  ribosome (paquets de papa) : ${D.ribo.n}, à ${D.ribo.vitesses.join('/')} ms : ${D.ribo.panne} sans lecture (panne), ${D.ribo.direct} directs, ${D.ribo.lus} lus`);
  log(`  tour_temps (${D.tt.length}) : total médian ${f(med(D.tt.map((e) => e.total_ms)) / 1000)} s = fin de tour ${f(med(D.tt.map((e) => e.attente_fin_tour_ms)) / 1000)} + transcription ${f(med(D.tt.map((e) => e.transcription_ms)) / 1000)} + premier mot ${f(med(D.premierMot) / 1000)} + voix ${f(med(D.voixMs) / 1000)} s ; sans son : ${D.tt.filter((e) => !e.son).length}`);
  log(`  transcription de fin de tour : ${D.transcription.ajuste ? `ajustée sur ${D.pairs.length} tours` : 'par défaut'} : ${f(D.transcription.a / 1000)} s + ${f(D.transcription.b / 1000, 2)} s par seconde de parole`);
  log(`  événements ${new Date(D.diagDe).toLocaleTimeString('fr-CH')}–${new Date(D.diagA).toLocaleTimeString('fr-CH')} : ${Object.entries(D.evts).map(([k, v]) => `${k} ${v}`).join(', ')}`);
  // ce soir, en vrai : sa voix qui démarre pendant un tour de papa
  let reelles = 0;
  const parole = D.fus.filter((s) => s.n >= 4);
  for (const v of D.hakimVoix) if (parole.some((t) => v.t_ms > t.a + 200 && v.t_ms < t.b - 200)) reelles++;
  log(`  ce soir, sa voix partie pendant ta parole (tes segments de 4 mots et plus) : ${reelles} fois sur ${D.hakimVoix.length} morceaux dits ; ton débit ${f(D.debit)} mots/s ; tours datés par tour_temps : ${D.tours.filter((t) => t.mesure).length}, dits pendant sa parole : ${D.tours.filter((t) => t.pendant).length}`);
  log(`  interrupteurs : te_couper ${D.corps.te_couper}, coupe_net ${D.corps.coupe_net}, parole_liee ${D.corps.parole_liee}, parole_libre ${D.corps.parole_libre}, sauter_suite ${D.corps.sauter_suite}, tunnel ${D.corps.tunnel}, reponse_directe ${D.corps.reponse_directe}`);

  const profils = lire('reglages-profils.json', []), G = grille(), res = {};
  // contrôle : ce soir, le forfait épuisé, ses voix vivantes ne répondaient plus (pistes.jsonl) ; sans elles, la simulation doit
  // retrouver le temps mesuré (tour_temps)
  const sansVoix = { ...D, pDire: 0 }, ctl = evaluer(sansVoix, 'Hakim', actuels('Hakim', profils));
  log(`  contrôle (Hakim, réglages du moment, sans voix vivantes comme ce soir) : 1er mot simulé ${f(ctl.premier_s)} s ; mesuré ${f(med(D.tt.map((e) => e.total_ms)) / 1000)} s`);
  res.controle = { simule_s: ctl.premier_s, mesure_s: med(D.tt.map((e) => e.total_ms)) / 1000 };
  for (const mode of Object.keys(MODES)) {
    const a = actuels(mode, profils), base = evaluer(D, mode, a);
    let best = null;
    for (const g of G) { const x = evaluer(D, mode, g); const s = score(mode, x); if (!best || s < best.s) best = { g, x, s }; }
    // sensibilité : le meilleur reste-t-il le meilleur si tes blancs sont deux fois plus rares ou plus fréquents ?
    const sens = [0.5, 2].map((k) => { let b = null; for (const g of G.filter((y) => y.choix_ms === best.g.choix_ms && y.stringence === best.g.stringence && y.plafond_mots === best.g.plafond_mots && y.relais_pct === best.g.relais_pct)) { const x = evaluer(D, mode, g, k); const s = score(mode, x); if (!b || s < b.s) b = { g, s }; } return { k, chunk: b.g.chunk_papa_ms }; });
    res[mode] = { actuel: { g: a, x: base, s: score(mode, base) }, optimal: best, sensibilite: sens };
    log(`\n${mode} (${MODES[mode]}) :`);
    const ligne = (n, g, x, s) => log(`  ${n.padEnd(8)} choix ${String(g.choix_ms).padStart(4)} · chunk ${String(g.chunk_papa_ms).padStart(4)} · relais ${g.relais_ribosomes}×${g.relais_pct}% de ${g.plafond_mots} mots · stringence ${g.stringence} → 1er mot ${f(x.premier_s)} s (p90 ${f(x.premier_p90_s)}), répondu à temps ${f(x.repondu * 100, 0)} %, coupe papa ${f(x.coupures, 2)}/tour, sautés ${f(x.sautes, 2)}/tour, appels ${f(x.appels, 1)}/tour, mots ${f(x.mots, 0)}, justesse ${f(x.justesse * 100, 0)} %, triés ${f(x.tries * 100, 0)} % ; score ${f(s, 2)}`);
    ligne('actuel', a, base, score(mode, base)); ligne('optimal', best.g, best.x, best.s);
    // le compromis de ta parole : le meilleur réglage à chaque chunk_papa_ms (le temps gagné contre les fois où il te coupe)
    res[mode].parChunk = {};
    for (const ch of [400, 600, 800, 1100]) {
      let b = null; for (const g of G.filter((y) => y.chunk_papa_ms === ch)) { const x = evaluer(D, mode, g); const s = score(mode, x); if (!b || s < b.s) b = { g, x, s }; }
      res[mode].parChunk[ch] = b; ligne(`chunk${ch}`, b.g, b.x, b.s);
    }
    log(`  sensibilité aux blancs de ta voix : chunk optimal ${sens.map((y) => `${y.chunk} (blancs ×${y.k})`).join(', ')}`);
  }
  if (JSON_OUT) console.log(JSON.stringify(res, null, 1));
  return res;
}
if (require.main === module) main();
module.exports = { donnees, simulerTour, evaluer, grille, score, delaiLecteur, blancsParSeconde };
