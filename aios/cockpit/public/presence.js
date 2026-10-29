/* La preuve de présence (audit du cockpit, C-H1) pour les pages autres que Parler : une empreinte FRAÎCHE pour un geste
   sensible, liée à ce geste. Sur le téléphone : sa passkey, ou l'appli Hakim qui signe le défi ; sur le Mac : Touch ID
   s'il est activé (sinon rien n'est demandé). La même chose que dans parler.js (29/10, la page Immunité). */
(() => {
  const deb64uOctets = (s) => Uint8Array.from(atob(s.replace(/-/g, '+').replace(/_/g, '/') + '==='.slice((s.length + 3) % 4)), (c) => c.charCodeAt(0));
  const b64uOctets = (buf) => btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  function parAppli(defi, action) {
    return new Promise((ok, ko) => {
      window.__presenceApp = (r) => {
        window.__presenceApp = null;
        if (r && r.signature) ok({ app: r.app, defi, signature: r.signature });
        else ko(new Error((r && r.erreur) || 'empreinte annulée ou non reconnue : rien n’a été fait'));
      };
      try { window.HakimApp.presence(defi, action); } catch (e) { window.__presenceApp = null; ko(e); }
    });
  }
  window.preuvePresence = async function (action, informer) {
    const r = await fetch('/api/presence/options', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jeton() },
      body: JSON.stringify({ action }) });
    const o = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(o.erreur || `erreur ${r.status}`);
    if (o.aucune) return undefined;
    if (informer) informer('pose ton doigt : ce geste demande ton empreinte');
    if (window.HakimApp && window.HakimApp.presence) return parAppli(o.challenge, action);
    let cred;
    try {
      cred = await navigator.credentials.get({ publicKey: { challenge: deb64uOctets(o.challenge), rpId: o.rpId, userVerification: 'required',
        timeout: o.timeout, allowCredentials: o.allowCredentials.map((c) => ({ type: 'public-key', id: deb64uOctets(c.id) })) } });
    } catch (e) { throw new Error(e.name === 'NotAllowedError' ? 'empreinte annulée ou non reconnue : rien n’a été fait' : e.message); }
    return { id: b64uOctets(cred.rawId), clientDataJSON: b64uOctets(cred.response.clientDataJSON),
      authenticatorData: b64uOctets(cred.response.authenticatorData), signature: b64uOctets(cred.response.signature) };
  };
})();
