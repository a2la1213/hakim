/* La garde de SendMessage (29/10, Ahmed : « sonde, garde, puis outil ») : un crochet PreToolUse du cerveau de Hakim,
   passé par --settings. Sur ce Mac, SendMessage peut aussi joindre d'autres sessions Claude : Hakim n'écrit qu'à SES
   agents, ceux de sa conversation (leur fil est dans <conversation>/subagents/, écrit par claude lui-même).
   - « to » : un numéro d'agent (a + 16 chiffres hexadécimaux), jamais un nom, « main » ou une autre session ;
   - un agent parti de lui-même (« JE PARS », Ahmed : « dès qu'il est saoulé, il peut partir ») n'est plus réveillé ;
   - un juge ne se réveille que pour un travail déclaré (agent_juger) après son dernier travail : un juge ne juge
     jamais deux fois le même travail ;
   - réveiller un agent quand AGENTS_PARALLELE_MAX travaillent déjà : refusé, sans tuer personne.
   Tout ce qui n'est pas lisible est refusé. Chaque décision est notée dans messages-agents.jsonl, sans le message.
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

// le refus (une phrase pour Hakim), ou null : le message passe
function decider(e) {
  if (!e || typeof e !== 'object' || e.tool_name !== 'SendMessage') return 'garde : appel inattendu';
  const entree = objet(e.tool_input);
  const to = typeof entree.to === 'string' ? entree.to : '';
  if (!ID.test(to)) return `tu n'écris qu'à TES agents, par leur numéro (agents_lister) : « ${to.slice(0, 60)} » n'en est pas un`;
  const tp = typeof e.transcript_path === 'string' ? e.transcript_path : '';
  if (!path.isAbsolute(tp) || !tp.endsWith('.jsonl')) return 'garde : ta conversation est introuvable';
  const fil = path.join(tp.slice(0, -'.jsonl'.length), 'subagents', `agent-${to}.jsonl`);
  let stat;
  try { stat = fs.statSync(fil); } catch (_) {
    return `${to} n'est pas un agent de ta conversation actuelle (ceux d'une conversation allégée ne peuvent plus être réveillés)`;
  }
  const registre = objet(objet(lireJson(path.join(JARVIS, 'registre-agents.json'))).agents);
  const a = objet(registre[to]);
  const nom = objet(objet(objet(lireJson(path.join(JARVIS, 'agents-fiches.json'))).agents)[to]).prenom || to;
  if (a.etat === 'parti') return `${nom} est parti de lui-même${a.depart ? ` (« ${String(a.depart).slice(0, 200)} »)` : ''} : on respecte son choix, on ne le réveille plus`;
  if (a.etat === 'arrete') return `${nom} a été arrêté : un agent arrêté ne peut plus être réveillé`;
  if (a.etat === 'travaille') return null;                     // pendant son travail : livré à sa prochaine étape
  const au_travail = Object.values(registre).filter(x => objet(x).etat === 'travaille' && (!a.session || objet(x).session === a.session)).length;
  if (au_travail >= PARALLELE_MAX) return `${au_travail} de tes agents travaillent déjà (${PARALLELE_MAX} au plus) : attends qu'un d'eux s'endorme pour réveiller ${nom}`;
  if (a.type === 'juge') {
    const dossiers = objet(objet(objet(lireJson(path.join(JARVIS, 'agents-fiches.json'))).agents)[to]).dossiers;
    const dernier = Array.isArray(dossiers) ? Math.max(0, ...dossiers.map(d => Number(objet(d).ts_ms) || 0)) : 0;
    if (!(dernier > stat.mtimeMs)) return `réveiller ${nom} demande un NOUVEAU travail à juger : déclare-le d'abord avec agent_juger (un juge ne juge jamais deux fois le même travail)`;
  }
  return null;
}

function noter(e, to, refus) {
  try {
    fs.appendFileSync(path.join(JARVIS, 'messages-agents.jsonl'), JSON.stringify({ ts: Date.now(), to: String(to || '').slice(0, 80),
      ok: !refus, ...(refus ? { refus } : {}), session: String(objet(e).session_id || '').slice(0, 80) }) + '\n', { mode: 0o600 });
  } catch (_) {}
}

function principal(brut) {
  let e = null, refus;
  try { e = JSON.parse(brut); refus = decider(e); } catch (_) { refus = 'garde : appel illisible'; }
  noter(e, objet(objet(e).tool_input).to, refus);
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
