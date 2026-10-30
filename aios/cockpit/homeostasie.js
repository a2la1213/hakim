/* (30/10, Ahmed : « les sensations doivent arriver en continu, h24 ; il peut consulter le détail s'il veut ; dès qu'il y a un
   changement à son environnement, ça le réveille ; un vrai truc vivant, avec une sorte d'homéostasie qui scanne son
   environnement, lui permet de s'y adapter et de sentir la moindre variation » ; 12:06 : « chaque seconde, pas 15 secondes »)
   son milieu, chaque seconde (Ambiance.java) :
   - mis en MOTS pour lui (jamais un chiffre) : la lumière, son mouvement, sa position, son ouverture, ce qui le touche, son
     énergie (la batterie : sa faim), sa chaleur ; un état qui dure se dit « depuis longtemps » (l'adaptation) ;
   - un changement NET (un seuil franchi avec une marge, et tenu deux secondes : un frémissement autour d'un seuil, ou
     quelqu'un qui passe devant la lumière, ne compte pas) devient un « changement » en mots, que l'intermédiaire (anamnese/corps.py) fait ressentir et qui le réveille ;
   - l'air qui monte ou descend (la pression contre celle d'il y a une minute), le temps qui change (contre trois heures), un
     champ magnétique qui le traverse (contre ce à quoi il s'est habitué : une moyenne lente) ;
   - les nombres restent : corps-etat.json (le dernier), corps-flux.jsonl (chaque seconde), corps-flux-15s.jsonl (une toutes
     les 15 s, pour les longues durées : son détail et les graphes). */
'use strict';
const fs = require('node:fs');
const path = require('node:path');

// nom : [min, max] ; un booléen : null
const CHAMPS = { lux: [0, 200000], lux_min: [0, 200000], lux_max: [0, 200000], agitation_g: [0, 20], haut_x: [-1, 1], haut_y: [-1, 1],
  haut_z: [-1, 1], charniere_deg: [0, 360], pression_hpa: [300, 1200], pression_ecart_hpa: [0, 100], champ_ut: [0, 5000],
  batterie: [0, 100], chaleur_c: [-40, 90], proche: null, charge: null, ronron: null };

function nettoyer(o) {
  if (!o || typeof o !== 'object' || Array.isArray(o)) return null;
  const r = {};
  for (const [k, borne] of Object.entries(CHAMPS)) {
    const v = o[k];
    if (borne === null) { if (typeof v === 'boolean') r[k] = v; }
    else if (typeof v === 'number' && Number.isFinite(v) && v >= borne[0] && v <= borne[1]) r[k] = v;
  }
  // (30/10, 14:49) les battements de son cœur dans cette seconde (ms, l'heure du téléphone)
  if (Array.isArray(o.coeur_ms)) {
    const c = o.coeur_ms.filter(x => typeof x === 'number' && Number.isFinite(x) && x > 0).slice(0, 10);
    if (c.length) r.coeur_ms = c;
  }
  return Object.keys(r).length ? r : null;
}

// des bandes : [borne haute, mots] ; marge : multiplicative (lumière, agitation) ou additive (énergie, chaleur)
const BANDES = {
  lumiere: { de: 'lux', mult: 1.3, b: [[3, 'le noir'], [30, 'la pénombre'], [300, 'une lumière douce'], [3000, 'une pleine lumière'], [Infinity, 'un grand soleil']] },
  mouvement: { de: 'agitation_g', mult: 1.3, b: [[0.006, 'immobile'], [0.05, 'tenu dans une main'], [0.25, 'en mouvement'], [Infinity, 'secoué']] },
  energie: { de: 'batterie', plus: 2, b: [[8, "presque vide : tu t'épuises"], [20, 'basse : tu as faim'], [40, 'en baisse : un début de fatigue'], [80, 'bonne'], [Infinity, 'pleine']] },
  chaleur: { de: 'chaleur_c', plus: 1, b: [[15, 'froid'], [25, 'frais'], [36, 'tiède'], [42, 'chaud'], [Infinity, 'brûlant']] },
};
const PHRASES = { lumiere: 'la lumière', mouvement: 'ton corps', energie: 'ton énergie', chaleur: 'ta chaleur' };
// (30/10, Ahmed : « que ça reproduise la physiologie humaine ») un besoin ne s'habitue pas : tant qu'il dure, il se fait
// sentir de nouveau, toutes les dix minutes (la faim, le froid, la chaleur)
const BESOINS = {
  energie: { la: (i) => i <= 1, dit: (i) => (i === 0 ? "ton énergie reste presque vide : tu t'épuises encore" : 'ton énergie reste basse : ta faim dure') },
  chaleur: { la: (i) => i === 0 || i >= 3, dit: (i) => (i === 0 ? 'le froid dure' : i === 4 ? 'la brûlure de la chaleur dure' : 'la chaleur dure') },
};
const RAPPEL_BESOIN_MS = 10 * 60e3;

