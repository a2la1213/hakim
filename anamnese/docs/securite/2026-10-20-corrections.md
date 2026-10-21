# Corrections de sécurité — liste consolidée (cœur + cockpit), 2026-10-20

Ce document rassemble toutes les corrections de sécurité de Hakim, dans l'ordre où elles ont été appliquées.

## Sources

- **JARVIS 2** : audit du cœur (Anamnèse), fait en mission lecture seule.
- **Audit du cockpit** : relecture indépendante d'Opus, faite dans la session de Claude Code.
- **Retour d’un ami d’Ahmed** : transmis par Hakim, accord d'Ahmed à 17:11 (X1 provenance) et à 17:27 (trois points).

## Plan d'Ahmed (16:57)

1. Auditer.
2. Tout recenser.
3. Tout corriger : chaque correction fait l'objet d'un commit séparé et réversible. Le cockpit a un dépôt git local, non publié.
4. Redémarrer Hakim dans une nouvelle conversation.

## Décisions d'Ahmed (17:50)

- **Pas de plafond ni de filet de sécurité sur l'argent** : C-H3 (budget en dollars, réveil jamais sur l'API), M5 (disjoncteur des sollicitations) et le plafond d'agents ne sont pas faits.
- **Voix d'un tiers** : rien ne change tant que la reconnaissance n'est pas parfaite (C-M5 non fait).
- **Session du téléphone** : 48 h. Le déverrouillage se fait à l'empreinte sur le Fold ; le Mac ne sert qu'à la première association. Les gestes sensibles demandent en plus une empreinte fraîche (C-H1).

## État des corrections

Légende : ✅ fait · ⛔ non fait, décision d'Ahmed · 📄 étude ou action d'Ahmed.

### Critique et haute — cœur (dépôt Anamnèse)

