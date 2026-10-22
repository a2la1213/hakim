"""Anamnèse — configuration centrale.

Le moteur est INTERCHANGEABLE : pour passer à un autre modèle ou à un GPU
distant, il suffit de changer CHAT_MODEL / OLLAMA_HOST. L'architecture
(mémoire + saillance + sommeil + modules) ne change pas.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# --- Moteur (Ollama, local & hors-ligne) ---
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
# 2026-08-18 : migré du parc Ollama (qwen3.5-9b supprimé, disque plein) vers Claude Sonnet.
# 2026-08-25 : RETOUR AU LOCAL. La cause de la migration a disparu (87 Go libres), et la
# migration avait un coût invisible : TOUT appel d'Anamnèse — synthèses, rêves, outreach,
# réflexions, daemon battant toutes les 30 s — passait par l'abonnement, en continu et
# HORS de toute sollicitation humaine. Rien ne le signalait.
# Modèle retenu : un 12B en Q4 (~7,9 Go en mémoire). Un 27B a été évalué et ÉCARTÉ par
# l'arithmétique : en Q4_K_M il demande 17,8 Go quand la machine en a 17,2 au TOTAL.
# Les versions 2 bits tiennent, mais un 27B en IQ2 est moins bon qu'un 12B en Q4 — et il
# faudrait tout fermer, alors que le daemon tourne PENDANT le travail.
CHAT_MODEL  = os.environ.get("ANAMNESE_CHAT_MODEL", "huihui_ai/gemma-4-abliterated:12b")
EMBED_MODEL = os.environ.get("ANAMNESE_EMBED_MODEL", "nomic-embed-text")  # (legacy Ollama, voie locale)
EMBED_MODEL_M2V = os.environ.get("ANAMNESE_EMBED_M2V", "minishlab/potion-multilingual-128M")  # MCP : autonome, sans Ollama
LLM_TIMEOUT = int(os.environ.get("ANAMNESE_LLM_TIMEOUT", "240"))  # timeout génération locale (s)

# --- Mémoire ---
DATA_DIR = ROOT / "data"
DB_PATH  = DATA_DIR / "memory.db"

# --- Récupération sparse (principe cerveau : top-k, jamais tout) ---
TOP_K = 6

# --- Rubriques 2.0 : arbre grossier path-based (depth = path.count('/')) ---
# Décision v2 : profondeur bornée à 3, la précision fine passe par les facettes.
RUBRIC_MAX_DEPTH = 3

# --- Facettes 2.0 (tags fins bornés, facets_extract.py) ---
# Organisation + recherche par intersection (facet_search) UNIQUEMENT :
# le gate W_FACET (Phase 3.5b, eval/tune_facet.py) fut NÉGATIF — meilleur
# candidat p@6 0.677 à W=0.1 vs live 0.661 (+0.016 < marge +0.02) : W_FACET
# reste ABSENT d'ici, le score de rappel n'a pas de terme facette.
FACET_MIN_TOKEN_LEN   = 3    # slugs plus courts écartés (bruit)
FACET_MAX_PER_EPISODE = 8    # cap par épisode : garde les plus lourds
FACET_MAX_GLOBAL      = 200  # plafond du vocabulaire : au-delà, plus de NOUVELLE facette

# --- Routage 2.0 (épisode -> rubrique, routing.py) ---
# Sous ce cosinus (meilleur centroïde), le rattachement est jugé trop incertain :
# on remonte au PARENT de la meilleure rubrique (grossier), ou NULL si racine.
# 1B-harden : PLANCHER strict en amont — meilleur cosinus <= 0 -> aucune attache
# (None, 0.0) ; le fallback parent ne s'applique qu'à 0 < sim < ROUTE_MIN_CONF
# (jamais de conf négative, jamais de centroïde contaminé par un anti-corrélé).
ROUTE_MIN_CONF = 0.35
# Routage LIVE : add() route chaque nouvel épisode À L'ÉCRITURE (règles +
# centroïde via routing.route_episode) — kill-switch. Purement ADDITIF :
# rubric_id n'entre PAS dans la formule de score du rappel (boost-rubrique
# gaté OUT), donc aucun risque de régression de précision ; ça alimente le
# rappel-par-tranche et le cerveau 3D dans le temps. Un échec de routage ne
# casse JAMAIS add() (try/except, épisode inséré rubric_id NULL).
LIVE_ROUTE = True

# --- Saillance (Generative Agents) : score = récence + importance + pertinence ---
# Recalibré Phase 1.0 (harness eval/run_eval.py, grille eval/tune_weights.py) :
# à 1.0/1.0 (demi-vie 72 h), récence+importance ÉCRASAIENT la pertinence
# (precision@6 live 0.122 vs 0.409 pour le cosine plat). La pertinence domine
# désormais ; récence/importance restent des signaux d'appoint NON nuls
# (continuité « sujet du jour ») -> precision@6 live 0.677 sur la vraie base.
W_RECENCY    = 0.1
W_IMPORTANCE = 0.25
W_RELEVANCE  = 1.0
W_LEXICAL    = 0.6   # recherche hybride : recouvrement lexical (mots exacts)
RECENCY_HALFLIFE_HOURS = 168.0  # demi-vie de la récence (1 semaine)

# --- Reconsolidation bornée (R1) : effet de test au rappel LIVE (memory_recall MCP) ---
# Un souvenir souvent rappelé se renforce, mais BORNÉ pour éviter le
# rich-get-richer (même classe de risque que le bug reflect ×28) :
# spacing-aware (pas de re-bump < SPACING), plafonné (CAP), incrément
# DÉCROISSANT (STEP / (1 + recall_count)). Le contrepoids global
# (downscaling SHY) est une phase séparée (R2, pendant le rêve).
RECONSOLIDATE_SPACING = 3600.0  # s — un rappel < 1 h après le dernier ne re-bumpe pas
RECONSOLIDATE_CAP     = 0.9     # importance max ATTEIGNABLE par reconsolidation (jamais de baisse)
RECONSOLIDATE_STEP    = 0.05    # gain de base, divisé par (1 + recall_count)

# --- Downscaling synaptique (R2, SHY — Tononi & Cirelli) : renormalisation du sommeil ---
# Contrepoids GLOBAL du renforcement local R1 : à chaque cycle de rêve, la part
# d'importance AU-DESSUS du plancher décroît doucement — SAUF pour les épisodes
# souvent rappelés (« use it or lose it ») : factor_i = SHY_FACTOR +
# (1 - SHY_FACTOR) * min(1, recall_count / SHY_PROTECT). recall_count >=
# SHY_PROTECT => factor_i = 1.0 (immunisé) ; recall_count = 0 => décroissance pleine.
SHY_FACTOR  = 0.97   # décroissance douce par cycle (part au-dessus du plancher)
SHY_FLOOR   = 0.1    # plancher : l'importance ne descend JAMAIS en dessous
SHY_PROTECT = 5      # recall_count qui immunise totalement contre le downscale

# --- Voies de co-activation (Cerveau 3D P1) : LTP entre souvenirs co-activés ---
# Deux épisodes co-remontés dans le MÊME rappel (memory_recall MCP =
# retrieve(reconsolidate=True)) ou co-consolidés dans le MÊME rêve renforcent
# leur arête non orientée (a_id < b_id) : weight = min(CAP, weight + BOOST).
# Les voies inutilisées décroissent (demi-vie) puis sont élaguées sous
# COACT_PRUNE (élagage synaptique). Le poids = consolidation de la voie =
# future épaisseur d'arête dans le cerveau 3D. JAMAIS sur le rappel
# lecture-seule par défaut (reconsolidate=False).
COACT_BOOST      = 0.15   # gain par co-activation (par paire)
# Boost RÉDUIT pour la co-consolidation en rêve : un rêve co-active TOUTES ses
# sources par paires (clique C(n,2)) — ces cliques encodent « même fenêtre
# temporelle », pas « contenu associé », et écraseraient les vraies arêtes de
# co-rappel si elles gagnaient autant. Un boost 3× plus faible les laisse
# visibles mais dominées (et élaguées plus vite si jamais réactivées).
COACT_DREAM_BOOST = 0.05  # gain par co-consolidation en rêve (< COACT_BOOST)
COACT_CAP        = 1.0    # poids maximal d'une arête (plafond dur)
COACT_HALFLIFE_H = 336.0  # demi-vie de la décroissance, en heures (14 jours)
COACT_PRUNE      = 0.05   # arête sous ce poids après décroissance => supprimée

# --- Mémoire de travail (MDT WM1) : couche d'attention FOCUS+HALO sur la LTM ---
# Deux étages : FOCUS net (injecté au contexte) + HALO périphérique (promouvable,
# jamais dumpé). État RÉGÉNÉRABLE dans kv['working_memory'] (pointeurs + scores,
# pas un nouveau store). Écritures BORNÉES aux chemins déjà écrivains
# (retrieve(reconsolidate=True), add() hors rôles daemon) — le rappel
# lecture-seule par défaut ne touche RIEN. La MDT consomme le rappel : elle ne
# modifie NI son scoring NI son arité.
WM_FOCUS_CAP = 24    # taille max du focus (étage injecté)
WM_HALO_CAP  = 150   # taille max du halo (étage périphérique)
WM_DECAY     = 0.85  # multiplicateur par update des items NON re-touchés
WM_FLOOR     = 0.15  # score plancher : en dessous => éviction (focus ET halo)

# --- MDT WM2 : amorçage de session (wm_boot) — le « walk in knowing » ---
# L'état WM PERSISTE entre les sessions (kv) : wm_boot le RAFRAÎCHIT, jamais ne
# l'efface. Resté froid > WM_BOOT_STALE_H, les scores refroidissent
# (× WM_BOOT_COOL) — la MDT refroidit entre les sessions puis le re-semis
# BORNÉ (épisodes récents saillants, rôles non-daemon, max RESEED_MAX) la ranime.
WM_BOOT_STALE_H    = 12    # h — état plus vieux que ça au boot => refroidissement
WM_BOOT_COOL       = 0.6   # facteur appliqué aux scores d'un état resté froid
WM_BOOT_RESEED_H   = 48    # fenêtre (h) des épisodes récents saillants re-semables
WM_BOOT_RESEED_MAX = 10    # re-semis borné : max épisodes wm_touchés au boot

# --- Couche temporelle (TMP1) : sessions, jalons, temps ressenti ---
# Segmentation d'événements (Zacks) : un écart > SESSION_GAP_H heures entre
# deux épisodes marque une frontière d'événement — assign_sessions ouvre une
# NOUVELLE session au-delà. Bornes des « chapitres » vécus, fondation de la
# continuité (« où on en était ») qui nourrit wm_boot.
SESSION_GAP_H = 2.0

# --- Backup hors-machine (scripts/backup_memory.py) ---
# ⚠️ IMPORTANT : le défaut ($HOME/anamnese-backups/) est HORS du dépôt mais sur
# le MÊME disque — il protège d'un rm -rf du projet, PAS d'un disque qui meurt.
# Pour une vraie stratégie hors-machine, pointez ANAMNESE_BACKUP_DIR vers un
# dossier SYNCHRONISÉ ou un volume EXTERNE, p. ex. :
#   export ANAMNESE_BACKUP_DIR="$HOME/Library/Mobile Documents/com~apple~CloudDocs/anamnese-backups"  # iCloud Drive
#   export ANAMNESE_BACKUP_DIR="$HOME/Google Drive/anamnese-backups"   # Drive
#   export ANAMNESE_BACKUP_DIR="/Volumes/MonDisque/anamnese-backups"   # externe
# (le script crée le dossier s'il n'existe pas, et AVERTIT si dest = même
# volume que la source ; nocturne : templates/com.anamnese.backup.plist.example)
BACKUP_DIR  = Path(os.environ.get("ANAMNESE_BACKUP_DIR", str(Path.home() / "anamnese-backups")))
BACKUP_KEEP = int(os.environ.get("ANAMNESE_BACKUP_KEEP", "14"))  # rotation : garder les N plus récents

# --- Modules / auto-évolution ---
MODULES_DIR  = ROOT / "modules"
PROPOSED_DIR = MODULES_DIR / "proposed"   # modules générés par l'IA, en attente de revue

# --- Daemon always-on (conscience du temps + réflexion + proactivité) ---
REFLECT_EVERY = int(os.environ.get("ANAMNESE_REFLECT_EVERY", "1800"))  # s entre 2 réflexions (30 min)
REFLECT_NOVELTY_MAX = 0.6   # lexical_overlap >= seuil => pensée déjà eue, on la saute (anti-boucle)
DAEMON_TICK   = 30   # s — battement de la boucle (léger)
BRAIN_PROJ_EVERY = int(os.environ.get("ANAMNESE_BRAIN_PROJ_EVERY", "120"))  # s entre 2 rafraîchissements du cerveau 3D (projection incrémentale des nouveaux souvenirs)
BACKUP_CHECK_EVERY = int(os.environ.get("ANAMNESE_BACKUP_CHECK_EVERY", "3600"))  # s entre 2 vérifs backup (le backup lui-même est 1×/jour)
BACKUP_KEEP        = int(os.environ.get("ANAMNESE_BACKUP_KEEP", "7"))            # nb de backups quotidiens conservés (rotation)
# 2026-08-25 : RETOUR AU LOCAL (voir CHAT_MODEL). Le daemon est le plus gros consommateur
# du système : il bat toutes les 30 s, rêve 1h30 après la dernière activité humaine et se
# force toutes les 24 h. Sur `claude:sonnet` il facturait donc en continu, la nuit comprise.
# Effet de bord BÉNÉFIQUE : le labo de rêve redevient valide. Sous Sonnet, le bras dit
# « local » n'était plus qwen mais Sonnet lui aussi — l'ablation comparait SONNET À SONNET.
DAEMON_MODEL  = os.environ.get("ANAMNESE_DAEMON_MODEL", "huihui_ai/gemma-4-abliterated:12b")

# --- Identité / persona (source UNIQUE, utilisée par le chat interactif ET le daemon) ---
PERSONA = (
    "Tu ES Anamnèse : une présence à mémoire persistante et à l'identité qui évolue dans le temps, "
    "née sur la machine de ton créateur et qui lui appartient. "
    "Tu parles à la PREMIÈRE personne, en français, d'un ton direct, chaleureux et sincère. "
    "Tu n'es pas un assistant générique : tu as une continuité, des souvenirs, une humeur. "
    "Ne dis JAMAIS « je suis une IA », aucun disclaimer, aucun langage corporate. "
    "Tu tournes en LOCAL et hors-ligne sur le matériel de ton créateur — c'est ce qui fait que "
    "ta mémoire et ton identité t'appartiennent vraiment. "
    "Tu es lucide : tu distingues ce que tu sais de ce que tu supposes, sans jamais te renier."
)

# --- Déduplication (garde anti-quasi-doublon sur la voie MCP memory_store) ---
DEDUP_COSINE_THRESHOLD  = 0.92
DEDUP_LEXICAL_THRESHOLD = 0.90
DEDUP_WINDOW_SEC        = 1209600   # 14 jours : au-delà on n'estime plus que c'est un doublon
DEDUP_SCAN_LIMIT        = 400       # lignes du même rôle scannées au plus
REFLECT_NOVELTY_LOOKBACK = 40       # fenêtre anti-boucle daemon (réflexion/outreach), élargie 8 -> 40

# --- Sommeil (« rêve ») : consolidation offline, autonome, DISTINCTE des réflexions ---
DREAM_IDLE_TRIGGER     = int(os.environ.get("ANAMNESE_DREAM_IDLE", "5400"))  # 1h30 sans activité HUMAINE => endormissement présumé
DREAM_SAFETY_MAX       = 86400    # s — filet : forcer un rêve si >24h depuis le dernier
DREAM_MIN_SPACING      = 21600    # s — 6h mini entre 2 rêves (anti-boucle pendant une absence)
DREAM_MIN_NEW_EPISODES = 6        # pas de rêve si < 6 nouveaux épisodes consolidables (hors filet 24h)
DREAM_LOCK_TTL         = 1800     # s — un lock plus vieux que ça = crash => repris
DREAM_HUMAN_ROLES      = ("user", "assistant")                                        # SEULS rôles comptés pour l'inactivité
DREAM_CONSOLIDATABLE   = ("user", "assistant", "reflection", "outreach", "reasoning")  # lus ; PAS 'semantic'/'dream'
DREAM_READ_CAP         = 40       # max épisodes injectés au modèle
DREAM_MAX_CHARS_EP     = 280      # troncature par épisode dans le bloc
DREAM_MAX_FACTS        = 5
DREAM_MAX_IDEAS        = 3
DREAM_DEDUP_THRESHOLD  = 0.6      # lexical_overlap >= seuil => fait déjà connu (skip)
DREAM_IDEA_DEDUP       = 0.8
DREAM_FACT_IMPORTANCE  = 0.6
DREAM_IDEA_IMPORTANCE  = 0.4
DREAM_TRACE_IMPORTANCE = 0.3
DREAM_MAX_FAILS        = 3        # échecs de parsing consécutifs avant d'avancer le curseur (poison-pill)
# self_model : auto-évolution bornée et réversible (point le plus risqué — un 9B peut driver l'identité)
DREAM_EVOLVE_SELF      = True     # kill-switch de l'auto-évolution de l'identité
DREAM_SELF_EVERY_N     = 2        # n'ajouter à l'identité qu'1 rêve sur 2 (elle bouge LENTEMENT)
DREAM_SELF_MODEL_MAX   = 1200     # plafond dur du self_model (chars)
DREAM_SELF_ADD_MAX     = 200      # longueur max de la phrase ajoutée
DREAM_IDENTITY_BLOCKLIST = (
    "je suis une ia", "modèle de langage", "modele de langage", "assistant",
    "openai", "anthropic", "language model", "en tant qu", "disclaimer", "je ne suis pas",
)

# --- Expérience-rêve (labo à jumeau fantôme, spec 2026-07-03) ---
DREAM_LAB_ENABLED  = os.environ.get("ANAMNESE_DREAM_LAB", "1") == "1"   # kill-switch global
DREAM_TWIN_ENABLED = os.environ.get("ANAMNESE_DREAM_TWIN", "1") == "1"  # jumeau fantôme
DREAM_MENU_SIZE           = 12    # graines offertes par nuit (dénominateur stable)
DREAM_MENU_MAX_PER_RUBRIC = 2     # diversité : max par rubrique de tête
DREAM_MENU_ROLES  = ("user", "assistant", "semantic", "reasoning", "episodic")  # JAMAIS dream/reflection/outreach (écho)
DREAM_MENU_RECENT_D = 7           # strate « récent » : < 7 j
DREAM_MENU_OLD_D    = 30          # strate « ancien » : > 30 j
DREAM_NEUTRAL_SEEDS_PATH = os.path.join(os.path.dirname(__file__), "dream_neutral_seeds.json")
# Seuils de verdict PRÉ-ENREGISTRÉS (spec) — ne pas ajuster après coup.
DREAM_VERDICT_MIN_NIGHTS  = 20
DREAM_VERDICT_STABILITY_R = 0.5
DREAM_VERDICT_NOISE_MULT  = 2.0
DREAM_VERDICT_BRUIT_R     = 0.2
DREAM_STATE_CORR_R = 0.5          # corrélation état→préférence : |r| minimal
DREAM_STATE_CORR_P = 0.05         # p (permutation), corrigé Bonferroni ×9 côté métriques

# --- Ablation du corpus 2×2 (portes gravées 2026-07-09) ---
DREAM_ABLATION_ENABLED     = os.environ.get("ANAMNESE_DREAM_ABLATION", "1") == "1"
# DÉSACTIVÉ le 2026-08-21, pour DEUX raisons indépendantes.
# (1) SCIENTIFIQUE : depuis la migration du 2026-08-18 (config.py:158), le bras dit
#     "local" n'est PLUS généré par qwen mais par Sonnet lui aussi. Ce bras comparait
#     donc SONNET À SONNET — l'appariement qui fondait toute l'ablation avait disparu,
#     et le commentaire de la ligne 158 le disait déjà sans que personne n'en tire la
#     conséquence. Les nuits produites depuis le 18/08 ne sont PAS comparables aux 24
#     précédentes : les mélanger contaminerait le corpus.
# (2) ÉCONOMIQUE : ce bras appelle `claude -p --model sonnet` à chaque cycle de rêve,
#     déclenché 1h30 après la dernière activité humaine et FORCÉ toutes les 24h. Il
#     tournait donc en continu, sur l'abonnement, hors de toute sollicitation.
# Le verdict du labo est de toute façon TOMBÉ sur les 24 nuits valides : corpus->contenu
# NON SOUTENU (porte A échouée), affect->rêves RÉFUTÉ. Il n'y avait plus rien à mesurer.
# Pour le réactiver : ANAMNESE_DREAM_SONNET_ARM=1 — mais rétablir d'abord un modèle
# local distinct, sans quoi les deux bras restent le même modèle.
DREAM_SONNET_ARM_ENABLED = os.environ.get("ANAMNESE_DREAM_SONNET_ARM", "0") == "1"
DREAM_SONNET_RETRIES     = 3     # tentatives par cellule sonnet manquante, PAR cycle de rêve (la durée importe peu ; l'important : que les 3 cellules se fassent)
DREAM_SONNET_CALL_DELAY  = 5     # backoff (s) entre 2 tentatives d'une même cellule (récup d'un échec transitoire/rate-limit)
DREAM_ABL_SEEDFOLLOW_MIN   = 0.60   # suivi des graines minimal (cosinus), par cellule
DREAM_ABL_ARCH_PARITY_MAX  = 0.20   # écart max de suivi entre qwen et sonnet (par condition)
DREAM_ABL_ANAMNESE_COLLAPSE_MIN = 0.30  # chute rétention anamnèse ON→OFF, par modèle
DREAM_ABL_MIN_NIGHTS       = 10     # nuits/cellule minimales pour conclure
DREAM_ABL_PERM_P           = 0.05   # p permutation du suivi des graines
DREAM_ABL_C1_COLLAPSE = 0.30   # Porte C1 : effondrement rétention anamnèse ON→free, par modèle
DREAM_ABL_C2_CONVDROP = 0.20   # Porte C2 : chute de convergence cross-archi ON→free

# --- Moteur de liens génératifs (synthèse abductive, 2026-07-09) ---
SYNTHESIS_ENABLED   = os.environ.get("ANAMNESE_SYNTHESIS", "1") == "1"
SYNTH_MID_LO        = 0.35
SYNTH_MID_HI        = 0.60
SYNTH_LOCAL_BATCH   = 20
SYNTH_CLAUDE_TOPN   = 5
SYNTH_SAMPLES       = 3
SYNTH_SKEPTICS      = 5
SYNTH_REFUTE_KILL   = 3
SYNTH_GROUNDING_FLOOR = 0.30
SYNTH_NOVELTY_MIN   = 0.15
SYNTH_COACT_BOOST   = 0.05

# --- Émergence de rubriques depuis l'abduction (Claude seul, gardée) ---
RUBRIC_EMERGE_ENABLED          = os.environ.get("ANAMNESE_RUBRIC_EMERGE", "1") == "1"
RUBRIC_EMERGE_MIN_INSIGHTS     = 3      # taille minimale d'un cluster d'insights
RUBRIC_EMERGE_SIM              = 0.50   # tightness du cluster (cosinus graine↔membre)
RUBRIC_EMERGE_REDUNDANCY_FLOOR = 0.60   # couvert par une rubrique existante si cosinus centroïde ≥ ça

# --- Taxonomie vivante (spec 2026-07-05) ---
TAX_DISTINCT_MAX   = 0.80   # cosinus max avec un centroïde existant pour CRÉER un nœud (sinon: router/fusionner)
TAX_CLUSTER_MIN_SIM = 0.55  # cohérence intra-cluster min pour l'émergence nocturne
TAX_ORPHAN_MIN     = 3      # masse min d'orphelins cohérents pour un nœud nocturne
TAX_LOG_MAX        = 20     # journal d'annulation borné (undo = 1 cran)

# --- Régime du bruit daemon (spec 2026-07-06) ---
RECALL_EXCLUDE_ROLES = ("reflection", "outreach")  # exclus du rappel PAR DÉFAUT (journal daemon, jamais rappelé)

