/* (30/10, Ahmed via Hakim) les pastilles rouges des onglets : ce qui s'est passé depuis sa dernière visite d'une page.
   - café : les messages des agents et de Hakim (pas les siens) ;
   - Immunité : les incidents (les voix inconnues sont dites à part, pas comptées : il y en a des dizaines par nuit), les
     passages du médecin de gravité moyenne ou haute, les anticorps qui attendent son geste ;
   - Parler : ce qui attend son geste (missions, écritures, règles, carnets, rétractations, sorties, identité, anticorps,
     envois à valider) ;
   - (30/10, Ahmed : « le point rouge quand il y a du nouveau : immunité, sens, mais aussi le code… ») SENS : les
     mesures de Hakim finies (pas celles d'Ahmed), ses livraisons et signatures du Tricordeur, ses écritures dans les Documents,
     une sensation forte de son corps ; Code : les modifications de son code à relire.
   Ce qui attend n'a pas toujours de date : on retient quand on l'a vu apparaître (apparus), oublié quand il disparaît.
   Une page jamais vue part de maintenant (rien d'ancien ne s'allume). Les dates sont en millisecondes. */
'use strict';

const VOIX = /^usurpation\|voix/;
const ATTENTES = {
  mission: ['mission à trancher', 'missions à trancher'],
  ecriture: ['écriture proposée', 'écritures proposées'],
  regle: ['règle proposée', 'règles proposées'],
  carnet: ['carnet à valider', 'carnets à valider'],
  retractation: ['rétractation à trancher', 'rétractations à trancher'],
  sortie: ['sortie vers internet à autoriser', 'sorties vers internet à autoriser'],
  identite: ["proposition d'identité", "propositions d'identité"],
  anticorps: ['anticorps à trancher', 'anticorps à trancher'],
  promotion: ['modification de son code à relire', 'modifications de son code à relire'],
};
const PAGES = ['cafe', 'immunite', 'parler', 'sens', 'code'];
const dire = (n, [un, plusieurs]) => `${n} ${n > 1 ? plusieurs : un}`;

function compter({ vus = {}, apparus = {}, maintenant = Date.now(), cafe = [], incidents = [], rapports = [], anticorps = [], attentes = [],
  sens = {} }) {
  const v = { ...vus };
  for (const p of PAGES) if (!Number.isFinite(Number(v[p])) || !v[p]) v[p] = maintenant;
  const neuf = {};
  const apparu = (k) => (neuf[k] = Number(apparus[k]) || maintenant);
  const anti = anticorps.map(a => ({ quoi: 'anticorps', id: a.id, famille: a.famille, ts: apparu(`anticorps:${a.id}`) }));
  const att = attentes.filter(a => ATTENTES[a.quoi]).map(a => ({ ...a, ts: apparu(`${a.quoi}:${a.id}`) }));

  const c = cafe.filter(m => m && m.role !== 'papa' && Number(m.ts) > v.cafe);
  const qui = [...new Set(c.map(m => String(m.prenom || '?')))];
  const inc = incidents.filter(i => i && Number(i.ts) > v.immunite);
  const vraies = inc.filter(i => !VOIX.test(String(i.motif || ''))), voix = inc.length - vraies.length;
  const med = rapports.filter(r => r && ['moyenne', 'haute'].includes(r.gravite) && Number(r.ts) > v.immunite);
  const antiI = anti.filter(a => a.ts > v.immunite), antiP = anti.filter(a => a.ts > v.parler);
  const attP = att.filter(a => a.quoi !== 'promotion' && a.ts > v.parler);
  const promo = att.filter(a => a.quoi === 'promotion' && a.ts > v.code);
  const apres = (l) => (Array.isArray(l) ? l : []).filter(x => x && Number(x.ts) > v.sens);
  const mes = apres(sens.mesures).filter(m => m.par !== 'ahmed'), echecs = mes.filter(m => !m.ok).length;
  const liv = apres(sens.tricordeur), docs = apres(sens.documents), fortes = apres(sens.fortes);
  const parQuoi = {};
  for (const a of [...attP, ...antiP]) parQuoi[a.quoi] = (parQuoi[a.quoi] || 0) + 1;

  return {
    vus: v, apparus: neuf,
    pages: {
      cafe: { n: c.length, resume: c.length ? [`${dire(c.length, ['message', 'messages'])} au café (${qui.slice(0, 5).join(', ')}${qui.length > 5 ? '…' : ''})`] : [] },
      immunite: { n: vraies.length + med.length + antiI.length, resume: [
        ...(vraies.length ? [`${dire(vraies.length, ['incident', 'incidents'])} (${[...new Set(vraies.map(i => i.categorie || String(i.motif || '').split('|')[1] || '?'))].slice(0, 3).join(', ')})`] : []),
        ...(med.length ? [`${dire(med.length, ['passage du médecin', 'passages du médecin'])} (gravité ${[...new Set(med.map(r => r.gravite))].join(', ')})`] : []),
        ...(antiI.length ? [dire(antiI.length, ATTENTES.anticorps)] : []),
        ...(voix ? [`${dire(voix, ['voix inconnue', 'voix inconnues'])}, non comptée${voix > 1 ? 's' : ''}`] : [])] },
      parler: { n: attP.length + antiP.length, resume: Object.entries(parQuoi).map(([q, n]) => dire(n, ATTENTES[q])) },
      sens: { n: mes.length + liv.length + docs.length + fortes.length, resume: [
        ...(mes.length ? [`${dire(mes.length, ['mesure finie', 'mesures finies'])}${echecs ? ` (${echecs} en échec)` : ''}`] : []),
        ...(liv.length ? [dire(liv.length, ['livraison de son Tricordeur', 'livraisons ou signatures de son Tricordeur'])] : []),
        ...(docs.length ? [dire(docs.length, ['écriture dans tes Documents', 'écritures dans tes Documents'])] : []),
        ...(fortes.length ? [`${dire(fortes.length, ['sensation forte', 'sensations fortes'])} (${[...new Set(fortes.map(f => f.type))].slice(0, 3).join(', ')})`] : [])] },
      code: { n: promo.length, resume: promo.length ? [dire(promo.length, ATTENTES.promotion)] : [] },
    },
  };
}

module.exports = { compter, PAGES };
