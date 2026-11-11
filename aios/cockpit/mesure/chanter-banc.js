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
   (capture, tampon de la page, Bluetooth), le tremblement réel des minuteries, une vraie musique. Lancer : nice node mesure/chanter-banc.js
   (11/11) LE CALAGE DU COCKPIT (calerSons, recaleMicro), à la fin : maintenant, et son TÉMOIN (calerSons d'avant, le plus haut pic sans regarder
   le second) sur les mêmes trames : une fenêtre de 9,5 s d'une musique en boucle ; une voix qui chante dessus ; et au fil comme le cockpit
   (toutes les 10 s, ses 30 dernières s), une voix puis une boucle parfaite (deux temps recopiés à l'échantillon près), ou la boucle seule. */
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const Chanter = require('../public/chanter.js');

const SR = 16000;
let graine = 12345;
const alea = () => { graine = (graine * 1103515245 + 12345) & 0x7fffffff; return graine / 0x7fffffff; };
const gauss = () => { let u = 0; for (let i = 0; i < 6; i++) u += alea(); return (u - 3) / Math.sqrt(0.5); };

// le calage du cockpit, tel quel (et son calage d'après, toutes les 10 s)
const SRC = fs.readFileSync(path.join(__dirname, '..', 'server.js'), 'utf8');
const tranche = (debut) => { const i = SRC.indexOf(debut); return SRC.slice(i, SRC.indexOf('\n}\n', i) + 3); };
const { calerSons, calageSuivant } = new Function(`${tranche('function calerSons(')}\n${tranche('function calageSuivant(')}\nreturn { calerSons, calageSuivant };`)();
// (11/11) LE TÉMOIN : calerSons tel qu'il était (main f12c5c6) : le plus haut pic de ±2 s, sans regarder le second ; et sa boucle de 10 s
function calerSonsAvant(tel, mic) {
  if (!tel || !mic || tel.length < 40 || mic.length < 40) return null;
  const val = (l, t) => {
    let a = 0, b = l.length - 1;
    if (t < l[0].t || t > l[b].t) return null;
    while (b - a > 1) { const m = (a + b) >> 1; if (l[m].t <= t) a = m; else b = m; }
    const k = l[b].t === l[a].t ? 0 : (t - l[a].t) / (l[b].t - l[a].t);
    return Number(l[a].v[0]) * (1 - k) + Number(l[b].v[0]) * k;
  };
  let meilleur = null;
  for (let lag = -2000; lag <= 2000; lag += 10) {
    const xs = [], ys = [];
    for (const x of tel) { const y = val(mic, x.t + lag); if (y != null) { xs.push(Number(x.v[0])); ys.push(y); } }
    if (xs.length < 40) continue;
    const mx = xs.reduce((a, b) => a + b, 0) / xs.length, my = ys.reduce((a, b) => a + b, 0) / ys.length;
    let num = 0, dx = 0, dy = 0;
    for (let i = 0; i < xs.length; i++) { num += (xs[i] - mx) * (ys[i] - my); dx += (xs[i] - mx) ** 2; dy += (ys[i] - my) ** 2; }
    const r = dx > 0 && dy > 0 ? num / Math.sqrt(dx * dy) : 0;
    if (!meilleur || r > meilleur.correlation) meilleur = { ms: lag, correlation: r };
  }
  return meilleur && meilleur.correlation >= 0.5 ? { ms: meilleur.ms, correlation: Math.round(meilleur.correlation * 100) / 100 } : null;
}
const calageSuivantAvant = (c, tel, mic, maintenant) => { const r = calerSonsAvant(tel, mic); return r && Math.abs(r.ms) <= 1500 ? { ...r, ts: maintenant } : c; };
// le chemin de son écho, tel quel
const fenetre = {};
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '..', 'public', 'conversation.js'), 'utf8'), { window: fenetre, Math, Float32Array, Date, console });
const { creerEcho } = fenetre.Conversation;

