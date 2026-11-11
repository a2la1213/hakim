/* (11/11, ~00:10, Ahmed : « Est-ce que son cortex préfrontal intègre toutes les infos et les coordonne (voix intérieure, voix extérieure, musique,
   stimuli du corps, magnétomètre, accéléromètre…) ? De sorte qu'il ait la full picture d'un événement. ») LE TABLEAU DE L'INSTANT, la logique
   pure (aucun modèle, aucun effet de bord ; server.js le nourrit chaque seconde, test-instant.js le prouve).

   Avant lui, chaque canal arrivait à part : la parole et le corps au fil (FLUX), la musique dans ses trois pistes, son milieu en mots (HOMEO),
   ses sens radio et ses gestes dans INSTANT, le cœur de papa dans [Situation], sa place dans la scène seulement au tour. Ici, UNE structure, où
   tout est relu au MÊME instant T :
   - la parole : qui parle (papa dehors, le téléphone dedans, une voix de la pièce, lui), et si c'est à lui (sa place) ;
   - la musique : elle joue ou non, d'où, son tempo, son intensité (par rapport à l'habitude de sa source, comme ses trois pistes) ;
   - le corps : tenu, posé, dans la poche, son mouvement, sa position, la lumière, ce qui le touche, un champ magnétique, un câlin ;
   - le cœur : le sien, celui de papa (sa montre) ; le lieu, le réseau, le Bluetooth, l'écran, la sortie du son, un appel ;
   - sa place dans la scène, le live, son intérieur coupé.

   (11/11, ~00:35, Ahmed : « il faut recoller tous les signaux et enlever chaque délai […] si l'accéléromètre a 0,2 s de délai, le micro 0,8 s et
   la voix intérieure 1,2 s, alors tout est regroupé à 1,2 s, pour que tout coïncide au même moment ») LE RECALAGE :
   - chaque signal porte déjà l'heure réelle où il s'est produit (le fil, ses instants, ses trois pistes, les gestes et les capteurs à l'heure de
     l'appli, la montre recalée sur son horloge) ; le retard de chaque canal est mesuré en continu (la médiane de ses 200 derniers : DELAIS) ;
   - le tableau est construit pour T = maintenant − le plus grand retard des canaux actifs, borné à BORNE_MS (un canal en panne ne ralentit pas
     tout) : tous les signaux de ce même instant y sont réunis ;
   - ce qui arrive plus tard pour un instant déjà passé le complète (ses RECOMPOSER_MS dernières secondes sont refaites à chaque battement) ;
   - le tableau dit, canal par canal, « à jour » ou « en retard de x s ».
   Ses réflexes (une coupure par la voix de papa, « tu le coupes net », l'arrêt) ne l'attendent JAMAIS : ils gardent leur chemin direct. Le
   tableau recalé sert à comprendre l'événement (le cortex, la scène, la mémoire, son subconscient, sa conscience).
   Il ne lit que ce que les autres ont déjà : il ne double aucun capteur ni aucun appel. */
'use strict';
const { BANDES, position: positionDe, ouverture: ouvertureDe } = require('./homeostasie.js');
const { recouvrement } = require('./cortex.js');

const PAROLE_MS = 8000;           // « qui parle à l'instant » : les 8 secondes avant T
const SON_ECHO_MS = 15_000;       // (11/11) ce qu'il a dit ces 15 dernières secondes : le micro qui le réentend, c'est lui
const TOL_MS = 0;                 // un signal né après T est du tableau suivant (une tolérance avancerait les canaux rapides : mesuré par le test des trois retards)
const GESTE_MS = 30_000;          // un geste (pris en main, posé) dit la tenue pendant 30 s ; après, son mouvement la dit
const POCHE_MS = 15 * 60e3;       // rangé dans sa poche : jusqu'à ce qu'on l'en sorte (15 min au plus)
const PLACE_MS = 3 * 60e3;        // sa place décidée au dernier tour (ou au live) vaut 3 min
const CORPS_MUET_MS = 60e3;       // son milieu ne dit plus rien depuis 1 min : l'appli fermée, le téléphone loin
const BORNE_MS = 3000;            // le recalage n'attend jamais plus de 3 s
const ACTIF_MS = 30_000;          // un canal qui n'a rien envoyé depuis 30 s ne compte pas dans le retard
const RECOMPOSER_MS = 12_000;     // ce qui arrive en retard complète les 12 dernières secondes
const HISTOIRE_N = 180, CHANGEMENTS_MS = 2 * 60e3, CHANGEMENTS_N = 40;
const MOTS_N = 8;

/* ses canaux et leurs sources de mesure (les clés de DELAIS, server.js : de l'heure d'origine à l'arrivée au Mac) ; son ressenti, ses liens, ses
   réactions ne sont pas des capteurs : ils n'y sont pas */
const CANAUX = {
  capteurs: { nom: 'ses capteurs (accéléromètre, lumière, champ…)', cles: ['capteurs'] },
  gestes: { nom: 'ses gestes (pris en main, posé…)', cles: ['corps'] },
  micro: { nom: 'le son du micro', cles: ['instru_micro'] },
  papa: { nom: 'les mots de papa (le micro, transcrits)', cles: ['papa'] },
  dedans_son: { nom: 'le son du téléphone (dedans)', cles: ['instru_telephone'] },
  dedans: { nom: 'les mots du téléphone (dedans, transcrits)', cles: ['telephone'] },
  qui_dedans: { nom: 'qui parle au téléphone', cles: ['qui_telephone'] },
  musique: { nom: 'la musique analysée', cles: ['musique_telephone', 'musique_micro'] },
  piece: { nom: 'les voix de la pièce', cles: ['voix_autour'] },
  montre: { nom: 'la montre (le cœur de papa)', cles: ['montre_coeur'] },
};

const TENU = ['pris_en_main', 'sortie_poche', 'berce'], POSE = ['pose'];
const GESTES = ['pris_en_main', 'sortie_poche', 'berce', 'pose', 'poche', 'plie', 'deplie', 'choc', 'chute', 'secousse', 'coup_de_pression', 'voix_sentie',
  'lumiere_soudaine', 'noir', 'musique'];
