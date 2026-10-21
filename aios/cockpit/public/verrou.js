/* Le verrou d'empreinte de Hakim sur le téléphone (lot A, point 16 de la liste du 2026-10-19).
   Autonome (pas de nav.js : ses appels seraient refusés tant que c'est verrouillé). WebAuthn : la clé privée
   reste dans le téléphone ; l'empreinte (ou le visage) est exigée à chaque déverrouillage. */
'use strict';
const $ = (id) => document.getElementById(id);
const jeton = () => (document.querySelector('meta[name="cockpit-jeton"]') || {}).content || '';
const b64u = (buf) => btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
const deb64u = (s) => Uint8Array.from(atob(s.replace(/-/g, '+').replace(/_/g, '/') + '==='.slice((s.length + 3) % 4)), (c) => c.charCodeAt(0));

function dire(texte, erreur = false) { const m = $('message'); m.textContent = texte; m.classList.toggle('erreur', erreur); }

async function poster(route, corps) {
  const r = await fetch(route, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() }, body: JSON.stringify(corps || {}) });
  let o = {}; try { o = await r.json(); } catch (_) {}
  if (!r.ok) throw new Error(o.erreur || (r.status === 403 ? 'le cockpit a redémarré : recharge la page' : `erreur ${r.status}`));
  return o;
}

function nomDuTelephone() {
  const ua = navigator.userAgent || '';
  const m = ua.match(/Android [\d.]+; ([^;)]+)/);
  return (m ? m[1].trim() : 'téléphone').slice(0, 40);
}

function retour() {
  // (audit 2026-10-20, B4) : « //autre-site » ou « /\\autre-site » feraient sortir vers un autre site : jamais
  const chemin = location.pathname === '/verrou' || !/^\/(?![\/\\])/.test(location.pathname) ? '/parler' : location.pathname + location.search;
  location.replace(new URL(chemin, location.origin).origin === location.origin ? chemin : '/parler');
}

async function deverrouiller(auto = false) {
  $('deverrouiller').disabled = true; dire('…');
  try {
    const o = await poster('/api/verrou/options');
    const cred = await navigator.credentials.get({ publicKey: {
      challenge: deb64u(o.challenge), rpId: o.rpId, userVerification: 'required', timeout: o.timeout,
      allowCredentials: o.allowCredentials.map((c) => ({ type: 'public-key', id: deb64u(c.id) })) } });
    await poster('/api/verrou/deverrouiller', { reponse: {
      id: b64u(cred.rawId), clientDataJSON: b64u(cred.response.clientDataJSON),
      authenticatorData: b64u(cred.response.authenticatorData), signature: b64u(cred.response.signature) } });
    dire('Ouvert.'); retour();
  } catch (e) {
    if (auto && e.name === 'NotAllowedError') dire('');            // le navigateur veut un geste : le bouton
    else dire(e.name === 'NotAllowedError' ? 'Annulé ou empreinte non reconnue. Réessaie.' : e.message, true);
  } finally { $('deverrouiller').disabled = false; }
}

async function associer() {
  const code = $('code').value.replace(/\D/g, '');
  if (code.length !== 6) return dire('Le code a 6 chiffres.', true);
  $('associer').disabled = true; dire('…');
  try {
    const o = await poster('/api/verrou/options-association', { code });
    const cred = await navigator.credentials.create({ publicKey: {
      challenge: deb64u(o.challenge), rp: o.rp, timeout: o.timeout, attestation: o.attestation,
      user: { id: deb64u(o.user.id), name: o.user.name, displayName: o.user.displayName },
      pubKeyCredParams: o.pubKeyCredParams, authenticatorSelection: o.authenticatorSelection,
      excludeCredentials: o.excludeCredentials.map((c) => ({ type: 'public-key', id: deb64u(c.id) })) } });
    await poster('/api/verrou/associer', { nom: nomDuTelephone(), reponse: {
      clientDataJSON: b64u(cred.response.clientDataJSON), attestationObject: b64u(cred.response.attestationObject) } });
    dire('Téléphone associé. Hakim demandera ton empreinte tous les 2 jours.'); setTimeout(retour, 1200);
  } catch (e) {
    dire(e.name === 'InvalidStateError' ? 'Ce téléphone est déjà associé.'
      : e.name === 'NotAllowedError' ? 'Annulé ou empreinte non reconnue. Réessaie avec un nouveau code.' : e.message, true);
  } finally { $('associer').disabled = false; }
}

async function demarrer() {
  if (!window.PublicKeyCredential) { dire('Ce navigateur ne connaît pas les passkeys (prends Chrome ou Samsung Internet à jour).', true); return; }
  let st = {};
  try { st = await (await fetch('/api/verrou', { cache: 'no-store' })).json(); } catch (_) { return dire('Cockpit injoignable.', true); }
  if (!st.distant) {
    $('titre').textContent = 'Verrou du téléphone';
    $('explication').textContent = "Cette page s'ouvre sur le téléphone. Sur le Mac, le code se tire dans Parler → réglages.";
    return;
  }
  if (st.illisible) {                                  // (C-M1) fermé, et aucune clé ne peut l'ouvrir : on réassocie
    $('titre').textContent = 'Verrou à réparer';
    $('explication').textContent = 'Le fichier du verrou est illisible : l’accès à distance est fermé. Tire un code sur le Mac (Parler → réglages) et réassocie ce téléphone.';
    $('blocAssocier').hidden = false;
    return;
  }
  if (st.actif && st.deverrouille && location.pathname !== '/verrou') return retour();
  if (st.actif && st.deverrouille) {
    $('titre').textContent = 'Hakim est ouvert sur ce téléphone';
    $('explication').innerHTML = '<a href="/parler">Retour à Hakim</a>';
    $('basculer').hidden = false;
  } else if (st.actif) {
    $('blocDeverrouiller').hidden = false; $('basculer').hidden = false;
    deverrouiller(true);                               // la demande d'empreinte s'ouvre d'elle-même (sinon : le bouton)
  }
  else {
    $('titre').textContent = 'Protéger Hakim sur ce téléphone';
    $('explication').textContent = 'Associe ton empreinte : ensuite, Hakim ne s’ouvrira ici qu’avec elle.';
    $('blocAssocier').hidden = false;
  }
}

$('deverrouiller').addEventListener('click', () => deverrouiller(false));
$('associer').addEventListener('click', associer);
$('code').addEventListener('keydown', (e) => { if (e.key === 'Enter') associer(); });
$('basculer').addEventListener('click', () => { $('blocAssocier').hidden = false; $('basculer').hidden = true; $('code').focus(); });
demarrer();
