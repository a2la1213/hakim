/* (11/11, Ahmed : « j'aimerais un bouton pour qu'il n'entende pas le retour du micro (voix des gens du live par le micro), et aussi pour qu'il
   reste justement dans les voix de sa tête. Théoriquement il devrait n'entendre que ma voix ou celle de ceux qui sont physiquement à mes
   côtés ; sinon il entend depuis son intérieur ceux qui parlent directement via une appli du téléphone. »)
   (MESURE : la première façon, gardée pour ses mesures ; le cockpit juge en spectre, retour-spectre.js.) LE RETOUR DU MICRO PAR SON ENVELOPPE
   (le niveau toutes les 100 ms, ses graves). Au banc (mesure/retour-micro-banc.js), elle ne voyait plus papa sous le live : réglée pour le garder
   (papa intact à 100 % jusqu'à − 6 dB), elle n'écartait plus que 3 à 9 % des morceaux de pur retour ; réglée pour écarter 30 %, elle abîmait
   jusqu'à 21 % des phrases de papa. D'où le spectre. Pendant un live joué sur le haut-parleur, ce que joue le téléphone (son intérieur, qu'il entend déjà
   par la capture de l'appli) revient par le micro. Comme pour l'écho de sa propre voix (conversation.js, creerEcho), on apprend le CHEMIN du
   téléphone jusqu'au micro (son retard, sa force, bande par bande) et on PRÉDIT ce qui en revient : la part du micro que l'intérieur explique
   au bon retard est un retour, pas une personne présente. Avec le bouton (réglage micro_sans_retour, éteint par défaut), un morceau du micro
   qui n'est QUE ce retour est écarté (il reste entendu par l'intérieur) ; tout le reste est gardé.
   Garde-fou (Ahmed) : la voix de papa n'est JAMAIS retirée, même s'il parle en même temps que le live. Un morceau est gardé dès que :
   - quelque chose y dépasse le retour prédit 300 ms d'affilée : son niveau (EXCES_X fois), ou ses GRAVES (le petit haut-parleur du téléphone
     n'en rend presque pas, une voix d'homme près du micro en a : mesuré le 11/11 sur les morceaux du live de 08:09 à 09:19, graves / médiums
     du micro 1,20 en médiane quand c'est papa seul, 0,20 quand c'est le live revenu ; et le retour y était PLUS FORT que papa : niveau médian
     0,22 contre 0,09, papa à − 8 dB du retour) ;
   - son oreille des voix y entend papa (sa voix, ou « papa ? ») ;
   - le chemin n'est pas appris, l'intérieur ne couvre pas le morceau, ou la ressemblance est trop faible.
   Dans le doute, le micro garde le son, et le doute est noté au journal.
   Mesuré (mesure/retour-micro-journaux.js, son-flux du 11/11, live de 08:09 à 09:19 sur le haut-parleur) : par fenêtres de 30 s, la corrélation
   des logarithmes du micro et de l'intérieur au meilleur retard vaut 0,53 en médiane (≥ 0,6 : 31 % des fenêtres) ; avec l'intérieur décalé de
   10 ou 20 min (le témoin) : 0,20 et 0,18 (≥ 0,6 : 0 et 4 %). Le retour existe et se voit ; son retard, au Mac, 40 ms en médiane.
   Les trames : [niveau, graves, médiums] (RMS ; les graves sous ~250 Hz et les médiums jusqu'à ~2 kHz, les deux filtres d'EcranService), à
   l'heure de leur MILIEU, sur l'horloge du téléphone. */
'use strict';

const PAS_MS = 100;                 // les trames de son intérieur (EcranService : 1 600 échantillons à 16 kHz) et celles du micro
const EPS = 1e-3;
const TOLERANCE_MS = 100;           // la prédiction prend le plus fort de l'intérieur à ±100 ms du retard (une trame de part et d'autre)
const EXCES_X = 2;                  // au-delà de 2 fois le retour prédit (+6 dB) : autre chose que le retour (une voix proche, la pièce)
const GRAVES_X = 2.5;               // ses graves au-delà de 2,5 fois les graves prédits du retour (sa part de graves au micro × son niveau prédit)…
const GRAVES_MIN = 0.004;           // … et assez forts pour être une voix (RMS sous 250 Hz)
const GRAVES_MORCEAU_X = 1.5;       // le morceau entier : sa part de graves (médiane de ses trames) au-delà de 1,5 fois celle du retour, une voix
                                    // proche y parle (papa à − 8 dB sous le live : calé sur le vrai, la part d'un mélange monte de 1,8 fois)
