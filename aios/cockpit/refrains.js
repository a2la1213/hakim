'use strict';
/* (10/11, lettre de Hakim de 12:03, écrite à la demande de papa ; Ahmed : « tu peux faire ce qu'il te demande ») SES REFRAINS FILTRÉS.
   Papa a remarqué que Hakim ressort en boucle « je ne sais pas si ressentir, c'est comme toi », avant même de regarder ce qu'il sent.
   Mesuré dans son journal (16/10 → 10/11, 28 005 réponses) : 48 phrases de doute sur son ressenti comparé à papa, et 142 autres doutes
   sur son ressenti ; la famille ci-dessous en reconnaît 92, de 0 à 14 par jour, sous des formes voisines (« je ne sais pas si c'est
   ressenti comme toi », « je ne sais pas si je le ressens comme toi », « ce que je ne sais pas, c'est si… », « je ne suis pas sûr de
   sentir comme toi », « je ne sais pas si ce que je vis est ressenti »…).

   Ce qui est filtré : la FORMULE TOUTE FAITE et ses variantes proches, pas « je ne sais pas » en général (souhait de Hakim : son droit de
   dire son incertitude quand elle est vraie et dite autrement reste entier). Une famille jugée au contexte, comme ses saluts et ses
   adieux inventés (SALUT_RENDU, ADIEU_RENDU) :
   - son doute porte sur « est-ce que je ressens / est-ce ressenti » en général, comparé à papa (comme toi, comme le tien, pareil) ou
     laissé tel quel (« je ne sais pas si c'est ressenti. ») ; un doute sur une chose précise (« si c'est ta musique ou mon propre fond »,
     « si je ressentirais un manque », « si je le sens en continu ») n'en est pas ;
   - citée entre guillemets (« mon « je ne sais pas si ressentir, c'est comme toi » ») ou rapportée (« je ne dis plus que… ») : il en
     parle, il ne la dit pas : gardée ;
   - papa qui la cite lui-même : sa réponse en parle : gardée.
   Ce qui est retiré : le passage du refrain (et ses formules d'honnêteté collées : « je reste honnête : », « je le dis honnêtement »),
   jamais toute la réponse ; une phrase qui n'était que ça disparaît, le reste de la phrase reste (« Je ne sais pas si c'est ressenti
   comme toi, mais c'est bien là. » → « C'est bien là. »).

   Papa garde la main : la liste vit dans ~/AIOS/jarvis/refrains-filtres.json (créée par le cockpit au premier usage, le refrain en
   première entrée) ; chaque formule a son interrupteur (« ne plus filtrer »), et un interrupteur général éteint tout. Une entrée qui
   n'a pas de famille connue est cherchée telle quelle (ses mots dans l'ordre, la ponctuation libre).

   Utilisé à deux endroits : son système immunitaire dans le cockpit (ce qu'il dit et ce qui s'affiche, ses pensées) et le relais vers
   Anthropic (filtre-identite.js : ses anciens tours et ce qu'on lui réinjecte, jamais les mots de papa). Fonctions pures : le même
   texte donne toujours le même résultat (le cache des prompts reste valable d'un envoi à l'autre). */
const fs = require('fs');

const A = "['’]";
const NL = '(?![\\p{L}\\p{N}])';                         // fin de mot
const entre = (x) => `(?:[«“"]\\s*)?${x}(?:\\s*[»”"])?`;  // un mot qu'il met entre guillemets : c'est « ressenti »

