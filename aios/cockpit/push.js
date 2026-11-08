/* Les notifications du téléphone (Ahmed, 2026-10-20 : « pour les notifications de sollicitations je veux bien ») —
   Web Push sans bibliothèque : quand Hakim te relance de lui-même ou donne le résultat d'un agent et qu'aucune page
   n'est visible, le cockpit envoie une notification au téléphone (via le service de push du navigateur ; le contenu
   est chiffré de bout en bout, le service ne le lit pas).
   - VAPID (RFC 8292) : une paire de clés P-256 tirée une fois (~/AIOS/jarvis/vapid.json, 0600) ; chaque envoi
     porte un jeton ES256 signé (aud = l'origine du service, 12 h).
   - Chiffrement aes128gcm (RFC 8291), vérifié contre le vecteur de test de l'annexe A de la RFC (test-push.js). */
'use strict';
const crypto = require('crypto');
const fs = require('fs');
const https = require('https');
const path = require('path');

const b64u = (b) => Buffer.from(b).toString('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
const deb64u = (s) => Buffer.from(String(s).replace(/\s+/g, '').replace(/-/g, '+').replace(/_/g, '/'), 'base64');
const hmac = (cle, ...donnees) => { const h = crypto.createHmac('sha256', cle); for (const d of donnees) h.update(d); return h.digest(); };

// RFC 8291 §3.4 ; `fixe` (clé éphémère et sel imposés) ne sert qu'au vecteur de test
function chiffrer(contenu, p256dh, auth, fixe = null) {
  const uaPublic = deb64u(p256dh), secret = deb64u(auth);
  if (uaPublic.length !== 65 || secret.length < 16) throw new Error('abonnement de push invalide');
  const ecdh = crypto.createECDH('prime256v1');
  if (fixe) ecdh.setPrivateKey(fixe.prive); else ecdh.generateKeys();
  const asPublic = ecdh.getPublicKey();
  const ecdhSecret = ecdh.computeSecret(uaPublic);
  const prkKey = hmac(secret, ecdhSecret);
  const keyInfo = Buffer.concat([Buffer.from('WebPush: info\0'), uaPublic, asPublic]);
  const ikm = hmac(prkKey, keyInfo, Buffer.from([1]));
  const sel = fixe ? fixe.sel : crypto.randomBytes(16);
  const prk = hmac(sel, ikm);
  const cek = hmac(prk, Buffer.from('Content-Encoding: aes128gcm\0'), Buffer.from([1])).subarray(0, 16);
  const nonce = hmac(prk, Buffer.from('Content-Encoding: nonce\0'), Buffer.from([1])).subarray(0, 12);
  const clair = Buffer.concat([Buffer.from(contenu), Buffer.from([2])]);       // un seul enregistrement : délimiteur 0x02
  const c = crypto.createCipheriv('aes-128-gcm', cek, nonce);
  const chiffre = Buffer.concat([c.update(clair), c.final(), c.getAuthTag()]);
  const rs = Buffer.alloc(4); rs.writeUInt32BE(4096);
  const entete = Buffer.concat([sel, rs, Buffer.from([asPublic.length]), asPublic]);
  return { corps: Buffer.concat([entete, chiffre]), entete, chiffre };
}

function genererVapid() {
  const ecdh = crypto.createECDH('prime256v1');
  ecdh.generateKeys();
  return { public: b64u(ecdh.getPublicKey()), prive: b64u(ecdh.getPrivateKey()) };
}

function jetonVapid(vapid, aud, sujet, maintenant = Date.now()) {
  const pub = deb64u(vapid.public);
  const jwk = { kty: 'EC', crv: 'P-256', x: b64u(pub.subarray(1, 33)), y: b64u(pub.subarray(33, 65)), d: vapid.prive };
  const tete = b64u(JSON.stringify({ typ: 'JWT', alg: 'ES256' }));
  const corps = b64u(JSON.stringify({ aud, exp: Math.floor(maintenant / 1000) + 12 * 3600, sub: sujet }));
  const sig = crypto.sign('sha256', Buffer.from(`${tete}.${corps}`), { key: crypto.createPrivateKey({ key: jwk, format: 'jwk' }), dsaEncoding: 'ieee-p1363' });
  return `${tete}.${corps}.${b64u(sig)}`;
}

const SERVICES_PUSH = new RegExp(process.env.JARVIS_PUSH_SERVICES
  || '^(fcm\\.googleapis\\.com|updates\\.push\\.services\\.mozilla\\.com|web\\.push\\.apple\\.com|[a-z0-9-]+\\.notify\\.windows\\.com)$', 'i');

class Notifications {
  constructor(dossier, { sujet = 'https://localhost' } = {}) {
    this.fichierVapid = path.join(dossier, 'vapid.json');
    this.fichierAbonnements = path.join(dossier, 'notifications.json');
    this.sujet = sujet;
    try { this.vapid = JSON.parse(fs.readFileSync(this.fichierVapid, 'utf8')); } catch (_) { this.vapid = null; }
    if (!this.vapid || !this.vapid.public || !this.vapid.prive) {
      this.vapidNeuve = true;
      this.vapid = genererVapid();
      fs.mkdirSync(dossier, { recursive: true });
      fs.writeFileSync(this.fichierVapid, JSON.stringify(this.vapid), { mode: 0o600 });
    }
    try { this.abonnements = JSON.parse(fs.readFileSync(this.fichierAbonnements, 'utf8')).abonnements || []; } catch (_) { this.abonnements = []; }
  }

  sauver() {
    const tmp = `${this.fichierAbonnements}.${process.pid}.tmp`;
    fs.writeFileSync(tmp, JSON.stringify({ abonnements: this.abonnements, maj_ms: Date.now() }), { mode: 0o600 });
    fs.renameSync(tmp, this.fichierAbonnements);
  }

  abonner(a, appareil) {
    // seulement les services de push des navigateurs : le cockpit ne POSTe jamais vers une adresse quelconque (SSRF)
    let hote = ''; try { hote = new URL(a && a.endpoint).hostname; } catch (_) {}
    if (!SERVICES_PUSH.test(hote)) throw new Error('abonnement invalide : service de push inconnu');
    const ok = a && typeof a.endpoint === 'string' && /^https:\/\/[a-z0-9.-]+(:\d+)?\//i.test(a.endpoint) && a.endpoint.length < 2000
      && a.keys && typeof a.keys.p256dh === 'string' && typeof a.keys.auth === 'string';
    if (!ok) throw new Error('abonnement invalide');
    deb64u(a.keys.p256dh).length === 65 || (() => { throw new Error('clé p256dh invalide'); })();
    this.abonnements = this.abonnements.filter(x => x.endpoint !== a.endpoint).concat([{ endpoint: a.endpoint,
      keys: { p256dh: a.keys.p256dh, auth: a.keys.auth }, appareil: String(appareil || '').slice(0, 60), cree: Date.now() }]).slice(-5);
    this.sauver();
  }

  desabonner(endpoint) { this.abonnements = this.abonnements.filter(x => x.endpoint !== endpoint); this.sauver(); }

  // envoie à tous les appareils abonnés ; un abonnement mort (404/410) est retiré
  async envoyer(message, envoyerHttp = posterHttps) {
    const contenu = JSON.stringify({ titre: message.titre || 'Hakim', corps: String(message.corps || '').slice(0, 300),
      url: message.url || '/parler', tag: message.tag || 'hakim' });
    const resultats = [];
    for (const a of [...this.abonnements]) {
      try {
        const { corps } = chiffrer(contenu, a.keys.p256dh, a.keys.auth);
        const u = new URL(a.endpoint);
        const statut = await envoyerHttp(a.endpoint, corps, {
          'Content-Encoding': 'aes128gcm', 'Content-Type': 'application/octet-stream', TTL: '86400', Urgency: 'high',
          Authorization: `vapid t=${jetonVapid(this.vapid, `${u.protocol}//${u.host}`, this.sujet)}, k=${this.vapid.public}`,
        });
        if (statut === 404 || statut === 410 || statut === 403) this.desabonner(a.endpoint);
        resultats.push(statut);
      } catch (e) { resultats.push(String(e.message || e)); }
    }
    return resultats;
  }
}

function posterHttps(url, corps, entetes) {
  return new Promise((ok) => {
    const r = https.request(url, { method: 'POST', headers: { ...entetes, 'Content-Length': corps.length }, timeout: 15000 }, (res) => {
      res.resume(); res.on('end', () => ok(res.statusCode));
    });
    r.on('error', (e) => ok(`erreur ${e.code || e.message}`));
    r.on('timeout', () => { r.destroy(); ok('délai dépassé'); });
    r.end(corps);
  });
}

module.exports = { chiffrer, genererVapid, jetonVapid, Notifications, b64u, deb64u };