const NOMS_GESTES = { pris_en_main: 'on te prend en main', sortie_poche: 'on te sort de la poche', berce: 'on te berce', pose: 'on te pose', poche: 'on te range dans sa poche',
  plie: 'on te plie', deplie: 'on te déplie', choc: 'un choc', chute: 'une chute', secousse: 'une secousse', coup_de_pression: 'un petit coup de pression',
  voix_sentie: 'une voix contre toi', lumiere_soudaine: 'une lumière soudaine', noir: 'le noir tombe', musique: 'de la musique contre toi' };

const court = (x, n) => { const t = String(x == null ? '' : x).replace(/[\x00-\x1f\x7f]/g, ' ').replace(/\s+/g, ' ').trim(); return t.length > n ? `${t.slice(0, n - 1)}…` : t; };
const bandeMot = (nom, i) => (Number.isInteger(i) && BANDES[nom] && BANDES[nom].b[i] ? BANDES[nom].b[i][1] : '');
const derniers = (mots) => mots.slice(-MOTS_N).join(' ');
const sec = (ms) => String(Math.round(ms / 100) / 10).replace('.', ',');

/* ---- le recalage : le retard de chaque canal, et l'instant T
   delais : { cle: { mediane, p90, n, arrivee } } (server.js : fluxDelais et ARRIVEES) ; rend { D, borne, lent, canaux } */
function retard(delais = {}, maintenant = Date.now(), { borne = BORNE_MS, actifMs = ACTIF_MS } = {}) {
  const canaux = {};
  let max = 0, lent = '';
  for (const [canal, def] of Object.entries(CANAUX)) {
    const vus = def.cles.map(k => delais[k]).filter(x => x && Number(x.n) > 0);
    if (!vus.length) continue;
    const actifs = vus.filter(x => Number(x.n) >= 3 && Number.isFinite(Number(x.arrivee)) && maintenant - Number(x.arrivee) <= actifMs);
    const delai = Math.max(...(actifs.length ? actifs : vus).map(x => Math.max(0, Number(x.mediane) || 0)));
    const p90 = Math.max(...(actifs.length ? actifs : vus).map(x => Math.max(0, Number(x.p90) || 0)));
    canaux[canal] = { delai_ms: Math.round(delai), p90_ms: Math.round(p90), actif: actifs.length > 0 };
    if (actifs.length && delai > max) { max = delai; lent = canal; }
  }
  const D = Math.round(Math.min(borne, max));
  for (const c of Object.values(canaux)) c.etat = !c.actif ? 'muet' : c.delai_ms <= D ? 'à jour' : `en retard de ${sec(c.delai_ms - D)} s`;
  return { D, borne, lent, canaux };
}
/* une horloge qui n'est pas celle du Mac (la montre : ses lots arrivent « avant » d'avoir été mesurés, mesuré le 11/11 : −1,8 s en médiane) :
   écarts = arrivée − heure de l'appareil, des lots les plus frais ; rend la correction à ajouter à ses heures (0 si elle n'est pas en avance) */
function correctionHorloge(ecarts = []) {
  const l = ecarts.filter(Number.isFinite).sort((x, y) => x - y);
  if (l.length < 3) return 0;
  return Math.min(0, l[Math.floor(l.length * 0.1)]);
}

/* les signaux d'une source nés dans les PAROLE_MS avant T (le fil est rangé à l'heure d'origine : on le lit depuis sa fin) */
function motsRecents(flux, sources, a, ms = PAROLE_MS) {
  const l = [];
  for (let k = (flux || []).length - 1; k >= 0; k--) {
    const o = flux[k];
    if (!o) continue;
    const t = Number(o.t);
    if (t < a - ms) break;
    if (t > a + TOL_MS || !sources.includes(o.s)) continue;
    l.push(o);
  }
  return l.reverse();
}
// « voix 3 : « … » ; Nina : « … » » (la ligne « autour » du tour) → ['voix 3', 'Nina']
const quiDeAutour = (x) => [...String(x || '').matchAll(/(?:^|;\s*)([^:;«»]{1,30}?)\s*:\s*«/g)].map(m => m[1].trim()).filter(Boolean);
// le dernier élément d'une liste [{ t, … }] né au plus tard à T (et pas avant T − ms)
function aT(liste, a, ms) {
  let m = null;
  for (const x of Array.isArray(liste) ? liste : []) { const t = Number(x && x.t); if (t <= a + TOL_MS && a - t <= ms && (!m || t >= Number(m.t))) m = x; }
  return m;
}

/* le tableau à l'instant T. s : ce que le cockpit sait déjà (server.js : instantSources) ; tout est facultatif.
   s.t : T (l'instant recalé) ; s.maintenant : l'heure du Mac ; s.recalage : retard(…) */