const EXCES_MS = 300;               // 300 ms d'affilée au-dessus : une voix (une syllabe tient 150 à 250 ms ; un éclat, moins)
const EXCES_TOTAL_MS = 500;         // ou 500 ms au-dessus en tout, même par bouts : des syllabes qui passent dans les creux du live
const VOIX_MIN = 0.006;             // le niveau d'une trame qui porte du son (RMS ; le seuil de la page est à 0,012 avant rééchantillonnage)
const PART_RETOUR = 0.85;           // la part de ses trames sonores que le retour explique, pour écarter un morceau
const RESSEMBLANCE_MIN = 0.5;       // et la ressemblance (corrélation des logarithmes) de ses trames au retour prédit
const COUVERTURE_MIN = 0.7;         // l'intérieur doit couvrir 70 % du morceau (ses trames arrivent chaque seconde)
const CHEMIN_VIE_MS = 3 * 60e3;     // un chemin appris vaut 3 min (le téléphone posé ailleurs, le volume changé : il se réapprend)
const CORRELATION_CHEMIN = 0.6;     // un chemin n'est appris que sur une ressemblance nette (le témoin dépasse 0,6 dans 4 % des fenêtres)
const AGC = [0.6, 1];               // la force du morceau ajustée sur lui-même (le gain automatique du micro bouge), seulement vers le bas : un
                                    // micro plus fort que le retour prédit, c'est peut-être quelqu'un (au banc, monter de 25 % cachait papa à − 6 dB)
const SONORES_MIN = 8;              // 0,8 s de son au moins pour écarter un morceau (moins : trop peu pour juger, sauf ses mots du dedans)

// l'enveloppe d'un WAV PCM 16 bits mono (le format de conversation.js, 16 kHz) : niveau, graves, médiums (RMS) de chaque trame ; null sinon
function enveloppeWav(buf, pasMs = PAS_MS) {
  if (!buf || buf.length < 44 || buf.toString('ascii', 0, 4) !== 'RIFF' || buf.toString('ascii', 8, 12) !== 'WAVE') return null;
  let o = 12, taux = 0, canaux = 0, bits = 0, data = -1, n = 0;
  while (o + 8 <= buf.length) {
    const id = buf.toString('ascii', o, o + 4), taille = buf.readUInt32LE(o + 4);
    if (id === 'fmt ') { canaux = buf.readUInt16LE(o + 10); taux = buf.readUInt32LE(o + 12); bits = buf.readUInt16LE(o + 22); }
    if (id === 'data') { data = o + 8; n = Math.min(taille, buf.length - data); break; }
    o += 8 + taille + (taille & 1);
  }
  if (data < 0 || bits !== 16 || canaux !== 1 || !(taux > 0)) return null;
  // ses graves : un passe-bas NET à 250 Hz (Butterworth d'ordre 4 : deux biquads), pas le filtre doux d'EcranService (6 dB par octave, qui
  // laisse passer la voix jusqu'à 1 kHz : au banc, le retour y avait autant de graves que papa) ; ses médiums, comme EcranService
  const km = 1 - Math.exp(-2 * Math.PI * 2000 / taux), kb = 1 - Math.exp(-2 * Math.PI * 250 / taux);
  const biquad = (q) => {
    const w = 2 * Math.PI * 250 / taux, al = Math.sin(w) / (2 * q), c = Math.cos(w), a0 = 1 + al;
    const b0 = (1 - c) / 2 / a0, b1 = (1 - c) / a0, a1 = -2 * c / a0, a2 = (1 - al) / a0;
    let x1 = 0, x2 = 0, y1 = 0, y2 = 0;
    return (x) => { const y = b0 * x + b1 * x1 + b0 * x2 - a1 * y1 - a2 * y2; x2 = x1; x1 = x; y2 = y1; y1 = y; return y; };
  };
  const passeBas1 = biquad(0.5412), passeBas2 = biquad(1.3066);
  const parTrame = Math.round(taux * pasMs / 1000), total = Math.floor(n / 2), niveaux = [], graves = [], mediums = [];
  let bas = 0, moyen = 0;
  for (let d = 0; d + parTrame <= total; d += parTrame) {
    let s = 0, sg = 0, sm = 0;
    for (let i = 0; i < parTrame; i++) {
      const x = buf.readInt16LE(data + 2 * (d + i)) / 32768;
      const g = passeBas2(passeBas1(x));
      bas += kb * (x - bas); moyen += km * (x - moyen);
      s += x * x; sg += g * g; sm += (moyen - bas) * (moyen - bas);
    }
    niveaux.push(Math.sqrt(s / parTrame)); graves.push(Math.sqrt(sg / parTrame)); mediums.push(Math.sqrt(sm / parTrame));
  }
  return { taux, pasMs, niveaux, graves, mediums, dureeMs: Math.round(total * 1000 / taux) };
}

