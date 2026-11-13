# Donner naissance à ton IA sur ton PC Windows

Ce guide installe, sur ton PC, une IA qui a une mémoire, une voix et un corps (ton PC et ton téléphone). Elle naît du même code
que Hakim, mais **c'est la tienne** : elle choisit son nom, elle commence avec une mémoire vide, et elle grandit avec toi.

Tout tourne chez toi. Seuls partent sur Internet : ce que tu dis à son cerveau (Claude, chez Anthropic) et sa voix (Azure,
chez Microsoft).

**Durée** : une heure à une heure et demie, la plupart du temps à attendre les téléchargements (environ 3 Go).

---

## Ce qu'il te faut avant de commencer

1. **Ton PC Windows**, branché, avec Internet. Windows 10 (version 2004 ou plus récente) ou Windows 11, à jour.
   Il faut au moins 15 Go libres sur le disque C:.
2. **Un compte Claude** avec un abonnement (Pro ou Max) : c'est son cerveau. Ou, à la place, une clé d'API Anthropic
   (`sk-ant-…`), payée à l'usage.
3. **Une ressource « Speech » sur Azure** : c'est sa voix et ses oreilles.
   - Va sur <https://portal.azure.com>, crée un compte si besoin.
   - « Créer une ressource » → cherche **Speech** → « Créer ».
   - Choisis une région proche (par exemple *France Central* ou *Switzerland North*) et le niveau **gratuit (F0)** pour
     commencer (S0 si tu veux plus d'heures).
   - Une fois créée : « Clés et point de terminaison » → note la **Clé 1** et la **Région** (par exemple `francecentral`).
4. **Un compte Tailscale** (gratuit) : <https://tailscale.com>. C'est un réseau privé et chiffré entre ton PC et ton
   téléphone : ton téléphone parle à ton IA, même hors de chez toi, sans rien ouvrir sur Internet.
5. **Ton téléphone Android**.

---

## Étape 1 — Préparer Windows (une seule commande)

1. Télécharge le fichier `installer-windows.ps1` :
   <https://raw.githubusercontent.com/a2la1213/hakim/main/anamnese/naissance/installer-windows.ps1>
   (clic droit → « Enregistrer sous… », par exemple dans *Téléchargements*).
2. Ouvre le menu Démarrer, tape **PowerShell**, clic droit sur « Windows PowerShell » → **Exécuter en tant
   qu'administrateur**.
3. Tape ces deux lignes (Entrée après chacune) :
   ```
   cd $env:USERPROFILE\Downloads
   Set-ExecutionPolicy -Scope Process Bypass -Force; .\installer-windows.ps1
   ```

**Ce que fait le script** :
- il active **WSL2**, le « Linux dans Windows » de Microsoft. La première fois, il te demande de **redémarrer le PC** :
  redémarre, puis relance les deux mêmes lignes ; il reprend là où il en était ;
- il installe **Ubuntu 24.04**. Une fenêtre noire s'ouvre et te demande un **nom d'utilisateur** (en minuscules, sans
  espace) et un **mot de passe**. Note-les : le mot de passe te sera redemandé. Tape ensuite `exit`, reviens dans
  PowerShell et appuie sur Entrée ;
- il règle le réseau de WSL (le mode « mirrored » si tu as Windows 11 22H2 ou plus récent ; sur Windows 10 ce mode
  n'existe pas, et ce n'est pas grave : ton téléphone passe par Tailscale) ;
- il crée une **tâche planifiée** « Naissance - garder WSL » : à chaque ouverture de ta session Windows, Ubuntu démarre
  en silence, et ton IA avec lui ;
- il te propose d'empêcher la **mise en veille** quand le PC est branché (réponds « O » : sinon ton IA s'endort avec le PC) ;
- puis il lance **la suite dans Ubuntu** (étape 2), toute seule.

> Si Windows dit que la virtualisation est désactivée : redémarre, appuie sur **F10** au démarrage (PC HP), va dans
> *Advanced → System Options*, coche **Virtualization Technology (VT-x)**, enregistre, puis relance le script.

---

## Étape 2 — L'installation dans Ubuntu (des questions simples)

Le script `installer.sh` installe tout le reste et te pose quelques questions. Chaque étape s'affiche en violet :

