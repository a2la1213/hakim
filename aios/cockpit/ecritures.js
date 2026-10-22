/* Les écritures de Hakim dans les projets d'Ahmed, une à une (demande de Hakim, accord d'Ahmed le 2026-10-22 : « je suis
   ok pour tout sauf le point 8 »). Côté Hakim : anamnese/mcp_server.py, proposer_ecriture.

   - Hakim DÉPOSE une proposition précise dans ~/AIOS/jarvis/ecritures (son serveur MCP seul y écrit) : un projet, un
     fichier, le texte exact à remplacer et le nouveau (ou un fichier neuf), la raison.
   - Le cockpit la relit et refait TOUTES les vérifications (les mêmes que les missions : projetPermis, refusEcriture,
     CACHES ; et ici : fichier dans le projet, pas de lien, texte à remplacer présent une seule fois, taille). Il en
     garde SA copie avec son empreinte (~/AIOS/jarvis/ecritures-cockpit) : ce qu'Ahmed a lu est ce qui s'applique.
   - RIEN ne s'écrit sans le geste d'Ahmed (Appliquer : jeton de la page, et passkey depuis le téléphone).
   - Appliquée : le projet doit être un dépôt git et le fichier sans modification en cours ; le texte est remplacé, puis
     un commit À PART, de ce seul fichier (« Hakim : <raison> (validé par Ahmed) »), sans crochets. « Annuler » fait un
     git revert de ce commit : la modification se défait par un nouveau commit, l'historique reste. */
'use strict';
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { execFileSync } = require('child_process');
const { projetPermis, refusEcriture, CACHES, masquer } = require('./missions.js');

const ID = /^E-\d{8}-\d{6}-[0-9a-f]{4}$/;
const TAILLE_MAX = 200 * 1024;
const GIT = ['/Applications/Xcode.app/Contents/Developer/usr/bin/git', '/usr/bin/git'].find(g => fs.existsSync(g)) || 'git';

function git(projet, args) {
  return execFileSync(GIT, ['-C', projet, '-c', 'core.hooksPath=/dev/null', '-c', 'commit.gpgsign=false', ...args],
    { encoding: 'utf8', timeout: 30000, stdio: ['ignore', 'pipe', 'pipe'] }).trim();
}

class Ecritures {
  constructor({ dossier, donnees, maison, evenement = () => {} }) {
    Object.assign(this, { dossier, donnees, maison, evenement });
    fs.mkdirSync(donnees, { recursive: true, mode: 0o700 });
    this.fichier = path.join(donnees, 'ecritures.json');
    this.journal = path.join(donnees, 'ecritures.jsonl');
    this.ecritures = {};
    try { this.ecritures = JSON.parse(fs.readFileSync(this.fichier, 'utf8')).ecritures || {}; } catch (_) {}
  }

  sauver() {
    const tmp = `${this.fichier}.${process.pid}.tmp`;
    fs.writeFileSync(tmp, JSON.stringify({ ecritures: this.ecritures }), { mode: 0o600 });
    fs.renameSync(tmp, this.fichier);
  }

  noter(e, etat, plus = {}) {
    Object.assign(e, plus, { etat, maj: Date.now() });
    try { fs.appendFileSync(this.journal, JSON.stringify({ ts: Date.now() / 1000, id: e.id, etat, ...plus }) + '\n'); } catch (_) {}
    try { this.sauver(); } catch (_) {}
    try { this.evenement(etat, e); } catch (_) {}
  }

  // Le fichier visé, vérifié : dans un projet permis, en écriture permise, hors des chemins qui s'exécutent seuls.
  verifier(f) {
    const projet = projetPermis(String(f.projet || '').replace(/^~(?=\/|$)/, this.maison), this.maison);
    const refus = refusEcriture(projet, this.maison);
    if (refus) throw new Error(refus);
    const rel = String(f.fichier || '');
    if (!rel || path.isAbsolute(rel) || rel.split(/[\\/]/).some(x => x === '..' || x === '')) throw new Error('chemin de fichier invalide (relatif au projet, sans « .. »)');
    if (rel.split(/[\\/]/).some(x => CACHES.includes(x) || x.startsWith('.env'))) throw new Error('chemin protégé (git, réglages, dépendances, environnement, secrets)');
    const cible = path.join(projet, rel);
    let reelle = null; try { reelle = fs.realpathSync(cible); } catch (_) {}
    if (reelle && reelle !== cible) throw new Error('le fichier est un lien : refusé');
    const parent = (() => { try { return fs.realpathSync(path.dirname(cible)); } catch (_) { return null; } })();
    if (!parent || !(parent === projet || parent.startsWith(projet + path.sep))) throw new Error('dossier du fichier introuvable ou hors du projet');
    if (String(f.nouveau).length > TAILLE_MAX || String(f.ancien).length > TAILLE_MAX) throw new Error('proposition trop grosse (200 Ko au plus)');
    const existe = fs.existsSync(cible);
    if (!f.ancien) { if (existe) throw new Error('le fichier existe déjà : donne le texte exact à remplacer'); }
    else {
      if (!existe) throw new Error('fichier introuvable');
      const t = fs.readFileSync(cible, 'utf8');
      const n = t.split(String(f.ancien)).length - 1;
      if (n !== 1) throw new Error(n ? `le texte à remplacer apparaît ${n} fois : il doit être unique` : 'le texte à remplacer est introuvable dans le fichier');
    }
    try { git(projet, ['rev-parse', '--is-inside-work-tree']); } catch (_) { throw new Error("le projet n'est pas un dépôt git : rien ne serait réversible"); }
    return { projet, cible, rel };
  }

