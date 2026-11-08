/* Les règles tirées des erreurs de Hakim, niveau 2 (sa proposition, validée par Ahmed le 2026-10-22 à 14:09).
   Côté Anamnèse : regles_apprises.py regroupe le carnet d'erreurs par le sens et propose une règle par groupe.

   - Une proposition (~/AIOS/jarvis/regles/propositions.json, écrite par Anamnèse ou par Claude Code) : la règle (25 mots au
     plus), le groupe, la cause, ses sources (les erreurs d'origine). Ahmed l'accepte ou la refuse dans Parler, une par une
     (jeton de la page, et passkey depuis le téléphone).
   - Acceptée, elle entre en vigueur après DEUX NUITS TÉMOINS (garde-fou de Hakim : on garde une comparaison du taux de
     récidive), puis le cockpit l'écrit dans la partie « Règles apprises » de regles-de-session.md, avec ses sources et sa
     date ; « Retirer » l'en sort. 10 règles apprises actives au plus (le fichier est lu à chaque conversation).
   - Le cockpit ne touche qu'à sa partie du fichier, entre deux marques ; ce qu'Ahmed y écrit à la main reste intact. */
'use strict';
const fs = require('fs');
const path = require('path');

const ID = /^R-[0-9a-f]{6}$/;
const ACTIVES_MAX = 10;
const DEBUT = '<!-- règles apprises (cockpit) -->', FIN = '<!-- fin des règles apprises -->';

// le matin (7 h) de la troisième journée après l'acceptation : deux nuits complètes sans la règle
function enVigueurApres(ts) {
  const d = new Date(ts);
  d.setDate(d.getDate() + 2);
  d.setHours(7, 0, 0, 0);
  return d.getTime();
}

class Regles {
  constructor({ fichier, regles, evenement = () => {} }) {
    Object.assign(this, { fichier, regles, evenement });
  }

  lire() {
    try { const d = JSON.parse(fs.readFileSync(this.fichier, 'utf8')); return d && typeof d.propositions === 'object' ? d : { propositions: {} }; }
    catch (_) { return { propositions: {} }; }
  }

  ecrire(d) {
    fs.mkdirSync(path.dirname(this.fichier), { recursive: true });
    const tmp = `${this.fichier}.${process.pid}.tmp`;
    fs.writeFileSync(tmp, JSON.stringify(d, null, 1), { mode: 0o600 });
    fs.renameSync(tmp, this.fichier);
  }

  liste() {
    return Object.values(this.lire().propositions).filter(p => ID.test(String(p.id))).sort((a, b) => (a.recu || 0) - (b.recu || 0));
  }

  actives(maintenant = Date.now()) {
    return this.liste().filter(p => p.etat === 'acceptee' && p.en_vigueur_ts <= maintenant);
  }

  trancher(id, action, maintenant = Date.now()) {
    const d = this.lire();
    const p = d.propositions[id];
    if (!p || !ID.test(id)) throw new Error('règle inconnue');
    if (action === 'accepter' || action === 'refuser') {
      if (p.etat !== 'proposee') throw new Error('déjà tranchée');
      if (action === 'accepter' && this.liste().filter(x => x.etat === 'acceptee').length >= ACTIVES_MAX)
        throw new Error(`déjà ${ACTIVES_MAX} règles apprises : retires-en une avant`);
      Object.assign(p, action === 'accepter' ? { etat: 'acceptee', decide_ts: maintenant, en_vigueur_ts: enVigueurApres(maintenant) }
        : { etat: 'refusee', decide_ts: maintenant });
    } else if (action === 'retirer') {
      if (p.etat !== 'acceptee') throw new Error("elle n'est pas en vigueur");
      Object.assign(p, { etat: 'retiree', retire_ts: maintenant });
    } else throw new Error('action inconnue');
    this.ecrire(d);
    this.ecrireFichierRegles(maintenant);
    try { this.evenement(p.etat, p); } catch (_) {}
    return p;
  }

  // La partie du cockpit dans regles-de-session.md : les règles actives (après leurs deux nuits témoins), avec leurs sources.
  ecrireFichierRegles(maintenant = Date.now()) {
    let t = ''; try { t = fs.readFileSync(this.regles, 'utf8'); } catch (_) {}
    const actives = this.actives(maintenant);
    const jour = (ms) => new Date(ms).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' });
    const bloc = actives.length ? [DEBUT, '', '## Règles apprises de tes erreurs (acceptées par Ahmed, niveau 2)', '',
      ...actives.map((p, k) => `${k + 1}. ${p.regle} — sources : ${(p.sources || []).join(', ')} (acceptée le ${jour(p.decide_ts)})`), '', FIN] : [];
    const i = t.indexOf(DEBUT), f = t.indexOf(FIN);
    let neuf = i >= 0 && f > i ? (t.slice(0, i).replace(/\n+$/, '') + (bloc.length ? '\n\n' + bloc.join('\n') : '') + t.slice(f + FIN.length))
      : (bloc.length ? t.replace(/\n*$/, '\n\n') + bloc.join('\n') + '\n' : t);
    if (!neuf.endsWith('\n')) neuf += '\n';
    if (neuf !== t) { const tmp = `${this.regles}.${process.pid}.tmp`; fs.writeFileSync(tmp, neuf); fs.renameSync(tmp, this.regles); }
    return actives.length;
  }
}

module.exports = { Regles, enVigueurApres, ACTIVES_MAX, DEBUT, FIN };