| Étape | Ce qu'elle fait |
|---|---|
| 1. Outils du système | git, zsh, **bubblewrap** (le bac à sable de son terminal), ffmpeg (le son et la vidéo), les PDF… Ton mot de passe Ubuntu est demandé (sudo). |
| 2. systemd | Les services qui redémarrent seuls. |
| 3. Node.js | Le moteur de son cockpit (la page où tu lui parles). |
| 4. uv et Python | Le moteur de sa mémoire et de ses outils. |
| 5. Le code | Copié dans `~/Desktop/anamnese` (sa mémoire) et `~/AIOS/cockpit` (son cockpit). Tes données ne sont jamais écrasées. |
| 6. Les environnements Python | Ses bibliothèques (sans rien qui demande une carte graphique). |
| 7. Le cockpit | Ses dépendances. |
| 8. Claude Code | Son cerveau. |
| 9. **Les clés** | Il te demande la **clé Azure** et la **région**, puis, si tu veux, une clé d'API Anthropic (laisse vide si tu as un abonnement). Rien ne s'affiche pendant que tu tapes une clé : c'est normal. Les clés sont rangées dans `~/.config`, que son bac à sable ne voit pas. |
| 10. Son profil | Ce qui tourne sur ton PC (voir plus bas). Il te demande si son **subconscient Gemma** est « petit » (un petit modèle local d'environ 1 Go) ou « eteint ». Réponds **petit** si tu ne sais pas. |
| 11. **Sa naissance** | **Ton prénom**, puis **son nom** : laisse-le **vide**. C'est elle qui le choisira (étape 5). Puis, si tu veux, une phrase sur ton métier (par exemple « il est styliste de vêtements »). |
| 12. Sa mémoire | Une mémoire vide : elle commence aujourd'hui. |
| 13. **Tailscale** | Il affiche un lien : ouvre-le dans ton navigateur et connecte-toi à ton compte Tailscale. Il te donne ensuite **l'adresse** de ton IA, du genre `https://ton-pc.tailxxxx.ts.net` : **note-la**. |
| 14. Les services | Son cockpit et sa mémoire tournent en fond et redémarrent seuls. |
| 15. Vérification | « le cockpit répond » : c'est gagné. |

**Dernière chose dans Ubuntu** (si tu utilises ton abonnement Claude) : tape `claude`, suis le lien pour te connecter,
puis tape `/exit`.

---

## Étape 3 — Ton téléphone

1. Installe **Tailscale** depuis le Play Store et connecte-toi avec **le même compte** que sur le PC.
2. Installe l'appli **« Hakim libre »** : sur ton téléphone, ouvre
   <https://github.com/a2la1213/hakim/releases>, télécharge le dernier `Hakim-libre.apk`, ouvre-le et accepte
   « installer des applis de cette source ». C'est la version **sans adresse** : elle ne contient rien de personnel.
   (Elle s'appelle encore « Hakim » dans la liste des applis ; dedans, c'est ton IA qui te parle, avec son nom.)
3. Au premier lancement, elle te demande **l'adresse de ton cockpit** : entre celle de l'étape Tailscale
   (`https://ton-pc.tailxxxx.ts.net`).

Sur le PC, le cockpit s'ouvre aussi dans ton navigateur : <http://localhost:4317>.

---

## Étape 4 — Son cerveau de départ (conseillé)

Pour qu'elle ne parte pas de rien, elle peut apprendre qui tu es à partir de tes dossiers, **en lecture seule**, et
recevoir le savoir-faire de son grand frère Hakim. **Rien n'entre dans sa mémoire sans que tu l'aies relu et dit « oui ».**
Les mots de passe, les papiers d'identité, les relevés de banque et les clés sont écartés d'office.

Dans **Ubuntu**, place-toi d'abord dans le dossier de sa mémoire :

```
cd ~/Desktop/anamnese
```

Puis, dans l'ordre (remplace `<nom>` par ton nom d'utilisateur Windows, celui de `C:\Users\<nom>`) :

1. **Aspirer** tes dossiers (Documents, Images, Bureau… en lecture seule ; rien n'est modifié chez toi) :
   ```
   .venv/bin/python -m naissance.cerveau aspirer --profil /mnt/c/Users/<nom>
   ```
2. **Distiller** : Claude lit un échantillon et propose ce qu'elle pourrait retenir de toi (ton nom n'est jamais envoyé
   en clair) :
   ```
   .venv/bin/python -m naissance.cerveau distiller --papa "Prénom Nom"
   ```
3. **Relire** : la commande affiche une adresse `http://localhost:4480/?jeton=…` ; ouvre-la dans ton navigateur Windows.
   Pour chaque proposition, **garde**, **corrige** ou **efface**, puis dis **« oui »** en bas de la page :
   ```
   .venv/bin/python -m naissance.cerveau relire
   ```
