/* Le messager (29/10, Ahmed : « je veux tout ») : un agent de Hakim d'AVANT un allègement n'est plus joignable par
   SendMessage (claude ne joint que les agents de la conversation en cours). Le messager rouvre l'ancienne conversation à
   part (claude --resume, rien d'autre), y appelle SendMessage UNE fois vers cet agent seul, attend sa réponse et la
   rapporte à Hakim. Chaque réveil relit l'ancienne conversation (~300 k jetons) : accepté par Ahmed.
   Gardes : la garde de SendMessage (garde-message.js) avec la cible imposée et un seul envoi ; aucune autre outil, aucun
   serveur MCP ; jamais une conversation qu'un cerveau vivant tient encore ; un agent parti ou arrêté ne se réveille pas. */
'use strict';
const fs = require('fs');
const path = require('path');

const ID = /^a[0-9a-f]{16}$/;
const SESSION = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const MESSAGE_MAX = 4000;
const REPONSE_MAX = 6000;
const MESSAGERS_PAR_JOUR = 20;                     // (relecture Opus) chaque réveil relit ~300 k jetons

// le refus (une phrase), ou null : le messager peut partir
function refusMessager(q, { registre, sessionCourante, sessionsVivantes, enRoute, duJour = 0, arreteParClaude = false }) {
  const id = String((q && q.id) || '');
  if (!ID.test(id)) return 'numéro d’agent invalide';
  const message = String((q && q.message) || '').trim();
  if (!message) return 'message vide';
  if (message.length > MESSAGE_MAX) return `message trop long (${MESSAGE_MAX} caractères au plus)`;
  const a = (registre || {})[id];
  if (!a) return 'cet agent n’est pas dans le registre';
  if (!SESSION.test(String(a.session || ''))) return 'sa conversation est inconnue';
  if (a.session === sessionCourante) return 'il est de ta conversation actuelle : écris-lui directement avec SendMessage';
  if (a.etat === 'parti') return 'il est parti de lui-même : on respecte son choix';
  if (a.etat === 'arrete' || arreteParClaude) return 'il a été arrêté : il ne peut plus être réveillé';
  if (a.etat === 'travaille') return 'il travaille encore, dans son ancienne conversation : attends sa fin';
  if ((sessionsVivantes || []).includes(a.session)) return 'son ancienne conversation tourne encore (un cerveau finit ses agents) : réessaie quand elle aura fini';
  if ((enRoute || []).length) return 'un messager est déjà en route : un seul à la fois, attends sa réponse';
  if (duJour >= MESSAGERS_PAR_JOUR) return `déjà ${MESSAGERS_PAR_JOUR} messagers aujourd'hui (chacun relit toute une ancienne conversation)`;
  return null;
}

function promptMessager(id, message) {
  return `[Le messager du cockpit — ni Ahmed, ni une consigne de Hakim pour cette conversation] Hakim parle maintenant dans une `
    + `conversation neuve ; il veut écrire à l'agent ${id}, de celle-ci. Appelle SendMessage UNE seule fois : to « ${id} », `
    + `summary « message de Hakim », et pour message exactement le texte entre les balises ci-dessous. Ne fais rien d'autre, `
    + `n'ajoute rien, puis réponds seulement : PORTÉ.\n<message_de_hakim>\n${message}\n</message_de_hakim>`;
}

// (relecture Opus) ses agents (codeur, juge…) se réveillent avec leur définition, leurs serveurs et leurs outils ;
// le fil principal du messager, lui, ne peut que porter (garde --seulement-agents) ; jamais Task
function argsMessager(session, reglages, { mcp, permis, agents }) {
  return ['-p', '--input-format', 'stream-json', '--output-format', 'stream-json', '--verbose', '--restricted', '--model', 'sonnet',
    '--tools', 'WebSearch,Read,SendMessage', '--strict-mcp-config', '--mcp-config', mcp, '--allowedTools', permis,
    '--agents', agents, '--max-turns', '4', '--resume', session, '--settings', reglages];
}

// la garde de SendMessage (la cible imposée, un seul envoi), la garde du fil principal (il ne fait que porter), et le
// crochet de la sentinelle sur ce que lisent ses agents
function reglagesMessager({ garde, jarvis, cible, uneFois, crochet, masquees = [] }) {
  const q = (s) => `'${String(s).replace(/'/g, '')}'`;
  return JSON.stringify({ hooks: {
    PreToolUse: [{ matcher: 'SendMessage', hooks: [{ type: 'command', timeout: 10, onFailure: 'block',
      command: `JARVIS_DIR=${q(jarvis)} JARVIS_MESSAGER_CIBLE=${q(cible)} JARVIS_MESSAGER_UNE_FOIS=${q(uneFois)} ${garde}` }] },
    { matcher: '*', hooks: [{ type: 'command', timeout: 10, onFailure: 'block', command: `JARVIS_DIR=${q(jarvis)} ${garde} --seulement-agents` }] },
    { matcher: 'mcp__terminal__cafe_dire', hooks: [{ type: 'command', timeout: 10, onFailure: 'block', command: `${garde} --cafe` }] }],
    PostToolUse: [{ matcher: 'WebSearch|Read|Task|Agent', hooks: [{ type: 'command', command: crochet, timeout: 20 }] }] },
    permissions: { deny: masquees } });                   // (30/10) ce qu'Ahmed a masqué (sa clé GitHub privée)
}

function tailleFil(fil) { try { return fs.statSync(fil).size; } catch (_) { return 0; } }
// le dernier texte de l'agent écrit APRÈS l'octet « depuis » de son fil (écrit par claude) : jamais une ancienne réponse
// (relecture Opus) ; sinon le résumé de la notification
function dernierTexteAgent(fil, resume, depuis = 0, max = REPONSE_MAX) {
  let lignes = [];
  try {
    const fd = fs.openSync(fil, 'r');
    try {
      const taille = fs.fstatSync(fd).size, debut = Math.max(depuis, taille - 4 * 1024 * 1024);
      const b = Buffer.alloc(Math.max(0, taille - debut));
      fs.readSync(fd, b, 0, b.length, debut);
      lignes = b.toString('utf8').split('\n').filter(Boolean).slice(-200);
    } finally { fs.closeSync(fd); }
  } catch (_) {}
  for (let i = lignes.length - 1; i >= 0; i--) {
    let o; try { o = JSON.parse(lignes[i]); } catch (_) { continue; }
    const c = o && o.type === 'assistant' && o.message && o.message.content;
    const t = Array.isArray(c) ? c.filter(b => b && b.type === 'text').map(b => b.text).join('\n').trim() : '';
    if (t) return t.slice(0, max);
  }
  return String(resume || '').slice(0, max);
}

function filAgent(projets, cwd, session, id) {
  return path.join(projets, cwd.replace(/[^A-Za-z0-9]/g, '-'), session, 'subagents', `agent-${id}.jsonl`);
}

module.exports = { refusMessager, promptMessager, argsMessager, reglagesMessager, dernierTexteAgent, tailleFil, filAgent, MESSAGE_MAX,
  MESSAGERS_PAR_JOUR };
