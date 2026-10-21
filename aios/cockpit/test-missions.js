/* Missions : où une mission peut écrire (audit du cockpit, C-H5, 2026-10-20). Lancer : node test-missions.js
   - jamais dans un dossier que launchd exécute (ses programmes, et les dossiers que ses scripts nomment) ;
   - jamais, même dans le projet, dans .git, .claude, .vscode, .husky, .github, .envrc… (Edit/Write ET commandes).
   Le comportement réel de Claude Code (refus d'Edit/Write et du bac à sable, y compris par un lien ou un renommage)
   a été sondé à la main le 2026-10-20 ; ici, la logique du cockpit. */
'use strict';
const assert = require('assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { Missions, refusEcriture, projetPermis, CACHES } = require('./missions.js');

const maison = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'missions-')));
const d = (...x) => { const p = path.join(maison, ...x); fs.mkdirSync(p, { recursive: true }); return p; };
['Desktop/lance/src', 'Desktop/libre', 'Desktop/anamnese', 'AIOS/bin', 'AIOS/outils', 'Library/LaunchAgents'].forEach(x => d(x));
fs.writeFileSync(path.join(maison, 'AIOS/bin/tache.sh'), '#!/bin/bash\ncd "$HOME/Desktop/lance" && ./run.sh >> ~/Desktop/.\n', { mode: 0o755 });
fs.writeFileSync(path.join(maison, 'Library/LaunchAgents/com.essai.plist'), `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict><key>Label</key><string>com.essai</string>
<key>ProgramArguments</key><array><string>/bin/bash</string><string>${maison}/AIOS/bin/tache.sh</string></array></dict></plist>`);

let ok = 0;
const vrai = (c, m) => { assert.ok(c, m); ok++; };

vrai(/launchd : AIOS\/bin/.test(refusEcriture(path.join(maison, 'AIOS/bin'), maison) || ''), 'le dossier du script lancé');
vrai(/launchd : Desktop\/lance/.test(refusEcriture(path.join(maison, 'Desktop/lance'), maison) || ''), 'le dossier que le script nomme');
vrai(/launchd/.test(refusEcriture(path.join(maison, 'Desktop/lance/src'), maison) || ''), 'un sous-dossier');
vrai(refusEcriture(path.join(maison, 'Desktop/libre'), maison) === null, 'un projet ordinaire');
vrai(refusEcriture(path.join(maison, 'AIOS/outils'), maison) === null, 'un autre dossier de ~/AIOS');
vrai(/Anamnèse/.test(refusEcriture(path.join(maison, 'Desktop/anamnese'), maison) || ''), 'son propre code');
vrai(projetPermis(path.join(maison, 'Desktop/libre'), maison) === path.join(maison, 'Desktop/libre'), 'projet permis');

// (relecture Opus) formes courantes : bash -c "cd DIR && …", "$HOME"/x, script sans #!, script appelé par un script ;
// un plist illisible fait refuser l'écriture
const maison2 = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'missions2-')));
const d2 = (...x) => { const p = path.join(maison2, ...x); fs.mkdirSync(p, { recursive: true }); return p; };
['Desktop/cdc', 'Desktop/guille', 'Desktop/sansdiese', 'Desktop/niveau2', 'Desktop/libre', 'AIOS/bin', 'Library/LaunchAgents'].forEach(x => d2(x));
fs.writeFileSync(path.join(maison2, 'AIOS/bin/a.sh'), 'cd "$HOME"/Desktop/guille && ./b.sh\n' + `${maison2}/AIOS/bin/b.sh\n`, { mode: 0o755 });
fs.writeFileSync(path.join(maison2, 'AIOS/bin/b.sh'), '#!/bin/sh\ncd ~/Desktop/niveau2 && make\n', { mode: 0o755 });
fs.writeFileSync(path.join(maison2, 'Desktop/sansdiese/run.sh'), 'echo pas de diese\n');
const plist = (label, args) => `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict><key>Label</key><string>${label}</string><key>ProgramArguments</key><array>${args.map(a => `<string>${a}</string>`).join('')}</array></dict></plist>`;
fs.writeFileSync(path.join(maison2, 'Library/LaunchAgents/a.plist'), plist('a', ['/bin/bash', '-c', `cd ${maison2}/Desktop/cdc &amp;&amp; ./x`]));
fs.writeFileSync(path.join(maison2, 'Library/LaunchAgents/b.plist'), plist('b', ['/bin/sh', `${maison2}/AIOS/bin/a.sh`]));
fs.writeFileSync(path.join(maison2, 'Library/LaunchAgents/c.plist'), plist('c', ['/bin/sh', `${maison2}/Desktop/sansdiese/run.sh`]));
for (const x of ['Desktop/cdc', 'Desktop/guille', 'Desktop/sansdiese', 'Desktop/niveau2'])
  vrai(/launchd/.test(refusEcriture(path.join(maison2, x), maison2) || ''), `détecté : ${x}`);
vrai(refusEcriture(path.join(maison2, 'Desktop/libre'), maison2) === null, 'projet libre');
fs.writeFileSync(path.join(maison2, 'Library/LaunchAgents/z.plist'), 'pas un plist');
require('./missions.js').viderCacheLaunchd();
vrai(/illisible/.test(refusEcriture(path.join(maison2, 'Desktop/libre'), maison2) || ''), 'plist illisible : refus par prudence');
fs.rmSync(maison2, { recursive: true, force: true });

const M = new Missions({ dossier: d('fiches'), donnees: d('donnees'), claude: 'claude', maison });
const projet = path.join(maison, 'Desktop/libre');
const ecrit = M.arguments({ titre: 'x', consigne: 'x', modele: 'sonnet', projet, ecriture: true });
const refus = ecrit[ecrit.indexOf('--disallowedTools') + 1].split(',');
for (const c of ['.git', '.claude', '.vscode', '.husky', '.envrc', '.github'])
  vrai(refus.includes(`Edit(/${projet}/${c}/**)`) && refus.includes(`Edit(/${projet}/**/${c}/**)`) && refus.includes(`Edit(/${projet}/${c})`), `Edit refusé : ${c}`);
const bac = JSON.parse(ecrit[ecrit.indexOf('--settings') + 1]).sandbox;
vrai(bac.filesystem.denyWrite.includes(path.join(projet, '.git')) && bac.filesystem.denyWrite.includes(path.join(projet, '**', '.git')), 'bac à sable : .git refusé');
vrai(bac.filesystem.denyWrite.length === CACHES.length * 2, 'bac à sable : tous les dossiers cachés refusés');
vrai(bac.allowUnsandboxedCommands === false && bac.failIfUnavailable === true, 'pas d’échappatoire');
const lit = M.arguments({ titre: 'x', consigne: 'x', modele: 'sonnet', projet, ecriture: false });
vrai(lit[lit.indexOf('--tools') + 1] === 'Read,Grep,Glob', 'lecture seule : ni Edit ni Bash');

fs.rmSync(maison, { recursive: true, force: true });
console.log(`test-missions : ${ok} vérifications, TOUT VERT`);
