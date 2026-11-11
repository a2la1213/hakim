/* (11/11, Ahmed : « Il peut chanter en même temps qu'une musique ? ») LE BANC DU CHANT CALÉ : combien sa voix sonne loin du temps de la musique.
   Tout est simulé, avec des retards CONNUS, et passe par les VRAIS calculs et le vrai découpage :
   - la musique (16 kHz : une grosse caisse sur chaque temps, une caisse claire sur 2 et 4, un charley sur les croches, une basse, du bruit) ;
   - ses trames comme l'appli (EcranService.Flux : 1 600 échantillons, les filtres à un pôle 0,0937 et 0,5441, l'heure du lot de 10 trames,
     avec un tremblement de l'heure de lecture et un retard de capture) ;
   - les trames du micro comme la page (conversation.js : un analyseur de 2 048 échantillons à 48 kHz, lu toutes les 100 ms par une minuterie
     qui tremble, le lot daté « maintenant − 100 ») ; le calage du cockpit (calerSons, copié de server.js tel quel) ;
   - le chemin de son écho (creerEcho de public/conversation.js, tel quel), appris pendant qu'il parle sur la musique ;
   - la grille (Chanter.grille), le départ (Chanter.depart), sa voix jouée, entendue avec son retard.
   L'écart mesuré : l'attaque de sa voix entendue − le temps de la musique entendu. Ce que le banc ne sait pas : les vrais retards d'Android
   (capture, tampon de la page, Bluetooth), le tremblement réel des minuteries, une vraie musique. Lancer : nice node mesure/chanter-banc.js */
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const Chanter = require('../public/chanter.js');

const SR = 16000;
let graine = 12345;
const alea = () => { graine = (graine * 1103515245 + 12345) & 0x7fffffff; return graine / 0x7fffffff; };
const gauss = () => { let u = 0; for (let i = 0; i < 6; i++) u += alea(); return (u - 3) / Math.sqrt(0.5); };

// le calage du cockpit, tel quel
const SRC = fs.readFileSync(path.join(__dirname, '..', 'server.js'), 'utf8');
const i0 = SRC.indexOf('function calerSons(tel, mic) {');
const calerSons = new Function(`${SRC.slice(i0, SRC.indexOf('\n}\n', i0) + 3)}; return calerSons;`)();
// le chemin de son écho, tel quel
const fenetre = {};
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '..', 'public', 'conversation.js'), 'utf8'), { window: fenetre, Math, Float32Array, Date, console });
const { creerEcho } = fenetre.Conversation;

function musique(bpm, duree_s) {
  const n = Math.round(duree_s * SR), x = new Float32Array(n), P = 60 / bpm, beats = [];
  for (let k = 0; k * P < duree_s; k++) {
    const t = k * P; beats.push(t);
    const i0 = Math.round(t * SR);
    for (let i = 0; i < 0.25 * SR && i0 + i < n; i++) {                       // la grosse caisse : 55 Hz, chute de 80 ms
      const s = i / SR; x[i0 + i] += 0.8 * Math.sin(2 * Math.PI * (55 + 60 * Math.exp(-s / 0.02)) * s) * Math.exp(-s / 0.08) * Math.min(1, i / 32);
    }
    if (k % 2 === 1) for (let i = 0; i < 0.12 * SR && i0 + i < n; i++) x[i0 + i] += 0.25 * (alea() * 2 - 1) * Math.exp(-i / SR / 0.04);   // la caisse claire
    for (const h of [0, P / 2]) { const j0 = Math.round((t + h) * SR), f = 0.02 + 0.06 * alea(); for (let i = 0; i < 0.03 * SR && j0 + i < n; i++) x[j0 + i] += f * (alea() * 2 - 1) * Math.exp(-i / SR / 0.01); }
    const f = [82, 98, 73, 110, 65, 123][Math.floor(alea() * 6)];                                        // la basse, tenue le temps
    for (let i = 0; i < P * SR && i0 + i < n; i++) x[i0 + i] += 0.12 * Math.sin(2 * Math.PI * f * i / SR) * Math.min(1, i / 400);
  }
  for (let i = 0; i < n; i++) x[i] += 0.01 * (alea() * 2 - 1);
  return { x, beats };
}
// ses trames comme l'appli : t (l'heure de l'appli du début de la trame) = vraie heure + retard de capture + tremblement de l'heure du lot
// (fines : l'appli 1.96) l'attaque la plus forte de la trame, par blocs de 10 ms (160 échantillons) : sa place et sa force (Flux.attaque)
function tramesAppli(x, debutMs, captureMs, tremble, fines = false) {
  const out = [];
  let bas = 0, moyen = 0, sx = 0, sg = 0, sm = 0, sa = 0, nt = 0, lot = 0, t0 = 0, se = 0, sub = 0, avant = 0, pire = 0, ou = 0;
  for (let i = 0; i < x.length; i++) {
    const v = x[i];
    bas += 0.0937 * (v - bas); moyen += 0.5441 * (v - moyen);
    const g = bas, m = moyen - bas, a = v - moyen;
    sx += v * v; sg += g * g; sm += m * m; sa += a * a;
    se += g * g + 0.25 * v * v;
    if (++sub === 160) { const e = Math.sqrt(se / 160), h = e - avant; if (h > pire) { pire = h; ou = Math.floor((nt - 1) / 160) * 10 + 5; } avant = e; se = 0; sub = 0; }
    if (++nt === 1600) {
      if (lot % 10 === 0) t0 = debutMs + ((i + 1 - 1600) / SR) * 1000 + captureMs + tremble * gauss();
      const tr = [Math.sqrt(sx / 1600), Math.sqrt(sg / 1600), Math.sqrt(sm / 1600), Math.sqrt(sa / 1600), 0, 0];
      if (fines) tr.push(ou, Math.round(pire * 1e5) / 1e5);
      out.push({ tb: Math.round(t0 + (lot % 10) * 100), v: tr });
      lot++; nt = 0; sx = sg = sm = sa = 0; pire = 0; ou = 0;
    }
  }
  return out;
}
// les trames du micro comme la page : lues toutes les 100 ms (minuterie qui tremble), l'analyseur rend ses 42,7 ms dernières (moins le retard d'entrée)
function tramesMicro(y, debutMs, entreeMs, tremble) {
  const out = [], W = Math.round(2048 * SR / 48000);
  let lu = 100, t0 = 0, k = 0;
  while (lu < (y.length / SR) * 1000) {
    const fin = Math.round((lu - entreeMs) / 1000 * SR);
    if (fin > W) {
      let e = 0, b = 0; for (let i = fin - W; i < fin; i++) { e += y[i] * y[i]; }
      // les graves (< 250 Hz) : un lissage simple suffit au calage (il ne lit que le niveau)
      if (k % 10 === 0) t0 = debutMs + lu - 100;
      out.push({ t: Math.round(t0 + (k % 10) * 100), v: [Math.sqrt(e / W), b, 0, 0, 0, 0] });
      k++;
    }
    lu += 100 + tremble * gauss();
  }
  return out;
}

