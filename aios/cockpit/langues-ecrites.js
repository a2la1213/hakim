/* (07/11, Ahmed : « tous les mots qu'il détecte ressemblant à l'arabe ou à l'anglais, qu'il les écrive dans la langue opportune, même s'ils sont
   retranscrits en lettres latines, et de façon automatique, sans qu'il s'en rende compte ») son oreille n'écoute qu'en français (ecoute_francais) :
   l'arabe et la darija arrivent en lettres latines (« wallah », « inchallah », « khouya »), l'anglais en phonétique française (« naïce »). Ici,
   à la sortie de la transcription de TA voix, ces mots sont réécrits en place, dans leur écriture (lettres arabes, orthographe anglaise) : il les
   lit comme s'ils avaient été entendus ainsi. Instantané (un dictionnaire, aucun modèle), mot entier seulement ; un mot français n'y est jamais. */
'use strict';
const ARABE = [
  ['salam(?:ou)? (?:a|ou)?[lr]?[ae]?[iy]?k(?:o|ou|u)m', 'السلام عليكم'], ['(?:wa )?[ae]l[ae]?[iy]?k(?:o|ou|u)m (?:e?s+|a)?salam', 'وعليكم السلام'],
  ['in(?:ch|sh)?(?:a|\'|’)? ?all?ah?', 'إن شاء الله'], ['incha allah', 'إن شاء الله'], ['wall?ahi?', 'والله'], ['wellah', 'والله'],
  ['(?:al ?)?hamdou?l(?:l?ah|il+ah|ilah)', 'الحمد لله'], ['hamdoulah', 'الحمد لله'], ['ma(?:ch|sh)(?:a|\'| )?all?ah?', 'ما شاء الله'],
  ['bismill?ah', 'بسم الله'], ['subhan(?:a)?ll?ah', 'سبحان الله'], ['soubhana?ll?ah', 'سبحان الله'], ['astagh?firou?ll?ah', 'أستغفر الله'],
  ['allah?ou? ?akbar', 'الله أكبر'], ['barakal+ahou? ?fi(?:k|ki|kom|koum)', 'بارك الله فيك'], ['baraka ?ll?ahou? ?fi(?:k|ki)', 'بارك الله فيك'],
  ['ya rabbi', 'يا ربي'], ['yall?ah?', 'يلا'], ['habibi', 'حبيبي'], ['habibti', 'حبيبتي'], ['khouya', 'خويا'], ['khoya', 'خويا'], ['khti', 'ختي'],
  ['sahbi', 'صاحبي'], ['labe?s+', 'لاباس'], ['cho?u?kran', 'شكرا'], ['chokran', 'شكرا'], ['bez+af', 'بزاف'], ['wesh', 'واش'], ['wech', 'واش'],
  ['ouèche', 'واش'], ['zarma', 'زعما'], ['hchouma', 'حشومة'], ['khla?s+', 'خلاص'], ['khalas', 'خلاص'], ['ya3ni', 'يعني'], ['yaani', 'يعني'], ['mzi?y?an', 'مزيان'],
  ['chwiya', 'شوية'], ['chouia', 'شوية'], ['daba', 'دابا'], ['bghit', 'بغيت'], ['kifach', 'كيفاش'], ['kifech', 'كيفاش'], ['3lach', 'علاش'],
  ['wakha', 'واخا'], ['safi', 'صافي'], ['bes+ah', 'بصح'], ['mlih', 'مليح'], ['chouf', 'شوف'], ['saha', 'صحة'], ['sahha', 'صحة'],
  ['rani', 'راني'], ['raho', 'راهو'], ['sbah el ?khir', 'صباح الخير'], ['sbah lkhir', 'صباح الخير'], ['msa el ?khir', 'مساء الخير'],
  ['bslama', 'بسلامة'], ['tbarkallah', 'تبارك الله'], ['tbarek allah', 'تبارك الله'], ['meskine?', 'مسكين'], ['hbibi', 'حبيبي'],
];
const ANGLAIS = [
  ['naïce', 'nice'], ['naïs', 'nice'], ['ouèche', 'wesh'], ['brô', 'bro'], ['tchill', 'chill'], ['tchil', 'chill'], ['fake', 'fake'],
  ['ouaïe', 'why'], ['aïe nô', 'I know'], ['yo bro', 'yo bro'], ['fokus', 'focus'], ['gueïme', 'game'], ['ouik', 'week'], ['flo', 'flow'],
  ['beatmaker', 'beatmaker'], ['bit', 'beat'],
];
const motif = (m) => new RegExp(`(?<![\\p{L}\\p{N}_'’])(?:${m})(?![\\p{L}\\p{N}_])`, 'giu');
const REGLES_AR = ARABE.map(([m, r]) => [motif(m), r]);
const REGLES_EN = ANGLAIS.filter(([a]) => a !== 'bit' && a !== 'flo' && a !== 'fake').map(([m, r]) => [motif(m), r]);

