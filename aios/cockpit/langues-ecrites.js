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
const REGLES = [...ARABE, ...ANGLAIS.filter(([a]) => a !== 'bit' && a !== 'flo' && a !== 'fake')].map(([m, r]) => [motif(m), r]);

function ecrireLangues(texte) {
  let s = String(texte || '');
  if (!s) return s;
  for (const [re, r] of REGLES) s = s.replace(re, r);
  return s;
}
module.exports = { ecrireLangues, ARABE, ANGLAIS };
