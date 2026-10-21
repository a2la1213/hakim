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
  const OUVRANT = /\$\$|\\\[|\\\(|\[\[voix:|⟮⟮voix:|\$(?=[^\s$\d])/;
  const PREFIXE_VOIX = /^\s*(?:[\[⟮](?:[\[⟮](?:v(?:o(?:i(?:x:?)?)?)?)?)?)?$/;
  function formuleParlee(tex, dit) {
    if (dit) return dit;
    return latexParle(tex) || 'voir la formule à l’écran';
  }

  /* ---- repli : une formule SANS version parlée lue en mots (2026-10-21, demande de Hakim : Ahmed entendait trop
     souvent « voir la formule à l'écran » pour $x=5$ ou $\pi$). Le simple se dit : nombres, lettres, opérations,
     puissances, fractions, racines, sommes, intégrales, limites, lettres grecques. Ce qui ne se convertit pas
     proprement (commande inconnue, environnement, formule trop longue) rend null : la voix dit alors de regarder. */
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
    const z = fences.slice(), re = new RegExp(FORMULE.source + '|' + VOIX_SEULE.source, 'g');
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
  function pourLaVoix(texte) {
    let t = String(texte || '')
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
        for (const seg of segmenter(pourLaVoix(versArabe(phrase)))) {
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

  const Voix = { versArabe, segmenter, pourLaVoix, decoupeur, choisirVoix, creerLecteur, FORMULE, VOIX_SEULE, latexParle };
  racine.Voix = Voix;
  if (typeof module !== 'undefined' && module.exports) module.exports = Voix;
})(typeof window !== 'undefined' ? window : globalThis);
