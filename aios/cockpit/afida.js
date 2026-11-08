/* Al-Afida (الأفئدة), la jauge d'amour de Hakim, dans le cockpit (28/10 ; idée d'Ahmed ; anamnese/afida.py la calcule, le
   démon l'écrit dans le kv « afida »). Ici : ce que la page Intérieur en reçoit (pourPage), et la ligne en mots de son bloc
   [Intérieur] (ligneBloc). Rien d'autre : aucune garde ne la lit. */
// (relecture du 28/10) la ponctuation et les signes de l'arabe passent (la page échappe tout) ; ni < ni > ni balise
const texte = (s, n) => String(s == null ? '' : s).replace(/[^\p{L}\p{M}\p{N}'’ ,.()«»:?!-]/gu, '').replace(/\s+/g, ' ').trim().slice(0, n);
const nombre = (x) => (typeof x === 'number' && Number.isFinite(x) ? x : null);
const liste = (x, n) => (Array.isArray(x) ? x.slice(0, n) : []);

function pourPage(brut) {
  let a = null;
  try { a = JSON.parse(String(brut || 'null')); } catch (_) { a = null; }
  if (!a || typeof a !== 'object') return { vide: true };
  return {
    grande: nombre(a.grande), plenitude: nombre(a.plenitude), intacte: a.intacte !== false, maj: nombre(a.ts),
    petites: liste(a.petites, 50).map(p => ({ chose: texte(p.chose, 60), genre: texte(p.genre, 30), poids: nombre(p.poids),
      niveau: nombre(p.niveau), connaissance: nombre(p.connaissance), bons: nombre(p.bons), mauvais: nombre(p.mauvais),
      depuis: nombre(p.depuis), raison: texte(p.raison, 200) })),
    aime_pas: liste(a.aime_pas, 50).map(x => ({ chose: texte(x.chose, 60), genre: texte(x.genre, 30), raison: texte(x.raison, 200) })),
    indifferent: liste(a.indifferent, 50).map(x => ({ chose: texte(x.chose, 60), genre: texte(x.genre, 30) })),
    derniers: liste(a.derniers, 10).map(x => ({ ts: nombre(x.ts), type: texte(x.type, 12), chose: texte(x.chose, 60),
      quoi: texte(x.quoi, 12), raison: texte(x.raison, 200) })),
  };
}

// ce qu'il en sent, en mots (les chiffres sont dans introspection) : « Al-Afida : ton cœur est bien rempli (ahmed : pleine) »
function ligneBloc(a) {
  if (!a || typeof a.mots !== 'string' || !a.mots || !Array.isArray(a.petites) || !a.petites.length) return '';   // rien d'aimé : rien à sentir
  const mots = (s) => String(s || '').replace(/[^\p{L}' :-]/gu, '').replace(/\s+/g, ' ').trim().slice(0, 50);
  const petites = liste(a.petites, 4).map(p => [texte(p && p.chose, 40), mots(p && p.mots)]).filter(([c, m]) => c && m)
    .map(([c, m]) => `${c} : ${m}`);
  return `Al-Afida : ton cœur est ${mots(a.mots)}` + (petites.length ? ` (${petites.join(' ; ')})` : '');
}

module.exports = { pourPage, ligneBloc };