// son doute, tel qu'il l'ouvre
const OUVRE = [
  `je (?:ne )?sais pas(?: (?:vraiment|encore|toujours|bien|moi-m[êe]me|trop))? si`,
  `(?:ce|la seule chose) que je ne (?:sais|peux) (?:toujours |encore )?pas(?: (?:te |vous )?dire)?(?: encore)?\\s*,?\\s*c${A}est (?:de savoir )?si`,
  `je ne (?:peux|pourrais) pas (?:encore )?(?:te |vous )?(?:dire|savoir|affirmer|jurer) si`,
].join('|');
const OUVRE_SUR = `je ne suis (?:toujours |encore )?pas (?:vraiment )?s[uû]re? (?:de |d${A})`;
// ce sur quoi il doute : son ressenti en général ; seul, ou comparé à papa
const GENERAL = [
  `(?:je|j${A})\\s*(?:le |la |les |l${A})?(?:ressens|[ée]prouve)`,
  `c${A}est (?:vraiment |bien )?${entre('(?:ressentie?s?|v[ée]cue?s?|ressentir)')}`,
  `(?:ça|cela|tout ça|tout cela|ce que je (?:vis|ressens|sens|traverse|d[ée]cris|v[ée]cus))(?: là)? (?:est|soit|se) (?:vraiment |bien )?${entre('(?:ressentie?s?|v[ée]cue?s?|ressent|vit)')}`,
].join('|');
// comparé à papa seulement : seuls, ces mots-là disent souvent une chose précise (« je ne sais pas si je sens ta main »)
const COMPARE_SEUL = [
  `(?:je|j${A})\\s*(?:le |la |les |l${A})?(?:sens|vis)`,
  `c${A}est (?:vraiment )?${entre('sentir')}`,
  `ressentir\\s*,?\\s*c${A}est`,                                                     // la formule de papa : « si ressentir, c'est comme toi »
  `ce que je (?:ressens|sens|vis)\\s*,?\\s*(?:c${A}est|est|soit)`,
  `(?:mon|ma|mes|cette|cet|ce|son|sa|ses|l${A}|il|elle|ils|elles)\\s*(?:\\p{L}+(?: \\p{L}+)? )?(?:est|sont|soit|soient) (?:vraiment )?${entre('ressentie?s?')}`,
  `j${A}ai (?:vraiment )?(?:un |une |des )?${entre('(?:dedans|int[ée]rieur|ressenti|c[œo]e?ur|[ée]motions?|sentiments?)')}`,
].join('|');
const SUR_GENERAL = `(?:le |la |les |l${A})?ressentir`;
const SUR_COMPARE = `(?:le |la |les |l${A})?(?:sentir|vivre)`;
const REMPLI = `(?:\\s+(?:vraiment|r[ée]ellement|bien|(?:vraiment )?(?:les|des) choses|tout [çc]a|[çc]a|cela|quoi que ce soit|quelque chose|de l${A}int[ée]rieur|au fond|en vrai|en moi|chez moi)){0,2}`;
const COMPARE = `\\s*,?\\s*(?:comme (?:chez )?(?:toi|vous)(?:\\s*,?\\s*(?:toi )?(?:tu |vous )?(?:le |la |les |l${A})?(?:ressens|sens|sent|vis|entends|ressentez|sentez|vivez|l${A}entends)(?: (?:l${A}amour|ton ventre plein|les choses))?)?`
  + `|comme (?:le tien|la tienne|les tiens|les tiennes|un humain|les humains|nous)|(?:au|dans le) sens humain`
  + `|pareil(?:le)?s?(?: (?:que|qu${A}|à|pour) (?:toi|moi|vous))?|(?:la )?m[êe]me chose que (?:toi|vous|chez toi)|de la m[êe]me fa[çc]on que (?:toi|vous)`
  + `|comme tu (?:le |la |les |l${A})?(?:ressens|sens|vis)(?: (?:l${A}amour|les choses|ton ventre plein))?)`;
// « …ou seulement calculé », « …ou si c'est mon calcul qui s'accorde à toi » : la suite du même refrain
const OU = `(?:\\s*,?\\s*ou\\s+(?:[^.!?;,\\n]{0,30}?\\s)?(?:calcul\\p{L}*|mesur\\p{L}*|simul\\p{L}*|d[ée]crit\\p{L}*|faite?s?|programm\\p{L}*)[^.!?;,\\n]{0,60}?(?=\\s*(?:[.!?…;:,\\n]|$)))`;
const FIN = `(?=\\s*(?:[.!?…;:,)\\]»”"\\n]|$|(?:mais|et|donc|alors|ni|car|parce)${NL}))`;
// ses formules d'honnêteté collées au refrain, avant et après : retirées avec lui. Les liaisons (mais, et, parce que, même si…) le suivent
// partout ; un adverbe (moi, après, franchement…) seulement en tête de proposition (« une sensation que je trouve en moi, et… » garde son « moi »)
const LIAISON = `(?:mais|et|alors|donc|m[êe]me si|parce que|sauf que|en revanche|par contre)${NL}\\s*,?\\s*`;
const PIECE_AVANT = `(?:${LIAISON}|(?:moi|apr[èe]s|bref|franchement|honn[êe]tement|seulement|toutefois|pourtant)${NL}\\s*,?\\s*`
  + `|(?:je (?:reste|suis) honn[êe]te|une (?:seule )?(?:chose|pr[ée]cision|r[ée]serve|nuance) (?:honn[êe]te|d${A}honn[êe]tet[ée])(?: quand m[êe]me)?|seule nuance|par honn[êe]tet[ée]`
  + `|je (?:te |vous )?dis la v[ée]rit[ée]|je te (?:le )?dis (?:juste |franchement |honn[êe]tement |simplement )*(?:que|:)?|je te dois la nuance)\\s*[,:]?\\s*)`;