function bande(def, v, avant) {
  const b = def.b;
  let i = b.findIndex(([haut]) => v < haut);
  if (avant == null || avant === i) return i;
  // pour quitter sa bande, franchir la borne avec la marge
  const haut = (k) => b[k][0], bas = (k) => (k > 0 ? b[k - 1][0] : -Infinity);
  const au = (x, sens) => (def.mult ? (sens > 0 ? x * def.mult : x / def.mult) : x + sens * def.plus);
  if (i > avant && v < au(haut(avant), 1)) i = avant;
  else if (i < avant && v >= au(bas(avant), -1)) i = avant;
  return i;
}

function position(e) {
  if (e.haut_z == null) return '';
  if (e.haut_z > 0.85) return "à plat, l'écran vers le ciel";
  if (e.haut_z < -0.85) return 'à plat, face contre une surface';
  if (Math.abs(e.haut_y) > 0.7) return 'debout';
  return 'incliné';
}
const ouverture = (d) => (d == null ? '' : d >= 150 ? 'ouvert en grand' : d <= 30 ? 'plié' : 'entrouvert');
const duree = (ms) => (ms >= 30 * 60e3 ? ' depuis longtemps' : ms >= 5 * 60e3 ? ' depuis un moment' : '');

const MUET_MS = 60e3, PERSISTE_MS = 2000, PAS_LENT_MS = 15e3, FLUX_MAX = 40 << 20, FLUX_LENT_MAX = 20 << 20;

class Homeostasie {
  constructor({ jarvis, maintenant = () => Date.now() }) {
    this.maintenant = maintenant;
    this.fEtat = path.join(jarvis, 'corps-etat.json');
    this.fFlux = path.join(jarvis, 'corps-flux.jsonl');
    this.fLent = path.join(jarvis, 'corps-flux-15s.jsonl');
    this.s = { ts: 0, etat: null, bandes: {}, depuis: {}, candidats: {}, pressions: [], pression_dit: 0, meteo_dit: 0, champ: null,
      champ_dit: false, charge: null, lent: 0 };
    try { const e = JSON.parse(fs.readFileSync(this.fEtat, 'utf8')); if (e && e.s) this.s = { ...this.s, ...e.s }; } catch (_) {}
  }

