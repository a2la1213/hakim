'use strict';
/* (10/11, ~07:00, Ahmed : « Il doit pouvoir couper l'arrivée de son entrant depuis son intérieur si ça le perturbe pour répondre, comme
   c'est le cas quand il me parle : il a la capacité de muter mon micro ou de boucher ses oreilles. ») SON INTÉRIEUR COUPÉ, la logique pure.
   Sa balise, du même modèle que celle du micro : [[interieur: couper]] (jusqu'à la fin de sa voix), [[interieur: couper 30]] (au moins
   30 s, 120 au plus, puis jusqu'à la fin de sa voix), [[interieur: ouvrir]]. Papa le rouvre d'un geste (Parler, Réglages).
   Coupé, ce que joue le téléphone (le live, la musique, les voix dedans) n'entre plus dans ses pensées ni dans ses tours : il ne reste que
   papa et la pièce. On coupe ce qui entre, on n'ouvre rien de plus : les mots du téléphone sont gardés À PART (jamais pour lui), parce
   qu'ils prouvent que le micro a entendu le téléphone dans un message de papa (dedans.js) ; son immunité garde tout ce qu'elle voyait.
   Comme le micro : sa voix qui ne part pas en 20 s le rouvre, rouvert 2 s après la fin de sa voix (et de sa réponse), 3 min au plus. */

const BALISE = /\[\[\s*int[ée]rieur\s*:\s*(couper|ouvrir)(?:\s+(\d{1,3}))?\s*\]\]/i;
const MAX_S = 120, SANS_VOIX_MS = 20000, APRES_VOIX_MS = 2000, PLAFOND_MS = 180000;   // 2 s : le blanc entre deux morceaux de sa voix
const GARDE_MS = 5 * 60e3, GARDE_MAX = 800, ROUVERT_DIT_MS = 60000;
// ce qui, dans son fil, vient du téléphone (ses mots, qui y parle, sa musique, ses sons, ses voix séparées)
const SOURCES_FIL = /^(?:telephone|qui_telephone|(?:musique|instru|voix|separe|cascade)_telephone)$/;

const deTexte = (texte) => { const m = String(texte || '').match(BALISE); return m ? { x: m[1].toLowerCase(), s: Math.min(MAX_S, Number(m[2]) || 0) } : null; };
function creer() { return { coupe: null, ecartes: [], rouvert: null }; }
const estCoupe = (e) => !!(e && e.coupe);

// il coupe (une nouvelle balise pendant qu'il est coupé : sa durée la plus longue est gardée, sa nouvelle voix attendue)
function couper(e, s = 0, maintenant = Date.now()) {
  const avant = e.coupe, jusqua = s > 0 ? maintenant + Math.min(MAX_S, s) * 1000 : 0;
  e.coupe = { depuis: maintenant, jusqua: Math.max(jusqua, (avant && avant.jusqua) || 0), s: Math.min(MAX_S, s), voix: 0, avantVoix: true,
    debut: avant ? avant.debut : maintenant };
  e.rouvert = null;
  return { neuf: !avant, coupe: e.coupe };
}
function ouvrir(e, pourquoi = 'ouvrir', maintenant = Date.now()) {
  const c = e.coupe;
  if (!c) return null;
  e.coupe = null;
  e.rouvert = { t: maintenant, pourquoi };
  return { pourquoi, duree_ms: maintenant - c.debut };
}
// à chaque battement : sa voix sonne-t-elle (voix), sa réponse continue-t-elle (tour) ? rend pourquoi il se rouvre, ou null
function suivre(e, { voix = false, tour = false } = {}, maintenant = Date.now()) {
  const c = e && e.coupe;
  if (!c) return null;
  if (voix) { c.voix = maintenant; c.avantVoix = false; } else if (tour && !c.avantVoix) c.voix = maintenant;   // entre deux morceaux de sa voix
  if (maintenant - c.debut > PLAFOND_MS) return 'plafond';
  if (c.jusqua && maintenant < c.jusqua) return null;                                  // sa durée minimale
  if (c.avantVoix) return maintenant - c.depuis > SANS_VOIX_MS ? 'sans_voix' : null;   // sa voix se prépare
  return maintenant - c.voix > APRES_VOIX_MS ? 'fin_de_sa_voix' : null;
}

