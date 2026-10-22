/* Les écritures de Hakim dans les projets d'Ahmed (2026-10-22) : node --test test-ecritures.js
   Une vraie maison temporaire avec un vrai dépôt git ; rien ne touche aux vrais projets. */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const { Ecritures } = require('./ecritures.js');

function maison() {
  const m = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'maison-')));
  const projet = path.join(m, 'Desktop', 'projet');
  fs.mkdirSync(path.join(m, 'Library', 'LaunchAgents'), { recursive: true });
  fs.mkdirSync(path.join(projet, 'src'), { recursive: true });
  fs.writeFileSync(path.join(projet, 'src', 'a.js'), "const salut = 'bonjour';\nmodule.exports = salut;\n");
  const g = (...a) => execFileSync('git', ['-C', projet, ...a], { stdio: 'ignore' });
  g('init', '-q'); g('-c', 'user.email=a@b', '-c', 'user.name=Ahmed', 'add', '.'); g('-c', 'user.email=a@b', '-c', 'user.name=Ahmed', 'commit', '-qm', 'départ');
  execFileSync('git', ['-C', projet, 'config', 'user.email', 'a@b']); execFileSync('git', ['-C', projet, 'config', 'user.name', 'Ahmed']);
  const dossier = path.join(m, 'AIOS', 'jarvis', 'ecritures');
  fs.mkdirSync(dossier, { recursive: true });
  const evts = [];
  const E = new Ecritures({ dossier, donnees: path.join(m, 'AIOS', 'jarvis', 'ecritures-cockpit'), maison: m, evenement: (etat, e) => evts.push(etat) });
  const deposer = (id, f) => { fs.writeFileSync(path.join(dossier, `${id}.json`), JSON.stringify(f)); E.scruter(); return E.ecritures[id]; };
  return { m, projet, E, deposer, evts, log: () => execFileSync('git', ['-C', projet, 'log', '--format=%s'], { encoding: 'utf8' }) };
}

test('proposée, appliquée d’un geste en commit à part, puis annulée par un revert', () => {
  const x = maison();
  const e = x.deposer('E-20261022-101500-ab12', { projet: '~/Desktop/projet', fichier: 'src/a.js', ancien: "'bonjour'", nouveau: "'salam'", raison: 'saluer en arabe' });
  assert.strictEqual(e.etat, 'proposee');
  assert.throws(() => x.E.trancher(e.id, 'appliquer', 'mauvaise'), /a changé/);
  x.E.trancher(e.id, 'appliquer', e.empreinte);
  assert.strictEqual(e.etat, 'appliquee');
  assert.match(fs.readFileSync(path.join(x.projet, 'src', 'a.js'), 'utf8'), /'salam'/);
  assert.match(x.log(), /^Hakim : saluer en arabe \(validé par Ahmed\)/);
  x.E.trancher(e.id, 'annuler');
  assert.strictEqual(e.etat, 'annulee');
  assert.match(fs.readFileSync(path.join(x.projet, 'src', 'a.js'), 'utf8'), /'bonjour'/);
  assert.deepStrictEqual(x.evts, ['proposee', 'appliquee', 'annulee']);
});

test('refusées par le cockpit : hors projet, chemin protégé, texte absent ou en double, lien, pas de git', () => {
  const x = maison();
  fs.writeFileSync(path.join(x.projet, 'src', 'b.js'), 'x x');
  fs.symlinkSync('/etc/hosts', path.join(x.projet, 'src', 'lien.js'));
  const cas = [
    [{ projet: '/etc', fichier: 'hosts', ancien: 'a', nouveau: 'b' }, /hors des projets|introuvable/],
    [{ projet: x.projet, fichier: '.git/config', ancien: 'a', nouveau: 'b' }, /protégé/],
    [{ projet: x.projet, fichier: '../../x.js', ancien: '', nouveau: 'b' }, /invalide/],
    [{ projet: x.projet, fichier: 'src/a.js', ancien: 'absent', nouveau: 'b' }, /introuvable/],
    [{ projet: x.projet, fichier: 'src/b.js', ancien: 'x', nouveau: 'y' }, /2 fois/],
    [{ projet: x.projet, fichier: 'src/lien.js', ancien: 'a', nouveau: 'b' }, /lien/],
    [{ projet: x.projet, fichier: 'src/a.js', ancien: '', nouveau: 'écrasé' }, /existe déjà/],
  ];
  cas.forEach(([f, motif], k) => {
    const e = x.deposer(`E-20261022-1016${String(k).padStart(2, '0')}-cd34`, f);
    assert.strictEqual(e.etat, 'invalide', JSON.stringify(f));
    assert.match(e.raison_refus, motif);
  });
});

test('un fichier modifié à la main entre-temps : rien n’est écrit ; un fichier neuf, oui', () => {
  const x = maison();
  const e = x.deposer('E-20261022-101700-ef56', { projet: x.projet, fichier: 'src/a.js', ancien: "'bonjour'", nouveau: "'salut'", raison: 'r' });
  fs.appendFileSync(path.join(x.projet, 'src', 'a.js'), '// Ahmed écrit ici\n');
  assert.throws(() => x.E.trancher(e.id, 'appliquer', e.empreinte), /modifications en cours/);
  assert.match(fs.readFileSync(path.join(x.projet, 'src', 'a.js'), 'utf8'), /'bonjour'/);
  const n = x.deposer('E-20261022-101800-0a0b', { projet: x.projet, fichier: 'src/neuf.md', ancien: '', nouveau: '# Neuf\n', raison: 'note' });
  x.E.trancher(n.id, 'appliquer', n.empreinte);
  assert.strictEqual(fs.readFileSync(path.join(x.projet, 'src', 'neuf.md'), 'utf8'), '# Neuf\n');
  assert.match(x.log(), /^Hakim : note/);
});
