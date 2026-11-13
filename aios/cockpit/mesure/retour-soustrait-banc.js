#!/usr/bin/env node
/* (13/11) LE BANC de la soustraction du retour (retour-spectre.js : soustraire), papa par-dessus le live : le même live simulé que
   mesure/retour-spectre-banc.js (voix de say, haut-parleur calé sur le vrai du 11/11, la pièce, le gain automatique du micro, les morceaux
   découpés comme la page, le retard appris au fil), et le son de l'intérieur en blocs de 8 s (capté 30 ms après le mélange).
   Le masque de chaque morceau est appliqué AUSSI, à part, à la voix de papa seule et au retour seul (tels que le micro les a reçus) :
   - le live retiré : l'énergie du retour avant / après (dB), sur tout le morceau et dans les blancs de papa ;
   - papa gardé : l'énergie de sa voix avant / après (dB), là où il parle ; ses « bouts de mots » (200 ms de sa voix) gardés à − 3 dB près ;
   - ses PHRASES intactes : aucun morceau écarté entier (porte fermée partout) qui porte 100 ms de sa voix, aucun bout perdu ;
   - le rapport papa / live dans ce qui part à la transcription, avant et après.
   TÉMOIN : les mêmes morceaux avec le son de l'intérieur de 97 s plus loin : rien ne doit être soustrait (ni live retiré, ni papa abîmé).
   Usage : BANC_VOIX=<dossier des voix (mesure/retour-micro-voix.sh)> node mesure/retour-soustrait-banc.js
   Réglages : REGLAGES='{"alpha":2,"garde_ms":120,"sol":0}' NIVEAUX=0,-6,-12 GRAINES=1,2 DUREE=120 */
'use strict';
const B = require('./retour-micro-banc.js');
const S = require('../retour-spectre.js');
const SR = 16000;
const en = (x, a = 0, b = x.length) => { let s = 0; for (let i = Math.max(0, a); i < Math.min(x.length, b); i++) s += x[i] * x[i]; return s; };
const db = (a, b) => 10 * Math.log10((a + 1e-12) / (b + 1e-12));

