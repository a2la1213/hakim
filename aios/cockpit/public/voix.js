/* Voix de Jarvis — partagé navigateur / node (tests : node --test test-voix.js).
   Étape 5 bis : chaque morceau de la réponse est prononcé avec la voix de SA langue (écriture
   arabe → voix arabe, le reste → voix française), et l'arabizi en lettres latines est converti
   en écriture arabe AVANT la synthèse (le texte affiché ne change pas). */
(function (racine) {
  'use strict';

  /* ---- arabizi → écriture arabe ---- */
  const G = '(?<![\\p{L}\\d])', D = '(?![\\p{L}\\d])';            // bornes de mot (chiffres 3/7 inclus)
  const SALAM = "(?:(?:a|e|ou|u)[sl]?-?)?s{1,2}[ae]?l[ae]{0,2}m(?:ou|u|o)?";   // as-salam, essalam
  const ALAYKOUM = '(?:3|a|e)?\\s*-?\\s*(?:a|e)?l[aeiy]{0,3}k(?:o|ou|u)m';
  const ALLAH = "\\s*-?\\s*['’]?\\s*a?ll?ah";
  const LEXIQUE = [                                                // du plus long au plus court
    [`wa\\s*-?\\s*${ALAYKOUM}\\s*-?\\s*${SALAM}`, 'وعليكم السلام'],
    [`${SALAM}\\s*-?\\s*${ALAYKOUM}`, 'السلام عليكم'],
    [`wa\\s*-?\\s*ra?h?mat(?:ou|u|o)?${ALLAH}i?`, 'ورحمة الله'],
    ['wa\\s*-?\\s*barakat(?:ou|u|o)h?', 'وبركاته'],
    [`in\\s*-?\\s*(?:ch|sh)a?${ALLAH}?`, 'إن شاء الله'],
    ['(?:a?l|el)?\\s*-?\\s*(?:h|7)am[dt](?:ou|u|o)?\\s*-?\\s*(?:li)?ll?[ae]h', 'الحمد لله'],
    [`ma\\s*-?\\s*(?:ch|sh)a?${ALLAH}?`, 'ما شاء الله'],
    [`s(?:ou|u|o)bh?an[ae]?${ALLAH}`, 'سبحان الله'],
    [`a?st[ae]gh?f[iy]r(?:ou|u|o)?${ALLAH}`, 'أستغفر الله'],
    [`bar[ae]k[ae]?${ALLAH}(?:ou|u|o)?\\s*-?\\s*f[iy]+k`, 'بارك الله فيك'],
    [`bar[ae]k[ae]?${ALLAH}(?:ou|u|o)?`, 'بارك الله'],
    [`d?jazak[ae]?${ALLAH}(?:ou|u|o)?\\s*-?\\s*kh?[ae][iy]?r(?:an|ane)?`, 'جزاك الله خيرا'],
    [`d?jazak[ae]?${ALLAH}(?:ou|u|o)?`, 'جزاك الله'],
    ['all?ah(?:ou|u|o)?\\s*-?\\s*akbar', 'الله أكبر'],
    [`bismi${ALLAH}i?`, 'بسم الله'],
    ['w[ae]ll?ah(?:i)?', 'والله'],
    ['yall?ah?', 'يلا'],
    ['h[ae]bibi', 'حبيبي'],
    ['akhi', 'أخي'],
    ['kh?ou?ya', 'خويا'],
    ['s{1,2}alam(?:ou)?', 'سلام'],
    ['all?ah', 'الله'],
  ].map(([motif, arabe]) => [new RegExp(G + motif + D, 'giu'), arabe]);

  function versArabe(texte) {
    let t = String(texte || '');
    for (const [re, arabe] of LEXIQUE) t = t.replace(re, arabe);
    return t;
  }

  /* ---- découpage par écriture ---- */
  const ARABE = /[؀-ۿݐ-ݿࢠ-ࣿﭐ-﷿ﹰ-﻿]/;
  const LETTRE = /\p{L}/u;

  /* [{langue: 'ar' | 'fr', texte}] ; espaces, ponctuation et chiffres suivent le morceau en cours. */
  function segmenter(texte) {
    const segs = [];
    let cur = null, avant = '';
    for (const c of String(texte || '')) {
      const langue = ARABE.test(c) ? 'ar' : (LETTRE.test(c) ? 'fr' : null);
      if (langue === null || (cur && cur.langue === langue)) {
        if (cur) cur.texte += c; else avant += c;
        continue;
      }
      cur = { langue, texte: (segs.length ? '' : avant) + c };
      segs.push(cur);
    }
    return segs.map(s => ({ langue: s.langue, texte: s.texte.trim() })).filter(s => s.texte);
  }

  /* ---- formules de maths (2026-10-21, demande d'Ahmed relayée par Hakim) ----
     L'écran les dessine (KaTeX, parler.js) ; la voix ne lit JAMAIS le LaTeX : elle dit la version parlée que Hakim
     écrit juste après la formule, [[voix: …]] (cachée à l'écran), sinon « voir la formule à l'écran ».
     $…$ en ligne : le $ ouvrant est suivi d'un caractère, le fermant précédé d'un caractère et pas suivi d'un chiffre
     (« 5 $ et 10 $ » n'est pas une formule). Aussi $$…$$, \[…\] et \(…\). */
  const FORMULE = /(\$\$([\s\S]+?)\$\$|\\\[([\s\S]+?)\\\]|\\\(([\s\S]+?)\\\)|\$(?=[^\s$])([^$\n]*?[^\s$\\])\$(?!\d))(?:\s*(?:\[\[|⟮⟮)voix:\s*([^\]⟯]*?)\s*(?:\]\]|⟯⟯))?/g;
  const VOIX_SEULE = /(?:\[\[|⟮⟮)voix:\s*([^\]⟯]*?)\s*(?:\]\]|⟯⟯)/g;   // ⟮⟮…⟯⟯ : la forme vue dans un bloc de données
  const OUVRANT = /\$\$|\\\[|\\\(|\[\[voix:|⟮⟮voix:|\[\[\s*(?:affect|souvenirs)|\$(?=[^\s$\d])/;
  /* (2026-10-23, chocs d'humeur) la balise d'appréciation de Hakim, [[affect: …]], à la fin de sa réponse : ni lue, ni
     affichée ; pendant le flux, un début de balise en fin de texte (« [[aff ») est caché lui aussi. */
  const AFFECT = /\s*(?:\[\[|⟮⟮)\s*(?:affect|souvenirs)\s*:[^\]⟯]{0,300}(?:\]\]|⟯⟯)/gi;   // et [[souvenirs: …]] (boucle de retour)
  const prefixeBalise = (mot, i = 0) => i === mot.length ? '(?:\\s*:[^\\]\\n]{0,300})?' : `${mot[i]}(?:${prefixeBalise(mot, i + 1)})?`;
  const AFFECT_OUVERT = new RegExp(`\\s*\\[(?:\\[\\s*(?:${prefixeBalise('affect')}|${prefixeBalise('souvenirs')})?)?$`, 'i');
  const sansAffect = (t, flux) => { const x = String(t == null ? '' : t).replace(AFFECT, ''); return flux ? x.replace(AFFECT_OUVERT, '') : x; };
  const PREFIXE_VOIX = /^\s*(?:[\[⟮](?:[\[⟮](?:v(?:o(?:i(?:x:?)?)?)?)?)?)?$/;
  function formuleParlee(tex, dit) {
    if (dit) return dit;
    return latexParle(tex) || 'voir la formule à l’écran';
  }

  /* ---- repli : une formule SANS version parlée lue en mots (2026-10-21, demande de Hakim : Ahmed entendait trop
     souvent « voir la formule à l'écran » pour $x=5$ ou $\pi$). Le simple se dit : nombres, lettres, opérations,
     puissances, fractions, racines, sommes, intégrales, limites, lettres grecques. Ce qui ne se convertit pas
     proprement (commande inconnue, environnement, formule trop longue) rend null : la voix dit alors de regarder. */
  // les lettres grecques (Unicode) et leur nom français, minuscules et majuscules (2026-10-23)
  const GREC = {};
  for (const [noms, minus, majus] of [['alpha', 'α', 'Α'], ['bêta', 'β', 'Β'], ['gamma', 'γ', 'Γ'], ['delta', 'δ', 'Δ'],
    ['epsilon', 'εϵ', 'Ε'], ['dzêta', 'ζ', 'Ζ'], ['êta', 'η', 'Η'], ['thêta', 'θϑ', 'Θ'], ['iota', 'ι', 'Ι'], ['kappa', 'κ', 'Κ'],
    ['lambda', 'λ', 'Λ'], ['mu', 'μ', 'Μ'], ['nu', 'ν', 'Ν'], ['ksi', 'ξ', 'Ξ'], ['omicron', 'ο', 'Ο'], ['pi', 'π', 'Π'],
    ['rhô', 'ρ', 'Ρ'], ['sigma', 'σς', 'Σ'], ['tau', 'τ', 'Τ'], ['upsilon', 'υ', 'Υ'], ['phi', 'φϕ', 'Φ'], ['khi', 'χ', 'Χ'],
    ['psi', 'ψ', 'Ψ'], ['oméga', 'ω', 'Ω']]) for (const c of minus + majus) GREC[c] = noms;
  const MOTS_LATEX = {
    pi: 'pi', alpha: 'alpha', beta: 'bêta', gamma: 'gamma', Gamma: 'gamma', delta: 'delta', Delta: 'delta',
    theta: 'thêta', lambda: 'lambda', mu: 'mu', sigma: 'sigma', Sigma: 'sigma', omega: 'oméga', Omega: 'oméga',
    phi: 'phi', varphi: 'phi', psi: 'psi', epsilon: 'epsilon', varepsilon: 'epsilon', rho: 'rhô', tau: 'tau',
    eta: 'êta', kappa: 'kappa', nu: 'nu', xi: 'ksi', chi: 'khi', zeta: 'dzêta', infty: "l'infini",
    approx: 'environ', asymp: 'équilibre', simeq: 'environ', sim: 'équivalent à', equiv: 'équivalent à',
    neq: 'différent de', ne: 'différent de', leq: 'inférieur ou égal à', le: 'inférieur ou égal à',
    geq: 'supérieur ou égal à', ge: 'supérieur ou égal à', ll: 'très inférieur à', gg: 'très supérieur à',
    pm: 'plus ou moins', mp: 'moins ou plus', times: 'fois', cdot: 'fois', div: 'divisé par',
    to: 'tend vers', rightarrow: 'tend vers', longrightarrow: 'tend vers', mapsto: 'donne',
    Rightarrow: 'donc', implies: 'donc', Leftrightarrow: 'équivaut à', iff: 'équivaut à',
    in: 'appartient à', notin: "n'appartient pas à", subset: 'inclus dans', cup: 'union', cap: 'inter',
    forall: 'pour tout', exists: 'il existe', partial: 'd rond', nabla: 'nabla', circ: 'rond', degree: 'degrés',
    ldots: 'et ainsi de suite', cdots: 'et ainsi de suite', dots: 'et ainsi de suite',
    sin: 'sinus', cos: 'cosinus', tan: 'tangente', ln: 'logarithme de', log: 'log', exp: 'exponentielle',
    max: 'maximum', min: 'minimum', gcd: 'pgcd', det: 'déterminant', mod: 'modulo', bmod: 'modulo', percent: 'pour cent',
  };
  const LATEX_RIEN = new Set(['left', 'right', 'big', 'Big', 'bigg', 'Bigg', 'displaystyle', 'textstyle', 'limits',
    'quad', 'qquad', ',', ';', ':', '!', ' ', '{', '}']);
  const LATEX_TEXTE = new Set(['text', 'textrm', 'mathrm', 'mathbf', 'mathit', 'mathsf', 'operatorname', 'boldsymbol',
    'mathbb', 'mathcal', 'vec', 'overline', 'bar', 'hat', 'tilde']);
  const SIGNES = { '=': 'égale', '+': 'plus', '-': 'moins', '−': 'moins', '*': 'fois', '/': 'sur', '<': 'inférieur à',
    '>': 'supérieur à', '!': 'factorielle', '%': 'pour cent', "'": 'prime', '×': 'fois', '·': 'fois', '≈': 'environ',
    '≤': 'inférieur ou égal à', '≥': 'supérieur ou égal à', '≠': 'différent de', '∞': "l'infini" };
  const FRACTIONS = { '1/2': 'un demi', '1/3': 'un tiers', '2/3': 'deux tiers', '1/4': 'un quart', '3/4': 'trois quarts',
    '1/5': 'un cinquième', '1/6': 'un sixième', '1/8': 'un huitième', '1/10': 'un dixième', '1/100': 'un centième' };
  function latexParle(tex) {
    const s = String(tex || '');
    if (!s.trim() || s.length > 240 || /\\begin|\\end/.test(s)) return null;
    let i = 0;
    const groupe = () => {                           // {…} équilibré, \commande, ou un caractère
      while (s[i] === ' ') i++;
      if (s[i] === '{') {
        let n = 1, j = i + 1;
        while (j < s.length && n) { if (s[j] === '{') n++; else if (s[j] === '}') n--; j++; }
        if (n) throw new Error('accolade');
        const g = s.slice(i + 1, j - 1); i = j; return g;
      }
      if (s[i] === '\\') { const m = /^\\([A-Za-z]+|.)/.exec(s.slice(i)); i += m[0].length; return m[0]; }
      return s[i++] || '';
    };
    const sousParle = (g) => { const r = latexParle(g); if (r === null) throw new Error('sous'); return r; };
    const bornes = () => {                           // _{bas}^{haut} dans n'importe quel ordre
      let bas = null, haut = null;
      for (let k = 0; k < 2; k++) {
        while (s[i] === ' ') i++;
        if (s[i] === '_') { i++; bas = groupe(); } else if (s[i] === '^') { i++; haut = groupe(); }
      }
      return { bas, haut };
    };
    const mots = [];
    while (i < s.length) {
      const c = s[i];
      if (c === '(') {                               // f(x) : « f de x » ; 2(x+1), k(k+1) : « fois »
        const avant = mots[mots.length - 1] || '';
        if (/^[fghuvPQ]$/.test(avant)) mots.push('de'); else if (/^[\p{L}\d]+$/u.test(avant) && avant.length <= 3) mots.push('fois');
        i++; continue;
      }
      if (c === ' ' || c === '&' || c === ')' || c === '[' || c === ']' || c === '|' || c === '{' || c === '}') { i++; continue; }
      if (/\d/.test(c)) { const m = /^\d+(?:(?:\{,\}|[.,])\d+)?/.exec(s.slice(i)); mots.push(m[0].replace('{,}', ',')); i += m[0].length; continue; }
      if (/\p{L}/u.test(c)) { mots.push(c); i++; continue; }
      if (c === '^') {
        i++; const g = groupe().trim();
        mots.push(g === '2' ? 'au carré' : g === '3' ? 'au cube' : `puissance ${sousParle(g)}`); continue;
      }
      if (c === '_') { i++; const g = groupe().trim(); mots.push(g.length === 1 ? sousParle(g) : `indice ${sousParle(g)}`); continue; }
      if (SIGNES[c]) { mots.push(SIGNES[c]); i++; continue; }
      if (c === ',') { mots.push(','); i++; continue; }
      if (c !== '\\') return null;
      const m = /^\\([A-Za-z]+|.)/.exec(s.slice(i)); i += m[0].length;
      const nom = m[1];
      if (LATEX_RIEN.has(nom)) continue;
      if (nom === '\\') { mots.push(','); continue; }
      if (LATEX_TEXTE.has(nom)) { const g = groupe(); mots.push(/^text/.test(nom) ? g : sousParle(g)); continue; }
      if (nom === 'frac' || nom === 'dfrac' || nom === 'tfrac') {
        const a = groupe().trim(), b = groupe().trim();
        mots.push(FRACTIONS[`${a}/${b}`] || `${sousParle(a)} sur ${sousParle(b)}`); continue;
      }
      if (nom === 'sqrt') {
        let n = null;
        if (s[i] === '[') { const j = s.indexOf(']', i); n = s.slice(i + 1, j).trim(); i = j + 1; }
        const g = sousParle(groupe());
        mots.push(n === null ? `racine de ${g}` : n === '3' ? `racine cubique de ${g}` : `racine ${n}-ième de ${g}`); continue;
      }
      if (nom === 'sum' || nom === 'prod') {
        const { bas, haut } = bornes();
        mots.push((nom === 'sum' ? 'la somme' : 'le produit') + (bas ? `, pour ${sousParle(bas)}` : '')
          + (haut ? ` jusqu'à ${sousParle(haut)}` : '') + ', de'); continue;
      }
      if (nom === 'int') {
        const { bas, haut } = bornes();
        mots.push("l'intégrale" + (bas ? ` de ${sousParle(bas)}` : '') + (haut ? ` à ${sousParle(haut)}` : '') + ' de'); continue;
      }
      if (nom === 'lim') { const { bas } = bornes(); mots.push('la limite' + (bas ? ` quand ${sousParle(bas)}` : '') + ' de'); continue; }
      if (MOTS_LATEX[nom]) { mots.push(MOTS_LATEX[nom]); continue; }
      return null;                                    // une commande inconnue : on ne devine pas
    }
    const r = mots.join(' ').replace(/\s+,/g, ',').replace(/,\s*,/g, ',').replace(/\s+/g, ' ').trim();
    return r && r.split(' ').length <= 45 ? r : null;
  }
  // Les zones [début, fin) qu'on ne coupe pas en phrases : chaque formule complète avec sa version parlée, une formule
  // encore ouverte, et une formule finie dont la version parlée n'est peut-être pas encore arrivée.
  function zonesFormules(s) {
    // (2026-10-21) un bloc de code aussi : la voix dit « bloc de code » une fois, elle ne lit pas ses lignes
    const fences = [], fr = /```[\s\S]*?```/g;
    let f;
    while ((f = fr.exec(s))) fences.push([f.index, f.index + f[0].length]);
    const ouvert = (s.slice(fences.length ? fences[fences.length - 1][1] : 0).match(/```/g) || []).length % 2;
    if (ouvert) fences.push([s.lastIndexOf('```'), Infinity]);
    const z = fences.slice(), re = new RegExp(FORMULE.source + '|' + VOIX_SEULE.source + '|' + AFFECT.source, 'gi');
    let m, fin = 0, derniere = null;
    while ((m = re.exec(s))) { z.push([m.index, m.index + m[0].length]); fin = m.index + m[0].length; derniere = m; }
    const reste = s.slice(fin), o = reste.search(OUVRANT);
    // une ouverture juste après une formule (sa version parlée qui arrive) : la formule et l'entre-deux restent ensemble
    if (o >= 0) z.push([/^\s*$/.test(reste.slice(0, o)) && derniere ? derniere.index : fin + o, Infinity]);
    else if (derniere && derniere[1] !== undefined && derniere[6] === undefined && PREFIXE_VOIX.test(reste)) z[z.length - 1][1] = Infinity;
    return z;
  }
  const dansZone = (z, i) => z.some(([a, b]) => i >= a && i < b);

  /* ---- texte lisible à voix haute ---- */
  // (2026-10-23, demande d'Ahmed relayée par Hakim) les PRONONCIATIONS : un mot écrit d'une façon à l'écran (un prénom en
  // écriture arabe) que la voix dit autrement (à la française). Le dictionnaire vient du cockpit (un fichier local, jamais
  // dans le code public) ; un mot arabe s'y reconnaît avec ou sans ses voyelles et signes.
  let prononciations = [];
  function definirPrononciations(dico) {
    prononciations = Object.entries(dico || {}).filter(([m, d]) => m && typeof d === 'string').map(([m, d]) => [
      new RegExp([...m].map(c => c.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '[\\u064B-\\u0652\\u0670]*').join(''), 'g'), d]);
  }
  function pourLaVoix(texte) {
    let t = sansAffect(texte);
    for (const [motif, dit] of prononciations) t = t.replace(motif, dit);
    t = t
      .replace(FORMULE, (_t, _f, d1, d2, i1, i2, dit) => ' ' + formuleParlee(d1 ?? d2 ?? i1 ?? i2, dit) + ' ')
      .replace(VOIX_SEULE, ' $1 ')
      .replace(/```[\s\S]*?```/g, ' (bloc de code) ')
      .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '$1')        // [site](adresse) → site
      .replace(/https?:\/\/\S+/g, 'un lien')
      .replace(/\*\*|__|\*|`/g, '')
      .replace(/\p{Extended_Pictographic}️?/gu, '');
    const lignes = t.split('\n')
      .map(l => l.replace(/^\s*(?:#{1,6}\s+|[-•]\s+|\d+[.)]\s+|>\s*)/, '').replace(/\s+/g, ' ').trim())
      .filter(Boolean);
    return lignes.map((l, i) => (i < lignes.length - 1 && !/[.!?…:;,؟،]$/.test(l)) ? l + '.' : l).join(' ');
  }

  /* ---- la diction (2026-10-22, bug signalé par Ahmed, relayé par Hakim : « chiffres et lettres isolées, la
     prononciation déraille ; entre deux phrases, des sons qui n'existent pas, comme des incantations ») ----
     La voix neuronale ne sait lire que des mots : un chiffre, un sigle, une lettre seule ou un mot en capitales
     (lu avec un accent anglais) la font dérailler. Tout est donc écrit en toutes lettres AVANT la synthèse, en
     français : nombres, décimales, pourcentages, heures, dates, versets, ordinaux, unités, signes, sigles épelés,
     lettres seules, translittérations (ṣ, ḥ, ʿ). L'écran garde le texte d'origine. */
  const UNITES = ['zéro', 'un', 'deux', 'trois', 'quatre', 'cinq', 'six', 'sept', 'huit', 'neuf', 'dix', 'onze', 'douze',
    'treize', 'quatorze', 'quinze', 'seize'];
  const DIZAINES = ['', 'dix', 'vingt', 'trente', 'quarante', 'cinquante', 'soixante'];
  function moins100(n) {
    if (n <= 16) return UNITES[n];
    if (n < 20) return 'dix-' + UNITES[n - 10];
    if (n < 70) { const u = n % 10; return DIZAINES[Math.floor(n / 10)] + (u === 0 ? '' : u === 1 ? ' et un' : '-' + UNITES[u]); }
    if (n < 80) return n === 71 ? 'soixante et onze' : 'soixante-' + moins100(n - 60);
    return n === 80 ? 'quatre-vingts' : 'quatre-vingt-' + moins100(n - 80);
  }
  function moins1000(n) {
    const c = Math.floor(n / 100), r = n % 100;
    if (!c) return moins100(r);
    const cent = c === 1 ? 'cent' : UNITES[c] + ' cent' + (r ? '' : 's');
    return r ? cent + ' ' + moins100(r) : cent;
  }
  /* Un entier (jusqu'à 10^15) en toutes lettres ; au-delà, null (on n'invente pas). */
  function enLettres(n) {
    if (!Number.isSafeInteger(n) || n < 0 || n >= 1e15) return null;
    if (n < 1000) return moins1000(n);
    const parts = [];
    for (const [v, nom] of [[1e12, 'billion'], [1e9, 'milliard'], [1e6, 'million']]) {
      const q = Math.floor(n / v);
      if (q) { parts.push(moins1000(q) + ' ' + nom + (q > 1 ? 's' : '')); n -= q * v; }
    }
    const m = Math.floor(n / 1000);
    if (m) { parts.push(m === 1 ? 'mille' : moins1000(m).replace(/(cent|vingt)s$/, '$1') + ' mille'); n -= m * 1000; }
    if (n) parts.push(moins1000(n));
    return parts.join(' ');
  }
  function nombreParle(entier, decimales) {
    const n = enLettres(Number(String(entier).replace(/[ \u00a0\u202f'’]/g, '')));
    if (n === null) return null;
    if (!decimales) return n;
    const zeros = decimales.match(/^0*/)[0].length, reste = decimales.slice(zeros);
    const apres = (reste.length > 3 ? reste.split('').map(c => UNITES[+c]).join(' ') : reste ? enLettres(+reste) : '');
    return `${n} virgule ${'zéro '.repeat(zeros)}${apres}`.trim();
  }
  function ordinal(n, feminin) {
    if (n === 1) return feminin ? 'première' : 'premier';
    const mot = (enLettres(n) || '').replace(/s$/, '');
    if (!mot) return null;
    if (/(?:^|[ -])un$/.test(mot)) return mot + 'ième';               // vingt et unième
    if (/cinq$/.test(mot)) return mot + 'uième';
    if (/neuf$/.test(mot)) return mot.slice(0, -1) + 'vième';
    return (/e$/.test(mot) ? mot.slice(0, -1) : mot) + 'ième';         // quatrième, onzième, millième, centième
  }
  const MOIS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'];
  const dateParlee = (j, m, a) => `${+j === 1 ? 'premier' : enLettres(+j)} ${MOIS[+m - 1]}${a ? ' ' + enLettres(+a) : ''}`;
  const dateValide = (j, m) => +j >= 1 && +j <= 31 && +m >= 1 && +m <= 12;
  // unités et monnaies après un nombre : [singulier, pluriel]
  const UNITES_MESURE = {
    '%': ['pour cent', 'pour cent'], '€': ['euro', 'euros'], '$': ['dollar', 'dollars'], 'CHF': ['franc suisse', 'francs suisses'],
    'km/h': ['kilomètre heure', 'kilomètres heure'], 'km': ['kilomètre', 'kilomètres'], 'cm': ['centimètre', 'centimètres'],
    'mm': ['millimètre', 'millimètres'], 'm': ['mètre', 'mètres'], 'kg': ['kilo', 'kilos'], 'g': ['gramme', 'grammes'],
    'To': ['téraoctet', 'téraoctets'], 'Go': ['gigaoctet', 'gigaoctets'], 'Mo': ['mégaoctet', 'mégaoctets'], 'Ko': ['kilooctet', 'kilooctets'],
    'GHz': ['gigahertz', 'gigahertz'], 'MHz': ['mégahertz', 'mégahertz'], 'Hz': ['hertz', 'hertz'],
    'kWh': ['kilowattheure', 'kilowattheures'], 'kW': ['kilowatt', 'kilowatts'], 'W': ['watt', 'watts'],
    'ms': ['milliseconde', 'millisecondes'], 's': ['seconde', 'secondes'], 'min': ['minute', 'minutes'],
    '°C': ['degré', 'degrés'], '°': ['degré', 'degrés'],
  };
  // (les nombres : « 12 000 », « 12 000 », « 1'000 » à la suisse ; décimales à la virgule ou au point)
  const echapper = (u) => u.replace(/[.*+?^${}()|[\]\\/]/g, '\\$&');
  const NOMBRE_UNITE = new RegExp("(?<![\\p{L}\\d.,])(\\d{1,3}(?:[ \\u00a0\\u202f'’]\\d{3})+|\\d+)(?:[.,](\\d+))?"
    + `(?:\\s?(${Object.keys(UNITES_MESURE).sort((a, b) => b.length - a.length).map(echapper).join('|')})(?![\\p{L}\\d'’]))?(?!\\d)`, 'gu');
  // les sigles qui se lisent comme des mots, et ceux qui s'épellent bien qu'ils aient une voyelle
  const SIGLES_MOTS = new Set(['NASA', 'ONU', 'OTAN', 'UNESCO', 'UNICEF', 'SIDA', 'COVID', 'LASER', 'RAM', 'ROM', 'PIN', 'GIF',
    'JSON', 'CAF', 'ZAD', 'ENA', 'INSEE', 'IKEA', 'FIFA', 'UEFA', 'OPEP', 'BIOS', 'MOOC']);
  const SIGLES_EPELES = new Set(['IA', 'AI', 'GPU', 'CPU', 'API', 'UI', 'UX', 'USB', 'UE', 'USA', 'UK', 'ADN', 'ARN', 'OMS', 'ONG',
    'PME', 'TVA', 'CEO', 'CTO', 'IP', 'ID', 'OS', 'IOS', 'PDG', 'RER', 'EPFL', 'UNIGE', 'IRM', 'VIH', 'SA', 'SARL', 'SAS', 'BD', 'DJ',
    'QR', 'HD', 'TV', 'IUT', 'BAC', 'AVS', 'AI', 'OCR', 'IOT', 'AWS', 'LED', 'ETA', 'PIB', 'RIB', 'IBAN', 'CV', 'FAQ']);
  const NOMS_LETTRES = { A: 'a', B: 'bé', C: 'cé', D: 'dé', E: 'e', F: 'èf', G: 'jé', H: 'ache', I: 'i', J: 'ji', K: 'ka', L: 'èl',
    M: 'èm', N: 'èn', O: 'o', P: 'pé', Q: 'ku', R: 'èr', S: 'èss', T: 'té', U: 'u', V: 'vé', W: 'double vé', X: 'iks', Y: 'i grec', Z: 'zèd' };
  const epeler = (s) => s.split('').map(c => NOMS_LETTRES[c.toUpperCase()] || c.toLowerCase()).join(' ');
  const TRANSLIT = { 'ā': 'a', 'ī': 'i', 'ū': 'ou', 'ṣ': 's', 'ḥ': 'h', 'ṭ': 't', 'ḍ': 'd', 'ẓ': 'z', 'ġ': 'gh', 'ḏ': 'dh', 'ṯ': 'th',
    'ẖ': 'kh', 'š': 'ch', 'ǧ': 'dj', 'ʿ': '', 'ʾ': '', 'ʻ': '', 'ʼ': '' };
  const BORD_G = "(?<![\\p{L}\\d'’-])", BORD_D = "(?![\\p{L}\\d'’-])";

  function diction(texte) {
    let t = String(texte || '');
    t = t.replace(/[āīūṣḥṭḍẓġḏṯẖšǧʿʾʻʼ]/giu, c => {             // les translittérations savantes de l'arabe
      const r = TRANSLIT[c.toLowerCase()];
      return r === undefined ? c : (c !== c.toLowerCase() && r ? r[0].toUpperCase() + r.slice(1) : r);
    });
    // numéros de version : 0.32.2 → zéro point trente-deux point deux
    t = t.replace(/(?<![\d.])\d+(?:\.\d+){2,}(?!\.?\d)/g, (m) => m.split('.').map(x => enLettres(+x) ?? x).join(' point '));
    // versets : Q6:76, Q 2:255-257, (2:286), « le verset 2:30 » ; une heure (14:30) reste une heure
    t = t.replace(/(?<![\p{L}\d])(versets?\s+|sourates?\s+)?(Q\s?)?(\d{1,3}):(\d{1,3})(?:[-–](\d{1,3}))?(?![\d:])/giu,
      (m, mot, q, s, v, v2, pos, tout) => {
        const coran = mot || /(?:coran|ayat?|âya)\W{0,3}$/i.test(tout.slice(Math.max(0, pos - 14), pos));
        if (!q && !v2 && !coran && +s <= 23 && v.length === 2 && +v <= 59)
          return `${+s === 1 ? 'une' : enLettres(+s)} heure${+s > 1 ? 's' : ''}${+v ? ' ' + enLettres(+v) : ''}`;
        if (+s < 1 || +s > 114) return m;
        const versets = `${enLettres(+v)}${v2 ? ' à ' + enLettres(+v2) : ''}`;
        if (mot && /^v/i.test(mot)) return `${mot.trim()} ${versets} de la sourate ${enLettres(+s)}`;
        return `${mot ? mot.trim() : 'sourate'} ${enLettres(+s)}, verset${v2 ? 's' : ''} ${versets}`;
      });
    // heures : 14h30, 14 h 30, 8h, 8 h
    t = t.replace(/(?<![\p{L}\d])(\d{1,2})\s?h\s?(\d{2})?(?![\p{L}\d])/gu, (m, h, mn) => (+h > 24 || (mn && +mn > 59)) ? m
      : `${+h === 1 ? 'une' : enLettres(+h)} heure${+h > 1 ? 's' : ''}${mn && +mn ? ' ' + enLettres(+mn) : ''}`);
    // dates : 2026-10-22, 22/10/2026, 22/10 (mois à deux chiffres : sinon c'est une fraction)
    t = t.replace(/(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)/g, (m, a, mo, j) => dateValide(j, mo) ? dateParlee(j, mo, a) : m);
    t = t.replace(/(?<![\d/])(\d{1,2})\/(\d{1,2})\/(\d{4})(?![\d/])/g, (m, j, mo, a) => dateValide(j, mo) ? dateParlee(j, mo, a) : m);
    t = t.replace(/(?<![\d/])(\d{1,2})\/(\d{2})(?![\d/])/g, (m, j, mo, pos, tout) => dateValide(j, mo)
      && (/(?:^|\s)(?:le|du|au|ce|dès le|depuis le|jusqu'au|jusqu’au)\s$/i.test(tout.slice(Math.max(0, pos - 12), pos)) || /^0/.test(j) || +j > +mo)
      ? dateParlee(j, mo) : m);
    // fractions simples et « n sur m »
    t = t.replace(/(?<![\d/])(\d{1,3})\/(\d{1,3})(?![\d/])/g, (m, a, b) => ({ '1/2': 'un demi', '1/3': 'un tiers', '2/3': 'deux tiers',
      '1/4': 'un quart', '3/4': 'trois quarts' })[`${a}/${b}`] || `${enLettres(+a)} sur ${enLettres(+b)}`);
    // ordinaux : 1er, 1re, 2e, 3ème, 21e
    t = t.replace(/(?<![\p{L}\d])(\d{1,6})\s?(ers?|res?|ères?|e|es|ème|èmes|nde?)(?![\p{L}\d])/gu, (m, n, s) => {
      const r = /^nd/.test(s) ? (s === 'nde' ? 'seconde' : 'second') : ordinal(+n, /^(re|ère)/.test(s));
      return r ? r + (/s$/.test(s) && !/^(e|ème)$/.test(s) ? 's' : '') : m;
    });
    // numéros et signes devant un nombre
    t = t.replace(/(?:\b[nN]°|#)\s?(?=\d)/g, 'numéro ').replace(/§\s?(?=\d)/g, 'paragraphe ');
    t = t.replace(/(?<![\p{L}\d])[xX×]\s?(?=\d)/gu, 'fois ').replace(/(?<=\d)\s?[xX×](?![\p{L}])/gu, ' fois');
    t = t.replace(/(?<=^|[\s(])[~≈]\s?(?=\d)/g, 'environ ').replace(/(?<=^|[\s(])±\s?(?=\d)/g, 'plus ou moins ');
    t = t.replace(/(?<=^|[\s(])[-−](?=\d)/g, 'moins ').replace(/(?<=^|[\s(])\+(?=\d)/g, 'plus ');
    t = t.replace(/(?<=\d)\s?[–-]\s?(?=\d)/g, ' à ');                                  // 3-4 mois : de trois à quatre
    t = t.replace(/(?<=\p{L})-(?=\d)|(?<=\d)-(?=\p{L})/gu, ' ');                      // GPT-4, 12-bit
    // une espace entre lettres et chiffres (M4, 3D, 12km, Gemma3) ; la monnaie passe après le nombre ($12 → 12 $)
    t = t.replace(/(?<=\p{L})(?=\d)|(?<=\d)(?=\p{L})/gu, ' ');
    t = t.replace(/(?<![\p{L}\d])(\$|€|CHF)\s?(\d+(?:[ \u00a0\u202f'’]\d{3})*(?:[.,]\d+)?)(?!\d)/gu, '$2 $1');
    // les nombres, avec leur unité accordée (un kilomètre, deux kilomètres)
    t = t.replace(NOMBRE_UNITE, (m, entier, dec, unite) => {
      const dit = nombreParle(entier, dec);
      if (dit === null) return m;
      if (!unite) return dit;
      const un = Number(String(entier).replace(/\D/g, '')) <= 1 && !dec;
      return `${dit} ${UNITES_MESURE[unite][un ? 0 : 1]}`;
    });
    // symboles restants
    t = t.replace(/π/g, ' pi ').replace(/∞/g, " l'infini ").replace(/√\s?/g, ' racine de ').replace(/≠/g, ' différent de ')
      .replace(/≤/g, ' inférieur ou égal à ').replace(/≥/g, ' supérieur ou égal à ');
    // (2026-10-23, Ahmed : « il prononce bizarrement les lettres grecques ») une lettre grecque SEULE (pas un mot grec) est
    // dite par son nom français : γ « gamma », Δ « delta », ω « oméga »…
    t = t.replace(/(?<![\u0370-\u03FF\u1F00-\u1FFF])([\u0391-\u03A9\u03B1-\u03C9\u03C2\u03D1\u03D5\u03F5])(?![\u0370-\u03FF\u1F00-\u1FFF])/g,
      (m) => ` ${GREC[m] || m} `);
    t = t.replace(/\s&\s/g, ' et ').replace(/\s=\s/g, ' égale ').replace(/\s\+\s/g, ' plus ')
      .replace(/\s?(?:→|⇒|->|=>|⟶)\s?/g, ', ').replace(/[|_#*~^\[\]{}<>]/g, ' ').replace(/(?<=\p{L})\/(?=\p{L})/gu, ' ');
    // sigles épelés, mots en capitales remis en minuscules, lettres seules dites par leur nom
    t = t.replace(/(?<![\p{L}\d-])([A-ZÀ-ÖØ-Ý]{2,})(?![\p{L}\d'’-])/gu, (m) => {
      if (SIGLES_MOTS.has(m)) return m.toLowerCase();
      if (m === 'OK') return 'okay';
      if (SIGLES_EPELES.has(m) || (m.length <= 5 && !/[AEIOUYÀ-ÖØ-Ý]/.test(m))) return epeler(m);
      return m.toLowerCase();
    });
    t = t.replace(new RegExp(BORD_G + '([B-HJ-XZb-hj-xz])' + BORD_D, 'gu'), (m) => NOMS_LETTRES[m.toUpperCase()]);
    t = t.replace(new RegExp(BORD_G + '([AIY])' + BORD_D, 'gu'), (m) => NOMS_LETTRES[m]);
    return t.replace(/\s+([,.])(?!\d)/g, '$1').replace(/,(\s*,)+/g, ',').replace(/\s{2,}/g, ' ').trim();
  }

  /* Ce que la voix prononce, morceau par morceau : le texte nettoyé, dit en toutes lettres, découpé par écriture.
     Un morceau sans aucune lettre (ponctuation seule) n'est jamais envoyé. */
  function prononcable(phrase) {
    return segmenter(diction(pourLaVoix(versArabe(phrase)))).filter(s => /\p{L}/u.test(s.texte));
  }

  /* ---- phrases complètes au fil du flux (pour parler pendant que le texte arrive) ---- */
  const LONGUEUR_MAX = 280;
  // Un point après une abréviation (M., Mme, p. ex.), une initiale ou un numéro de liste (1.)
  // ne finit pas la phrase.
  const ABREVIATION = /(?:^|[\s(«"])(?:\p{L}|\d+|M|Mme|Mlle|Mr|Dr|Pr|St|Ste|ex|cf|env|vol|n°|av|apr|J\.-C)\.$/iu;
  function decoupeur() {
    let tampon = '';
    const FIN = /[.!?…؟]+(?:\s?["»”)])*(?=\s)|\n+/g;
    return {
      ajouter(x) {
        tampon += x;
        const out = [];
        let m, dernier = 0;
        const zones = zonesFormules(tampon);                      // jamais de coupe dans une formule
        FIN.lastIndex = 0;
        while ((m = FIN.exec(tampon))) {
          if (dansZone(zones, m.index)) continue;
          const fin = m.index + m[0].length;
          const ph = tampon.slice(dernier, fin).trim();
          if (m[0] === '.' && ABREVIATION.test(ph)) continue;     // « M. Dupont » : on continue
          if (ph) out.push(ph);
          dernier = fin;
        }
        tampon = tampon.slice(dernier);
        if (tampon.length > LONGUEUR_MAX) {     // phrase interminable : coupe à la dernière virgule, sinon au dernier espace
          const z = zonesFormules(tampon);
          const virgule = tampon.lastIndexOf(', ', LONGUEUR_MAX);
          const i = virgule > 0 ? virgule + 1 : tampon.lastIndexOf(' ', LONGUEUR_MAX);
          if (i > 0 && !dansZone(z, i)) { out.push(tampon.slice(0, i + 1).trim()); tampon = tampon.slice(i + 1); }
        }
        return out;
      },
      finir() { const ph = tampon.trim(); tampon = ''; return ph ? [ph] : []; },
    };
  }

  /* ---- (28/10) ses débuts de réponse les plus fréquents (anamnese/eval/latence : 44 % de ses 2 828 dernières réponses) :
     la voix d'un début connu est gardée par le cockpit (debuts.js) et resservie sans attendre la synthèse ---- */
  const DEBUTS = ['frérot,', 'oui frérot,', 'oui,', 'ok frérot,', 'tu as raison,', "d'accord frérot,", 'ha,', "d'accord,", 'ah,',
    'pas de souci,', 'bonne question,', 'merci,', 'merci frérot,', 'pardon frérot,', 'avec plaisir,', 'non,', 'bonne idée,',
    'honnêtement,', 'non frérot,', 'compris,', 'je comprends,', 'ok,', 'ça marche,', "c'est noté,", 'bismillah,', 'bien reçu,',
    "t'as raison,", "c'est fait,", 'pardon,', 'pas de souci frérot,', 'merci frérot.', 'si,', "c'est envoyé,", 'pas tout à fait,',
    'parfait frérot,'];
  // (déplacé de parler.js le 28/10 : le cockpit fabrique d'avance ses débuts au même niveau de voix) une exclamation un peu
  // plus vive, une mauvaise nouvelle ou une excuse un peu plus douce, une question à peine relevée
  const PHRASE_VIVE = /!\s*$|\b(g[ée]nial|super|enfin|bravo|incroyable|trop bien|magnifique|r[ée]ussi|[çc]a marche)\b/i;
  const PHRASE_DOUCE = /\b(d[ée]sol[ée]|pardon|malheureusement|dommage|triste|perdu|rat[ée]|[ée]chou[ée]|je regrette|h[ée]las)\b/i;
  function expressivitePhrase(base, texte) {
    if (!Number.isFinite(base)) return base;
    const t = String(texte || '');
    return base + (PHRASE_VIVE.test(t) ? 0.08 : 0) - (PHRASE_DOUCE.test(t) ? 0.06 : 0) + (/\?\s*$/.test(t) ? 0.03 : 0);
  }
  // le début connu par lequel commence ce texte (sa casse gardée), s'il est suivi d'autre chose ; sinon null
  function debutDe(texte) {
    const t = String(texte || '');
    const m = t.match(/^\s*([^,.!?]{1,30}[,.])\s+\S/u);
    if (!m) return null;
    return DEBUTS.includes(m[1].toLowerCase().replace(/\s+/g, ' ')) ? m[1] : null;
  }

  /* ---- choix des voix du système ---- */
  function choisirVoix(voix, langue, prefere) {
    const toutes = Array.from(voix || []);
    if (prefere) { const p = toutes.find(v => v.name === prefere); if (p) return p; }
    const score = (v) => (/premium/i.test(v.name) ? 4 : 0) + (/enhanced|améliorée/i.test(v.name) ? 3 : 0)
      + (/^(fr-FR|ar-SA|ar-001)$/i.test(v.lang || '') ? 1 : 0) + (v.localService === false ? -1 : 0);
    return toutes.filter(v => (v.lang || '').toLowerCase().startsWith(langue)).sort((a, b) => score(b) - score(a))[0] || null;
  }

  /* ---- lecteur (navigateur) : file d'énoncés, une voix par langue ---- */
  function creerLecteur(synth, Enonce, voixPour, vitesse) {
    const enCours = new Set();      // garder les références : sinon Chrome peut perdre onend
    const lecteur = {
      surFin: null,
      dire(phrase) {
        for (const seg of prononcable(phrase)) {
          const u = new Enonce(seg.texte);
          const v = voixPour(seg.langue);
          if (v) { u.voice = v; u.lang = v.lang; } else u.lang = seg.langue === 'ar' ? 'ar-SA' : 'fr-FR';
          u.rate = (typeof vitesse === 'function' ? vitesse() : vitesse) || 1;
          const fini = () => { enCours.delete(u); if (!enCours.size && lecteur.surFin) lecteur.surFin(); };
          u.onend = fini; u.onerror = fini;
          u.onstart = () => { if (lecteur.surSegment) lecteur.surSegment(seg.texte); };
          u.onboundary = () => { if (lecteur.surMot) lecteur.surMot(); };      // la voix du Mac : une impulsion par mot
          enCours.add(u);
          synth.speak(u);
        }
      },
      arreter() { enCours.clear(); synth.cancel(); },
      get actif() { return enCours.size > 0; },
    };
    return lecteur;
  }

  const Voix = { versArabe, segmenter, pourLaVoix, decoupeur, choisirVoix, creerLecteur, FORMULE, VOIX_SEULE, AFFECT, sansAffect, latexParle,
    definirPrononciations,
    diction, prononcable, enLettres, DEBUTS, debutDe, expressivitePhrase };
  racine.Voix = Voix;
  if (typeof module !== 'undefined' && module.exports) module.exports = Voix;
})(typeof window !== 'undefined' ? window : globalThis);
