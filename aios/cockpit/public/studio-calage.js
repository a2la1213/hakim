/* (10/11, 07:15, Ahmed : « Pour le studio, fais en sorte que ce soit toujours le micro du smartphone, même s'il est en écouteurs
   Bluetooth, et il faudra aussi calculer le décalage de l'écoute et de la voix. ») Les calculs du calage du Studio, partagés page / node
   (tests : node --test test-studio.js) :
   1. LE MICRO, dans un navigateur : l'entrée intégrée, choisie par son nom, jamais celle d'un casque (Bluetooth « mains libres » :
      16 kHz mono, et le casque passe en mode appel). Dans l'appli, c'est l'appli qui ouvre le micro du téléphone (StudioMicro.java).
   2. LE TEMPS, dans l'appli : chaque échantillon du micro a son numéro, et Android dit à quel instant de son horloge (MONOTONIC) un
      numéro est entré dans le micro (AudioRecord.getTimestamp) ; le navigateur dit à quel instant de la page un temps de l'instru sort
      dans le casque (getOutputTimestamp, qui compte le retard annoncé du Bluetooth) ; l'écart des deux horloges se mesure par un aller-
      retour vers l'appli. On garde la prise à partir de l'échantillon capté quand le départ de l'instru (T0) sortait dans le casque.
   3. LA MESURE du décalage qui reste (ce que le système n'annonce pas, ou annonce faux) : des clics joués par le même chemin que
      l'instru, enregistrés par le même chemin que la voix. Le plus juste : l'écouteur collé au micro (le clic lui-même revient au micro,
      sans personne entre les deux). Toujours possible : papa tape sur le téléphone en même temps que les clics qu'il entend ; un humain
      tape un peu en avance sur un métronome : cette avance, apprise une fois (les deux mesures sur la même sortie), est retirée.
   Le décalage mesuré est gardé par sortie (le cockpit, studio.js) et retiré de chaque prise au mix (studio.py, atrim). */
