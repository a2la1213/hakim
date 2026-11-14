// (14/11, Ahmed : « j'aimerais juste que les mix [de ma voix] soient aussi bien que sa voix ») la voix de RÉFÉRENCE dans la page Studio :
// le choix de la voix sur laquelle la voix de papa se cale (auto, une voix du projet, le profil gardé, aucune), le calage par voix
// (auto / oui / non), « garder cette voix comme référence » (un travail en file sur le Mac). Les routes passent par studio_projet.py
// (ici, un faux : jamais le vrai disque du studio) ; la page tourne dans une vm avec un DOM « caméléon ».
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const http = require('http');
const vm = require('vm');
const S = require('./studio.js');

const lire = (f) => fs.readFileSync(path.join(__dirname, f), 'utf8');
const lireCorps = (req, max) => new Promise((ok) => { const m = []; let n = 0; req.on('data', c => { n += c.length; if (n <= max) m.push(c); }); req.on('end', () => ok(n > max ? null : Buffer.concat(m))); });
function serveurDe(studio) {
  return new Promise((ok) => {
    const srv = http.createServer((req, res) => studio.route(req, res, new URL(req.url, 'http://x').pathname));
    srv.listen(0, '127.0.0.1', () => ok(srv));
  });
}
async function appel(srv, methode, chemin, corps) {
  const r = await fetch(`http://127.0.0.1:${srv.address().port}${chemin}`, { method: methode, headers: { 'Content-Type': 'application/json' },
    body: corps === undefined ? undefined : JSON.stringify(corps) });
  let j = null; try { j = JSON.parse(Buffer.from(await r.arrayBuffer()).toString()); } catch (_) {}
  return { statut: r.status, j };
}

test('(14/11) les routes de la référence : la choisir (bornée), garder une voix comme référence (en file), lister les profils gardés', async () => {
  const racine = fs.mkdtempSync(path.join(os.tmpdir(), 'studio-ref-'));
  const jarvis = path.join(racine, 'jarvis'), pid = 'PJ-20261114-053742-9bc3';
  fs.mkdirSync(path.join(jarvis, 'chansons', 'studio', 'projets', pid, 'pistes'), { recursive: true });
  let projet = { id: pid, titre: 'Moujahid', rev: 3, reference: { source: 'auto', piste: '', profil: 'hakim' }, zones: [], rendus: [],
    pistes: [{ id: 't4', nom: 'Voix de Hakim', role: 'voix_hakim', fichier: 'pistes/vocals.flac', regions: [] }] };
  const cmds = [];
  const studio = S.creer({ jarvis, lireCorps, appeler: () => ({ ok: true }), projet: (q) => {
    cmds.push(q);
    if (q.action === 'references') return { ok: true, references: [{ nom: 'hakim', source: 'Moujahid — Voix de Hakim', t: 1 }] };
    if (q.action === 'reference') {
      if (q.rev !== projet.rev) return { ok: false, erreur: 'le projet a changé entre-temps' };
      projet = { ...projet, rev: projet.rev + 1, reference: { ...projet.reference, ...(q.source ? { source: q.source } : {}), ...(q.piste !== undefined ? { piste: q.piste } : {}) } };
      return { ok: true, projet };
    }
    if (q.action === 'garder_reference') return { ok: true, travail: { id: 'J-1', type: 'reference' }, piste: q.piste };
    return { ok: false, erreur: 'inconnu' };
  } });
  const srv = await serveurDe(studio);
  try {
    let r = await appel(srv, 'POST', '/api/studio/projet/reference', { id: pid, rev: 3, source: 'piste', piste: 't4' });
    assert.equal(r.statut, 200);
    assert.deepEqual(cmds.at(-1), { action: 'reference', id: pid, rev: 3, par: 'papa', source: 'piste', piste: 't4' });
    assert.equal(r.j.projet.reference.source, 'piste');
    assert.equal(r.j.projet.pistes[0].f, `studio/projets/${pid}/pistes/vocals.flac`, 'le projet rendu à la page porte ses chemins servis');
    // une source inconnue ne passe pas ; une version d'avant : 409 (la page recharge)
    await appel(srv, 'POST', '/api/studio/projet/reference', { id: pid, rev: 4, source: 'n’importe', piste: '<b>t9</b>' });
    assert.equal(cmds.at(-1).source, undefined);
    assert.ok(!/[<>]/.test(cmds.at(-1).piste), 'les mots nettoyés');
    assert.equal((await appel(srv, 'POST', '/api/studio/projet/reference', { id: pid, rev: 1, source: 'aucune' })).statut, 409);
    assert.equal((await appel(srv, 'POST', '/api/studio/projet/reference', { id: '../x', source: 'aucune' })).statut, 404);
    r = await appel(srv, 'POST', '/api/studio/projet/garder-reference', { id: pid, piste: 't4' });
    assert.equal(r.statut, 200);
    assert.deepEqual(cmds.at(-1), { action: 'garder_reference', id: pid, piste: 't4', nom: 'hakim', par: 'papa' });
    r = await appel(srv, 'GET', '/api/studio/references');
    assert.equal(r.statut, 200);
    assert.deepEqual(r.j.references.map(x => x.nom), ['hakim']);
  } finally { srv.close(); studio.arreter(); fs.rmSync(racine, { recursive: true, force: true }); }
});

