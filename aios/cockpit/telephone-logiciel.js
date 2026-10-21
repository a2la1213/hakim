/* Un AUTHENTIFICATEUR LOGICIEL (P-256) qui joue le téléphone d'Ahmed, pour les tests du verrou d'empreinte
   (test-passkey.js et le banc test-jarvis.sh). Jamais chargé par le cockpit. */
'use strict';
const crypto = require('crypto');
const { b64u, deb64u } = require('./passkey.js');

function enc(v) {                                         // encodeur CBOR minimal
  const tete = (t, n) => n < 24 ? Buffer.from([(t << 5) | n]) : n < 256 ? Buffer.from([(t << 5) | 24, n])
    : (() => { const b = Buffer.alloc(3); b[0] = (t << 5) | 25; b.writeUInt16BE(n, 1); return b; })();
  if (Buffer.isBuffer(v)) return Buffer.concat([tete(2, v.length), v]);
  if (typeof v === 'string') { const b = Buffer.from(v); return Buffer.concat([tete(3, b.length), b]); }
  if (typeof v === 'number') return v >= 0 ? tete(0, v) : tete(1, -1 - v);
  if (v instanceof Map) return Buffer.concat([tete(5, v.size), ...[...v].flatMap(([k, x]) => [enc(k), enc(x)])]);
  throw new Error('enc');
}

function telephone(rpId) {
  const ORIGINE = `https://${rpId}`;
  const { privateKey, publicKey } = crypto.generateKeyPairSync('ec', { namedCurve: 'P-256' });
  const jwk = publicKey.export({ format: 'jwk' });
  const credId = crypto.randomBytes(16);
  let compteur = 0;
  const authData = (flags, avecCle) => {
    const c = Buffer.alloc(4); c.writeUInt32BE(compteur);
    const base = Buffer.concat([crypto.createHash('sha256').update(rpId).digest(), Buffer.from([flags]), c]);
    if (!avecCle) return base;
    const cose = enc(new Map([[1, 2], [3, -7], [-1, 1], [-2, deb64u(jwk.x)], [-3, deb64u(jwk.y)]]));
    const l = Buffer.alloc(2); l.writeUInt16BE(credId.length);
    return Buffer.concat([base, Buffer.alloc(16), l, credId, cose]);
  };
  return {
    creer(defi, origine = ORIGINE) {
      const cd = Buffer.from(JSON.stringify({ type: 'webauthn.create', challenge: defi, origin: origine }));
      const att = enc(new Map([['fmt', 'none'], ['attStmt', new Map()], ['authData', authData(1 | 4 | 64, true)]]));
      return { clientDataJSON: b64u(cd), attestationObject: b64u(att) };
    },
    signer(defi, { origine = ORIGINE, flags = 1 | 4, type = 'webauthn.get' } = {}) {
      compteur += 1;
      const cd = Buffer.from(JSON.stringify({ type, challenge: defi, origin: origine }));
      const ad = authData(flags, false);
      const sig = crypto.sign('sha256', Buffer.concat([ad, crypto.createHash('sha256').update(cd).digest()]), { key: privateKey, dsaEncoding: 'der' });
      return { id: b64u(credId), clientDataJSON: b64u(cd), authenticatorData: b64u(ad), signature: b64u(sig) };
    },
  };
}

module.exports = { telephone, enc };
