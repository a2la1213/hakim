/* La page « Le code de Hakim » (28/10 ; plan anamnese/docs/superpowers/plans/2026-10-28-hakim-code-avec-maman.md, tâche 7).
   FERMÉE : Hakim ne peut pas la changer. Elle lit l'état (/api/code/etat, sous jeton) et ne fait rien sans le geste
   strict : l'appli du téléphone signe un défi qui porte le texte du geste, fabriqué par le serveur. */
'use strict';
const $ = (id) => document.getElementById(id);
const jeton = () => (document.querySelector('meta[name="cockpit-jeton"]') || {}).content || '';
let etat = null;

function dire(t, erreur = false) {
  const m = $('message');
  m.hidden = !t; m.textContent = t || '';
  m.style.color = erreur ? '#f0a090' : '';
}

async function sha12(texte) {
  const b = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(texte));
  return [...new Uint8Array(b)].map(x => x.toString(16).padStart(2, '0')).join('').slice(0, 12);
}

// l'empreinte de l'appli : la page ne choisit que l'action ; le texte affiché vient du défi du serveur
function signerParAppli(defi, action) {
  return new Promise((ok, ko) => {
    window.__presenceApp = (r) => {
      window.__presenceApp = null;
      if (r && r.signature) ok({ app: r.app, defi, signature: r.signature });
      else ko(new Error((r && r.erreur) || 'empreinte annulée : rien n’a été fait'));
    };
    try { window.HakimApp.presence(defi, action); } catch (e) { window.__presenceApp = null; ko(e); }
  });
}

async function geste(corps, action, details = {}) {
  if (!window.HakimApp || !window.HakimApp.presence) { dire('Ce geste se fait dans l’appli Hakim de ton téléphone.', true); return; }
  try {
    const r = await fetch('/api/presence/options', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() },
      body: JSON.stringify({ action, ...details }) });
    const o = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(o.erreur || `erreur ${r.status}`);
    dire('Pose ton doigt : l’appli t’affiche ce que tu valides.');
    const presence = await signerParAppli(o.challenge, action);
    const g = await fetch('/api/code/geste', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() },
      body: JSON.stringify({ ...corps, presence }) });
    const res = await g.json().catch(() => ({}));
    if (!g.ok) throw new Error(res.erreur || `erreur ${g.status}`);
    dire('C’est fait.');
  } catch (e) { dire(e.message, true); }
  await charger();
}

function el(tag, attrs = {}, ...enfants) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) if (v !== undefined) e[k] = v;
  for (const c of enfants) if (c !== null && c !== undefined) e.append(c);
  return e;
}

