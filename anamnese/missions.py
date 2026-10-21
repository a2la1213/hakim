"""Les missions confiées par Hakim à Claude Code (accord d'Ahmed, 2026-10-20 08:19 : « on peut foncer », confirmé à
Claude Code : « j'ai tout validé ce qu'il dit »).

- Hakim PRÉPARE une mission (mission_proposer) : un titre, une consigne, le dossier du projet, et s'il faut y
  écrire. Elle est déposée ici, dans ~/AIOS/jarvis/missions (que ni ses fichiers ni son terminal ne peuvent
  écrire : seul ce module, appelé par son serveur MCP, y dépose).
- RIEN ne part sans Ahmed : le cockpit la lui montre (page, téléphone) ; il l'accepte ou la refuse d'un geste,
  derrière la passkey. Le cockpit en garde sa PROPRE copie dès qu'il la voit : une fiche modifiée après coup ne
  change pas ce qu'Ahmed a lu.
- Acceptée, une session de Claude Code part dans ce dossier : tours limités, une mission à la fois, trois par jour,
  une heure au plus ; sans écriture, elle ne peut que lire ; avec, elle n'écrit que dans ce dossier. Le résultat
  revient à Hakim par courrier et à Ahmed (page, téléphone) ; tout est noté au journal des missions.
"""
import json
import os
import re
import time
import uuid
from pathlib import Path

DOSSIER = Path(os.environ.get("JARVIS_MISSIONS", Path.home() / "AIOS" / "jarvis" / "missions"))
MAISON = Path.home()
EN_ATTENTE_MAX = 5
MODELES = ("sonnet", "opus")


class Refus(Exception):
    pass


def racines_permises(maison=None):
    m = Path(maison or MAISON)
    return [m / "Desktop", m / "AIOS"]


def projet_permis(chemin, maison=None):
    """Le dossier réel du projet s'il est permis : un sous-dossier de ~/Desktop ou de ~/AIOS (jamais ces racines
    elles-mêmes, ni ~/AIOS/jarvis — la maison de Hakim : son journal, son jardin —, sauf son atelier de calcul
    ~/AIOS/jarvis/cwd, ni le cockpit) ; sinon Refus. Le cockpit refait les mêmes vérifications (missions.js)."""
    m = Path(maison or MAISON)
    try:
        p = Path(os.path.expanduser(str(chemin or ""))).resolve(strict=True)
    except (OSError, RuntimeError):
        raise Refus(f"dossier introuvable : {chemin}")
    if not p.is_dir():
        raise Refus("le projet doit être un dossier")
    racines = [r.resolve() for r in racines_permises(m) if r.exists()]
    if not any(p != r and r in p.parents for r in racines):
        raise Refus("dossier hors des projets d'Ahmed (un sous-dossier de ~/Desktop ou de ~/AIOS)")
    jarvis = (m / "AIOS" / "jarvis").resolve() if (m / "AIOS" / "jarvis").exists() else None
    atelier = (m / "AIOS" / "jarvis" / "cwd").resolve() if (m / "AIOS" / "jarvis" / "cwd").exists() else None
    if jarvis and (p == jarvis or jarvis in p.parents) and not (atelier and (p == atelier or atelier in p.parents)):
        raise Refus("ta maison (~/AIOS/jarvis) est hors mission, sauf ton atelier (~/AIOS/jarvis/cwd)")
    if any(part.startswith(".") for part in p.relative_to(m).parts):
        raise Refus("pas de dossier caché")
    if re.search(r"[,()*?\[\]{}\"'`\\\x00-\x1f]", str(p)):
        raise Refus("caractère interdit dans le chemin (virgule, parenthèse, joker, guillemet) : renomme le dossier")
    cockpit = m / "AIOS" / "cockpit"
    if cockpit.exists() and (p == cockpit.resolve() or cockpit.resolve() in p.parents):
        raise Refus("le cockpit est hors mission (ses secrets : passkey, notifications, jeton)")
    return p


_NOMMES = re.compile(r"(?:\$\{?HOME\}?|~|/)[A-Za-z0-9_./-]*")


def dossiers_launchd(maison=None, illisibles=None):
    """(audit du cockpit, C-H5 ; élargi après la relecture Opus du 2026-10-20) Les dossiers que launchd exécute : ses
    programmes, leur dossier de travail, les chemins nommés dans leurs arguments (« bash -c "cd DIR && …" »,
    « "$HOME"/x ») et dans les scripts lancés (deux niveaux, seulement ce qui s'exécute). Mêmes règles que le cockpit
    (missions.js, dossiersLaunchd), qui refait la vérification. `illisibles` reçoit les plists qu'on ne sait pas lire."""
    import plistlib
    m = Path(maison or MAISON).resolve()
    racines = {m, (m / "Desktop").resolve(), (m / "AIOS").resolve()}
    dossiers, lus = set(), set()

    def nommes(t):
        net = str(t).replace('"', "").replace("'", "")
        out = []
        for c in _NOMMES.findall(net):
            if len(c) < 2:
                continue
            c = re.sub(r"[./]+$", "", re.sub(r"^(\$\{?HOME\}?|~)", str(m), c))
            if c.startswith("/"):
                out.append(c)
        return out

    def visiter(x, niveau):
        try:
            r = Path(x).resolve(strict=True)
        except (OSError, RuntimeError):
            return
        if r in lus:
            return
        lus.add(r)
        d = r if r.is_dir() else r.parent
        if m in d.parents and d not in racines:
            dossiers.add(d)
        try:
            if not r.is_file() or r.stat().st_size > 256 * 1024 or niveau >= 2 or m not in r.parents:
                return
            t = r.read_bytes()
        except OSError:
            return
        if b"\0" in t[:4096]:
            return
        if niveau > 0 and not (r.stat().st_mode & 0o111) and not t.startswith(b"#!"):
            return
        for c in nommes(t.decode("utf-8", "replace")):
            visiter(c, niveau + 1)

    for f in sorted((m / "Library" / "LaunchAgents").glob("*.plist")):
        try:
            d = plistlib.loads(f.read_bytes())
        except Exception:
            if illisibles is not None:
                illisibles.append(f.name)
            continue
        args = d.get("ProgramArguments") if isinstance(d.get("ProgramArguments"), list) else []
        for x in [d.get("Program"), d.get("WorkingDirectory"), *args]:
            if isinstance(x, str):
                for c in [x, *nommes(x)]:
                    if c.startswith("/"):
                        visiter(c, 0)
    return sorted(dossiers)


