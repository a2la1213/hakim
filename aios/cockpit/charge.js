/* (11/11, Ahmed, pendant le live : « il ne doit pas stocker sa parole au-delà de 50 % des CPU et GPU ») la charge de ses processeurs, en %, pour la
   page Parler (/api/corps/charge) : le CPU du Mac (la part de temps non oisive de tous ses cœurs depuis la mesure d'avant), son GPU (« Device
   Utilization % » d'ioreg, comme anamnese/interoception.py), et le téléphone tel que l'appli le dit (processeurs-appareils.json, toutes les 5 s) :
   ses cœurs (leur fréquence sur leur maximum, en moyenne : Android ne laisse plus lire leur charge), son GPU, sa marge thermique (100 : il bride).
   Rien ne tourne en fond : la mesure se fait quand une page la demande, au plus une fois toutes les 4 s ; ioreg part sans bloquer. */
'use strict';

const pct = (v) => (v != null && Number.isFinite(Number(v)) ? Math.max(0, Math.min(100, Math.round(Number(v)))) : null);

// la part non oisive (0-100) entre deux relevés d'os.cpus()
function cpuEntre(avant, apres) {
  if (!Array.isArray(avant) || !Array.isArray(apres) || !avant.length || avant.length !== apres.length) return null;
  let total = 0, oisif = 0;
  for (let i = 0; i < apres.length; i++) {
    const a = (avant[i] && avant[i].times) || {}, b = (apres[i] && apres[i].times) || {};
    const t = ['user', 'nice', 'sys', 'idle', 'irq'].reduce((s, k) => s + Math.max(0, (Number(b[k]) || 0) - (Number(a[k]) || 0)), 0);
    total += t; oisif += Math.max(0, (Number(b.idle) || 0) - (Number(a.idle) || 0));
  }
  return total > 0 ? pct((100 * (total - oisif)) / total) : null;
}

// « Device Utilization % »=77 dans la sortie d'ioreg (le plus haut s'il y en a plusieurs)
function gpuDeIoreg(texte) {
  const l = [...String(texte || '').matchAll(/"Device Utilization %"\s*=\s*(\d+)/g)].map(m => Number(m[1]));
  return l.length ? pct(Math.max(...l)) : null;
}

// le téléphone : { tel_cpu, tel_gpu, tel_thermique, tel_age_ms } d'après processeurs-appareils.json (son âge à l'horloge du Mac : la page n'a
// pas la même horloge)
function telephoneDe(tout, maintenant = Date.now()) {
  const p = tout && tout.telephone;
  if (!p || !Number.isFinite(Number(p.ts))) return {};
  const coeurs = Array.isArray(p.coeurs) ? p.coeurs.filter(x => x != null && Number.isFinite(Number(x))).map(Number) : [];
  return { tel_cpu: coeurs.length ? pct((100 * coeurs.reduce((s, x) => s + x, 0)) / coeurs.length) : null,
    tel_gpu: p.gpu != null ? pct(100 * Number(p.gpu)) : null, tel_thermique: p.thermique != null ? pct(100 * Number(p.thermique)) : null, tel_age_ms: Math.max(0, maintenant - Number(p.ts)) };
}

function creer({ cpus, lireProcesseurs, ioreg, maintenant = () => Date.now(), pasMs = 4000 } = {}) {
  const etat = { avant: null, mac_cpu: null, mac_gpu: null, mesureA: 0, gpuEnCours: false };
  function mesurer() {
    const now = maintenant();
    if (now - etat.mesureA < pasMs) return;
    etat.mesureA = now;
    try { const c = cpus(); const v = cpuEntre(etat.avant, c); if (v != null) etat.mac_cpu = v; etat.avant = c; } catch (_) {}
    if (ioreg && !etat.gpuEnCours) {
      etat.gpuEnCours = true;
      try { ioreg((texte) => { etat.gpuEnCours = false; const g = gpuDeIoreg(texte); if (g != null) etat.mac_gpu = g; }); } catch (_) { etat.gpuEnCours = false; }
    }
  }
  function vue() {
    mesurer();
    let tel = {};
    try { tel = telephoneDe(lireProcesseurs ? lireProcesseurs() : null, maintenant()); } catch (_) {}
    return { mac_cpu: etat.mac_cpu, mac_gpu: etat.mac_gpu, ...tel, t: maintenant() };
  }
  return { mesurer, vue, etat };
}

module.exports = { cpuEntre, gpuDeIoreg, telephoneDe, creer, pct };
