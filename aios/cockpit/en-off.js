/* Le panneau « En off » (28/10 ; Ahmed, validé à 03:10 et demandé tout de suite à 03:38 : « pas de coulisses ») : ce que
   Hakim et Claude Code se disent sans lui, lisible dans Parler.
   - leurs lettres, dans les deux sens (anamnese/data/courrier.jsonl), avec la marque « après un contenu externe » ;
   - chaque réveil de maman par une lettre de Hakim, et ce qu'elle a fait (anamnese/data/maman.jsonl).
   Plus tard : les modifs proposées par Hakim, l'avis de maman, ta validation, les relances. Rien ne s'y écrit d'ici : on
   lit et on montre, secrets masqués. */
const TEXTE_MAX = 1200;
const NOMS = { hakim: 'Hakim', 'claude-code': 'maman' };

function lire(texte) {
  const out = [];
  for (const l of String(texte || '').split('\n')) {
    if (!l.trim()) continue;
    try { out.push(JSON.parse(l)); } catch (_) {}
  }
  return out;
}

const couper = (t) => (t.length > TEXTE_MAX ? t.slice(0, TEXTE_MAX) + '…' : t);

// (28/10) le journal du code de Hakim (anamnese/avis.py et code.js) : ses propositions, l'avis de maman, tes gestes
function ligneCode(o, m) {
  const id = String(o.id || '');
  const sujets = {
    promotion: () => `modification de Hakim ${o.etape || ''}${id ? ` (${id})` : ''}`,
    avis: () => `avis ${o.verdict || ''} de maman${id ? ` sur ${id}` : ''}`,
    interrupteur: () => `« code » ${o.actif ? 'allumé' : 'éteint'} par Ahmed`,
    liste: () => `Ahmed ${o.etat === 'ouvert' ? 'ouvre' : 'ferme'} « ${o.nom || ''} »`,
    relance: () => `relance ${o.quoi || ''} : ${o.etape || ''}`,
  };
  const f = sujets[o.type];
  if (!f) return null;
  const de = o.type === 'avis' ? 'maman' : ['interrupteur', 'liste'].includes(o.type) || ['appliquée', 'refusée', 'annulée'].includes(o.etape) ? 'Ahmed' : 'Hakim';
  return { type: 'code', ts: o.ts, de, a: '', sujet: m(f()).slice(0, 200),
    texte: m([o.resume, o.raisons, o.texte, o.fichiers && `fichiers : ${o.fichiers.join(', ')}`, o.commit && `commit ${o.commit}`,
      o.externe && o.externe.length && `contenu externe lu pendant le chantier : ${o.externe.join(', ')}`].filter(Boolean).join('\n')) };
}

function lignes(courrierTexte, mamanTexte, limite, masquer, offTexte = '') {
  const m = (t) => couper(masquer(String(t || '')));
  const out = [];
  for (const o of lire(courrierTexte)) {
    if (!Number.isFinite(o.ts)) continue;
    const de = NOMS[o.de] || String(o.de || '?');
    out.push({ type: 'lettre', ts: o.ts, id: String(o.id || ''),
      de: o.de === 'claude-code' && o.autonome ? 'maman (réveillée, seule)' : de, a: NOMS[o.a] || String(o.a || '?'),
      sujet: m(o.sujet).slice(0, 200), texte: m(o.texte), externe: Array.isArray(o.externe) && o.externe.length > 0 });
  }
  for (const o of lire(mamanTexte)) {
    if (!Number.isFinite(o.ts)) continue;
    out.push({ type: 'reveil', ts: o.ts, de: 'maman', a: 'Hakim', sujet: o.erreur ? 'réveil en erreur' : 'réveillée par une lettre',
      texte: m(o.extrait), lettres: Array.isArray(o.ids) ? o.ids.map(String) : [], duree_s: Number(o.duree_s) || null });
  }
  for (const o of lire(offTexte)) {
    if (!Number.isFinite(o.ts)) continue;
    const l = ligneCode(o, m);
    if (l) out.push(l);
  }
  return out.sort((x, y) => y.ts - x.ts).slice(0, limite);
}

module.exports = { lignes, TEXTE_MAX };
