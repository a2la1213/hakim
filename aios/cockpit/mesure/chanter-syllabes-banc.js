/* (11/11, ~03:00, Ahmed : « chaque syllabe sur le temps » ; « mesure l'écart syllabe par syllabe au banc » ; « l'écart de hauteur en cents »)
   LE BANC DU CHANT V2 : chaque syllabe de sa voix, entendue, contre le temps de la musique ; et sa hauteur contre la note du morceau.
   Tout passe par les VRAIS calculs, avec des erreurs CONNUES :
   - la musique et ses trames comme l'appli 1.96 (mesure/chanter-banc.js), la grille (Chanter.grille) ;
   - le chanteur du morceau chante une ligne sur les doubles croches du VRAI tempo ; Azure en lit les mots avec ±40 ms d'erreur (l'heure de
     chaque mot, pas de ses syllabes) ; la voix séparée tient la mélodie (avec un vibrato et ±15 cents d'erreur de mesure) ;
   - Chanter.planifierSyllabes place ses syllabes sur la grille et leur donne leurs notes ; chanter-voix.js rend la ligne chantée, à partir de
     la voix de say (macOS, Eddy, un blanc entre chaque mot comme les <break> d'Azure ; à défaut, la voix de synthèse) ;
   - le départ du son (Chanter.depart, par le micro ou sans) : l'essai du banc v1, mêmes cas (haut-parleur, enceinte, deux chemins).
   L'écart d'une syllabe entendue = l'écart du départ + (sa place sur la grille − le vrai temps le plus proche) + (son attaque dans le son rendu
   − sa place). Sa hauteur : mesurée dans le son rendu par une autre méthode (l'autocorrélation à 24 kHz), contre sa note (à l'octave de sa
   voix) ; et la note du morceau, à l'octave près (le « juste »). Ce que le banc ne sait pas : la vraie voix d'Azure, une vraie voix séparée,
   les vrais retards d'Android, l'oreille d'Ahmed. Lancer : nice node mesure/chanter-syllabes-banc.js */
'use strict';
const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFileSync } = require('child_process');
const Chanter = require('../public/chanter.js');
const V = require('../chanter-voix.js');
const S = require('./voix-synthetique.js');
const Banc = require('./chanter-banc.js');

let graine = 4242;
const alea = () => { graine = (graine * 1103515245 + 12345) & 0x7fffffff; return graine / 0x7fffffff; };
const gauss = () => { let u = 0; for (let i = 0; i < 6; i++) u += alea(); return (u - 3) / Math.sqrt(0.5); };
const hzDe = (m) => 440 * Math.pow(2, (m - 69) / 12);
const med = (l) => V.mediane(l);
// le détecteur d'attaques du banc, plus fin que celui par défaut (la force × 2 en 15 ms) : une syllabe qui suit une consonne voisée (« lu-mière »)
// monte moins ; à 0,5, 58 attaques sur 576 n'étaient pas retrouvées, à 0,3, 13 (son écart médian et son max ne bougent pas)
const SAUT = 0.3;
const pct = (l, p) => { const s = l.slice().sort((a, b) => a - b); return s[Math.min(s.length - 1, Math.floor(s.length * p))]; };

// les lignes : ses mots, la durée de chaque syllabe (en doubles croches) et la note du chanteur (midi)
const LIGNES = [
  { mots: ['Moujahid', 'moujahid', 'je', 'ne', 'plie', 'pas'], seizes: [2, 2, 2, 2, 2, 2, 2, 2, 2, 4], notes: [69, 69, 72, 69, 69, 72, 74, 72, 71, 69] },
  { mots: ['la', 'lumière', 'revient', 'toujours'], seizes: [1, 1, 2, 1, 1, 2, 4], notes: [64, 67, 69, 67, 64, 62, 64] },
  { mots: ['quand', 'ça', 'monte', 'on', 'reste', 'debout'], seizes: [1, 1, 2, 1, 2, 2, 4], notes: [57, 57, 60, 62, 64, 62, 60] },
];
// sa voix : say (comme Azure : un blanc entre chaque mot), sinon la voix de synthèse
function voixDe(mots) {
  try {
    const f = path.join(os.tmpdir(), `banc-chant-${process.pid}-${mots.length}.wav`);
    execFileSync('say', ['-v', 'Eddy (Français (France))', '-o', f, '--file-format=WAVE', '--data-format=LEI16@24000', mots.join(' [[slnc 260]] ')], { timeout: 20000 });
    const b = fs.readFileSync(f); fs.unlinkSync(f);
    return { wav: b, par: 'say' };
  } catch (_) {
    return { wav: S.voixSynthetique(mots.map(m => Chanter.syllabesMot(m).length)).wav, par: 'synthese' };
  }
}

