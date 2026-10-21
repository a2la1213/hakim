/* Le verrou d'empreinte (passkey.js) contre un AUTHENTIFICATEUR LOGICIEL : node --test test-passkey.js
   Une vraie clé P-256 joue le téléphone (telephone-logiciel.js) : association (attestation « none » en CBOR), puis déverrouillages
   juste et piégés (défi, origine, domaine, empreinte absente, signature, compteur). */
'use strict';
const test = require('node:test');
const assert = require('node:assert');
const P = require('./passkey.js');

const RP = 'mac.exemple.ts.net', ORIGINE = `https://${RP}`;

const { telephone: tel } = require('./telephone-logiciel.js');
const telephone = () => tel(RP);

test('association puis déverrouillage avec l’empreinte', () => {
  const t = telephone();
  const cle = P.verifierAssociation(t.creer('defi-1'), { defi: 'defi-1', origine: ORIGINE, rpId: RP });
  assert.strictEqual(cle.alg, -7);
  const compteur = P.verifierDeverrouillage(t.signer('defi-2'), cle, { defi: 'defi-2', origine: ORIGINE, rpId: RP });
  assert.strictEqual(compteur, 1);
});

test('les pièges sont refusés : défi, origine, domaine, sans empreinte, signature, compteur, clé inconnue', () => {
  const t = telephone();
  const cle = P.verifierAssociation(t.creer('d0'), { defi: 'd0', origine: ORIGINE, rpId: RP });
  const opts = (defi) => ({ defi, origine: ORIGINE, rpId: RP });
  assert.throws(() => P.verifierDeverrouillage(t.signer('autre'), cle, opts('d1')), /défi/);
  assert.throws(() => P.verifierDeverrouillage(t.signer('d2', { origine: 'https://evil.ts.net' }), cle, opts('d2')), /origine/);
  assert.throws(() => P.verifierDeverrouillage(t.signer('d3'), cle, { defi: 'd3', origine: ORIGINE, rpId: 'evil.ts.net' }), /domaine/);
  assert.throws(() => P.verifierDeverrouillage(t.signer('d4', { flags: 1 }), cle, opts('d4')), /empreinte/);
  assert.throws(() => P.verifierDeverrouillage(t.signer('d5', { type: 'webauthn.create' }), cle, opts('d5')), /type/);
  const s = t.signer('d6'); s.signature = P.b64u(Buffer.from(P.deb64u(s.signature)).fill(1, 10, 14));
  assert.throws(() => P.verifierDeverrouillage(s, cle, opts('d6')), /signature|asn1|DER|bad|wrong|ECDSA/i);
  const bon = t.signer('d7');
  const c7 = P.verifierDeverrouillage(bon, cle, opts('d7'));
  assert.throws(() => P.verifierDeverrouillage(bon, { ...cle, compteur: c7 }, opts('d7')), /compteur/);   // rejeu
  assert.throws(() => P.verifierDeverrouillage({ ...t.signer('d8'), id: 'inconnue' }, cle, opts('d8')), /inconnue/);
});

test('l’association sans empreinte est refusée', () => {
  const t = telephone();
  const r = t.creer('x');
  const att = P.cbor(P.deb64u(r.attestationObject))[0];
  const ad = Buffer.from(att.get('authData')); ad[32] = 1 | 64;                    // présent, mais pas vérifié (UV)
  att.set('authData', ad);
  const encAtt = (m) => { const parts = [Buffer.from([0xa3])]; for (const [k, v] of m) {
    const kb = Buffer.from(k); parts.push(Buffer.from([0x60 | kb.length]), kb);
    if (Buffer.isBuffer(v)) { const l = Buffer.alloc(3); l[0] = 0x59; l.writeUInt16BE(v.length, 1); parts.push(l, v); }
    else if (typeof v === 'string') { const vb = Buffer.from(v); parts.push(Buffer.from([0x60 | vb.length]), vb); }
    else parts.push(Buffer.from([0xa0])); } return Buffer.concat(parts); };
  assert.throws(() => P.verifierAssociation({ clientDataJSON: r.clientDataJSON, attestationObject: P.b64u(encAtt(att)) },
    { defi: 'x', origine: ORIGINE, rpId: RP }), /empreinte/);
});

