/* (30/10, Ahmed : « intègre tous les capteurs du projet tricodeur à Hakim ; qu'il puisse tout capter, les lire comme il veut et
   en faire ce qu'il veut ») ses sens, côté cockpit : la file des demandes que Hakim écrit (anamnese/jarvis/sens.py →
   ~/AIOS/jarvis/sens-demandes.jsonl), donnée une à une à l'appli du téléphone (Sens.java) ; ses résultats rangés dans son
   atelier, atelier/sens/<id>/donnees.csv et resume.json, jamais à travers un lien (son terminal écrit dans l'atelier) ;
   chaque fin est dite une fois (le réveil de Hakim). Une demande donnée sans retour revient après sa durée + 2 min (deux
   fois au plus) ; jamais prise en 2 h : échec (« le téléphone n'a pas répondu »). */
'use strict';
const fs = require('node:fs');
const path = require('node:path');

const ID = /^S-\d{8}-\d{6}-[0-9a-f]{4}$/;
const SENS = new Set(['inventaire', 'imu', 'sismo', 'baro', 'magneto', 'son']);
const EXPIRE_MS = 2 * 3600 * 1000, MARGE_MS = 120 * 1000, ESSAIS = 3;
// (30/10, Ahmed : « ses propres modules ») ses instruments à lui : donnés à son Tricordeur (le module), qui rend par
// Documents/Hakim/sens/<id>/ (Syncthing) ; on attend sa durée + 30 min (la synchronisation)
const NOM = /^[a-z][a-z0-9_]{2,29}$/, PAQUET = /^[a-z][a-z0-9_.]{2,80}$/, MARGE_MODULE_MS = 30 * 60 * 1000;
// (30/10, Hakim pour Ahmed : « que papa puisse jouer avec aussi ») les sens intégrés, pour qu'Ahmed lance les mêmes mesures
// (page SENS) : nom → [ce qu'il capte, durée par défaut, durée max] (les mêmes que anamnese/jarvis/sens.py)
const INTEGRES = {
  inventaire: ["tous les capteurs du téléphone et ce qu'ils savent faire", 0, 0],
  imu: ['les capteurs de mouvement et d’ambiance, bruts (cadence : jeu, max, normal ou des Hz)', 10, 300],
  sismo: ['les secousses (le sismographe) : le téléphone posé à plat', 60, 900],
  baro: ['la pression, l’altitude relative, les infrasons, les coups de pression', 60, 900],
  magneto: ['le champ magnétique : moyenne, variations rapides', 20, 300],
  son: ['le micro en niveaux, spectre, bandes, pics, ultrasons (rien n’est enregistré)', 10, 60],
};

class FileSens {
  constructor({ jarvis, atelier, telephone, maintenant = () => Date.now() }) {
    this.jarvis = jarvis; this.atelier = atelier; this.maintenant = maintenant;
    this.telephone = telephone || path.join(jarvis, 'cwd', 'fichiers', 'telephone', 'Z Fold 7');
    this.fichier = path.join(jarvis, 'sens-demandes.jsonl');
    this.etatFichier = path.join(jarvis, 'sens-etat.json');
    this.lu = 0; this.demandes = new Map(); this.dire = []; this.ressentir = [];
    try {
      const e = JSON.parse(fs.readFileSync(this.etatFichier, 'utf8'));
      this.lu = Number(e.lu) || 0;
      for (const d of e.demandes || []) this.demandes.set(d.id, d);
    } catch (_) {}
  }

  _sauver() {
    const garder = [...this.demandes.values()].filter(d => d.etat === 'attente' || d.etat === 'donnee' || d.etat === 'relayee');
    try { fs.writeFileSync(`${this.etatFichier}.tmp`, JSON.stringify({ lu: this.lu, demandes: garder }), { mode: 0o600 }); fs.renameSync(`${this.etatFichier}.tmp`, this.etatFichier); }
    catch (_) {}
  }