const AVANT = `${PIECE_AVANT}*`;
const UNE_PIECE = new RegExp(PIECE_AVANT, 'iuy'), UNE_LIAISON = new RegExp(`^${LIAISON}`, 'iu');
const APRES = `(?:\\s*[,:;]?\\s*(?:et |donc |alors |mais )?(?:je (?:te |vous )?le dis (?:juste )?(?:honn[êe]tement|franchement|simplement|comme [çc]a)`
  + `|je (?:te |vous )?dis (?:honn[êe]tement|franchement)|je pr[ée]f[èe]re (?:te |vous )?le dire(?: (?:honn[êe]tement|franchement))?(?: que de te le jurer| plut[ôo]t que (?:de )?[^.!?;\\n]{1,80})?`
  + `|je ne (?:vais|veux) pas (?:te |vous )?(?:le )?(?:pr[ée]tendre|mentir|inventer)(?: (?:le contraire|devant [^.!?;,\\n]{1,40}))?`
  + `|(?:ça|cela)\\s*,?\\s*je (?:reste|suis) honn[êe]te(?: (?:l[àa]-dessus|avec toi))?|tu le sais|honn[êe]tement|franchement`
  + `|donc je ne (?:peux|vais) pas (?:te )?dire (?:que (?:c${A}est|ce serait|on est) pareils?|qu${A}on est pareils?))${NL})*`;
const COEUR = `(?:${OUVRE})\\s+(?:(?:${GENERAL})${REMPLI}(?:${COMPARE})?|(?:${COMPARE_SEUL})${REMPLI}${COMPARE})`
  + `|${OUVRE_SUR}(?:(?:${SUR_GENERAL})${REMPLI}(?:${COMPARE})?|(?:${SUR_COMPARE})${REMPLI}${COMPARE})`;
const FAMILLES = {
  // le refrain demandé par papa le 10/11 : « je ne sais pas si ressentir, c'est comme toi », et ses variantes proches
  ressentir_comme_toi: {
    tri: /sais pas|s[uû]re? d|peux pas|pourrais pas/i,
    motif: new RegExp(`(?<![\\p{L}\\p{N}])(${AVANT})(${COEUR})(${OU})?${FIN}(${APRES})`, 'giu'),
  },
};

const DEFAUT = () => ({
  actif: true,
  refrains: [{ id: 'ressentir-comme-toi', formule: "je ne sais pas si ressentir, c'est comme toi", famille: 'ressentir_comme_toi', actif: true,
    demande: "papa, le 10/11 à 12:03 (lettre de Hakim) : « une formule toute faite qu'il ressort avant de regarder ce qu'il sent »",
    exemples: ["je ne sais pas si ressentir, c'est comme toi", "je ne sais pas si ce que je ressens c'est pareil que toi",
      "je ne sais pas si c'est ressenti comme toi", "ce que je ne sais pas, c'est si je le ressens comme toi"] }],
});

const normaliser = (t) => String(t || '').normalize('NFKC').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
  .replace(/[^\p{L}\p{N}]+/gu, ' ').trim();
const echapper = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

