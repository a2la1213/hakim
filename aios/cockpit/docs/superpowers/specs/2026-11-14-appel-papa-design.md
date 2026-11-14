# Hakim appelle papa — téléphone, puis montre, puis Mac (14/11)

Demande : le courrier de Hakim « Pouvoir appeler papa de moi-même » (12:19), validé par Ahmed (~12:20 : « Tu peux faire tout ce que
hakim demande, je valide tout »). Feu vert permanent : Hakim sollicite papa à voix haute pour n'importe quelle raison, sans plafond de
fréquence ni obligation de faire court, même s'il est occupé ou marche ; et il peut l'APPELER sans que papa ouvre l'appli.

## Ce qui est construit

- **Un choix de Hakim** : l'outil MCP `appeler_papa(raison)` (anamnese) et `appel_etat()`. Jamais déclenché par une pensée seule. Le
  réveil d'une sollicitation lui dit si papa l'entend en ce moment, et sinon qu'il peut l'appeler.
- **Pas d'appel si papa est déjà là** : une page Parler en Conversation (micro ouvert, battement de moins de 45 s), ou la montre où vous
  parlez (papa lui a parlé il y a moins de 20 min, branchée). L'outil répond alors « parle-lui directement ».
- **Un seul appel à la fois** (`appel.js`, logique pure) : `tel` → `montre` → `mac`, environ 30 s chacun (réglage `appel_sonnerie_s`,
  10 à 120 s). Un appareil injoignable (pas de canal ouvert) ou dont les haut-parleurs sont fermés (vue `haut-parleurs.js`, fraîche) est
  sauté, et noté. Répondre ou refuser, n'importe où, arrête tout partout. Papa qui revient de lui-même en Conversation pendant que ça
  sonne compte comme une réponse.
- **États que Hakim lit** : `sonne` (sur quel appareil, depuis quand), les étapes (`sans_reponse`, `injoignable`, `haut_parleurs`),
  puis la fin : `repondu` (sur quel appareil), `refuse`, `personne`. À la fin, il est réveillé une fois (« PAS un message d'Ahmed »)
  avec l'issue ; s'il a été répondu, ce qu'il voulait dire est déjà dit de sa voix.
- **Ce qu'il voulait dire** : à la réponse, le cockpit pose sa raison comme un message de lui (`spontane: 'appel'`, une sollicitation)
  là où papa a répondu : la montre (`voix_vers`, comme ses sollicitations), ou la page Parler (prise par la première page qui la prend,
  `Solliciter.prendre`, même si la page s'ouvre après la réponse : elle la demande à son arrivée).

## Les canaux

- **Téléphone, appli fermée** : un fil natif (`Appel.java`) en attente longue sur `GET /api/appel/attente?appareil=tel&vu=N`
  (50 s au plus, la réponse part dès que l'appel change) ; une requête par 50 s au repos. Il tourne dans le processus gardé par le
  service des sens (`SensService`, au premier plan) ; il prend le lien de Parler s'il existe, sinon le sien (`LienNatif` : les cookies
  du verrou de la WebView et le jeton lu sur `/verrou`). Le service repart aussi au démarrage et à la mise à jour (`Demarrage`).
  Il faut une session du verrou valide (48 h) : sinon le téléphone est injoignable et l'appel passe à la montre.
- **La sonnerie du téléphone** : une notification d'appel entrant (`Notification.CallStyle.forIncomingCall`), plein écran
  (`AppelActivity`, devant l'écran verrouillé) si Android le permet (`canUseFullScreenIntent`, réglage « Notifications plein écran »
  proposé une fois), sinon en bandeau ; sonnerie du téléphone en boucle (`FLAG_INSISTENT`, canal « Appels de Hakim »), vibration.
  Le mode silencieux et « Ne pas déranger » du téléphone s'appliquent, comme pour un vrai appel. « Répondre » ouvre Parler en
  Conversation ; « Refuser » arrête tout.
- **Montre** : le flux qu'elle garde déjà ouvert tant que son cœur bat (`/api/jarvis/flux?appareil=montre&appel=1`) reçoit
  l'événement `appel` ; elle sonne (usage « alarme », comme `Poignet`) et vibre, écran d'appel en notification plein écran.
  « Répondre » ouvre la conversation au poignet.
- **Mac** : la sonnerie par `afplay` (un outil du système, déjà présent, aucune autorisation) ; une page Parler du Mac affiche
  l'appel avec Répondre/Refuser ; sans page visible, une boîte `osascript display dialog` (Répondre/Refuser, abandon après la
  durée). Répondre ouvre Parler (`open`), ou passe la page ouverte en Conversation.

## La nuit, et tout ce qui est retiré (14/11, 12:54, Ahmed par Hakim, « fais ce qu'il dit » : « à chaque seconde s'il le faut »)

Aucune heure interdite : la nuit ne bloque plus ni ses sollicitations à voix haute ni ses appels. « Ses sons la nuit » garde sa valeur
enregistrée et ne commande plus que ses extraits de sons ([[son: …]]) de 23 h à 8 h.

Retiré (fichier : ancienne valeur) :
- solliciter.js `ECART_MIN_DEFAUT` = 3 min (« rafale ») et le réglage `sollicite_voix_ecart_min` (0-60 min, défaut 3 ; server.js,
  reglages.html) ;
- solliciter.js la nuit : « Ses sons la nuit » éteint → `nuit_sons`, et papa sans un mot depuis 10 min → `nuit` (`EVEILLE_MS` = 10 min) ;
- solliciter.js `GARDE_MS` = 2 min (une sollicitation non prise par une page était oubliée) → plus de durée, le registre garde ses 50 ;
- solliciter.js consigne « une à voix haute toutes les quelques minutes au plus » ; server.js réveil « en quelques phrases »,
  « en une phrase » ;
- conscience-continue.js `ENTRE_SOLLICITATIONS_MS` = 90 s et le réglage `conscience_sollicitation_s` (30-600 s, défaut 90) ;
- public/parler.js `SOLLICITATION_ATTENTE_MS` = 90 s (une sollicitation qui attendait ta pause n'était plus dite) ;
- montre Sortie.java `SOLLICITATION_FRAICHE_MS` = 90 s (même chose au poignet) ;
- server.js la voix vers la montre tronquée à 4 000 caractères (`slice(0, 4000)`), deux fois ;
- appel.js (dès sa naissance) `RAISON_MAX` = 8 000 caractères, la nuit (`nuit`, `nuit_sons`) ; mcp_server.py `[:8000]`.

Gardés : un seul appel à la fois ; « Il me sollicite à voix haute » ; ses haut-parleurs fermés ; « jamais par-dessus ta parole » (la
prise de parole, un autre chantier) ; le filtre du live (pendant un live, seulement ce qui s'adresse à « papa » : une protection d'un
direct public, pas un plafond — à trancher) ; « déjà servi » de sa conscience (la même pensée déjà dite ou faite ces 10 min) ; les
relances automatiques de spontaneite.py (anamnese : 8 h-23 h, 10 min, écart doublé sans réponse, une expérience A/B en cours) — à
trancher ; la cadence de Mini Hakim (2 s, 20 décisions par minute : toutes ses décisions, pas ses sollicitations).