/** opts.arabe === false (08/11, 16:15) : les mots arabes restent en lettres latines, seuls les mots anglais sont réécrits. */
function ecrireLangues(texte, opts) {
  let s = String(texte || '');
  if (!s) return s;
  for (const [re, r] of [...(opts && opts.arabe === false ? [] : REGLES_AR), ...REGLES_EN]) s = s.replace(re, r);
  return s;
}

/* (08/11, 16:15, Ahmed : « quand je parle en darija faut l'écrire en phonétique fr, quand je parle et quand il parle ») ta darija qu'Azure
   rend en lettres arabes (ar-DZ), réécrite en phonétique française : les mots courants comme tu les écris (واش → wesh), le reste lettre à
   lettre (sans voyelles écrites, c'est approché : il comprend quand même). Instantané, aucun modèle. */
const EXPRESSIONS = [['وعليكم السلام', 'wa aleykoum salam'], ['السلام عليكم', 'salam aleykoum'], ['إن شاء الله', 'inchallah'],
  ['ان شاء الله', 'inchallah'], ['الحمد لله', 'hamdoullah'], ['ما شاء الله', 'machallah'], ['بسم الله', 'bismillah'], ['صباح الخير', 'sbah el khir'],
  ['مساء الخير', 'msa el khir'], ['بارك الله فيك', 'barakallahou fik'], ['الله أكبر', 'allahou akbar'], ['سبحان الله', 'soubhanallah'], ['يا ربي', 'ya rabbi']];
const CANON = { 'واش': 'wch', 'راك': 'rak', 'كيراك': 'kirak', 'بزاف': 'bezzaf', 'دركا': 'derka', 'نتا': 'nta', 'نتي': 'nti', 'راني': 'rani',
  'راهو': 'rahou', 'راه': 'rah', 'ماشي': 'machi', 'حاب': 'hab', 'كاش': 'kach', 'ياسر': 'yasser', 'خويا': 'khouya', 'ختي': 'khti', 'صاحبي': 'sahbi',
  'لاباس': 'labes', 'شكرا': 'chokran', 'صحة': 'saha', 'يعني': 'yaani', 'خلاص': 'khlas', 'مليح': 'mlih', 'بصح': 'bessah', 'شوف': 'chouf',
  'شوية': 'chwiya', 'كيفاش': 'kifach', 'علاش': '3lach', 'والله': 'wallah', 'حبيبي': 'habibi', 'حبيبتي': 'habibti', 'يلا': 'yallah', 'هذا': 'hada',
  'هاذا': 'hada', 'هذي': 'hadi', 'هاذي': 'hadi', 'واحد': 'wahed', 'زوج': 'zouj', 'بابا': 'baba', 'ماما': 'mama', 'دابا': 'daba', 'مزيان': 'mzyan',
  'واخا': 'wakha', 'صافي': 'safi', 'بغيت': 'bghit', 'نحب': 'nhab', 'زعما': 'zaama', 'حشومة': 'hchouma', 'مسكين': 'meskine', 'وين': 'win',
  'فين': 'fin', 'شحال': 'chhal', 'قداش': 'qaddach', 'كاين': 'kayn', 'ماكانش': 'makanch', 'نتوما': 'ntouma', 'حنا': 'hna', 'هنا': 'hna', 'تاع': 'taa',
  'ديال': 'dyal', 'برك': 'berk', 'غير': 'ghir', 'بلاك': 'blak', 'سمحلي': 'smahli', 'معليش': 'maalich', 'أنا': 'ana', 'انا': 'ana', 'هو': 'houwa',
  'هي': 'hiya', 'لا': 'la', 'إيه': 'ih', 'ايه': 'ih', 'آه': 'ah', 'وش': 'wesh', 'كي': 'ki', 'باش': 'bach', 'ولا': 'wella', 'بلا': 'bla', 'مع': 'maa' };