test('le verrou : code du Mac, défis à usage unique, sessions gardées sur disque, essais limités', () => {
  const os = require('os'), fs = require('fs'), path = require('path');
  const f = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'verrou-')), 'verrou.json');
  let t = 1e12;
  const v = new P.Verrou(f, { maintenant: () => t });
  const ctx = { origine: ORIGINE, rpId: RP };
  assert.strictEqual(v.actif(), false);
  assert.throws(() => v.optionsAssociation('000000', RP), /pas de code/);
  const { code } = v.nouveauCode();
  assert.throws(() => v.optionsAssociation('111111' === code ? '222222' : '111111', RP), /code faux/);
  const o = v.optionsAssociation(code, RP);
  assert.strictEqual(o.authenticatorSelection.userVerification, 'required');
  assert.throws(() => v.optionsAssociation(code, RP), /pas de code/);                     // un code ne sert qu'une fois
  const tel = telephone();
  const { session } = v.associer({ ...tel.creer(o.challenge) }, { ...ctx, nom: 'Fold 7' });
  assert.ok(v.actif() && v.sessionValide(session));
  assert.throws(() => v.associer(tel.creer(o.challenge), ctx), /défi/);                   // défi déjà pris
  // déverrouillage, puis rejeu du même défi refusé
  const od = v.optionsDeverrouillage(RP);
  const rep = tel.signer(od.challenge);
  const s2 = v.deverrouiller(rep, ctx).session;
  assert.ok(v.sessionValide(s2));
  assert.throws(() => v.deverrouiller(rep, ctx), /défi/);
  // un redémarrage du cockpit garde la clé et les sessions (par empreinte seulement)
  const brut = fs.readFileSync(f, 'utf8');
  assert.ok(!brut.includes(s2) && (fs.statSync(f).mode & 0o777) === 0o600);
  const v2 = new P.Verrou(f, { maintenant: () => t });
  assert.ok(v2.actif() && v2.sessionValide(s2) && !v2.sessionValide('nimporte'));
  // la session expire
  t += P.DUREE_SESSION + 1;
  assert.ok(!v2.sessionValide(s2));
  // défi périmé
  const od2 = v2.optionsDeverrouillage(RP); t += 3 * 60e3;
  assert.throws(() => v2.deverrouiller(tel.signer(od2.challenge), ctx), /défi/);
  // des échecs en rafale ne gèlent PAS le déverrouillage du vrai téléphone (relecture du 2026-10-20)
  for (let k = 0; k < 30; k++) { try { v2.deverrouiller(tel.signer('faux'), ctx); } catch (_) {} }
  const od3 = v2.optionsDeverrouillage(RP);
  assert.ok(v2.sessionValide(v2.deverrouiller(tel.signer(od3.challenge), ctx).session));
  // oublier : plus de clé, plus de session
  v2.oublier();
  assert.ok(!v2.actif());
});

test('le code à 6 chiffres : 5 essais au plus, puis il faut en tirer un autre', () => {
  const os = require('os'), fs = require('fs'), path = require('path');
  const v = new P.Verrou(path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'verrou-')), 'v.json'));
  const { code } = v.nouveauCode();
  const faux = code === '000000' ? '000001' : '000000';
  for (let k = 0; k < 5; k++) assert.throws(() => v.optionsAssociation(faux, RP), /code faux/);
  assert.throws(() => v.optionsAssociation(code, RP), /pas de code/);
  assert.strictEqual(P.lireCookie('a=1; verrou=abc; b=2', 'verrou'), 'abc');
  assert.strictEqual(P.lireCookie('', 'verrou'), null);
});

test('compteur : une clé qui comptait ne peut pas revenir à 0', () => {
  const t = telephone();
  const cle = P.verifierAssociation(t.creer('a'), { defi: 'a', origine: ORIGINE, rpId: RP });
  const ok = t.signer('b');
  assert.throws(() => P.verifierDeverrouillage(ok, { ...cle, compteur: 5 }, { defi: 'b', origine: ORIGINE, rpId: RP }), /compteur/);
  assert.strictEqual(P.verifierDeverrouillage(ok, { ...cle, compteur: 0 }, { defi: 'b', origine: ORIGINE, rpId: RP }), 1);
  assert.throws(() => P.lireAuthData(Buffer.alloc(10)), /trop courtes/);
});


