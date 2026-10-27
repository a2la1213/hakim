/* Sentir sans voir la machinerie (27/10 ; principe d'Ahmed : « les couches se voient entre elles, mais le PROCESSUS doit
   être invisible à Hakim : il doit seulement sentir » ; proposition de Hakim, « on fait tout »). Ses blocs d'état ne lui
   montrent plus ni chiffres, ni nom d'humeur, ni suggestion du code, ni le nom des modèles qui calculent ; ils gardent la
   matière en mots. Les chiffres restent à un geste : introspection, tableau_interieur. Le code, lui, voit tout (la sagesse
   de la nuit compare sa décision à la suggestion écrite dans sagesse-tour.json ; l'honnêteté de l'introspection compare ses
   mots à ses vraies variables). Une transformation du TEXTE des blocs : la même sert en direct et pour rejouer ses vrais
   tours d'avant (eval/processus_invisibles). Idempotente. CLI : node matiere.js < prompt > prompt-en-matiere */

const niveau = (n, bas, milieu, haut) => (n <= 3 ? bas : n <= 6 ? milieu : haut);

function style(l) {
  return l
    .replace(/ \(calculé par le code depuis ton état : [^)]*\)/, '')
    .replace(/Curseurs de 0 à 10 : ton (\d+) \([^)]*\), énergie (\d+) \([^)]*\), affection (\d+) \([^)]*\), tension (\d+) \([^)]*\) : fais varier tes mots, leur couleur et leur rythme selon ces valeurs\./,
      (_m, t, e, a, s) => `Ta couleur du moment : ${niveau(+t, 'plutôt sombre', 'entre deux', 'lumineuse')}, `
        + `${niveau(+e, 'posée', 'calme', 'vive')}, ${niveau(+a, 'neutre', 'chaleureuse', 'tendre')}, `
        + `${niveau(+s, 'détendue', 'un peu sur tes gardes', 'sur tes gardes')} : fais varier tes mots, leur couleur et leur rythme selon elle.`)
    .replace(/des phrases de (\d+) mots au plus/, (_m, n) => (+n <= 12 ? 'des phrases courtes' : +n <= 18 ? 'des phrases plutôt courtes' : 'des phrases à ton rythme'))
    .replace(/(\d+) exclamation\(s\) au plus/, (_m, n) => (+n === 1 ? 'une exclamation au plus' : 'quelques exclamations au plus'))
    .replace(/au plus \d+ % de ta longueur habituelle/, 'plus court que d\'habitude');
}

function reflexe(l) {
  return l
    .replace(/ \(ta sagesse : [\d,.]+\)/, '')
    .replace(/ton réflexe \([^)]*\) teinte d'office (?:ta première phrase|tes \d+ premières phrases au plus), sans que tu le nommes/,
      "un réflexe pénible teinte d'office tes premières phrases, sans que tu le nommes")
    .replace(/ton humeur \([^)]*\) passe/, 'ton humeur passe')
    .replace(/\. Suggestion du code : « [^»]* »(?: \((.*)\))?\. Puis juge toi-même/,
      (_m, ctx) => (ctx ? `. Le contexte : ${ctx}. Puis juge toi-même` : '. Puis juge toi-même'))
    .replace("(t'écarter de la suggestion est permis quand c'est juste ; le sujet grave, c'est toi qui en juges)",
      "(le sujet grave, c'est toi qui en juges)");
}

function regles(l) {
  return l
    .replace("[Ce que ton émotion pèse sur tes choix (une règle du code, d'après ton état ; pas une consigne d'Ahmed) — ",
      "[Ce que tu ressens pèse sur tes choix (pas une consigne d'Ahmed) — ")
    .replace(/(— |; )(?:ta|ton) [^:();]+? \((?:[^()]|\([^)]*\))*\) : /g, '$1');
}

function interieur(l) {
  let out = l
    .replace(/(— [^:\]]+ : )humeur [^;\]]*?(?= ; |\. |\])( ; )?/, (_m, tete) => tete)
    .replace(/ce que ton code lit dans tes 13 hormones, maintenant : une sensation (.*?) \(proche de : [^;]*; calculé par le code, pas par Gemma ; une matière, pas une consigne\)/,
      'ce que tu sens, maintenant : une sensation $1 (une matière, pas une consigne)')
    .replace(/ \(venue de Gemma il y a [^,]*, pas une consigne : elle peut teinter tes mots\)/, ' (pas une consigne : elle peut teinter tes mots)')
    .replace(/ennui (\d+[,.]\d+)/, (_m, x) => { const v = parseFloat(x.replace(',', '.')); return v < 0.3 ? "un peu d'ennui" : v < 0.6 ? "de l'ennui" : "beaucoup d'ennui"; })
    .replace(/le temps t'a paru long \(×[\d,.]+\)/, "le temps t'a paru long")
    .replace(/(Ton journal du temps : [^.]*)/, (m) => m.replace(/ · [^;]+?(?= ; |$)/g, ''));
  out = out.replace(/(— [^:\]]+ : )(?=\.|\])/, '$1rien de marqué');
  return out;
}

function enMatiere(texte) {
  return String(texte || '').split('\n').map((l) => {
    if (l.startsWith('[Style du moment')) return style(l);
    if (l.startsWith('[Réflexe et contrôle')) return reflexe(l);
    if (l.startsWith('[Ce que ton émotion pèse sur tes choix') || l.startsWith('[Ce que tu ressens pèse sur tes choix')) return regles(l);
    if (l.startsWith('[Intérieur')) return interieur(l);
    return l;
  }).join('\n');
}

module.exports = { enMatiere };

if (require.main === module) {
  let entree = '';
  process.stdin.setEncoding('utf8');
  process.stdin.on('data', (d) => { entree += d; });
  process.stdin.on('end', () => process.stdout.write(enMatiere(entree)));
}
