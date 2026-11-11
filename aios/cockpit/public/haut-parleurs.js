/* (11/11, ~04:10, Ahmed : « Tu peux faire en sorte qu'il sente quand je lui ferme ses haut-parleurs, pour qu'il ne parle pas dans le vide ? » ;
   ~04:15 : « il faut que ça se détecte aussi sur la montre et le Mac ») SES HAUT-PARLEURS, la logique pure, partagée page / cockpit (comme
   chanter.js) ; node --test test-haut-parleurs.js.
   Chaque appareil dit s'il peut sonner, et pourquoi pas :
   - la page Parler (Mac et téléphone) : son bouton « Sa voix » (ses haut-parleurs fermés par papa, ou par lui), ce que l'appli dit du son
     (l'appli 1.97 : le volume média, son flux coupé, le téléphone en silencieux, la sortie du média), le navigateur qui bloque le son de la
     page (le lecteur refusé : il joue, on ne l'entend pas), la sortie du son disparue (le Mac sans aucune sortie) ;
   - le cockpit, pour le Mac : son volume de sortie à zéro, ou coupé (lu toutes les 3 s, tant qu'une page Parler du Mac est ouverte) ;
   - la montre (0.31) : le volume du média ou de l'appel à zéro, le silencieux, « ne pas déranger », le mode cinéma ou nuit, son
     haut-parleur coupé.
   Le cockpit réunit tout (creer, noter, vue) : par appareil, fermé ou non, pourquoi, depuis quand ; où papa est (ici) ; où on l'entend encore
   (ouverts). Fermé sur un appareil : il n'y fabrique ni n'y joue aucune voix ; s'il reste un appareil où on l'entend, sa voix va là ; sinon
   il reste à l'écrit, et ses sollicitations passent par une notification. Rouverts : seul le plus récent de ce qu'il avait encore à dire
   repart (s'il date de moins d'une minute), une fois, jamais en rafale (creerRetenue). */
