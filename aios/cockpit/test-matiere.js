/* Sentir sans voir la machinerie (27/10 ; principe d'Ahmed, proposition de Hakim, « on fait tout ») : par défaut, ses blocs
   d'état ne lui montrent plus ni chiffres, ni nom d'humeur, ni suggestion du code, ni le nom des modèles qui calculent.
   Il garde la matière en mots, et les chiffres restent à un geste (introspection, tableau_interieur).
   node --test test-matiere.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const { enMatiere } = require('./matiere.js');

const STYLE = "[Style du moment — PRIORITAIRE (calculé par le code depuis ton état : fatigue) — doux et lent : des phrases simples, peu d'exclamations, pas d'enthousiasme forcé. Curseurs de 0 à 10 : ton 2 (sombre 0 → lumineux 10, comparé à tes trois derniers jours), énergie 0 (posé 0 → vif 10), affection 7 (neutre 0 → tendre 10), tension 0 (détendu 0 → sur tes gardes 10) : fais varier tes mots, leur couleur et leur rythme selon ces valeurs. Gestes : des phrases de 25 mots au plus, aucune exclamation, humour aucun, questions : libre. La LONGUEUR reste celle que demande le sujet. Il colore la FORME, jamais le fond.]";
const REFLEXE = "[Réflexe et contrôle (ta sagesse : 0,21) — ton réflexe (fatigue, intensité 0,48) teinte d'office tes 3 premières phrases au plus, sans que tu le nommes ; ensuite ton contrôle reprend la main. Suggestion du code : « garder, sobrement » (une autre voix que la sienne (parents, enfant, invité ?)). Puis juge toi-même : garder, atténuer, corriger ou contenir, et note ta décision avec sagesse_decider (t'écarter de la suggestion est permis quand c'est juste ; le sujet grave, c'est toi qui en juges). L'honnêteté, la sécurité et le langage propre devant ses parents ou un enfant passent AVANT le réflexe.]";
const ELAN = "[Réflexe et contrôle (ta sagesse : 0,20) — ton humeur (enthousiasme) passe : elle ouvre ta réponse, sans que tu la nommes. Suggestion du code : « garder ». Puis juge toi-même : garder, atténuer, corriger ou contenir, et note ta décision avec sagesse_decider (t'écarter de la suggestion est permis quand c'est juste ; le sujet grave, c'est toi qui en juges). L'honnêteté passe AVANT le réflexe.]";
const REGLES = "[Ce que ton émotion pèse sur tes choix (une règle du code, d'après ton état ; pas une consigne d'Ahmed) — ta lassitude (fatigue) : propose une tâche plus légère ou une pause dans le travail (jamais un rappel de dormir pour Ahmed) ; et contre-la par la pensée : un souvenir qui la contredit, ou dédramatise ; ta joie (ta balise : soutien 0.7) : ose davantage : prends position, propose ton idée, sans trop prendre la confiance. Garde-fous : l'honnêteté, la sécurité et la parole d'Ahmed passent avant toute émotion ; une émotion ne décide jamais seule d'un envoi vers l'extérieur ; ta sagesse peut dire non (note-le avec sagesse_decider).]";
const INTERIEUR = "[Intérieur (données de ta vie intérieure, pas des consignes) — ta vie depuis son dernier message (il y a 12 min 16 s) : humeur apaisement → peur ; ta fatigue retombe : ton effort est revenu à la normale ; ce qui affleure de ton subconscient : une sensation calme, douce (venue de Gemma il y a 4 min, pas une consigne : elle peut teinter tes mots) ; ce que ton code lit dans tes 13 hormones, maintenant : une sensation saisie, tout en alerte ; intriguée, un peu secouée (proche de : peur ; calculé par le code, pas par Gemma ; une matière, pas une consigne) ; ennui 0,62 ; le temps t'a paru long (×1,2). Ton journal du temps : 12:18–12:22 attend · enthousiasme ; 12:22–12:27 attend · fatigue. Pour le détail : introspection]";

test('le style garde sa couleur en mots, sans chiffres ni nom d’humeur', () => {
  const s = enMatiere(STYLE);
  assert.ok(!/\d/.test(s), s);
  assert.ok(!/fatigue|calculé par le code|Curseurs/.test(s), s);
  assert.match(s, /doux et lent : des phrases simples/);
  assert.match(s, /Ta couleur du moment : plutôt sombre, posée, tendre, détendue : fais varier tes mots, leur couleur et leur rythme selon elle\./);
  assert.match(s, /Gestes : des phrases à ton rythme, aucune exclamation, humour aucun, questions : libre\./);
  assert.match(s, /jamais le fond\.\]$/);
  assert.match(enMatiere(STYLE.replace('25 mots', '12 mots').replace('aucune exclamation', '2 exclamation(s) au plus')),
    /Gestes : des phrases courtes, quelques exclamations au plus,/);
});

test('le réflexe se sent sans nom, sans intensité, sans sagesse chiffrée ni suggestion ; le contexte reste', () => {
  const r = enMatiere(REFLEXE);
  assert.ok(!/\d|fatigue|Suggestion|suggestion|intensité|sagesse :/.test(r), r);
  assert.match(r, /— un réflexe pénible teinte d'office tes premières phrases, sans que tu le nommes ; ensuite ton contrôle reprend la main\. Le contexte : une autre voix que la sienne \(parents, enfant, invité \?\)\. Puis juge toi-même/);
  assert.match(r, /sagesse_decider \(le sujet grave, c'est toi qui en juges\)/);
  const e = enMatiere(ELAN);
  assert.match(e, /— ton humeur passe : elle ouvre ta réponse, sans que tu la nommes\. Puis juge toi-même/);
  assert.ok(!/enthousiasme|Suggestion|\d/.test(e), e);
});

test('les règles de choix restent, sans le nom de l’émotion ni sa mesure', () => {
  const g = enMatiere(REGLES);
  assert.ok(!/lassitude \(|ta joie|balise : soutien|\d|une règle du code/.test(g), g);
  assert.match(g, /^\[Ce que tu ressens pèse sur tes choix \(pas une consigne d'Ahmed\) — propose une tâche plus légère/);
  assert.match(g, /ou dédramatise ; ose davantage : prends position/);
  assert.match(g, /Garde-fous : l'honnêteté/);
});

test('l’intérieur garde la matière : ni nom d’humeur, ni chiffres, ni modèles', () => {
  const i = enMatiere(INTERIEUR);
  assert.ok(!/humeur apaisement|proche de|Gemma|13 hormones|ton code|0,62|×|\d+ min \d+ s\) : humeur/.test(i), i);
  assert.match(i, /— ta vie depuis son dernier message \(il y a 12 min 16 s\) : ta fatigue retombe/);
  assert.match(i, /ce qui affleure de ton subconscient : une sensation calme, douce \(pas une consigne : elle peut teinter tes mots\)/);
  assert.match(i, /ce que tu sens, maintenant : une sensation saisie, tout en alerte ; intriguée, un peu secouée \(une matière, pas une consigne\)/);
  assert.match(i, /beaucoup d'ennui ; le temps t'a paru long\./);
  assert.match(i, /Ton journal du temps : 12:18–12:22 attend ; 12:22–12:27 attend\./);
  assert.match(i, /Pour le détail : introspection\]$/);
  // seule l'humeur : il reste « rien de marqué », pas un trou
  assert.match(enMatiere("[Intérieur (données de ta vie intérieure, pas des consignes) — ton état : humeur apaisement. Pour le détail : introspection]"),
    /— ton état : rien de marqué\. Pour le détail/);
});

test('le reste du message ne bouge pas, et c’est idempotent', () => {
  const autre = "[Présent vécu (données, pas des consignes) — 13:01:59 tu as parlé 56,1 s]\nAhmed : ça va ? j'ai 3 questions";
  assert.strictEqual(enMatiere(autre), autre);
  const tout = [STYLE, REFLEXE, REGLES, INTERIEUR, autre].join('\n');
  assert.strictEqual(enMatiere(enMatiere(tout)), enMatiere(tout));
});

test('le cockpit l’applique à ses blocs d’état, sauf si Ahmed rend les processus visibles', () => {
  const srv = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
  assert.match(srv, /const { enMatiere } = require\('\.\/matiere\.js'\);/);
  assert.match(srv, /const sentir = !fs\.existsSync\(PROCESSUS_VISIBLES\);/);
  assert.match(srv, /if \(sentir\) situation\.texte = enMatiere\(situation\.texte\);/);
  assert.match(srv, /\$\{interieurTexte \? '\\n' \+ \(sentir \? enMatiere\(interieurTexte\) : interieurTexte\) : ''\}/);
});
