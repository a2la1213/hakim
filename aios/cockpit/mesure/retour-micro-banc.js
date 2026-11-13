#!/usr/bin/env node
/* (11/11, Ahmed : « un bouton pour qu'il n'entende pas le retour du micro ») LE BANC du juge du retour (retour-micro.js), papa par-dessus le live.
   Des voix de synthèse (say : cinq voix pour le live, deux pour papa ; mesure/retour-micro-voix.sh) mêlées comme sur le téléphone :
   - le live joue sur le haut-parleur : son intérieur (ses trames de 100 ms, calculées comme EcranService), et son RETOUR au micro, retardé,
     sans graves (un petit haut-parleur), avec la résonance de la pièce ;
   - papa parle par moments, au niveau du retour − 6, 0, + 6 ou + 12 dB, souvent PAR-DESSUS le live ;
   - le micro : le retour + papa, son réglage automatique de gain (± 3 dB qui ondulent), un souffle ;
   - ses morceaux : découpés comme la page (une voix qui tient 120 ms ouvre le tour, 1 s de silence le ferme, chaque blanc de 400 ms en fait
     un morceau transcrit), 500 ms de pré-écoute ;
   - le chemin : appris sur les morceaux des 45 s d'avant (comme au cockpit) ; chaque morceau jugé avec l'intérieur qui joue.
   TÉMOIN : les mêmes morceaux jugés avec l'intérieur de 97 s plus loin (le vrai chemin) : un morceau écarté là l'est par hasard.
   Compte : les morceaux de pur retour écartés ; les PHRASES DE PAPA intactes (aucun morceau qui en porte 200 ms écarté) ; le temps du juge.
   Usage : node mesure/retour-micro-banc.js <dossier des voix> */
'use strict';
const fs = require('fs'), path = require('path');
const R = require('./retour-enveloppe.js');
const DIR = process.env.BANC_VOIX || process.argv[2];
if (!DIR || !fs.existsSync(DIR)) { console.error('le dossier des voix (mesure/retour-micro-voix.sh)'); process.exit(1); }
const SR = 16000;
function lireWav(f) {
  const b = fs.readFileSync(f); let o = 12, data = -1, n = 0;
  while (o + 8 <= b.length) { const id = b.toString('ascii', o, o + 4), t = b.readUInt32LE(o + 4); if (id === 'data') { data = o + 8; n = t; break; } o += 8 + t + (t & 1); }
  const x = new Float32Array(Math.floor(n / 2)); for (let i = 0; i < x.length; i++) x[i] = b.readInt16LE(data + 2 * i) / 32768; return x;
}
const fichiers = fs.readdirSync(DIR).filter(f => f.endsWith('.wav')).sort();
const LIVE = fichiers.filter(f => f.startsWith('live-')).map(f => lireWav(path.join(DIR, f)));
const PAPA = fichiers.filter(f => f.startsWith('papa')).map(f => lireWav(path.join(DIR, f)));
const rmsDe = (x, a = 0, b = x.length) => { let s = 0, n = 0; for (let i = a; i < b; i++) { if (Math.abs(x[i]) > 1e-4) { s += x[i] * x[i]; n++; } } return n ? Math.sqrt(s / n) : 0; };