/* ---------- la page, dans une vm ---------- */
const CODE = fs.readFileSync(path.join(__dirname, 'public/studio-pistes.js'), 'utf8');
function element() {
  const vals = { value: '', checked: false, hidden: false, disabled: false, textContent: '', innerHTML: '', style: {}, dataset: {}, selectedOptions: [] };
  const ecouteurs = {};
  const proxy = new Proxy(function () {}, {
    get(_, k) {
      if (k === 'then' || typeof k === 'symbol') return undefined;
      if (k === '_ecouteurs') return ecouteurs;
      if (k === 'addEventListener') return (t, f) => { (ecouteurs[t] = ecouteurs[t] || []).push(f); };
      if (k === 'querySelectorAll' || k === 'getElementsByClassName') return () => [];
      if (k === 'querySelector' || k === 'closest') return () => null;
      if (k === 'getBoundingClientRect') return () => ({ left: 0, top: 0, width: 800, height: 60 });
      if (k in vals) return vals[k];
      return () => proxy;
    },
    set(_, k, v) { vals[k] = v; return true; },
    apply() { return proxy; },
  });
  return proxy;
}
function page(references) {
  const projet = { id: 'PJ1', titre: 'essai', rev: 1, tempo: 140, zones: [], rendus: [], master: {},
    reference: { source: 'auto', piste: '', profil: 'hakim' },
    pistes: [
      { id: 't1', role: 'batterie', nom: 'Batterie', f: 'a.flac', volume_db: 0, pan: 0, eq: {}, comp: {}, regions: [] },
      { id: 't4', role: 'voix_hakim', nom: 'Voix de <Hakim>', f: 'b.flac', volume_db: 0, pan: 0, eq: {}, comp: {}, regions: [], pro: { actif: true } },
      { id: 't5', role: 'voix_papa', nom: 'Voix de papa', f: 'c.wav', volume_db: 0, pan: 0, eq: {}, comp: {}, regions: [], pro: { actif: true, reference: 'auto' } },
    ] };
  const postes = [];
  const reponse = (o) => ({ ok: true, status: 200, json: async () => o });
  const els = new Map();
  const doc = { hidden: false, body: element(), getElementById: (id) => { if (!els.has(id)) els.set(id, element()); return els.get(id); },
    querySelectorAll: () => [], querySelector: () => null, addEventListener() {} };
  const bac = {
    esc: (x) => String(x == null ? '' : x).replace(/[&<>"']/g, (c) => '&#' + c.charCodeAt(0) + ';'),
    window: { jeton: () => 'x', addEventListener() {}, StudioAudio: { contexte: async () => ({}), dire() {}, recharger() {}, occupe: () => false } },
    document: doc, console, URLSearchParams, Map, Set, Promise, Math, Number, String, JSON, Date, Error, Float32Array,
    localStorage: { getItem: () => null, setItem() {} },
    fetch: async (u, o) => {
      u = String(u);
      if (o && o.method === 'POST') {
        const corps = JSON.parse(o.body);
        postes.push([u, corps]);
        if (u === '/api/studio/projet/reference') {
          projet.rev += 1;
          projet.reference = { ...projet.reference, source: corps.source, piste: corps.piste };
          return reponse({ ok: true, projet });
        }
        return reponse({ ok: true, travail: { id: 'J-1' } });
      }
      if (u.startsWith('/api/studio/projets')) return reponse({ ok: true, projets: [{ id: 'PJ1', titre: 'essai', pistes: 3, rev: 1 }] });
      if (u.startsWith('/api/studio/projet?')) return reponse({ ok: true, projet });
      if (u.startsWith('/api/studio/references')) return reponse({ ok: true, references });
      return reponse({ ok: true, pics: [], duree_s: 10 });
    },
    getComputedStyle: () => ({ getPropertyValue: () => '' }), devicePixelRatio: 1,
    requestAnimationFrame: () => 1, cancelAnimationFrame() {}, setInterval: () => 0, setTimeout, clearTimeout,
  };
  bac.window.document = doc;
  vm.createContext(bac);
  vm.runInContext(CODE, bac);
  return { el: (id) => doc.getElementById(id), postes, projet };
}
const attendre = (ms) => new Promise(r => setTimeout(r, ms));

test('(14/11) la page : la voix de référence se choisit (auto, chaque voix, le profil gardé, aucune), les noms échappés', async () => {
  const P = page([{ nom: 'hakim', source: 'Moujahid — Voix de Hakim', t: 1 }]);
  await attendre(30);
  const html = P.el('mpReference').innerHTML;
  assert.match(html, /<option value="auto" selected>auto : la voix de Hakim du projet, sinon le profil gardé<\/option>/);
  assert.match(html, /<option value="piste:t4">la voix « Voix de &#60;Hakim&#62; »<\/option>/, 'les voix seulement, leurs noms échappés');
  assert.match(html, /<option value="piste:t5">/);
  assert.ok(!/piste:t1/.test(html), 'pas la batterie');
  assert.match(html, /<option value="profil">le profil gardé « hakim » \(Moujahid — Voix de Hakim\)<\/option>/);
  assert.match(html, /<option value="aucune">/);
  // un choix part avec la version vue ; « piste:t4 » devient { source: 'piste', piste: 't4' }
  P.el('mpReference').value = 'piste:t4';
  await Promise.all(P.el('mpReference')._ecouteurs.change.map(f => f({})));
  assert.deepEqual(P.postes.at(-1), ['/api/studio/projet/reference', { id: 'PJ1', rev: 1, source: 'piste', piste: 't4' }]);
  assert.match(P.el('mpReference').innerHTML, /<option value="piste:t4" selected>/, 'la page montre le nouveau choix');
  P.el('mpReference').value = 'aucune';
  await Promise.all(P.el('mpReference')._ecouteurs.change.map(f => f({})));
  assert.deepEqual(P.postes.at(-1)[1], { id: 'PJ1', rev: 2, source: 'aucune', piste: '' });
});

test('(14/11) la page : sans profil gardé, pas de choix « profil »', async () => {
  const P = page([]);
  await attendre(30);
  assert.ok(!/value="profil"/.test(P.el('mpReference').innerHTML));
});

test('(14/11) la page : par voix, « calée sur la voix de référence » (auto/oui/non) et « garder cette voix comme référence »', () => {
  const js = lire('public/studio-pistes.js'), h = lire('public/studio.html');
  assert.match(js, /choix\('pro\.reference', pro\.reference \|\| 'auto', \[\['auto', 'auto \(ta voix, s’il y a une référence\)'\], \['oui', 'oui'\], \['non', 'non'\]\]\)/);
  assert.match(js, /data-garder-ref="\$\{esc\(t\.id\)\}"/);
  assert.match(js, /poster\('\/api\/studio\/projet\/garder-reference', \{ id: s\.projet\.id, piste: d\.garderRef \}\)/);
  assert.match(h, /<select id="mpReference" aria-label="La voix de référence"><\/select>/);
  assert.match(h, /jamais ta hauteur ni ton timbre : ta voix reste la tienne/);
  // le texte venu du disque, toujours échappé (la règle de la page)
  const html = js.split('\n').filter(l => !/textContent =/.test(l)).join('\n');
  const nus = (html.match(/\$\{(?!esc\()[^{}]*\.(titre|texte|nom|f|id|couleur|role|erreur|mp3|source|piste)\}/g) || []).filter(x => !/\.id === /.test(x));
  assert.deepEqual(nus, []);
});