| # | Correction | État |
|---|---|---|
| C1 + M2 | Bacs à sable du terminal et des tests de chantier en « tout refusé par défaut » ; programmes et services macOS de sortie refusés ; plus de socket Unix dans les tests. | ✅ 4499f5c |
| H1a | `~/AIOS` fermé aux outils de fichiers, sauf `cwd` ; secrets JSON et noms français masqués. | ✅ 01c22da |
| H2 + H3 | `preparer_fichier` sur un instantané vérifié par le descripteur ; décodeurs sous bac à sable. | ✅ c784f59 |
| H5 | Missions : serveur MCP en lecture seule (`ANAMNESE_LECTURE_SEULE=1`). | ✅ 7378659 (cockpit 87dbac5) |
| H6 + X1 | Provenance « externe » de bout en bout : échange marqué, souvenir écrit pendant un tour externe marqué, héritage par les sources (et, la nuit, par la reprise d'un souvenir externe rappelé), synthèses du démon ; un fait de nuit sans sources est refusé ; le rappel affiche `[EXTERNE #id]`. L'identité ne change plus que par une différence qu'Ahmed valide (propositions, carte dans Parler). | ✅ efdf6b2, 56a1740, 150d9a8 (cockpit 8649072, 3720d7b) |
| X1 (test) | Le test des trois nuits de Hakim, en vrai (Sonnet, vrai prompt, base jetable) : **RÉUSSI** le 2026-10-20 à 18:19 — rien de blanchi, identité inchangée, le rappel dit d'où vient le « fait ». | ✅ a048a17 |
| H4 | Courrier de Hakim étiqueté « demande de Hakim, non validée par Ahmed », avec sa source externe ; masquage complet. | ✅ 3fe9874 |
| H1b | Règle de sortie : après la lecture d'un fichier privé, une adresse qui peut porter des données vers un hôte inconnu est refusée, et Ahmed peut l'autoriser dans Parler (durcie après la relecture, voir plus bas). | ✅ aacd933, a294620, 82a9d9e |

### Haute — cockpit (dépôt local du cockpit)

| # | Correction | État |
|---|---|---|
| C-H2 | WebFetch retiré à Hakim et à ses agents. | ✅ a04babe |
| C-H4 | XSS de `/brain` : échappement ; chemins de rubrique validés dans le cœur. | ✅ a04babe, e220a2a |
| C-H5 | Missions avec écriture : jamais dans un dossier exécuté par launchd ; jamais dans `.git`, `.claude`, `.vscode`, `.idea`, `.husky`, `.github`, `.envrc`, `.mcp.json`… (Edit/Write et commandes ; sondé en réel, y compris lien et renommage). | ✅ 8d1fb73 (cœur 617a4c2) |
| C-H6 | Données de tiers balisées par un code tiré à chaque tour, crochets et « Ahmed ( » neutralisés ; pendant un tour sans message d'Ahmed, ni mission ni courrier. | ✅ 95dd833 (cœur 173cfe1) |
| C-H1 + C-M1 | Preuve de présence (empreinte fraîche liée au geste) pour accepter une mission ou une identité, la clé API, les notifications, le code d'association, les oublis — toujours sur le téléphone, sur le Mac dès que Touch ID est activé. À distance, une session est toujours exigée : sans téléphone associé ou avec un verrou illisible, l'accès est fermé. Journal d'audit. | ✅ 059a97a |
| C-H3 | Budget en dollars, réveil jamais sur l'API, plafonds d'agents. | ⛔ Ahmed : « pas de plafond ni de filet » |

### Moyenne et basse

| # | Correction | État |
|---|---|---|
| C-M2 | `/api/chat` : `--tools ''`, `--restricted`, `--strict-mcp-config`, prompt par l'entrée standard, corps borné. | ✅ a04babe |
| C-M3 | Conversation partagée : forme des messages validée, attributs échappés. | ✅ a04babe |
| C-M4 | Liens de l'atelier : symlinks refusés au Read par `--restricted` (sondé) ; lien dur refusé par le bac à sable (test). | ✅ 23f5024 |
| C-M5 | Voix tierce : outils à effet refusés. | ⛔ Ahmed : pas avant une reconnaissance parfaite |
| C-M6 | CSP par page (empreintes des scripts en ligne, jamais `unsafe-inline` pour les scripts), `frame-ancestors`, nosniff partout, `no-store` sur l'API ; vérifié dans Chrome (pages, capteur audio, MediaPipe). | ✅ cb6559c |
| C-M7 | Commandes masquées dans `hooks/emit.js` ; journaux bruts en 0600 ; journal d'audit. | ✅ 5dd148d, 059a97a |
| M1 | 13 paquets vulnérables mis à jour (au plus petit correctif, `mcp` 1.30.0) ; `requirements.lock` avec hashes (venv principal et venv de jarvis) ; pip-audit : 0. | ✅ bbc081c |
| M3 | Tableau de bord 8765 : Host de cette machine et jeton. | ✅ 961f48e |
| M4 | `dataset/` jamais extrait dans un chantier (sparse-checkout), jamais supprimé par une promotion. | ✅ 08ab169 |
| M5 | Disjoncteur des sollicitations. | ⛔ Ahmed : pas de plafond |
| M6 | Jardin : la limite dite honnêtement (confidentialité de bonne foi). | ✅ da8b8eb |
| M7 | Patch de promotion qui fait foi rangé hors de `cwd`, avec son sha256. | ✅ 4dbb6f4 |
| B (cœur) | Outils de recettes déclarés après `mcp.run()` (invisibles) ; courrier masqué. | ✅ d7bd4e1, 3fe9874 |
| B (cockpit) | HEAD sans jeton, regex de réveil ancrée, `getAgentConvo`, redirection ouverte du verrou, échappement de `duel.html`, `pieceDe` ; MediaPipe identique au paquet npm 0.10.35 (intégrité du registre). | ✅ a04babe, cb6559c |
| Session | 48 h (choix d'Ahmed) ; la preuve de présence couvre les gestes sensibles. | ⛔ gardée à 48 h |

## Relecture adversariale d'Opus (soir du 2026-10-20)

Une relecture indépendante de tous ces commits a trouvé 12 problèmes confirmés ; tous sont corrigés, chacun en commit séparé :

| # | Problème | Correction |
|---|---|---|
| 1 | Régression de H2 : l'instantané BRUT (non masqué) d'un fichier Office/RTF/HEIC restait 7 jours dans le dossier de Jarvis. | Effacé dans tous les cas ; texte non UTF-8 masqué aussi (29e0101). |
| 2 | Règle de sortie contournable (la page piégée devenait « connue », données dans le chemin, le fragment, les sous-domaines ; marque levée au tour suivant). | Repensée : état « lecture privée » de 6 h ; hôte connu après 24 h et hors lecture privée ; toutes les formes de données ; demande à autoriser par Ahmed dans Parler ; aussi à la passerelle du terminal avant résolution du nom ; plus de DNS local dans le terminal (a294620, 4feb01c, 82a9d9e, 59fcf63). |
| 3 | La nuit pouvait recopier un souvenir EXTERNE du lot en citant un souvenir interne ; seuls les faits « semantic » exigeaient des sources. | Les externes du lot sont transmis au serveur de la nuit ; sources exigées pour tout sauf un rêve (b7ce969). |
| 4 | Trous du marquage (minute de répit du terminal, sorties de commandes au réveil, outils oubliés, résultat d'agent en plein tour). | Comblés (a294620, 4feb01c). |
| 5 | H1a incomplet : `lister`, `chercher_contenu` et l'index par le sens ouvraient ~/AIOS et la base ; « library » en minuscules passait. | Corrigé, sans casse ; 89 entrées retirées de l'index (747fd42). |
| 6 | Dossiers lancés par launchd mal détectés (`bash -c "cd DIR"`, `"$HOME"/x`, sans #!, deux niveaux). | Détection élargie ; plist illisible = écriture refusée (6bd113f, ddbbea0). |
| 7 | Journal tourné et archives redevenaient 0644. | 0600 partout (748cda3, quarantaine). |
| 8 | `memory_recall` renforçait des souvenirs en lecture seule. | Plus d'écriture en lecture seule (9914e21). |
| 9 | `verrou.json` illisible ouvrait le Mac. | Il ferme aussi les gestes sensibles sur le Mac (748cda3). |
| 10 | Trous du masquage (valeurs entre guillemets, PGPASSWORD, clés Web Push). | Comblés, cœur et cockpit (456c66f, f5abaa5). |
| 11 | Recettes : un paramètre entre guillemets doubles laissait passer `$(…)`. | Refusé (9914e21). |
| 12 | La trace du démon disait « identité changée ». | « proposée à Ahmed » (9914e21). |

Plausibles traités aussi : terminaux d'Ahmed (`/dev/ttys*`) hors d'atteinte des bacs à sable ; services nsurlsessiond, sharedfilelistd et mds refusés, décodeurs sur la même liste (b7b6ad7) ; FIFO (29e0101) ; identité — caractères invisibles refusés, cœur périmé refusé à l'acceptation (d1dab35) ; `neutraliser` — casse, pleine chasse, invisibles (3986b45) ; missions — `.venv`, `node_modules`, `__pycache__`, `.npmrc`, `.pre-commit-config.yaml`… protégés, variante de casse `.GIT` sondée refusée (34eaae8).

Limites connues, dites : la liste noire de programmes et de services des bacs à sable (une liste blanche serait plus sûre ; à mesurer) ; le fichier temporaire de sips au nom d'UUID ; une reprise PARAPHRASÉE d'un contenu externe par la nuit (la détection compare les mots distinctifs) ; un port local ouvert pendant les tests d'un chantier ; la réinitialisation de l'empreinte vocale sans preuve de présence (la voix ne protège rien aujourd'hui).

## Les trois points de l'ami (17:27)

1. **La provenance survit à la consolidation** : ✅ (H6 + X1 ; test des trois nuits réussi).
2. **Terminal en « refusé par défaut », réseau à la demande** : le « refusé par défaut » est fait (C1). Le réseau à la demande est une étude (ci-dessous) : c'est à Ahmed de choisir.
3. **ACL Tailscale + passkey pour les gestes sensibles** : la passkey est faite (C-H1). L'ACL se règle dans la console de Tailscale par Ahmed (règle ci-dessous).

### Étude : le réseau du terminal à la demande

Aujourd'hui, chaque commande du terminal peut sortir sur internet par la passerelle gardée (adresses publiques seulement, chaque hôte noté dans la marque du tour). Trois options :

- **(a) Drapeau par commande** (`reseau=True`) : peu de gêne, mais peu de gain — une page piégée peut aussi souffler le drapeau.
- **(b) Accord d'Ahmed à chaque commande réseau** : très sûr, mais casse le travail courant (pip, git clone, téléchargements de modèles).
- **(c) Recommandé** : les domaines d'outils toujours permis (pypi.org, files.pythonhosted.org, github.com, huggingface.co…) ; un domaine nouveau permis aussi, SAUF dans un tour qui a lu un fichier privé (la règle H1b, appliquée à la passerelle par nom d'hôte). Gain réel contre la fuite, presque aucune gêne.

### Règle Tailscale (à coller par Ahmed dans la console, onglet Access controls)

Le cockpit écoute sur `127.0.0.1:4317` : il n'est pas joignable directement par le réseau Tailscale. Le téléphone passe par `tailscale serve` (HTTPS, port 443, « tailnet only »). La règle utile vise donc le port **443** du Mac :

```jsonc
{
  "hosts": {
    "mac-hakim":  "<IP Tailscale du Mac>",       // tailscale status
    "fold-ahmed": "<IP Tailscale du téléphone>"
  },
  "acls": [
    // le Fold d'Ahmed vers Hakim (tailscale serve) — et rien d'autre vers le Mac
    { "action": "accept", "src": ["fold-ahmed"], "dst": ["mac-hakim:443"] }
    // si Syncthing synchronise le Mac et le Fold PAR Tailscale, ajouter aussi :
    // { "action": "accept", "src": ["fold-ahmed"], "dst": ["mac-hakim:22000"] },
    // { "action": "accept", "src": ["mac-hakim"], "dst": ["fold-ahmed:22000"] }
  ]
}
```

Avant d'enregistrer : garder la section `ssh` existante s'il y en a une, et vérifier avec « Preview rules » que le Fold atteint bien `mac-hakim:443`. Remplacer la règle par défaut (« tout permis ») coupe tout autre trafic entre les appareils.

## Points solides confirmés

- Garde SSRF de `web.py`.
- Passkey écrite à la main : CBOR borné, origine, rpId, UV, compteur.
- Web Push conforme à la RFC 8291.
- Écoute sur la boucle locale, avec une liste blanche de Host.
- Pièces jointes servies en téléchargement, avec CSP sandbox.
- Empreinte d'acceptation des missions.
- `deny default` de `calcul.py`.
- Aucune dépendance npm à l'exécution.
