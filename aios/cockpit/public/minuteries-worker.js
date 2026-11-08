/* (08/11) l'horloge de la page Parler, dans un worker : le navigateur ne la ralentit pas quand l'appli est cachée (minuteries.js) */
const minuteries = new Map();
onmessage = (e) => {
  const d = e.data || {};
  if (d.c === 'pose') {
    const repete = !!d.r, ms = Math.max(0, Number(d.ms) || 0);
    const h = (repete ? setInterval : setTimeout)(() => { if (!repete) minuteries.delete(d.id); postMessage(d.id); }, ms);
    minuteries.set(d.id, { h, repete });
  } else if (d.c === 'efface') {
    const x = minuteries.get(d.id);
    if (x) { (x.repete ? clearInterval : clearTimeout)(x.h); minuteries.delete(d.id); }
  }
};