  _lire() {
    let taille = 0; try { taille = fs.statSync(this.fichier).size; } catch (_) { return; }
    if (taille < this.lu) this.lu = 0;
    if (taille === this.lu) return;
    const fd = fs.openSync(this.fichier, 'r');
    const b = Buffer.alloc(taille - this.lu);
    try { fs.readSync(fd, b, 0, b.length, this.lu); } finally { fs.closeSync(fd); }
    const texte = b.toString('utf8'), fin = texte.lastIndexOf('\n');
    if (fin < 0) return;
    this.lu += Buffer.byteLength(texte.slice(0, fin + 1));
    for (const l of texte.slice(0, fin).split('\n')) {
      let o; try { o = JSON.parse(l); } catch (_) { continue; }
      const module = o && o.module && PAQUET.test(String(o.module)) && NOM.test(String(o.sens)) && !SENS.has(o.sens) ? String(o.module) : null;
      if (!o || !ID.test(String(o.id)) || (!SENS.has(o.sens) && !module) || this.demandes.has(o.id)) continue;
      this.demandes.set(o.id, { id: o.id, sens: o.sens, module, ...(o.par === 'ahmed' ? { par: 'ahmed' } : {}), secondes: Math.max(0, Math.min(module ? 86400 : 900, Number(o.secondes) || 0)),
        cadence: /^(jeu|max|normal|\d{1,4}(\.\d{1,2})?)?$/.test(String(o.cadence || '')) ? String(o.cadence || '') : '',
        ts: Number(o.ts) * 1000 || this.maintenant(), etat: 'attente', essais: 0 });
    }
    this._sauver();
  }

  _echec(d, erreur) {
    d.etat = 'echec';
    this._noter({ id: d.id, sens: d.sens, secondes: d.secondes, ok: false, erreur, ...(d.par ? { par: d.par } : {}) });
  }

  _noter(o) {
    try { fs.appendFileSync(path.join(this.jarvis, 'sens-resultats.jsonl'), JSON.stringify({ ...o, ts: this.maintenant() / 1000 }) + '\n', { mode: 0o600 }); } catch (_) {}
    if (o.par !== 'ahmed') this.dire.push(o);                       // une mesure d'Ahmed ne réveille pas Hakim
    this.ressentir.push(o);                                         // (30/10) mais toutes se ressentent (son corps)
    this._sauver();
  }

  // les sens intégrés, puis les instruments de son Tricordeur (atelier/tricordeur/instruments.json, comme sens.py)
  instruments() {
    const r = Object.entries(INTEGRES).map(([nom, [description, defaut, max]]) => ({ nom, description, defaut, max }));
    let d = null; try { d = JSON.parse(fs.readFileSync(path.join(this.atelier, 'tricordeur', 'instruments.json'), 'utf8')); } catch (_) {}
    for (const x of (d && Array.isArray(d.instruments) ? d.instruments : []).slice(0, 30)) {
      if (!x || typeof x !== 'object') continue;
      const nom = String(x.nom || ''), module = String(x.module || 'ch.foldlab.hakim');
      if (!NOM.test(nom) || INTEGRES[nom] || !PAQUET.test(module) || r.some(y => y.nom === nom)) continue;
      const max = Math.max(1, Math.min(Number.parseInt(x.max, 10) || 3600, 86400)), defaut = Math.max(1, Math.min(Number.parseInt(x.defaut, 10) || 60, max));
      r.push({ nom, description: String(x.description || '').replace(/\s+/g, ' ').slice(0, 300), defaut, max, module });
    }
    return r;
  }

  // une mesure lancée par Ahmed : la même file que celles de Hakim
  demander({ sens, secondes, cadence } = {}) {
    const i = this.instruments().find(x => x.nom === String(sens || ''));
    if (!i) throw new Error(`sens inconnu : « ${String(sens || '').slice(0, 40)} »`);
    const s = Number.parseInt(secondes, 10) > 0 ? Math.min(Number.parseInt(secondes, 10), i.max || 0) : i.defaut;
    const c = String(cadence || '');
    if (c && !/^(jeu|max|normal|\d{1,4}(\.\d{1,2})?)$/.test(c)) throw new Error('cadence : jeu, max, normal ou un nombre de Hz');
    const z = (n) => String(n).padStart(2, '0'), t = new Date(this.maintenant());
    const id = `S-${t.getFullYear()}${z(t.getMonth() + 1)}${z(t.getDate())}-${z(t.getHours())}${z(t.getMinutes())}${z(t.getSeconds())}-${require('node:crypto').randomBytes(2).toString('hex')}`;
    const d = { id, sens: i.nom, secondes: s, cadence: c, ts: this.maintenant() / 1000, par: 'ahmed', ...(i.module ? { module: i.module } : {}) };
    fs.appendFileSync(this.fichier, JSON.stringify(d) + '\n', { mode: 0o600 });
    return d;
  }