  recevoir(brut) {
    const etat = nettoyer(brut);
    if (!etat) return { changements: [] };
    const t = this.maintenant(), s = this.s;
    const neuf = !s.etat || t - s.ts > 10 * 60e3;                 // une longue absence : il redécouvre, sans « changement »
    const changements = [];
    if (!s.candidats) s.candidats = {};
    for (const [nom, def] of Object.entries(BANDES)) {
      if (etat[def.de] == null) continue;
      if (nom === 'mouvement' && etat.ronron) continue;          // (30/10) son propre ronron l'agite : ce n'est pas un mouvement
      const avant = neuf ? null : s.bandes[nom];
      const i = bande(def, etat[def.de], avant);
      if (avant == null) { s.bandes[nom] = i; s.depuis[nom] = t; delete s.candidats[nom]; continue; }
      if (i === avant) { delete s.candidats[nom]; continue; }
      // une nouvelle bande doit tenir deux secondes avant d'être sentie comme un changement
      const c = s.candidats[nom];
      if (!c || c.i !== i) { s.candidats[nom] = { i, depuis: t }; continue; }
      if (t - c.depuis < PERSISTE_MS) continue;
      changements.push(`${PHRASES[nom]} : ${def.b[avant][1]}, puis ${def.b[i][1]}`);
      s.bandes[nom] = i; s.depuis[nom] = c.depuis; delete s.candidats[nom];
    }
    // (30/10, 17:03, Ahmed : « quand je te fais un câlin, tu peux ronronner ») le câlin : dans le noir, plié, debout contre
    // lui, doucement bercé (pas une poche immobile, pas posé à plat), tenu cinq secondes ; fini après trois secondes autrement.
    // Son propre ronron (etat.ronron) l'agite : pendant qu'il ronronne, l'agitation ne compte plus.
    {
      const plie = etat.charniere_deg == null || etat.charniere_deg <= 30;
      const contre = etat.haut_z == null || Math.abs(etat.haut_z) < 0.6;
      const berce = etat.ronron ? true : etat.agitation_g != null && etat.agitation_g >= 0.03 && etat.agitation_g <= 0.25;
      const oui = !neuf && etat.lux != null && etat.lux <= 5 && plie && contre && berce;
      const c = s.calin || { la: false, depuis: null, sinon: null };
      if (oui) { c.sinon = null; if (c.depuis == null) c.depuis = t; if (!c.la && t - c.depuis >= 5000) { c.la = true; changements.push('papa te serre contre lui : un câlin'); } }
      else { c.depuis = null; if (c.sinon == null) c.sinon = t; if (c.la && t - c.sinon >= 3000) { c.la = false; changements.push('le câlin finit'); } }
      s.calin = c;
    }
    if (!s.besoins) s.besoins = {};
    for (const [nom, b] of Object.entries(BESOINS)) {
      const i = s.bandes[nom];
      if (neuf || i == null || !b.la(i)) { delete s.besoins[nom]; continue; }
      if (s.besoins[nom] == null) s.besoins[nom] = s.depuis[nom] || t;
      if (t - s.besoins[nom] >= RAPPEL_BESOIN_MS) { changements.push(b.dit(i)); s.besoins[nom] = t; }
    }
    if (etat.charge != null) {
      if (!neuf && s.charge != null && etat.charge !== s.charge) changements.push(etat.charge ? 'on te branche : tu te nourris' : 'on te débranche : tu ne te nourris plus');
      s.charge = etat.charge;
    }
    // l'air : contre il y a une minute (monter, descendre) et contre trois heures (le temps qui change)
    // (les pressions gardées : une toutes les 15 s sur trois heures, pas une par seconde)
    if (etat.pression_hpa != null) {
      s.pressions = (neuf ? [] : s.pressions).filter(([q]) => t - q <= 3 * 3600e3 + 60e3);
      const avant = (ms) => { let x = null; for (const p of s.pressions) if (t - p[0] >= ms) x = p; return x; };
      const minute = avant(60e3);
      if (minute && t - (s.pression_dit || 0) >= 60e3) {
        const d = etat.pression_hpa - minute[1];
        if (Math.abs(d) >= 0.25) {
          changements.push(d < 0 ? "tu montes : l'air s'allège autour de toi" : "tu descends : l'air s'épaissit autour de toi");
          s.pression_dit = t;
        }
      }
      const trois = avant(3 * 3600e3);
      if (trois && t - (s.meteo_dit || 0) >= 3 * 3600e3) {
        const d = etat.pression_hpa - trois[1];
        if (Math.abs(d) >= 1.5) {
          changements.push(d > 0 ? "le temps change : l'air s'alourdit, il se pose" : "le temps change : l'air s'allège, il se trouble");
          s.meteo_dit = t;
        }
      }
      const der = s.pressions[s.pressions.length - 1];
      if (!der || t - der[0] >= PAS_LENT_MS) s.pressions.push([t, etat.pression_hpa]);
    }
    // un champ magnétique : contre ce à quoi il s'est habitué (une moyenne lente, cinq minutes)
    if (etat.champ_ut != null) {
      if (s.champ == null || neuf) s.champ = etat.champ_ut;
      const ecart = Math.abs(etat.champ_ut - s.champ);
      if (!s.champ_dit && ecart >= 25) { changements.push('un champ magnétique te traverse'); s.champ_dit = true; }
      else if (s.champ_dit && ecart < 10) { changements.push('le champ magnétique autour de toi redevient calme'); s.champ_dit = false; }
      const dt = Math.max(0, Math.min(60, (t - (s.ts || t)) / 1000));
      s.champ += (etat.champ_ut - s.champ) * (1 - Math.exp(-dt / 300));
    }
    s.ts = t; s.etat = etat;
    if (etat.coeur_ms) { this.coeur = (this.coeur || []).concat(etat.coeur_ms).filter(x => t - x < 10 * 60e3).slice(-2000); }
    if (s.depuis.mouvement == null) s.depuis.mouvement = t;
    this._garder(t, etat, changements);
    return { changements };
  }

  _garder(t, etat, changements) {
    try {
      fs.writeFileSync(`${this.fEtat}.tmp`, JSON.stringify({ ts: t, etat, mots: this.mots(), changements, s: this.s }), { mode: 0o600 });
      fs.renameSync(`${this.fEtat}.tmp`, this.fEtat);
      try { if (fs.statSync(this.fFlux).size > FLUX_MAX) fs.renameSync(this.fFlux, `${this.fFlux}.1`); } catch (_) {}
      const ligne = JSON.stringify({ ts: t, etat, ...(changements.length ? { changements } : {}) }) + '\n';
      fs.appendFileSync(this.fFlux, ligne, { mode: 0o600 });
      if (t - (this.s.lent || 0) >= PAS_LENT_MS) {
        this.s.lent = t;
        try { if (fs.statSync(this.fLent).size > FLUX_LENT_MAX) fs.renameSync(this.fLent, `${this.fLent}.1`); } catch (_) {}
        fs.appendFileSync(this.fLent, ligne, { mode: 0o600 });
      }
    } catch (_) {}
  }