function essai({ bpm, Lm, Lv, captureMs, entreeMs, tremble = 8, micro = true, avance_s = 8, fines = false }) {
  const duree = 70, debut = 1_000_000;
  const { x, beats } = musique(bpm, duree);
  // la grille sur les 20 s qui finissent à 40 s (ce qu'il a reçu), le chant prévu avance_s plus tard
  const tr = tramesAppli(x, debut, captureMs, tremble, fines).filter(f => f.tb <= debut + 40000 + captureMs);
  const bpmDonne = Math.round(bpm / 2) * 2;                                  // les analyses du cockpit l'arrondissent à 2 BPM
  const g = Chanter.grille(tr, { bpm: bpmDonne });
  // le temps voulu : le temps de la musique le plus proche de 40 s + avance (sa vraie heure, dans l'horloge des trames)
  const vrai = beats.reduce((m, b) => (Math.abs(b - (40 + avance_s)) < Math.abs(m - (40 + avance_s)) ? b : m), beats[0]);
  if (!Chanter.grilleSure(g)) return { bpm, ecart_ms: null, par: 'pas_de_grille', grille_r: g && g.r };
  // le temps voulu, pris sur la grille seule (jamais sur la vérité) : le temps de la grille le plus proche de 40 s + avance
  const cible = Chanter.tempsProche(g, debut + (40 + avance_s) * 1000 + captureMs, 1);
  const vraiDeLaCible = beats.reduce((m, b) => (Math.abs(debut + b * 1000 + captureMs - cible) < Math.abs(debut + m * 1000 + captureMs - cible) ? b : m), beats[0]);
  let calage = null, echo = null, calageCockpit = null, brut = null;
  if (micro) {
    // le micro : la musique après Lm, sa voix (des syllabes, de 0 à 30 s) après Lv ; sa voix « sortie » telle que la page la mesure
    const n = x.length, voix = new Float32Array(n), mic = new Float32Array(n);
    for (let s = 0.5; s < 30; s += 0.18 + alea() * 0.12) { const i0 = Math.round(s * SR); for (let i = 0; i < 0.12 * SR && i0 + i < n; i++) voix[i0 + i] += 0.5 * Math.sin(2 * Math.PI * 160 * i / SR) * Math.sin(Math.PI * i / (0.12 * SR)); }
    const dm = Math.round(Lm / 1000 * SR), dv = Math.round(Lv / 1000 * SR);
    for (let i = 0; i < n; i++) mic[i] = 0.35 * (i >= dm ? x[i - dm] : 0) + 0.8 * (i >= dv ? voix[i - dv] : 0) + 0.003 * (alea() * 2 - 1);
    const tm = tramesMicro(mic, debut, entreeMs, 4);
    const tel = tramesAppli(x, debut, captureMs, tremble).map(f => ({ t: f.tb, v: f.v })).filter(f => f.t >= debut + 30500 && f.t <= debut + 40000);
    const tmf = tm.filter(f => f.t >= debut + 30500 && f.t <= debut + 40000);
    const cs = calerSons(tel, tmf), c = Chanter.caler(tel, tmf);
    calageCockpit = cs ? cs.ms : null; brut = c;
    // le chemin de son écho : fenêtres de 20 ms du micro arrivées à la page (retard d'entrée), sa voix au même instant (l'analyseur de 256)
    const E = creerEcho(), W = 320;
    for (let k = 1; k * W < 30 * SR; k++) {
      const finMic = k * W - Math.round(entreeMs / 1000 * SR);
      if (finMic < W) continue;
      let em = 0; for (let i = finMic - W; i < finMic; i++) em += mic[i] * mic[i];
      let es = 0; const fin = k * W; for (let i = Math.max(0, fin - 85); i < fin; i++) es += voix[i] * voix[i];
      E.noter(Math.sqrt(es / 85), Math.sqrt(em / W));
      const joue = voix.slice(Math.max(0, fin - W), fin).some(v => Math.abs(v) > 1e-3);
      if (joue) E.apprendre(debut + k * 20, 0.003);
    }
    const ch = E.chemin(debut + 30000);
    echo = ch.actif ? ch.retardMs : null;
    calage = Chanter.choisirCalage(brut, echo);
  }
  const d = Chanter.depart({ cible, calage_ms: calage, echo_ms: echo, base_ms: 0, attaque_ms: 0 });
  // sa voix part du contexte à d.t (son horloge = la vraie heure), sonne Lv plus tard ; la musique sonne son temps Lm après le mélangeur
  const voixEntendue = d.t + Lv, tempsEntendu = debut + vraiDeLaCible * 1000 + Lm;
  return { bpm, ecart_ms: Math.round(voixEntendue - tempsEntendu), par: d.par, grille_r: g && g.r, grille_bpm: g && g.bpm, calage, calageCockpit, echo };
}