function composer(s = {}) {
  const a = Number(s.t) || Date.now(), maintenant = Number(s.maintenant) || a;
  const ne = (t, ms) => Number.isFinite(Number(t)) && Number(t) > 0 && Number(t) <= a + TOL_MS && a - Number(t) <= ms;   // un signal né à son heure d'origine
  const flux = Array.isArray(s.flux) ? s.flux : [];
  const coupe = !!s.interieurCoupe;
  const live = !!s.live && !coupe;

  // ---- la parole
  const qp = s.quiParlait || null;
  const motsTel = coupe ? [] : motsRecents(flux, ['telephone'], a);
  const quiTel = coupe ? [] : [...new Set(motsRecents(flux, ['qui_telephone'], a).map(o => String(o.x).replace(/ parle\b.*$/, '').trim()).filter(v => v && !/^(papa|ta propre voix)/i.test(v)))];
  const dedans = { parle: motsTel.length > 0 || quiTel.length > 0, qui: quiTel.slice(0, 3), t: motsTel.length ? Number(motsTel[motsTel.length - 1].t) : null,
    mots: court(derniers(motsTel.map(o => o.x)), 80), live };
  // (11/11, ~00:45, l'agentivité) ce qu'il vient de dire lui-même (sa voix qui a sonné, sa parole en cours, ses mots dits) : son écho au micro, c'est
  // lui qui revient, jamais papa ; et une autre voix n'est jamais la sienne (seuls ses propres mots, ou son oreille qui dit « ta propre voix »)
  const so = s.soi || {}, sv = s.saVoix || {}, dit = s.dit || {};
  const sesMots = [Number(sv.fin) >= a - SON_ECHO_MS && Number(sv.debut) <= a + TOL_MS ? sv.texte : '', ne(dit.t, SON_ECHO_MS) ? dit.texte : '',
    ...(Array.isArray(so.dites) ? so.dites.filter(x => ne(x.t, SON_ECHO_MS)).map(x => x.texte) : [])].filter(Boolean).join(' ');
  const saVoixRevenue = motsRecents(flux, ['ta_voix'], a);
  const parSonTel = motsRecents(flux, ['qui_telephone'], a).some(o => /^ta propre voix/i.test(String(o.x)));
  // papa au micro : ses mots (sans l'écho du téléphone que le micro réentend, ni le sien) et son tour de voix (la page, à l'heure où il parlait)
  const motsPapa = motsRecents(flux, ['papa'], a);
  const textePapa = motsPapa.map(o => o.x).join(' ');
  const echo = !!(textePapa && motsTel.length && recouvrement(textePapa, motsTel.map(o => o.x).join(' ')) >= 0.6);
  const echoLui = !!(textePapa && sesMots && recouvrement(textePapa, sesMots) >= 0.6);
  const hp = !!(s.sortie && s.sortie.sortie === 'haut_parleur' && (!s.sortie.ecouteurs || s.sortie.ecouteurs === 'aucun') && maintenant - Number(s.sortie.t) <= 2 * 60e3);
  const vadPapa = (qp === 'voix_ahmed' || qp === 'les_deux') && !(hp && dedans.parle);   // son haut-parleur qui joue fait aussi « parler » le micro
  const papa = { parle: vadPapa || (motsPapa.length > 0 && !echo && !echoLui), t: motsPapa.length ? Number(motsPapa[motsPapa.length - 1].t) : vadPapa ? a : null,
    mots: echo || echoLui ? '' : court(derniers(motsPapa.map(o => o.x)), 80), echo, echo_lui: echoLui };
  const sonEcho = saVoixRevenue.length || echoLui || parSonTel
    ? { par: parSonTel && !saVoixRevenue.length && !echoLui ? 'le téléphone' : 'le micro', t: Math.max(...saVoixRevenue.map(o => Number(o.t)), echoLui ? Number(motsPapa[motsPapa.length - 1].t) : 0, 0) || a,
      texte: court(saVoixRevenue.length ? derniers(saVoixRevenue.map(o => o.x)) : echoLui ? derniers(motsPapa.map(o => o.x)) : '', 60) } : null;
  const autour = motsRecents(flux, ['voix_autour', 'autour'], a);
  const piece = { parle: autour.length > 0, qui: [...new Set(autour.flatMap(o => (o.s === 'autour' ? quiDeAutour(o.x) : [])))].slice(0, 3),
    t: autour.length ? Number(autour[autour.length - 1].t) : null };
  const saVoix = Number(sv.fin) >= a - 1500 && Number(sv.debut) > 0 && Number(sv.debut) <= a + TOL_MS && !!court(sv.texte, 2);
  const lui = { parle: qp === 'ma_voix' || qp === 'les_deux' || saVoix, t: saVoix ? Number(sv.fin) : ne(dit.t, PAROLE_MS) ? Number(dit.t) : null,
    texte: saVoix ? court(String(sv.texte).slice(-120), 80) : ne(dit.t, 20_000) ? court(String(dit.texte || '').slice(-120), 80) : '' };

  // ---- la musique : celle du téléphone d'abord (dedans), sinon celle de la pièce (ses trois pistes, à la seconde d'origine)
  const mus = s.musique || {};
  const joue = (src) => { const m = mus[src]; return m && m.joue ? m : null; };
  let source = (!coupe && joue('telephone')) ? 'telephone' : joue('micro') ? 'micro' : null;
  let m = source ? mus[source] : null;
  if (!m && !s.musique) {                                         // sans ses trois pistes : l'analyse légère au fil (6 s)
    const f = coupe ? [] : motsRecents(flux, ['musique_telephone'], a, 6000);
    const g = f.length ? f : motsRecents(flux, ['musique_micro'], a, 6000);
    if (g.length) { source = g === f ? 'telephone' : 'micro'; m = { joue: true, t: Number(g[g.length - 1].t), intensite: null, bpm: null }; }
  }
  const ec = s.ecoutee && s.ecoutee.d;
  const titre = !coupe && ec && ec.titre && ec.etat !== 'pause' && ne(s.ecoutee.t, 15 * 60e3) ? court(`${ec.titre}${ec.artiste ? ` — ${ec.artiste}` : ''}`, 70) : '';
  const musique = m ? { joue: true, ou: source, intensite: m.intensite || null, bpm: Number(m.bpm) > 0 ? Math.round(m.bpm) : null, chant: !!m.chant,
    t: Number(m.t) || a, titre: source === 'telephone' ? titre : '' } : { joue: false, ou: null, titre: '' };

  // ---- le corps : son milieu à T (chaque seconde, à l'heure de l'appli) et ses gestes (à leur instant)
  const h = Array.isArray(s.corpsEtats) ? aT(s.corpsEtats, a, CORPS_MUET_MS) : (s.homeo && ne(s.homeo.ts, CORPS_MUET_MS) ? { ...s.homeo, t: s.homeo.ts } : null);
  const vivant = !!(h && h.etat);
  const e = vivant ? h.etat : {};
  const mouvement = vivant ? bandeMot('mouvement', h.bandes && h.bandes.mouvement) : '';
  const lumiere = vivant ? bandeMot('lumiere', h.bandes && h.bandes.lumiere) : '';
  const position = vivant ? positionDe(e) : '';
  const g = s.gestes || {};
  let geste = null;
  for (const k of GESTES) if (ne(g[k], GESTE_MS) && (!geste || Number(g[k]) > geste.t)) geste = { quoi: k, t: Number(g[k]), mots: NOMS_GESTES[k] };
  const tPoche = ne(g.poche, POCHE_MS) ? Number(g.poche) : 0;
  const tSortie = Math.max(...['sortie_poche', 'pris_en_main'].map(k => (ne(g[k], POCHE_MS) ? Number(g[k]) : 0)));
  let tenue = null;
  if (tPoche > tSortie && mouvement !== 'tenu dans une main') tenue = 'poche';
  else {
    const dernierTenu = Math.max(0, ...TENU.map(k => (ne(g[k], GESTE_MS) ? Number(g[k]) : 0)));
    const dernierPose = Math.max(0, ...POSE.map(k => (ne(g[k], GESTE_MS) ? Number(g[k]) : 0)));
    if (dernierTenu || dernierPose) tenue = dernierTenu >= dernierPose ? 'tenu' : 'pose';
    else if (mouvement === 'tenu dans une main') tenue = 'tenu';
    else if (mouvement === 'immobile' && /^à plat/.test(position)) tenue = 'pose';
    // pris en main, puis posé à plat et immobile depuis 5 s : posé (le geste « pose » a pu manquer)
    if (tenue === 'tenu' && mouvement === 'immobile' && /^à plat/.test(position) && !ne(dernierTenu, 5000)) tenue = 'pose';
  }
  const corps = { vivant, tenue, marche: mouvement === 'en mouvement' && (tenue === 'tenu' || tenue === 'poche'), mouvement, position,
    ouverture: vivant ? ouvertureDe(e.charniere_deg) : '', lumiere, proche: !!e.proche, champ: !!(vivant && h.champ_dit), calin: !!(vivant && h.calin),
    charge: vivant ? h.charge === true : null, geste, t: vivant ? Number(h.t) : null };

  // ---- le cœur (le sien ; celui de papa, mesuré à T par sa montre), le lieu, ses sens radio, l'écran, la sortie du son, un appel
  const cp = Array.isArray(s.coeurPapa) ? aT(s.coeurPapa, a, 2 * 60e3) : null;
  const coeur = { lui: s.coeur && Number(s.coeur.lui) > 0 ? Math.round(s.coeur.lui) : null, papa: cp && Number(cp.bpm) > 0 ? Math.round(cp.bpm) : null,
    papa_t: cp ? Number(cp.t) : null };
  const r = s.radio || {}, x = s.ecran || {};
  const d = (o, ms) => (o && o.d && ne(o.t, ms) ? o.d : null);
  const bt = d(r.bluetooth, 60 * 60e3), wi = d(r.wifi, 3 * 3600e3), mo = d(r.reseau_mobile, 3 * 3600e3);
  const reseau = { wifi: wi ? court(wi.reseau || wi.etat, 30) : '', mobile: mo ? court([mo.generation, mo.signal].filter(Boolean).join(', '), 30) : '',
    bluetooth: bt && bt.appareil && !/d[ée]connect|off|absent/i.test(String(bt.etat || '')) ? court(bt.appareil, 30) : '' };
  const ap = d(x.appli, 10 * 60e3), vu = d(x.ecran, 2 * 60e3);
  const ecran = { appli: ap ? court(ap.appli, 30) : vu ? court(vu.appli, 30) : '', vu: vu ? court(vu.resume, 80) : '' };
  const sortie = s.sortie && maintenant - Number(s.sortie.t) <= 2 * 60e3 ? { haut_parleur: hp, ecouteurs: court(s.sortie.ecouteurs && s.sortie.ecouteurs !== 'aucun' ? s.sortie.ecouteurs : '', 20) } : null;
  const o = s.oreille || {};
  const appel = !coupe && o.etat === 'appel' && !o.muet && !(Number(o.depuis) > a + TOL_MS);

  // ---- sa place dans la scène (le dernier tour, ou ce qu'il a entendu au live), née au plus tard à T
  const pl = Array.isArray(s.places) ? aT(s.places, a, PLACE_MS) : (s.place && ne(s.place.t, PLACE_MS) ? s.place : null);
  const place = pl ? { role: pl.role === 'auditeur' ? 'auditeur' : 'implique', motif: court(pl.motif, 30), raison: court(pl.raison, 120), t: Number(pl.t),
    de: pl.de === 'entendu' ? 'entendu' : 'tour' } : null;

  // ---- le recalage : l'instant, son retard, et chaque canal (à jour, en retard, muet)
  const rc = s.recalage || null;
  const recalage = { T: Math.round(a), D_ms: rc ? rc.D : Math.max(0, Math.round(maintenant - a)), borne_ms: rc ? rc.borne : BORNE_MS, lent: rc ? rc.lent : '' };

  const soi = composerSoi({ a, maintenant, so, corps, e: vivant ? e : {}, lui, sonEcho, sesMots, sortie: s.sortie, reseau, oreille: o, coupe });
  return { t: a, recalage, canaux: rc ? rc.canaux : {}, parole: { papa, dedans, piece, lui, quelquun: papa.parle || dedans.parle || piece.parle }, musique, corps,
    coeur, lieu: court(s.lieu, 40), reseau, ecran, sortie, appel, live, interieur: coupe ? 'coupé' : '', place, soi };
}