function banc(cfg, o = {}) {
  const s = B.simuler({ ...cfg, composantes: true });
  const niveauPapa = 0.08 * Math.pow(10, (cfg.papaDb || 0) / 20);
  const papaActif = (i) => Math.sqrt(en(s.papa, i, i + 320) / 320) * s.kp > 0.25 * niveauPapa;
  const blocs = [], temoin = [];
  for (let a = 0; a < s.live.length; a += 8 * SR) { const pcm = s.live.slice(a, a + 8 * SR); blocs.push({ t0: a / 16 + 30, pcm }); temoin.push({ t0: a / 16 + 30 - 97000, pcm }); }
  let prior = null, papaFin = 0;
  const morceaux = [];
  for (const m of s.morceaux) {
    const t0 = m.a / 16, pcm = s.mic.slice(m.a, m.b);
    const pres = (bl) => bl.filter(b => b.t0 + 8000 > t0 - 2500 && b.t0 < t0 + pcm.length / 16 + 2500);
    const tA = process.hrtime.bigint();
    const r = S.soustraire({ pcm, t0 }, pres(blocs), prior, { ...o, masque: true });
    const ms = Number(process.hrtime.bigint() - tA) / 1e6;
    const rt = S.soustraire({ pcm, t0 }, pres(temoin), prior, { ...o, masque: true });
    const jg = r.jugement;
    if (jg && jg.retardMs !== null && jg.net && jg.ressemblance >= 0.6) prior = prior === null ? jg.retardMs : Math.round(0.7 * prior + 0.3 * jg.retardMs);
    const p = s.composantes.papa.slice(m.a, m.b), ret = s.composantes.retour.slice(m.a, m.b);
    // ce que la page enverrait : écarté entier (la porte fermée partout, sans voix proche, papa pas venu de parler) ; sinon le reste
    // la décision du cockpit (retourDecider) : écarté entier, le son entier (dans le doute), ou le reste
    const recent = papaFin && t0 - papaFin < 2000;
    const dec = (x) => S.decider(x, { papaRecent: !!recent });
    const ecarte = dec(r) === 'ecarte', ecarteT = dec(rt) === 'ecarte';
    if (r.applique && (r.voixMs >= S.VOIX_MS || (r.jugement && r.jugement.voixMs >= S.VOIX_MS))) papaFin = t0 + pcm.length / 16;
    const sortie = (x, sig) => (dec(x) === 'reste' ? S.appliquer(sig, x.G) : dec(x) === 'doux' ? S.appliquer(sig, x.Gdoux) : sig);
    const pS = ecarte ? new Float32Array(p.length) : sortie(r, p), rS = ecarte ? new Float32Array(ret.length) : sortie(r, ret);
    const pT = ecarteT ? new Float32Array(p.length) : sortie(rt, p), rT = ecarteT ? new Float32Array(ret.length) : sortie(rt, ret);
    // fenêtres de 20 ms : papa parle / se tait ; ses bouts de 200 ms
    let eP = 0, eP1 = 0, eR = 0, eR1 = 0, eRb = 0, eRb1 = 0, ePT = 0, eRT = 0, papaMs = 0, liveMs = 0;
    const bouts = []; let bout = null;
    const dl = Math.round(cfg.retardMs * 16);
    for (let i = 0; i + 320 <= p.length; i += 320) {
      const actif = papaActif(m.a + i);
      if (en(s.live, m.a + i - dl, m.a + i - dl + 320) / 320 > 1e-4) liveMs += 20;
      eR += en(ret, i, i + 320); eR1 += en(rS, i, i + 320); eRT += en(rT, i, i + 320);
      if (actif) {
        papaMs += 20; eP += en(p, i, i + 320); eP1 += en(pS, i, i + 320); ePT += en(pT, i, i + 320);
        if (!bout || bout.n >= 10) { bout = { e: 0, e1: 0, n: 0 }; bouts.push(bout); }
        bout.e += en(p, i, i + 320); bout.e1 += en(pS, i, i + 320); bout.n++;
      } else { eRb += en(ret, i, i + 320); eRb1 += en(rS, i, i + 320); bout = null; }
    }
    const vrai = papaMs === 0 ? 'retour' : papaMs >= 100 ? (liveMs >= 200 ? 'papaSur' : 'papaSeul') : 'frontiere';
    // (ECRIRE=dossier) les sons du morceau pour une oreille (mesure/retour-soustrait-mots.py) : le mélange (ce qui part aujourd'hui), le reste
    // (ce qui partirait), papa seul (ses vrais mots)
    if (o.ecrire && (vrai === 'papaSur' || vrai === 'retour')) {
      const fs = require('fs'), path = require('path'), id = `${cfg.papaDb}-${cfg.retardMs}-${cfg.agcDb}-${cfg.graine}-${m.a}`;
      const reste = ecarte ? new Float32Array(pcm.length) : dec(r) === 'reste' ? r.pcm : dec(r) === 'doux' ? r.pcmDoux : pcm;
      fs.writeFileSync(path.join(o.ecrire, `${id}-melange.wav`), B.wavDe(pcm, 0, pcm.length));
      fs.writeFileSync(path.join(o.ecrire, `${id}-reste.wav`), B.wavDe(reste, 0, reste.length));
      if (vrai === 'papaSur') fs.writeFileSync(path.join(o.ecrire, `${id}-papa.wav`), B.wavDe(p, 0, p.length));
      fs.appendFileSync(path.join(o.ecrire, 'manifeste.jsonl'), JSON.stringify({ id, vrai, papaDb: cfg.papaDb, applique: r.applique, ecarte, decision: dec(r), repli: ['reste', 'doux'].includes(dec(r)) && S.voixVue(r) }) + '\n');
    }
    morceaux.push({ a: m.a, b: m.b, vrai, applique: r.applique, appliqueT: rt.applique, ecarte, ecarteT, ms, eP, eP1, eR, eR1, eRb, eRb1, ePT, eRT,
      bouts: bouts.filter(x => x.n >= 5), papaMs });
  }
  const phrases = s.papaPhrases.map(ph => {
    const touche = morceaux.filter(x => x.b > ph.a && x.a < ph.b);
    let k = 0; for (const x of touche) if (x.ecarte) for (let i = Math.max(x.a, ph.a); i + 320 <= Math.min(x.b, ph.b); i += 320) if (papaActif(i)) k += 20;
    return { ecartee: k >= 100, boutsPerdus: touche.reduce((a, x) => a + x.bouts.filter(b => b.e1 < 0.5 * b.e).length, 0) };
  });
  return { morceaux, phrases };
}
const pc = (a, b) => (b ? `${Math.round(100 * a / b)} %` : '-');
function grille(o = {}, niveaux = [0, -6, -12], graines = [1], duree = 120) {
  const lignes = [], total = {};
  for (const papaDb of niveaux) {
    const t = { retour: 0, retourAppl: 0, retourEcarte: 0, retourT: 0, papaSur: 0, papaSurAppl: 0, eP: 0, eP1: 0, eR: 0, eR1: 0, eRb: 0, eRb1: 0, ePT: 0, eRT: 0,
      bouts: 0, boutsGardes: 0, phrases: 0, intactes: 0, ecartees: 0, ms: [], sirAvant: 0, sirApres: 0, eRsur: 0, eR1sur: 0 };
    for (const retardMs of [40, 150, 300]) for (const agcDb of [0, 3]) for (const graine of graines) {
      const r = banc({ graine: graine + retardMs + agcDb * 10 + papaDb * 100, retardMs, papaDb, agcDb, duree, hp: 'vrai' }, o);
      for (const m of r.morceaux) {
        t.ms.push(m.ms);
        if (m.vrai === 'retour') { t.retour++; if (m.applique) t.retourAppl++; if (m.ecarte) t.retourEcarte++; if (m.appliqueT) t.retourT++; }
        if (m.vrai === 'papaSur') {
          t.papaSur++; if (m.applique) t.papaSurAppl++;
          t.eP += m.eP; t.eP1 += m.eP1; t.eRsur += m.eR; t.eR1sur += m.eR1; t.ePT += m.ePT;
          for (const b of m.bouts) { t.bouts++; if (b.e1 >= 0.5 * b.e) t.boutsGardes++; }
        }
        if (m.vrai !== 'papaSeul') { t.eR += m.eR; t.eR1 += m.eR1; t.eRb += m.eRb; t.eRb1 += m.eRb1; t.eRT += m.eRT; }
      }
      for (const p of r.phrases) { t.phrases++; if (!p.ecartee && !p.boutsPerdus) t.intactes++; if (p.ecartee) t.ecartees++; }
    }
    total[papaDb] = t;
    const ms = t.ms.slice().sort((a, b) => a - b);
    lignes.push(`papa ${papaDb >= 0 ? '+' : ''}${papaDb} dB | live retiré ${db(t.eR, t.eR1).toFixed(1)} dB (blancs de papa ${db(t.eRb, t.eRb1).toFixed(1)} dB ; témoin ${db(t.eR, t.eRT).toFixed(1)} dB)`
      + ` · pur retour soustrait ${pc(t.retourAppl, t.retour)}, écarté entier ${pc(t.retourEcarte, t.retour)} (témoin soustrait ${pc(t.retourT, t.retour)})`
      + ` | papa sur le live : ${t.papaSur} morceaux, soustraits ${pc(t.papaSurAppl, t.papaSur)} ; sa voix ${(-db(t.eP, t.eP1)).toFixed(1)} dB (témoin ${(-db(t.eP, t.ePT)).toFixed(1)}),`
      + ` papa/live ${db(t.eP, t.eRsur).toFixed(1)} → ${db(t.eP1, t.eR1sur).toFixed(1)} dB ; bouts de 200 ms gardés ${pc(t.boutsGardes, t.bouts)} (${t.bouts})`
      + ` | phrases ${t.phrases}, intactes ${pc(t.intactes, t.phrases)}, écartées ${t.ecartees} | ${ms[ms.length >> 1].toFixed(0)} ms (p95 ${ms[Math.floor(ms.length * 0.95)].toFixed(0)})`);
  }
  return { total, lignes };
}
if (require.main === module) {
  const o = { ...(process.env.REGLAGES ? JSON.parse(process.env.REGLAGES) : {}), ...(process.env.ECRIRE ? { ecrire: process.env.ECRIRE } : {}) };
  const g = grille(o, process.env.NIVEAUX ? process.env.NIVEAUX.split(',').map(Number) : undefined, (process.env.GRAINES || '1').split(',').map(Number), Number(process.env.DUREE) || 120);
  console.log(`== la soustraction du retour ${JSON.stringify(o)}`);
  for (const l of g.lignes) console.log(l);
}
module.exports = { banc, grille };