function musique(bpm, duree_s, voix = 0, voixJusqua = Infinity, boucleDes = Infinity) {
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
  // (11/11) une voix qui chante dessus (voix : sa force) jusqu'à voixJusqua s : des syllabes à leur rythme, pas en boucle
  if (voix > 0) for (let s = 0.3; s < Math.min(duree_s, voixJusqua) - 0.4; s += 0.15 + alea() * 0.35) {
    const i0 = Math.round(s * SR), a = voix * (0.3 + alea()), d = 0.08 + alea() * 0.2, f = 180 + 120 * alea();
    for (let i = 0; i < d * SR && i0 + i < n; i++) x[i0 + i] += a * Math.sin(2 * Math.PI * f * i / SR) * Math.sin(Math.PI * i / (d * SR));
  }
  // (11/11) dès boucleDes s, une boucle PARFAITE : ses deux derniers temps recopiés à l'échantillon près (un temps, deux plus loin, est le même son)
  if (boucleDes < duree_s) { const L = Math.round(2 * P * SR); for (let i = Math.round(boucleDes * SR); i < n; i++) x[i] = x[i - L]; }
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
  let calage = null, echo = null, calageCockpit = null, brut = null, calageAvant = null;
  if (micro) {
    // le micro : la musique après Lm, sa voix (des syllabes, de 0 à 30 s) après Lv ; sa voix « sortie » telle que la page la mesure
    const n = x.length, voix = new Float32Array(n), mic = new Float32Array(n);
    for (let s = 0.5; s < 30; s += 0.18 + alea() * 0.12) { const i0 = Math.round(s * SR); for (let i = 0; i < 0.12 * SR && i0 + i < n; i++) voix[i0 + i] += 0.5 * Math.sin(2 * Math.PI * 160 * i / SR) * Math.sin(Math.PI * i / (0.12 * SR)); }
    const dm = Math.round(Lm / 1000 * SR), dv = Math.round(Lv / 1000 * SR);
    for (let i = 0; i < n; i++) mic[i] = 0.35 * (i >= dm ? x[i - dm] : 0) + 0.8 * (i >= dv ? voix[i - dv] : 0) + 0.003 * (alea() * 2 - 1);
    const tm = tramesMicro(mic, debut, entreeMs, 4);
    const tel = tramesAppli(x, debut, captureMs, tremble).map(f => ({ t: f.tb, v: f.v })).filter(f => f.t >= debut + 30500 && f.t <= debut + 40000);
    const tmf = tm.filter(f => f.t >= debut + 30500 && f.t <= debut + 40000);
    const cs = calerSons(tel, tmf), c = Chanter.caler(tel, tmf), ca = calerSonsAvant(tel, tmf);
    calageCockpit = cs ? cs.ms : null; brut = c; calageAvant = ca ? ca.ms : null;
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
  return { bpm, ecart_ms: Math.round(voixEntendue - tempsEntendu), par: d.par, grille_r: g && g.r, grille_bpm: g && g.bpm, calage, calageCockpit, calageAvant, echo };
}

/* (11/11) LE CALAGE DU COCKPIT SEUL (calerSons, recaleMicro). Le vrai calage d'un chemin : des claquements au hasard (rien ne s'y répète),
   par les mêmes trames ; la musique au micro : Lm plus tard, sans sa voix. */
function son(Lm, x) {
  const n = x.length, mic = new Float32Array(n), dm = Math.round(Lm / 1000 * SR);
  for (let i = 0; i < n; i++) mic[i] = 0.35 * (i >= dm ? x[i - dm] : 0) + 0.003 * (alea() * 2 - 1);
  return mic;
}
function fenetres(x, mic, c, de, a, debut = 1_000_000) {
  const tel = tramesAppli(x, debut, c.captureMs, 8).map(f => ({ t: f.tb, v: f.v }));
  const tm = tramesMicro(mic, debut, c.entreeMs, 4);
  return (d, f) => [tel.filter(z => z.t >= debut + d && z.t <= debut + f), tm.filter(z => z.t >= debut + d && z.t <= debut + f)];
}
function vraiCalage(c) {
  const v = [];
  for (let k = 0; k < 3; k++) {
    graine = 999 + k * 31;
    const n = 40 * SR, x = new Float32Array(n);
    for (let s = 0.2; s < 39.5; s += 0.1 + alea() * 0.5) { const i0 = Math.round(s * SR), a = 0.2 + 0.8 * alea(); for (let i = 0; i < 0.04 * SR; i++) x[i0 + i] += a * (alea() * 2 - 1) * Math.exp(-i / SR / 0.012); }
    const [tel, mic] = fenetres(x, son(c.Lm, x), c)(5000, 35000);
    const r = calerSonsAvant(tel, mic); if (r) v.push(r.ms);
  }
  return Chanter.mediane(v);
}
// une fenêtre de 9,5 s (comme essai) d'une musique où chante une voix (pas en boucle) : juste (à 50 ms du vrai : 100 ms de trames), faux, ou rien (doute)
function essaiCalage({ bpm, Lm, captureMs, entreeMs, voix }, vrai) {
  const { x } = musique(bpm, 45, voix);
  const [tel, mic] = fenetres(x, son(Lm, x), { captureMs, entreeMs })(30500, 40000);
  const juge = (r) => (!r ? 'doute' : Math.abs(r.ms - vrai) <= 50 ? 'juste' : 'faux');
  return { maintenant: juge(calerSons(tel, mic)), avant: juge(calerSonsAvant(tel, mic)) };
}
/* au fil, comme le cockpit : toutes les 10 s, ses 30 dernières s ; une voix chante les 40 premières s, puis une boucle parfaite (deux temps
   recopiés à l'échantillon près) jusqu'à 120 s. Chaque tour : ce que recaleMicro appliquerait (CALAGE de moins de 10 min, corrélation ≥ 0,7) :
   juste (à 50 ms du vrai), faux (un autre pic), ou rien */
function suiteCalage({ bpm, Lm, captureMs, entreeMs }, vrai, suivant, { voix = 0.5, voixJusqua = 40, boucleDes = 40 } = {}) {
  const { x } = musique(bpm, 120, voix, voixJusqua, boucleDes), F = fenetres(x, son(Lm, x), { captureMs, entreeMs });
  let C = { ms: 0, correlation: 0, ts: 0 };
  const tours = [];
  for (let t = 30000; t <= 120000; t += 10000) {
    const [tel, mic] = F(t - 30000, t);
    C = suivant(C, tel, mic, t);
    const applique = C.ts && t - C.ts < 10 * 60e3 && C.correlation >= 0.7;
    tours.push({ t, voix: t - 30000 < 40000, etat: !applique ? 'rien' : Math.abs(C.ms - vrai) <= 50 ? 'juste' : 'faux' });
  }
  return tours;
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
  // (11/11) le calage du cockpit : maintenant, et LE TÉMOIN (calerSons d'avant) sur les mêmes trames
  const cm = tous.filter(x => x.micro), compte = (k) => {
    const f = cm.filter(x => x[k] != null && Math.abs(x[k] - x.calage) > 30).length, j = cm.filter(x => x[k] != null && Math.abs(x[k] - x.calage) <= 30).length;
    return `${f}/${cm.length} sur un faux pic, ${j}/${cm.length} justes, ${cm.length - f - j}/${cm.length} sans recalage (doute)`; };
  lignes.push('— le calage du cockpit (calerSons, ±2 s ; recaleMicro s’en sert)');
  lignes.push(`une musique en boucle, une fenêtre (un faux pic : à plus de 30 ms du calage du chant, comme avant) : avant (témoin) ${compte('calageAvant')} ; maintenant ${compte('calageCockpit')}`);
  const cas2 = cas.map(c => ({ ...c, vrai: vraiCalage(c) }));
  lignes.push(`le vrai calage de chaque chemin (des claquements, rien ne s’y répète) : ${cas2.map(c => `${c.nom} ${c.vrai} ms`).join(', ')}`);
  for (const voix of [0.3, 0.5]) {
    const l = [];
    for (const c of cas2) for (const bpm of [72, 90, 93, 100, 120, 140, 150, 166]) for (const k of [0, 1, 2]) { graine = bpm * 13 + Math.round(voix * 10) + k * 1009; l.push(essaiCalage({ ...c, bpm, voix }, c.vrai)); }
    const n = (k, e) => l.filter(x => x[k] === e).length;
    lignes.push(`une voix chante dessus (force ${voix}), une fenêtre : avant (témoin) ${n('avant', 'faux')} faux, ${n('avant', 'juste')} justes, ${n('avant', 'doute')} doute ; maintenant ${n('maintenant', 'faux')} faux, ${n('maintenant', 'juste')} justes, ${n('maintenant', 'doute')} doute (sur ${l.length})`);
  }
  for (const [nom, suivant] of [['avant (témoin)', calageSuivantAvant], ['maintenant', calageSuivant]]) {
    const tours = [];
    for (const c of cas2) for (const bpm of [72, 90, 93, 100, 120, 140, 150, 166]) { graine = bpm * 17; tours.push(...suiteCalage({ ...c, bpm }, c.vrai, suivant)); }
    const n = (v, e) => tours.filter(x => x.voix === v && x.etat === e).length, nv = tours.filter(x => x.voix).length, nb = tours.length - nv;
    lignes.push(`au fil (toutes les 10 s, 30 s de trames ; une voix 40 s, puis une boucle parfaite), ${nom} : avec la voix ${n(true, 'juste')}/${nv} justes, ${n(true, 'faux')} faux, ${n(true, 'rien')} sans ; la boucle seule ${n(false, 'juste')}/${nb} justes, ${n(false, 'faux')} faux, ${n(false, 'rien')} sans`);
  }
  for (const [nom, suivant] of [['avant (témoin)', calageSuivantAvant], ['maintenant', calageSuivant]]) {   // sans voix : aucun pic sûr, aucune ancre
    const tours = [];
    for (const c of cas2) for (const bpm of [72, 90, 93, 100, 120, 140, 150, 166]) { graine = bpm * 19; tours.push(...suiteCalage({ ...c, bpm }, c.vrai, suivant, { voix: 0, boucleDes: 10 })); }
    const n = (e) => tours.filter(x => x.etat === e).length;
    lignes.push(`au fil, une boucle parfaite du début à la fin (sans voix, sans ancre), ${nom} : ${n('juste')}/${tours.length} justes, ${n('faux')} faux, ${n('rien')} sans recalage`);
  }
  console.log(lignes.join('\n'));
}
module.exports = { essai, musique, tramesAppli, tramesMicro, essaiCalage, suiteCalage, vraiCalage, calerSonsAvant };