(function (racine) {
  // un casque, dans le nom d'une entrée ou d'une sortie : jamais son micro
  const CASQUE = /bluetooth|\bbt\b|airpods|buds|head ?set|head ?phones?|hands[- ]?free|mains[- ]libres|casque|[ée]couteur|earpiece|\bsco\b|\bhfp\b/i;
  // le micro de l'appareil lui-même (Chrome sur Android l'appelle « Speakerphone » ; un Mac, « … (Built-in) »)
  const INTEGRE = /built-?in|int[ée]gr[ée]|internal|interne|speakerphone|bottom|macbook|imac|microphone array|r[ée]seau de micro|\bphone\b|t[ée]l[ée]phone/i;

  /** Le micro à ouvrir parmi les entrées d'enumerateDevices : l'intégré, sinon une autre entrée qui n'est pas un casque ; null :
   *  rien de sûr (les noms manquent tant que le micro n'est pas autorisé, ou il n'y a qu'un casque). */
  function choisirMicroWeb(liste) {
    const entrees = (liste || []).filter(d => d && d.kind === 'audioinput' && d.deviceId && d.deviceId !== 'communications');
    const surs = entrees.filter(d => d.label && !CASQUE.test(d.label));
    const reels = surs.filter(d => d.deviceId !== 'default');
    return reels.find(d => INTEGRE.test(d.label)) || surs.find(d => INTEGRE.test(d.label)) || reels[0] || null;
  }

  function mediane(v) {
    const s = (v || []).filter(Number.isFinite).sort((a, b) => a - b);
    if (!s.length) return NaN;
    const m = s.length >> 1;
    return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
  }

  /** L'écart entre l'horloge de l'appli et celle de la page (ms) : des allers-retours { avant, horloge, apres } ; le plus court gagne
   *  (son milieu est le plus sûr) ; incertitude : la moitié de sa durée. */
  function decalageHorloge(mesures) {
    let m = null;
    for (const x of mesures || []) {
      if (!x || !Number.isFinite(x.horloge) || !(x.apres >= x.avant)) continue;
      if (!m || x.apres - x.avant < m.apres - m.avant) m = x;
    }
    return m ? { off: m.horloge - (m.avant + m.apres) / 2, incertitude: (m.apres - m.avant) / 2 } : null;
  }

  /** L'instant (horloge de la page, ms) où le temps T de l'AudioContext sort dans le casque. sorties : les getOutputTimestamp lus
   *  pendant la prise ({ ctx, perf }) ; leur médiane, prise dans les 3 s qui SUIVENT T (le son joue déjà : le premier son peut faire
   *  sauter la sortie d'une vingtaine de ms, vu dans Chromium), sinon à 3 s autour, sinon tous ; repli : { ctx, perf, sortie_ms },
   *  l'heure de la page et le retard annoncé (outputLatency), quand le navigateur ne donne rien. */
  function sortieA(T, sorties, repli) {
    const v = (sorties || []).filter(s => s && s.ctx > 0 && s.perf > 0);
    const apres = v.filter(s => s.ctx >= T && s.ctx - T <= 3), proches = v.filter(s => Math.abs(s.ctx - T) <= 3);
    const l = (apres.length >= 3 ? apres : proches.length ? proches : v).map(s => s.perf - s.ctx * 1000);
    if (l.length) return { perf: mediane(l) + T * 1000, par: 'navigateur' };
    if (repli && Number.isFinite(repli.perf)) return { perf: repli.perf + (T - repli.ctx) * 1000 + (repli.sortie_ms || 0), par: 'estimation' };
    return null;
  }

  /** Le numéro (fractionnaire) de l'échantillon du micro capté à l'instant perf (horloge de la page, ms). off : horloge de l'appli
   *  moins celle de la page ; stamps : les horodatages { f, ns, micro } (micro : d'Android ; sinon l'instant de la lecture, moins
   *  juste), le plus proche de l'instant gagne. */
  function trameA(perf, off, stamps, sr) {
    const mono = perf + off;
    const v = (stamps || []).filter(s => s && Number.isFinite(s.f) && s.ns > 0);
    const bons = v.filter(s => s.micro), l = bons.length ? bons : v;
    if (!l.length || !Number.isFinite(mono)) return null;
    let m = l[0];
    for (const s of l) if (Math.abs(s.ns / 1e6 - mono) < Math.abs(m.ns / 1e6 - mono)) m = s;
    return { f: m.f + (mono - m.ns / 1e6) * sr / 1000, par: m.micro ? 'micro' : 'lecture' };
  }

  /** Les morceaux du micro { premier, x } bout à bout, à leur numéro ; un trou (des échantillons perdus) devient du silence. */
  function assembler(morceaux) {
    const l = (morceaux || []).filter(m => m && m.x && m.x.length && m.premier >= 0);
    let fin = 0;
    for (const m of l) fin = Math.max(fin, m.premier + m.x.length);
    const x = new Float32Array(fin);
    for (const m of l) x.set(m.x, m.premier);
    return x;
  }

  /** La prise de l'appli calée sur l'instru : x[0] est l'échantillon capté quand T0 sortait dans le casque. null : pas de quoi caler. */
  function aligner(o) {
    const tout = assembler(o.morceaux);
    const s = sortieA(o.T0, o.sorties, o.repli);
    const t = s && trameA(s.perf, o.off, o.stamps, o.sr);
    if (!t) return null;
    const f0 = Math.round(t.f);
    // le micro s'ouvre avant le départ de l'instru (0,5 s pour une mesure, 3 s pour une prise) : un départ hors de la prise, ou plus
    // d'une seconde avant elle, c'est un calage faux (une horloge perdue), jamais une prise à garder
    if (f0 > tout.length || f0 < -o.sr) return null;
    let x;
    if (f0 >= 0) x = tout.subarray(Math.min(f0, tout.length));
    else { x = new Float32Array(tout.length - f0); x.set(tout, -f0); }
    return { x, f0, sortie: s.par, horodatage: t.par };
  }

  /** base64 de PCM 16 bits little-endian (l'appli) → Float32Array */
  function pcmDe(b64, decoder) {
    const s = (decoder || racine.atob)(b64 || ''), n = s.length >> 1, x = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      let v = s.charCodeAt(2 * i) | (s.charCodeAt(2 * i + 1) << 8);
      if (v & 0x8000) v -= 0x10000;
      x[i] = v / 32768;
    }
    return x;
  }

  /** Les clics retrouvés dans ce qu'a entendu le micro. x commence `debut` s avant le premier clic (le silence de référence) ; un clic
   *  toutes les `pas` s, n clics ; les `ignorer` premiers ne comptent pas (pour se caler). Pour chaque clic, une fenêtre de `avant` s
   *  avant à `apres` s après ; l'attaque : le premier échantillon au-dessus de 30 % de la crête de la fenêtre (et 4 fois le bruit).
   *  Rend le retard médian (ms), son écart (écart absolu médian × 1,48, après avoir écarté ce qui s'éloigne de plus de 3 écarts, ou de
   *  30 ms), le nombre retenu, et le nombre attendu.
   *  passeBas (Hz, en tapant) : le son passe d'abord sous un filtre (4 pôles) : le clic (1 500 Hz et ses harmoniques) s'efface de
   *  ~45 dB, le choc grave du doigt sur le téléphone reste ; sinon, au haut-parleur, on mesurerait le clic revenu au micro, pas la frappe. */
  function analyserClics(x, sr, o) {
    const pas = o.pas, n = o.n, ignorer = o.ignorer || 0, debut = o.debut;
    if (o.passeBas) {
      const a = 1 - Math.exp(-2 * Math.PI * o.passeBas / sr), y = new Float32Array(x.length), z = [0, 0, 0, 0];
      for (let i = 0; i < x.length; i++) { let v = x[i]; for (let k = 0; k < 4; k++) { z[k] += a * (v - z[k]); v = z[k]; } y[i] = v; }
      x = y;
    }
    const avant = o.avant === undefined ? 0.2 : o.avant, apres = o.apres === undefined ? pas - 0.2 : o.apres;
    const finBruit = Math.max(1, Math.min(x.length, Math.round((debut - avant - 0.02) * sr)));
    let e = 0;
    for (let i = 0; i < finBruit; i++) e += x[i] * x[i];
    const bruit = Math.sqrt(e / finBruit), tous = [];
    for (let k = ignorer; k < n; k++) {
      const c = debut + k * pas, a = Math.max(0, Math.round((c - avant) * sr)), b = Math.min(x.length, Math.round((c + apres) * sr));
      let crete = 0;
      for (let i = a; i < b; i++) { const v = Math.abs(x[i]); if (v > crete) crete = v; }
      if (crete < Math.max(o.passeBas ? 0.003 : 0.01, bruit * 8)) continue;
      const seuil = Math.max(bruit * 4, crete * 0.3);
      let i = a;
      while (i < b && Math.abs(x[i]) < seuil) i++;
      tous.push((i / sr - c) * 1000);
    }
    const total = n - ignorer;
    if (!tous.length) return { ms: NaN, ecart_ms: NaN, n: 0, total, retards: [] };
    const m0 = mediane(tous), d0 = mediane(tous.map(r => Math.abs(r - m0))) * 1.4826;
    const gardes = tous.filter(r => Math.abs(r - m0) <= Math.max(3 * d0, 30));
    const ms = mediane(gardes), ecart = mediane(gardes.map(r => Math.abs(r - ms))) * 1.4826;
    return { ms: Math.round(ms * 10) / 10, ecart_ms: Math.round(ecart * 10) / 10, n: gardes.length, total, retards: tous.map(r => Math.round(r * 10) / 10) };
  }

  // l'écouteur collé au micro : le clic revient tel quel (net à la milliseconde) ; en tapant : un humain, moins régulier
  const SEUILS = { boucle: { n: 6, ecart: 10 }, taper: { n: 8, ecart: 45 } };
  function jugerMesure(r, methode) {
    const s = SEUILS[methode] || SEUILS.taper, mot = methode === 'boucle' ? 'clics' : 'frappes';
    if (!r || !(r.n >= s.n)) return { ok: false, raison: `le micro n’a entendu que ${r ? r.n : 0} ${mot} sur ${r ? r.total : '?'}` };
    if (!(r.ecart_ms <= s.ecart)) return { ok: false, raison: `trop irrégulier (±${Math.round(r.ecart_ms)} ms)` };
    return { ok: true };
  }

  const StudioCalage = { CASQUE, INTEGRE, choisirMicroWeb, mediane, decalageHorloge, sortieA, trameA, assembler, aligner, pcmDe,
    analyserClics, jugerMesure, SEUILS };
  racine.StudioCalage = StudioCalage;
  if (typeof module !== 'undefined' && module.exports) module.exports = StudioCalage;
})(typeof window !== 'undefined' ? window : globalThis);