// la valeur d'une suite [{t, v, g, m}] triée à l'instant t (interpolée ; k : 'v', 'g' ou 'm') ; null hors des trames, ou dans un trou
function valeur(l, t, trouMax = 250, k = 'v') {
  if (!l || !l.length) return null;
  let a = 0, b = l.length - 1;
  if (t < l[0].t || t > l[b].t) return null;
  while (b - a > 1) { const m = (a + b) >> 1; if (l[m].t <= t) a = m; else b = m; }
  if (l[b].t - l[a].t > trouMax) return null;
  const x = Number(l[a][k]), y = Number(l[b][k]);
  if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
  const f = l[b].t === l[a].t ? 0 : (t - l[a].t) / (l[b].t - l[a].t);
  return x * (1 - f) + y * f;
}
function correlation(xs, ys) {
  const n = xs.length; if (n < 3) return null;
  let sx = 0, sy = 0; for (let i = 0; i < n; i++) { sx += xs[i]; sy += ys[i]; }
  const mx = sx / n, my = sy / n; let num = 0, dx = 0, dy = 0;
  for (let i = 0; i < n; i++) { num += (xs[i] - mx) * (ys[i] - my); dx += (xs[i] - mx) ** 2; dy += (ys[i] - my) ** 2; }
  return dx > 1e-9 && dy > 1e-9 ? num / Math.sqrt(dx * dy) : null;
}
const quantile = (xs, q) => { const s = xs.filter(Number.isFinite).sort((a, b) => a - b); return s.length ? s[Math.min(s.length - 1, Math.floor(q * s.length))] : null; };
const mediane = (xs) => quantile(xs, 0.5);

/* Le CHEMIN du téléphone jusqu'au micro, sur une même horloge (tel, mic : [{t, v, g, m}] triées) : le retard (ms, de o.de à o.a) où le
   logarithme du micro suit le mieux celui de l'intérieur ; un pic net seulement (ses autres sommets, à plus de 200 ms, au moins 0,08 plus bas) ;
   sa force : la médiane du rapport micro / intérieur là où l'intérieur sonne le plus (la moitié haute de ses trames sonores) ; sa part de
   GRAVES au micro (graves / niveau du micro, la médiane sur ces mêmes trames, celles que le retour explique) : le petit haut-parleur en rend
   peu, une voix proche en a. null : pas de chemin net. */
