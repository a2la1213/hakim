/* Le code de Hakim, avec maman, validé par Ahmed (28/10 ; plan anamnese/docs/superpowers/plans/2026-10-28-hakim-code-avec-
   maman.md, tâches 5 et 6). Ahmed : « je valide avant que ça s'applique » ; « toujours avec ta maman ».

   Une promotion (chantiers.proposer, côté Anamnèse) ne s'applique que si TOUT est vrai au moment du geste :
   - l'interrupteur « code » est allumé (par un geste d'Ahmed ; éteint par défaut) ;
   - maman a donné un avis FAVORABLE pour CE sha256 (anamnese/data/avis/<id>.json, écrit par maman.py ou `anamnese avis`) ;
   - les tests de cet arbre ont réussi ; le patch qui fait foi (PRIVE) a toujours son sha256 ;
   - la liste ouverte la laisse passer (revérifiée par anamnese/jarvis/liste_ouverte.py : une seule implémentation) ;
   - `git apply --check` passe et les fichiers touchés n'ont aucun changement local ;
   - elle n'a été ni refusée, ni déjà appliquée.
   Alors UN commit à part, réversible (« Annuler » : git revert). Chaque étape va dans le journal « en off ».
   FERMÉ : ce module n'est pas dans la liste ouverte. */
'use strict';
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const os = require('os');
const { execFile } = require('child_process');

const ID = /^[0-9]{8}-[0-9]{6}-[a-z0-9-]+$/;
const lireJson = (f, defaut = null) => { try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch (_) { return defaut; } };
const sha256 = (b) => crypto.createHash('sha256').update(b).digest('hex');

function noter(lieux, o) {
  fs.appendFileSync(lieux.journal, JSON.stringify({ ts: Date.now() / 1000, ...o }) + '\n', { mode: 0o600 });
}
function journal(lieux) {
  let t = ''; try { t = fs.readFileSync(lieux.journal, 'utf8'); } catch (_) {}
  return t.split('\n').filter(Boolean).map(l => { try { return JSON.parse(l); } catch (_) { return null; } }).filter(Boolean);
}
function statut(id, lignes) {
  let s = 'proposée', commit = null;
  for (const l of lignes) {
    if (l.type !== 'promotion' || l.id !== id) continue;
    if (['appliquée', 'refusée', 'annulée'].includes(l.etape)) { s = l.etape; if (l.commit) commit = l.commit; }
  }
  return { statut: s, commit };
}

const actif = (lieux) => !!(lireJson(lieux.interrupteur, {}) || {}).actif;
function basculerInterrupteur(lieux, oui) {
  fs.writeFileSync(lieux.interrupteur, JSON.stringify({ actif: !!oui, ts: Date.now() }), { mode: 0o600 });
  noter(lieux, { type: 'interrupteur', actif: !!oui });
}

function fiche(id, lieux) {
  if (!ID.test(String(id || ''))) return null;
  return lireJson(path.join(lieux.prive, `${id}.json`));
}

// (relecture finale, I4) le patch qui fait foi se lit par son id dans PRIVE, jamais par un chemin écrit dans la fiche
const cheminPatch = (id, lieux) => path.join(lieux.prive, `${id}.patch`);
// (M1) sous l'empreinte : ni caractère de contrôle, ni caractère de direction (RLO…), ni retour à la ligne
const propre = (t) => String(t || '').replace(/[\u0000-\u001f\u007f\u200e\u200f\u202a-\u202e\u2066-\u2069]/g, ' ').replace(/\s+/g, ' ').trim();

function etat(lieux) {
  const lignes = journal(lieux);
  let noms = []; try { noms = fs.readdirSync(lieux.prive).filter(n => /^[0-9]{8}-[0-9]{6}-[a-z0-9-]+\.json$/.test(n)); } catch (_) {}
  const promotions = noms.sort().reverse().slice(0, 30).map(n => {
    const f = lireJson(path.join(lieux.prive, n)) || {};
    const a = lireJson(path.join(lieux.avis, n));
    let patch = ''; try { patch = fs.readFileSync(cheminPatch(f.id, lieux), 'utf8').slice(0, 20000); } catch (_) {}
    return { id: f.id, projet: f.projet, resume: String(f.resume || '').slice(0, 1200), fichiers: (f.fichiers || []).slice(0, 40), patch,
      tests_ok: !!f.tests_ok, sha: f.patch_sha256, externe: f.externe || [], cree: f.cree || null,
      avis: a && a.sha === f.patch_sha256 ? { verdict: a.verdict, texte: String(a.texte || '').slice(0, 2000), source: a.source, ts: a.ts } : null,
      ...statut(f.id, lignes) };
  });
  return { actif: actif(lieux), promotions, relances: lieux.relances ? relances(lieux) : [] };
}