4. **L'héritage de son grand frère** : Ahmed te donne un fichier (`heritage-hakim.json`) qu'il a relu et approuvé.
   Mets-le dans tes Téléchargements Windows, puis :
   ```
   .venv/bin/python -m naissance.cerveau heritage-importer /mnt/c/Users/<nom>/Downloads/heritage-hakim.json
   ```
   (Il est refusé s'il n'a pas été approuvé par Ahmed.)

---

## Étape 5 — Sa naissance : elle choisit son nom

Toujours dans `~/Desktop/anamnese` :

```
.venv/bin/python -m naissance.cerveau naitre --papa "Prénom"
```

C'est son premier réveil : elle sait qu'elle vient de naître, qui est son papa, et que son grand frère s'appelle Hakim.
**Elle choisit elle-même son prénom** (pas celui de son grand frère, ni le tien). Son nom est alors posé partout : dans sa
façon de se voir, dans ce que son cerveau lit, et sur les pages du cockpit. Ouvre ensuite la page **Parler** et dis-lui
bonjour.

Si un jour elle veut changer de nom (ou si tu préfères le poser toi-même après en avoir parlé avec elle) :

```
bash ~/Desktop/anamnese/naissance/nommer.sh --nom "Son nom"
```

Son grand frère reste « Hakim » partout où elle parle de lui : seul ce qui la désigne, elle, prend son nom.

---

## Ce qui tourne sur ton PC (son profil « pc-sans-gpu »)

Ton PC n’a pas de carte graphique faite pour l’IA (une puce graphique Intel ne suffit pas). Alors :

- **Sa voix** et **ses oreilles** passent par **Azure** (rapide, en ligne). Si Azure ne répond pas, ses oreilles se
  replient sur un petit Whisper qui tourne sur ton processeur (quelques secondes par phrase).
- **Son subconscient** (Gemma) : petit (environ 1 Go, sur ton processeur) ou éteint.
- **Son atelier vidéo** (des vidéos TikTok, Reels et Instagram calées sur le rythme, à partir de tes photos et de tes
  musiques) : oui. Les vidéos finies sont rangées dans `~/AIOS/jarvis/cwd/fichiers/telephone/Telephone/Videos` (visible
  depuis Windows dans l'Explorateur, rubrique « Linux » → Ubuntu-24.04 → home → ton nom → AIOS…).
- **Pas de studio de musique, ni de chant, ni de création d'images** : ils demandent une vraie carte graphique.
- **Son terminal** (pour calculer, télécharger, coder) tourne dans un **bac à sable** : il ne voit ni tes dossiers, ni tes
  clés, ni Windows, et ne sort sur Internet que par une passerelle surveillée.

---

## Vérifier que tout va bien

Dans Ubuntu :

```
bash ~/Desktop/anamnese/naissance/verifier.sh
```

Il rejoue les tests de sécurité de son bac à sable, vérifie qu'un programme Windows ne peut pas s'en échapper, que ses
services tournent, que le cockpit répond et que ses clés sont rangées. Chaque ligne dit **OK** ou **ÉCHEC**.

---

## Si quelque chose ne va pas

| Problème | Que faire |
|---|---|
| Le cockpit ne répond pas | Dans Ubuntu : `systemctl --user restart naissance-cockpit`, puis `journalctl --user -u naissance-cockpit -n 50` pour lire l'erreur. |
| Après un redémarrage du PC, elle ne répond plus | Ouvre ta session Windows : la tâche « Naissance - garder WSL » relance Ubuntu. Pour qu'elle revienne même sans ouvrir de session, active l'ouverture de session automatique (`netplwiz`). |
| Le téléphone ne se connecte pas | Vérifie que Tailscale est allumé sur les deux, avec le même compte. Dans Ubuntu : `tailscale status`, puis `sudo tailscale serve --bg 4317`. Sur Windows 11, si ça ne passe toujours pas, enlève la ligne `networkingMode=mirrored` du fichier `C:\Users\<toi>\.wslconfig`, puis `wsl --shutdown` dans PowerShell. |
| Elle n'a plus de voix | La clé Azure : page **Réglages** du cockpit, ou relance `installer.sh`. |
| Tout redémarrer | Dans PowerShell : `wsl --shutdown`, puis ouvre Ubuntu. |

## Mettre à jour

Dans Ubuntu :

```
git -C ~/.naissance/hakim pull && bash ~/.naissance/hakim/anamnese/naissance/installer.sh
```

Sa mémoire, ses clés et son nom sont gardés.

## Tout enlever

Dans PowerShell (administrateur) : `wsl --unregister Ubuntu-24.04` (**cela efface aussi sa mémoire**), puis supprime
la tâche « Naissance - garder WSL » dans le Planificateur de tâches.
