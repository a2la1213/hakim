/* Le verrou d'empreinte du téléphone (lot A, point 16 de la liste du 2026-10-19 : « PRIORITÉ ») — WebAuthn
   (passkey) sans bibliothèque : la clé privée reste dans le téléphone d'Ahmed (empreinte ou visage pour s'en
   servir) ; le cockpit ne garde que la clé publique et vérifie les signatures.
   - Association : un code à 6 chiffres affiché SUR LE MAC (preuve qu'on est devant), valable 10 min, puis
     navigator.credentials.create() sur le téléphone ; on garde l'identifiant et la clé publique (COSE → JWK).
   - Déverrouillage : navigator.credentials.get() avec un défi du cockpit ; on vérifie le défi, l'origine, le
     domaine (rpIdHash), la présence ET la vérification de l'utilisateur (empreinte : drapeau UV), le compteur,
     puis la signature (ES256 ou RS256). Une session de 48 h suit (choix d'Ahmed, réglable par JARVIS_VERROU_DUREE_H) (cookie HttpOnly, Secure, SameSite=Lax ; tout POST
   exige en plus le jeton de la page). */
'use strict';
const crypto = require('crypto');

const b64u = (b) => Buffer.from(b).toString('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
const deb64u = (s) => Buffer.from(String(s).replace(/-/g, '+').replace(/_/g, '/'), 'base64');

// CBOR minimal (ce que WebAuthn utilise : entiers, octets, textes, tableaux, tables, booléens). Relecture Opus du
// 2026-10-20 : une longueur ANNONCÉE de milliards d'éléments faisait boucler/allouer jusqu'à la mort du cockpit
// (« heap out of memory ») → chaque longueur est bornée par ce qui reste vraiment dans le tampon, et la
// profondeur par 8.
function cbor(buf, i = 0, profondeur = 0) {
  if (profondeur > 8) throw new Error('CBOR : trop imbriqué');
  if (i >= buf.length) throw new Error('CBOR : tronqué');
  const tete = buf[i]; const type = tete >> 5; let info = tete & 31; i += 1;
  let n;
  if (info < 24) n = info;
  else if (info === 24) { n = buf[i]; i += 1; }
  else if (info === 25) { n = buf.readUInt16BE(i); i += 2; }
  else if (info === 26) { n = buf.readUInt32BE(i); i += 4; }
  else if (info === 27) { n = Number(buf.readBigUInt64BE(i)); i += 8; }
  else throw new Error('CBOR : longueur indéfinie non prise en charge');
  if (i > buf.length) throw new Error('CBOR : tronqué');
  const reste = buf.length - i;                              // chaque élément tient au moins un octet
  if ((type === 2 || type === 3) && n > reste) throw new Error('CBOR : longueur impossible');
  if ((type === 4 && n > reste) || (type === 5 && 2 * n > reste)) throw new Error('CBOR : longueur impossible');
  if (type === 0) return [n, i];
  if (type === 1) return [-1 - n, i];
  if (type === 2) return [buf.subarray(i, i + n), i + n];
  if (type === 3) return [buf.subarray(i, i + n).toString('utf8'), i + n];
  if (type === 4) { const a = []; for (let k = 0; k < n; k++) { const [v, j] = cbor(buf, i, profondeur + 1); a.push(v); i = j; } return [a, i]; }
  if (type === 5) { const m = new Map(); for (let k = 0; k < n; k++) { const [c, j] = cbor(buf, i, profondeur + 1); const [v, j2] = cbor(buf, j, profondeur + 1); m.set(c, v); i = j2; } return [m, i]; }
  if (type === 7) return [info === 21 ? true : info === 20 ? false : null, i];
  throw new Error(`CBOR : type ${type} non pris en charge`);
}

function lireAuthData(ad) {
  if (!Buffer.isBuffer(ad) || ad.length < 37) throw new Error('données de l’authentificateur trop courtes');
  const rpIdHash = ad.subarray(0, 32), flags = ad[32], compteur = ad.readUInt32BE(33);
  const out = { rpIdHash, flags, compteur, up: !!(flags & 1), uv: !!(flags & 4) };
  if (flags & 64) {                                        // données d'identifiant attesté (à l'association)
    if (ad.length < 55) throw new Error('données de l’authentificateur trop courtes');
    const l = ad.readUInt16BE(53);
    if (55 + l > ad.length) throw new Error('identifiant de clé tronqué');
    out.credId = ad.subarray(55, 55 + l);
    out.cose = cbor(ad, 55 + l)[0];
  }
  return out;
}

function coseVersJwk(cose) {
  const kty = cose.get(1), alg = cose.get(3);
  if (kty === 2 && alg === -7) return { alg, jwk: { kty: 'EC', crv: 'P-256', x: b64u(cose.get(-2)), y: b64u(cose.get(-3)) } };
  if (kty === 3 && alg === -257) return { alg, jwk: { kty: 'RSA', n: b64u(cose.get(-1)), e: b64u(cose.get(-2)) } };
  throw new Error(`clé non prise en charge (kty ${kty}, alg ${alg})`);
}

const defiDe = (clientDataJSON) => String(JSON.parse(deb64u(clientDataJSON).toString('utf8')).challenge || '');

function verifierClient(clientDataJSON, type, defi, origine) {
  const c = JSON.parse(Buffer.from(clientDataJSON).toString('utf8'));
  if (c.type !== type) throw new Error(`type ${c.type} inattendu`);
  if (!defi || c.challenge !== defi) throw new Error('défi inconnu ou périmé');
  if (c.origin !== origine) throw new Error(`origine ${c.origin} refusée`);
  if (c.crossOrigin) throw new Error('appel depuis une autre origine refusé');
  return c;
}

// Association : rend { id, jwk, alg, compteur } à garder
function verifierAssociation({ clientDataJSON, attestationObject }, { defi, origine, rpId }) {
  verifierClient(deb64u(clientDataJSON), 'webauthn.create', defi, origine);
  const att = cbor(deb64u(attestationObject))[0];
  if (!(att instanceof Map) || !Buffer.isBuffer(att.get('authData'))) throw new Error('réponse d’association illisible');
  const ad = lireAuthData(att.get('authData'));
  if (!ad.rpIdHash.equals(crypto.createHash('sha256').update(rpId).digest())) throw new Error('domaine (rpId) refusé');
  if (!ad.up || !ad.uv) throw new Error("l'empreinte (vérification de l'utilisateur) est exigée");
  if (!ad.credId || !(ad.cose instanceof Map)) throw new Error('pas de clé dans la réponse');
  const { alg, jwk } = coseVersJwk(ad.cose);
  crypto.createPublicKey({ key: jwk, format: 'jwk' });           // une clé mal formée est refusée dès maintenant
  return { id: b64u(ad.credId), jwk, alg, compteur: ad.compteur };
}

// Déverrouillage : rend le nouveau compteur ; lève une erreur au moindre écart
function verifierDeverrouillage({ id, clientDataJSON, authenticatorData, signature }, cle, { defi, origine, rpId }) {
  if (!cle || cle.id !== id) throw new Error('clé inconnue');
  const cd = deb64u(clientDataJSON), ad = deb64u(authenticatorData);
  verifierClient(cd, 'webauthn.get', defi, origine);
  const a = lireAuthData(ad);
  if (!a.rpIdHash.equals(crypto.createHash('sha256').update(rpId).digest())) throw new Error('domaine (rpId) refusé');
  if (!a.up || !a.uv) throw new Error("l'empreinte (vérification de l'utilisateur) est exigée");
  const avant = cle.compteur || 0;                               // 0 des deux côtés : passkey synchronisée (Google)
  if ((a.compteur !== 0 || avant !== 0) && a.compteur <= avant) throw new Error('compteur en arrière : clé clonée ?');
  const donnees = Buffer.concat([ad, crypto.createHash('sha256').update(cd).digest()]);
  const pub = crypto.createPublicKey({ key: cle.jwk, format: 'jwk' });
  const ok = cle.alg === -7 ? crypto.verify('sha256', donnees, { key: pub, dsaEncoding: 'der' }, deb64u(signature))
    : crypto.verify('sha256', donnees, { key: pub, padding: crypto.constants.RSA_PKCS1_PADDING }, deb64u(signature));
  if (!ok) throw new Error('signature fausse');
  return a.compteur;
}

/* ---- Le verrou lui-même : clés associées, code du Mac, défis à usage unique, sessions ----
   Tout est gardé dans un fichier 0600 (les sessions par leur empreinte SHA-256 seulement) : un redémarrage
   du cockpit ne reverrouille pas le téléphone. */
const fs = require('fs');
const path = require('path');

const DUREE_SESSION = (Number(process.env.JARVIS_VERROU_DUREE_H) || 48) * 3600e3;     // 2 jours (Ahmed, 2026-10-20)
const DUREE_CODE = 10 * 60e3, ESSAIS_CODE = 5;
const DUREE_DEFI = 2 * 60e3;
const ECHECS_MAX = 10, FENETRE_ECHECS = 15 * 60e3;               // au-delà : plus aucun essai pendant 15 min
const empreinte = (s) => crypto.createHash('sha256').update(String(s)).digest('hex');

// (audit du cockpit, C-H1 + C-M1, 2026-10-20) Deux sortes de clés : celles du téléphone (rpId = l'adresse Tailscale)
// et le Touch ID du Mac (rpId « localhost »). Les actions sensibles exigent une PREUVE DE PRÉSENCE fraîche : une
// signature d'empreinte sur un défi lié à CETTE action (à usage unique, 2 min). Un fichier présent mais illisible
// ferme le verrou (aucune clé ne peut l'ouvrir) au lieu de l'ouvrir : on le répare en réassociant depuis le Mac.
const MAC = 'localhost';
const estMac = (k) => k && k.rpId === MAC;

class Verrou {
  constructor(fichier, { maintenant = Date.now } = {}) {
    this.fichier = fichier; this.maintenant = maintenant;
    this.defis = new Map(); this.code = null; this.echecs = [];
    this.d = { cles: [], sessions: {} };
    this.illisible = false;
    let brut = null;
    try { brut = fs.readFileSync(fichier, 'utf8'); } catch (e) { if (e.code !== 'ENOENT') this.illisible = true; }
    if (brut !== null) {
      try {
        const d = JSON.parse(brut);
        if (d && Array.isArray(d.cles)) this.d = { cles: d.cles, sessions: d.sessions && typeof d.sessions === 'object' ? d.sessions : {} };
        else this.illisible = true;
      } catch (_) { this.illisible = true; }
    }
  }

  clesPour(rpId) { return this.d.cles.filter(k => (rpId === MAC ? estMac(k) : !estMac(k))); }
  // (2026-10-21) les seules passkeys (WebAuthn) : les clés des applis Android (téléphone, montre) n'en sont pas — mises
  // dans allowCredentials, elles faisaient échouer l'empreinte du navigateur pour les gestes sensibles
  passkeysPour(rpId) { return this.clesPour(rpId).filter(k => k.type !== 'app'); }
  // Les applis dont la clé exige l'empreinte à chaque usage (l'appli du téléphone ; pas la montre, gardée par son seul
  // verrouillage) : elles peuvent prouver la présence d'Ahmed pour un geste sensible. Les clés associées avant le
  // 2026-10-21 18:30 n'ont pas la marque : celles de l'appli du téléphone s'appellent « appli … » (créées par elle).
  appsAvecEmpreinte() {
    return this.d.cles.filter(k => k.type === 'app' && (k.empreinte === true || (k.empreinte === undefined && /^appli /.test(k.nom || ''))));
  }

  sauver() {
    const t = Date.now();
    for (const [h, fin] of Object.entries(this.d.sessions)) if (!(fin > this.maintenant())) delete this.d.sessions[h];
    fs.mkdirSync(path.dirname(this.fichier), { recursive: true, mode: 0o700 });
    const tmp = `${this.fichier}.${process.pid}.${t}.tmp`;
    fs.writeFileSync(tmp, JSON.stringify(this.d, null, 1), { mode: 0o600 });
    fs.renameSync(tmp, this.fichier);
  }

  actif() { return this.illisible || this.clesPour(null).length > 0; }     // le verrou du TÉLÉPHONE

  touchIdMac() { return this.clesPour(MAC).length > 0; }

  cles() { return this.d.cles.map(c => ({ id: c.id, nom: c.nom, cree: c.cree, dernier: c.dernier || null, mac: estMac(c) })); }

  bloque() {
    const t = this.maintenant();
    this.echecs = this.echecs.filter(x => t - x < FENETRE_ECHECS);
    return this.echecs.length >= ECHECS_MAX;
  }

  echec(e) { this.echecs.push(this.maintenant()); return e; }

  // Le code à 6 chiffres, tiré SUR LE MAC (route locale seulement)
  nouveauCode() {
    const v = String(crypto.randomInt(0, 1e6)).padStart(6, '0');
    this.code = { v, fin: this.maintenant() + DUREE_CODE, essais: 0 };
    return { code: v, fin: this.code.fin };
  }

  defi(type, extra = {}) {
    const t = this.maintenant();
    for (const [k, x] of this.defis) if (x.fin <= t) this.defis.delete(k);
    const v = b64u(crypto.randomBytes(32));
    while (this.defis.size >= 64) this.defis.delete(this.defis.keys().next().value);    // borné, les plus vieux d'abord
    this.defis.set(v, { type, fin: t + DUREE_DEFI, ...extra });
    return v;
  }

  prendreDefi(v, type) {                                          // à usage unique, même si la suite échoue
    const x = this.defis.get(v);
    this.defis.delete(v);
    return x && x.type === type && x.fin > this.maintenant() ? x : null;
  }

  verifierCode(code) {
    if (this.bloque()) throw new Error('trop d’essais ratés : réessaie dans un quart d’heure');
    const c = this.code;
    if (!c || c.fin <= this.maintenant()) throw this.echec(new Error('pas de code en cours : tire-en un sur le Mac'));
    c.essais += 1;
    const recu = Buffer.from(String(code || '').replace(/\D/g, '')), attendu = Buffer.from(c.v);
    if (recu.length !== attendu.length || !crypto.timingSafeEqual(recu, attendu)) {
      if (c.essais >= ESSAIS_CODE) this.code = null;
      throw this.echec(new Error('code faux'));
    }
    this.code = null;                                               // un code ne sert qu'une fois
  }

  optionsAssociation(code, rpId) {
    this.verifierCode(code);
    return {
      challenge: this.defi('create'), rp: { id: rpId, name: 'Hakim' },
      user: { id: b64u(crypto.randomBytes(16)), name: 'ahmed', displayName: 'Ahmed' },
      pubKeyCredParams: [{ type: 'public-key', alg: -7 }, { type: 'public-key', alg: -257 }],
      authenticatorSelection: { authenticatorAttachment: 'platform', residentKey: 'preferred', userVerification: 'required' },
      attestation: 'none', timeout: 120000,
      excludeCredentials: this.passkeysPour(rpId).map(k => ({ type: 'public-key', id: k.id })),
    };
  }

  // Le Touch ID du Mac : associé depuis le Mac lui-même (route locale seulement), sans code ; un seul à la fois.
  optionsAssociationMac() {
    if (this.touchIdMac()) throw new Error('le Touch ID de ce Mac est déjà associé (retire-le d’abord)');
    return {
      challenge: this.defi('create-mac'), rp: { id: MAC, name: 'Hakim (Mac)' },
      user: { id: b64u(crypto.randomBytes(16)), name: 'ahmed-mac', displayName: 'Ahmed (Mac)' },
      pubKeyCredParams: [{ type: 'public-key', alg: -7 }, { type: 'public-key', alg: -257 }],
      authenticatorSelection: { authenticatorAttachment: 'platform', residentKey: 'preferred', userVerification: 'required' },
      attestation: 'none', timeout: 120000,
    };
  }

  associerMac(reponse, { origine }) {
    let v; try { v = defiDe(reponse.clientDataJSON); } catch (_) { throw new Error('réponse illisible'); }
    if (!this.prendreDefi(v, 'create-mac')) throw new Error('défi inconnu ou périmé : recommence');
    if (this.touchIdMac()) throw new Error('le Touch ID de ce Mac est déjà associé');
    const cle = verifierAssociation(reponse, { defi: v, origine, rpId: MAC });
    this.d.cles.push({ ...cle, rpId: MAC, nom: 'Touch ID du Mac', cree: this.maintenant() });
    this.sauver();
  }

  // La preuve de présence : un défi lié à UNE action (« mission:accepter:<id> »…), à usage unique.
  optionsPresence(rpId, action) {
    const cles = this.passkeysPour(rpId);
    if (!cles.length && (rpId === MAC || !this.appsAvecEmpreinte().length))
      throw new Error(rpId === MAC ? 'aucun Touch ID associé sur ce Mac' : 'aucun téléphone associé');
    return { challenge: this.defi('presence', { action: String(action), rpId }), rpId, userVerification: 'required', timeout: 120000,
      allowCredentials: cles.map(k => ({ type: 'public-key', id: k.id })) };
  }

  verifierPresence(reponse, { origine, rpId, action }) {
    if (reponse && reponse.app) return this.verifierPresenceApp(reponse, { rpId, action });
    let v; try { v = defiDe(reponse && reponse.clientDataJSON); } catch (_) { throw new Error('aucune preuve de présence'); }
    const x = this.prendreDefi(v, 'presence');
    if (!x || x.action !== String(action) || x.rpId !== rpId) throw new Error('preuve de présence périmée ou faite pour une autre action');
    const cle = this.passkeysPour(rpId).find(k => k.id === reponse.id);
    const compteur = verifierDeverrouillage(reponse, cle, { defi: v, origine, rpId });
    cle.compteur = compteur; cle.dernier = this.maintenant();
    this.sauver();
    return true;
  }

  // (2026-10-21, accord d'Ahmed) la même preuve, signée par l'appli Android : son empreinte débloque sa clé, qui signe
  // le défi de présence (lié à l'action, à usage unique, 2 min) — jamais pour le Mac, jamais par la montre
  verifierPresenceApp(reponse, { rpId, action }) {
    const defi = String(reponse.defi || '');
    const x = this.prendreDefi(defi, 'presence');
    if (!x || x.action !== String(action) || x.rpId !== rpId || rpId === MAC) throw new Error('preuve de présence périmée ou faite pour une autre action');
    const cle = this.appsAvecEmpreinte().find(k => k.id === reponse.app);
    if (!cle) throw new Error('cette appli ne peut pas prouver ta présence (clé inconnue ou sans empreinte)');
    let ok = false;
    try {
      ok = crypto.verify('sha256', Buffer.from(defi), { key: Buffer.from(cle.spki, 'base64'), format: 'der', type: 'spki' },
        Buffer.from(String(reponse.signature || ''), 'base64'));
    } catch (_) { ok = false; }
    if (!ok) throw new Error('signature refusée');
    cle.dernier = this.maintenant();
    this.sauver();
    return true;
  }

  associer(reponse, { origine, rpId, nom }) {
    if (this.bloque()) throw new Error('trop d’essais ratés : réessaie dans un quart d’heure');
    let v; try { v = defiDe(reponse.clientDataJSON); } catch (_) { throw this.echec(new Error('réponse illisible')); }
    if (!this.prendreDefi(v, 'create')) throw this.echec(new Error('défi inconnu ou périmé : recommence avec un nouveau code'));
    let cle; try { cle = verifierAssociation(reponse, { defi: v, origine, rpId }); } catch (e) { throw this.echec(e); }
    if (this.d.cles.some(k => k.id === cle.id)) throw new Error('ce téléphone est déjà associé');
    this.d.cles.push({ ...cle, rpId, nom: String(nom || 'téléphone').slice(0, 60), cree: this.maintenant() });
    this.illisible = false;                                         // réassocier depuis le Mac répare un fichier illisible
    const session = this.ouvrirSession();                           // associer, c'est aussi déverrouiller
    return { session };
  }

  optionsDeverrouillage(rpId) {
    const passkeys = this.passkeysPour(rpId);
    if (!passkeys.length) throw new Error('aucun téléphone associé');
    return { challenge: this.defi('get'), rpId, userVerification: 'required', timeout: 120000,
      allowCredentials: passkeys.map(k => ({ type: 'public-key', id: k.id })) };
  }

  // L'appli Android de Hakim (2026-10-21) : une clé de signature EC P-256 gardée par Android (Keystore, empreinte exigée
  // à chaque usage), associée avec le même code à 6 chiffres tiré sur le Mac ; le déverrouillage signe un défi à usage
  // unique (2 min). Même session que le navigateur (cookie « verrou », 2 jours).
  associerApp(code, spkiB64, nom, empreinte = false) {
    this.verifierCode(code);
    let cle;
    try { cle = crypto.createPublicKey({ key: Buffer.from(String(spkiB64 || ''), 'base64'), format: 'der', type: 'spki' }); }
    catch (_) { throw this.echec(new Error('clé illisible')); }
    if (cle.asymmetricKeyType !== 'ec') throw this.echec(new Error('clé refusée (EC P-256 attendue)'));
    const id = 'app-' + b64u(crypto.randomBytes(12));
    this.d.cles.push({ id, type: 'app', spki: String(spkiB64), rpId: 'appli', nom: String(nom || 'appli Android').slice(0, 60),
      empreinte: empreinte === true, cree: this.maintenant() });
    this.illisible = false;
    return { id, session: this.ouvrirSession() };
  }

  defiApp() {
    if (!this.d.cles.some(k => k.type === 'app')) throw new Error('aucune appli associée');
    return this.defi('app');
  }

  deverrouillerApp(id, defi, signatureB64) {
    if (!this.prendreDefi(String(defi || ''), 'app')) throw new Error('défi inconnu ou périmé');
    const cle = this.d.cles.find(k => k.type === 'app' && k.id === id);
    if (!cle) throw new Error('appli inconnue : réassocie-la avec un code tiré sur le Mac');
    let ok = false;
    try {
      ok = crypto.verify('sha256', Buffer.from(String(defi)), { key: Buffer.from(cle.spki, 'base64'), format: 'der', type: 'spki' },
        Buffer.from(String(signatureB64 || ''), 'base64'));
    } catch (_) { ok = false; }
    if (!ok) throw new Error('signature refusée');
    cle.dernier = this.maintenant();
    return { session: this.ouvrirSession() };
  }

  // Relecture du 2026-10-20 : le gel après 10 échecs bloquait AUSSI le vrai téléphone (10 réponses vides
  // suffisaient). Une signature d'empreinte ne se devine pas : pas de gel ici, seulement pour le code à 6 chiffres.
  deverrouiller(reponse, { origine, rpId }) {
    let v; try { v = defiDe(reponse.clientDataJSON); } catch (_) { throw new Error('réponse illisible'); }
    if (!this.prendreDefi(v, 'get')) throw new Error('défi inconnu ou périmé');
    const cle = this.passkeysPour(rpId).find(k => k.id === reponse.id);
    const compteur = verifierDeverrouillage(reponse, cle, { defi: v, origine, rpId });
    cle.compteur = compteur; cle.dernier = this.maintenant();
    return { session: this.ouvrirSession() };
  }

  ouvrirSession() {
    const s = b64u(crypto.randomBytes(32));
    this.d.sessions[empreinte(s)] = this.maintenant() + DUREE_SESSION;
    this.sauver();
    return s;
  }

  sessionValide(s) {
    if (!s) return false;
    const fin = this.d.sessions[empreinte(s)];
    return Number.isFinite(fin) && fin > this.maintenant();
  }

  fermerSession(s) { if (s && delete this.d.sessions[empreinte(s)]) this.sauver(); }

  oublier(id) {                                                    // id absent : tous les téléphones (pas le Touch ID du Mac)
    this.d.cles = id ? this.d.cles.filter(k => k.id !== id) : this.d.cles.filter(estMac);
    if (!this.clesPour(null).length) this.d.sessions = {};
    this.illisible = false;
    this.sauver();
  }

  oublierMac() { this.d.cles = this.d.cles.filter(k => !estMac(k)); this.sauver(); }
}

const lireCookie = (entete, nom) => {
  for (const p of String(entete || '').split(';')) {
    const i = p.indexOf('=');
    if (i > 0 && p.slice(0, i).trim() === nom) return p.slice(i + 1).trim();
  }
  return null;
};

module.exports = { cbor, lireAuthData, coseVersJwk, verifierAssociation, verifierDeverrouillage, b64u, deb64u,
  Verrou, lireCookie, DUREE_SESSION, MAC };