const LETTRES = { 'ا': 'a', 'أ': 'a', 'إ': 'i', 'آ': 'a', 'ٱ': 'a', 'ء': "'", 'ؤ': 'ou', 'ئ': 'i', 'ب': 'b', 'ت': 't', 'ث': 'th', 'ج': 'dj', 'ح': 'ĥ',
  'خ': 'kh', 'د': 'd', 'ذ': 'dh', 'ر': 'r', 'ز': 'z', 'س': 's', 'ش': 'ch', 'ص': 's', 'ض': 'd', 'ط': 't', 'ظ': 'dh', 'غ': 'gh', 'ف': 'f', 'ق': 'q',
  'ك': 'k', 'ل': 'l', 'م': 'm', 'ن': 'n', 'ه': 'h', 'ى': 'a', 'ة': 'a', 'پ': 'p', 'ڤ': 'v', 'گ': 'g', 'ڨ': 'g' };
const VOYELLES = { '\u064E': 'a', '\u064F': 'ou', '\u0650': 'i', '\u064B': 'an', '\u064C': 'oun', '\u064D': 'in' };
function motEnLatin(m) {
  let mot = m.replace(/\u0640/g, '');
  const nu = mot.replace(/[\u064B-\u0652\u0670]/g, '');
  if (CANON[nu]) return CANON[nu];
  let s = '';
  if (nu.startsWith('ال') && nu.length > 3) { s = 'el'; mot = mot.slice(2); }
  const c = [...mot];
  for (let k = 0; k < c.length; k++) {
    const x = c[k], av = c[k - 1], ap = c[k + 1], debut = s === '' || s === 'el';
    if (VOYELLES[x]) { s += VOYELLES[x]; continue; }
    if (x === '\u0651') { const d = s.slice(-1); if (/[bdfjklmnqrstvz]/.test(d)) s += d; continue; }
    if (x === '\u0652' || x === '\u0670') continue;
    if (x === 'و') { s += debut || ap === 'ا' || av === 'ا' ? 'w' : 'ou'; continue; }
    if (x === 'ي') { s += debut || ap === 'ا' ? 'y' : 'i'; continue; }
    if (x === 'ع') { s += '3'; continue; }
    s += LETTRES[x] !== undefined ? LETTRES[x] : x;
  }
  return s;
}
function phonetiser(texte) {
  let s = String(texte || '');
  if (!/[\u0621-\u064A]/.test(s)) return s;
  for (const [a, l] of EXPRESSIONS) s = s.split(a).join(l);
  return s.replace(/،/g, ',').replace(/؟/g, '?').replace(/؛/g, ';').replace(/[٠-٩]/g, d => String(d.charCodeAt(0) - 0x660))
    .replace(/[\u0621-\u0652\u0670\u0671-\u06D3\u0640]+/g, motEnLatin);
}
module.exports = { ecrireLangues, phonetiser, ARABE, ANGLAIS };