  scruter() {
    let noms = []; try { noms = fs.readdirSync(this.dossier).filter(n => n.endsWith('.json')); } catch (_) { return; }
    for (const n of noms) {
      const id = n.slice(0, -5);
      if (!ID.test(id) || this.ecritures[id]) continue;
      let f; try { f = JSON.parse(fs.readFileSync(path.join(this.dossier, n), 'utf8')); } catch (_) { continue; }
      const e = { id, recu: Date.now(), projet: String(f.projet || '').slice(0, 400), fichier: String(f.fichier || '').slice(0, 400),
        ancien: String(f.ancien || ''), nouveau: String(f.nouveau || ''), raison: String(f.raison || '').slice(0, 400) };
      e.empreinte = crypto.createHash('sha256').update(JSON.stringify([e.projet, e.fichier, e.ancien, e.nouveau])).digest('hex').slice(0, 16);
      this.ecritures[id] = e;
      try { const v = this.verifier(e); e.projet = v.projet; this.noter(e, 'proposee'); }
      catch (err) { this.noter(e, 'invalide', { raison_refus: String(err.message || err).slice(0, 300) }); }
    }
  }

  trancher(id, action, empreinte) {
    const e = this.ecritures[id];
    if (!e) throw new Error('écriture inconnue');
    if (action === 'refuser') { if (e.etat !== 'proposee') throw new Error('déjà tranchée'); this.noter(e, 'refusee'); return e; }
    if (action === 'annuler') {
      if (e.etat !== 'appliquee' || !e.commit) throw new Error("rien à annuler : elle n'est pas appliquée");
      let sortie;
      try { sortie = git(e.projet, ['revert', '--no-edit', e.commit]); }
      catch (err) {                                                      // un conflit : on n'en laisse aucune trace à moitié
        try { git(e.projet, ['revert', '--abort']); } catch (_) {}
        throw new Error(`annulation impossible (le fichier a changé depuis) : ${String(err.stderr || err.message || err).slice(0, 200)}`);
      }
      this.noter(e, 'annulee', { revert: git(e.projet, ['rev-parse', '--short', 'HEAD']), sortie: masquer(sortie).slice(0, 300) });
      return e;
    }
    if (action !== 'appliquer') throw new Error('action inconnue');
    if (e.etat !== 'proposee') throw new Error('déjà tranchée');
    if (empreinte !== e.empreinte) throw new Error("la proposition a changé depuis que tu l'as lue : recharge la page");
    const { projet, cible, rel } = this.verifier(e);                       // tout revérifié au moment du geste
    if (git(projet, ['status', '--porcelain', '--', rel])) throw new Error('le fichier a des modifications en cours : rien n’est écrit');
    const avant = fs.existsSync(cible) ? fs.readFileSync(cible, 'utf8') : null;
    fs.writeFileSync(cible, avant === null ? e.nouveau : avant.replace(e.ancien, () => e.nouveau));
    try {
      git(projet, ['add', '--', rel]);
      git(projet, ['commit', '--no-verify', '--only', '-m', `Hakim : ${e.raison || 'modification proposée'} (validé par Ahmed)`, '--', rel]);
    } catch (err) {
      if (avant === null) fs.unlinkSync(cible); else fs.writeFileSync(cible, avant);   // rien de fait à moitié
      try { git(projet, ['reset', '-q', '--', rel]); } catch (_) {}
      throw new Error(`commit impossible : ${String(err.stderr || err.message || err).slice(0, 200)}`);
    }
    this.noter(e, 'appliquee', { commit: git(projet, ['rev-parse', '--short', 'HEAD']) });
    return e;
  }

  publique(e) {
    const { id, recu, projet, fichier, raison, etat, empreinte, commit, revert, raison_refus } = e;
    return { id, recu, projet: path.relative(this.maison, projet) || projet, fichier, raison, etat, empreinte, commit, revert, raison_refus,
      ancien: masquer(e.ancien).slice(0, 4000), nouveau: masquer(e.nouveau).slice(0, 4000) };
  }

  liste() { return Object.values(this.ecritures).sort((a, b) => a.recu - b.recu).slice(-30).map(e => this.publique(e)); }
}

module.exports = { Ecritures, ID };