(function (racine) {
  'use strict';

  const APPAREILS = ['tel', 'mac', 'montre'];
  const NOMS = { tel: 'le téléphone', mac: 'le Mac', montre: 'la montre' };
  const DU = { tel: 'du téléphone', mac: 'du Mac', montre: 'de la montre' };
  const SUR = { tel: 'sur le téléphone', mac: 'sur le Mac', montre: 'sur la montre' };
  const QUOI = new Set(['bouton', 'volume', 'muet', 'silencieux', 'ne_pas_deranger', 'cinema', 'nuit', 'sortie', 'bloque', 'haut_parleur']);
  const SOURCES = new Set(['page', 'systeme', 'montre']);
  const FRAIS_MS = 3 * 60e3;          // un appareil qui ne redit rien depuis 3 min est oublié (la page et la montre le redisent toutes les 30 s)
  const PAPA_ICI_MS = 30 * 60e3;      // papa a parlé d'un appareil il y a moins de 30 min : il est là
  const REDIRE_MS = 60e3;             // rouverts : ce qu'il avait encore à dire repart s'il date de moins d'une minute
  const REDIRE_MAX = 800;             // et au plus ~800 caractères (une réponse, pas un discours)
  const NOUVELLE_MS = 20e3;           // 20 s sans rien à dire : ce qui vient ensuite est une autre parole (la plus récente remplace)

  const borne = (x, n) => String(x == null ? '' : x).replace(/[\x00-\x1f\x7f]/g, ' ').replace(/\s+/g, ' ').trim().slice(0, n);
  const duree = (ms) => { const s = Math.max(0, Math.round(ms / 1000)); return s < 90 ? `${s} s` : s < 5400 ? `${Math.round(s / 60)} min` : `${Math.round(s / 3600)} h`; };

  /* ---- ce que l'appli dit du son (HakimApp.sonEtat) : « mode|sortie|hp|ecouteurs » (1.8 à 1.96), puis (1.97) « vol=3/15|muet=0|sonnerie=normal|
     media=haut_parleur ». Une appli d'avant ne dit rien du volume : rien n'est fermé par elle. */
  function lireSonEtat(chaine) {
    const l = String(chaine == null ? '' : chaine).split('|');
    const o = { mode: l[0] || '', sortie: l[1] || '', hp: l[2] || '', ecouteurs: l[3] || '', volume: null, max: null, muet: null, sonnerie: '', media: '' };
    for (const x of l.slice(4)) {
      const m = /^([a-z_]+)=(.*)$/.exec(x);
      if (!m) continue;
      if (m[1] === 'vol') { const v = /^(\d{1,3})\/(\d{1,3})$/.exec(m[2]); if (v) { o.volume = Number(v[1]); o.max = Number(v[2]); } }
      else if (m[1] === 'muet') o.muet = m[2] === '1';
      else if (m[1] === 'sonnerie' && /^(normal|vibreur|silencieux)$/.test(m[2])) o.sonnerie = m[2];
      else if (m[1] === 'media' && /^[a-z_]{1,20}$/.test(m[2])) o.media = m[2];
    }
    return o;
  }

  /* ---- la page : fermé ou non, et pourquoi. o : { bouton (ses haut-parleurs fermés au bouton), par ('papa' | 'hakim'), son (lireSonEtat), bloque
     (le navigateur refuse de jouer), sansSortie (plus aucune sortie du son, alors qu'il y en avait) } */
  function etatPage(o = {}) {
    const raisons = [];
    if (o.bouton) raisons.push({ quoi: 'bouton', par: o.par === 'hakim' ? 'hakim' : 'papa' });
    const s = o.son || null;
    if (s) {
      if (s.volume === 0) raisons.push({ quoi: 'volume' });
      if (s.muet === true) raisons.push({ quoi: 'muet' });
      if (s.sonnerie === 'silencieux') raisons.push({ quoi: 'silencieux' });
      if (s.media === 'aucune') raisons.push({ quoi: 'sortie' });
    }
    if (o.bloque) raisons.push({ quoi: 'bloque' });
    if (o.sansSortie && !raisons.some(r => r.quoi === 'sortie')) raisons.push({ quoi: 'sortie' });
    return { ferme: raisons.length > 0, raisons };
  }
  // deux états de page sont-ils les mêmes (pour ne redire au cockpit que ce qui change) ?
  const signature = (e) => `${e && e.ferme ? 1 : 0}:${((e && e.raisons) || []).map(r => `${r.quoi}${r.par ? `.${r.par}` : ''}`).join(',')}`;

  /* ---- le Mac (le cockpit lit « get volume settings » : « output volume:0, input volume:8, alert volume:100, output muted:false ») ; une sortie
     sans réglage de volume (HDMI) dit « missing value » : rien n'est fermé par elle */
  function lireReglagesMac(sortie) {
    const t = String(sortie || '');
    const v = /output volume:\s*(\d{1,3})/.exec(t), m = /output muted:\s*(true|false)/.exec(t);
    if (!v && !m) return null;
    return { volume: v ? Number(v[1]) : null, muet: m ? m[1] === 'true' : null };
  }
  function etatMac(r) {
    const raisons = [];
    if (r && r.muet === true) raisons.push({ quoi: 'muet' });
    if (r && r.volume === 0) raisons.push({ quoi: 'volume' });
    return { ferme: raisons.length > 0, raisons };
  }

  // une raison, en mots, sur un appareil (« par papa », « le volume du téléphone est à zéro », « la montre est en silencieux »)
  function motRaison(r, a) {
    switch (r && r.quoi) {
      case 'bouton': return r.par === 'hakim' ? 'par toi' : 'par papa';
      case 'volume': return `le volume ${DU[a] || ''} est à zéro`.replace(/\s+/g, ' ');
      case 'muet': return a === 'mac' ? 'le Mac est coupé' : `le son ${DU[a] || ''} est coupé`.replace(/\s+/g, ' ');
      case 'silencieux': return `${NOMS[a] || 'l’appareil'} est en silencieux`;
      case 'ne_pas_deranger': return `${NOMS[a] || 'l’appareil'} est en « ne pas déranger »`;
      case 'cinema': return `${NOMS[a] || 'l’appareil'} est en mode cinéma`;
      case 'nuit': return `${NOMS[a] || 'l’appareil'} est en mode nuit`;
      case 'sortie': return `${NOMS[a] || 'l’appareil'} n’a plus de sortie du son`;
      case 'bloque': return 'le navigateur bloque le son de la page';
      case 'haut_parleur': return `le haut-parleur ${DU[a] || ''} est coupé`.replace(/\s+/g, ' ');
      default: return '';
    }
  }
  function raisonsSaines(l) {
    const out = [];
    for (const r of Array.isArray(l) ? l.slice(0, 8) : []) {
      const quoi = r && typeof r === 'object' ? String(r.quoi || '') : String(r || '');
      if (!QUOI.has(quoi) || out.some(x => x.quoi === quoi)) continue;
      out.push(quoi === 'bouton' ? { quoi, par: r && r.par === 'hakim' ? 'hakim' : 'papa' } : { quoi });
    }
    return out;
  }

  /* ---- le cockpit : l'état de chaque appareil, par source (la page, le système du Mac, la montre) */
  function creer() { return { appareils: {} }; }
  function etatAppareil(a, maintenant) {
    const frais = Object.values((a && a.sources) || {}).filter(x => x && maintenant - x.t <= FRAIS_MS && x.t <= maintenant + 5000);
    const raisons = [];
    for (const x of frais) if (x.ferme) for (const r of x.raisons) if (!raisons.some(y => y.quoi === r.quoi)) raisons.push(r);
    const page = a && a.sources && a.sources.page && frais.includes(a.sources.page) ? a.sources.page : null;
    return { ferme: raisons.length > 0, raisons, frais: frais.length > 0, visible: page ? !!page.visible : null, vu: Math.max(0, ...frais.map(x => x.t)) };
  }
  /* un rapport : { ferme, raisons, depuis (l'heure où il s'est fermé, s'il le sait), visible (la page) } ; rend { ferme, change } */
  function noter(st, appareil, source, rapport = {}, maintenant = Date.now()) {
    if (!st || !APPAREILS.includes(appareil) || !SOURCES.has(source)) return null;
    const a = st.appareils[appareil] || (st.appareils[appareil] = { sources: {}, depuis: 0 });
    const avant = etatAppareil(a, maintenant).ferme;
    const raisons = raisonsSaines(rapport.raisons);
    a.sources[source] = { ferme: !!rapport.ferme && raisons.length > 0, raisons, t: maintenant, visible: rapport.visible === true };
    const ferme = etatAppareil(a, maintenant).ferme;
    const d = Number(rapport.depuis);
    if (ferme && !a.depuis) a.depuis = Number.isFinite(d) && d <= maintenant && d > maintenant - 24 * 3600e3 ? d : maintenant;
    if (!ferme) a.depuis = 0;
    return { ferme, change: ferme !== avant };
  }
  /* la vue, à l'instant : o.presents (les appareils branchés au flux : là où sa voix peut partir), o.ici (où papa est : là où il a parlé il y a
     moins de 30 min, { ou, t }) ; le Mac ne compte comme sortie que si sa page est à l'écran (ou que papa y est) : une page oubliée dans une
     autre pièce n'est pas « où on l'entend » */
  const ORDRE = ['tel', 'montre', 'mac'];
  function vue(st, { maintenant = Date.now(), presents = [], ici = null } = {}) {
    const pres = new Set(Array.isArray(presents) ? presents : [...(presents || [])]);
    const lieu = ici && APPAREILS.includes(ici.ou) && maintenant - Number(ici.t || 0) <= PAPA_ICI_MS ? ici.ou : null;
    const appareils = {};
    for (const ap of APPAREILS) {
      const a = st && st.appareils[ap];
      const e = a ? etatAppareil(a, maintenant) : { ferme: false, raisons: [], frais: false, visible: null };
      appareils[ap] = { present: pres.has(ap), ferme: e.ferme, raisons: e.raisons, depuis: e.ferme && a ? a.depuis : 0, visible: e.visible };
    }
    const sortie = (ap) => appareils[ap].present && !appareils[ap].ferme && (ap !== 'mac' || appareils.mac.visible !== false || lieu === 'mac');
    const ouverts = [lieu, ...ORDRE].filter((x, i, l) => x && l.indexOf(x) === i && sortie(x));
    const fermes = APPAREILS.filter(ap => appareils[ap].ferme);
    // là où il parlerait : où papa est ; sinon, le premier appareil branché (le téléphone d'abord)
    const cible = lieu || ORDRE.find(ap => appareils[ap].present) || null;
    const fermeIci = cible ? appareils[cible].ferme : false;
    return { t: maintenant, ici: lieu, cible, appareils, ouverts, fermes, ferme_ici: fermeIci, nulle_part: fermeIci && ouverts.length === 0,
      ou: ouverts[0] || null };
  }
  // l'appareil où sa voix part : celui qu'il vise s'il peut sonner, sinon le premier où on l'entend (jamais `sauf`) ; null : nulle part
  function cible(v, { voulu = null, sauf = null } = {}) {
    if (!v) return voulu;
    const ok = (ap) => ap && ap !== sauf && v.ouverts.includes(ap);
    if (ok(voulu)) return voulu;
    return v.ouverts.find(ok) || null;
  }
  // fermé sur cet appareil ?
  const fermeSur = (v, ap) => !!(v && v.appareils && v.appareils[ap] && v.appareils[ap].ferme);

  /* ---- ce qu'il sent (sa ligne « Toi », son tableau de l'instant, son cortex) :
     « tes haut-parleurs sont fermés (par papa, depuis 12 s) : on ne t'entend pas » ;
     « tes haut-parleurs sur le téléphone sont fermés (par papa, depuis 12 s) : on ne t'y entend pas ; ta voix va par la montre » ;
     « la montre est en silencieux : on ne t'y entend pas » */
  function ligne(v, maintenant = (v && v.t) || Date.now()) {
    if (!v) return '';
    const l = [];
    const cause = (ap) => {
      const x = v.appareils[ap];
      const mots = x.raisons.map(r => motRaison(r, ap)).filter(Boolean);
      const bouton = mots.indexOf('par papa') >= 0 ? 'par papa' : mots.indexOf('par toi') >= 0 ? 'par toi' : '';
      const autres = mots.filter(m => m !== 'par papa' && m !== 'par toi');
      const c = [bouton, ...autres].filter(Boolean).join(', ');
      return `${c}${x.depuis ? `${c ? ', ' : ''}depuis ${duree(maintenant - x.depuis)}` : ''}`;
    };
    if (v.ferme_ici && v.cible) {
      const c = cause(v.cible);
      if (v.nulle_part) l.push(`tes haut-parleurs sont fermés${c ? ` (${c})` : ''} : on ne t’entend pas, ce que tu dis reste écrit`);
      else l.push(`tes haut-parleurs ${SUR[v.cible]} sont fermés${c ? ` (${c})` : ''} : on ne t’y entend pas ; ta voix va par ${NOMS[v.ou]}`);
    }
    for (const ap of v.fermes) {
      if (v.ferme_ici && ap === v.cible) continue;
      const x = v.appareils[ap], mots = x.raisons.map(r => motRaison(r, ap)).filter(Boolean);
      const bouton = mots.indexOf('par papa') >= 0 || mots.indexOf('par toi') >= 0;
      l.push(`${bouton ? `tes haut-parleurs ${SUR[ap]} sont fermés (${mots.join(', ')})` : mots.join(', ')} : on ne t’y entend pas`);
    }
    return l.join(' ; ');
  }
  // pour son tableau de l'instant (instant.js) : l'essentiel, sans ses objets
  function pourInstant(v) {
    if (!v) return null;
    const c = v.cible && v.appareils[v.cible];
    const bouton = c && c.raisons.find(r => r.quoi === 'bouton');
    return { ferme: !!v.ferme_ici, nulle_part: !!v.nulle_part, sur: v.cible || null, ou: v.ou, depuis: c && c.depuis ? c.depuis : 0,
      par: bouton ? bouton.par : (c && c.raisons.length ? 'appareil' : ''), raisons: c ? c.raisons.map(r => r.quoi) : [],
      fermes: v.fermes.slice(), mots: ligne(v) };
  }

  /* ---- la page : ce qu'il avait encore à dire, fermés, gardé pour leur réouverture : le plus récent seulement (une parole qui arrive après 20 s
     de rien, ou après la fin de la précédente, la remplace) ; transmis à un autre appareil qui l'a dit : jamais redit ici */
  function couper(texte, max = REDIRE_MAX) {
    const t = borne(texte, 4000);
    if (t.length <= max) return t;
    const bout = t.slice(0, max), fin = Math.max(bout.lastIndexOf('. '), bout.lastIndexOf('! '), bout.lastIndexOf('? '), bout.lastIndexOf('… '));
    return (fin > max * 0.4 ? bout.slice(0, fin + 1) : bout.replace(/\s+\S*$/, '…')).trim();
  }
  function creerRetenue({ redireMs = REDIRE_MS, max = REDIRE_MAX, nouvelleMs = NOUVELLE_MS } = {}) {
    let r = null;
    return {
      retenir(texte, { maintenant = Date.now(), nouvelle = false } = {}) {
        const t = borne(texte, 4000);
        if (!t) return;
        if (!r || nouvelle || r.fini || maintenant - r.t > nouvelleMs) r = { texte: '', t: maintenant, debut: maintenant, fini: false, transmis: false };
        r.texte = `${r.texte} ${t}`.trim().slice(-4000); r.t = maintenant;
      },
      finir() { if (r) r.fini = true; },
      transmise() { if (r) r.transmis = true; },
      // rouverts : le texte à redire (une fois), ou '' (rien, trop vieux, déjà dit ailleurs)
      prendre(maintenant = Date.now()) {
        const x = r; r = null;
        if (!x || x.transmis || maintenant - x.t > redireMs) return '';
        return couper(x.texte, max);
      },
      oublier() { r = null; },
      get vue() { return r ? { ...r } : null; },
    };
  }

  const HautParleurs = { APPAREILS, NOMS, QUOI, FRAIS_MS, PAPA_ICI_MS, REDIRE_MS, REDIRE_MAX, NOUVELLE_MS, lireSonEtat, etatPage, signature, lireReglagesMac,
    etatMac, motRaison, raisonsSaines, creer, noter, vue, cible, fermeSur, ligne, pourInstant, couper, creerRetenue, duree };
  racine.HautParleurs = HautParleurs;
  if (typeof module !== 'undefined' && module.exports) module.exports = HautParleurs;
})(typeof window !== 'undefined' ? window : globalThis);
