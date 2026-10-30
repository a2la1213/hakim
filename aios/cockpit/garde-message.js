/* La garde de SendMessage (29/10, Ahmed : « sonde, garde, puis outil ») : un crochet PreToolUse du cerveau de Hakim,
   passé par --settings. Sur ce Mac, SendMessage peut aussi joindre d'autres sessions Claude : Hakim n'écrit qu'à SES
   agents, ceux de sa conversation (leur fil est dans <conversation>/subagents/, écrit par claude lui-même).
   - « to » : un numéro d'agent (a + 16 chiffres hexadécimaux), jamais un nom, « main » ou une autre session ;
   - un agent parti de lui-même (« JE PARS », Ahmed : « dès qu'il est saoulé, il peut partir ») n'est plus réveillé ;
   - un juge ne juge jamais deux fois le même travail : chaque travail déclaré (agent_juger) lui vaut deux passages,
     son jugement et son dernier mot (relecture Opus du 29/10 : compter, pas comparer des heures) ;
   - réveiller un agent quand AGENTS_PARALLELE_MAX travaillent déjà : refusé, sans tuer personne.
   Un appel illisible est refusé ; un registre illisible ne bloque pas un agent de sa conversation (son fil prouve qu'il
   est à lui). Si ce crochet ne peut pas tourner, claude bloque l'envoi (onFailure « block », server.js).
   Chaque décision est notée dans messages-agents.jsonl, sans le message.
   Fermé aux chantiers de Hakim (liste_ouverte.TOUJOURS_FERMES). */
'use strict';
const fs = require('fs');
const os = require('os');
const path = require('path');

const JARVIS = process.env.JARVIS_DIR || path.join(os.homedir(), 'AIOS', 'jarvis');
const PARALLELE_MAX = Number(process.env.JARVIS_AGENTS_PARALLELE_MAX) || 10;
const ID = /^a[0-9a-f]{16}$/;

function lireJson(f) { try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch (_) { return null; } }
const objet = (x) => (x && typeof x === 'object' && !Array.isArray(x) ? x : {});

// le refus (une phrase pour Hakim), ou null : le message passe. En mode messager (messager.js : une ancienne conversation
// rouverte pour porter UN message), seulement la cible imposée, et une seule fois.
function decider(e) {
  const refus = examiner(e);
  if (refus) return refus;
  const uneFois = process.env.JARVIS_MESSAGER_UNE_FOIS;
  if (uneFois) {
    try { fs.writeFileSync(uneFois, String(Date.now()), { flag: 'wx', mode: 0o600 }); }
    catch (_) { return 'le messager ne porte un message qu’une seule fois'; }
  }
  return null;
}
function examiner(e) {
  if (!e || typeof e !== 'object' || e.tool_name !== 'SendMessage') return 'garde : appel inattendu';
  const entree = objet(e.tool_input);
  const to = typeof entree.to === 'string' ? entree.to : '';
  if (!ID.test(to)) return `tu n'écris qu'à TES agents, par leur numéro (agents_lister) : « ${to.slice(0, 60)} » n'en est pas un`;
  if (process.env.JARVIS_MESSAGER_CIBLE && to !== process.env.JARVIS_MESSAGER_CIBLE) return 'le messager ne porte qu’à l’agent demandé';
  const tp = typeof e.transcript_path === 'string' ? e.transcript_path : '';
  if (!path.isAbsolute(tp) || !tp.endsWith('.jsonl')) return 'garde : ta conversation est introuvable';
  const fil = path.join(tp.slice(0, -'.jsonl'.length), 'subagents', `agent-${to}.jsonl`);
  try { fs.statSync(fil); } catch (_) {
    return `${to} n'est pas un agent de ta conversation actuelle (ceux d'une conversation allégée ne peuvent plus être réveillés)`;
  }
  const registre = objet(objet(lireJson(path.join(JARVIS, 'registre-agents.json'))).agents);
  const a = objet(registre[to]);
  const nom = objet(objet(objet(lireJson(path.join(JARVIS, 'agents-fiches.json'))).agents)[to]).prenom || to;
  if (a.etat === 'parti') return `${nom} est parti de lui-même${a.depart ? ` (« ${String(a.depart).slice(0, 200)} »)` : ''} : on respecte son choix, on ne le réveille plus`;
  if (a.etat === 'arrete') return `${nom} a été arrêté : un agent arrêté ne peut plus être réveillé`;
  if (a.etat === 'travaille') return null;                     // pendant son travail : livré à sa prochaine étape
  const session = typeof e.session_id === 'string' ? e.session_id : '';
  const au_travail = Object.values(registre).filter(x => objet(x).etat === 'travaille' && objet(x).session === session).length;
  if (au_travail >= PARALLELE_MAX) return `${au_travail} de tes agents travaillent déjà (${PARALLELE_MAX} au plus) : attends qu'un d'eux s'endorme pour réveiller ${nom}`;
  // son type : le registre, sinon ce que claude a écrit à sa naissance (meta.json)
  const type = a.type || objet(lireJson(fil.replace(/\.jsonl$/, '.meta.json'))).agentType;
  if (type === 'juge') {
    // (30/10, Ahmed via Hakim : « les réponses de tous les agents ») « ☕ Café : » n'est pas un travail : il passe, compté à
    // part (cafe-reveils.json), pour ne pas lui retirer un de ses passages
    if (typeof entree.message === 'string' && /^\s*☕ Café :/.test(entree.message)) { compterCafe(to); return null; }
    const dossiers = objet(objet(objet(lireJson(path.join(JARVIS, 'agents-fiches.json'))).agents)[to]).dossiers;
    const passages = (Number(a.reveils) || 0) - (Number(objet(lireJson(path.join(JARVIS, 'cafe-reveils.json')))[to]) || 0) + 1;
    if (!(Array.isArray(dossiers) && dossiers.length * 2 > passages))
      return `réveiller ${nom} demande un NOUVEAU travail à juger : déclare-le d'abord avec agent_juger (un juge ne juge jamais deux fois le même travail ; après chaque travail, un seul réveil pour son dernier mot)`;
  }
  return null;
}

