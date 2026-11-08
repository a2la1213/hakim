# Cockpit v2 — « Observatoire bioluminescent » : design

- **Date** : 2026-07-03
- **Statut** : design validé par Ahmed (structure multi-vues ; données = explorateur + analytique ; style = fusion « structure Observatoire + lueurs Bioluminescent », maquette validée au visual companion ; inventaire complet préservé ; cerveau 3D restylé).
- **Cible** : `~/AIOS/cockpit/` (Node.js zéro dépendance, non-git — backup obligatoire). Spec versionnée ici (repo anamnese).
- **Maquettes de référence** : `~/AIOS/cockpit/.superpowers/brainstorm/13187-1783063759/content/fusion-v1.html` (validée) et `visual-style.html`.

## Objectif

Refondre le cockpit (localhost:4317) en application multi-vues au design ultra-pro :
un design system unique, 4 vues (Dashboard, Cerveau 3D, Labo des rêves, Mémoire),
la fin définitive du texte tronqué (overlay de détail universel), un labo des rêves
de première classe (verdict intégré, rêve intégral en un clic), et un explorateur +
analytique de la mémoire. 100 % vanilla, offline, lecture seule.

## Design system — tokens (extraits de la maquette validée)

- **Fond** : `radial-gradient(ellipse 80% 50% at 70% -10%, #0b2a2e 0%, #04141a 45%, #030a0c 100%)` + aurores décoratives (radial teal `rgba(45,212,191,.10)` / rose `rgba(249,168,212,.06)`, pointer-events:none).
- **Verre** : cartes `rgba(255,255,255,.035)` + `backdrop-filter: blur(12px)` + bord `1px solid rgba(45,212,191,.14)` (accent fort `.20`, rose `.16`) + `border-radius: 16px`.
- **Couleurs** : primaire teal `#2dd4bf` (clair `#5eead4`, profond `#0d9488`), secondaire rose `#f9a8d4`, succès `#4ade80`, alerte `#fbbf24`, titres `#e6fffa`, corps `#d7efe9`, atténué `#8fb8b0`, éteint `#6d9a94`/`#5e8d87`.
- **Lueurs** : glow teal `box-shadow: 0 0 28px rgba(45,212,191,.45)` (orbe), barres avec `0 0 8px` de leur couleur, inset doux `0 0 40px rgba(45,212,191,.07) inset` sur cartes accentuées.
- **Typo** : système sans-serif pour l'UI ; **la voix d'Anamnèse** (pensées, humeur verbale, rêves) en `Georgia, serif` italique ; monospace UI (`ui-monospace`) pour l'activité/feed. Labels de section : 9-10px, `letter-spacing: 2px`, couleur accent, préfixe glyphe (◈ ◉ ✧ 🌙 ▤).
- **Orbe d'humeur** : sphère radiale `radial-gradient(circle at 35% 30%, #5eead4, #0d9488 55%, #043a38 90%)` + double glow ; sa teinte glisse avec la valence (teal→rose selon négatif/positif), sa pulsation (animation lente) suit l'arousal.
- **Nav** : barre top — point pulsant teal + « AIOS » + pills (`DASHBOARD · CERVEAU 3D · LABO DES RÊVES · MÉMOIRE`, active = fond `rgba(45,212,191,.10)` + bord `.35`) + à droite statut monospace (`● daemon · consolidation Xh · HH:MM:SS`).
- **Responsive** : bento grid en `grid-template-columns` fluides, dégrade en 1 colonne < 900px.

## Les 4 vues

### 1. Dashboard (`index.html` + `app.js`) — refonte de la maquette validée
Bento grid : Humeur (orbe + valence/arousal + 9 barres neuromodulateurs) · Activité
live (SSE existant, feed monospace à bord coloré par type) · Pensées internes (serif
italique, extrait + « ▸ lire tout » → overlay) · bandeau Labo des rêves (verdict badge
+ mini-courbe divergence/bruit + lien vue Labo) · Mémoire (sparkline volume/jour + top
rubriques + mémoires récentes cliquables) · Sessions Claude Code (+ clic → conversation
agent via `/api/agent`, overlay) · Inventaire actif (carte compacte : compteurs MCP/
skills/agents/CLIs/plugins, dépliable).

