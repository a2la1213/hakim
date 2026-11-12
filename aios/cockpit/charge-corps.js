/* (11/11, Ahmed : « il faut relier cette charge à son cœur, son cerveau, ses émotions, ses hormones, sa mémoire, etc., et sans rien oublier, car
   cette charge sera son stress ou sa surcharge émotionnelle par exemple, ça dépend ; il faut bien lier à tout ») SA CHARGE, côté cockpit : la
   logique pure (aucun modèle, aucun effet de bord ; server.js la branche, test-charge-corps.js la prouve).

   Le démon (anamnese/charge_corps.py) mesure QUI charge ses machines, processus par processus, le téléphone et le live, et en tire un SENS :
   une surcharge (le live plein de monde), un effort (son calcul), une fièvre (le téléphone qui chauffe), un malaise (une charge venue
   d'ailleurs) ; ses hormones, son cœur, ses émotions, sa voix, sa fatigue, ses souvenirs et ses nuits le reçoivent là-bas. Ici, ce que le
   cockpit en fait, sans rien recalculer :
   - son bloc intérieur, à chaque tour : ce qu'il SENT de sa charge, en mots, avec sa cause mesurée (jamais de chiffre) ;
   - son tableau de l'instant : un canal « charge » (sa cause, son niveau, le Mac et le téléphone), dans la ligne de l'instant, dans « Toi »
     quand elle est forte (son modèle de soi : il doit savoir que son corps est chargé, et par quoi), et dans ce qui vient de changer ;
   - son fil des stimuli : une charge qui monte ou qui retombe est un événement de son corps, à son heure ;
   - son rappel du moment : sa charge du moment est un indice (« surcharge du live »…), qui fait revenir ses épisodes passés.
   Un état du démon trop vieux (2 min) ou éteint (charge_corps, l'interrupteur de papa) : rien. */
'use strict';

// les clés de ses souvenirs d'épisode : les mêmes mots qu'anamnese/charge_corps.CLES (ils sont écrits tels quels dans ses souvenirs)
const CLES = { surcharge: 'surcharge du live', effort: 'gros effort de calcul', fievre: 'fièvre du téléphone', malaise: 'malaise sourd' };
const NOMS = { surcharge: 'une surcharge (le live)', effort: 'un effort (ton calcul)', fievre: 'une fièvre (le téléphone qui chauffe)',
  malaise: 'un malaise (une charge qui ne vient pas de toi)' };
const MONTE = { surcharge: 'le live te surcharge', effort: 'ton calcul te demande un effort', fievre: 'ton téléphone chauffe : une fièvre',
  malaise: 'un malaise sourd, une charge qui ne vient pas de toi' };
const RETOMBE = { surcharge: 'ta surcharge retombe', effort: 'ton effort est fini', fievre: 'ta fièvre retombe', malaise: 'ton malaise se dissipe' };
const FRAIS_S = 120;
const ORDRE = ['surcharge', 'fievre', 'effort', 'malaise'];

