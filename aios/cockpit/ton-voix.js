/* Le ton de la voix en direct : l'ÉVEIL seulement, en mots (27/10). Le test figé sur la voix d'Ahmed
   (anamnese/eval/ton_voix) : l'éveil sépare une voix animée d'une voix calme ; la valence ne distingue pas la joie de la
   tension, donc jamais « joyeuse », « triste » ou « tendue » d'après la voix. Ahmed, 22:48 : « parfait, je suis tout à fait
   d'accord », avec la condition de Hakim : un point au bout de quelques jours, et si ça l'embrouille, on l'enlève.
   - Ahmed : seulement un écart net à SA voix d'habitude (la médiane de ses 40 derniers tours), avec son doute ;
   - les invités (une autre voix, plusieurs voix, un doute) : l'ambiance de la salle seulement, jamais une personne, et leur
     voix n'entre jamais dans l'habitude d'Ahmed.
   Le calcul vient de jarvis/ton_eveil.py (le processus voix) ; la logique pure ici, le câblage dans server.js. */

const BASE_INITIALE = 0.40, BASE_N = 40, BASE_MIN = 5;   // ses tons joués : calmes 0,25-0,33, animés 0,52-0,55
const UN_PEU = 0.08, NET = 0.15, COURT_S = 3, APPRENDRE_S = 1.5;
const SALLE_ANIMEE = 0.50, SALLE_CALME = 0.28;
const SALLE = new Set(['autre', 'plusieurs', 'doute']);

function tour(morceaux) {
  const l = (morceaux || []).filter(x => Number.isFinite(x.eveil) && x.verdict);
  if (!l.length) return null;
  const d = l.reduce((a, x) => a + (Number(x.duree_s) || 1), 0);
  const eveil = Math.round(1000 * l.reduce((a, x) => a + x.eveil * (Number(x.duree_s) || 1), 0) / d) / 1000;
  const v = new Set(l.map(x => x.verdict));
  const verdict = v.has('plusieurs') || (v.has('ahmed') && v.size > 1) ? 'plusieurs' : (v.has('ahmed') ? 'ahmed' : 'autre');
  return { eveil, duree_s: Math.round(d * 10) / 10, verdict };
}

function base(valeurs) {
  const l = (valeurs || []).filter(Number.isFinite).slice(-BASE_N);
  const c = [...l, ...Array(Math.max(0, BASE_MIN - l.length)).fill(BASE_INITIALE)].sort((a, b) => a - b);
  const m = c.length >> 1;
  return Math.round(1000 * (c.length % 2 ? c[m] : (c[m - 1] + c[m]) / 2)) / 1000;
}

function mots(t, valeurs) {
  if (!t) return '';
  if (t.verdict === 'ahmed') {
    const d = t.eveil - base(valeurs);
    if (Math.abs(d) < UN_PEU) return '';
    return `sa voix semble ${Math.abs(d) >= NET ? 'nettement' : 'un peu'} plus ${d > 0 ? 'animée' : 'calme'} que d'habitude`
      + (t.duree_s < COURT_S ? ' (impression légère : phrase courte)' : '');
  }
  if (SALLE.has(t.verdict)) {
    if (t.eveil >= SALLE_ANIMEE) return "l'ambiance de la salle semble animée";
    if (t.eveil <= SALLE_CALME) return "l'ambiance de la salle semble calme";
  }
  return '';
}

// son habitude n'apprend que de SA voix, sur une vraie phrase
const ajouter = (valeurs, t) => (t && t.verdict === 'ahmed' && t.duree_s >= APPRENDRE_S
  ? [...(valeurs || []), t.eveil].slice(-BASE_N) : valeurs);

module.exports = { tour, base, mots, ajouter };