function essaiLigne({ bpm, ligne, voix, depart }) {
  const duree = 70, debut = 1_000_000, captureMs = 25;
  const { x, beats } = Banc.musique(bpm, duree);
  const tr = Banc.tramesAppli(x, debut, captureMs, 8, true).filter(f => f.tb <= debut + 40000 + captureMs);
  const g = Chanter.grille(tr, { bpm: Math.round(bpm / 2) * 2 });
  if (!Chanter.grilleSure(g)) return null;
  const P = 60000 / bpm, vrai16 = (t) => { const k = Math.round((t - (debut + captureMs)) / (P / 4)); return debut + captureMs + k * P / 4; };
  // le chanteur : la ligne commence sur le temps le plus proche de 48 s ; ses syllabes sur les doubles croches du vrai tempo
  const b0 = beats.reduce((m, b) => (Math.abs(b - 48) < Math.abs(m - 48) ? b : m), beats[0]);
  const start = debut + captureMs + b0 * 1000, vraies = [];
  let acc = 0;
  for (const s of ligne.seizes) { vraies.push(start + acc * P / 4); acc += s; }
  // Azure : l'heure de chaque mot (le début de sa première syllabe), ±40 ms
  const parMot = ligne.mots.map(m => Chanter.syllabesMot(m).length);
  if (parMot.reduce((a, b) => a + b, 0) !== ligne.seizes.length) throw new Error(`syllabes ≠ rythme : ${ligne.mots.join(' ')}`);
  const motsT = []; let k = 0;
  for (const n of parMot) { motsT.push(vraies[k] + 40 * gauss()); k += n; }
  const t0 = motsT[0];
  // la ligne entendue la dernière fois, 32 temps plus tôt (sa mélodie) ; celle à venir, calée au demi-temps comme prevoir
  const source = t0 - 32 * P;
  const l = { t: Math.round(Chanter.tempsProche(g, t0, 2)), d: Math.round(acc * P / 4), texte: ligne.mots.join(' '), mots: ligne.mots.map((m, i) => [m, Math.round(motsT[i] - t0)]), source_tb: Math.round(source) };
  // la voix séparée du morceau sous cette ligne-là : ses notes, un vibrato de 5 Hz, ±15 cents de mesure, 40 ms
  const hz = [];
  for (let t = -200; t < acc * P / 4 + 400; t += 40) {
    let i = 0; while (i + 1 < vraies.length && vraies[i + 1] - start <= t) i++;
    const silence = t < 0 || t > acc * P / 4;
    hz.push(silence ? 0 : Math.round(hzDe(ligne.notes[i]) * Math.pow(2, (15 * gauss() + 20 * Math.sin(2 * Math.PI * 5 * t / 1000)) / 1200)));
  }
  const melodies = [{ tb0: Math.round(source + (vraies[0] - start) - 200 - (t0 - start)), pas: 40, hz, src: 'voix' }];
  const plan = Chanter.planifierSyllabes({ lignes: [l] }, g, melodies);
  if (!plan) return null;
  const m = plan[0];
  // le son
  const r0 = Date.now();
  const r = V.chanterLigne(voix.wav, m.mots, m.syllabes);
  const ms = Date.now() - r0;
  if (!r) return { echec: true };
  const p = V.lirePcm(r.wav);
  const att = V.attaquesDe(p.x, p.sr, { saut: SAUT }).map(i => i / p.sr * 1000 - r.zero_ms);
  const out = [];
  m.syllabes.forEach((s, i) => {
    const slot = m.a + s.t;
    const grilleE = slot - vrai16(slot), fidele = Math.abs(slot - vraies[i]) <= P / 8;
    const a = att.reduce((b, v) => (Math.abs(v - s.t) < Math.abs(b - s.t) ? v : b), Infinity), sonE = Math.abs(a - s.t) <= 60 ? a - s.t : null;
    const R = r.syllabes[i], u = Math.round(p.sr * (s.t + r.zero_ms) / 1000);
    const f = S.hauteurMesuree(p.x, p.sr, u, u + Math.round(p.sr * Math.min(0.2, Math.max(0.06, s.d / 1000 * 0.8))));
    const cents = f && R.cible_hz ? 1200 * Math.log2(f / R.cible_hz) : null;
    const pc = f ? ((1200 * Math.log2(f / hzDe(ligne.notes[i])) % 1200) + 1800) % 1200 - 600 : null;   // contre la note du morceau, à l'octave près
    out.push({ grilleE, fidele, sonE, cents, pc, total: sonE == null ? null : depart + grilleE + sonE });
  });
  return { syllabes: out, ms, dsp_ms: r.ms, voix: voix.par };
}

