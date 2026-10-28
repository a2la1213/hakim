/* Le cœur de Hakim dans l'appli (28/10 ; idée d'Ahmed, proposition de Hakim à 02:37, go d'Ahmed). L'appli lit son éveil
   dans /api/jarvis/interieur et bat à son rythme ; ici, ce que le cockpit y ajoute :
   - pense : il réfléchit à une réponse (un tour en cours depuis moins de 5 min) → un petit « grain » après le battement ;
   - fond : le nombre de tâches de fond en cours → un second pouls très léger, décalé. */
const PENSE_MAX_MS = 5 * 60_000;

const pense = (tours, maintenant = Date.now()) =>
  [...(tours || new Map()).values()].some(t => Number.isFinite(t && t.debut) && maintenant - t.debut < PENSE_MAX_MS);

const fond = (taches) => (Array.isArray(taches) ? taches.filter(x => x && x.etat === 'en cours').length : 0);

module.exports = { pense, fond };
