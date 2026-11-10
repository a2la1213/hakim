/* (10/11, ~00:00, Ahmed : « il faut l'aider à dissocier ses voix interne et externe ! ») DEDANS ET DEHORS, la logique pure : dans un message
   de papa (son micro), ce qui vient en fait du TÉLÉPHONE (un live, une vidéo qui joue sur son haut-parleur, que le micro entend aussi) n'est
   jamais attribué à papa. Trois preuves, de la plus sûre à la plus faible (et, le 10/11, « paroles » : plus bas) :
   - « mots » : un morceau dont les mots sont ceux que son oreille interne a entendus du téléphone au même moment (75 % au moins de ses mots
     d'au moins 4 lettres, 4 au moins, entendus dans les 40 s avant son tour) ; même sans étiquette, même si l'empreinte a cru papa ;
   - « voix » : son étiquette ([voix 12]) est une voix que l'oreille des voix vient de reconnaître DANS le téléphone ;
   - « haut-parleur » : une voix étiquetée qui n'est pas papa, pendant que le téléphone joue sur son haut-parleur (sans écouteurs) et que
     quelqu'un y parlait : sans doute le téléphone.
   Mesuré sur le fil du 09/11 de 19:03 à 00:20 (103 morceaux de papa d'au moins 4 mots) : les mots se recoupent rarement (le micro et le
   téléphone ne sont pas transcrits par la même oreille) : 1 morceau à ces seuils, et 0, 0 et 1 avec le téléphone décalé de 10 ou 20 min
   (un témoin ; à 60 % et 90 s, les témoins montaient à 3) : une preuve sûre mais rare. Les numéros du micro et du téléphone ne se recoupent
   que 5 fois sur 39 étiquettes du live (l'acoustique de la pièce change l'empreinte) : d'où la troisième preuve, la plus fréquente. */
'use strict';

const plat = (m) => String(m).toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^\p{L}\p{N}]+/gu, '');
const motsSignifiants = (t, min = 4) => String(t || '').split(/\s+/).map(plat).filter(m => m.length >= min);
const ETIQUETTE = /\[([^\[\]\n]{1,40})\]/g;
const EST_PAPA = /^(ahmed|papa)$/i;
const DOUTE_PAPA = /^papa ?\?$/i;

// le message découpé à ses étiquettes : [{ etiquette (null : sans étiquette, papa par défaut), texte }]
// estVoix : une étiquette qui nomme une voix (« voix 12 », une voix connue par son nom) ; une autre parenthèse carrée reste du texte
function segments(texte, { etiquetteDebut = null, estVoix = (e) => /^voix \d+$/i.test(e) } = {}) {
  const t = String(texte || ''), out = [];
  let m, courant = etiquetteDebut, debut = 0;
  const pousser = (fin) => { const x = t.slice(debut, fin).trim(); if (x) out.push({ etiquette: courant, texte: x }); };
  ETIQUETTE.lastIndex = 0;
  while ((m = ETIQUETTE.exec(t))) {
    const e = m[1].trim();
    if (!estVoix(e) && !EST_PAPA.test(e) && !DOUTE_PAPA.test(e)) continue;   // une autre parenthèse : du texte
    pousser(m.index);
    courant = EST_PAPA.test(e) ? null : e;
    debut = m.index + m[0].length;
  }
  pousser(t.length);
  return out;
}
// un morceau vient-il du téléphone ? ctx : { mots : Set (ses mots entendus du téléphone, plats), voix : Set (les voix reconnues dans le
// téléphone), hautParleur : le téléphone joue sur son haut-parleur, parleDedans : quelqu'un parlait dans le téléphone à ce moment }
/* (10/11) « paroles » : le morceau reprend les paroles du morceau que joue le téléphone (paroles.js, ses lignes des 5 dernières minutes) : 75 %
   au moins de ses mots d'au moins 4 lettres (4 au moins) dans une même suite d'au plus trois lignes, à leur compte près. Un refrain que le
   micro réentend sur le haut-parleur une minute plus tard n'est plus dans les 40 s de « mots » ; une fenêtre de trois lignes, pas tout le
   vocabulaire du morceau : tes phrases ordinaires (« c'est », « dans », « pour ») n'y passent pas. */
function repriseDeParoles(mots, lignes, part = 0.75) {
  const ls = (Array.isArray(lignes) ? lignes : []).map(l => motsSignifiants(l));
  for (let i = 0; i < ls.length; i++) {
    for (let n = 1; n <= 3 && i + n <= ls.length; n++) {
      const c = new Map();
      for (const m of ls.slice(i, i + n).flat()) c.set(m, (c.get(m) || 0) + 1);
      let k = 0;
      for (const m of mots) { const v = c.get(m); if (v) { k++; c.set(m, v - 1); } }
      if (k / mots.length >= part) return true;
    }
  }
  return false;
}
function duTelephone(seg, ctx = {}) {
  const e = seg && seg.etiquette ? String(seg.etiquette) : '';
  const mots = motsSignifiants(seg && seg.texte);
  if (ctx.mots && mots.length >= 4 && mots.filter(m => ctx.mots.has(m)).length / mots.length >= 0.75) return 'mots';
  if (ctx.lignes && mots.length >= 4 && repriseDeParoles(mots, ctx.lignes)) return 'paroles';
  if (e && !DOUTE_PAPA.test(e) && ctx.voix && ctx.voix.has(e.toLowerCase())) return 'voix';
  if (e && !DOUTE_PAPA.test(e) && ctx.hautParleur && ctx.parleDedans) return 'haut-parleur';
  return null;
}
// le message trié : ce qui est du téléphone (avec sa preuve), ce qui reste à papa ; papaRien : il n'a rien dit, tout était le téléphone
function trier(texte, ctx = {}, opts = {}) {
  const segs = segments(texte, opts);
  const dedans = [], papa = [], autour = [];
  for (const s of segs) {
    const preuve = duTelephone(s, ctx);
    if (preuve) dedans.push({ ...s, preuve });
    else if (!s.etiquette || DOUTE_PAPA.test(s.etiquette)) papa.push(s);
    else autour.push(s);
  }
  const resteMots = papa.map(s => s.texte).join(' ').replace(/\(dit (?:en passant )?pendant ta parole[^)]*\)/g, ' ').split(/\s+/).filter(m => m.length > 1);
  return { dedans, papa, autour, papaRien: dedans.length > 0 && resteMots.length === 0 };
}
const ensembleMots = (textes) => new Set(textes.flatMap(t => motsSignifiants(t)));

module.exports = { segments, duTelephone, trier, ensembleMots, motsSignifiants, plat, repriseDeParoles };