function simuler({ graine = 1, retardMs = 120, papaDb = 0, agcDb = 3, duree = 300, hp = 'vrai' }) {
  let g = graine * 7919 + 13; const alea = () => { g = (g * 1103515245 + 12345) & 0x7fffffff; return g / 0x7fffffff; };
  const N = duree * SR, live = new Float32Array(N), papa = new Float32Array(N);
  const papaPhrases = [];
  for (let i = Math.round(SR * 0.5); i < N;) {            // le live : ses phrases à la suite, des blancs de 0,15 à 1,2 s
    const s = LIVE[Math.floor(alea() * LIVE.length)], k = 0.7 + 0.6 * alea();
    for (let j = 0; j < s.length && i + j < N; j++) live[i + j] += s[j] * k;
    i += s.length + Math.round(SR * (0.15 + 1.05 * alea()));
  }
  for (let i = Math.round(SR * (20 + 5 * alea())); i < N - SR * 6;) {   // papa : une phrase toutes les 9 à 15 s (après 20 s : son chemin appris)
    const s = PAPA[Math.floor(alea() * PAPA.length)];
    for (let j = 0; j < s.length && i + j < N; j++) papa[i + j] += s[j];
    papaPhrases.push({ a: i, b: i + s.length });
    i += s.length + Math.round(SR * (9 + 6 * alea()));
  }
  // le retour : le petit haut-parleur du téléphone rend peu de graves. CALÉ SUR LE VRAI (le 11/11, 08:09-09:19, le rapport graves / médiums
  // de la page, ses quartiles : papa 0,67 / 1,20 / 2,33, le live revenu 0,00 / 0,20 / 0,50) : « vrai », le micro coupe sous 250 Hz (ordre 2 ;
  // papa de say : 0,68 / 1,29 / 2,22) et le haut-parleur sous 450 Hz (ordre 3 ; le retour : 0,08 / 0,20 / 0,46) ; « pessimiste », le micro
  // sous 200 Hz (ordre 2) et le haut-parleur sous 400 Hz (ordre 2) : le retour à 0,22 / 0,50 / 1,13, 2,5 fois plus de graves que le vrai ;
  // retardé ; la pièce qui résonne (deux peignes) ; au niveau 0,08
  const ret = new Float32Array(N), d = Math.round(retardMs * SR / 1000);
  const passeHaut = (x, fc, ordre = 1) => { let y = x; for (let o = 0; o < ordre; o++) { const a = 1 / (1 + 2 * Math.PI * fc / SR), z = new Float32Array(y.length); let yp = 0, xp = 0; for (let i = 0; i < y.length; i++) { yp = a * (yp + y[i] - xp); xp = y[i]; z[i] = yp; } y = z; } return y; };
  const retarde = new Float32Array(N); for (let i = d; i < N; i++) retarde[i] = live[i - d];
  ret.set(hp === 'pessimiste' ? passeHaut(retarde, 400, 2) : passeHaut(retarde, 450, 3));
  const c1 = Math.round(0.0297 * SR), c2 = Math.round(0.0371 * SR), z1 = new Float32Array(N), z2 = new Float32Array(N);
  for (let i = 0; i < N; i++) { z1[i] = ret[i] + (i >= c1 ? 0.7 * z1[i - c1] : 0); z2[i] = ret[i] + (i >= c2 ? 0.65 * z2[i - c2] : 0); }
  for (let i = 0; i < N; i++) ret[i] = ret[i] + 0.12 * (z1[i] + z2[i]);
  const kr = 0.08 / Math.max(1e-6, rmsDe(ret)), kp = 0.08 * Math.pow(10, papaDb / 20) / Math.max(1e-6, rmsDe(papa));
  const mic = new Float32Array(N), phi = alea() * 6.28;
  for (let i = 0; i < N; i++) {
    const agc = Math.pow(10, agcDb * Math.sin(2 * Math.PI * i / SR / 6.3 + phi) / 20);
    mic[i] = (ret[i] * kr + papa[i] * kp) * agc + 0.001 * (alea() * 2 - 1);
  }
  mic.set(passeHaut(mic, hp === 'pessimiste' ? 200 : 250, 2));   // le micro du téléphone
  // (13/11) ses deux parts, chacune passée par le même micro (le banc de la soustraction mesure ce que le masque laisse de chacune)
  let composantes = null;
  if (arguments[0] && arguments[0].composantes) {
    const r2 = new Float32Array(N), p2 = new Float32Array(N);
    for (let i = 0; i < N; i++) { const agc = Math.pow(10, agcDb * Math.sin(2 * Math.PI * i / SR / 6.3 + phi) / 20); r2[i] = ret[i] * kr * agc; p2[i] = papa[i] * kp * agc; }
    composantes = { retour: passeHaut(r2, hp === 'pessimiste' ? 200 : 250, 2), papa: passeHaut(p2, hp === 'pessimiste' ? 200 : 250, 2) };
  }
  // son intérieur : ses trames de 100 ms (RMS, graves, médiums : les filtres d'EcranService), l'heure de leur MILIEU, captées 30 ms après le
  // mélange (± 5 ms)
  const tel = []; let bas = 0, moyen = 0;
  for (let f = 0; (f + 1) * 1600 <= N; f++) {
    let s = 0, sg = 0, sm = 0;
    for (let i = f * 1600; i < (f + 1) * 1600; i++) { const x = live[i]; bas += 0.0937 * (x - bas); moyen += 0.5441 * (x - moyen); s += x * x; sg += bas * bas; sm += (moyen - bas) ** 2; }
    tel.push({ t: f * 100 + 50 + 30 + (alea() - 0.5) * 10, v: Math.sqrt(s / 1600), g: Math.sqrt(sg / 1600), m: Math.sqrt(sm / 1600) });
  }
  // la page : fenêtres de 20 ms, une voix qui tient 120 ms ouvre le tour, 1 s de silence le ferme ; un morceau à chaque blanc de 400 ms
  const W = SR / 50, morceaux = []; let bruit = 0.01, etat = 'attente', tenue = 0, debut = 0, silence = 0, coupe = 0;
  for (let w = 0; (w + 1) * W <= N; w++) {
    let s = 0; for (let i = w * W; i < (w + 1) * W; i++) s += mic[i] * mic[i];
    const rms = Math.sqrt(s / W), seuil = Math.max(0.012, bruit * 3.2), fort = rms > seuil;
    if (etat === 'attente') {
      bruit = Math.max(0.002, bruit * 0.985 + Math.min(rms, seuil) * 0.015);
      tenue = fort ? tenue + 1 : 0;
      if (tenue >= 6) { etat = 'parole'; debut = Math.max(0, w - 25); coupe = debut; silence = 0; }
      continue;
    }
    silence = fort ? 0 : silence + 1;
    if (silence === 20 && w - coupe > 25) { morceaux.push({ a: coupe * W, b: (w + 1) * W, seuil }); coupe = w + 1; }
    if (silence >= 50) { if (w - coupe > 5) morceaux.push({ a: coupe * W, b: (w + 1) * W, seuil }); etat = 'attente'; tenue = 0; }
  }
  // comme la page (voisees) : un morceau sans 5 fenêtres de voix n'est jamais envoyé
  const voisees = (m) => { let n = 0; for (let i = m.a; i + W <= m.b; i += W) { let s = 0; for (let k = i; k < i + W; k++) s += mic[k] * mic[k]; if (Math.sqrt(s / W) > m.seuil) n++; } return n; };
  morceaux.splice(0, morceaux.length, ...morceaux.filter(m => voisees(m) >= 5));
  return { mic, live, papa, papaPhrases, tel, morceaux, kp, composantes };
}
// un morceau : son WAV (PCM 16 bits, comme la page), son enveloppe par retour-micro.js
function wavDe(x, a, b) {
  const n = b - a, buf = Buffer.alloc(44 + 2 * n);
  buf.write('RIFF', 0); buf.writeUInt32LE(36 + 2 * n, 4); buf.write('WAVE', 8); buf.write('fmt ', 12); buf.writeUInt32LE(16, 16);
  buf.writeUInt16LE(1, 20); buf.writeUInt16LE(1, 22); buf.writeUInt32LE(SR, 24); buf.writeUInt32LE(2 * SR, 28); buf.writeUInt16LE(2, 32); buf.writeUInt16LE(16, 34);
  buf.write('data', 36); buf.writeUInt32LE(2 * n, 40);
  for (let i = 0; i < n; i++) buf.writeInt16LE(Math.max(-32768, Math.min(32767, Math.round(x[a + i] * 32767))), 44 + 2 * i);
  return buf;
}
// un live simulé, morceau par morceau, comme au cockpit : le chemin réappris toutes les 2 s sur les morceaux des 45 s d'avant, chaque morceau
// jugé (et jugé encore avec l'intérieur de 97 s plus loin : le témoin). Rend un relevé par morceau et les phrases de papa.
function banc(cfg, opts = {}) {
  const s = simuler(cfg);
  const tel97 = s.tel.map(x => ({ ...x, t: x.t - 97000 }));
  const niveauPapa = 0.08 * Math.pow(10, (cfg.papaDb || 0) / 20);
  // papa parle dans cette fenêtre de 20 ms : sa voix au quart de son niveau habituel au moins
  const papaActif = (i) => rmsDe(s.papa, i, i + 320) * s.kp > 0.25 * niveauPapa;
  const ring = [], morceaux = [], ms = [];
  let chemin = null, appris = -1e9;
  for (const m of s.morceaux) {
    const t0 = m.a / SR * 1000, finMs = (m.b - m.a) / 16;
    const tA = process.hrtime.bigint();
    const trames = R.tramesDuMorceau(t0, R.enveloppeWav(wavDe(s.mic, m.a, m.b)));
    if (t0 - appris >= 2000) {
      const c = R.apprendreChemin(s.tel.filter(x => x.t >= t0 - 45000 && x.t < t0), ring.filter(x => x.t >= t0 - 46500));
      if (c) chemin = { ...c, ts: t0 };
      appris = t0;
    }
    const tel = s.tel.filter(x => x.t >= t0 - 2500 && x.t <= t0 + finMs + 2500);
    const v = R.jugerMorceau({ mic: trames, tel, chemin, maintenant: t0, o: opts });
    ms.push(Number(process.hrtime.bigint() - tA) / 1e6);
    const vt = R.jugerMorceau({ mic: trames, tel: tel97.filter(x => x.t >= t0 - 2500 && x.t <= t0 + finMs + 2500), chemin, maintenant: t0, o: opts });
    for (const x of trames) ring.push(x);
    while (ring.length && ring[0].t < t0 - 60000) ring.shift();
    let papaMs = 0, liveMs = 0;
    for (let i = m.a; i + 320 <= m.b; i += 320) { if (papaActif(i)) papaMs += 20; if (rmsDe(s.live, i - Math.round(cfg.retardMs * 16), i - Math.round(cfg.retardMs * 16) + 320) > 0.01) liveMs += 20; }
    // le vrai : « retour » (papa n'y dit RIEN), « papa » (100 ms de sa voix au moins : un « oui »), sinon une frontière (non comptée)
    const vrai = papaMs === 0 ? 'retour' : papaMs >= 100 ? (liveMs >= 200 ? 'papaSur' : 'papaSeul') : 'frontiere';
    morceaux.push({ a: m.a, b: m.b, vrai, papaMs, v, vt });
  }
  // ses phrases : abîmées si un morceau écarté porte 100 ms de sa voix ; « par-dessus le live » : le live jouait pendant la moitié de la phrase
  const phrases = s.papaPhrases.map(p => {
    let liveMs = 0, n = 0; for (let i = p.a; i + 320 <= p.b; i += 320) { n += 20; if (rmsDe(s.live, i, i + 320) > 0.01) liveMs += 20; }
    const abimee = morceaux.some(x => x.v.verdict === 'retour' && (() => { let k = 0; for (let i = Math.max(x.a, p.a); i + 320 <= Math.min(x.b, p.b); i += 320) if (papaActif(i)) k += 20; return k >= 100; })());
    return { sur: liveMs >= n * 0.5, abimee };
  });
  return { morceaux, phrases, ms };
}
const pc = (a, b) => (b ? `${Math.round(100 * a / b)} %` : '-');
function grille(opts = {}, niveaux = [-12, -6, 0, 6, 12], hp = 'vrai', graines = (process.env.GRAINES || '1,2').split(',').map(Number), duree = Number(process.env.DUREE) || 240) {
  const lignes = [], total = {};
  for (const papaDb of niveaux) {
    const t = { retour: 0, ecartes: 0, doute: 0, temoin: 0, papa: 0, papaEcartes: 0, phrases: 0, abimees: 0, sur: 0, surAbimees: 0, ms: [], raisons: {} };
    for (const retardMs of [40, 150, 300]) for (const agcDb of [0, 3]) for (const graine of graines) {
      const o = banc({ graine: graine + retardMs + agcDb * 10 + papaDb * 100, retardMs, papaDb, agcDb, duree, hp }, opts);
      for (const m of o.morceaux) {
        t.raisons[`${m.vrai}:${m.v.verdict}:${m.v.raison}`] = (t.raisons[`${m.vrai}:${m.v.verdict}:${m.v.raison}`] || 0) + 1;
        if (m.vrai === 'retour') { t.retour++; if (m.v.verdict === 'retour') t.ecartes++; if (m.v.verdict === 'doute') t.doute++; if (m.vt.verdict === 'retour') t.temoin++; }
        if (m.vrai === 'papaSur' || m.vrai === 'papaSeul') { t.papa++; if (m.v.verdict === 'retour') t.papaEcartes++; }
      }
      for (const p of o.phrases) { t.phrases++; if (p.abimee) t.abimees++; if (p.sur) { t.sur++; if (p.abimee) t.surAbimees++; } }
      t.ms.push(...o.ms);
    }
    total[papaDb] = t;
    const s = t.ms.slice().sort((a, b) => a - b);
    lignes.push(`papa ${papaDb >= 0 ? '+' : ''}${papaDb} dB : morceaux de pur retour ${t.retour}, écartés ${pc(t.ecartes, t.retour)} (en doute ${pc(t.doute, t.retour)}) · témoin écartés ${pc(t.temoin, t.retour)} | `
      + `phrases de papa ${t.phrases}, intactes ${pc(t.phrases - t.abimees, t.phrases)} (par-dessus le live : ${t.sur}, intactes ${pc(t.sur - t.surAbimees, t.sur)}) ; morceaux avec sa voix écartés ${t.papaEcartes}/${t.papa} | `
      + `juge ${s[s.length >> 1].toFixed(2)} ms (p95 ${s[Math.floor(s.length * 0.95)].toFixed(2)})`);
  }
  return { total, lignes };
}
if (require.main === module) {
  const hp = process.env.HP || 'vrai';
  const base = process.env.REGLAGES ? JSON.parse(process.env.REGLAGES) : {};
  // le juge entier, puis ses TÉMOINS : le même juge sans ses graves, sans ses excès (chaque garde de papa coupée à son tour)
  const cas = [['le juge entier', base], ['TÉMOIN : sans ses graves', { ...base, graves: false }], ['TÉMOIN : sans ses graves ni ses excès', { ...base, graves: false, exces_x: 1e9, exces_ms: 1e9, exces_total_ms: 1e9 }]];
  for (const [nom, opts] of cas) {
    if (process.env.SEUL && nom !== 'le juge entier') continue;
    const g = grille(opts, undefined, hp);
    console.log(`== ${nom} (haut-parleur ${hp})`);
    for (const l of g.lignes) console.log(l);
    if (process.env.DETAIL) for (const [db, t] of Object.entries(g.total)) console.log(db, JSON.stringify(Object.entries(t.raisons).sort((a, b) => b[1] - a[1])));
  }
}
module.exports = { simuler, banc, grille, lireWav, wavDe };