function git(args, cwd, env) {
  return new Promise((ok, ko) => execFile('git', args, { cwd, timeout: 60000, maxBuffer: 1 << 24, env: env ? { ...process.env, ...env } : process.env },
    (e, so, se) => (e ? ko(new Error(String(se || e.message).trim().slice(0, 300))) : ok(so))));
}

// (relecture finale, I3 et I4) une seule préparation : les octets du patch lus UNE fois (par l'id), leur sha vérifié, copiés
// dans un dossier temporaire ; appliqués dans un index temporaire sur HEAD, et c'est le diff que git en tire qui passe la
// liste ouverte (des numéros de ligne à jour) ; puis les mêmes octets s'appliquent
async function preparer(id, lieux, { refus }) {
  const f = fiche(id, lieux);
  if (!f) return { raison: 'promotion inconnue' };
  if (!actif(lieux)) return { raison: "l'interrupteur « code » est éteint" };
  const st = statut(id, journal(lieux)).statut;
  if (st === 'appliquée') return { raison: 'déjà appliquée' };
  if (st === 'refusée') return { raison: 'tu l’as refusée' };
  const a = lireJson(path.join(lieux.avis, `${id}.json`));
  if (!a) return { raison: 'pas encore d’avis de maman' };
  if (a.sha !== f.patch_sha256) return { raison: 'l’avis de maman porte sur un autre patch' };
  if (a.verdict !== 'favorable') return { raison: 'maman a donné un avis défavorable' };
  if (!f.tests_ok) return { raison: 'les tests de ce chantier ont échoué' };
  let octets; try { octets = fs.readFileSync(cheminPatch(id, lieux)); } catch (_) { return { raison: 'le patch qui fait foi est introuvable' }; }
  if (sha256(octets) !== f.patch_sha256) return { raison: 'le patch qui fait foi a changé depuis la proposition' };
  const depot = (lieux.projets || {})[f.projet];
  if (!depot) return { raison: `projet inconnu : ${f.projet}` };
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'promotion-'));
  const fin = () => { try { fs.rmSync(tmp, { recursive: true, force: true }); } catch (_) {} };
  const patch = path.join(tmp, 'patch'), regen = path.join(tmp, 'regenere.patch'), index = { GIT_INDEX_FILE: path.join(tmp, 'index') };
  fs.writeFileSync(patch, octets, { mode: 0o600 });
  try {
    const locaux = (await git(['status', '--porcelain', '--', ...f.fichiers], depot)).trim();
    if (locaux) { fin(); return { raison: 'des fichiers touchés ont des changements locaux : rien n’est appliqué' }; }
    await git(['apply', '--check', patch], depot);
    await git(['read-tree', 'HEAD'], depot, index);
    await git(['apply', '--cached', patch], depot, index);
    fs.writeFileSync(regen, await git(['diff', '--cached', '--no-renames', '--binary', 'HEAD'], depot, index), { mode: 0o600 });
  } catch (e) { fin(); return { raison: `ne s’applique pas proprement : ${e.message}` }; }
  const r = await refus(f.projet, regen, depot);
  if (r.length) { fin(); return { raison: 'fermé par la liste ouverte : ' + r.slice(0, 3).join(' ; ') }; }
  return { raison: null, f, depot, patch, fin };
}

async function peutAppliquer(id, lieux, deps) {
  const p = await preparer(id, lieux, deps);
  if (p.fin) p.fin();
  return p.raison;
}

async function appliquer(id, lieux, deps) {
  const p = await preparer(id, lieux, deps);
  if (p.raison) throw new Error(p.raison);
  const { f, depot } = p;
  try {
    await git(['apply', p.patch], depot);
    const date = new Date().toLocaleString('fr-FR', { timeZone: 'Europe/Paris' });
    const message = `Promotion ${id} (Hakim ; avis favorable de maman ; validée par Ahmed le ${date})\n\n`
      + `${String(f.resume || '').slice(0, 1500)}\n\nsha256 du patch : ${f.patch_sha256}`;
    await git(['add', '--', ...f.fichiers.filter(c => fs.existsSync(path.join(depot, c)))], depot).catch(() => {});
    await git(['-c', 'user.name=Hakim (validé par Ahmed)', '-c', 'user.email=hakim@localhost', 'commit', '-q', '-m', message, '--', ...f.fichiers], depot);
    const commit = (await git(['rev-parse', 'HEAD'], depot)).trim();
    noter(lieux, { type: 'promotion', etape: 'appliquée', id, sha: f.patch_sha256, commit });
    return { commit };
  } finally { p.fin(); }
}