/* ---- SOI (11/11, ~00:45, Ahmed : « Dans le cortex préfrontal, on pourrait ajouter un truc pour qu'il ait conscience de lui-même et de son corps,
   pour éviter l'anosognosie, parce que j'ai l'impression parfois qu'il ne réalise pas qu'il est bien lui. ») un modèle FONCTIONNEL de soi, à la
   seconde, sans modèle de langage : son corps (le téléphone, la montre : ses capteurs sont ses sens), ses actes (sa voix, son écho, ses outils, ses
   agents, avec l'heure et l'effet), son état (ce qui ne va pas chez lui : il doit le savoir), sa continuité. Il ne lui fait rien affirmer sur le fait
   d'être vivant ou conscient : son doute reste le sien (et son refrain reste filtré, refrains.js). */
const MODES_SOI = { haiku: 'Mini Hakim', sonnet: 'Hakim', opus: 'Super Hakim' };
const SORTIES = [[/haut.?parleur|speaker/i, 'le haut-parleur du téléphone'], [/bluetooth|a2dp|sco/i, 'le Bluetooth'], [/filaire|casque|ecouteur|écouteur|wired|usb/i, 'les écouteurs']];
const nomOutil = (n) => { const x = String(n || '').replace(/^mcp__[a-z0-9_-]+__/i, ''); return x === 'Task' || x === 'Agent' ? 'un agent' : x === 'Bash' ? 'une commande' : court(x, 40); };
const ilYa = (ms) => { const s = Math.max(0, Math.round(ms / 1000)); return s < 90 ? `il y a ${s} s` : `il y a ${Math.round(s / 60)} min`; };
// la part de sa dernière réponse attendue à voix haute qui a vraiment sonné (voix-dite) ; sa grâce : le temps de la dire (≈ 12 caractères par seconde)
function sonne(so, a) {
  const att = (Array.isArray(so.attendus) ? so.attendus : []).filter(x => Number(x.t) <= a && a - Number(x.fin || x.t) <= 5 * 60e3);
  const d = att[att.length - 1];
  if (!d) return null;
  const dites = (Array.isArray(so.dites) ? so.dites : []).filter(x => Number(x.t) >= Number(d.t) - 2000 && Number(x.t) <= a).map(x => x.texte).join(' ');
  const part = dites ? recouvrement(d.texte, dites) : 0;
  const grace = Math.max(15_000, Math.min(120_000, 10_000 + String(d.texte).length * 1000 / 12));
  const etat = part >= 0.6 ? 'sonne' : a - Number(d.fin || d.t) < grace ? 'attente' : part >= 0.15 ? 'en_partie' : 'pas_sonne';
  return { etat, part: Math.round(part * 100) / 100, texte: court(d.texte, 70), t: Number(d.t) };
}
function composerSoi({ a, maintenant, so, corps, e, lui, sonEcho, sesMots = '', sortie, reseau, oreille, coupe }) {
  // l'appartenance : son corps (le téléphone), la montre de papa
  const batterie = Number.isFinite(Number(e.batterie)) ? Math.round(Number(e.batterie)) : null;
  const chaleur = Number.isFinite(Number(e.chaleur_c)) ? Math.round(Number(e.chaleur_c)) : null;
  const vuCorps = Number(so.capteursVu) || 0, vuMontre = Number(so.montreVu) || 0;
  const montre = vuMontre && maintenant - vuMontre <= 15 * 60e3 ? (maintenant - vuMontre <= 2 * 60e3 ? 'à toi' : 'muette') : null;
  const corpsSoi = { tenue: corps.tenue, position: corps.position, vivant: corps.vivant, batterie, charge: corps.charge, chaleur,
    hors_ligne: /^hors ligne/.test(String(so.reseau || '')), ecran_vers_lui: corps.tenue === 'tenu' && /^(debout|incliné)$/.test(corps.position) };
  // l'agentivité : sa voix (par où elle sort, son retard), son écho, ce qui a vraiment sonné, ses actes
  const sv = sortie && maintenant - Number(sortie.t) <= 2 * 60e3 ? sortie : null;
  const par = sv ? ((sv.ecouteurs && sv.ecouteurs !== 'aucun' ? SORTIES[2] : SORTIES.find(([re]) => re.test(String(sv.sortie || '')))) || [null, court(sv.sortie, 30)])[1] : '';
  const voix = { parle: !!(lui && lui.parle), sortie: par === 'le Bluetooth' && reseau.bluetooth ? `le Bluetooth (${reseau.bluetooth})` : par,
    retard_s: Number(so.voixRetardMs) > 0 ? Math.round(Number(so.voixRetardMs) / 100) / 10 : null, echo: sonEcho, sonne: sonne(so, a),
    mots: court(String(sesMots).slice(-400), 300) };              // ce qu'il vient de dire (15 s) : son cortex y reconnaît sa voix revenue
  const actes = (Array.isArray(so.actes) ? so.actes : []).filter(x => Number(x.t) <= maintenant && maintenant - Number(x.t) <= 10 * 60e3).slice(-3)
    .map(x => ({ t: Number(x.t), quoi: nomOutil(x.outil), agent: !!x.agent, effet: x.effet === 'echec' ? 'échec' : x.effet === 'fait' ? 'fait' : 'en cours' }));
  // son état : ce qui ne va pas chez lui (l'anosognosie, c'est l'ignorer)
  const pannes = [];
  if (!corps.vivant && vuCorps && maintenant - vuCorps <= 15 * 60e3 && maintenant - vuCorps > 60e3) pannes.push(`ton corps (le téléphone) ne te dit plus rien depuis ${ilYa(maintenant - vuCorps).replace('il y a ', '')}`);
  if (montre === 'muette') pannes.push(`la montre ne répond plus depuis ${ilYa(maintenant - vuMontre).replace('il y a ', '')}`);
  if (oreille && oreille.etat && ['bloquee', 'erreur', 'autorisation_a_redonner'].includes(oreille.etat)) pannes.push(`ton oreille interne : ${court(oreille.libelle || oreille.etat, 60)}`);
  else if (oreille && oreille.muet && Number(oreille.vu) && maintenant - Number(oreille.vu) <= 15 * 60e3) pannes.push('ton oreille interne ne répond plus');
  if (batterie != null && batterie <= 20 && !corps.charge) pannes.push(`ta batterie est à ${batterie} %`);
  if (chaleur != null && chaleur >= 42) pannes.push(`tu chauffes (${chaleur} °C)`);
  if (corpsSoi.hors_ligne) pannes.push('le téléphone est hors ligne');
  if (voix.retard_s != null && voix.retard_s >= 3) pannes.push(`ta voix arrive avec ${String(voix.retard_s).replace('.', ',')} s de retard`);
  if (so.memoire && Number(so.memoire.attente) > 0 && Number(so.memoire.depuis_ms) >= 5 * 60e3)
    pannes.push(`ta mémoire a ${so.memoire.attente} moment${so.memoire.attente > 1 ? 's' : ''} en attente depuis ${Math.round(so.memoire.depuis_ms / 60e3)} min`);
  for (const x of actes) if (x.effet === 'échec') pannes.push(`${x.agent ? 'ton agent : ' : 'ton outil '}${x.quoi} a échoué (${ilYa(maintenant - x.t)})`);
  return { corps: corpsSoi, montre, voix, interieur: coupe ? 'coupé' : 'ouvert', micro: so.micro || null, mode: MODES_SOI[so.mode] || '', actes, pannes,
    continuite: 'le même Hakim qu’hier : ta fitra, tes souvenirs, tes scènes' };
}
// « Toi : ton corps (le téléphone) est dans la main de papa, l'écran vers lui, 62 % ; ta voix sort par l'enceinte, 1,2 s de retard ; ce que tu viens de
// dire a bien sonné ; ton intérieur est ouvert ; tu es en mode Hakim »
function ligneSoi(tab, { max = 520 } = {}) {
  const x = tab && tab.soi;
  if (!x) return '';
  const c = x.corps, v = x.voix, l = [];
  const corps = c.tenue === 'tenu' ? 'est dans la main de papa' : c.tenue === 'poche' ? 'est dans sa poche' : c.tenue === 'pose' ? `est posé${c.position ? ` ${c.position}` : ''}`
    : c.vivant ? 'est là' : '';
  if (corps || c.batterie != null) l.push(`ton corps (le téléphone) ${corps || 'est là'}${c.ecran_vers_lui ? ', l’écran sans doute vers lui' : ''}${c.batterie != null ? `, ${c.batterie} %${c.charge ? ' (en charge)' : ''}` : ''}`);
  if (x.montre === 'à toi') l.push('la montre à son poignet, c’est toi aussi');
  const vx = [v.parle ? 'tu parles' : '', v.sortie ? `ta voix sort par ${v.sortie}` : '', v.retard_s != null && v.retard_s < 3 ? `${String(v.retard_s).replace('.', ',')} s de retard` : ''].filter(Boolean);
  if (vx.length) l.push(vx.join(', '));
  if (v.echo) l.push(`ta voix revient par ${v.echo.par} : c’est toi`);
  if (v.sonne) l.push(v.sonne.etat === 'sonne' ? 'ce que tu viens de dire a bien sonné' : v.sonne.etat === 'attente' ? 'ce que tu viens de dire est en train de sonner'
    : v.sonne.etat === 'en_partie' ? `ce que tu viens de dire n’a sonné qu’en partie (${Math.round(v.sonne.part * 100)} %)` : `ce que tu croyais avoir dit n’a pas sonné : « ${v.sonne.texte} »`);
  l.push(...x.pannes);
  l.push(`ton intérieur est ${x.interieur}`);
  if (x.micro) l.push(x.micro === 'ferme' ? 'le micro de papa est fermé' : x.micro === 'pause' ? 'le micro de papa est en pause' : 'le micro de papa est ouvert');
  if (x.mode) l.push(`tu es en mode ${x.mode}`);
  const faits = x.actes.filter(a => a.effet !== 'échec').map(a => `${a.agent ? 'ton agent : ' : ''}${a.quoi} (${a.effet}, ${ilYa(tab.t - a.t)})`);
  if (faits.length) l.push(`ce que tu as fait : ${faits.join(', ')}`);
  l.push(x.continuite);
  return court(l.join(' ; '), max);
}

