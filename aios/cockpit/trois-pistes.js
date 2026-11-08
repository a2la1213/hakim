/* (06/11, 09:27, Ahmed : « faut que toutes ses mesures et découpes (voix + musique, ou voix + background) soient automatiquement processées
   par le subconscient, et que le signal soit envoyé à Hakim processé et net, pour parole, musique ou background, avec les mots exacts en
   temps réel d'apparition, et la piste de musique ou de background calée dessus » ; Hakim : « il me manque la transcription mot à mot
   horodatée de la voix séparée de la musique, et la musique (tempo, accords, sections) calée dessus ») LES TROIS PISTES.

   Pour chaque source (le téléphone, dedans ; le micro, autour), une ligne du temps à la seconde :
   - la PAROLE : les mots exacts, chacun à son instant (ils restent dans le fil du cockpit, sources papa / telephone) ;
   - la MUSIQUE : tempo, tonalité, accords et leurs changements, sections (A, B, retour de A), intensité ;
   - le FOND : ce qui n'est ni parole ni musique (la pièce, un souffle, un bruit sourd, des chocs, une voix lointaine).
   Les cellules d'une seconde viennent de la séparation (Demucs, jarvis/separation.py : « pistes ») et, entre deux séparations, de
   l'analyse légère des trames (analyseMusicale) ; les notes brutes de la voix (« Ré4 296 Hz 0,1 s ») ne sortent plus telles quelles :
   elles sont résumées (resumeNotes). Rien de l'audio n'est gardé ici, seulement ces nombres, 15 min au plus.
   Module pur (sans dépendance) : server.js le nourrit et lit son texte (blocTroisPistes, resumeCourant). */
'use strict';

const DUREE_MS = 15 * 60e3;
const SOURCES = { telephone: 'Le téléphone (dedans)', micro: 'Autour (le micro)' };
const INSTRUMENTS = { bass: 'basse', drums: 'batterie', guitar: 'guitare', piano: 'piano', other: 'autre instrument' };
const NATURES = { chocs: 'des chocs', sourd: 'un bruit sourd', souffle: 'un souffle', 'pièce': 'le bruit de la pièce' };