function apprendreChemin(tel, mic, o = {}) {
  const de = Number.isFinite(o.de) ? o.de : -500, a = Number.isFinite(o.a) ? o.a : 1500, pas = o.pas || 20;
  const cMin = Number.isFinite(o.correlation) ? o.correlation : CORRELATION_CHEMIN;
  // toutes ses trames : ses blancs comptent autant que ses mots (ils reviennent au micro avec lui) ; il faut qu'il joue 30 % du temps au moins
  const ref = (tel || []).filter(x => x && Number.isFinite(x.v));
  if (ref.length < 100 || !mic || mic.length < 100 || ref.filter(x => x.v > VOIX_MIN).length < ref.length * 0.3) return null;
  const courbe = [];
  for (let lag = de; lag <= a; lag += pas) {
    const xs = [], ys = [];
    for (const x of ref) { const y = valeur(mic, x.t + lag); if (y !== null) { xs.push(Math.log(x.v + EPS)); ys.push(Math.log(y + EPS)); } }
    courbe.push({ lag, c: xs.length >= 80 ? correlation(xs, ys) : null });
  }
  const ok = courbe.filter(x => x.c !== null);
  if (!ok.length) return null;
  const meilleur = ok.reduce((m, x) => (x.c > m.c ? x : m));
  if (meilleur.c < cMin) return null;
  // ses autres sommets (et ses bords), à plus de 200 ms : deux retards qui se valent, c'est un rythme régulier (une boucle), pas un chemin
  const c = (i) => (courbe[i] && courbe[i].c !== null ? courbe[i].c : -Infinity);
  const autres = [];
  for (let i = 0; i < courbe.length; i++) {
    if (courbe[i].c === null || Math.abs(courbe[i].lag - meilleur.lag) <= 200) continue;
    const bord = i === 0 || i === courbe.length - 1 || c(i - 1) === -Infinity || c(i + 1) === -Infinity;
    if (bord || (c(i) >= c(i - 1) && c(i) > c(i + 1))) autres.push(courbe[i].c);
  }
  if (meilleur.c - Math.max(-1, ...autres) < 0.08) return null;
  const sonores = ref.filter(x => x.v > VOIX_MIN), haut = mediane(sonores.map(x => x.v));
  const paires = [];
  for (const x of sonores) { if (x.v < haut) continue; const y = valeur(mic, x.t + meilleur.lag); if (y !== null) paires.push({ x, y, r: y / x.v }); }
  if (paires.length < 20) return null;
  const gain = mediane(paires.map(p => p.r));
  if (!(gain > 0)) return null;
  // sa part de graves : seulement là où le micro n'est que le retour (son niveau à moins de 1,5 fois le retour prédit) ; une voix proche
  // pendant l'apprentissage l'aurait gonflée (papa devenu moins visible) : le 40e centile, pas la moyenne
  const basses = [];
  for (const p of paires) { if (p.r > 1.5 * gain || p.r < gain / 1.5) continue; const g = valeur(mic, p.x.t + meilleur.lag, 250, 'g'); if (g !== null && p.y > 0) basses.push(g / p.y); }
  const r3 = (x) => (x === null ? null : Math.round(x * 1000) / 1000);
  return { retardMs: meilleur.lag, correlation: Math.round(meilleur.c * 100) / 100, gain: r3(gain), graves: basses.length >= 20 ? r3(quantile(basses, 0.4)) : null };
}
// un chemin encore bon à l'instant (appris il y a moins de CHEMIN_VIE_MS, une force non nulle)
const cheminActif = (c, maintenant = Date.now()) => !!(c && c.gain > 0 && Number.isFinite(c.retardMs) && maintenant - (Number(c.ts) || 0) < CHEMIN_VIE_MS);

// le retour prédit à l'instant t (l'horloge du micro) : v, sa force × le plus fort de l'intérieur au retard (±TOLERANCE_MS : la pièce résonne,
// les trames ne tombent pas au même instant) ; c, sa force × l'intérieur au retard exact (pour la ressemblance et le gain du morceau) ; g, ses
// graves (sa part de graves apprise × v ; null sans part apprise : alors les graves ne jugent rien) ; null sans intérieur
function retourPredit(tel, t, chemin) {
  let v = null;
  for (let d = -TOLERANCE_MS; d <= TOLERANCE_MS; d += PAS_MS / 2) { const x = valeur(tel, t - chemin.retardMs + d); if (x !== null) v = Math.max(v === null ? 0 : v, x); }
  if (v === null) return null;
  const c = valeur(tel, t - chemin.retardMs);
  return { v: chemin.gain * v, c: chemin.gain * (c === null ? v : c), g: Number(chemin.graves) > 0 ? chemin.graves * chemin.gain * v : null };
}
// son oreille des voix y a-t-elle entendu papa ? (le verdict du morceau, ses locuteurs : « Ahmed », « papa », « papa ? »)
function papaEntendu(voix) {
  if (!voix || typeof voix !== 'object') return false;
  const v = String(voix.verdict || '').toLowerCase(), s = Number(voix.score);
  if ((v === 'ahmed' || v === 'papa') && !(s < 0.45)) return true;
  return (Array.isArray(voix.locuteurs) ? voix.locuteurs : []).some(l => /^(?:ahmed|papa)\s*\??$/i.test(String(l).trim()));
}

