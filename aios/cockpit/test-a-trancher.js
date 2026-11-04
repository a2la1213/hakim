// (04/11, 15:45, Ahmed : « je ne vois pas ses signalements ; il faut que ça fasse la même chose que quand il m'envoie un fichier : ça doit
// s'afficher dans la conv, quel que soit le mode ») ce qui attend ton geste (un signalement, un anticorps, une mission, une écriture…)
// s'affiche toujours, même en Conversation avec l'épissage, même en Télépathie
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const PAGE = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const ligne = (debut) => { const i = PAGE.indexOf(debut); return PAGE.slice(i, PAGE.indexOf('\n', i)).replace(/^const /, 'var '); };
const prendre = (nom) => { const i = PAGE.indexOf(`function ${nom}(`); return PAGE.slice(i, PAGE.indexOf('\n}\n', i) + 2); };

test('ce qui attend ton geste s’affiche dans tous les modes ; sa réponse, elle, reste cachée avec l’épissage', () => {
  const ctx = vm.createContext({ Number, Date, Set,
    etat: { conversation: { debut: 0 }, reglages: { sesParoles: true } },
    reglagesCorps: { epissage: true, afficher_papa: true, afficher_hakim: true } });
  vm.runInContext([ligne('const enTelepathie = '), ligne('const parolesVisibles = '), ligne('const reponseCachee = '), ligne('const voixEpissee = '),
    prendre('messageMasque')].join('\n') + '\nthis.masque = messageMasque;', ctx);
  const t = Date.now();
  assert.strictEqual(ctx.masque({ qui: 'j', texte: 'Oui papa', ts: t }), true, 'sa réponse complète : cachée (épissage)');
  for (const spontane of ['signalement', 'anticorps', 'mission', 'ecriture', 'regle', 'carnet', 'retractation', 'identite', 'sortie', 'membre', 'promotion']) {
    assert.strictEqual(ctx.masque({ qui: 'j', spontane, texte: 'x', ts: t }), false, `${spontane} : affiché`);
  }
  ctx.reglagesCorps.afficher_papa = false; ctx.reglagesCorps.afficher_hakim = false;   // Télépathie
  assert.strictEqual(ctx.masque({ qui: 'j', spontane: 'signalement', texte: 'x', ts: t }), false, 'même en Télépathie');
  assert.strictEqual(ctx.masque({ qui: 'j', spontane: 'signalement', texte: 'x', ts: t, cache: true }), false, 'même « dans sa tête »');
});
