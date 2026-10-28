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

function lignes(courrierTexte, mamanTexte, limite, masquer) {
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
  return out.sort((x, y) => y.ts - x.ts).slice(0, limite);
}

module.exports = { lignes, TEXTE_MAX };