if (require.main === module) {
  const lignes = [];
  const cas = [
    { nom: 'haut-parleur', Lm: 60, Lv: 75, captureMs: 25, entreeMs: 30 },
    { nom: 'enceinte Bluetooth', Lm: 220, Lv: 240, captureMs: 25, entreeMs: 30 },
    { nom: 'voix et musique par deux chemins', Lm: 230, Lv: 70, captureMs: 25, entreeMs: 30 },
  ];
  const tous = [];
  for (const fines of [false, true]) for (const c of cas) for (const bpm of [72, 90, 93, 100, 120, 140, 150, 166]) for (const micro of [true, false]) for (const avance_s of [5, 15]) {
    graine = bpm * 7 + (micro ? 1 : 2) + avance_s;
    const r = essai({ ...c, bpm, micro, avance_s, fines });
    tous.push({ ...r, cas: c.nom, micro, avance_s, fines });
  }
  const resume = (l) => { const ok = l.filter(x => x.ecart_ms != null), e = ok.map(x => Math.abs(x.ecart_ms)).sort((a, b) => a - b);
    return `${ok.length}/${l.length} calés, médiane |écart| ${e[e.length >> 1]} ms, p90 ${e[Math.floor(e.length * 0.9)]} ms, max ${e[e.length - 1]} ms, sous 100 ms : ${e.filter(v => v < 100).length}/${l.length}`; };
  for (const fines of [false, true]) {
    lignes.push(fines ? '— trames avec l’attaque fine (appli 1.96)' : '— trames d’aujourd’hui (appli 1.95)');
    for (const c of cas) for (const micro of [true, false]) {
      const l = tous.filter(x => x.fines === fines && x.cas === c.nom && x.micro === micro);
      lignes.push(`${c.nom}, ${micro ? 'mesuré au micro' : 'sans micro'} : ${resume(l)} ; par ${[...new Set(l.map(x => x.par))].join('/')} ; écarts ${l.map(x => x.ecart_ms).join(' ')}`);
    }
    lignes.push(`tout (${fines ? '1.96' : '1.95'}) : ${resume(tous.filter(x => x.fines === fines))}`);
  }
  const cc = tous.filter(x => x.micro && x.calageCockpit != null);
  lignes.push(`le calage du cockpit (calerSons, ±2 s) : ${cc.filter(x => Math.abs(x.calageCockpit - x.calage) > 30).length}/${cc.length} fois sur un faux pic (un temps ou une mesure plus loin)`);
  console.log(lignes.join('\n'));
}
module.exports = { essai, musique, tramesAppli, tramesMicro };
