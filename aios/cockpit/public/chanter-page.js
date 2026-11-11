/* (11/11, ~01:15, Ahmed : « Il peut chanter en même temps qu'une musique, s'il le veut ? En coordonnant la sortie de sa voix avec la sortie du
   son, sur le smartphone ou en Bluetooth. ») SON CHANT, côté page (chargé après parler.js, dont il prend le contexte audio, son analyseur et
   son journal). Le cockpit envoie le plan (« chanter », pour le téléphone seulement) : ses morceaux, chacun à l'instant où la musique jouera ce
   temps (l'heure de l'appli, celle de la page), et le calage de la musique jusqu'au micro. La page :
   - fabrique sa voix de chaque morceau d'avance, en même temps (/api/chanter/voix : Azure au débit de sa durée) ;
   - la fait partir à l'heure (Chanter.depart : par le micro, l'écho de sa voix et le calage de la musique ; sinon le même appareil, moins le
     tampon de la page), le blanc du début de sa voix retiré ; trop tard pour un morceau : il est laissé (jamais à contretemps) ;
   - sa voix passe par son analyseur : son écho reste le sien (jamais pris pour papa), et « couper le son » le coupe aussi ;
   - papa parle, « stop », son intérieur coupé, le cockpit qui annule : il se tait net.
   (v2, 11/11 ~03:00) une ligne vient en syllabes (chacune sur la grille et sur sa note) : le cockpit la rend chantée d'un seul son, qui
   commence X-Zero-Ms avant sa première syllabe ; c'est ce point qui part à l'heure. Pas prête avant de devoir sonner : laissée. */
