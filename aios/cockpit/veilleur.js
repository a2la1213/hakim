/* Le veilleur d'un cerveau (28/10, Ahmed : « un garde-fou pour les problèmes venus d'Anthropic »). À 08:09, la requête est
   restée 1 min 43 s sans rien renvoyer ; coupée, l'outil Claude a écrit « No response requested. » à la place de Hakim.
   Une demande est ouverte quand claude rejoue un message (il commence à le traiter) et close à son résultat. Bloqué = une
   demande ouverte, aucun outil à lui qui travaille, et aucune ligne depuis `delaiMs` (le premier mot vient en 25 s au
   99e centile sur 786 tours, 43 s au plus : 60 s, c'est une panne). */
function creer(delaiMs) {
  let derniere = 0, demandes = 0;
  const outils = new Set();
  return {
    ligne(o, now) {
      derniere = now;
      if (!o || o.parent_tool_use_id) return;                 // un sous-agent qui parle : une activité, pas ses outils à lui
      if (o.type === 'user' && o.isReplay && !o.isSynthetic) demandes++;
      const contenu = o.message && Array.isArray(o.message.content) ? o.message.content : [];
      if (o.type === 'assistant') for (const b of contenu) if (b && b.type === 'tool_use' && b.id) outils.add(b.id);
      if (o.type === 'user') for (const b of contenu) if (b && b.type === 'tool_result') outils.delete(b.tool_use_id);
      if (o.type === 'result') { demandes = Math.max(0, demandes - 1); outils.clear(); }
    },
    bloque(now) { return demandes > 0 && outils.size === 0 && now - derniere >= delaiMs; },
  };
}

module.exports = { creer };