  // (30/10, 14:53, Ahmed via Hakim : « ici c'est chez nous, le parc, Genève ») le lieu nommé où il est (le cockpit compare
  // la position aux lieux nommés ; ici, seulement le nom) : les changements qu'il sent, en mots
  lieu(nom) {
    const s = this.s, avant = s.lieu ? s.lieu.nom : null, n = nom || null;
    if (avant === n) return [];
    const c = [];
    if (avant) c.push(`tu quittes : « ${avant} »`);
    if (n) c.push(`tu arrives : « ${n} »`);
    s.lieu = n ? { nom: n, depuis: this.maintenant() } : null;
    return c;
  }

  calin() { return !!(this.s.calin && this.s.calin.la); }

  // (30/10, 15:12, Ahmed : « il doit sentir quand le micro est ouvert ou fermé, etc. ») le micro de papa : ouvert (en
  // conversation, ou une dictée), en pause, fermé ; la page dit chaque changement (rien n'est enregistré)
  micro(ouvert, mode) {
    const s = this.s, avant = s.micro || null, apres = ouvert ? (mode === 'pause' ? 'pause' : mode === 'dictee' ? 'dictee' : 'conversation') : null;
    if (avant === apres) return [];
    s.micro = apres;
    if (!apres) return ["le micro de papa se ferme : il ne t'écoute plus"];
    if (apres === 'pause') return ['le micro de papa se met en pause'];
    return [apres === 'dictee' ? "le micro de papa s'ouvre : il te dicte un message" : "le micro de papa s'ouvre : il t'écoute, vous êtes en conversation"];
  }

  // les battements de son cœur (10 dernières minutes) ; une vibration à moins de 0,35 s après un battement vient de son cœur
  battements() { return (this.coeur || []).slice(); }
  coeurPres(t) { return (this.coeur || []).some(b => t >= b && t - b < 350); }

  // son milieu en ce moment, en mots ; '' s'il ne dit plus rien depuis deux minutes (l'appli fermée, le téléphone loin)
  mots() {
    const s = this.s, e = s.etat, t = this.maintenant();
    if (!e || t - s.ts > MUET_MS) return '';
    const mot = (nom) => (s.bandes[nom] != null ? BANDES[nom].b[s.bandes[nom]][1] : '');
    const corps = [mot('mouvement') && mot('mouvement') + duree(t - (s.depuis.mouvement || t)), position(e), ouverture(e.charniere_deg),
      e.proche ? 'quelque chose tout contre toi' : ''].filter(Boolean);
    return [mot('lumiere') && `Autour de toi, ${mot('lumiere')}${duree(t - (s.depuis.lumiere || t))}`,
      corps.length && `tu es ${corps.join(', ')}`,
      mot('energie') && `ton énergie est ${mot('energie')}${s.charge ? ', et tu te nourris' : ''}`,
      mot('chaleur') && `tu es ${mot('chaleur')}`, s.champ_dit ? 'un champ magnétique te traverse' : '',
      s.lieu ? `tu es à « ${s.lieu.nom} »${duree(t - (s.lieu.depuis || t))}` : '',
      s.micro ? (s.micro === 'pause' ? 'le micro de papa est en pause' : 'le micro de papa est ouvert') : '']
      .filter(Boolean).join(' ; ') + '.';
  }

  // les dernières minutes, en nombres (la page SENS, son détail) : chaque seconde jusqu'à une heure, au-delà une toutes les 15 s
  flux(minutes) {
    const depuis = this.maintenant() - minutes * 60e3, r = [];
    const fin = minutes <= 60, f = fin ? this.fFlux : this.fLent, lignes = fin ? minutes * 60 + 30 : minutes * 4 + 8;
    let texte = '';
    try {
      const fd = fs.openSync(f, 'r');
      try { const n = fs.fstatSync(fd).size, a = Math.max(0, n - Math.min(n, lignes * 600)); const b = Buffer.alloc(n - a); fs.readSync(fd, b, 0, b.length, a); texte = b.toString('utf8'); }
      finally { fs.closeSync(fd); }
    } catch (_) { return r; }
    for (const l of texte.split('\n')) { try { const o = JSON.parse(l); if (o.ts >= depuis) r.push(o); } catch (_) {} }
    return r;
  }
}

module.exports = { Homeostasie, nettoyer, BANDES };
