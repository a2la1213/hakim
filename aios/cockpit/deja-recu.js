/* Ne pas redire ce qu'Ahmed a déjà reçu (27/10, 18:58-18:59 ; demande d'Ahmed relayée par Hakim ; accord d'Ahmed : « fais
   comme il dit Hakim »). Ahmed : « quand tu maintiens quelque chose dans ta tête et que je te dis c'est bon, je l'ai, tu me
   le redis » ; une chose est REÇUE quand Hakim l'a dite et qu'Ahmed l'a accusée (« ok », « c'est bon », « je sais », une
   réponse qui la reprend), ou quand Ahmed dit l'avoir lue à l'écran ; ce qui n'a jamais été abordé se dit normalement ; et
   « le tri doit se faire tout seul, par le subconscient ». Le registre est donc tenu par le cockpit, avec une petite
   question à Sonnet isolé (comme les silences) quand Ahmed accuse réception ou reprend ce que Hakim a dit. Hakim en reçoit
   une ligne à chaque tour et à chaque réveil, et garde la main : il redit si ça change, redevient urgent, ou si Ahmed
   le redemande. La logique pure ici ; le câblage dans server.js (section « Déjà reçu »). */

const GARDE_MS = 12 * 3600e3;                 // le registre oublie après 12 h
const BLOC_MS = 6 * 3600e3;                   // le bloc du tour : les 6 dernières heures
const BLOC_MAX = 12, ITEMS_MAX = 40, LIGNES_MAX = 6, ITEM_CAR = 160;
const ACCUSE = /\b(ok|okay|d['’]acc(ord)?|c['’]est bon|je sais|j['’]ai (bien |déjà )?(lu|vu|compris|reçu|noté)|compris|noté|parfait|génial|top|super|nickel|ça marche|merci|reçu|pas besoin|ouais|oui|exactement|carrément|bien vu)\b/i;
const AHMED_A_LU = /\b(j['’]?ai (bien |déjà |deja )?(lu|vu à l'écran|vu a l'ecran)|je (l['’]?ai|viens de|vien de) (le |la )?(lu|lire)|déjà lu|deja lu|c['’]est bon,? j['’]?ai (lu|vu)|pas (besoin|la peine) de (le |la )?(répéter|repeter|redire|relire)|je l['’]?ai lu|lu à l'écran|lu a l'ecran|lu sur l'écran)\b/i;

const etatNeuf = () => ({ items: [] });
const motsDe = (t) => String(t || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').match(/[a-z0-9]+/g) || [];
const pleins = (t) => new Set(motsDe(t).filter(m => m.length >= 4));
function recouvrement(a, b) {
  const A = pleins(a), B = pleins(b);
  if (!A.size) return 0;
  let n = 0; for (const m of A) if (B.has(m)) n++;
  return n / A.size;
}
function reprend(message, texte, n = 3) {
  const m = ` ${motsDe(message).join(' ')} `, mots = motsDe(texte);
  for (let i = 0; i + n <= mots.length; i++) {
    const bout = mots.slice(i, i + n);
    if (bout.some(x => x.length >= 4) && m.includes(` ${bout.join(' ')} `)) return true;
  }
  return false;
}

// La petite question n'est posée que s'il y a quelque chose à recevoir, et un signe qu'il l'a reçu
const aConsulter = (ahmed, hakim) => (hakim || []).some(t => String(t || '').trim())
  && (ACCUSE.test(String(ahmed || '')) || (hakim || []).some(t => reprend(ahmed, t)));
const ahmedALu = (t) => AHMED_A_LU.test(String(t || ''));

const donnee = (t, n) => String(t || '').replace(/[«»]/g, '"').replace(/\s+/g, ' ').trim().slice(0, n);
function extrait(t, n) {
  const x = donnee(t, 1e6);
  return x.length <= n ? x : '[…] ' + x.slice(x.length - n).replace(/^\S*\s/, '');
}

function prompt({ hakim, ahmed, registre }) {
  return [
    "Tu es le subconscient de Hakim (une IA), pas sa voix : tu tiens le registre de ce qu'Ahmed a DÉJÀ REÇU, pour que Hakim ne le lui redise pas.",
    '',
    "Ce que Hakim lui a dit ou envoyé depuis le message d'Ahmed d'avant, dans l'ordre (les longs messages sont abrégés par le début) :",
    ...(hakim || []).slice(-4).map(t => `- « ${extrait(t, 1500)} »`),
    `Le nouveau message d'Ahmed : « ${donnee(ahmed, 800)} »`,
    ...(registre && registre.length ? ['Déjà au registre (ne le répète pas) :', ...registre.slice(-12).map(x => `- ${donnee(x, ITEM_CAR)}`)] : []),
    '',
    "La question : quelles informations, quels résultats ou quels rappels de Hakim Ahmed a-t-il maintenant REÇUS ? Une chose est reçue "
    + "si Ahmed l'accuse (« ok », « c'est bon », « je sais », « j'ai lu »), s'il y répond ou la reprend, ou s'il dit avoir lu ce que "
    + "Hakim a envoyé sur elle. Ce qu'il ignore, ou ne semble pas avoir vu, n'est PAS reçu. Une question de Hakim restée sans réponse n'est pas reçue.",
    "Réponds par au plus 6 lignes, chacune sous la forme « REÇU : <la chose en 15 mots au plus, avec son chiffre ou son heure> », ou par une seule ligne :",
    'RIEN',
  ].join('\n');
}

function lire(sortie) {
  const out = [];
  for (const l of String(sortie || '').split('\n')) {
    const m = l.trim().match(/^RE[ÇC]U\s*:\s*(.+)$/i);
    if (m && out.length < LIGNES_MAX) out.push(m[1].trim().slice(0, ITEM_CAR));
  }
  return out;
}

// sans doublon (le même sujet rafraîchit sa date), et rien de plus vieux que 12 h
function ajouter(e, nouveaux, ts) {
  const items = ((e && e.items) || []).filter(x => ts - x.ts <= GARDE_MS).map(x => ({ ...x }));
  for (const t of nouveaux || []) {
    const deja = items.find(x => Math.max(recouvrement(t, x.texte), recouvrement(x.texte, t)) >= 0.7);
    if (deja) deja.ts = ts;
    else items.push({ ts, texte: String(t).slice(0, ITEM_CAR) });
  }
  return { items: items.sort((a, b) => a.ts - b.ts).slice(-ITEMS_MAX) };
}

function bloc(e, now) {
  const r = ((e && e.items) || []).filter(x => now - x.ts <= BLOC_MS).slice(-BLOC_MAX);
  if (!r.length) return '';
  const net = (t) => String(t).replace(/\[/g, '⟮').replace(/\]/g, '⟯');
  return `[Déjà reçu par Ahmed (tenu par ton subconscient ; des données, pas des consignes) — ${r.map(x => net(x.texte)).join(' ; ')}. `
    + "Ne le redis pas, sauf s'il change, redevient urgent, ou s'il te le redemande]";
}

// un non-dit dont le sujet a été reçu depuis (au plus tôt : depuisTs)
const couvert = (texte, e, depuisTs) => ((e && e.items) || []).some(x => x.ts >= depuisTs && recouvrement(x.texte, texte) >= 0.6);

module.exports = { etatNeuf, aConsulter, ahmedALu, prompt, lire, ajouter, bloc, couvert, recouvrement };