test('CBOR piégé (longueur annoncée géante, imbrication) : refusé tout de suite, sans allocation', () => {
  const t0 = Date.now();
  const geant = Buffer.from([0x9b, 0x00, 0x00, 0x00, 0x10, 0x00, 0x00, 0x00, 0x00]);     // tableau de 2^36 éléments
  assert.throws(() => P.cbor(geant), /impossible/);
  assert.throws(() => P.cbor(Buffer.from([0xbb, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff])), /impossible/);
  assert.throws(() => P.cbor(Buffer.alloc(40, 0x81)), /imbriqué/);
  // dans un authenticatorData de déverrouillage avec le drapeau AT
  const ad = Buffer.concat([Buffer.alloc(32), Buffer.from([1 | 4 | 64]), Buffer.alloc(4), Buffer.alloc(16), Buffer.from([0, 1, 7]), geant]);
  assert.throws(() => P.lireAuthData(ad), /impossible/);
  assert.ok(Date.now() - t0 < 1000);
});

test('C-H1 : preuve de présence liée à UNE action, à usage unique ; Touch ID du Mac à part', () => {
  const os = require('os'), fs = require('fs'), path = require('path');
  const f = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'verrou-')), 'verrou.json');
  const v = new P.Verrou(f);
  const ctx = { origine: ORIGINE, rpId: RP };
  const { code } = v.nouveauCode();
  const t = telephone();
  v.associer(t.creer(v.optionsAssociation(code, RP).challenge), { ...ctx, nom: 'Fold' });
  // sur le téléphone : la preuve vaut pour l'action demandée, une fois
  const o = v.optionsPresence(RP, 'mission:accepter:x1');
  assert.strictEqual(o.userVerification, 'required');
  const r = t.signer(o.challenge);
  assert.throws(() => v.verifierPresence(r, { ...ctx, action: 'mission:accepter:x2' }), /autre action/);
  const o2 = v.optionsPresence(RP, 'mission:accepter:x1');
  const r2 = t.signer(o2.challenge);
  assert.ok(v.verifierPresence(r2, { ...ctx, action: 'mission:accepter:x1' }));
  assert.throws(() => v.verifierPresence(r2, { ...ctx, action: 'mission:accepter:x1' }), /périmée|autre action/);   // rejeu
  assert.throws(() => v.verifierPresence({}, { ...ctx, action: 'cle-api' }), /aucune preuve/);
  // sans empreinte (UV absent) : refusée
  const o3 = v.optionsPresence(RP, 'cle-api');
  assert.throws(() => v.verifierPresence(t.signer(o3.challenge, { flags: 1 }), { ...ctx, action: 'cle-api' }), /empreinte/);
  // le Mac : pas de Touch ID tant qu'il n'est pas associé ; la clé du téléphone ne sert pas pour localhost
  assert.ok(!v.touchIdMac());
  assert.throws(() => v.optionsPresence(P.MAC, 'cle-api'), /aucun Touch ID/);
  const mac = tel(P.MAC);
  const om = v.optionsAssociationMac();
  v.associerMac(mac.creer(om.challenge, 'http://localhost:4317'), { origine: 'http://localhost:4317' });
  assert.ok(v.touchIdMac() && v.actif());
  assert.throws(() => v.optionsAssociationMac(), /déjà associé/);
  const op = v.optionsPresence(P.MAC, 'verrou:code');
  assert.deepStrictEqual(op.allowCredentials.length, 1);
  assert.ok(v.verifierPresence(mac.signer(op.challenge, { origine: 'http://localhost:4317' }), { origine: 'http://localhost:4317', rpId: P.MAC, action: 'verrou:code' }));
  const opt = v.optionsPresence(P.MAC, 'verrou:code');                       // le téléphone ne signe pas pour le Mac
  assert.throws(() => v.verifierPresence(t.signer(opt.challenge), { origine: 'http://localhost:4317', rpId: P.MAC, action: 'verrou:code' }), /inconnue/);
  // oublier les téléphones garde le Touch ID du Mac
  v.oublier();
  assert.ok(!v.actif() && v.touchIdMac());
  v.oublierMac();
  assert.ok(!v.touchIdMac());
});

test('C-M1 : un fichier du verrou illisible FERME le verrou (au lieu de l’ouvrir)', () => {
  const os = require('os'), fs = require('fs'), path = require('path');
  const f = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'verrou-')), 'verrou.json');
  fs.writeFileSync(f, '{ abîmé');
  const v = new P.Verrou(f);
  assert.ok(v.illisible && v.actif());
  assert.throws(() => v.optionsDeverrouillage(RP), /aucun téléphone/);
  fs.writeFileSync(f, '{"autre": 1}');
  assert.ok(new P.Verrou(f).actif());
  const absent = new P.Verrou(path.join(path.dirname(f), 'absent.json'));
  assert.ok(!absent.illisible && !absent.actif());
});