function rendre() {
  $('etatInter').textContent = etat.actif
    ? 'Allumé : une modification avec l’avis favorable de maman peut être appliquée par ton geste.'
    : 'Éteint : rien ne peut être appliqué, même avec ton geste.';
  $('btnInter').textContent = etat.actif ? 'Éteindre' : 'Allumer';
  $('btnInter').onclick = () => geste({ quoi: 'interrupteur', actif: !etat.actif }, `code:interrupteur:${etat.actif ? 0 : 1}`);

  const promos = $('promos'); promos.textContent = '';
  if (!etat.promotions.length) promos.append(el('p', { className: 'note', textContent: 'Aucune pour l’instant.' }));
  for (const p of etat.promotions) {
    const sha = String(p.sha || '').slice(0, 12);
    const avis = p.avis ? el('span', { className: `etiquette ${p.avis.verdict === 'favorable' ? 'ok' : 'non'}`, textContent: `maman : ${p.avis.verdict}` })
      : el('span', { className: 'etiquette attente', textContent: 'avis de maman attendu' });
    const carte = el('div', { className: 'carte glass' },
      el('div', { className: 'ligne' }, el('strong', { textContent: p.id }), el('span', { className: 'etiquette', textContent: p.statut }), avis,
        el('span', { className: `etiquette ${p.tests_ok ? 'ok' : 'non'}`, textContent: p.tests_ok ? 'tests réussis' : 'tests en échec' })),
      el('p', { className: 'note', textContent: 'Écrit par Hakim :' }), el('p', { className: 'texte', textContent: p.resume || '' }),
      el('p', { className: 'fichier', textContent: (p.fichiers || []).join(', ') }),
      p.externe && p.externe.length ? el('p', { className: 'externe', textContent: `⚠ Un contenu externe a été lu pendant ce chantier : ${p.externe.join(', ')}` }) : null,
      p.avis ? el('details', {}, el('summary', { textContent: 'l’avis de maman' }), el('p', { className: 'texte', textContent: p.avis.texte || '' })) : null,
      // (relecture finale, C1) le diff lui-même, ce qui sera appliqué : pas seulement le résumé de Hakim et l'avis
      p.patch ? el('details', {}, el('summary', { textContent: 'le diff (ce qui sera appliqué)' }), el('pre', { className: 'texte', textContent: p.patch })) : null);
    const boutons = el('div', { className: 'ligne' });
    if (p.statut === 'proposée') {
      boutons.append(el('button', { type: 'button', className: 'fort', textContent: 'Appliquer', disabled: !(etat.actif && p.avis && p.avis.verdict === 'favorable' && p.tests_ok),
        onclick: () => geste({ quoi: 'appliquer', id: p.id }, `code:appliquer:${sha}`) }));
      boutons.append(el('button', { type: 'button', className: 'danger', textContent: 'Refuser', onclick: () => geste({ quoi: 'refuser', id: p.id }, `code:refuser:${sha}`) }));
    } else if (p.statut === 'appliquée') {
      boutons.append(el('button', { type: 'button', className: 'danger', textContent: 'Annuler', onclick: () => geste({ quoi: 'annuler', id: p.id }, `code:annuler:${sha}`) }));
    }
    carte.append(boutons);
    promos.append(carte);
  }

  const rel = $('relances'); rel.textContent = '';
  // (30/10, 16:20, Ahmed : « un bouton pour relancer le cockpit quand je veux ») toujours là ; il attend que ses agents et tâches
  // aient fini (sa garde du 29/10), pas le tour de Hakim
  rel.append(el('div', { className: 'carte glass' },
    el('p', { className: 'texte', textContent: 'Relancer toi-même, quand tu veux : la relance attend qu’aucun agent ni tâche ne travaille (au plus 10 min), et Hakim est prévenu.' }),
    el('div', { className: 'ligne' },
      el('button', { type: 'button', className: 'fort', textContent: 'Relancer le cockpit', onclick: () => geste({ quoi: 'relance_ahmed', cible: 'cockpit' }, 'code:relancer-moi:cockpit') }),
      el('button', { type: 'button', textContent: 'Relancer le démon', onclick: () => geste({ quoi: 'relance_ahmed', cible: 'demon' }, 'code:relancer-moi:demon') }))));
  if (!(etat.relances || []).length) rel.append(el('p', { className: 'note', textContent: 'Aucune relance proposée par Hakim.' }));
  for (const r of etat.relances || []) {
    const quoi = r.quoi === 'demon' ? 'le démon (sa mémoire)' : 'le cockpit';
    const ligne = el('div', { className: 'carte glass' },
      el('div', { className: 'ligne' }, el('strong', { textContent: `Relancer ${quoi}` }), el('span', { className: 'etiquette', textContent: r.etat })),
      el('p', { className: 'texte', textContent: `Écrit par Hakim : ${r.raison || ''}` }));
    if (r.etat === 'proposée') {
      const id12 = async () => [...new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(String(r.id))))]
        .map(x => x.toString(16).padStart(2, '0')).join('').slice(0, 12);
      ligne.append(el('div', { className: 'ligne' },
        el('button', { type: 'button', className: 'fort', textContent: 'Accepter', onclick: async () => geste({ quoi: 'relance', id: r.id, accepter: true }, `code:relancer:${await id12()}`) }),
        el('button', { type: 'button', className: 'danger', textContent: 'Refuser', onclick: async () => geste({ quoi: 'relance', id: r.id, accepter: false }, `code:refuser-relance:${await id12()}`) })));
    }
    rel.append(ligne);
  }

  const liste = $('liste'); liste.textContent = '';
  for (const g of (etat.liste && etat.liste.groupes) || []) {
    liste.append(el('h3', { className: 'sous', textContent: g.titre }));
    for (const f of g.fichiers || []) {
      const vers = f.etat === 'ouvert' ? 'ferme' : 'ouvert';
      const b = el('button', { type: 'button', className: f.etat === 'ouvert' ? 'fort' : '', textContent: f.etat === 'ouvert' ? 'Ouvert' : 'Fermé',
        disabled: vers === 'ouvert' && !(f.chemins || []).length, title: vers === 'ouvert' ? 'Ouvrir ce fichier à Hakim' : 'Le fermer',
        onclick: async () => geste({ quoi: 'liste', nom: f.nom, etat: vers }, 'code:liste:' + await sha12(`${f.nom}|${vers}`), { nom: f.nom, etat: vers }) });
      liste.append(el('div', { className: 'liste-ligne' }, el('span', { className: 'fichier', textContent: f.nom }), b,
        el('span', { className: 'raison', textContent: f.raison || '' })));
    }
  }
}

async function charger() {
  try {
    const r = await fetch('/api/code/etat', { headers: { 'X-Jeton': jeton() }, cache: 'no-store' });
    if (!r.ok) throw new Error(`erreur ${r.status}`);
    etat = await r.json();
    rendre();
  } catch (e) { dire(`Impossible de lire l’état : ${e.message}`, true); }
}
charger();
setInterval(charger, 30000);