def refus_ecriture(p, maison=None):
    """La raison du refus d'écrire dans ce dossier, ou None. Ton propre code (Anamnèse) ne se modifie pas par mission
    (il passe par les chantiers et les promotions), ni ton atelier (ses chemins peuvent bouger entre l'accord d'Ahmed
    et le lancement : relecture Opus du 2026-10-20), ni un dossier que le Mac exécute tout seul (launchd)."""
    m = Path(maison or MAISON)
    p = Path(p).resolve()
    for interdit in (m / "Desktop" / "anamnese", m / "AIOS" / "jarvis" / "cwd"):
        if interdit.exists() and (p == interdit.resolve() or interdit.resolve() in p.parents):
            return ("pas d'écriture par mission dans ton propre code (Anamnèse : chantier et promotion) ni dans ton "
                    "atelier ; en lecture seule, oui")
    illisibles = []
    for d in dossiers_launchd(m, illisibles):
        if p == d or d in p.parents or p in d.parents:
            return (f"pas d'écriture dans un dossier que le Mac exécute tout seul (launchd : "
                    f"{d.relative_to(m.resolve())}) ; en lecture seule, oui")
    if illisibles:
        return f"un LaunchAgent illisible ({illisibles[0]}) : écriture refusée par prudence ; en lecture seule, oui"
    return None


def ecriture_permise(p, maison=None):
    return refus_ecriture(p, maison) is None


def _fiches(dossier=None):
    d = Path(dossier or DOSSIER)
    out = []
    for f in sorted(d.glob("*.json")) if d.exists() else []:
        try:
            out.append(json.loads(f.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
    return out


def proposer(titre, consigne, projet, ecriture=False, modele="sonnet", dossier=None, maison=None, journal=None):
    """Dépose la mission (état « proposée ») ; rend sa fiche. Le cockpit fait le reste, avec l'accord d'Ahmed."""
    titre = " ".join(str(titre or "").split())[:120]
    consigne = str(consigne or "").strip()
    if len(titre) < 4:
        raise Refus("donne un titre (4 caractères au moins)")
    if not 20 <= len(consigne) <= 6000:
        raise Refus("la consigne fait entre 20 et 6 000 caractères")
    if modele not in MODELES:
        raise Refus("modèle : sonnet ou opus")
    p = projet_permis(projet, maison)
    refus = ecriture and refus_ecriture(p, maison)
    if refus:
        raise Refus(refus)
    import echanges
    if echanges._masquer(consigne) != consigne:
        raise Refus("la consigne contient un secret (clé, mot de passe) : retire-le, Claude Code le trouvera lui-même si besoin")
    d = Path(dossier or DOSSIER)
    # relecture Opus (A6) : « en attente » se lit dans le journal du cockpit (la fiche, elle, reste « proposee »)
    if len(en_attente(journal, d)) >= EN_ATTENTE_MAX:
        raise Refus(f"déjà {EN_ATTENTE_MAX} missions attendent Ahmed : attends qu'il tranche")
    m = {"id": time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4], "ts": time.time(), "etat": "proposee",
         "titre": titre, "consigne": consigne, "projet": str(p), "ecriture": bool(ecriture), "modele": modele,
         "auteur": "hakim"}
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / f".{m['id']}.tmp"
    tmp.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, d / f"{m['id']}.json")
    return m


def _journal_cockpit(journal=None):
    j = Path(journal or Path(os.environ.get("JARVIS_DIR", Path.home() / "AIOS" / "jarvis")) / "missions-cockpit" / "missions.jsonl")
    dernier = {}
    try:
        for l in j.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(l)
            except ValueError:
                continue
            if e.get("id"):
                dernier[e["id"]] = {**dernier.get(e["id"], {}), **e}
    except OSError:
        pass
    return dernier


def en_attente(journal=None, dossier=None):
    """Les missions qui attendent encore Ahmed : pas encore vues par le cockpit, ou vues et toujours « proposee »."""
    dernier = _journal_cockpit(journal)
    return [f for f in _fiches(dossier) if dernier.get(f["id"], {}).get("etat", "proposee") == "proposee"]


def etat(journal=None, dossier=None, n=8):
    """Où en sont ses missions : le journal du cockpit (la vérité : acceptée, refusée, finie…), sinon la fiche."""
    dernier = _journal_cockpit(journal)
    lignes = []
    for f in _fiches(dossier)[-n:]:
        e = dernier.get(f["id"], {})
        quoi = e.get("etat") or f.get("etat")
        res = e.get("resume")
        lignes.append(f"- {f['id']} « {f['titre']} » ({Path(f['projet']).name}, {'écriture' if f.get('ecriture') else 'lecture seule'}) : {quoi}"
                      + (f" — {str(res)[:300]}" if res else ""))
    return "\n".join(lignes) or "Aucune mission."
