/* (09/11, Ahmed : « tout ce qui arrive de ses sens traité en temps réel, parallélisé, comme sa parole » ; 19:29-19:32 : « que tu dissocies
   ce que disent les autres de mes paroles » ; « reconnaître les signatures vocales en temps réel pendant le live, et pouvoir les enregistrer
   à la volée ») le client de L'OREILLE DES VOIX (jarvis/oreille_voix.py) : un petit processus qui ne fait que reconnaître qui parle
   (l'empreinte WeSpeaker sur le processeur, aucun Whisper, ~140 Mo mesurés), à côté de la transcription et jamais derrière elle.
   Un seul point d'entrée (demander), un processus lancé au premier besoin et relancé s'il tombe ; une ligne JSON par demande.
   Les demandes de papa (priorite) passent toujours ; les autres (le son du téléphone) sont laissées quand trois attendent déjà.
   Module sans état global : server.js le crée (creer) et le teste en lui donnant un faux spawn. */
'use strict';

function creer({ spawn, python, script, env = process.env, delaiMs = 4000, enAttenteMax = 3, journal = () => {} }) {
  const o = { proc: null, pret: false, tampon: '', ids: 0, attente: new Map(), lances: 0 };
  function lancer() {
    if (o.proc) return;
    let p;
    try { p = spawn(python, ['-B', '-W', 'ignore', script], { stdio: ['pipe', 'pipe', 'ignore'], env }); } catch (_) { return; }
    o.proc = p; o.pret = false; o.tampon = ''; o.lances++;
    p.stdout.on('data', (d) => {
      o.tampon += d;
      let i;
      while ((i = o.tampon.indexOf('\n')) >= 0) {
        const l = o.tampon.slice(0, i); o.tampon = o.tampon.slice(i + 1);
        let x; try { x = JSON.parse(l); } catch (_) { continue; }
        if (x.pret) { o.pret = true; continue; }
        const a = o.attente.get(x.id);
        if (!a) continue;
        o.attente.delete(x.id); clearTimeout(a.minuteur);
        a.resoudre({ ...x, attente_ms: Date.now() - a.t });
      }
    });
    const fin = () => {
      if (o.proc !== p) return;
      o.proc = null; o.pret = false;
      for (const [, a] of o.attente) { clearTimeout(a.minuteur); a.resoudre({ erreur: 'oreille des voix arrêtée' }); }
      o.attente.clear();
    };
    p.on('exit', fin); p.on('error', fin);
    if (p.stdin && p.stdin.on) p.stdin.on('error', () => {});
  }
  // une demande : { op, fichier, … } ; rend toujours (jamais d'exception) : la réponse, ou { occupee } / { erreur }
  function demander(d, { priorite = false, delai = delaiMs } = {}) {
    return new Promise((resoudre) => {
      lancer();
      if (!o.proc) return resoudre({ erreur: 'oreille des voix injoignable' });
      if (!priorite && o.attente.size >= enAttenteMax) return resoudre({ occupee: true });
      const id = ++o.ids, t = Date.now();
      const minuteur = setTimeout(() => {
        if (!o.attente.has(id)) return;
        o.attente.delete(id); resoudre({ erreur: 'trop lente', ms: Date.now() - t });
        journal({ e: 'oreille_voix_lente', op: d && d.op, ms: Date.now() - t });
      }, delai);
      if (minuteur.unref) minuteur.unref();
      o.attente.set(id, { resoudre, minuteur, t });
      try { o.proc.stdin.write(JSON.stringify({ id, ...d }) + '\n'); }
      catch (_) { o.attente.delete(id); clearTimeout(minuteur); resoudre({ erreur: 'oreille des voix injoignable' }); }
    });
  }
  // arrêt par l'objet du processus (son PID), jamais par motif
  function arreter() { const p = o.proc; o.proc = null; o.pret = false; if (p) { try { p.kill('SIGTERM'); } catch (_) {} } }
  return { demander, lancer, arreter, etat: () => ({ pret: o.pret, vivant: !!o.proc, enAttente: o.attente.size, lances: o.lances }) };
}

module.exports = { creer };