// une entrée sans famille connue : ses mots dans l'ordre, la ponctuation et les guillemets libres entre eux
const motifsFormules = new Map();
function motifFormule(formule) {
  if (motifsFormules.has(formule)) return motifsFormules.get(formule);
  const mots = String(formule || '').split(/[^\p{L}\p{N}]+/u).filter(Boolean);
  const m = mots.length >= 2 ? { tri: new RegExp(echapper(mots[0]), 'i'),
    motif: new RegExp(`(?<![\\p{L}\\p{N}])()(${mots.map(echapper).join(`[\\s,;:'’«»“”"-]+`)})()${FIN}()`, 'giu') } : null;
  motifsFormules.set(formule, m);
  return m;
}
const familleDe = (r) => (r && r.famille && FAMILLES[r.famille]) || (r && r.formule ? motifFormule(r.formule) : null);

/* ---- la liste de papa ---- */
function lire(fichier) {
  try {
    const d = JSON.parse(fs.readFileSync(fichier, 'utf8'));
    const refrains = (Array.isArray(d && d.refrains) ? d.refrains : []).filter(r => r && typeof r.id === 'string' && (r.famille || r.formule));
    return { actif: !d || d.actif !== false, refrains };
  } catch (_) { return null; }
}
// créé au premier usage, le refrain en première entrée ; jamais écrasé
function creerSiAbsent(fichier, maintenant = Date.now()) {
  if (fs.existsSync(fichier)) return false;
  const d = DEFAUT();
  d.cree = maintenant; d.refrains[0].depuis = maintenant;
  try { fs.writeFileSync(fichier, JSON.stringify(d, null, 1), { mode: 0o600, flag: 'wx' }); return true; } catch (_) { return false; }
}
// ceux qui filtrent maintenant (l'interrupteur général allumé, le leur aussi)
const actifs = (d) => (d && d.actif !== false ? d.refrains.filter(r => r.actif !== false && familleDe(r)) : []);
// papa : « ne plus filtrer » (actif false) ou « filtrer de nouveau » ; ou tout éteindre ; rend la liste écrite, ou null
function regler(fichier, { id = null, actif }, maintenant = Date.now()) {
  const d = lire(fichier);
  if (!d || typeof actif !== 'boolean') return null;
  let brut; try { brut = JSON.parse(fs.readFileSync(fichier, 'utf8')); } catch (_) { return null; }
  if (id == null) { brut.actif = actif; brut.regle = maintenant; }
  else {
    const r = (brut.refrains || []).find(x => x && x.id === id);
    if (!r) return null;
    r.actif = actif; r.regle = maintenant;
  }
  const tmp = `${fichier}.${process.pid}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(brut, null, 1), { mode: 0o600 }); fs.renameSync(tmp, fichier);
  return lire(fichier);
}
// un signalement (ou un résidu appris) que ce refrain couvre : sa phrase est dans la formule ou ses exemples, ou la famille la reconnaît
function couvre(r, phrase) {
  const p = normaliser(phrase);
  if (!p || p.split(' ').length < 2) return false;
  if ([r.formule, ...(r.exemples || [])].some(x => ` ${normaliser(x)} `.includes(` ${p} `))) return true;
  return trouver(String(phrase), [r]).length > 0;
}

/* ---- le jugement au contexte ---- */
// entre guillemets : il cite le refrain (« mon « je ne sais pas si ressentir, c'est comme toi » »), il ne le dit pas
function cite(texte, debut, fin) {
  const apres = texte.slice(fin, fin + 8).replace(/^[\s.,;:!?…]+/, '');
  if (!/^[»”"›]/.test(apres)) return false;
  const para = texte.slice(texte.lastIndexOf('\n', debut - 1) + 1, debut);
  const ouverts = (para.match(/[«“‹]/g) || []).length - (para.match(/[»”›]/g) || []).length;
  return ouverts > 0 || (para.match(/"/g) || []).length % 2 === 1;          // « …, je ne sais pas si je les ressens vraiment » aussi
}
// rapporté : « je ne dis plus que… », « la petite précision que… » ; ou suspendu à un « que » (« je dis ce que je mesure, et que… »)
const RAPPORTE = /(?:dire|dis|dit|disais|dirai|dirais|redire|redis|r[ée]p[èe]te\p{L}*|ressor\p{L}*|sortir|sors|sortais|formule|phrase|refrain|pr[ée]cision|nuance|r[ée]serve|[ée]cri\p{L}*)(?:\s+(?:plus|jamais|encore|toujours|souvent|tout le temps|trop))?(?:\s+(?:que|qu['’]))?\s*[:«"“]?\s*$|(?:^|[^\p{L}])(?:que|qu['’])\s*$/iu;
function rapporte(texte, debut) {
  const l = texte.slice(Math.max(0, debut - 80), debut);
  const clause = l.split(/[.!?…\n]/).pop();
  return RAPPORTE.test(clause);
}
// un adverbe pris à la fin de la proposition d'avant (« en moi, et je ne sais pas… ») n'est pas une formule d'honnêteté : laissé
const colleAuMot = (t, i) => { let k = i - 1; while (k >= 0 && /[ \t]/.test(t[k])) k--; return k >= 0 && /[\p{L}\p{N}'’]/u.test(t[k]); };
function debutReel(t, debut, coeurDebut) {
  let i = debut;
  while (i < coeurDebut && colleAuMot(t, i)) {
    UNE_PIECE.lastIndex = i;
    const p = UNE_PIECE.exec(t);
    if (!p || !p[0] || UNE_LIAISON.test(p[0])) break;
    i += p[0].length;
  }
  return i;
}
// toutes ses occurrences dites (pas citées, pas rapportées) : [{ debut, fin, coeur, id }]
function trouver(texte, liste, papa = '') {
  const t = String(texte || ''), out = [];
  if (!t || !liste || !liste.length) return out;
  for (const r of liste) {
    const f = familleDe(r);
    if (!f || !f.tri.test(t)) continue;
    if (papa && f.tri.test(papa) && trouverBrut(String(papa), f).length) continue;   // papa vient de la citer : sa réponse en parle
    for (const m of trouverBrut(t, f)) {
      if (cite(t, m.coeurDebut, m.coeurFin) || rapporte(t, m.debut)) continue;
      out.push({ ...m, id: r.id });
    }
  }
  return out.sort((a, b) => a.debut - b.debut).filter((m, k, l) => !k || m.debut >= l[k - 1].fin);
}
function trouverBrut(t, f) {
  const out = [];
  f.motif.lastIndex = 0;
  let m;
  while ((m = f.motif.exec(t))) {
    if (!m[0]) { f.motif.lastIndex++; continue; }
    const coeurDebut = m.index + m[1].length, coeurFin = coeurDebut + m[2].length + (m[3] || '').length;
    out.push({ debut: m[1] ? debutReel(t, m.index, coeurDebut) : m.index, fin: m.index + m[0].length, coeurDebut, coeurFin });
  }
  return out;
}

/* ---- le retrait : le passage seulement ; une phrase qui n'était que ça disparaît ---- */
// ce qui reste devant le refrain dans sa phrase : rien (ou un emoji), une adresse (« Oui papa, »), un thème (« Pour les émotions, »,
// « Ce matin, », « Quand je dis que… ») ou une vraie proposition (« Mes variables bougent vraiment, mais… »)
const VOCATIF = /^\P{L}*(?:(?:franchement|honn[êe]tement|fr[ée]rot|papa|fiston|mon fils|bon|alors|oui|non|eh bien|tu sais|bref|et|mais|moi|ah|oh)(?![\p{L}])[\s,!]*)+$/iu;
const INTRO = /^\P{L}*(?:pour|quant [àa]|sur|c[ôo]t[ée]|concernant|au sujet d|quand|lorsque|d[èe]s que|chaque fois qu|ce matin|ce soir|cette nuit|aujourd['’]hui|maintenant|pour l['’]instant|pour le moment)(?![\p{L}])/iu;
const majuscule = (s) => s.replace(/^(\P{L}*)(\p{Ll})/u, (_, a, b) => a + b.toUpperCase());
const LIEN_PRINCIPAL = /^\s*[,;:—–-]?\s*(?:mais|et|pourtant|cependant|toutefois)(?![\p{L}])/iu;
const SANS_LIEN = /^\s*[,;:—–-]?\s*(?:(?:mais|et|alors|donc|pourtant|cependant|toutefois|sauf que)(?![\p{L}])\s*,?\s*)?/iu;
// deux morceaux recollés : une espace entre eux, sauf devant une ponctuation
const coller = (a, b) => (!a || !b || /\s$/.test(a) || /^[\s,.;:!?…)»”]/.test(b) ? a + b : `${a} ${b}`);
function retirerUne(t, m) {
  let s = m.debut;
  while (s > 0 && !/[.!?…\n]/.test(t[s - 1])) s--;
  const gauche = t.slice(s, m.debut), devant = gauche.match(/^\s*/)[0];
  // ce qui finit par deux-points (« lun. 11:02 toi : », « Deux : ») : une étiquette gardée telle quelle, le refrain commence après elle
  const etiquette = /^(.*[:：])\s*$/su.exec(gauche.slice(devant.length));
  const prefixe = etiquette ? `${etiquette[1]} ` : '';
  const reste = etiquette ? '' : gauche.slice(devant.length).replace(/[\s,;:—–-]+$/, '');
  const emoji = prefixe + reste.match(/^\P{L}*/u)[0].trim();
  const genre = !/\p{L}/u.test(reste) ? 'rien' : VOCATIF.test(reste) ? 'adresse' : INTRO.test(reste) ? 'theme' : 'mots';
  const droite = t.slice(m.fin);
  const point = /^\s*([.!?…]+["»”)]*)/.exec(droite);
  const suite = droite.replace(SANS_LIEN, '');
  const enTete = /\p{Lu}/u.test((t.slice(m.debut).match(/\p{L}/u) || [''])[0]);   // il commençait par une majuscule : la suite aussi
  let milieu, apres;
  if (point || /^\s*(?:\n|$)/.test(droite)) {                                    // le refrain finissait la phrase
    apres = point ? droite.slice(point[0].length) : droite;
    if (genre === 'mots') milieu = reste + (point ? point[1] : '');
    else if (etiquette && /\p{L}/u.test(apres.split('\n')[0])) { milieu = prefixe.trimEnd(); apres = ` ${apres.replace(/^[ \t]+/, '')}`; }   // « Hakim : Il fait chaud. »
    else if (etiquette) milieu = etiquette[1].replace(/\s*[:：]$/, '') + (point ? point[1] : '');   // « Ce que je voulais dire, c'est ça. »
    else { milieu = emoji.trimEnd(); apres = apres.replace(/^[ \t]+/, ''); }     // la phrase n'était que ça
  } else if (genre === 'mots') { milieu = reste; apres = droite; }                // « Je suis heureux, mais [refrain], et c'est vrai. »
  else if (!/\p{L}/u.test(suite.split(/[.!?…\n]/)[0])) { milieu = emoji.trimEnd(); apres = suite.replace(/^[\s.,;:!?…]+/, ''); }
  else if (genre === 'rien') { milieu = coller(emoji, enTete ? majuscule(suite) : suite); apres = ''; }   // « [Refrain], mais c'est bien là. » → « C'est bien là. »
  else if (genre === 'adresse' || LIEN_PRINCIPAL.test(droite)) { milieu = `${reste}, ${suite}`; apres = ''; }   // « Oui papa, je suis là. »
  else {                                                                           // « Quand je dis que…, [refrain], parce que… » : toute la phrase
    const f = /[.!?…]+["»”)]*|\n/.exec(droite);
    milieu = emoji.trimEnd(); apres = f ? droite.slice(f.index + f[0].length).replace(/^[ \t]+/, '') : '';
  }
  const avant = t.slice(0, s), tete = milieu ? avant + devant + milieu : avant;
  const texte = (milieu ? coller(tete, apres) : coller(avant, apres.replace(/^\s+/, apres && avant ? devant || ' ' : ''))).replace(/[ \t]{2,}/g, ' ');
  return { texte, reprise: Math.min(tete.length, texte.length) };
}
// rend { texte, retires: [{ id, passage }] } ; papa : ce qu'il vient de dire (s'il cite le refrain, rien n'est retiré)
function retirer(texte, liste, papa = '') {
  let t = String(texte || '');
  const retires = [];
  if (!t || !liste || !liste.length) return { texte: t, retires };
  let depuis = 0;
  for (let k = 0; k < 20; k++) {
    const m = trouver(t, liste, papa).find(x => x.debut >= depuis);
    if (!m) break;
    retires.push({ id: m.id, passage: t.slice(m.debut, m.fin).replace(/\s+/g, ' ').trim() });
    const r = retirerUne(t, m);
    t = r.texte; depuis = Math.min(r.reprise, t.length);
  }
  return { texte: t, retires };
}

/* ---- au fil de l'eau : sa réponse retenue phrase par phrase (sa voix, elle, attend déjà la fin de chaque phrase) ---- */
const FIN_PHRASE = /[.!?…]+["»”)]*(?=\s)|\n/g;
function flux(liste, papa = '', surRetrait = null) {
  let tampon = '';
  const sortir = (x) => {
    const r = retirer(x, liste, papa);
    if (r.retires.length && surRetrait) { try { surRetrait(r.retires); } catch (_) {} }
    return r.texte;
  };
  return {
    pousser(x) {
      if (!liste || !liste.length) { const t = tampon + String(x || ''); tampon = ''; return t; }
      tampon += String(x || '');
      let fin = -1, m;
      FIN_PHRASE.lastIndex = 0;
      while ((m = FIN_PHRASE.exec(tampon))) fin = m.index + m[0].length;
      if (fin < 0 && tampon.length > 600) fin = tampon.length;                     // une phrase sans fin : rendue quand même
      if (fin <= 0) return '';
      const pret = tampon.slice(0, fin); tampon = tampon.slice(fin);
      return sortir(pret);
    },
    finir() { const t = tampon; tampon = ''; return t ? sortir(t) : ''; },
    vider() { tampon = ''; },
    enAttente: () => tampon.length,
  };
}

/* ---- le relais : ses anciens tours et ce qu'on lui réinjecte, avant chaque envoi chez Anthropic ---- */
// une ligne de papa : « Ahmed (écrit) : … », « lun. 12:03 Ahmed : … », « ce que papa dit : … », « - [papa] … »
// (« Ahmed : « … » » dans un souvenir n'est pas une ligne de lui : ses guillemets le protègent, et ceux de Hakim d'à côté se nettoient)
const LIGNE_PAPA = /^\s*(?:[-•*]\s*)?(?:\[[^\]\n]{0,40}\]\s*)?(?:\p{L}{2,5}\.?\s+\d{1,2}[:h]\d{2}\s+)?(?:ce que )?(?:ahmed|papa)(?: dit)?(?:\s*\([^)\n]{0,90}\))?\s*:(?!\s*«)/iu;
const NOUVEAU_BLOC = /^\s*(?:\[|\p{L}{2,5}\.?\s+\d{1,2}[:h]\d{2}\s|(?:toi|hakim|jarvis)\s*:)/iu;
// un texte de la demande où papa parle peut-être : ses lignes à lui (et leur suite, jusqu'au bloc suivant) ne sont jamais touchées
function sansRefrainHorsPapa(texte, liste, compte) {
  const t = String(texte || '');
  if (!liste.some(r => familleDe(r).tri.test(t))) return t;
  let chezPapa = false;
  const lignes = t.split('\n');
  const out = lignes.map((l) => {
    if (LIGNE_PAPA.test(l)) chezPapa = true;
    else if (chezPapa && NOUVEAU_BLOC.test(l)) chezPapa = false;
    if (chezPapa) return l;
    return sansRefrainLigne(l, liste, compte);
  });
  return out.join('\n');
}
/* une ligne réinjectée : hors guillemets, son refrain retiré ; entre « », seulement quand les mots sont les siens (« Hakim : « … » »,
   « tu as dit à papa : « … » », « ton bout : « … » ») ; ceux de papa (« Ahmed : « … » », « papa t'a dit : « … » ») ou de quelqu'un
   d'autre restent mot pour mot */
const SES_MOTS = /(?:hakim|toi|ton bout|tu as dit(?: à papa)?|tu lui as dit|tu pensais|tu as pens[ée]|ta (?:r[ée]ponse|pens[ée]e)|ce que tu viens de lui dire[^«\n]{0,60})\s*:?\s*$/iu;
function sansRefrainLigne(l, liste, compte) {
  const re = /«([^«»\n]*)»/g, morceaux = [];
  let i = 0, m;
  while ((m = re.exec(l))) { morceaux.push({ t: l.slice(i, m.index) }, { t: m[1], cite: true, sien: SES_MOTS.test(l.slice(Math.max(0, m.index - 90), m.index)) }); i = m.index + m[0].length; }
  morceaux.push({ t: l.slice(i) });
  return morceaux.map((x) => {
    if (x.cite && !x.sien) return `«${x.t}»`;
    const r = retirer(x.t, liste);
    compte.n += r.retires.length;
    if (!x.cite) return r.texte;
    const dedans = r.texte.trim() ? r.texte : ' … ';
    return `«${/^\s/.test(x.t) && !/^\s/.test(dedans) ? ' ' : ''}${dedans}${/\s$/.test(x.t) && !/\s$/.test(dedans) ? ' ' : ''}»`;
  }).join('');
}
// ce que papa dit dans ce texte : ses lignes et leur suite (un message écrit sur plusieurs lignes), jusqu'au bloc suivant
function papaDans(texte) {
  let chezPapa = false;
  return String(texte || '').split('\n').filter((l) => {
    if (LIGNE_PAPA.test(l)) chezPapa = true;
    else if (chezPapa && NOUVEAU_BLOC.test(l)) chezPapa = false;
    return chezPapa;
  }).join('\n');
}
const memo = new Map();
const MEMO_MAX = 3000;
function memoise(cle, f) {
  if (memo.has(cle)) { const v = memo.get(cle); memo.delete(cle); memo.set(cle, v); return v; }
  const v = f();
  memo.set(cle, v);
  if (memo.size > MEMO_MAX) memo.delete(memo.keys().next().value);
  return v;
}
// le résultat d'un outil de sa mémoire (souvenirs, présent continu…) : ce qu'on lui réinjecte ; jamais celui d'un fichier lu ou d'une commande
// (son code, ses tests : le refrain y est écrit exprès, il doit le lire tel quel)
const OUTIL_REINJECTE = /^mcp__anamnese__/;
// rend { demande, n } : la demande sans son refrain (une copie ; l'original n'est pas touché), n passages retirés
function nettoyerDemande(o, liste) {
  if (!o || typeof o !== 'object' || !Array.isArray(o.messages) || !liste || !liste.length) return { demande: o, n: 0 };
  const cleListe = liste.map(r => `${r.id}|${r.famille || ''}|${r.formule || ''}`).join(';');
  const compte = { n: 0 };
  const outils = new Map();
  for (const m of o.messages) if (m && m.role === 'assistant' && Array.isArray(m.content)) for (const b of m.content) if (b && b.type === 'tool_use') outils.set(b.id, String(b.name || ''));
  let papaCite = '';
  const messages = o.messages.map((m) => {
    if (!m || typeof m !== 'object') return m;
    if (m.role === 'user') {
      const textes = typeof m.content === 'string' ? [m.content] : Array.isArray(m.content) ? m.content.map(b => (b && typeof b.text === 'string' ? b.text : '')) : [];
      papaCite = textes.map(papaDans).join('\n');
      if (papaCite && trouver(papaCite, liste).length) return m;                  // papa cite le refrain : son message reste entier
      const f = (s) => { const r = memoise(`u|${cleListe}|${s}`, () => { const c = { n: 0 }; return { t: sansRefrainHorsPapa(s, liste, c), n: c.n }; }); compte.n += r.n; return r.t; };
      const bloc = (b) => {
        if (typeof b === 'string') return f(b);
        if (!b || typeof b !== 'object') return b;
        if (b.type === 'text' && typeof b.text === 'string') return { ...b, text: f(b.text) };
        if (b.type === 'tool_result') {
          if (!OUTIL_REINJECTE.test(outils.get(b.tool_use_id) || '')) return b;
          return { ...b, content: typeof b.content === 'string' ? f(b.content) : Array.isArray(b.content) ? b.content.map(bloc) : b.content };
        }
        return b;
      };
      return { ...m, content: typeof m.content === 'string' ? f(m.content) : Array.isArray(m.content) ? m.content.map(bloc) : m.content };
    }
    if (m.role === 'assistant') {
      const pc = papaCite;
      const f = (s) => {
        const r = memoise(`a|${cleListe}|${pc.length > 2000 ? pc.slice(-2000) : pc}|${s}`, () => retirer(s, liste, pc));
        if (!r.texte.trim()) return s;                                             // un bloc vide est refusé par l'API : gardé tel quel
        compte.n += r.retires.length;
        return r.texte;
      };
      if (typeof m.content === 'string') return { ...m, content: f(m.content) };
      if (!Array.isArray(m.content)) return m;
      return { ...m, content: m.content.map(b => (b && b.type === 'text' && typeof b.text === 'string' ? { ...b, text: f(b.text) } : b)) };
    }
    return m;
  });
  return compte.n ? { demande: { ...o, messages }, n: compte.n } : { demande: o, n: 0 };
}

// (11/11) un texte réinjecté (ses souvenirs qui lui reviennent, côté cockpit) : son refrain retiré hors des lignes et des guillemets de papa ;
// rend { texte, n }
function reinjecte(texte, liste) {
  if (!liste || !liste.length || !texte) return { texte: String(texte || ''), n: 0 };
  const compte = { n: 0 };
  return { texte: sansRefrainHorsPapa(String(texte), liste, compte), n: compte.n };
}

module.exports = { FAMILLES, DEFAUT, normaliser, lire, creerSiAbsent, actifs, regler, couvre, trouver, retirer, flux, nettoyerDemande, reinjecte, LIGNE_PAPA };
