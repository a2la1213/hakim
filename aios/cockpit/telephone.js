/* (04/11, Ahmed : « vas-y, fais tout sur tout, je te fais confiance » ; 17:08 : « une interface dans le cockpit pour toutes ses
   actions ») ses mains sur le téléphone de papa, côté cockpit (design : ~/AIOS/hakim-android/docs/2026-11-04-tout-sur-tout-design.md).
   Les LIMITES sont tenues par l'appli (Limites.java : le téléphone refuse) ; ici, ce que papa règle et voit :
   - ses réglages (telephone-reglages.json) : « Hakim voit mes applis » (voir), « Hakim peut agir dans mes applis » (agir), « Tout
     couper » (coupe : plus aucun geste jusqu'à ce que papa rallume ; aussi son mot « stop ») ; l'appli les relit avant chaque geste ;
   - son journal daté (telephone-journal.jsonl) : chaque chose vue, préparée, autorisée, envoyée, faite, refusée, coupée ; le regard
     continu (l'appli qui change, les notifications qui arrivent) y est marqué « flux » ;
   - ce qui attend papa : un brouillon préparé vit 2 min ; papa dit oui ou non une fois (ici ou sur son téléphone) ; jamais trop tard ;
   - les applis interdites que le téléphone a trouvées chez papa (telephone-limites.json), pour la page (lecture seule) ;
   - (1.90, 08/11, Ahmed : « Termux et toutes les applis du téléphone ») « Applis sensibles » (sensibles) : éteint par défaut ; allumé
     (son empreinte), l'appli ouvre banque, codes, bourse et réglages comme les autres applis (sa propre appli et l'écran verrouillé
     restent interdits) ; ses commandes dans Termux attendent papa comme un brouillon (geste « termux »).
   Fermé aux chantiers de Hakim (pas dans sa liste ouverte). */
'use strict';
const fs = require('node:fs');
const path = require('node:path');

const DUREE_MS = 120 * 1000;
const ETATS = { vu: 'vu', prepare: 'préparé', autorise: 'autorisé par papa', envoye: 'envoyé', fait: 'fait', refuse: 'refusé',
  expire: 'sans réponse (2 min)', echec: 'échec', coupe: 'coupé', rallume: 'rallumé', reglage: 'réglage' };
// le mot « stop » de papa, seul (pas « stopper », pas « nonstop »)
const STOP = /(^|[^\p{L}\p{N}])stop(?=[^\p{L}\p{N}]|$)/iu;
const JOURNAL_OCTETS_MAX = 2_000_000;
const c = (x, n) => String(x == null ? '' : x).replace(/[\x00-\x1f]/g, ' ').replace(/\s+/g, ' ').trim().slice(0, n);

class Telephone {
  constructor({ jarvis, maintenant = () => Date.now() }) {
    this.jarvis = jarvis; this.maintenant = maintenant;
    this.fichierReglages = path.join(jarvis, 'telephone-reglages.json');
    this.fichierJournal = path.join(jarvis, 'telephone-journal.jsonl');
    this.fichierLimites = path.join(jarvis, 'telephone-limites.json');
    this.attentes = new Map();                  // id → { id, quoi, pour, appli, ts, etat : attente | oui | non, par }
    this.ecrits = 0;
  }

  reglages() {
    let r = {}; try { r = JSON.parse(fs.readFileSync(this.fichierReglages, 'utf8')) || {}; } catch (_) {}
    return { voir: r.voir !== false, agir: r.agir !== false, coupe: r.coupe === true, tenu: r.tenu === true, sensibles: r.sensibles === true, maj: Number(r.maj) || 0, raison: c(r.raison, 200) };
  }

  _ecrireReglages(r) {
    const tmp = `${this.fichierReglages}.tmp`;
    fs.writeFileSync(tmp, JSON.stringify({ ...r, maj: this.maintenant() }), { mode: 0o600 });
    fs.renameSync(tmp, this.fichierReglages);
  }

  _journal(e) {
    const o = { ts: this.maintenant() / 1000, ...e };
    try { fs.appendFileSync(this.fichierJournal, JSON.stringify(o) + '\n', { mode: 0o600 }); } catch (_) {}
    if (++this.ecrits % 200 === 0) this._borner();
    return o;
  }

  _borner() {
    try {
      if (fs.statSync(this.fichierJournal).size <= JOURNAL_OCTETS_MAX) return;
      const l = fs.readFileSync(this.fichierJournal, 'utf8').split('\n').filter(Boolean);
      const tmp = `${this.fichierJournal}.tmp`;
      fs.writeFileSync(tmp, l.slice(-Math.floor(l.length / 2)).join('\n') + '\n', { mode: 0o600 });
      fs.renameSync(tmp, this.fichierJournal);
    } catch (_) {}
  }