function creer() {
  const cellules = { telephone: new Map(), micro: new Map() };   // seconde (ms / 1000, entière) → cellule
  const blocs = { telephone: [], micro: [] };                    // les séparations : { t0, t1, bpm, tonalite }
  const locuteurs = { telephone: [], micro: [] };                // qui parle : { t0, t1, qui }

  const cellule = (src, s) => {
    const m = cellules[src];
    if (!m) return null;
    let c = m.get(s);
    if (!c) { c = { s }; m.set(s, c); }
    return c;
  };
  const elaguer = (maintenant) => {
    const limite = Math.floor((maintenant - DUREE_MS) / 1000);
    for (const src of Object.keys(cellules)) {
      for (const s of cellules[src].keys()) if (s < limite) cellules[src].delete(s);
      while (blocs[src].length && blocs[src][0].t1 < maintenant - DUREE_MS) blocs[src].shift();
      while (locuteurs[src].length && locuteurs[src][0].t1 < maintenant - DUREE_MS) locuteurs[src].shift();
    }
  };

  /* une séparation : pistes = { fenetres: [{ t0, t1 (s du fichier), db, voix_db, fond_db, quoi, accord, chocs, nature }], bpm, tonalite,
     duree_s } ; t0 : l'instant (horloge du Mac) du début du fichier */
  function noterSeparation(src, t0, pistes, maintenant = Date.now(), instruments = [], voix = []) {
    if (!cellules[src] || !pistes || !Array.isArray(pistes.fenetres) || !(Number(t0) > 0)) return 0;
    let n = 0;
    for (const w of pistes.fenetres) {
      if (!w || !['musique', 'bruit', 'silence'].includes(w.quoi)) continue;
      const debut = Number(t0) + Number(w.t0) * 1000, fin = Number(t0) + Number(w.t1) * 1000;
      for (let s = Math.floor(debut / 1000); s * 1000 < fin; s++) {
        const c = cellule(src, s);
        c.sep = { quoi: w.quoi, accord: w.accord || null, db: Number(w.db), fond_db: Number(w.fond_db), voix_db: Number(w.voix_db),
          chocs: Number(w.chocs) || 0, nature: w.nature || null };
        n++;
      }
    }
    // (06/11, Ahmed : « telle note et tel piano ou telle guitare ») chaque instrument séparé (htdemucs_6s) : ses notes, seconde par seconde
    for (const ins of Array.isArray(instruments) ? instruments : []) {
      const nom = INSTRUMENTS[ins && ins.instrument];
      if (!nom) continue;
      const parS = Array.isArray(ins.notes_du_temps) ? ins.notes_du_temps : [];
      if (!parS.length) {                                          // la batterie, ou un instrument sans note nette : présent sur tout le bloc
        for (let s = Math.floor(Number(t0) / 1000); s * 1000 < Number(t0) + (Number(pistes.duree_s) || 0) * 1000; s++) {
          const c = cellule(src, s); (c.instr || (c.instr = {}))[nom] = c.instr[nom] || [];
        }
        continue;
      }
      for (const [ts, notes] of parS) {
        const c = cellule(src, Math.floor((Number(t0) + Number(ts) * 1000) / 1000));
        (c.instr || (c.instr = {}))[nom] = (Array.isArray(notes) ? notes : []).map(String).slice(0, 3);
      }
    }
    // (06/11) qui parle : chaque voix séparée (la cascade), sur ses segments ; papa, une voix connue par son nom, ou « voix n »
    for (const v of Array.isArray(voix) ? voix : []) {
      if (!v) continue;
      // (06/11, Ahmed : « il faut qu'il reconnaisse sa voix comme étant la sienne ») sa voix (l'empreinte « soi ») : « ta propre voix », son écho
      const qui = v.moi ? 'ta propre voix' : String(v.nom || v.timbre || `voix ${Number(v.numero) || 0}`).slice(0, 40);
      for (const sg of Array.isArray(v.segments) ? v.segments : []) {
        if (!Array.isArray(sg)) continue;
        locuteurs[src].push({ t0: Number(t0) + Number(sg[0]) * 1000, t1: Number(t0) + Number(sg[1]) * 1000, qui });
      }
    }
    while (locuteurs[src].length > 400) locuteurs[src].shift();
    const fin = Number(t0) + (Number(pistes.duree_s) || 0) * 1000;
    if (pistes.fenetres.length) {                                  // (la cascade qui suit une réponse partielle n'a plus de fenêtres)
      blocs[src].push({ t0: Number(t0), t1: fin, bpm: Number(pistes.bpm) || null, tonalite: pistes.tonalite || null });
      blocs[src].sort((a, b) => a.t0 - b.t0);
    }
    elaguer(maintenant);
    return n;
  }

  /* l'analyse légère (analyseMusicale, sur 20 s de trames) : elle vaut pour les 5 s qui précèdent t */
  function noterAnalyse(src, t, a, maintenant = Date.now()) {
    if (!cellules[src] || !a) return;
    for (let s = Math.floor((t - 5000) / 1000); s <= Math.floor(t / 1000); s++)
      cellule(src, s).ana = { bpm: a.bpm || null, tonalite: a.tonalite || null, contour: a.contour || null, voix: a.voix || 'aucune' };
    elaguer(maintenant);
  }

  /* les trames d'une seconde : leur niveau (dB) et leurs coups ; les notes de la voix, gardées pour leur résumé seulement */
  function noterTrames(src, t0, pas, trames, notes = []) {
    if (!cellules[src] || !Array.isArray(trames) || !trames.length) return;
    const parSeconde = new Map();
    trames.forEach((x, i) => {
      const s = Math.floor((t0 + i * pas) / 1000);
      const l = parSeconde.get(s) || [];
      l.push(Number(x[0]) || 0);
      parSeconde.set(s, l);
    });
    for (const [s, l] of parSeconde) {
      const rms = Math.sqrt(l.reduce((a, v) => a + v * v, 0) / l.length);
      cellule(src, s).niveau = Math.round(20 * Math.log10(Math.max(1e-6, rms)) * 10) / 10;
    }
    for (const n of notes || []) {
      const c = cellule(src, Math.floor(n.t / 1000));
      (c.notes || (c.notes = [])).push({ note: n.note, hz: n.hz, duree: n.duree, tenue: !!n.tenue });
    }
  }

  // ---- la lecture ----
  const quoiDe = (c) => {
    if (c.sep) return c.sep.quoi;
    const a = c.ana;
    if (a && (a.bpm || a.tonalite || a.voix === 'chante')) return 'musique';
    if (Number.isFinite(c.niveau) && c.niveau > -45) return 'son';              // un son, pas encore séparé
    return 'silence';
  };
  const dbDe = (c) => (c.sep && Number.isFinite(c.sep.db) ? c.sep.db : Number.isFinite(c.niveau) ? c.niveau : null);
  const blocA = (src, t) => blocs[src].find(b => t >= b.t0 - 500 && t <= b.t1 + 500) || null;

  /* les sections d'une source, sur toute sa mémoire : une section s'ouvre à la reprise de la musique (plus de 3 s sans elle), quand
     l'intensité saute de 6 dB, ou quand ses accords changent tout à fait ; nommée A, B… et « retour de A » quand elle revient */
  function sections(src) {
    const l = [...cellules[src].values()].sort((a, b) => a.s - b.s).filter(c => quoiDe(c) === 'musique');
    const out = [];
    let cur = null;
    const fermer = () => { if (cur) { out.push(cur); cur = null; } };
    // l'intensité lissée sur trois secondes (une seule seconde plus faible, un creux, n'ouvre pas de section ; mesuré sur « Rose »)
    const lisse = l.map((c, k) => mediane([l[k - 1], c, l[k + 1]].filter(x => x && Math.abs(x.s - c.s) <= 1).map(dbDe)));
    for (const [k, c] of l.entries()) {
      const db = lisse[k], ac = c.sep && c.sep.accord;
      if (cur) {
        const moy = cur.dbs.length ? cur.dbs.reduce((a, v) => a + v, 0) / cur.dbs.length : null;
        const recents = cur.recents.slice(-4).filter(Boolean);
        const sautDb = db != null && moy != null && cur.dbs.length >= 3 && Math.abs(db - moy) >= 6;
        const autresAccords = ac && cur.accords.size >= 2 && cur.s1 - cur.s0 >= 8 && !cur.accords.has(ac) && recents.length >= 2 && recents.every(x => !cur.accordsDebut.has(x));
        if (c.s - cur.s1 > 3 || sautDb || autresAccords) fermer();
      }
      if (!cur) cur = { s0: c.s, s1: c.s, dbs: [], accords: new Set(), accordsDebut: new Set(), recents: [] };
      cur.s1 = c.s;
      if (db != null) cur.dbs.push(db);
      if (ac) { cur.accords.add(ac); if (c.s - cur.s0 < 8) cur.accordsDebut.add(ac); }
      cur.recents.push(ac || null);
    }
    fermer();
    // les lettres : une section qui ressemble à une d'avant (mêmes accords pour moitié, intensité à 6 dB près) en reprend la lettre
    const lettres = [];
    for (const x of out) {
      const moy = x.dbs.length ? x.dbs.reduce((a, v) => a + v, 0) / x.dbs.length : null;
      x.db = moy;
      const pareille = lettres.find(y => {
        const inter = [...x.accords].filter(a => y.accords.has(a)).length, union = new Set([...x.accords, ...y.accords]).size;
        const memesAccords = union ? inter / union >= 0.5 : true;
        return memesAccords && (moy == null || y.db == null || Math.abs(moy - y.db) < 6);
      });
      if (pareille) { x.lettre = pareille.lettre; x.retour = true; }
      else { x.lettre = String.fromCharCode(65 + Math.min(25, lettres.length)); lettres.push(x); }
    }
    return out;
  }

  // (06/11, Ahmed : « il entend par Bluetooth aussi » ; mesuré : le même morceau capté 20 dB plus bas garde ses accords et ses notes) l'intensité
  // se dit par rapport à ce que la source fait d'habitude (sa médiane sur 15 min), pas en dB absolus : forte ou douce, quel que soit le niveau
  const reference = (src) => mediane([...cellules[src].values()].filter(c => quoiDe(c) === 'musique').map(dbDe));
  const intensiteDe = (src, db) => { const r = reference(src); if (db == null) return null; if (r == null) return 'moyenne'; return db > r + 4 ? 'forte' : db < r - 4 ? 'douce' : 'moyenne'; };
  const fmt = (ms) => { const d = ms / 1000; return `${d >= 0 ? (d > 0.05 ? '+' : '') : '−'}${Math.abs(d).toFixed(1).replace('.', ',')}`.replace(/^(\d)/, '$1'); };
  const fmtS = (ms) => `${fmt(ms)} s`;
  const plage = (a, t0, t1) => `${fmt(t0 - a)} → ${fmt(t1 - a)} s`;
  const mediane = (l) => { const s = l.filter(v => v != null).sort((x, y) => x - y); return s.length ? s[s.length >> 1] : null; };

  function musiqueTexte(src, a, debut, fin) {
    const secs = sections(src).filter(x => (x.s1 + 1) * 1000 > debut && x.s0 * 1000 < fin);
    const parts = [];
    for (const x of secs) {
      const s0 = Math.max(x.s0 * 1000, debut), s1 = Math.min((x.s1 + 1) * 1000, fin);
      const cs = [];
      for (let s = Math.floor(s0 / 1000); s * 1000 < s1; s++) { const c = cellules[src].get(s); if (c && quoiDe(c) === 'musique') cs.push(c); }
      if (!cs.length) continue;
      const bl = cs.map(c => blocA(src, c.s * 1000)).filter(Boolean);
      const bpm = mediane(bl.map(b => b.bpm).concat(cs.map(c => c.ana && c.ana.bpm)));
      const ton = (bl.find(b => b.tonalite) || {}).tonalite || (cs.find(c => c.ana && c.ana.tonalite) || { ana: {} }).ana.tonalite;
      // les accords et leurs changements, chacun à son instant
      const suite = [];
      for (const c of cs) { const ac = c.sep && c.sep.accord; if (ac && (!suite.length || suite[suite.length - 1].ac !== ac)) suite.push({ ac, t: c.s * 1000 }); }
      const accords = suite.slice(0, 8).map((x, i) => (i ? `${x.ac} (${fmtS(x.t - a)})` : x.ac)).join(' → ') + (suite.length > 8 ? ' …' : '');
      const dbs = cs.map(dbDe).filter(v => v != null);
      const tiers = Math.max(1, Math.floor(dbs.length / 3));
      const d0 = dbs.length ? dbs.slice(0, tiers).reduce((p, v) => p + v, 0) / tiers : null, d1 = dbs.length ? dbs.slice(-tiers).reduce((p, v) => p + v, 0) / tiers : null;
      const sens = d0 != null && d1 != null && dbs.length >= 4 ? (d1 - d0 > 4 ? ' ↑' : d0 - d1 > 4 ? ' ↓' : '') : '';
      const chant = cs.some(c => c.ana && c.ana.voix === 'chante') ? 'une voix chante' : '';
      const contour = (cs.slice().reverse().find(c => c.ana && c.ana.contour) || { ana: {} }).ana.contour;
      const melodie = resumeNotes(cs.flatMap(c => c.notes || []));
      // chaque instrument et ses notes, dans l'ordre où elles changent (la basse d'abord)
      const instr = [];
      for (const nom of Object.values(INSTRUMENTS)) {
        const suiteN = [];
        let present = false;
        for (const c of cs) {
          const n = c.instr && c.instr[nom];
          if (!n) continue;
          present = true;
          const k = n.join('+');
          if (k && (!suiteN.length || suiteN[suiteN.length - 1] !== k)) suiteN.push(k);
        }
        if (present) instr.push(suiteN.length ? `${nom} ${suiteN.slice(0, 6).join(' → ')}${suiteN.length > 6 ? ' …' : ''}` : nom);
      }
      const morceaux = [`section ${x.lettre}${x.retour ? ' (retour)' : ''}`, bpm ? `~${bpm} BPM` : '', ton || '', accords ? `accords ${accords}` : '', instr.length ? `instruments : ${instr.join(' ; ')}` : '',
        intensiteDe(src, mediane(dbs)) ? `intensité ${intensiteDe(src, mediane(dbs))}${sens}` : '', chant, melodie ? `mélodie ${melodie}${contour ? `, ${contour}` : ''}` : (contour && chant ? `la mélodie ${contour}` : '')];
      parts.push(`${plage(a, s0, s1)} : ${morceaux.filter(Boolean).join(', ')}`);
    }
    return parts.join(' · ');
  }

  function fondTexte(src, a, debut, fin, voixLointaines = []) {
    const l = [...cellules[src].values()].filter(c => c.s * 1000 >= debut - 999 && c.s * 1000 < fin).sort((x, y) => x.s - y.s);
    const runs = [];
    for (const c of l) {
      const q = quoiDe(c);
      if (q !== 'bruit' && q !== 'son') continue;
      const nat = q === 'son' ? 'un son pas encore séparé' : NATURES[c.sep.nature] || 'un bruit';
      const der = runs[runs.length - 1];
      if (der && der.nat === nat && c.s - der.s1 <= 1) { der.s1 = c.s; der.chocs += (c.sep && c.sep.chocs) || 0; der.dbs.push(dbDe(c)); continue; }
      runs.push({ nat, s0: c.s, s1: c.s, chocs: (c.sep && c.sep.chocs) || 0, dbs: [dbDe(c)] });
    }
    const parts = runs.map(r => {
      const db = mediane(r.dbs);
      return `${plage(a, Math.max(r.s0 * 1000, debut), Math.min((r.s1 + 1) * 1000, fin))} : ${r.nat}${r.chocs ? ` (${r.chocs})` : ''}${db != null ? `, ${String(Math.round(db)).replace('-', '−')} dB` : ''}`;
    });
    for (const v of voixLointaines) {
      const q = v.qui || '';
      parts.push(`${fmtS(v.t - a)} une voix lointaine${q ? ` (${q})` : ''} « ${v.mots.join(' ')} »`);
    }
    return parts.join(' · ');
  }

  /* les mots d'une source dans le fil, en phrases (moins de 1,5 s entre deux mots), chacune à l'instant de son premier mot */
  // qui parle à l'instant t (les segments de la cascade, à 0,3 s près ; le plus récent l'emporte)
  const quiA = (src, t) => { const l = locuteurs[src].filter(x => t >= x.t0 - 300 && t <= x.t1 + 300); return l.length ? l[l.length - 1].qui : ''; };
  function phrases(flux, sourcesMots, debut, fin, src = null) {
    const l = (flux || []).filter(o => sourcesMots.includes(o.s) && o.t >= debut && o.t <= fin).sort((x, y) => x.t - y.t);
    const out = [];
    for (const o of l) {
      const der = out[out.length - 1], qui = src ? quiA(src, o.t) : '';
      // une nouvelle phrase quand la voix change (une voix qui se tait un instant garde sa phrase)
      if (der && der.s === o.s && o.t - der.fin < 1500 && (!qui || !der.qui || qui === der.qui)) { der.mots.push(o.x); der.fin = o.t; if (!der.qui) der.qui = qui; continue; }
      out.push({ s: o.s, t: o.t, fin: o.t, mots: [o.x], qui });
    }
    return out;
  }

  /* le bloc pour son tour : les deux sources, chacune en trois pistes, sur la même ligne du temps (0 = l'instant a) */
  function bloc(flux, a = Date.now(), avant = 30000, apres = 3000, max = 2400) {
    const debut = a - avant, fin = a + apres;
    const lignes = [];
    for (const src of ['telephone', 'micro']) {
      const motsSources = src === 'telephone' ? ['telephone'] : ['papa'];
      const ph = phrases(flux, motsSources, debut, fin, src === 'micro' ? null : src);
      const lointaines = src === 'micro' ? phrases(flux, ['voix_autour'], debut, fin, src) : [];
      const parole = ph.map(p => { const q = src === 'micro' ? 'papa' : p.qui; return `${fmtS(p.t - a)}${q ? ` ${q}` : ''} « ${p.mots.join(' ')} »`; }).join(' · ');
      const musique = musiqueTexte(src, a, debut, fin);
      const fond = fondTexte(src, a, debut, fin, lointaines);
      if (!parole && !musique && !fond) continue;
      lignes.push(`${SOURCES[src]}\n  parole : ${parole || 'aucune'}\n  musique : ${musique || 'aucune'}\n  fond : ${fond || 'rien'}`);
    }
    const t = lignes.join('\n');
    return t.length > max ? `${t.slice(0, max - 1)}…` : t;
  }

  /* ce qui joue à l'instant a, en une ligne (pour « Au même moment ») */
  function resumeCourant(src, a = Date.now(), fenetre = 8000) {
    const m = musiqueTexte(src, a, a - fenetre, a + 1000);
    const f = fondTexte(src, a, a - fenetre, a + 1000);
    const derniere = (t) => String(t || '').split(' · ').pop().replace(/^[^:]+: /, '');
    return [m ? `musique : ${derniere(m)}` : '', f ? `fond : ${derniere(f)}` : ''].filter(Boolean).join(' ; ');
  }

  return { noterSeparation, noterAnalyse, noterTrames, sections, bloc, resumeCourant, musiqueTexte, fondTexte, _cellules: cellules, _locuteurs: locuteurs };
}

