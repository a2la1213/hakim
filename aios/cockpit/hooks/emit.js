#!/usr/bin/env node
/* Émetteur de hook : normalise l'évènement reçu sur stdin et l'ajoute à events.jsonl.
   Règle d'or : ne JAMAIS bloquer ni faire échouer l'outil → toujours exit 0, rapide. */
const fs = require('fs'), path = require('path'), os = require('os');
const EVENTS = path.join(os.homedir(), 'AIOS', 'cockpit', 'data', 'events.jsonl');
const type = process.argv[2] || 'event';
let raw = '';
process.stdin.on('data', d => raw += d);
process.stdin.on('error', () => process.exit(0));
process.stdin.on('end', () => {
  let o = {}; try { o = JSON.parse(raw || '{}'); } catch (_) {}
  const ev = { ts: Date.now() / 1000, type, session: (o.session_id || '').slice(0, 8) };
  if (o.tool_name) ev.tool = o.tool_name;
  const ti = o.tool_input || {};
  let s = ti.command || ti.file_path || ti.pattern || ti.description || ti.prompt || ti.query || o.prompt || '';
  // (audit du cockpit, C-M7) une commande ou un prompt peut porter un secret : masqué avant d'être écrit (mêmes
  // règles que les comptes rendus de missions), et le fichier n'est lisible que par Ahmed
  if (typeof s === 'string' && s) { try { s = require(path.join(__dirname, '..', 'missions.js')).masquer(s); } catch (_) { s = '(masqué)'; } ev.summary = s.slice(0, 140); }
  try { fs.appendFileSync(EVENTS, JSON.stringify(ev) + '\n', { mode: 0o600 }); } catch (_) {}
  process.exit(0);
});
setTimeout(() => process.exit(0), 1500); // failsafe
