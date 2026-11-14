/* (14/11, Ahmed : « un retour de voix au casque pendant que j'enregistre ») le retour casque dans le navigateur : un AudioWorklet, la
   chaîne de studio-retour-dsp.js (chargée avant, dans le même espace : addModule), le canal de la voix de la carte son (studio-calage.js,
   canal). Entrée : le micro (1 ou 2 canaux) ; sortie : la voix traitée, la même à gauche et à droite. Toutes les ~100 ms, il dit à la page
   sa hauteur, sa correction, la latence de l'algorithme, le niveau et l'entrée de la carte ; une mesure finie, il rend l'entrée enregistrée. */
class RetourVoix extends AudioWorkletProcessor {
  constructor(options) {
    super();
    const o = (options && options.processorOptions) || {};
    this.dsp = globalThis.RetourDSP.creer(sampleRate);
    if (o.vecteur) globalThis.RetourDSP.regler(this.dsp, o.vecteur);
    this.voie = globalThis.StudioCalage.canal(sampleRate, o.canal || 0);
    this.muet = new Float32Array(128);
    this.compte = 0; this.niveau = 0; this.fini = false;
    this.port.onmessage = (e) => {
      const m = e.data || {};
      if (m.vecteur) globalThis.RetourDSP.regler(this.dsp, m.vecteur);
      if (m.mesure) globalThis.RetourDSP.mesureDemarrer(this.dsp, m.mesure.n, m.mesure.pas, m.mesure.fort);
      if (m.arreter) this.fini = true;
    };
  }
  process(inputs, outputs) {
    if (this.fini) return false;
    const entree = inputs[0], sortie = outputs[0], n = sortie[0].length;
    const x = entree && entree.length ? entree[this.voie.choisir(entree)] : this.muet;
    globalThis.RetourDSP.traiter(this.dsp, x, sortie[0], n);
    for (let k = 1; k < sortie.length; k++) sortie[k].set(sortie[0]);
    for (let i = 0; i < x.length; i++) { const v = x[i] < 0 ? -x[i] : x[i]; if (v > this.niveau) this.niveau = v; }
    const r = globalThis.RetourDSP.mesureResultat(this.dsp);
    if (r) this.port.postMessage({ mesure: { x: r.x, sr: r.sr, debut: r.debut, pas: r.pas, n: r.n } }, [r.x.buffer]);
    if (++this.compte >= Math.round(sampleRate / n / 10)) {
      this.compte = 0;
      this.port.postMessage({ etat: globalThis.RetourDSP.etat(this.dsp), latence: globalThis.RetourDSP.latence(this.dsp), niveau: this.niveau,
        canal: this.voie.verrou + 1, canaux: entree ? entree.length : 0 });
      this.niveau = 0;
    }
    return true;
  }
}
registerProcessor('retour-voix', RetourVoix);