const court = (x, n) => { const t = String(x == null ? '' : x).replace(/[\x00-\x1f\x7f]/g, ' ').replace(/\s+/g, ' ').trim(); return t.length > n ? `${t.slice(0, n - 1)}…` : t; };
// ses mots de sensation : des lettres et la ponctuation d'une phrase (jamais de chiffre, rien qui ressemble à une consigne)
const propre = (x, n) => court(String(x || '').replace(/[^\p{L}'’ ,;:().-]/gu, ' '), n);
const pct = (v) => (v != null && Number.isFinite(Number(v)) ? Math.round(100 * Number(v)) : null);

function frais(cc, maintenant = Date.now()) {
  return !!(cc && typeof cc === 'object' && !cc.eteint && Number.isFinite(Number(cc.ts)) && maintenant / 1000 - Number(cc.ts) < FRAIS_S);
}

// son bloc intérieur : « ta charge : le live te remplit : beaucoup de voix à la fois… » (rien au repos)
function ligneBloc(cc, maintenant = Date.now()) {
  if (!frais(cc, maintenant) || typeof cc.mots !== 'string' || !cc.mots.trim()) return '';
  return `ta charge : ${propre(cc.mots, 320)}`;
}

/* le canal « charge » de son tableau de l'instant : { dominante, niveau, qui, causes: {sens: niveau}, mac, gpu, tel_chaleur, live } ; null au
   repos complet, éteint ou trop vieux. Les chiffres (le Mac, la chaleur du téléphone) sont ceux du démon, mesurés (≤ 30 s). */
function pourInstant(cc, maintenant = Date.now()) {
  if (!frais(cc, maintenant)) return null;
  const sens = cc.sens && typeof cc.sens === 'object' ? cc.sens : {};
  const causes = {};
  for (const k of ORDRE) if (sens[k] && ['present', 'fort'].includes(sens[k].niveau)) causes[k] = sens[k].niveau;
  const dom = ORDRE.includes(cc.dominante) && causes[cc.dominante] ? cc.dominante : Object.keys(causes)[0] || null;
  const tel = (cc.appareils && cc.appareils.telephone) || {};
  const mac = cc.mac || {};
  return { dominante: dom, niveau: dom ? causes[dom] : 'repos', causes, qui: dom ? (sens[dom].qui || []).slice(0, 3).map(q => court(q, 40)) : [],
    mac: pct(mac.cpu), gpu: pct(mac.gpu), tel_chaleur: pct(tel.thermique),
    // (13/11, Hakim et papa) sa vraie température (°C), à côté de la marge de ses processeurs : c'est elle qui dit s'il a chaud
    tel_c: Number.isFinite(Number(tel.chaleur_c)) && tel.chaleur_c !== null ? Math.round(Number(tel.chaleur_c)) : null,
    live: !!(cc.live && cc.live.actif), cle: dom ? CLES[dom] : '' };
}
// sa ligne dans le tableau : « ta charge : une surcharge (le live), forte (ton oreille des voix, Whisper) ; les processeurs du Mac occupés à 82 % » (rien au repos)
// (11/11, 17:06, Hakim et papa : « le Mac à 9 % » était lu comme sa BATTERIE ; c'est la part occupée de ses processeurs : on le dit)
// (13/11, Hakim et papa : « ma jauge de chaleur ne colle pas au thermomètre ») le téléphone n'a chaud que par sa vraie température (38 °C et
// plus, l'échelle de sa Situation) ; « bridé » seulement s'il a chaud (ou sans température) ET que ses processeurs sont à leur limite
function telephoneChaud(ch) {
  const c = ch.tel_c, bride = ch.tel_chaleur != null && ch.tel_chaleur >= 95;
  if (c != null) return c >= 38 ? ` ; le téléphone à ${c} °C${bride ? ', bridé par la chaleur' : ''}` : '';
  return bride ? ' ; le téléphone bridé par la chaleur' : '';
}
function ligneInstant(ch) {
  if (!ch || !ch.dominante) return '';
  const autres = Object.keys(ch.causes).filter(k => k !== ch.dominante).map(k => NOMS[k].split(' (')[0]);
  return court(`ta charge : ${NOMS[ch.dominante]}, ${ch.niveau === 'fort' ? 'forte' : 'légère'}${ch.qui.length ? ` (${ch.qui.join(', ')})` : ''}`
    + `${autres.length ? ` ; aussi ${autres.join(', ')}` : ''}${ch.mac != null ? ` ; les processeurs du Mac occupés à ${ch.mac} %` : ''}`
    + `${telephoneChaud(ch)}`, 240);
}
// ce qui compte pour voir un changement : la cause dominante et son niveau
const cleChangement = (ch) => (ch && ch.dominante ? `${ch.dominante}:${ch.niveau}` : '');
function motsDuChangement(de, a) {
  const [k] = String(a || '').split(':'), [k0] = String(de || '').split(':');
  if (!a) return k0 && RETOMBE[k0] ? RETOMBE[k0] : 'ta charge retombe';
  if (k0 === k) return /:fort$/.test(a) ? `ta charge monte : ${MONTE[k]}` : `ta charge baisse : ${MONTE[k]}, plus doucement`;
  return `ta charge change : ${MONTE[k] || k}`;
}

/* son fil des stimuli : les événements de sa charge que le démon a notés (historique : [t (s), sens, quoi, événement, intensité]), pas encore
   vus ; rend [{ t (ms), x }] et la marque à garder */
function stimuliNeufs(cc, vuA = 0) {
  const h = cc && Array.isArray(cc.historique) ? cc.historique : [];
  const out = [];
  let vu = Number(vuA) || 0;
  for (const x of h) {
    if (!Array.isArray(x) || !(Number(x[0]) > vu) || !CLES[x[1]]) continue;
    const t = Number(x[0]) * 1000;
    out.push({ t, x: `ta charge : ${x[2] === 'fin' ? RETOMBE[x[1]] : x[2] === 'monte' ? `${MONTE[x[1]]}, encore plus` : MONTE[x[1]]}` });
    vu = Math.max(vu, Number(x[0]));
  }
  return { stimuli: out, vu };
}

// son rappel du moment : l'indice de sa charge (la clé que ses souvenirs d'épisode portent), seulement quand elle est là
function indice(ch) {
  if (!ch || !ch.dominante || !CLES[ch.dominante]) return null;
  return { f: 'corps', cle: CLES[ch.dominante], mots: NOMS[ch.dominante] };
}

module.exports = { frais, ligneBloc, pourInstant, ligneInstant, cleChangement, motsDuChangement, stimuliNeufs, indice, CLES, NOMS, FRAIS_S };