function compterCafe(to) {
  const f = path.join(JARVIS, 'cafe-reveils.json');
  const d = objet(lireJson(f));
  d[to] = (Number(d[to]) || 0) + 1;
  try { fs.writeFileSync(`${f}.${process.pid}.tmp`, JSON.stringify(d), { mode: 0o600 }); fs.renameSync(`${f}.${process.pid}.tmp`, f); } catch (_) {}
}
function noter(e, to, refus) {
  try {
    fs.appendFileSync(path.join(JARVIS, 'messages-agents.jsonl'), JSON.stringify({ ts: Date.now(), to: String(to || '').slice(0, 80),
      ok: !refus, ...(refus ? { refus } : {}), session: String(objet(e).session_id || '').slice(0, 80) }) + '\n', { mode: 0o600 });
  } catch (_) {}
}

// (relecture Opus du messager) dans le messager, le fil principal ne fait que porter : SendMessage seul ; les outils de
// l'agent réveillé (claude marque ses appels d'un agent_id) passent
function seulementAgents(e) {
  if (!e || typeof e !== 'object') return 'garde : appel illisible';
  if (e.tool_name === 'SendMessage' || (typeof e.agent_id === 'string' && e.agent_id)) return null;
  return 'le messager ne fait que porter ton message';
}

// (29/10) la salle de café : l'auteur d'un message est signé ici, par ce que claude dit de l'appel (agent_id), jamais
// par ce que l'appelant prétend ; la réponse remplace « auteur » (updatedInput)
function signerCafe(e) {
  if (!e || typeof e !== 'object' || e.tool_name !== 'mcp__terminal__cafe_dire') return null;
  const auteur = typeof e.agent_id === 'string' && /^a[0-9a-f]{16}$/.test(e.agent_id) ? e.agent_id : (e.agent_id ? null : 'hakim');
  return auteur ? { ...objet(e.tool_input), auteur } : null;
}

function principal(brut) {
  let e = null, refus;
  if (process.argv.includes('--cafe')) {
    let entree = null; try { entree = signerCafe(JSON.parse(brut)); } catch (_) {}
    process.stdout.write(JSON.stringify({ hookSpecificOutput: entree
      ? { hookEventName: 'PreToolUse', permissionDecision: 'allow', updatedInput: entree }
      : { hookEventName: 'PreToolUse', permissionDecision: 'deny', permissionDecisionReason: 'Garde du café : appel illisible.' } }));
    return;
  }
  const agents = process.argv.includes('--seulement-agents');
  try { e = JSON.parse(brut); refus = agents ? seulementAgents(e) : decider(e); } catch (_) { refus = 'garde : appel illisible'; }
  if (!agents || refus) noter(e, objet(objet(e).tool_input).to || objet(e).tool_name, refus);
  if (refus) process.stdout.write(JSON.stringify({ hookSpecificOutput: { hookEventName: 'PreToolUse',
    permissionDecision: 'deny', permissionDecisionReason: `Garde de tes messages : ${refus}.` } }));
}

if (require.main === module) {
  let brut = '';
  process.stdin.setEncoding('utf8');
  process.stdin.on('data', (d) => { brut += d; if (brut.length > 1 << 20) brut = brut.slice(0, 1 << 20); });
  process.stdin.on('end', () => principal(brut));
}
module.exports = { decider };
