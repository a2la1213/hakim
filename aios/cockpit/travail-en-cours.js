/* Qui travaille encore (29/10, 17:05, Ahmed : « s'il y a un agent, elle doit m'interdire de relancer le truc, quel que
   soit X ») : les agents de Hakim au travail et ses tâches de fond en cours. Une relance du cockpit ou du démon les tuerait.
   - la relance proposée par Hakim et acceptée par Ahmed attend qu'il n'y ait plus personne (code.calme) ;
   - maman, avant toute relance : `node ~/AIOS/cockpit/travail-en-cours.js` (sortie 1 et la liste : on ne relance pas).
   Prudent : un agent noté au travail par le registre OU par la liste du cockpit compte. */
'use strict';
const fs = require('fs');
const os = require('os');
const path = require('path');

const objet = (x) => (x && typeof x === 'object' && !Array.isArray(x) ? x : {});
function lireJson(f) { try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch (_) { return null; } }
function vivant(pid) { try { process.kill(pid, 0); return true; } catch (e) { return e.code === 'EPERM'; } }

function travailEnCours(jarvis) {
  const agents = new Map();
  const liste = objet(lireJson(path.join(jarvis, 'agents-en-cours.json'))).agents;
  for (const a of Array.isArray(liste) ? liste : []) if (a && a.id) agents.set(String(a.id), String(a.description || '?'));
  for (const a of Object.values(objet(objet(lireJson(path.join(jarvis, 'registre-agents.json'))).agents)))
    if (objet(a).etat === 'travaille' && a.id && !agents.has(a.id)) agents.set(String(a.id), String(a.description || '?'));
  const taches = [];
  let noms = [];
  try { noms = fs.readdirSync(path.join(jarvis, 'cwd', 'taches')).filter(n => /^T-[\w-]+\.json$/.test(n)); } catch (_) {}
  for (const n of noms) {
    const t = objet(lireJson(path.join(jarvis, 'cwd', 'taches', n)));
    if (t.etat === 'en cours' && Number.isInteger(t.superviseur) && vivant(t.superviseur))
      taches.push({ id: String(t.id || n.slice(0, -5)), commande: String(t.commande || '').slice(0, 80) });
  }
  // (relecture du messager) un messager en route : une ancienne conversation rouverte, son agent peut-être au travail
  const messagers = [];
  let fichiers = [];
  try { fichiers = fs.readdirSync(path.join(jarvis, 'messager')).filter(n => n.endsWith('.pid.json')); } catch (_) {}
  for (const n of fichiers) {
    const m = objet(lireJson(path.join(jarvis, 'messager', n)));
    if (Number.isInteger(m.pid) && vivant(m.pid)) messagers.push({ id: String(m.id || '?'), session: String(m.session || '') });
  }
  return { agents: [...agents].map(([id, description]) => ({ id, description })), taches, messagers };
}

function texteTravail(t) {
  const morceaux = [];
  if (t.agents.length) morceaux.push(`${t.agents.length} agent${t.agents.length > 1 ? 's' : ''} au travail (${t.agents.map(a => `« ${a.description} »`).join(', ')})`);
  if (t.taches.length) morceaux.push(`${t.taches.length} tâche${t.taches.length > 1 ? 's' : ''} de fond (${t.taches.map(x => x.id).join(', ')})`);
  if ((t.messagers || []).length) morceaux.push(`${t.messagers.length} messager${t.messagers.length > 1 ? 's' : ''} en route`);
  return morceaux.join(' et ');
}

if (require.main === module) {
  const t = travailEnCours(process.env.JARVIS_DIR || path.join(os.homedir(), 'AIOS', 'jarvis'));
  if (t.agents.length || t.taches.length || t.messagers.length) {
    console.log(`NON : ${texteTravail(t)}. Une relance les tuerait : on attend qu'ils aient fini ou se soient endormis.`);
    process.exit(1);
  }
  console.log('OUI : aucun agent ni tâche de fond ne travaille.');
}
module.exports = { travailEnCours, texteTravail };