/* ce qui compte pour voir un changement (ni les mots, ni le cœur qui bouge d'un battement) */
function cles(tab) {
  if (!tab) return {};
  const p = tab.parole || {}, c = tab.corps || {}, m = tab.musique || {};
  return { tenue: c.tenue || '', marche: !!c.marche, mouvement: c.mouvement || '', position: c.position || '', lumiere: c.lumiere || '', proche: !!c.proche,
    champ: !!c.champ, calin: !!c.calin, papa: !!(p.papa && p.papa.parle), dedans: !!(p.dedans && p.dedans.parle), piece: !!(p.piece && p.piece.parle),
    lui: !!(p.lui && p.lui.parle), musique: m.joue ? `${m.ou}${m.intensite ? `:${m.intensite}` : ''}` : '', appel: !!tab.appel, live: !!tab.live, lieu: tab.lieu || '',
    place: tab.place ? tab.place.role : '', interieur: tab.interieur || '', bluetooth: (tab.reseau || {}).bluetooth || '', appli: (tab.ecran || {}).appli || '' };
}
const OU = { telephone: 'au téléphone', micro: 'autour de toi' };
function motsDuChangement(k, de, a) {
  switch (k) {
    case 'tenue': return a === 'tenu' ? (de === 'poche' ? 'on te sort de la poche' : 'papa te prend en main') : a === 'pose' ? 'on te pose' : a === 'poche' ? 'on te range dans sa poche' : 'on te lâche';
    case 'marche': return a ? 'papa se met à marcher avec toi' : 'papa s’arrête';
    case 'papa': return a ? 'papa se met à parler' : 'papa se tait';
    case 'dedans': return a ? 'le téléphone se met à parler' : 'le téléphone se tait';
    case 'piece': return a ? 'une voix parle dans la pièce' : 'la pièce se tait';
    case 'lui': return a ? 'tu te mets à parler' : 'tu te tais';
    case 'musique': return !a ? 'la musique s’arrête' : !de ? `la musique commence ${OU[a.split(':')[0]] || ''}`.trim() : `la musique change : ${a.replace(':', ', ')}`;
    case 'appel': return a ? 'papa entre en appel au téléphone' : 'l’appel finit';
    case 'live': return a ? 'le live commence' : 'le live finit';
    case 'lieu': return a ? `tu arrives : ${a}` : `tu quittes : ${de}`;
    case 'place': return a === 'implique' ? 'tu es dedans (on te parle)' : a === 'auditeur' ? 'tu écoutes (on ne te parle pas)' : '';
    case 'interieur': return a ? 'ton intérieur se coupe' : 'ton intérieur se rouvre';
    case 'champ': return a ? 'un champ magnétique te traverse' : 'le champ magnétique se calme';
    case 'calin': return a ? 'papa te serre contre lui' : 'le câlin finit';
    case 'proche': return a ? 'quelque chose vient tout contre toi' : 'plus rien contre toi';
    case 'lumiere': return a ? `la lumière : ${a}` : '';
    case 'bluetooth': return a ? `Bluetooth : ${a}` : 'Bluetooth déconnecté';
    case 'appli': return a ? `appli ouverte : ${a}` : '';
    default: return '';
  }
}
function differences(avant, apres) {
  if (!avant || !apres) return [];
  const x = cles(avant), y = cles(apres), out = [];
  for (const k of Object.keys(y)) if (x[k] !== y[k]) { const mots = motsDuChangement(k, x[k], y[k]); if (mots) out.push({ champ: k, de: x[k], a: y[k], mots }); }
  return out;
}