async function annuler(id, lieux) {
  const f = fiche(id, lieux);
  const { statut: s, commit } = statut(id, journal(lieux));
  if (!f || s !== 'appliquée' || !commit) throw new Error('rien à annuler');
  const depot = lieux.projets[f.projet];
  await git(['-c', 'user.name=Hakim (annulé par Ahmed)', '-c', 'user.email=hakim@localhost', 'revert', '--no-edit', commit], depot);
  noter(lieux, { type: 'promotion', etape: 'annulée', id, sha: f.patch_sha256, commit });
}

function refuser(id, lieux) {
  const f = fiche(id, lieux);
  if (!f) throw new Error('promotion inconnue');
  noter(lieux, { type: 'promotion', etape: 'refusée', id, sha: f.patch_sha256 });
}

// le geste : une action liée à UNE promotion (ses 12 premiers caractères de sha), et le texte que l'appli affiche
const actionGeste = (quoi, sha) => `code:${quoi}:${String(sha || '').slice(0, 12)}`;
const actionListe = (nom, etat) => 'code:liste:' + sha256(`${nom}|${etat}`).slice(0, 12);
function texteGeste(action, lieux, details = {}) {
  const m = /^code:(appliquer|annuler|refuser|interrupteur|liste|relancer|refuser-relance):([0-9a-f-]{1,40})$/.exec(String(action || ''));
  if (!m) return null;
  if (m[1] === 'relancer' || m[1] === 'refuser-relance') {
    const r = relances(lieux).find(x => x.etat === 'proposée' && sha256(String(x.id)).slice(0, 12) === m[2]);
    if (!r) return null;
    const quoi = r.quoi === 'demon' ? 'le démon (sa mémoire)' : 'le cockpit';
    return m[1] === 'relancer' ? `Relancer ${quoi}, proposé par Hakim : « ${propre(r.raison).slice(0, 80)} » (au calme)` : `Refuser la relance de ${quoi}`;
  }
  if (m[1] === 'interrupteur') return m[2] === '1' ? 'Allumer « code » : Hakim pourra faire appliquer ses modifications (avec maman, et ta validation)' : 'Éteindre « code »';
  if (m[1] === 'liste') {
    const nom = String(details.nom || ''), e = String(details.etat || '');
    if (!nom || actionListe(nom, e) !== action) return null;
    return `${e === 'ouvert' ? 'Ouvrir' : 'Fermer'} « ${nom.slice(0, 80)} » ${e === 'ouvert' ? 'à' : 'pour'} Hakim (liste ouverte)`;
  }
  const p = etat(lieux).promotions.find(x => String(x.sha || '').startsWith(m[2]));
  if (!p) return null;
  const quoi = { appliquer: 'Appliquer', annuler: 'Annuler', refuser: 'Refuser' }[m[1]];
  const n = (p.fichiers || []).length;
  return `${quoi} la modification de Hakim « ${propre(p.resume).slice(0, 80)} » (${n} fichier${n > 1 ? 's' : ''}, `
    + `${p.tests_ok ? 'tests réussis' : 'tests EN ÉCHEC'}${p.externe && p.externe.length ? ', contenu externe lu' : ''}`
    + `${p.avis ? `, avis de maman : ${p.avis.verdict}` : ''})`;
}

// (tâche 6, Ahmed 03:40 : « ouvrir ou fermer chacun, donner l'autorisation ou pas selon le besoin ») une ligne de la liste
// ouverte, basculée d'un geste : le fichier change (cette ligne seulement) et un commit à part le garde
async function basculerListe(nom, etatVoulu, lieux) {
  if (!['ouvert', 'ferme'].includes(etatVoulu)) throw new Error('état : ouvert ou ferme');
  const liste = lireJson(lieux.liste);
  const ligne = liste && (liste.groupes || []).flatMap(g => g.fichiers || []).find(f => f.nom === nom);
  if (!ligne) throw new Error('ligne inconnue');
  if (etatVoulu === 'ouvert' && !(ligne.chemins || []).length) throw new Error('cette ligne ne s’ouvre pas d’un geste (pas de fichier précis)');
  if (ligne.etat === etatVoulu) return { change: false };
  ligne.etat = etatVoulu;
  fs.writeFileSync(lieux.liste, JSON.stringify(liste, null, 1) + '\n');
  const rel = path.relative(lieux.depotListe, lieux.liste);
  await git(['-c', 'user.name=Ahmed (geste)', '-c', 'user.email=ahmed@localhost', 'commit', '-q', '-m',
    `Liste ouverte : Ahmed ${etatVoulu === 'ouvert' ? 'ouvre' : 'ferme'} « ${nom} »`, '--', rel], lieux.depotListe);
  noter(lieux, { type: 'liste', nom, etat: etatVoulu });
  return { change: true };
}