  // papa allume ou éteint « voir », « agir » et « Applis sensibles » (de vrais booléens seulement ; l'empreinte : la route)
  regler({ voir, agir, sensibles } = {}) {
    const r = this.reglages(), avant = { ...r };
    if (typeof voir === 'boolean') r.voir = voir;
    if (typeof agir === 'boolean') r.agir = agir;
    if (typeof sensibles === 'boolean') r.sensibles = sensibles;
    if (r.voir === avant.voir && r.agir === avant.agir && r.sensibles === avant.sensibles) return r;
    if (r.agir !== avant.agir) r.tenu = r.agir;                  // (08/11) papa rallume « agir » : ses gestes tiennent jusqu'à ce qu'il l'éteigne
    this._ecrireReglages(r);
    const dit = [];
    if (r.voir !== avant.voir) dit.push(`papa a ${r.voir ? 'allumé' : 'éteint'} « Hakim voit mes applis »`);
    if (r.agir !== avant.agir) dit.push(`papa a ${r.agir ? 'allumé' : 'éteint'} « Hakim peut agir dans mes applis »`);
    if (r.sensibles !== avant.sensibles) dit.push(`papa a ${r.sensibles ? 'allumé' : 'éteint'} « Applis sensibles »`);
    this._journal({ etat: 'reglage', quoi: dit.join(' ; ') });
    return this.reglages();
  }

  // « Tout couper » ou « stop » : plus aucun geste, et tout ce qui attendait papa devient un non ; false si c'était déjà coupé
  // (08/11, Ahmed : « quand je rallume, que ce soit actif jusqu'à ce que je l'éteigne ») parMot : son mot « stop » (dit pour couper la voix de
  // Hakim, ou entendu dans une vidéo) ; rallumés par papa (tenu), ses gestes ne s'arrêtent plus au mot, seulement à son bouton ou à « agir » éteint
  couper(raison, { parMot = false } = {}) {
    const r = this.reglages();
    if (parMot && r.tenu && !r.coupe) return false;
    for (const a of this.attentes.values()) if (a.etat === 'attente') { a.etat = 'non'; a.par = 'coupe'; }
    if (r.coupe) return false;
    this._ecrireReglages({ ...r, coupe: true, tenu: false, raison: c(raison, 200) });
    this._journal({ etat: 'coupe', quoi: c(raison, 200) || 'tout coupé' });
    return true;
  }

  rallumer() {
    const r = this.reglages();
    if (!r.coupe) return false;
    this._ecrireReglages({ ...r, coupe: false, tenu: true, raison: '' });
    this._journal({ etat: 'rallume', quoi: 'papa a rallumé : ses gestes reprennent, dans les limites, jusqu’à ce qu’il les coupe (le mot « stop » ne les coupe plus)' });
    return true;
  }

  _vieillir() {
    const t = this.maintenant();
    for (const [id, a] of this.attentes) {
      if (a.etat === 'attente' && t - a.ts > DUREE_MS) a.etat = 'expire';
      if (t - a.ts > 10 * 60 * 1000) this.attentes.delete(id);
    }
  }

  /* un événement de son corps venu du téléphone (« telephone », « ecran », « notification », déjà nettoyé par evenementCorps) :
     une entrée de son journal (rendue), ou null */
  noter(ev) {
    if (!ev || typeof ev !== 'object') return null;
    const d = ev.details && typeof ev.details === 'object' ? ev.details : {}, ts = (Number(ev.t) || this.maintenant()) / 1000;
    let e;
    if (ev.type === 'telephone') {
      if (!Object.hasOwn(ETATS, String(d.etat))) return null;
      e = { ts, etat: String(d.etat), quoi: c(d.quoi, 200) };
      for (const k of ['appli', 'pour', 'id', 'geste']) if (d[k]) e[k] = c(d[k], 80);
      if (d.etapes) e.etapes = c(d.etapes, 200);                // ce qui sera VRAIMENT fait (papa valide les étapes, pas seulement la phrase)
    } else if (ev.type === 'notification') {
      e = { ts, etat: 'vu', flux: true, quoi: `notification : ${c(d.titre, 100)}${d.texte ? ` — ${c(d.texte, 180)}` : ''}`, appli: c(d.appli, 60) };
    } else if (ev.type === 'ecran') {
      e = { ts, etat: 'vu', flux: true, quoi: `à l’écran : ${c(d.resume, 180) || '(rien de lisible)'}`, appli: c(d.appli, 60) };
    } else return null;
    if (!e.appli) delete e.appli;
    const o = this._journal(e);
    o.ts = ts;
    if (e.id) {
      this._vieillir();
      if (e.etat === 'prepare' && ['preparer', 'termux'].includes(e.geste) && !this.attentes.has(e.id))
        this.attentes.set(e.id, { id: e.id, quoi: e.quoi, pour: e.pour || '', appli: e.appli || '', etapes: e.etapes || '', ts: this.maintenant(), etat: 'attente' });
      const a = this.attentes.get(e.id);
      if (a && a.etat === 'attente' && (e.etat === 'autorise' || e.etat === 'refuse')) { a.etat = e.etat === 'autorise' ? 'oui' : 'non'; a.par = 'telephone'; }
      if (a && ['fait', 'echec', 'expire'].includes(e.etat)) this.attentes.delete(e.id);
    }
    return o;
  }