### 2. Cerveau 3D (`brain.html` + `brain.js`) — habillage + restyle matériaux
- **Mécanique INTACTE** : three.js vendored, OrbitControls, raycaster, toggles affect/WM,
  tooltip daté, clic → détail souvenir, `/api/brain` inchangé.
- **Restyle** : fond abysse + fog de profondeur ; nœuds émissifs (teinte par région,
  saturation/luminosité modulée par valence/importance — bioluminescence, pas de bloom
  post-processing coûteux : matériaux émissifs + sprites de halo) ; arêtes en filaments
  dont opacité/épaisseur suivent `weight` (les voies consolidées brillent) ; focus WM =
  pulsation douce (scale sinusoïdale), halo WM = lueur ténue ; panneaux (légende,
  toggles, détail) au style verre du design system.
- **Budget FPS** : pas pire qu'aujourd'hui sur le M4 ; tout effet qui coûte saute.

### 3. Labo des rêves (`dreams.html` + `dreams.js`) — refonte + enrichissement
- Tout l'existant conservé (nuits, réel/fantôme côte à côte, graines choisies
  surlignées, heatmap sur-choix, courbes divergence/appétit/dopamine + bande de bruit,
  volet Sonnet) restylé design system.
- **Nouveau** : panneau « Verdict » en tête — le rapport de `dream_metrics.report()`
  via `GET /api/dreams/verdict` (même source de vérité que le CLI, jamais de calcul
  dupliqué côté JS pour le verdict) ; badge du label (INSUFFISANT amber / RÉFUTÉ rouge /
  BRUIT gris / PLAUSIBLE teal / PROUVÉ vert lumineux).
- **Rêve intégral en un clic** : le détail de nuit (existant) passe dans l'overlay
  universel — texte complet non tronqué, état, menu, métadonnées.

### 4. Mémoire (`memory.html` + `memory.js`) — NOUVELLE vue, deux onglets
- **Explorateur** : barre de recherche plein texte + filtres (rubrique — arbre depuis
  `rubrics.path` —, facette, rôle, plage de dates, importance min) ; liste de résultats
  (extrait, rubrique, date, importance, badges facettes) ; clic → overlay texte intégral.
  Pagination simple (limit/offset).