if (require.main === module) {
  const voix = LIGNES.map(l => voixDe(l.mots));
  const froid = Date.now();
  V.chanterLigne(voix[1].wav, LIGNES[1].mots, LIGNES[1].mots.flatMap((m, i) => Chanter.syllabesMot(m).map((_, j) => ({ m: i, t: (i * 3 + j) * 300, d: 300, hz: 220 }))));
  const froidMs = Date.now() - froid;
  V.chanterLigne(voix[0].wav, LIGNES[0].mots, LIGNES[0].mots.flatMap((m, i) => Chanter.syllabesMot(m).map((_, j) => ({ m: i, t: (i * 3 + j) * 300, d: 300, hz: 0 }))));   // (le moteur chauffé, comme au cockpit après le premier chant)
  const cas = [
    { nom: 'haut-parleur', Lm: 60, Lv: 75, captureMs: 25, entreeMs: 30 },
    { nom: 'enceinte Bluetooth', Lm: 220, Lv: 240, captureMs: 25, entreeMs: 30 },
  ];
  const lignes = [`voix : ${[...new Set(voix.map(v => v.par))].join(', ')}`];
  const tous = [], lat = [];
  for (const c of cas) for (const micro of [true, false]) {
    const l = [];
    for (const bpm of [72, 90, 100, 120, 140, 160]) for (let li = 0; li < LIGNES.length; li++) {
      graine = bpm * 13 + li * 7 + (micro ? 1 : 2);
      const d = Banc.essai({ ...c, bpm, micro, avance_s: 8, fines: true });
      if (d.ecart_ms == null) continue;
      const e = essaiLigne({ bpm, ligne: LIGNES[li], voix: voix[li], depart: d.ecart_ms });
      if (!e || e.echec) { l.push({ echec: true }); continue; }
      lat.push(e.dsp_ms);
      for (const s of e.syllabes) l.push({ ...s, cas: c.nom, micro, bpm });
    }
    tous.push(...l);
    const ok = l.filter(x => !x.echec && x.total != null), tot = ok.map(x => Math.abs(x.total));
    lignes.push(`${c.nom}, ${micro ? 'par le micro' : 'sans micro'} : ${ok.length} syllabes entendues, |écart| médiane ${Math.round(med(tot))} ms, p90 ${Math.round(pct(tot, 0.9))}, max ${Math.round(Math.max(...tot))} ms ; sous 50 ms : ${tot.filter(v => v < 50).length}/${tot.length}`);
  }
  const s = tous.filter(x => !x.echec);
  const ab = (k) => s.filter(x => x[k] != null).map(x => Math.abs(x[k]));
  lignes.push(`— ses parts : la place sur la grille contre le vrai temps : médiane ${Math.round(med(ab('grilleE')))} ms, max ${Math.round(Math.max(...ab('grilleE')))} ; `
    + `l'attaque dans le son rendu contre sa place : médiane ${Math.round(med(ab('sonE')))} ms, max ${Math.round(Math.max(...ab('sonE')))} (${s.filter(x => x.sonE == null).length} attaques non retrouvées sur ${s.length})`);
  lignes.push(`— à la double croche où le chanteur la chantait : ${s.filter(x => x.fidele).length}/${s.length}`);
  const c = ab('cents'), pc = ab('pc');
  lignes.push(`— la hauteur (sa note) : |écart| médiane ${Math.round(med(c))} cents, p90 ${Math.round(pct(c, 0.9))}, max ${Math.round(Math.max(...c))} (${c.length} syllabes mesurées) ; `
    + `contre la note du morceau, à l'octave près : médiane ${Math.round(med(pc))} cents, p90 ${Math.round(pct(pc, 0.9))}, max ${Math.round(Math.max(...pc))} ; sous 50 cents : ${pc.filter(v => v < 50).length}/${pc.length}`);
  lignes.push(`— le traitement d'une ligne : médiane ${Math.round(med(lat))} ms, max ${Math.max(...lat)} ms (chauffé) ; la toute première après une relance : ${froidMs} ms`);
  console.log(lignes.join('\n'));
}
module.exports = { essaiLigne, voixDe, LIGNES };
