/* (30/10, Hakim, accord d'Ahmed) son atelier : la vraie limite est 10 Go depuis le 21/10 (anamnese/jarvis/terminal.py,
   ATELIER_MAX_KO), mais le cockpit lui disait encore « sur 5 Go » dès 4 Go. Il le dit comme le terminal : dès 8 Go, sur 10.
   node --test test-atelier.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const corps = src.slice(src.indexOf('function blocAtelier()'), src.indexOf('\n}\n', src.indexOf('function blocAtelier()')) + 3);

function bloc(ko) {
  const ctx = { atelierKo: ko };
  vm.createContext(ctx);
  vm.runInContext(corps + '\nthis.r = blocAtelier();', ctx);
  return ctx.r;
}

test('(10/11, 20 Go) rien sous 16 Go, puis « sur 20 Go »', () => {
  assert.equal(bloc(4.3 * 1048576), '');
  assert.equal(bloc(15.9 * 1048576), '');
  assert.match(bloc(16.4 * 1048576), /16,4 Go sur 20 Go/);
  assert.doesNotMatch(src, /Go sur (5|10) Go/);
});