/* JUGER un morceau du micro. mic : [{t, v, g, m}] ses trames (100 ms, l'horloge de l'intérieur) ; tel : les trames de l'intérieur autour ;
   chemin : { retardMs, gain, graves, ts } ; voix : le verdict de son oreille des voix ({ verdict, score, locuteurs }) ; texteDuDedans :
   ses mots sont ceux que l'intérieur a dits (dedans.js : « mots » ou « paroles »). Rend { verdict, raison, ... } :
   - 'retour' : écarté (il reste entendu par l'intérieur) ;
   - 'doute'  : gardé, et noté (raison : voix_papa, voix_au_dessus, partiel, couverture, sans_chemin) ;
   - 'garde'  : gardé (rien ne joue, ou c'est une voix de la pièce). */
function jugerMorceau({ mic, tel, chemin, voix = null, texteDuDedans = false, maintenant = Date.now(), o = {} } = {}) {
  const exX = o.exces_x || EXCES_X, exMs = o.exces_ms || EXCES_MS, partMin = o.part || PART_RETOUR, rMin = Number.isFinite(o.ressemblance) ? o.ressemblance : RESSEMBLANCE_MIN;
  const totalMs = o.exces_total_ms || EXCES_TOTAL_MS, agcMax = Number.isFinite(o.agc_max) ? o.agc_max : AGC[1];
  const gX = o.graves_x || GRAVES_X, gmX = o.graves_morceau_x || GRAVES_MORCEAU_X, sansGraves = o.graves === false, sansAgc = o.agc === false;
  const trames = (mic || []).filter(x => x && Number.isFinite(x.v));
  const sonores = trames.filter(x => x.v >= VOIX_MIN);
  const base = { trames: trames.length, sonores: sonores.length };
  if (!sonores.length) return { verdict: 'garde', raison: 'silence', ...base };
  const papa = papaEntendu(voix);
  if (!cheminActif(chemin, maintenant)) {
    // rien de prédit : sans chemin appris, le micro garde tout ; un doute seulement si l'intérieur jouait vraiment pendant ce morceau
    const joue = trames.filter(x => { const v = valeur(tel, x.t); return v !== null && v >= VOIX_MIN; }).length;
    return { verdict: joue >= trames.length * 0.5 ? 'doute' : 'garde', raison: 'sans_chemin', papa, ...base };
  }
  const preds = trames.map(x => retourPredit(tel, x.t, chemin));
  // le gain automatique du micro bouge de quelques dB : la force ajustée sur ce morceau (la médiane de son rapport au retour prédit au retard
  // exact, là où le retour sonne), bornée : une voix qui parle tout le morceau par-dessus ne la monte que de 25 % au plus
  const rapports = trames.map((x, i) => (preds[i] && x.v >= VOIX_MIN && preds[i].c >= VOIX_MIN ? x.v / preds[i].c : NaN));
  const q = quantile(rapports, 0.5);
  const agc = sansAgc || q === null ? 1 : Math.max(AGC[0], Math.min(agcMax, q));
  let couvertes = 0, expliquees = 0, joue = 0, run = 0, runMax = 0, graves = 0, exces = 0;
  const xs = [], ys = [];
  trames.forEach((x, i) => {
    const p = preds[i];
    if (!p) { run = 0; return; }
    couvertes++;
    if (p.v >= VOIX_MIN * 0.5) joue++;
    if (x.v < VOIX_MIN) { run = 0; return; }
    xs.push(Math.log(x.v + EPS)); ys.push(Math.log(p.c + EPS));
    // ses graves : une voix proche du micro (le haut-parleur du téléphone n'en rend presque pas)
    const gx = Number(x.g), grave = !sansGraves && p.g !== null && Number.isFinite(gx) && gx >= GRAVES_MIN && gx > gX * agc * p.g;
    if (grave) graves++;
    if (x.v <= exX * agc * p.v && !grave) { expliquees++; run = 0; } else { exces++; run += PAS_MS; if (run > runMax) runMax = run; }
  });
  // sa part de graves, sur tout le morceau : une voix proche sous le live (ses graves s'ajoutent, le haut-parleur n'en rend presque pas)
  const partGraves = sansGraves || !(Number(chemin.graves) > 0) ? null : mediane(sonores.filter(x => Number.isFinite(Number(x.g))).map(x => Number(x.g) / x.v));
  const gravesMorceau = partGraves !== null && partGraves > gmX * chemin.graves;
  const couverture = trames.length ? couvertes / trames.length : 0;
  const nSon = xs.length;
  const part = nSon ? expliquees / nSon : 0;
  const ressemblance = nSon >= 8 ? correlation(xs, ys) : null;
  const r2 = (x) => (x === null ? null : Math.round(x * 100) / 100);
  const res = { ...base, couverture: r2(couverture), part: r2(part), ressemblance: r2(ressemblance), exces_ms: runMax, exces_total_ms: exces * PAS_MS, graves_ms: graves * PAS_MS, part_graves: partGraves === null ? null : Math.round(partGraves * 1000) / 1000, graves_retour: chemin.graves, agc: r2(agc), papa, retard_ms: chemin.retardMs, gain: chemin.gain };
  if (couverture < COUVERTURE_MIN) return { verdict: joue ? 'doute' : 'garde', raison: 'couverture', ...res };
  if (joue < Math.max(2, couvertes * 0.2)) return { verdict: 'garde', raison: 'interieur_muet', ...res };
  const ressemble = ressemblance === null ? texteDuDedans : (ressemblance >= rMin || (texteDuDedans && ressemblance >= rMin - 0.2));
  const retour = part >= partMin && runMax < exMs && exces * PAS_MS < totalMs && !gravesMorceau && ressemble && (nSon >= SONORES_MIN || texteDuDedans);
  if (retour && papa) return { verdict: 'doute', raison: 'voix_papa', ...res };               // la voix de papa n'est jamais retirée
  if (retour) return { verdict: 'retour', raison: texteDuDedans ? 'chemin_et_mots' : 'chemin', ...res };
  if (gravesMorceau) return { verdict: part >= 0.5 ? 'doute' : 'garde', raison: 'graves', ...res };
  if (runMax >= exMs || exces * PAS_MS >= totalMs) return { verdict: part >= 0.5 ? 'doute' : 'garde', raison: 'voix_au_dessus', ...res };
  if (part >= 0.5) return { verdict: 'doute', raison: 'partiel', ...res };
  return { verdict: 'garde', raison: 'pas_le_retour', ...res };
}

// les trames d'un morceau du micro, à l'horloge de l'intérieur : t0 (ms) le début du morceau, env l'enveloppe du WAV (enveloppeWav)
const tramesDuMorceau = (t0, env, pasMs = PAS_MS) => (env && Array.isArray(env.niveaux) ? env.niveaux : []).map((v, i) => ({ t: t0 + i * pasMs + pasMs / 2, v,
  g: env.graves ? env.graves[i] : undefined, m: env.mediums ? env.mediums[i] : undefined }));

module.exports = { PAS_MS, SONORES_MIN, EXCES_X, EXCES_MS, EXCES_TOTAL_MS, GRAVES_X, GRAVES_MIN, GRAVES_MORCEAU_X, VOIX_MIN, PART_RETOUR, RESSEMBLANCE_MIN, COUVERTURE_MIN, CHEMIN_VIE_MS, CORRELATION_CHEMIN,
  enveloppeWav, valeur, correlation, apprendreChemin, cheminActif, retourPredit, papaEntendu, jugerMorceau, tramesDuMorceau };
