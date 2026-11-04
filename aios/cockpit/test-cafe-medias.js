// (04/11, 19:40, Ahmed : « petite modification dans le café : je dois pouvoir envoyer un son, une image ou une vidéo, pour que toute la
// famille en profite ») le fichier est rangé dans l'atelier de Hakim (fichiers/cafe), où lui et ses agents peuvent le lire ; au café,
// une ligne le dit ([image : cafe/…]) et la page le montre
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const PAGE = fs.readFileSync(path.join(__dirname, 'public', 'cafe.html'), 'utf8');
const prendre = (src, nom) => { const i = src.indexOf(`function ${nom}(`); assert.ok(i >= 0, `${nom} existe`); return src.slice(i, src.indexOf('\n}\n', i) + 2); };
const ligne = (src, debut) => src.slice(src.indexOf(debut), src.indexOf('\n', src.indexOf(debut)));

test('le café reçoit une image, un son ou une vidéo, et rien d’autre', () => {
  const ctx = {};
  vm.createContext(ctx);
  vm.runInContext(ligne(SRC, 'const CAFE_TYPES = ') + '\n' + prendre(SRC, 'mediaDuCafe') + 'this.m = mediaDuCafe;', ctx);
  assert.deepStrictEqual({ ...ctx.m('image/jpeg') }, { genre: 'image', ext: 'jpg' });
  assert.deepStrictEqual({ ...ctx.m('audio/mpeg') }, { genre: 'son', ext: 'mp3' });
  assert.deepStrictEqual({ ...ctx.m('video/mp4; codecs=avc1') }, { genre: 'vidéo', ext: 'mp4' });
  assert.deepStrictEqual({ ...ctx.m('audio/x-m4a') }, { genre: 'son', ext: 'm4a' });
  for (const t of ['text/html', 'image/svg+xml', 'application/javascript', '', undefined]) assert.strictEqual(ctx.m(t), null, `${t} refusé`);
  assert.match(SRC, /const CAFE_MEDIAS = path\.join\(JARVIS_CWD, 'fichiers', 'cafe'\);/, 'dans son atelier : lui et ses agents peuvent le lire');
  assert.match(SRC, /const CAFE_MEDIA_MAX = 60 \* 1024 \* 1024;/);
});

test('les routes : déposer (jeton, type permis, taille), puis le café l’annonce ; relire (nom strict)', () => {
  const r = SRC.slice(SRC.indexOf("if (p === '/api/cafe/media' && req.method === 'POST') {"), SRC.indexOf("if (p === '/api/cafe' && req.method === 'POST') {"));
  assert.ok(r.length > 100, 'la route existe, avant celle du texte');
  assert.match(r, /if \(!jetonValide\(req\)\)/);
  assert.match(r, /const m = mediaDuCafe\(req\.headers\['content-type'\]\);/);
  assert.match(r, /await lireCorps\(req, CAFE_MEDIA_MAX\)/);
  assert.match(r, /crypto\.randomBytes\(6\)\.toString\('hex'\)/);
  assert.match(r, /\{ mode: 0o600 \}/);
  assert.match(r, /\[\$\{m\.genre\} : cafe\/\$\{nom\}\]/, 'au café : une ligne qui le dit');
  assert.match(r, /cafeEnAttente\.push\(/, 'Hakim prévient la famille, comme pour un texte');
  assert.match(r, /const NOM_MEDIA = \/\^\[0-9a-f\]\{12\}\\\.\(jpg\|png\|gif\|webp\|mp3\|m4a\|aac\|ogg\|wav\|weba\|mp4\|webm\|mov\)\$\/;/);
  assert.match(r, /fs\.createReadStream\(f\)\.pipe\(res\)/);
});

test('la page : joindre, envoyer avec ou sans texte, et montrer l’image, le son ou la vidéo au café', () => {
  assert.match(PAGE, /<input type="file" id="media" accept="image\/\*,audio\/\*,video\/\*" hidden>/);
  assert.match(PAGE, /<button id="joindre" type="button" aria-label="Joindre une image, un son ou une vidéo" title="Joindre une image, un son ou une vidéo">/);
  assert.match(PAGE, /fetch\('\/api\/cafe\/media', \{ method: 'POST'/);
  const ctx = { esc: (s) => String(s) };
  vm.createContext(ctx);
  const i = PAGE.indexOf('function avecMedias(');                     // (dans la page, ses fonctions sont indentées)
  vm.runInContext(PAGE.slice(i, PAGE.indexOf('\n  }\n', i) + 4) + 'this.a = avecMedias;', ctx);
  assert.strictEqual(ctx.a('Regardez ! [image : cafe/0123456789ab.jpg]'), 'Regardez ! <div class="media" data-nom="0123456789ab.jpg" data-genre="image">…</div>');
  assert.strictEqual(ctx.a('[son : cafe/0123456789ab.mp3]'), '<div class="media" data-nom="0123456789ab.mp3" data-genre="son">…</div>');
  assert.strictEqual(ctx.a('[image : cafe/../../x.jpg]'), '[image : cafe/../../x.jpg]', 'un nom douteux reste du texte');
});