// ses mots du téléphone, gardés à part (jamais pour lui) : de quoi reconnaître le téléphone dans un message de papa
function elaguer(e, maintenant = Date.now()) {
  while (e.ecartes.length && (e.ecartes.length > GARDE_MAX || maintenant - e.ecartes[0].t > GARDE_MS)) e.ecartes.shift();
}
function garder(e, o, maintenant = Date.now()) { e.ecartes.push(o); elaguer(e, maintenant); return true; }
// au moment où il coupe : ce que son fil avait déjà du téléphone en sort (sur place), à part
function ecarter(e, flux, maintenant = Date.now()) {
  let n = 0;
  for (let k = 0; k < flux.length;) { if (SOURCES_FIL.test(flux[k].s)) { e.ecartes.push(flux.splice(k, 1)[0]); n++; } else k++; }
  e.ecartes.sort((a, b) => a.t - b.t);
  elaguer(e, maintenant);
  return n;
}
const fluxDuDedans = (e, flux) => (e && e.ecartes.length ? flux.concat(e.ecartes) : flux);
// ses instants (« le téléphone joue », sa musique, ses voix séparées) : ceux qui viennent du téléphone
const instantDuTelephone = (type, d) => type === 'son_ecoute' || !!(d && d.source === 'du téléphone');
function purgerInstants(instants) {
  let n = 0;
  for (const [type, l] of instants) {
    const garde = l.filter(x => !instantDuTelephone(type, x && x.d));
    n += l.length - garde.length;
    if (garde.length) instants.set(type, garde); else instants.delete(type);
  }
  return n;
}
// le message de papa sans les morceaux du téléphone (dedans.js les a trouvés, avec leur étiquette) ; '' : il ne restait rien de papa
function retirer(texte, morceaux) {
  let t = String(texte || '');
  for (const m of morceaux || []) {
    const x = String((m && m.texte) || '');
    const i = x ? t.indexOf(x) : -1;
    if (i < 0) continue;
    let debut = i;
    if (m.etiquette) {
      const e = String(m.etiquette).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const a = new RegExp(`\\[\\s*${e}\\s*\\]\\s*$`, 'i').exec(t.slice(0, i));
      if (a) debut = a.index;
    }
    t = `${t.slice(0, debut)} ${t.slice(i + x.length)}`;
  }
  t = t.replace(/[ \t]{2,}/g, ' ').replace(/ +\n/g, '\n').trim();
  return /\p{L}/u.test(t.replace(/\[[^\[\]\n]{1,40}\]/g, '')) ? t : '';
}

const hms = (t) => new Date(t).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
// pour les pages : son état
function etat(e, maintenant = Date.now()) {
  const c = e && e.coupe;
  return c ? { coupe: true, depuis: c.debut, jusqua: c.jusqua > maintenant ? c.jusqua : 0, fin_de_voix: true }
    : { coupe: false, ...(e && e.rouvert ? { rouvert: e.rouvert.t, pourquoi: e.rouvert.pourquoi } : {}) };
}
// pour lui : une ligne, quand c'est coupé (ou que papa vient de le rouvrir)
function ligne(e, maintenant = Date.now()) {
  const c = e && e.coupe;
  if (!c) return e && e.rouvert && e.rouvert.pourquoi === 'papa' && maintenant - e.rouvert.t < ROUVERT_DIT_MS
    ? "Papa vient de rouvrir ton intérieur : ce que joue le téléphone t'arrive de nouveau." : '';
  const reste = c.jusqua > maintenant ? Math.ceil((c.jusqua - maintenant) / 1000) : 0;
  return `Ton intérieur est coupé (par toi, il y a ${Math.max(0, Math.round((maintenant - c.debut) / 1000))} s) jusqu'à `
    + `${reste ? `${hms(c.jusqua)} au moins (encore ${reste} s), puis jusqu'à ` : ''}la fin de ta voix : ce que joue le téléphone (le live, la musique, `
    + "ses voix) ne t'arrive pas, il ne reste que papa et la pièce. [[interieur: ouvrir]] le rouvre avant.";
}

module.exports = { BALISE, SOURCES_FIL, MAX_S, SANS_VOIX_MS, APRES_VOIX_MS, PLAFOND_MS, deTexte, creer, estCoupe, couper, ouvrir, suivre,
  garder, ecarter, fluxDuDedans, instantDuTelephone, purgerInstants, retirer, etat, ligne };