  // la prochaine mesure pour le téléphone, ou null
  prochaine() {
    this._lire();
    const t = this.maintenant();
    for (const d of this.demandes.values()) {
      if ((d.etat === 'attente' || d.etat === 'donnee') && t - d.ts > EXPIRE_MS + (d.module ? d.secondes * 1000 : 0)) this._echec(d, "le téléphone n'a pas répondu (l'appli était fermée ?)");
      else if (d.etat === 'donnee' && t - d.donnee_ts > d.secondes * 1000 + MARGE_MS) {
        if (d.essais >= ESSAIS) this._echec(d, "le téléphone n'a rien rendu"); else d.etat = 'attente';
      }
    }
    const d = [...this.demandes.values()].filter(x => x.etat === 'attente').sort((a, b) => a.ts - b.ts)[0];
    if (!d) return null;
    d.etat = 'donnee'; d.donnee_ts = t; d.essais++;
    this._sauver();
    return { id: d.id, sens: d.sens, secondes: d.secondes, cadence: d.cadence, ...(d.module ? { module: d.module } : {}) };
  }

  _dossier(id) {
    if (!ID.test(String(id))) throw new Error('numéro de mesure invalide');
    const reel = (p) => { try { const s = fs.lstatSync(p); if (!s.isDirectory()) throw new Error('lien ou fichier à la place d’un dossier'); return true; } catch (e) { if (e.code === 'ENOENT') return false; throw e; } };
    const base = path.join(this.atelier, 'sens');
    if (!reel(this.atelier)) throw new Error('atelier introuvable');
    if (!reel(base)) fs.mkdirSync(base);
    if (!reel(base)) throw new Error('lien dans le chemin');
    const d = path.join(base, id);
    if (!reel(d)) fs.mkdirSync(d);
    if (!reel(d)) throw new Error('lien dans le chemin');
    return d;
  }

  _ecrire(f, octets) {
    try { if (fs.lstatSync(f).isSymbolicLink()) throw new Error('un lien à la place du fichier'); fs.unlinkSync(f); } catch (e) { if (e.code !== 'ENOENT') throw e; }
    const fd = fs.openSync(f, fs.constants.O_WRONLY | fs.constants.O_CREAT | fs.constants.O_EXCL | fs.constants.O_NOFOLLOW, 0o644);
    try { fs.writeSync(fd, octets); } finally { fs.closeSync(fd); }
  }

  donnees(id, octets) {
    this._ecrire(path.join(this._dossier(id), 'donnees.csv'), octets);
  }

  fini({ id, ok, erreur, resume }) {
    this._lire();
    const d = this.demandes.get(String(id));
    if (!d) throw new Error('mesure inconnue');
    const o = { id: d.id, sens: d.sens, secondes: d.secondes, ok: !!ok, erreur: String(erreur || '').slice(0, 300), resume: resume && typeof resume === 'object' ? resume : {} };
    this._ecrire(path.join(this._dossier(d.id), 'resume.json'), Buffer.from(JSON.stringify(o, null, 1)));
    d.etat = o.ok ? 'fini' : 'echec';
    this._noter({ id: o.id, sens: o.sens, secondes: o.secondes, ok: o.ok, erreur: o.erreur, ...(d.par ? { par: d.par } : {}) });
    return o;
  }

  // le téléphone a donné la mesure à son module : on attend son résultat dans ses Documents
  relais(id) {
    this._lire();
    const d = this.demandes.get(String(id));
    if (!d || !d.module) throw new Error('mesure inconnue, ou pas pour un module');
    d.etat = 'relayee'; d.relaye_ts = this.maintenant();
    this._sauver();
  }

  _relayees() {
    const t = this.maintenant();
    for (const d of this.demandes.values()) {
      if (d.etat !== 'relayee') continue;
      const dossier = path.join(this.telephone, 'Hakim', 'sens', d.id);
      let r = null;
      try { const st = fs.lstatSync(path.join(dossier, 'resume.json')); if (st.isFile() && st.size < 2 << 20) r = JSON.parse(fs.readFileSync(path.join(dossier, 'resume.json'), 'utf8')); } catch (_) {}
      if (r && typeof r === 'object') {
        try { const st = fs.lstatSync(path.join(dossier, 'donnees.csv')); if (st.isFile() && st.size < 60 << 20) this.donnees(d.id, fs.readFileSync(path.join(dossier, 'donnees.csv'))); } catch (_) {}
        try { this.fini({ id: d.id, ok: r.ok !== false, erreur: r.erreur, resume: r.resume || r }); } catch (_) {}
      } else if (t - d.relaye_ts > d.secondes * 1000 + MARGE_MODULE_MS) this._echec(d, "son module n'a rien rendu (Documents/Hakim/sens)");
    }
  }

  // (30/10, Ahmed : « relier toutes les sensations aux hormones ») les fins à ressentir, la sienne ou celle d'Ahmed (une fois)
  aRessentir() { return this.ressentir.splice(0); }

  // les fins pas encore dites à Hakim (une fois)
  aDire() { this._lire(); this._relayees(); return this.dire.splice(0); }
}

module.exports = { FileSens, ID };
