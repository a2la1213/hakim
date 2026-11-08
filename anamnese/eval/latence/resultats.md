# Latence d'un tour oral — backtest sur les journaux (28/10, ~10:50)

Demande d'Ahmed (10:29, via Hakim) : accélérer la préparation, l'oreille et la voix sans rien couper ; puis « un backtest au
lieu d'attendre ». Scripts : `backtest_preparation.py`, `backtest_voix_oreille.py` (ils relisent ~/AIOS/jarvis/*.jsonl).

| Étape (200 derniers tours au téléphone) | Médiane | 90 % des tours sous |
|---|---|---|
| attente de la fin de tour d'Ahmed | 2,0 s | 2,1 s |
| transcription (Whisper) | 4,3 s | 11,1 s |
| préparation du cockpit | 6,6 s | 11,0 s |
| cerveau jusqu'au premier mot | 3,8 s | 9,4 s |
| voix, du premier mot au premier son | 3,1 s | 6,4 s |

**Préparation : 90 % du temps est le rappel de mémoire, et surtout son tri.** Le tri est un Sonnet à part (`claude -p`) qui
lit le dossier du thème (jusqu'à ~500 lignes). Il a tourné dans 145 tours sur 200 : 7,0 s en médiane, 10,0 s au 9e décile.
Hors rappel, la préparation ne prend que 0,4 s en médiane. Un appel du tri avec un message vide prend déjà 3,0 à 3,4 s
(mesuré 3 fois), dont 0,05 s de démarrage de l'outil. Il y a donc environ 3 s d'aller-retour fixe, plus environ 4 s de
lecture.

**Voix (Chatterbox).** Fabriquer un morceau prend environ 1,54 s + 0,49 × la durée du son (moindres carrés sur 6 000
morceaux). Le coût fixe domine : un premier morceau plus court gagnerait au plus environ 0,9 s. Les 30 débuts de réponse
les plus fréquents (« frérot, », « oui, », « oui frérot, », « d'accord, »…) couvrent 41 % des 1 500 dernières réponses.

**Oreille (Whisper).** L'hypothèse « une voix en cours de fabrication fait attendre la transcription » est réfutée : ça
n'arrive que dans 4 tours sur 163. La longue queue (11 s) reste inexpliquée. Les journaux ne disent ni la durée de la
phrase d'Ahmed ni le temps passé sur le réseau : la mesure côté serveur (cockpit afa86de) le dira une fois allumée.

## Les essais (28/10, ~10:55-11:40)

**Le tri, autre modèle ou autre réglage** (`tri_modeles.py`, critères figés avant ; 35 requêtes-vérité, N = 500).
| | garde | au bout du compte | numéros inventés | temps médian |
|---|---|---|---|---|
| Sonnet (le direct) | 0,981 | 0,949 | 0 | 5,4 s |
| Haiku | 0,904 | 0,874 | 18 | 4,8 s |
| Sonnet, effort bas | 0,978 | 0,948 | 0 | 5,0 s |
- Haiku échoue aux quatre critères : Sonnet reste.
- L'effort bas garde la même qualité, mais il ne gagne que 7 % : T4 (au moins 30 % plus rapide) échoue. Selon la règle figée, il n'est pas adopté. C'est à Ahmed de trancher s'il veut ces 0,4 s.

**Le coût fixe d'un appel du tri** (environ 3 s, même pour une question vide) :
- C'est surtout l'aller-retour avec l'API, et il varie beaucoup (de 0,8 à 4 s).
- Lancer le processus d'avance n'aide pas : sans rien sur son entrée, il s'arrête au bout de 16 s ; avec une ligne écrite d'avance, il répond en 2,7 à 6,1 s, comme à froid.
- Pas de réflexion cachée (3 jetons de sortie).
- Couper le trafic accessoire de l'outil (`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`) fait gagner environ 0,15 s hors API : adopté.

**La voix, profil hors ligne** (une copie du modèle) :
- Fabriquer un morceau prend 1,0 à 2,0 s.
- Le rognage, l'étirement du rythme et les mesures du son prennent moins de 0,02 s à eux trois.
- La préparation de la voix de référence est déjà faite une seule fois.

**L'oreille, profil hors ligne** (12 sons gardés de sa voix, de 0,7 à 5,9 s) :
- La lecture du son prend 0,07 s.
- **La détection de la langue prend 1,1 s, à chaque fois, même quand la langue est imposée.** Elle sert alors seulement à reconnaître le silence et le bruit.
- Whisper lui-même prend de 1,0 à 1,7 s.
- L'empreinte, la prosodie et le ton prennent de 0,02 à 0,65 s.
- Aucun repli de température sur ces sons.
- Une piste mesurée à valider avant d'y toucher : reconnaître le silence autrement (avec un modèle minuscule, ou avec la probabilité de non-parole que rend Whisper). C'est environ 1 s de moins par transcription. Il faut d'abord un banc avec de vrais silences et de vrais bruits.