const chant = { id: null, sources: [], debut: 0, fin: 0, ctl: null };
// il chante à l'instant (sa voix sonne, ou va sonner dans la demi-seconde) : pour son écho et pour la coupure par papa
function chantSonne(m = Date.now()) { return !!chant.id && chant.sources.length > 0 && m >= chant.debut - 500 && m <= chant.fin + 200; }
function chantArreter(raison = 'stop') {
  const actif = !!chant.id;
  if (chant.ctl) { try { chant.ctl.abort(); } catch (_) {} }
  for (const s of chant.sources) { try { s.onended = null; s.stop(); s.disconnect(); } catch (_) {} }
  if (actif && typeof journalVoix === 'function') journalVoix('chant_arrete', { raison: String(raison).replace(/[^a-z_]/g, '').slice(0, 30) || 'stop' });
  chant.id = null; chant.sources = []; chant.ctl = null; chant.debut = 0; chant.fin = 0;
  return actif;
}
// papa parle ici : son tour en cours au micro, ou sa voix il y a moins de 1,5 s
function papaParleIci() {
  const c = typeof etat !== 'undefined' && etat.conversation ? etat.conversation.capteur : null;
  return !!((c && c.enParole) || (typeof etat !== 'undefined' && Date.now() - (Number(etat.papaVoixA) || 0) < 1500));
}
async function surChanter(o) {
  if (!o || typeof Chanter === 'undefined') return;
  if (o.cible && typeof appareilIci === 'function' && o.cible !== appareilIci()) return;
  if (o.annuler) { if (!o.id || o.id === chant.id) chantArreter(o.raison || 'cockpit'); return; }
  if (!o.id || !Array.isArray(o.morceaux) || !o.morceaux.length || chant.id === o.id) return;
  if (typeof reglagesCorps !== 'undefined' && reglagesCorps && reglagesCorps.chanter_musique === false) return;
  if (typeof contexteAudio === 'function') contexteAudio();
  if (typeof actx === 'undefined' || !actx || actx.state === 'closed' || !analyseurVoix) { if (typeof journalVoix === 'function') journalVoix('chant_sans_son', {}); return; }
  chantArreter('nouveau');
  const id = o.id, ctl = new AbortController();
  chant.id = id; chant.ctl = ctl;
  const t0 = Date.now();
  // (v2, 11/11) une ligne en syllabes (chacune à sa place et sur sa note) : sa voix rendue commence X-Zero-Ms avant sa première syllabe, et
  // elle doit être prête avant de devoir sonner (limite_ms : le temps qu'il reste, moins la marge du départ) ; sinon elle n'est pas chantée
  const prets = await Promise.all(o.morceaux.map(m => { let zero = null;
    return fetch('/api/chanter/voix', { method: 'POST', signal: ctl.signal,
      headers: { 'Content-Type': 'application/json', 'X-Jeton': typeof jeton === 'function' ? jeton() : '' },
      body: JSON.stringify({ texte: String(m.texte || ''), duree_ms: Number(m.d) || 0, langue: 'fr',
        ...(Array.isArray(m.syllabes) && Array.isArray(m.mots) ? { mots: m.mots, syllabes: m.syllabes, limite_ms: Math.max(1, Math.round(Number(m.a) - Date.now() - 400)) } : {}) }) })
      .then((r) => { if (!r.ok) return Promise.reject(new Error('voix')); const z = r.headers && r.headers.get ? r.headers.get('X-Zero-Ms') : null; if (z != null && z !== '' && Number.isFinite(Number(z))) zero = Number(z); return r.arrayBuffer(); })
      .then(ab => actx.decodeAudioData(ab)).then(buf => ({ m, buf, zero })).catch(() => null); }));
  if (chant.id !== id) return;                                       // annulé pendant qu'elle se faisait
  if (papaParleIci()) { if (typeof journalVoix === 'function') journalVoix('chant_papa', {}); chantArreter('papa'); return; }
  // les deux chemins jusqu'au micro : sa voix (le chemin de son écho, appris quand il parle) et la musique (le calage du cockpit, ses pics)
  const cap = typeof etat !== 'undefined' && etat.conversation ? etat.conversation.capteur : null;
  const ch = cap && cap.echo, echo = ch && ch.actif ? ch.retardMs : null;
  const calage = Chanter.choisirCalage(o.calage, echo);
  const base = Math.round((Number(actx.baseLatency) || 0) * 1000);
  let joues = 0, tard = 0, par = '';
  for (const x of prets) {
    if (!x) continue;
    const att = x.zero != null ? x.zero : Chanter.attaqueDe(x.buf.getChannelData(0), x.buf.sampleRate);   // (v2) le zéro de la ligne, dit par le cockpit
    const d = Chanter.depart({ cible: x.m.a, calage_ms: calage, echo_ms: echo, base_ms: base, attaque_ms: att });
    if (!d) continue;
    const quand = actx.currentTime + (d.t - Date.now()) / 1000;
    if (quand < actx.currentTime + 0.03) { tard++; continue; }       // trop tard : laissé, jamais à contretemps
    const src = actx.createBufferSource();
    src.buffer = x.buf;
    // un peu plus longue que sa place (au-delà de 4 %) : un rien plus vite, 6 % au plus
    const ratio = (x.buf.duration * 1000) / Math.max(1, Number(x.m.d) || x.buf.duration * 1000);
    if (x.zero == null && ratio > 1.04) src.playbackRate.value = Math.min(1.06, ratio);   // (v2) ses syllabes sont déjà à leur place : rien à presser
    src.connect(analyseurVoix);
    src.onended = () => { chant.sources = chant.sources.filter(s => s !== src); if (!chant.sources.length && chant.id === id) { chant.id = null; if (typeof journalVoix === 'function') journalVoix('chant_fini', {}); } };
    src.start(quand);
    chant.sources.push(src); joues++; par = d.par;
    chant.debut = chant.debut ? Math.min(chant.debut, d.t) : d.t;
    chant.fin = Math.max(chant.fin, d.t + (x.buf.duration * 1000) / src.playbackRate.value);
  }
  if (typeof journalVoix === 'function') journalVoix('chant_prevu', { joues, trop_tard: tard, rates: prets.filter(x => !x).length, par: par || 'aucun',
    echo_ms: echo == null ? -1 : echo, calage_ms: calage == null ? -1 : calage, base_ms: base, pret_ms: Date.now() - t0, avance_ms: chant.debut ? chant.debut - Date.now() : -1 });
  if (!joues) chantArreter('rien_a_temps');
}