/* les notes de la voix résumées en éléments musicaux : leur étendue, leur registre, combien de tenues ; jamais la liste des notes */
function resumeNotes(notes) {
  const l = (notes || []).filter(n => n && Number(n.hz) > 0 && n.note);
  if (l.length < 2) return '';
  // (06/11, Ahmed : « il sait que c'est telle note ») les notes qui comptent (tenues, ou revenues), nommées avec leur octave, dans leur ordre
  const fois = new Map();
  for (const n of l) fois.set(n.note, (fois.get(n.note) || 0) + (n.tenue ? 3 : 1) + Number(n.duree || 0) / 200);
  const gardees = [...fois.entries()].filter(([, v]) => v >= 2).sort((a, b) => b[1] - a[1]).slice(0, 6).map(([k]) => k);
  const suite = [];
  for (const n of l) if (gardees.includes(n.note) && suite[suite.length - 1] !== n.note) suite.push(n.note);
  const hz = l.map(n => Number(n.hz)).sort((a, b) => a - b);
  const med = hz[hz.length >> 1];
  const registre = med < 150 ? 'grave' : med < 330 ? 'médium' : 'aigu';
  const tenues = l.filter(n => n.tenue).length;
  return `${suite.length ? `${suite.slice(0, 8).join(' → ')}${suite.length > 8 ? ' …' : ''}, ` : ''}${registre}`
    + `${tenues ? `, ${tenues} tenue${tenues > 1 ? 's' : ''}` : ', des notes brèves'}`;
}

module.exports = { creer, resumeNotes, SOURCES };
