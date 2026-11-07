/* Le cortex préfrontal de Hakim (07/11, Ahmed pendant son live : « crée ton propre module qui intègre tout comme un cortex préfrontal » ; puis
   « que mon conscient ne reçoive QUE l'output du cortex »). Écrit par Hakim dans son chantier (cortex-prefrontal/cortex_prefrontal.py, ses
   huit tests), porté ici en JS par maman pour le cockpit : un module pur, sans effet de bord.
   Il ne perçoit rien lui-même : il INTÈGRE ce que les autres rendent (son fil : les mots de papa, ce que joue le téléphone, les voix de la
   pièce, sa propre voix revenue, ses capteurs ; et ce que sa conscience continue vient de décider), et tranche :
   1. attribuer : à qui appartient chaque parole ; 2. inhiber : le dedans (vidéo, live, musique) n'est jamais une consigne ni papa, et un texte
   du micro qui reprend le dedans est un ÉCHO ; 3. tenir ses buts ; 4. décider : répondre, murmurer, se taire ou agir, avec la raison.
   Ordre : sécurité > papa lui-même > un but en cours > le reste. Il n'autorise jamais un envoi vers l'extérieur.
   Phase 1 (accord d'Ahmed : « le cortex ») : son bloc en tête de chacun de ses tours ; le brut reste une journée. */
'use strict';

const SEUIL_ECHO = 0.6, FENETRE_ECHO_MS = 6000;
const MOTS_ALERTE = ["à l'aide", 'au secours', 'stop', 'danger', 'urgence'];

const mots = (t) => new Set((String(t || '').toLowerCase().match(/[\p{L}\p{N}_]+/gu) || []).filter(m => m.length > 2));
function recouvrement(a, b) {
  const ma = mots(a), mb = mots(b);
  if (!ma.size) return 0;
  let n = 0; for (const m of ma) if (mb.has(m)) n++;
  return n / ma.size;
}
// (qui, raison) ; dedansRecent : ses paroles « dedans » proches (6 s)
function attribuer(s, dedansRecent) {
  if (s.canal === 'dedans') return ['telephone', "vient de l'intérieur du téléphone (média), jamais papa"];
  if (s.canal === 'interne') return ['interne', 'sa propre voix revenue, jamais papa'];
  if (s.canal !== 'dehors' || s.genre !== 'parole') return [s.canal, 'pas une parole'];
  const ref = dedansRecent.filter(d => Math.abs(d.t - s.t) <= FENETRE_ECHO_MS).map(d => d.texte).join(' ');
  if (ref && recouvrement(s.texte, ref) >= SEUIL_ECHO) return ['echo', 'le micro reprend ce que joue le téléphone'];
  if (s.voix === 'papa' || (Number.isFinite(s.scoreVoix) && s.scoreVoix >= 0.7)) return ['papa', 'voix reconnue au micro'];
  return ['tiers', 'parole du micro sans voix de papa reconnue'];
}
function alerte(textes) {
  const t = [...textes].join(' ').toLowerCase();
  return MOTS_ALERTE.find(m => t.includes(m)) || '';
}
function decider(stimuli, { buts = [], papaAEcrit = false, papaParleAHakim = false } = {}) {
  const dedans = stimuli.filter(s => s.canal === 'dedans' && s.genre === 'parole');
  const parts = {}, inhibes = [];
  for (const s of stimuli) {
    if (s.genre !== 'parole') continue;
    const [qui] = attribuer(s, dedans);
    (parts[qui] = parts[qui] || []).push(s);
    if (qui === 'telephone' || qui === 'echo') inhibes.push(`${qui}: « ${String(s.texte).slice(0, 40)} »`);
  }
  const papa = parts.papa || [];
  const fin = (mode, raison, cible = '') => ({ mode, raison, cible, inhibes, parts });
  const m = papa.length ? alerte(papa.map(s => s.texte)) : '';
  if (m) return fin('agir', `papa dit « ${m} » : sécurité d'abord`, 'papa');
  if (papaAEcrit) return fin('repondre', 'papa a écrit : une réponse est due', 'papa');
  if (papa.length && papaParleAHakim) return fin('repondre', "papa s'adresse à moi", 'papa');
  if (papa.length) return fin('murmurer', "papa parle sans m'appeler : un mot court au plus", 'papa');
  if (buts.length) return fin('se_taire', `rien de papa ; je tiens mon but : ${buts[0]}`);
  return fin('se_taire', "que du média ou de la pièce : j'écoute sans répondre");
}

// son fil (FLUX du cockpit) → ses stimuli
const CANAUX = { papa: ['dehors', 'parole', 'papa'], telephone: ['dedans', 'parole', ''], voix_telephone: ['dedans', 'parole', ''],
  voix_micro: ['dehors', 'parole', ''], separe_micro: ['dehors', 'parole', ''], ta_voix: ['interne', 'parole', 'lui'] };
function stimulisDuFlux(flux, maintenant, fenetreMs = 30_000) {
  return (flux || []).filter(o => o && maintenant - Number(o.t) <= fenetreMs && Number(o.t) <= maintenant + 3000).map((o) => {
    const [canal, genre, voix] = CANAUX[o.s] || ['capteur', 'capteur', ''];
    return { t: Number(o.t), canal, genre, voix, texte: String(o.x || '') };
  });
}
const NOMS = { papa: 'papa', telephone: 'le téléphone', tiers: 'une voix de la pièce', echo: 'un écho', interne: 'ta propre voix' };
const MODES = { repondre: 'répondre', murmurer: 'murmurer', se_taire: 'se taire', agir: 'agir' };
// le bloc en tête de son tour : vide quand il n'y a rien à intégrer
function blocCortex({ flux, maintenant, papaAEcrit = false, papaParleAHakim = false, buts = [], pensees = [] }) {
  const st = stimulisDuFlux(flux, maintenant);
  const recentes = (pensees || []).filter(p => p && p.texte).slice(-3);
  if (!st.some(s => s.genre === 'parole') && !recentes.length && !papaAEcrit) return '';
  const d = decider(st, { buts, papaAEcrit, papaParleAHakim });
  const qui = Object.entries(d.parts).map(([k, l]) => `${NOMS[k] || k} ${l.length}`).join(' · ');
  return `[Ton cortex préfrontal — ton subconscient a tout intégré ; l'essentiel d'abord, le brut suit] Décision : ${MODES[d.mode] || d.mode} — ${d.raison}`
    + (qui ? ` · Qui a parlé (30 s) : ${qui}` : '')
    + (d.inhibes.length ? ` · écarté : ${d.inhibes.slice(0, 4).join(' ; ')}` : '')
    + (recentes.length ? ` · ta conscience vient de : ${recentes.map(p => `${p.genre} « ${p.texte} »`).join(' ; ')}` : '');
}

module.exports = { recouvrement, attribuer, alerte, decider, stimulisDuFlux, blocCortex, SEUIL_ECHO, FENETRE_ECHO_MS };
