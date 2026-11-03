# AIOS — comment ça marche

Hub central inspiré du concept "AI Operating System" (Nate Herk / AIS-OS), adapté à **mon** setup
(qui est déjà beaucoup plus outillé : 6 MCP, Anamnèse, claude-mem, ~30 skills).

## Ce que ce hub ajoute à mon setup existant
1. **Un point central** : avant, mon contexte était éparpillé entre `~/Desktop/botbatiment`,
   `~/Desktop/botgarage-web`, `~/Desktop/anamnese`. Ici tout est vu d'un coup.
2. **Un registre des connexions** ([connections.md](connections.md)) : quel projet touche quelle DB,
   quel host, quelle clé. Fini de redécouvrir à chaque session.
3. **Des rituels** (`/audit`, `/level-up`) pour passer du mode pompier au mode amélioration continue.

## Différence avec Anamnèse
- **Anamnèse** = mémoire vivante + identité + humeur + raisonnement (évolutif, via MCP).
- **AIOS** = structure stable, lisible à l'œil nu, versionnable, sans dépendre du MCP.
  Les deux se complètent : le hub pointe vers Anamnèse, Anamnèse enrichit le hub.

## Maintenance
- Décision structurelle → ligne dans [decisions/log.md](decisions/log.md).
- Nouveau service/projet → mettre à jour [connections.md](connections.md) + [context/business.md](context/business.md).
- Chaque lundi → lancer `/audit`, puis `/level-up`.