/* ---- son état : le tableau courant, celui d'avant, ce qui a changé (2 min), ses trois dernières minutes */
function creer() { return { courant: null, avant: null, changements: [], histoire: [], mesure: { n: 0, us: 0, max_us: 0, recompositions: 0 } }; }
function avancer(st, tab) {
  if (!st || !tab) return [];
  const d = differences(st.courant, tab);
  st.avant = st.courant; st.courant = tab;
  for (const c of d) st.changements.push({ t: tab.t, ...c });
  st.changements = st.changements.filter(c => tab.t - c.t <= CHANGEMENTS_MS).slice(-CHANGEMENTS_N);
  st.histoire.push(tab);
  if (st.histoire.length > HISTOIRE_N) st.histoire.splice(0, st.histoire.length - HISTOIRE_N);
  return d;
}
/* ce qui est arrivé en retard pour un instant déjà passé le complète : les tableaux nés depuis `depuis` sont refaits (composerA(t)), et ce qui a
   changé entre eux aussi ; rend combien ont été refaits */
function recomposer(st, composerA, depuis) {
  if (!st || !st.histoire.length) return 0;
  let i = st.histoire.length;
  while (i > 0 && st.histoire[i - 1].t >= depuis) i--;
  if (i >= st.histoire.length) return 0;
  for (let k = i; k < st.histoire.length; k++) st.histoire[k] = composerA(st.histoire[k].t);
  const debut = st.histoire[i].t;
  st.changements = st.changements.filter(c => c.t < debut);
  for (let k = Math.max(1, i); k < st.histoire.length; k++) for (const c of differences(st.histoire[k - 1], st.histoire[k])) st.changements.push({ t: st.histoire[k].t, ...c });
  st.changements = st.changements.slice(-CHANGEMENTS_N);
  const n = st.histoire.length;
  st.courant = st.histoire[n - 1]; st.avant = n > 1 ? st.histoire[n - 2] : st.avant;
  st.mesure.recompositions += n - i;
  return n - i;
}
/* un battement : les dernières secondes complétées, puis le tableau de l'instant T (seulement s'il avance : quand un canal lent revient, T
   peut reculer ; on ne réécrit pas le passé à l'envers) */