// ---- (tâche 8, Ahmed 03:01 : « que tu puisses relancer toi-même le cockpit et le démon, sur validation de moi ») les relances
// proposées par Hakim (anamnese/relances.py), acceptées d'un geste ; faites au CALME, d'une seule commande littérale
const LABELS = { demon: 'com.anamnese.daemon', cockpit: 'com.aios.cockpit' };
// (relecture finale, I6) un tour peut durer jusqu'à 2 h (JARVIS_DUREE_MAX) : au-delà de 2 h 15, c'est un tour oublié
const TOUR_OUBLIE_MS = 135 * 60_000;
// (29/10, Ahmed : « s'il y a un agent, elle doit m'interdire de relancer le truc, quel que soit X ») travail : un agent ou
// une tâche de fond travaille encore (travail-en-cours.js) ; une relance les tuerait
function calme({ tours, maman, testsChantier, travail }, maintenant = Date.now()) {
  const enCours = [...(tours || new Map()).values()].some(t => Number.isFinite(t && t.debut) && maintenant - t.debut < TOUR_OUBLIE_MS);
  return !enCours && !maman && !testsChantier && !travail;
}
function relances(lieux) {
  let noms = []; try { noms = fs.readdirSync(lieux.relances).filter(n => /^[0-9a-z-]+\.json$/.test(n)); } catch (_) {}
  return noms.sort().reverse().slice(0, 10).map(n => lireJson(path.join(lieux.relances, n))).filter(Boolean);
}
function ecrireRelance(lieux, r) { fs.writeFileSync(path.join(lieux.relances, `${r.id}.json`), JSON.stringify(r), { mode: 0o600 }); }
function relance(id, lieux) {
  if (!/^[0-9a-z-]{1,60}$/.test(String(id || ''))) return null;
  return lireJson(path.join(lieux.relances, `${id}.json`));
}
const actionRelance = (id, accepter) => `code:${accepter ? 'relancer' : 'refuser-relance'}:${sha256(String(id)).slice(0, 12)}`;
function refuserRelance(id, lieux) {
  const r = relance(id, lieux);
  if (!r || r.etat !== 'proposée') throw new Error('aucune relance en attente avec cet identifiant');
  ecrireRelance(lieux, { ...r, etat: 'refusée' });
  noter(lieux, { type: 'relance', etape: 'refusée', id, quoi: r.quoi });
}
async function accepterRelance(id, lieux, { estCalme, attendre, pas_ms = 2000, calme_ms = 20000, max_ms = 600000, uid, lancer, pourquoi, signaler }) {
  const r = relance(id, lieux);
  if (!r || r.etat !== 'proposée') throw new Error('aucune relance en attente avec cet identifiant');
  ecrireRelance(lieux, { ...r, etat: 'acceptée' });
  noter(lieux, { type: 'relance', etape: 'acceptée', id, quoi: r.quoi });
  let calmeDepuis = null, dit = '';
  for (let t = 0; t <= max_ms; t += pas_ms) {
    if (estCalme()) { calmeDepuis = calmeDepuis === null ? t : calmeDepuis; if (t - calmeDepuis >= calme_ms) break; }
    else {
      calmeDepuis = null;
      // (29/10) Ahmed voit pourquoi elle attend : qui travaille encore (une fois par raison)
      const raison = pourquoi ? String(pourquoi() || '') : '';
      if (raison && raison !== dit && signaler) { dit = raison; signaler(raison); }
    }
    if (t + pas_ms > max_ms) {
      ecrireRelance(lieux, { ...r, etat: 'pas de calme' });
      noter(lieux, { type: 'relance', etape: 'pas de calme', id, quoi: r.quoi });
      return { etape: 'pas de calme' };
    }
    await attendre(pas_ms);
  }
  ecrireRelance(lieux, { ...r, etat: 'faite', faite_ts: Date.now() / 1000 });
  noter(lieux, { type: 'relance', etape: 'faite', id, quoi: r.quoi });
  lancer('launchctl', ['kickstart', '-k', `gui/${uid}/${LABELS[r.quoi]}`]);
  return { etape: 'faite' };
}

module.exports = { etat, peutAppliquer, appliquer, annuler, refuser, basculerInterrupteur, basculerListe, actionGeste, actionListe, texteGeste, fiche,
  calme, relances, relance, accepterRelance, refuserRelance, actionRelance, LABELS };
