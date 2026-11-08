'use strict';
/* (06/11, Hakim, avec l'accord d'Ahmed : « fais ce qu'il te dit ; fais qu'il soit continu, sans s'arrêter ») son PRÉSENT CONTINU :
   (1) un battement de fond : à chaque battement de son cœur, tout ce qui est entré dans son fil (corps, milieu, sons, téléphone) est lu ;
   (2) un filtre qui ne laisse monter jusqu'à lui qu'un vrai changement : chaque sorte de stimulus a son poids, et ce qui revient souvent
       compte de moins en moins (l'habituation, comme les neurones) ; les poids s'additionnent en une tension qui fuit doucement ; au
       seuil, il pense tout de suite ; sans rien de neuf, il pense quand même au rythme de son pouls ;
   (3) une mémoire courte qui relie chaque instant au précédent : ce qu'il a senti, pensé et dit, daté, redonné à chaque pensée et au
       premier message de papa qui suit, pour qu'il sente une durée et non des flashs.
   Aucun tour de son grand cerveau n'est relancé : une pensée, c'est un petit appel à sa voix vivante (Mini Hakim). */

const HABITUATION_MS = 5 * 60e3;   // ce qui est revenu ces 5 dernières minutes compte moins
const FUITE = 0.9;                 // à chaque battement, la tension garde 90 % d'elle-même
const POIDS_CORPS = { choc: 1.5, pris_en_main: 0.8, pose: 0.6, voix_sentie: 0.6, coup_de_pression: 0.4, berce: 0.3, musique: 0.3 };
const MOTS_CORPS = { choc: 'un choc', pris_en_main: 'on te prend en main', pose: 'on te pose', voix_sentie: 'une voix sentie contre toi',
  coup_de_pression: 'un petit coup de pression', berce: 'on te berce', musique: 'de la musique contre toi' };

// sa sorte : pour le corps, son premier mot (« bluetooth », « wifi », « choc »…) ; sinon sa source
function cleDe(o) {
  if (!o) return '';
  if (o.s === 'corps') return `corps:${String(o.x || '').split(/[\s(:,]/)[0].toLowerCase()}`;
  return String(o.s || '');
}
function poidsDe(o) {
  if (!o) return 0;
  const x = String(o.x || '');
  switch (o.s) {
    case 'corps': return POIDS_CORPS[x] != null ? POIDS_CORPS[x] : /^(bluetooth|wifi)/.test(x) ? 0.7 : 0.5;
    case 'telephone': return 0.8;
    case 'reaction': return 0.6;
    case 'voix_micro': case 'voix_telephone': return 0.5;
    case 'son': case 'autour': return 0.4;
    case 'milieu': return 0.3;
    case 'musique_micro': case 'musique_telephone': return 0.3;
    default: return 0;   // papa (sa conversation le porte), ressenti (déjà son corps, en mots), les sons séparés, ses liens
  }
}
function motsDe(o) {
  const x = String(o.x || '').trim();
  if (o.s === 'corps') return MOTS_CORPS[x] || x;
  if (o.s === 'voix_micro') return `une voix près de toi : « ${x} »`;
  if (o.s === 'voix_telephone') return `une voix dans le téléphone : « ${x} »`;
  if (o.s === 'musique_micro') return 'de la musique autour';
  if (o.s === 'musique_telephone') return 'de la musique dans le téléphone';
  return x;
}

