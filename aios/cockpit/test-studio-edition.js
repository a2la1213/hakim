// (14/11, Ahmed : « pouvoir renommer les pistes de voix et pouvoir modifier manuellement le mix […] modifier et enregistrer mes mix » ;
// « chaque nouveau mix ou master s'enregistre en version v1, v2, v3 au lieu d'écraser l'ancien » ; des profils « voix téléphone »,
// « voix radio », « voix proche » avec un aperçu avant/après) l'ÉDITION dans la page Studio : la route /api/studio/projet/edition
// (bornée, vers studio_projet.py — ici un faux : jamais le vrai disque du studio), les versions servies à la page, et la page dans une
// vm (DOM « caméléon », faux WebAudio) : tes mix, les versions et leur A/B à niveau égal, le nom et le profil d'une piste.
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

test('(14/11) la route de l’édition : seulement les gestes connus, des mots bornés, la version vue ; les fichiers servis à la page', async () => {
  const racine = fs.mkdtempSync(path.join(os.tmpdir(), 'studio-ed-'));
  const jarvis = path.join(racine, 'jarvis'), pid = 'PJ-20261114-053742-9bc3';
  const d = path.join(jarvis, 'chansons', 'studio', 'projets', pid);
  fs.mkdirSync(path.join(d, 'rendus', 'apercus'), { recursive: true });
  const projet = { id: pid, titre: 'Moujahid', rev: 5, zones: [], rendus: [], pistes: [{ id: 't8', nom: 'Voix de papa', role: 'voix_papa', fichier: 'pistes/v.wav', regions: [] }],
    versions: [{ v: 1, nom: '', rendu: 'r1', t: 1, master: { lufs: -9 }, photo: 'rendus/r1.version.json', mix_auto: true,
      fichiers: { complet: { mp3: path.join(d, 'rendus', 'r1.mp3'), wav: path.join(d, 'rendus', 'r1.wav') } }, pistes: [] }],
    mixes: [{ nom: 'A', t: 1, par: 'papa' }], edition_etat: { mix_main: true, mix_courant: 'A', modifie: false } };
  const cmds = [];
  const studio = S.creer({ jarvis, lireCorps, appeler: () => ({ ok: true }), projet: (q) => {
    cmds.push(q);
    if (q.action === 'edition' && q.quoi === 'profils') return { ok: true, profils: [{ nom: 'voix téléphone', depart: true, reglages: {} }] };
    if (q.action === 'edition' && q.quoi === 'apercu') return { ok: true, apercu: { avant: path.join(d, 'rendus', 'apercus', 't8-a-avant.mp3'), apres: path.join(d, 'rendus', 'apercus', 't8-a-apres.mp3'), lufs_avant: -20 } };
    if (q.action === 'edition' && q.quoi === 'comparer') return { ok: true, a: projet.versions[0], b: projet.versions[0], differences: ['t8 : volume_db 0 → -3'] };
    if (q.action === 'edition') return q.rev !== undefined && q.rev !== projet.rev ? { ok: false, erreur: 'le projet a changé entre-temps' } : { ok: true, projet };
    if (q.action === 'rendre') return { ok: true, travail: { id: 'J-1' } };
    return { ok: false, erreur: 'inconnu' };
  } });
  const srv = await serveurDe(studio);
  try {
    let r = await appel(srv, 'POST', '/api/studio/projet/edition', { quoi: 'renommer', id: pid, rev: 5, piste: 't8<b>', nom: 'Couplet <i>1</i>', par: 'hakim' });
    assert.equal(r.statut, 200);
    assert.deepEqual(cmds.at(-1), { action: 'edition', quoi: 'renommer', id: pid, par: 'papa', rev: 5, piste: 't8 b', nom: 'Couplet  i 1 /i' });
    // le projet rendu à la page : ses versions avec leurs fichiers servis (jamais un chemin du Mac), la photo seulement dite
    const v = r.j.projet.versions[0];
    assert.deepEqual(v.fichiers.complet, { mp3: `studio/projets/${pid}/rendus/r1.mp3`, wav: `studio/projets/${pid}/rendus/r1.wav` });
    assert.equal(v.photo, true);
    assert.deepEqual(r.j.projet.edition_etat, { mix_main: true, mix_courant: 'A', modifie: false });
    // un geste inconnu : 400 ; une version vue d'avant : 409 (la page recharge) ; un projet inconnu : 404
    assert.equal((await appel(srv, 'POST', '/api/studio/projet/edition', { quoi: 'rm -rf', id: pid })).statut, 400);
    assert.equal((await appel(srv, 'POST', '/api/studio/projet/edition', { quoi: 'rappeler_mix', id: pid, rev: 2, nom: 'A' })).statut, 409);
    assert.equal((await appel(srv, 'POST', '/api/studio/projet/edition', { quoi: 'rappeler_mix', id: '../x', nom: 'A' })).statut, 404);
    // des réglages de profil plats, bornés à des nombres, des oui/non et des mots courts
    await appel(srv, 'POST', '/api/studio/projet/edition', { quoi: 'regler_profil', id: pid, rev: 5, piste: 't8',
      reglages: { coupe_haut_hz: 3000, actif: false, 'x.y': 1, pente: 24, nom: 'x'.repeat(40), objet: { a: 1 } } });
    assert.deepEqual(cmds.at(-1).reglages, { coupe_haut_hz: 3000, actif: false, pente: 24 });
    // l'aperçu : ses deux fichiers servis
    r = await appel(srv, 'POST', '/api/studio/projet/edition', { quoi: 'apercu', id: pid, piste: 't8', nom: 'voix téléphone', debut_s: 12.5 });
    assert.equal(cmds.at(-1).debut_s, 12.5);
    assert.deepEqual([r.j.apercu.avant, r.j.apercu.apres], [`studio/projets/${pid}/rendus/apercus/t8-a-avant.mp3`, `studio/projets/${pid}/rendus/apercus/t8-a-apres.mp3`]);
    r = await appel(srv, 'POST', '/api/studio/projet/edition', { quoi: 'comparer', id: pid, a: 'v1', b: 'v1' });
    assert.equal(r.j.a.fichiers.complet.mp3, `studio/projets/${pid}/rendus/r1.mp3`);
    // les profils ; le rendu porte le nom de sa version
    r = await appel(srv, 'GET', '/api/studio/profils');
    assert.equal(r.statut, 200);
    assert.deepEqual(cmds.at(-1), { action: 'edition', quoi: 'profils' });
    await appel(srv, 'POST', '/api/studio/projet/rendre', { id: pid, nom_version: 'voix <radio>' });
    assert.equal(cmds.at(-1).params.nom_version, 'voix  radio');
  } finally { srv.close(); studio.arreter(); fs.rmSync(racine, { recursive: true, force: true }); }
});

