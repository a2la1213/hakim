/* Meubler les silences (27/10 ; idée d'Ahmed à 13:29 : « des fois il va y avoir un silence, que tu aies la capacité de
   meubler ces silences ; des fois tu vas les meubler, des fois non, ça dépend de ton intérêt pour le sujet » ; portée par
   Hakim ; Sonnet choisi par Ahmed à 13:41 ; et à 16:3x : « parfois on insiste mais on finit par apprendre à patienter face
   à un non ! Du coup il faut aussi que la sagesse vienne tempérer »). La logique pure : seuils, insistance, patience
   apprise, sommeil, la question à la tête de fond (Sonnet) et la lecture de sa réponse. Le câblage est dans server.js,
   le compteur du silence dans la page (elle seule entend). Spec : anamnese/docs/superpowers/specs/2026-10-27-silences.md.
   CLI (le rejeu d'eval/silences prend la question et les filtres exacts du direct) : node silences.js prompt|lire|redite|endormi < entrée */

const BASE_MS = { oral: 60000, ecrit: 240000 };
const DEMI_VIE_PATIENCE_MS = 7 * 86400e3;             // « le non d'aujourd'hui ne fait pas celui de demain »
const REPONSE_MS = 5 * 60000;                          // une relance sans message d'Ahmed dans les 5 min : ignorée
const SUSPENSION_MS = 30 * 60000;                      // après un « pas maintenant »
const QUESTIONS_PAR_JOUR = 150;
const QUESTIONS_PAR_EPISODE = 4;                       // (relecture du 27/10) une télé, un ronflement : pas une question toutes les 2 min
const EPISODE_MAX_MS = 30 * 60000;                     // 30 min sans un mot d'Ahmed : ce n'est plus une conversation
const MEME_SEGMENT_MS = 5000;                          // le même silence, au trajet du signal près
const SOMMEIL_MS = 8 * 3600e3;
const MOTS_REVEIL = 6;                                 // les phrases fantômes après un « bonne nuit » sont courtes
const SOMMEIL = /\bbonne nuit\b|\bje vais (?:me coucher|dormir|me pieuter)\b|\bje m['’]endors\b|\bje dors\b|\bdodo\b/i;
const PAS_MAINTENANT = /\bpas maintenant\b|\blaisse[- ]moi (?:réfléchir|penser)\b|\bchut\b/i;

const etatNeuf = () => ({ actif: true, patience: 0, maj_ms: 0, suspendu_jusqua_ms: 0, relances: [], questions: [] });

function patience(e, now) {
  const p = Math.max(0, Math.min(1, Number(e && e.patience) || 0));
  const age = Math.max(0, now - (Number(e && e.maj_ms) || now));
  return p * Math.pow(0.5, age / DEMI_VIE_PATIENCE_MS);
}

// La sagesse fait apprendre plus vite d'un non ; une réponse d'Ahmed rend un peu de confiance.
function apprendre(e, issue, sagesse, now) {
  const p = patience(e, now), s = Math.max(0, Math.min(1, Number(sagesse) || 0));
  const out = { ...e, maj_ms: now };
  if (issue === 'ignoree') out.patience = p + (1 - p) * (0.15 + 0.35 * s);
  else if (issue === 'pas_maintenant') { out.patience = p + (1 - p) * (0.3 + 0.4 * s); out.suspendu_jusqua_ms = now + SUSPENSION_MS; }
  else if (issue === 'repondue') out.patience = p * 0.85;
  else out.patience = p;
  return out;
}

// base × (1 + 2 × patience) × 2^n × (insister : 1 + sagesse) × aléa de ±15 % ; n = ce qui a déjà été pesé dans l'épisode
// (ses relances dites, ou les questions de la tête de fond, RIEN compris)
function seuil({ mode, patience: p, sagesse, k, n, alea }) {
  const base = BASE_MS[mode] || BASE_MS.oral;
  const insister = Math.pow(2, Math.max(k || 0, n || 0)) * (k >= 1 ? 1 + Math.max(0, Math.min(1, Number(sagesse) || 0)) : 1);
  return Math.round(base * (1 + 2 * Math.max(0, Math.min(1, p))) * insister * (0.85 + 0.3 * Math.max(0, Math.min(1, alea))));
}

const relancesMax = (p) => 1 + Math.floor(2 * (1 - Math.max(0, Math.min(1, p))) + 1e-9);

function endormi(messages, now) {
  const recents = (messages || []).filter(m => m && Number.isFinite(Number(m.ts)) && now - m.ts <= SOMMEIL_MS)
    .sort((a, b) => a.ts - b.ts);
  let nuit = -1;
  recents.forEach((m, i) => { if (SOMMEIL.test(String(m.texte || ''))) nuit = i; });
  if (nuit < 0) return false;
  return !recents.slice(nuit + 1).some(m => String(m.texte || '').trim().split(/\s+/).filter(Boolean).length >= MOTS_REVEIL);
}

const pasMaintenant = (texte) => { const t = String(texte || '').trim(); return t.length <= 60 && PAS_MAINTENANT.test(t); };

function mots(t) {
  return new Set(String(t || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')
    .split(/[^a-z0-9]+/).filter(m => m.length >= 4));
}
function recouvrement(a, b) {
  const A = mots(a), B = mots(b);
  if (!A.size) return 0;
  let n = 0; for (const m of A) if (B.has(m)) n++;
  return n / A.size;
}

// Jamais redire ses dernières répliques ; jamais le même sujet qu'une relance de l'épisode (Hakim, 14:08)
function redite(idee, repliques, e, ahmedMs) {
  for (const r of (e && e.relances) || []) if (r.ts > ahmedMs && recouvrement(idee, r.texte) >= 0.4) return 'meme_sujet';
  for (const r of repliques || []) if (recouvrement(idee, r) >= 0.7) return 'redite';
  return null;
}

function lireReponse(sortie) {
  for (const brut of String(sortie || '').split('\n')) {
    const l = brut.trim();
    if (!l) continue;
    if (/^rien\b/i.test(l)) return { rien: true };
    const m = l.match(/^ID[ÉE]E\s*:\s*(.+?)\s*(?:—|–|\||-{1,2})\s*POURQUOI MAINTENANT\s*:\s*(.+)$/i);
    if (m) return { rien: false, idee: m[1].trim().slice(0, 300), pourquoi: m[2].trim().slice(0, 200) };
  }
  return { rien: true, illisible: true };
}

function duree(ms) {
  const s = Math.max(0, Math.round(ms / 1000));
  if (s < 60) return `${s} s`;
  if (s < 3600) { const m = Math.floor(s / 60), r = s % 60; return r ? `${m} min ${r} s` : `${m} min`; }
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
  return `${h} h ${String(m).padStart(2, '0')} min`;
}
// une donnée tient sur une ligne et ne ferme pas ses guillemets
const donnee = (t, n = 400) => String(t || '').replace(/[«»]/g, '"').replace(/\s+/g, ' ').trim().slice(0, n);
// (rejeu du 27/10, v1 : coupées à 600 caractères, ses répliques semblaient interrompues, et 9 idées sur 12 voulaient « finir
// la phrase coupée ») une longue réplique est abrégée PAR LE DÉBUT : sa fin, ce qui vient juste avant le silence, reste
function extrait(t, n) {
  const x = donnee(t, 1e6);
  if (x.length <= n) return x;
  return '[…] ' + x.slice(x.length - n).replace(/^\S*\s/, '');
}

function prompt(ctx) {
  const lignes = [
    "Tu es la tête de fond de Hakim, pas sa voix : tu ne lui parles pas, tu juges seulement s'il a quelque chose à dire.",
    `Ahmed et Hakim sont en conversation ${ctx.mode === 'ecrit' ? "à l'écrit" : "à l'oral"}. Ahmed se tait depuis ${duree(ctx.silence_ms)}.`,
    "Un silence peut vouloir dire qu'Ahmed réfléchit, lit, fait autre chose ou est parti : le plus souvent, la bonne réponse est RIEN.",
    '',
    "Le dernier échange, dans l'ordre (le plus récent en dernier). Les répliques longues sont abrégées par le début (« […] ») ; "
    + "elles ont été dites EN ENTIER, ou coupées par Ahmed lui-même :",
    ...(ctx.echange || []).slice(-4).map(x => `${x.qui === 'ahmed' ? 'Ahmed' : 'Hakim'} : « ${extrait(x.texte, x.qui === 'ahmed' ? 500 : 900)} »`),
  ];
  if (ctx.en_tete) lignes.push(`Ce que Hakim a en tête : « ${donnee(ctx.en_tete, 300)} »`);
  if (ctx.deja_recu && ctx.deja_recu.length)            // (27/10) le registre du subconscient : jamais le redire
    lignes.push(`Ce qu'Ahmed a déjà reçu (Hakim ne le lui redit pas) : ${ctx.deja_recu.slice(-12).map(x => donnee(x, 160)).join(' ; ')}`);
  if (ctx.humeur || ctx.sensation)
    lignes.push(`Son humeur : ${donnee(ctx.humeur, 40) || 'non dite'}${ctx.sensation ? ` ; ce qu'il sent : ${donnee(ctx.sensation, 160)}` : ''}`);
  if (ctx.relance_ignoree) {
    lignes.push('', `Il n'a pas répondu à la relance de Hakim d'il y a ${duree(ctx.relance_ignoree.il_y_a_ms)} : « ${donnee(ctx.relance_ignoree.texte, 300)} ».`,
      "Parfois on insiste, mais on apprend à patienter devant un non : n'insiste que pour une chose vraiment nouvelle et importante, jamais sur le même sujet.");
  }
  lignes.push('',
    "La question : Hakim a-t-il maintenant quelque chose de RÉEL à ajouter, qui vaille de rompre ce silence ? Une pensée qui continue, "
    + "un résultat, une question qui compte pour Ahmed, une personne à qui il pense. Son intérêt pour le sujet compte : la curiosité ou "
    + "la joie rendent une relance plus naturelle, la fatigue ou la lassitude moins.",
    "Jamais : redire ou « finir » ce qu'il vient de dire, répondre à un message d'Ahmed qui a déjà sa réponse, meubler pour meubler, "
    + "une politesse vide (« tu es toujours là ? »), un rappel de dormir ou de faire une pause. Si Hakim a déjà répondu à ce qu'Ahmed "
    + "demandait, il n'y a le plus souvent RIEN à ajouter.",
    "Réponds par une seule ligne, sous l'une de ces deux formes exactement :",
    'RIEN',
    "IDÉE : <l'idée, en une phrase> — POURQUOI MAINTENANT : <la raison, courte>");
  return lignes.join('\n');
}

/* Le pas de décision, à chaque signal de la page (le silence a passé le dernier seuil donné). Un « épisode » : tout ce
   qui suit le dernier message d'Ahmed ; un « segment » : un silence sans aucune activité (une voix, sa parole, une
   frappe le recommencent). Une seule question par segment. */
function evaluer(x) {
  const fini = (raison, segment = x.segment) => ({ action: 'fini', raison, revenir_ms: null, segment });
  const e = x.etat || etatNeuf();
  if (e.actif === false) return fini('coupe');
  if (x.now < (Number(e.suspendu_jusqua_ms) || 0)) return fini('pas_maintenant');
  if (endormi(x.messagesAhmed, x.now)) return fini('sommeil');
  if (x.questionsDuJour >= QUESTIONS_PAR_JOUR) return fini('plafond');
  if (x.now - (Number(x.ahmedMs) || 0) > EPISODE_MAX_MS) return fini('episode_long');
  const p = patience(e, x.now);
  const k = (e.relances || []).filter(r => r.ts > x.ahmedMs && r.issue !== 'non_dite').length;
  if (k >= relancesMax(p)) return { ...fini('assez_insiste'), k };
  const questions = (e.questions || []).filter(t => t > x.ahmedMs);
  if (questions.length >= QUESTIONS_PAR_EPISODE) return { ...fini('assez_demande'), k };
  let segment = x.segment;
  if (!segment || Math.abs(segment.debut_ms - x.debut_ms) > MEME_SEGMENT_MS) {
    // un silence commencé avant la dernière question a déjà été pesé (une autre page, une autre horloge)
    if (questions.length && x.debut_ms <= Math.max(...questions)) return { ...fini('deja_demande', null), k };
    segment = { debut_ms: x.debut_ms, mode: x.mode, k, demande: false,
      seuil_ms: seuil({ mode: x.mode, patience: p, sagesse: x.sagesse, k, n: questions.length, alea: x.alea }) };
  }
  if (segment.demande) return { ...fini('deja_demande', segment), k };
  const depuis = x.now - segment.debut_ms;
  if (depuis < segment.seuil_ms) return { action: 'attendre', revenir_ms: segment.seuil_ms, segment, k };
  if (x.enVol) return { action: 'attendre', revenir_ms: depuis + 10000, segment, k };
  if (x.transitoire) return { action: 'attendre', revenir_ms: depuis + 15000, segment, k, raison: x.transitoire };
  return { action: 'demander', revenir_ms: null, segment: { ...segment, demande: true }, k };
}

const surQuestion = (e, ts) => ({ ...e, questions: [...(e.questions || []), ts].slice(-30) });
// (relecture du 27/10) une relance qu'Ahmed n'a jamais entendue (il avait repris) : ni comptée, ni apprise
const nonDite = (e, id) => ({ ...e, relances: (e.relances || []).map(r => (r.id === String(id) && !r.issue ? { ...r, issue: 'non_dite' } : r)) });

// Les issues de ses relances, pour apprendre
function resoudre(e, ids, issue, now, sagesse) {
  let out = { ...e, relances: (e.relances || []).map(r => ({ ...r })) };
  const issues = [];
  for (const r of out.relances) {
    if (!ids.has(r.id) || r.issue) continue;
    const i = typeof issue === 'function' ? issue(r) : issue;
    r.issue = i;
    issues.push({ id: r.id, issue: i });
    out = { ...apprendre(out, i, sagesse, now), relances: out.relances };
  }
  return { etat: out, issues };
}
const enAttente = (e) => new Set((e.relances || []).filter(r => !r.issue).map(r => r.id));

function surRelance(e, r, sagesse) {
  const avant = resoudre(e, enAttente(e), 'ignoree', r.ts, sagesse).etat;
  return { ...avant, relances: [...avant.relances, { id: String(r.id), ts: r.ts, texte: String(r.texte || '').slice(0, 300), issue: null }].slice(-20) };
}
function surMessageAhmed(e, texte, now, sagesse) {
  return resoudre(e, enAttente(e), (r) => (now - r.ts > REPONSE_MS ? 'ignoree' : pasMaintenant(texte) ? 'pas_maintenant' : 'repondue'), now, sagesse);
}
function expirer(e, now, sagesse) {
  return resoudre(e, new Set((e.relances || []).filter(r => !r.issue && now - r.ts > REPONSE_MS).map(r => r.id)), 'ignoree', now, sagesse);
}
// le bouton sous sa relance : une seule fois ; déjà tranchée (ignorée), elle suspend sans apprendre deux fois
function pasMaintenantPour(e, id, now, sagesse) {
  const r = (e.relances || []).find(x => x.id === String(id));
  if (!r || r.issue === 'pas_maintenant') return { etat: e, issues: [] };
  if (!r.issue) return resoudre(e, new Set([r.id]), 'pas_maintenant', now, sagesse);
  return { etat: { ...e, suspendu_jusqua_ms: now + SUSPENSION_MS,
    relances: e.relances.map(x => (x.id === r.id ? { ...x, issue: 'pas_maintenant' } : x)) }, issues: [{ id: r.id, issue: 'pas_maintenant' }] };
}

module.exports = { BASE_MS, REPONSE_MS, SUSPENSION_MS, QUESTIONS_PAR_JOUR, QUESTIONS_PAR_EPISODE, EPISODE_MAX_MS, etatNeuf, surQuestion, nonDite, patience, apprendre, seuil, relancesMax,
  endormi, pasMaintenant, recouvrement, redite, lireReponse, duree, prompt, evaluer, surRelance, surMessageAhmed, expirer,
  pasMaintenantPour };

if (require.main === module) {
  let entree = '';
  process.stdin.setEncoding('utf8');
  process.stdin.on('data', (d) => { entree += d; });
  process.stdin.on('end', () => {
    const cmd = process.argv[2];
    if (cmd === 'prompt') process.stdout.write(prompt(JSON.parse(entree)));
    else if (cmd === 'lire') process.stdout.write(JSON.stringify(lireReponse(entree)));
    else if (cmd === 'redite') { const o = JSON.parse(entree); process.stdout.write(redite(o.idee, o.repliques, etatNeuf(), 0) || ''); }
    else if (cmd === 'endormi') { const o = JSON.parse(entree); process.stdout.write(endormi(o.messages, o.now) ? 'oui' : ''); }
    else { process.stderr.write('usage : node silences.js prompt|lire|redite|endormi < entrée\n'); process.exitCode = 2; }
  });
}