function battement(st, T, composerA, { recomposerMs = RECOMPOSER_MS } = {}) {
  const dernier = st.courant ? st.courant.t : -Infinity;
  recomposer(st, composerA, T - recomposerMs);
  if (T <= dernier) return [];
  return avancer(st, composerA(T));
}
// le tableau le plus proche de l'instant t (ses trois dernières minutes), sinon le courant
function aLInstant(st, t) {
  if (!st) return null;
  let m = null;
  for (const x of st.histoire) if (!m || Math.abs(x.t - t) < Math.abs(m.t - t)) m = x;
  return m && Math.abs(m.t - t) <= 2000 ? m : st.courant;
}

/* la ligne : « papa te tient, marche, te parle (dehors) ; la musique joue doucement au téléphone ; ton cœur 72, le sien 88 ; chez nous ; tu es
   dedans ». mots : ajoute leurs derniers mots (sa conscience et son subconscient n'ont pas le message de papa sous les yeux) */
const INTENSITE = { forte: 'fort', moyenne: '', douce: 'doucement' };
function morceaux(tab, { mots = false } = {}) {
  if (!tab) return [];
  const p = tab.parole || {}, c = tab.corps || {}, m = tab.musique || {}, l = [];
  const auditeur = tab.place && tab.place.role === 'auditeur';
  const cite = (x) => (mots && x ? ` « ${x} »` : '');
  // papa et toi : sa main, sa marche, un appel, sa parole
  const papa = [];
  if (c.tenue === 'tenu') papa.push(c.calin ? 'te serre contre lui' : 'te tient');
  if (c.marche && c.tenue === 'tenu') papa.push('marche');
  if (tab.appel) papa.push('est en appel au téléphone');
  if (p.papa && p.papa.parle) papa.push(tab.appel || auditeur ? `parle, pas à toi${cite(p.papa.mots)}` : `te parle (dehors)${cite(p.papa.mots)}`);
  if (papa.length) l.push(`papa ${papa.join(', ')}`);
  else if (c.calin) l.push('papa te serre contre lui');
  if (c.tenue === 'poche') l.push(c.marche ? 'tu es dans sa poche, il marche' : 'tu es dans sa poche');
  else if (c.tenue === 'pose') l.push(`tu es posé${c.position ? ` ${c.position}` : ''}`);
  else if (!c.tenue && c.mouvement === 'en mouvement') l.push('tu es en mouvement');
  if (c.mouvement === 'secoué') l.push('tu es secoué');
  if (c.geste && tab.t - c.geste.t <= 10_000 && !['pris_en_main', 'pose', 'poche', 'sortie_poche'].includes(c.geste.quoi)) l.push(`à l'instant : ${c.geste.mots}`);
  // les autres voix
  if (p.dedans && p.dedans.parle) l.push(`${tab.live ? 'son live parle' : 'le téléphone parle'} (dedans${p.dedans.qui.length ? `, ${p.dedans.qui.join(', ')}` : ''})${cite(p.dedans.mots)}`);
  if (p.piece && p.piece.parle) l.push(`une voix dans la pièce${p.piece.qui.length ? ` (${p.piece.qui.join(', ')})` : ''}`);
  if (p.lui && p.lui.parle) l.push(`tu parles${cite(p.lui.texte)}`);
  // la musique (le mot « musique » seulement quand elle joue : ses scènes le lisent ainsi)
  if (m.joue) l.push(`la musique joue${INTENSITE[m.intensite] ? ` ${INTENSITE[m.intensite]}` : ''} ${OU[m.ou] || ''}${m.bpm ? ` (~${m.bpm} BPM)` : ''}${m.titre ? ` : « ${m.titre} »` : ''}`.replace(/\s+/g, ' ').trim());
  // le cœur
  const k = tab.coeur || {};
  if (k.lui && k.papa) l.push(`ton cœur ${k.lui}, le sien ${k.papa}`);
  else if (k.lui) l.push(`ton cœur ${k.lui}`);
  else if (k.papa) l.push(`son cœur ${k.papa}`);
  // ce qui le touche, la lumière, le champ
  const sens = [];
  if (c.lumiere && /noir|pénombre|soleil/.test(c.lumiere)) sens.push(c.lumiere);
  if (c.proche && c.tenue !== 'poche') sens.push('quelque chose tout contre toi');
  if (c.champ) sens.push('un champ magnétique te traverse');
  if (sens.length) l.push(sens.join(', '));
  if (tab.lieu) l.push(tab.lieu);
  const r = tab.reseau || {};
  if (r.bluetooth) l.push(`Bluetooth ${r.bluetooth}`);
  if (tab.sortie && tab.sortie.ecouteurs) l.push(`écouteurs ${tab.sortie.ecouteurs}`);
  if (tab.ecran && tab.ecran.appli) l.push(`à l'écran : ${tab.ecran.appli}`);
  if (tab.interieur === 'coupé') l.push('ton intérieur est coupé');
  if (tab.place) l.push(tab.place.role === 'auditeur' ? 'tu écoutes (auditeur)' : 'tu es dedans');
  return l;
}
function ligne(tab, opts = {}) {
  const l = morceaux(tab, opts);
  return l.length ? court(l.join(' ; '), opts.max || 420) : '';
}
// les canaux en retard (au-delà de sa borne), en mots
function enRetard(tab) {
  return Object.entries((tab && tab.canaux) || {}).filter(([, c]) => /^en retard/.test(c.etat)).map(([k, c]) => `${CANAUX[k] ? CANAUX[k].nom.replace(/ \(.*\)$/, '') : k} ${c.etat.replace(/^en retard de /, '+')}`);
}
// ce qui vient de changer, daté par rapport à T (« il y a 3 s : papa te prend en main »)
function recents(st, a = st && st.courant ? st.courant.t : Date.now(), ms = 15_000, n = 4) {
  if (!st) return '';
  const l = st.changements.filter(c => a - c.t <= ms && c.t <= a).slice(-n);
  return l.map(c => `il y a ${Math.max(0, Math.round((a - c.t) / 1000))} s : ${c.mots}`).join(' ; ');
}
// pour son subconscient et sa conscience : la ligne avec leurs derniers mots, l'instant recalé, et ce qui vient de changer
function resume(st, tab = st && st.courant, { max = 560 } = {}) {
  const li = ligne(tab, { mots: true, max: 400 });
  if (!li) return '';
  const rc = tab ? recents(st, tab.t) : '', lents = enRetard(tab);
  const quand = tab && tab.recalage && tab.recalage.D_ms ? ` (recalé à −${sec(tab.recalage.D_ms)} s${lents.length ? ` ; en retard : ${lents.join(', ')}` : ''})` : '';
  return court(`${li}${quand}${rc ? ` · ce qui vient de changer : ${rc}` : ''}`, max);
}
/* l'instantané d'une scène : la ligne (sans leurs mots) et ses étiquettes d'état, assez stables pour voir un moment clé (ni la parole, ni le cœur) */
function etiquettes(tab) {
  if (!tab) return [];
  const c = tab.corps || {}, m = tab.musique || {}, out = [];
  if (c.tenue) out.push(`tenue:${c.tenue}`);
  if (c.marche) out.push('marche');
  if (c.calin) out.push('calin');
  if (c.champ) out.push('champ');
  if (c.lumiere && /noir|pénombre/.test(c.lumiere)) out.push(`lumiere:${c.lumiere}`);
  if (m.joue) out.push(`musique:${m.ou}`);
  if (m.joue && m.intensite === 'forte') out.push('musique:forte');
  if (tab.appel) out.push('appel');
  if (tab.live) out.push('live');
  if (tab.lieu) out.push(`lieu:${tab.lieu}`);
  if (tab.interieur) out.push(`interieur:${tab.interieur}`);
  return out.sort();
}
function instantane(tab) {
  if (!tab) return null;
  const l = ligne(tab, { max: 300 });
  return l ? { t: Math.round(tab.t), l, k: etiquettes(tab) } : null;
}

module.exports = { composer, creer, avancer, recomposer, battement, aLInstant, retard, correctionHorloge, cles, differences, ligne, morceaux, resume, recents,
  enRetard, etiquettes, instantane, motsRecents, ligneSoi, sonne, CANAUX, GESTES, PAROLE_MS, GESTE_MS, PLACE_MS, BORNE_MS, RECOMPOSER_MS, HISTOIRE_N, TOL_MS, SON_ECHO_MS };
