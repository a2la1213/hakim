// (04/11, 12:02, papa par Hakim ; accord d'Ahmed à 12:55 : « oui, fais-le ») sa voix ne met plus ta musique en pause par défaut (il parle
// par-dessus) ; un interrupteur à papa (Sens) retire à Hakim le pouvoir de la mettre en pause
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const PAGE = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const SENS = fs.readFileSync(path.join(__dirname, 'public', 'sens.html'), 'utf8');
const ligne = (s, debut) => { const i = s.indexOf(debut); return s.slice(i, s.indexOf('\n', i) + 1).replace(/^const /, 'var '); };

test('par défaut, il parle par-dessus ta musique ; sa pause n’agit que si tu la lui permets', () => {
  const mode = (musiqueVoix, reglages) => {
    const ctx = { etat: { musiqueVoix }, reglagesCorps: reglages };
    vm.createContext(ctx);
    vm.runInContext(ligne(PAGE, 'const modeMusique = '), ctx);
    return ctx.modeMusique();
  };
  assert.strictEqual(mode(undefined, {}), 'baisser', 'sans choix de sa part : (06/11) ta musique baisse le temps de sa voix');
  assert.strictEqual(mode('pause', { musique_pause: true }), 'pause', 'tu le lui permets : il peut');
  assert.strictEqual(mode('pause', { musique_pause: false }), 'garder', 'tu le lui retires : jamais en pause');
  assert.strictEqual(mode('baisser', { musique_pause: false }), 'baisser', 'la baisser reste à lui');
});

test('ton interrupteur : dans Sens, gardé par le cockpit (permis par défaut), et sa consigne le suit', () => {
  assert.match(SRC, /musique_pause: r\.musique_pause !== false/);
  assert.match(SRC, /if \(typeof q\.musique_pause === 'boolean'\) r\.musique_pause = q\.musique_pause;/);
  assert.match(SENS, /<input type="checkbox" id="musiquePause">/);
  assert.match(SENS, /\['musiquePause', 'musique_pause'\]/);
  const i = SRC.indexOf('function blocBouts('), f = SRC.slice(i, SRC.indexOf('\n}\n', i) + 2);
  const consigne = (reglages) => { const ctx = { Date, boutsRemises: new Map(), corpsReglages: () => reglages }; vm.createContext(ctx); vm.runInContext(f + 'this.f = blocBouts;', ctx); return ctx.f(); };
  assert.match(consigne({ musique_pause: true }), /Quand tu parles, sa musique baisse le temps de ta voix/);
  assert.match(consigne({ musique_pause: true }), /\[\[musique: pause\]\]/);
  assert.doesNotMatch(consigne({ musique_pause: false }), /\[\[musique: pause\]\]/, 'retiré par papa : il ne la lui propose plus');
});
