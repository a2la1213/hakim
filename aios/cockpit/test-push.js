/* Les notifications Web Push (push.js) : node --test test-push.js
   Le chiffrement aes128gcm est vérifié octet pour octet contre le vecteur de test de la RFC 8291 (annexe A). */
'use strict';
const test = require('node:test');
const assert = require('node:assert');
const crypto = require('crypto');
const P = require('./push.js');

const V = {   // RFC 8291, annexe A (les coupures de ligne de la RFC sont retirées par deb64u)
  clair: 'V2hlbiBJIGdyb3cgdXAsIEkgd2FudCB0byBiZSBhIHdhdGVybWVsb24',
  asPrive: 'yfWPiYE-n46HLnH0KqZOF1fJJU3MYrct3AELtAQ-oRw',
  uaPublic: 'BCVxsr7N_eNgVRqvHtD0zTZsEc6-VV-JvLexhqUzORcxaOzi6-AYWXvTBHm4bjyPjs7Vd8pZGH6SRpkNtoIAiw4',
  sel: 'DGv6ra1nlYgDCS1FRnbzlw',
  auth: 'BTBZMqHH6r4Tts7J_aSIgg',
  entete: 'DGv6ra1nlYgDCS1FRnbzlwAAEABBBP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27mlmlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wEqKK6PBru3jl7A8',
  chiffre: '8pfeW0KbunFT06SuDKoJH9Ql87S1QUrdirN6GcG7sFz1y1sqLgVi1VhjVkHsUoEsbI_0LpXMuGvnzQ',
};

test('aes128gcm : identique au vecteur de test de la RFC 8291', () => {
  const r = P.chiffrer(P.deb64u(V.clair), V.uaPublic, V.auth, { prive: P.deb64u(V.asPrive), sel: P.deb64u(V.sel) });
  assert.strictEqual(P.b64u(r.entete), V.entete);
  assert.strictEqual(P.b64u(r.chiffre), V.chiffre);
});

test('jeton VAPID : ES256 vérifiable avec la clé publique, aud et sub posés', () => {
  const v = P.genererVapid();
  const t = P.jetonVapid(v, 'https://fcm.googleapis.com', 'https://mac.exemple.ts.net', 1792440000000);
  const [tete, corps, sig] = t.split('.');
  const pub = P.deb64u(v.public);
  const cle = crypto.createPublicKey({ key: { kty: 'EC', crv: 'P-256', x: P.b64u(pub.subarray(1, 33)), y: P.b64u(pub.subarray(33)) }, format: 'jwk' });
  assert.ok(crypto.verify('sha256', Buffer.from(`${tete}.${corps}`), { key: cle, dsaEncoding: 'ieee-p1363' }, P.deb64u(sig)));
  const c = JSON.parse(P.deb64u(corps));
  assert.strictEqual(c.aud, 'https://fcm.googleapis.com');
  assert.strictEqual(c.sub, 'https://mac.exemple.ts.net');
});

test('abonnements : validés, plafonnés, retirés quand le service dit 410 ; contenu déchiffrable par le téléphone', async () => {
  const os = require('os'), fs = require('fs'), path = require('path');
  const n = new P.Notifications(fs.mkdtempSync(path.join(os.tmpdir(), 'push-')));
  assert.throws(() => n.abonner({ endpoint: 'http://pas-https/x', keys: {} }), /invalide/);
  assert.throws(() => n.abonner({ endpoint: 'https://127.0.0.1:4317/api/x', keys: { p256dh: 'x', auth: 'y' } }), /service de push inconnu/);
  // un « téléphone » logiciel : sa clé et son secret
  const ua = crypto.createECDH('prime256v1'); ua.generateKeys();
  const auth = crypto.randomBytes(16);
  n.abonner({ endpoint: 'https://fcm.googleapis.com/fcm/send/abc', keys: { p256dh: P.b64u(ua.getPublicKey()), auth: P.b64u(auth) } }, 'Fold');
  n.abonner({ endpoint: 'https://fcm.googleapis.com/fcm/send/mort', keys: { p256dh: P.b64u(ua.getPublicKey()), auth: P.b64u(auth) } }, 'vieux');
  const recus = [];
  const statuts = await n.envoyer({ corps: 'Le Juge a fini : tout est juste.' }, async (url, corps, entetes) => {
    recus.push({ url, corps, entetes }); return url.endsWith('/mort') ? 410 : 201;
  });
  assert.deepStrictEqual(statuts, [201, 410]);
  assert.strictEqual(n.abonnements.length, 1);
  assert.match(recus[0].entetes.Authorization, /^vapid t=.+, k=/);
  // déchiffrement côté téléphone (RFC 8291) : le contenu est bien celui envoyé
  const b = recus[0].corps, sel = b.subarray(0, 16), idlen = b[20], asPublic = b.subarray(21, 21 + idlen), chiffre = b.subarray(21 + idlen);
  const hmac = (k, ...d) => { const h = crypto.createHmac('sha256', k); d.forEach(x => h.update(x)); return h.digest(); };
  const ikm = hmac(hmac(auth, ua.computeSecret(asPublic)), Buffer.from('WebPush: info\0'), ua.getPublicKey(), asPublic, Buffer.from([1]));
  const prk = hmac(sel, ikm);
  const cek = hmac(prk, Buffer.from('Content-Encoding: aes128gcm\0'), Buffer.from([1])).subarray(0, 16);
  const nonce = hmac(prk, Buffer.from('Content-Encoding: nonce\0'), Buffer.from([1])).subarray(0, 12);
  const d = crypto.createDecipheriv('aes-128-gcm', cek, nonce);
  d.setAuthTag(chiffre.subarray(-16));
  const clair = Buffer.concat([d.update(chiffre.subarray(0, -16)), d.final()]);
  assert.strictEqual(JSON.parse(clair.subarray(0, -1).toString()).corps, 'Le Juge a fini : tout est juste.');
});