- **Analytique** : courbes SVG maison (aucune lib) — (a) humeur encodée dans le temps :
  `enc_valence`/`enc_arousal` moyens par jour (l'historique existe déjà dans episodes),
  (b) croissance mémoire (épisodes/jour, aire empilée par rôle), (c) top 15 facettes
  (barres), (d) répartition par rubrique de tête (barres), (e) activité des rêves
  (nuits/appétit depuis dream_log).

## L'overlay de détail universel (`detail.js`) — la fin du texte tronqué

Un seul composant partagé par les 4 vues : panneau verre plein écran (fermeture Échap/
clic dehors), affiche texte INTÉGRAL + métadonnées (date, rôle, rubrique, facettes,
importance, valence/arousal, recall_count) + actions contextuelles (« voir dans le
cerveau » quand pertinent). Sources : `/api/memory?id=` (existant) pour épisodes/pensées/
mémoires ; `/api/dreams?night=` (existant) pour les nuits ; `/api/agent?file=` (existant)
pour les conversations. Les listes gardent leurs extraits tronqués (perf), chaque item
porte désormais son `id`.

## Serveur (`server.js`) — additif uniquement, patterns existants

- `GET /api/dreams/verdict` → `{text}` : exécute `dream_metrics.report()` via le python
  du venv anamnese (`execFile`, timeout, cache 60 s — le rapport fait des permutations).
- `GET /api/episodes?q=&rubric=&facet=&role=&from=&to=&min_imp=&limit=&offset=` →
  liste `{id, ts, role, snippet(200), rubric, importance, facets[]}` ; params validés
  par regex/Number AVANT interpolation (pattern `/api/dreams`) ; `q` passé en paramètre
  `?` via `sqlite3` CLI n'étant pas paramétrable → échapper les `'` en `''` ET
  restreindre aux caractères sûrs ; LIMIT plafonné 200.
- `GET /api/analytics` → séries pré-agrégées SQL (jour, compte, moyennes) ; lecture seule.
- `/api/anamnese` : ajoute `id` à chaque pensée/mémoire (aujourd'hui tronquées sans id
  — cause racine du bug « texte tronqué »).
- Routes pages : `/memory` → memory.html (pattern `/brain`, `/dreams`).

## Inventaire de préservation (contrainte dure — rien ne disparaît)

Humeur 9D + valence/arousal · activité live SSE · inventaire actif (MCP/skills/agents/
CLIs/plugins) · pensées internes · sessions Claude Code + conversations agents ·
mémoires récentes · cerveau 3D complet (toutes fonctions actuelles) · page rêves
complète (toutes fonctions actuelles) · horloge + statut daemon/connexion.

## Ce qu'on ne fait PAS (YAGNI)

Pas de framework ni build step ni dépendance (offline strict ; three.js déjà vendored) ·
pas d'auth (localhost) · pas d'écriture en base depuis le cockpit (lecture seule
absolue) · pas de refonte de la mécanique three.js ni du serveur SSE · pas d'assets
générés (images/vidéos) : le style est 100 % code (SVG/CSS/canvas).

## Gardes qualité

- **Backup complet AVANT** : `cp -R ~/AIOS/cockpit ~/AIOS/cockpit.backup-pre-v2`.
- **`esc()` partout** : toute valeur dynamique injectée en innerHTML/attribut est
  échappée (leçon de la review expérience-rêve). Le helper vit dans `nav.js`
  (chargé en premier sur les 4 vues) et est exposé en global (`window.esc`).
- Params serveur validés avant interpolation ; endpoints lecture seule (`-readonly`).
- Chaque vue vérifiée navigateur (Playwright : rendu + **zéro erreur console**).
- Budget FPS cerveau 3D : ≥ actuel ; profiler avant/après si doute.
- `prefers-reduced-motion` : pulsations/aurores coupées.
- Contraste : texte corps ≥ 4.5:1 sur les fonds de carte (vérifié sur les tokens).

## Fichiers

| Fichier | Rôle |
|---|---|
| `public/theme.css` (create) | design system complet (tokens, verre, nav, overlay, responsive) |
| `public/nav.js` (create) | shell : nav + horloge + statut + `esc()` partagé |
| `public/detail.js` (create) | overlay de détail universel |
| `public/index.html` + `app.js` (rewrite) | dashboard bento |
| `public/brain.html` + `brain.js` (restyle) | habillage + matériaux bioluminescents |
| `public/dreams.html` + `dreams.js` (restyle+) | labo + verdict intégré |
| `public/memory.html` + `memory.js` (create) | explorateur + analytique |
| `server.js` (modify, additif) | 3 endpoints + ids + route /memory |
| `public/styles.css` (delete après migration) | remplacé par theme.css |

## Phases

| Phase | Contenu | Vérification |
|---|---|---|
| **V2-1** | backup + theme.css + nav.js + detail.js + endpoints serveur | curl endpoints + page témoin |
| **V2-2** | Dashboard refondu (inventaire de préservation complet) | Playwright + SSE vivant |
| **V2-3** | Vue Mémoire (explorateur + analytique) | recherches réelles + overlay |
| **V2-4** | Labo des rêves refondu + verdict | rendu + verdict == CLI |
| **V2-5** | Cerveau 3D restylé | FPS + toutes fonctions actuelles |

## Honnêtetés

- Le cockpit est non-git : la traçabilité = backup daté + `.dreams-report.md`-style
  (`.v2-report.md` par phase). Les reviews travaillent sur diffs manuels.
- `/api/episodes` avec `q` libre : la sécurité repose sur l'échappement + charlist +
  readonly — surface localhost uniquement, documenté.
- L'« historique d'humeur » analytique est un PROXY (valence/arousal encodés des
  épisodes au moment de l'écriture), pas un échantillonnage continu du kv affect —
  affiché comme tel dans l'UI.
- La page `/dreams` vient d'être livrée : la refonte V2-4 la restyle sans toucher à
  la logique des données (formules identiques, aucune re-dérivation).