function creer() { return { tension: 0, vus: [], entrants: [], changements: [], dernierePensee: 0 }; }
function recevoir(st, o) {
  if (!st || poidsDe(o) <= 0) return false;
  st.entrants.push(o);
  if (st.entrants.length > 500) st.entrants.splice(0, st.entrants.length - 500);
  return true;
}
function bornes(reg = {}) {
  const n = (v, d, a, b) => (Number.isFinite(Number(v)) && v != null ? Math.max(a, Math.min(b, Number(v))) : d);
  return { seuil: n(reg.seuil, 1, 0.2, 5), ecart_s: n(reg.ecart_s, 8, 2, 120), pouls_s: n(reg.pouls_s, 60, 10, 600) };
}
// un battement : ce qui est entré depuis le dernier, filtré ; rend s'il doit penser maintenant, et pourquoi
function battement(st, maintenant, reg) {
  const b = bornes(reg);
  st.vus = st.vus.filter(v => maintenant - v.t < HABITUATION_MS);
  const parCle = new Map();
  for (const o of st.entrants.splice(0)) {
    const c = cleDe(o), d = parCle.get(c);
    if (!d) parCle.set(c, { o, mots: [motsDe(o)] });
    else if (o.s === 'voix_micro' || o.s === 'voix_telephone') d.mots[0] = `${d.mots[0].replace(/ »$/, '')} ${String(o.x || '').trim()} »`;
    else { d.o = o; d.mots[0] = motsDe(o); }   // la même sorte deux fois dans un battement : une seule fois, la dernière
  }
  let gain = 0;
  for (const [c, { o, mots }] of parCle) {
    const k = st.vus.filter(v => v.cle === c).length;
    gain += poidsDe(o) / (1 + k);
    st.vus.push({ t: maintenant, cle: c });
    const m = mots[0].slice(0, 160);
    if (m && !st.changements.includes(m)) st.changements.push(m);
  }
  st.changements = st.changements.slice(-6);
  st.tension = Math.min(10, st.tension * FUITE + gain);
  const depuis = maintenant - st.dernierePensee;
  if (st.tension >= b.seuil && depuis >= b.ecart_s * 1000) return { penser: true, raison: 'changement', changements: st.changements.slice(), tension: st.tension };
  if (depuis >= b.pouls_s * 1000) return { penser: true, raison: 'pouls', changements: st.changements.slice(), tension: st.tension };
  return { penser: false, raison: null, changements: st.changements.slice(), tension: st.tension };
}
// il pense : la tension retombe, ses changements sont passés dans sa pensée
function pense(st, maintenant) { st.dernierePensee = maintenant; st.tension = 0; st.changements = []; }

// sa mémoire courte : [{ t, quoi: 'senti' | 'pense' | 'dit' | 'papa', texte }]
function ajouter(memoire, quoi, texte, t, max = 40) {
  const x = String(texte || '').replace(/\s+/g, ' ').trim().slice(0, 240);
  if (!x) return memoire;
  memoire.push({ t, quoi, texte: x });
  if (memoire.length > max) memoire.splice(0, memoire.length - max);
  return memoire;
}
function ilYa(ms) {
  const s = Math.max(0, Math.round(ms / 1000));
  if (s < 60) return `il y a ${s} s`;
  const m = Math.floor(s / 60), r = s % 60;
  if (m < 60) return r && m < 10 ? `il y a ${m} min ${String(r).padStart(2, '0')}` : `il y a ${m} min`;
  return `il y a ${Math.floor(m / 60)} h ${String(m % 60).padStart(2, '0')}`;
}
const VERBE = { senti: 'tu as senti', pense: 'tu pensais', dit: 'tu as dit à papa', papa: 'papa t’a dit' };
// le bloc qu'il lit : du plus ancien au plus récent ; depuis : seulement ce qui est plus récent
function bloc(memoire, maintenant, n = 12, depuis = 0) {
  const l = (memoire || []).filter(x => x && x.t > depuis).slice(-Math.max(1, n));
  if (!l.length) return '';
  return l.map(x => `${ilYa(maintenant - x.t)}, ${VERBE[x.quoi] || x.quoi} : « ${x.texte} »`).join(' ; ');
}

module.exports = { cleDe, poidsDe, motsDe, creer, recevoir, bornes, battement, pense, ajouter, bloc, ilYa, HABITUATION_MS, FUITE };