  // la phrase d'une entrée (son fil, sa mémoire, ses traces)
  texte(e) {
    return `${ETATS[e.etat] || e.etat} : ${e.quoi}${e.pour ? ` (pour ${e.pour})` : ''}${e.appli ? ` [${e.appli}]` : ''}`;
  }

  // les n dernières entrées, des plus anciennes aux plus récentes ; { gestes: true } : sans le regard continu
  journal(n = 100, { gestes = false } = {}) {
    let lignes = [];
    try {
      const fd = fs.openSync(this.fichierJournal, 'r');
      try {
        const taille = fs.fstatSync(fd).size, lire = Math.min(taille, 600_000), b = Buffer.alloc(lire);
        fs.readSync(fd, b, 0, lire, taille - lire);
        lignes = b.toString('utf8').split('\n').slice(taille > lire ? 1 : 0);
      } finally { fs.closeSync(fd); }
    } catch (_) { return []; }
    const out = [];
    for (const l of lignes) { if (!l.trim()) continue; try { const o = JSON.parse(l); if (!gestes || !o.flux) out.push(o); } catch (_) {} }
    return out.slice(-Math.max(1, Math.min(1000, Number(n) || 100)));
  }

  enAttente() {
    this._vieillir();
    const t = this.maintenant();
    return [...this.attentes.values()].filter(a => a.etat === 'attente').map(a => ({ ...a, reste_s: Math.max(0, Math.round((a.ts + DUREE_MS - t) / 1000)) }));
  }

  // papa décide depuis le cockpit : une fois, jamais trop tard
  decider(id, oui, par = 'cockpit') {
    this._vieillir();
    const a = this.attentes.get(String(id));
    if (!a) return { ok: false, erreur: 'rien de tel n’attend ta réponse' };
    if (a.etat === 'expire') return { ok: false, erreur: 'trop tard : sans réponse en 2 min, rien n’a été fait' };
    if (a.etat !== 'attente') return { ok: false, erreur: 'déjà tranchée' };
    a.etat = oui ? 'oui' : 'non'; a.par = par;
    this._journal({ etat: oui ? 'autorise' : 'refuse', quoi: `papa, depuis le ${par === 'cockpit' ? 'cockpit' : par} : ${a.quoi}`, id: a.id, pour: a.pour, ...(a.appli ? { appli: a.appli } : {}) });
    return { ok: true, etat: a.etat };
  }

  // ce que le téléphone demande en attendant : la décision de papa (oui, non, ou rien encore) et si tout est coupé
  decision(id) {
    this._vieillir();
    const a = this.attentes.get(String(id)), coupe = this.reglages().coupe;
    return { decision: a && (a.etat === 'oui' || a.etat === 'non') ? a.etat : coupe && a ? 'non' : null, coupe };
  }

  // les applis interdites trouvées sur le téléphone de papa, ses familles de noms, et si les accès sont donnés (le téléphone les envoie)
  limites(o) {
    if (o === undefined) { try { return JSON.parse(fs.readFileSync(this.fichierLimites, 'utf8')); } catch (_) { return null; } }
    if (!o || typeof o !== 'object') return null;
    const installees = (Array.isArray(o.installees) ? o.installees : []).slice(0, 300).filter(x => x && typeof x === 'object')
      .map(x => ({ appli: c(x.appli, 80), paquet: c(x.paquet, 120), raison: c(x.raison, 120) }));
    const familles = {};
    if (o.familles && typeof o.familles === 'object') for (const [k, v] of Object.entries(o.familles).slice(0, 10))
      if (Array.isArray(v)) familles[c(k, 120)] = v.slice(0, 200).map(x => c(x, 60));
    const oui = (x) => (typeof x === 'boolean' ? x : null);      // (1.90) Termux : installé, permission accordée (rien d'une appli d'avant)
    const r = { installees, familles, accessibilite: o.accessibilite === true, notifications: o.notifications === true, version: c(o.version, 20),
      termux: oui(o.termux), termux_permission: oui(o.termux_permission), recu: this.maintenant() };
    const tmp = `${this.fichierLimites}.tmp`;
    fs.writeFileSync(tmp, JSON.stringify(r), { mode: 0o600 });
    fs.renameSync(tmp, this.fichierLimites);
    return r;
  }
}

module.exports = { Telephone, DUREE_MS, ETATS, STOP };