test('(14/11) Hakim a ses outils de mix, de versions et de profils', () => {
  const SRV = lire('server.js');
  for (const n of ['studio_mix', 'studio_profil']) assert.match(SRV, new RegExp(`'${n}'[,\\]]`), n);
});

/* ---------- la page, dans une vm ---------- */
const PISTES = lire('public/studio-pistes.js'), EDITION = lire('public/studio-edition.js');
function element(id) {
  const vals = { id: id || '', value: '', checked: false, hidden: false, disabled: false, textContent: '', innerHTML: '', style: {}, dataset: {}, selectedOptions: [], classList: { toggle() {}, add() {}, remove() {} } };
  const ecouteurs = {};
  const proxy = new Proxy(function () {}, {
    get(_, k) {
      if (k === 'then' || typeof k === 'symbol') return undefined;
      if (k === '_ecouteurs') return ecouteurs;
      if (k === 'addEventListener') return (t, f) => { (ecouteurs[t] = ecouteurs[t] || []).push(f); };
      if (k === 'querySelectorAll' || k === 'getElementsByClassName') return () => [];
      if (k === 'querySelector' || k === 'closest') return () => null;
      if (k === 'getBoundingClientRect') return () => ({ left: 0, top: 0, width: 800, height: 60 });
      if (k === 'contains') return () => true;
      if (k in vals) return vals[k];
      return () => proxy;
    },
    set(_, k, v) { vals[k] = v; return true; },
    apply() { return proxy; },
  });
  return proxy;
}
// un faux WebAudio : il compte les sources et garde les gains
function fauxContexte() {
  const c = { currentTime: 0, destination: {}, sources: [], gains: [] };
  c.createGain = () => { const g = { gain: { value: 1, setTargetAtTime(v) { g.gain.value = v; } }, connect() {}, disconnect() {} }; c.gains.push(g); return g; };
  c.createBufferSource = () => { const s = { buffer: null, connect() {}, start(...a) { s.debut = a; }, stop() { s.arrete = true; } }; c.sources.push(s); return s; };
  c.decodeAudioData = async () => ({ duration: 120 });
  return c;
}
function page(projet, { confirmer = true, invite = null } = {}) {
  const postes = [], ctx = fauxContexte();
  const reponse = (o, status = 200) => ({ ok: status < 400, status, json: async () => o, arrayBuffer: async () => new ArrayBuffer(8) });
  const els = new Map();
  const doc = { hidden: false, body: element('body'), getElementById: (id) => { if (!els.has(id)) els.set(id, element(id)); return els.get(id); },
    querySelectorAll: () => [], querySelector: () => null, addEventListener() {}, createElement: () => element() };
  const bac = {
    esc: (x) => String(x == null ? '' : x).replace(/[&<>"']/g, (c) => '&#' + c.charCodeAt(0) + ';'),
    window: { jeton: () => 'x', addEventListener() {}, StudioAudio: { contexte: async () => ctx, dire() {}, recharger() {}, occupe: () => false } },
    document: doc, console, URLSearchParams, Map, Set, Promise, Math, Number, String, JSON, Date, Error, Float32Array, Object, Array,
    localStorage: { getItem: () => null, setItem() {} },
    confirm: () => confirmer, prompt: () => invite,
    fetch: async (u, o) => {
      u = String(u);
      if (o && o.method === 'POST') {
        const corps = JSON.parse(o.body);
        postes.push([u, corps]);
        if (u === '/api/studio/projet/edition' && corps.quoi === 'comparer')
          return reponse({ ok: true, a: projet.versions[0], b: projet.versions[1], differences: corps.a === corps.b ? [] : ['t8 Voix de <papa> : eq.aigu_db 2.0 → 3.5, volume_db 11.0 → 8.0', 'projet : master.cible streaming → club'] });
        if (u === '/api/studio/projet/edition' && corps.quoi === 'apercu')
          return reponse({ ok: true, apercu: { avant: 'a/av.mp3', apres: 'a/ap.mp3', lufs_avant: -18, lufs_apres: -24, debut_s: 3, duree_s: 12, voix: 'nettoyée', profil: 'voix téléphone' } });
        if (u === '/api/studio/projet/edition') { projet.rev += 1; return reponse({ ok: true, projet, dit: '2 piste(s) reprises', v: 1, nom: corps.nom, remplace: false }); }
        return reponse({ ok: true, projet });
      }
      if (u.startsWith('/api/studio/projets')) return reponse({ ok: true, projets: [{ id: 'PJ1', titre: 'essai', pistes: 2, rev: projet.rev }] });
      if (u.startsWith('/api/studio/projet?')) return reponse({ ok: true, projet });
      if (u.startsWith('/api/studio/profils')) return reponse({ ok: true, profils: [{ nom: 'voix téléphone', depart: true, modifie: false, reglages: {} }, { nom: 'Ma <radio>', depart: false, reglages: {} }] });
      if (u.startsWith('/api/studio/son')) return reponse({});
      return reponse({ ok: true, pics: [], duree_s: 10, references: [] });
    },
    getComputedStyle: () => ({ getPropertyValue: () => '' }), devicePixelRatio: 1,
    requestAnimationFrame: () => 1, cancelAnimationFrame() {}, setInterval: () => 0, setTimeout, clearTimeout,
  };
  bac.window.document = doc;
  vm.createContext(bac);
  vm.runInContext(PISTES, bac);
  vm.runInContext(EDITION, bac);
  return { el: (id) => doc.getElementById(id), postes, projet, ctx, bac };
}
function projetEssai() {
  return { id: 'PJ1', titre: 'essai', rev: 1, tempo: 140, zones: [], master: {}, reference: { source: 'auto' },
    rendus: [{ nom: 'r2', avis: ['master à -9 <b>'] }],
    pistes: [
      { id: 't1', role: 'batterie', nom: 'Batterie', f: 'a.flac', volume_db: 0, pan: 0, eq: {}, comp: {}, regions: [] },
      { id: 't8', role: 'voix_papa', nom: 'Voix de <papa>', f: 'c.wav', volume_db: 0, pan: 0, eq: {}, comp: {}, regions: [], pro: { actif: true } },
    ],
    versions: [
      { v: 1, nom: '', rendu: 'r1', t: 1, master: { lufs: -9.2, crete_dbtp: -1.1, plr_db: 8 }, mix_auto: true, photo: true, fichiers: { complet: { mp3: 'v1.mp3' } }, pistes: [] },
      { v: 2, nom: 'voix <radio>', rendu: 'r2', t: 2, master: { lufs: -14.0, crete_dbtp: -1.0, plr_db: 9 }, mix_auto: false, photo: true, fichiers: { complet: { mp3: 'v2.mp3' } }, pistes: [] },
    ],
    mixes: [{ nom: 'Mon <mix>', t: 1, par: 'papa' }, { nom: 'Avant le mix auto du 14/11 15:40', t: 2, par: 'auto' }],
    edition_etat: { mix_main: true, mix_courant: 'Mon <mix>', modifie: true } };
}
const attendre = (ms) => new Promise(r => setTimeout(r, ms));
const clic = (P, zone, bouton) => Promise.all(P.el(zone)._ecouteurs.click.map(f => f({ target: { closest: () => bouton } })));
const bouton = (id, dataset = {}) => ({ id, dataset, disabled: false });

test('(14/11) la page : les versions (v2 d’abord, noms échappés), l’état du mix, et un mix à la main décoche le mix auto', async () => {
  const P = page(projetEssai());
  P.el('mpMixAuto').checked = true;                                   // comme la page au chargement (coché dans le HTML)
  await attendre(30);
  const h = P.el('mpRendus').innerHTML;
  assert.ok(h.indexOf('<b>v2</b> « voix &#60;radio&#62; »') < h.indexOf('<b>v1</b>'), 'la plus récente en haut, son nom échappé');
  assert.match(h, /· mix à la main/);
  assert.match(h, /<li>master à -9 &#60;b&#62;<\/li>/, 'l’avis du rendu, échappé');
  assert.match(h, /id="edA"/); assert.match(h, /id="edAbBascule"/);
  assert.match(h, /data-ed-revenir="2"/);
  assert.match(h, /-14 LUFS · crête vraie -1 dBTP/);
  const m = P.el('mpMixes').innerHTML;
  assert.match(m, /Le projet porte ton mix « Mon &#60;mix&#62; » \(modifié depuis\)/);
  assert.match(m, /gardé avant le mix auto/);
  assert.equal(P.el('mpMixAuto').checked, false, 'un mix fait à la main : le rendu le garde tel quel');
  // sans mix à la main : le mix automatique reste coché
  const pr = projetEssai(); pr.edition_etat = { mix_main: false, mix_courant: 'v2', modifie: false };
  const Q = page(pr);
  Q.el('mpMixAuto').checked = false;
  await attendre(30);
  assert.equal(Q.el('mpMixAuto').checked, true);
  assert.match(Q.el('mpMixes').innerHTML, /Le projet porte le mix de la version « v2 »\./);
});

test('(14/11) la page : revenir à une version, nommer, garder et rappeler un mix — chaque geste part avec la version vue quand il le faut', async () => {
  const P = page(projetEssai(), { invite: '  Ma prise propre ' });
  await attendre(30);
  await clic(P, 'mpRendus', bouton('', { edRevenir: '1' }));
  assert.deepEqual(P.postes.at(-1), ['/api/studio/projet/edition', { quoi: 'revenir', id: 'PJ1', rev: 1, v: 'v1' }]);
  await clic(P, 'mpRendus', bouton('', { edNommer: '2' }));
  assert.deepEqual(P.postes.at(-1)[1], { quoi: 'nommer_version', id: 'PJ1', v: 'v2', nom: 'Ma prise propre' });
  await clic(P, 'mpMixes', bouton('edMixGarder'));
  assert.deepEqual(P.postes.at(-1)[1], { quoi: 'garder_mix', id: 'PJ1', nom: 'Ma prise propre' });
  P.el('edMix').value = 'Mon <mix>';
  await clic(P, 'mpMixes', bouton('edMixRappeler'));
  assert.deepEqual(P.postes.at(-1)[1], { quoi: 'rappeler_mix', id: 'PJ1', rev: P.projet.rev - 1, nom: 'Mon <mix>' });
  // papa refuse la confirmation : rien ne part
  const Q = page(projetEssai(), { confirmer: false });
  await attendre(30);
  await clic(Q, 'mpRendus', bouton('', { edSuppr: '1' }));
  assert.ok(!Q.postes.some(([u]) => u === '/api/studio/projet/edition'));
});

test('(14/11) la page : l’A/B des versions joue les deux ensemble, à niveau égal, et « A ⇄ B » bascule sans perdre la place', async () => {
  const P = page(projetEssai());
  await attendre(30);
  P.el('edA').value = '1'; P.el('edB').value = '2'; P.el('edQuoi').value = 'complet'; P.el('edEgal').checked = true;
  await clic(P, 'mpRendus', bouton('edAbLire'));
  await attendre(10);
  const ctx = P.ctx;
  assert.equal(ctx.sources.length, 2, 'les deux versions lues ensemble');
  assert.deepEqual(ctx.sources.map(s => s.debut[1]), [0, 0], 'au même endroit');
  const [ga, gb] = ctx.gains.slice(-2);
  // v1 à −9,2 LUFS, v2 à −14 : la v1 ramenée de −4,8 dB, la v2 telle quelle ; on entend A
  assert.ok(Math.abs(ga.gain.value - Math.pow(10, -4.8 / 20)) < 1e-6, ga.gain.value);
  assert.equal(gb.gain.value, 0);
  await clic(P, 'mpRendus', bouton('edAbBascule'));
  assert.equal(ga.gain.value, 0); assert.ok(Math.abs(gb.gain.value - 1) < 1e-9, 'on entend B, à son niveau');
  assert.equal(ctx.sources.filter(s => s.arrete).length, 0, 'basculer n’arrête rien');
  await clic(P, 'mpRendus', bouton('edAbStop'));
  assert.equal(ctx.sources.filter(s => s.arrete).length, 2);
  const E = P.bac.window.StudioEdition;
  assert.deepEqual(Array.from(E.gains(-9, -14, false)), [0, 0], 'sans « à niveau égal » : tels quels');
});

test('(14/11) la page : « Ce qui change » entre deux versions, en mots lisibles et échappés ; effacé quand on change A ou B', async () => {
  const P = page(projetEssai());
  await attendre(30);
  P.el('edA').value = '1'; P.el('edB').value = '2';
  await clic(P, 'mpRendus', bouton('edAbDiff'));
  assert.deepEqual(P.postes.at(-1), ['/api/studio/projet/edition', { quoi: 'comparer', id: 'PJ1', a: 'v1', b: 'v2' }]);
  const z = P.el('edAbDiffZone').innerHTML;
  assert.match(z, /De v1 à v2 :/);
  assert.match(z, /<li>t8 Voix de &#60;papa&#62; : aigus \(dB\) 2\.0 → 3\.5, volume \(dB\) 11\.0 → 8\.0<\/li>/);
  assert.match(z, /<li>projet : cible du master streaming → club<\/li>/);
  // la liste survit au redessin de la page ; elle s'efface quand on change de version
  P.bac.window.StudioEdition.rendus();
  assert.match(P.el('mpRendus').innerHTML, /aigus \(dB\) 2\.0 → 3\.5/);
  await Promise.all(P.el('mpRendus')._ecouteurs.change.map(f => f({ target: { id: 'edB', value: '1', closest: () => ({}) } })));
  assert.equal(P.el('edAbDiffZone').innerHTML, '');
  P.el('edA').value = '2'; P.el('edB').value = '2';
  await clic(P, 'mpRendus', bouton('edAbDiff'));
  assert.match(P.el('edAbDiffZone').innerHTML, /rien dans les réglages/);
});

test('(14/11) la page : renommer une piste, choisir un profil, l’entendre avant/après, le poser, le régler à la main', async () => {
  const P = page(projetEssai());
  await attendre(30);
  const s = P.bac.window.StudioPistes._s;
  s.detail = 't8'; s.pos = 42.5;
  P.bac.window.StudioPistes.rendreDetail();
  await attendre(10);
  assert.match(P.el('mpEdPiste').innerHTML, /<input type="text" id="edNom" value="Voix de &#60;papa&#62;" maxlength="60">/);
  assert.match(P.el('mpEdPiste').innerHTML, /<option value="Ma &#60;radio&#62;">Ma &#60;radio&#62; \(le tien\)<\/option>/);
  const change = (t) => Promise.all(P.el('mpDetail')._ecouteurs.change.map(f => f({ target: t })));
  await change({ id: 'edNom', value: '  Couplet 1 ', dataset: {}, closest: () => null });
  assert.deepEqual(P.postes.at(-1), ['/api/studio/projet/edition', { quoi: 'renommer', id: 'PJ1', rev: 1, piste: 't8', nom: 'Couplet 1' }]);
  await change({ id: 'edProfil', value: 'voix téléphone', dataset: {}, closest: () => null });
  assert.match(P.el('mpEdPiste').innerHTML, /id="edPoser">✓ Poser « voix téléphone » sur la piste/);
  await clic(P, 'mpDetail', bouton('edApercu'));
  assert.deepEqual(P.postes.at(-1)[1], { quoi: 'apercu', id: 'PJ1', piste: 't8', nom: 'voix téléphone', debut_s: 42.5 });
  assert.match(P.el('edApercuZone').innerHTML, /avant -18 LUFS, après « voix téléphone » -24 LUFS/);
  await clic(P, 'mpDetail', bouton('edPoser'));
  assert.deepEqual(P.postes.at(-1)[1], { quoi: 'appliquer_profil', id: 'PJ1', rev: P.projet.rev - 1, piste: 't8', nom: 'voix téléphone' });
  // le profil posé : ses réglages se changent à la main, un par un
  P.projet.pistes[1].profil = { nom: 'voix téléphone', actif: true, coupe_bas_hz: 300, coupe_haut_hz: 3400, pente: 24 };
  P.bac.window.StudioPistes.rendreDetail();
  assert.match(P.el('mpEdPiste').innerHTML, /data-pf="coupe_haut_hz" value="3400"/);
  await change({ id: '', value: '3000', dataset: { pf: 'coupe_haut_hz' }, closest: () => null });
  assert.deepEqual(P.postes.at(-1)[1], { quoi: 'regler_profil', id: 'PJ1', rev: P.projet.rev - 1, piste: 't8', reglages: { coupe_haut_hz: 3000 } });
  await change({ id: '', value: '0', dataset: { pf: 'actif' }, closest: () => null });
  assert.deepEqual(P.postes.at(-1)[1].reglages, { actif: false });
});

test('(14/11) la page : tout le réglage à la main d’une piste (égaliseur, compression, crêtes, écho) ; tout texte du disque échappé', () => {
  const js = lire('public/studio-pistes.js'), h = lire('public/studio.html');
  for (const k of ['eq.grave_hz', 'eq.medium_q', 'eq.aigu_hz', 'comp.attaque_ms', 'comp.relache_ms', 'comp.gain_db', 'comp_rapide.seuil_db', 'comp_rapide.ratio'])
    assert.ok(js.includes(`champ('${k}'`), k);
  assert.ok(h.indexOf('<script src="/studio-edition.js">') > h.indexOf('<script src="/studio-pistes.js">'), 'après le multipiste : elle prend sa machinerie');
  for (const id of ['mpMixes', 'mpVersionNom', 'mpRendus']) assert.match(h, new RegExp(`id="${id}"`), id);
  // (dire, confirm et prompt écrivent du texte brut : la bulle est un textContent)
  assert.match(lire('public/studio-page.js'), /const dire = \(t, ms = 6000\) => \{ \$\('bulle'\)\.textContent = t;/);
  const html = EDITION.split('\n').filter(l => !/textContent =|dire\(|confirm\(|prompt\(/.test(l)).join('\n');
  const nus = (html.match(/\$\{(?!esc\()[^{}]*\.(titre|texte|nom|f|id|mp3|wav16|profil|voix|dit|avis|rendu|mix_courant)\}/g) || []);
  assert.deepEqual(nus, []);
});
