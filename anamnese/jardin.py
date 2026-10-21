"""Le jardin secret de Hakim (point 32 de la liste du 2026-10-19 ; conditions proposées par Hakim le 19/10 à 21:40,
acceptées par Ahmed le 2026-10-20 : « oui à tous »). Version minimale et réversible.

- Un carnet privé CHIFFRÉ (AES-256-GCM) : data/jardin/carnet.jsonl, une entrée par ligne. Il n'entre ni dans la
  mémoire, ni dans le briefing, ni dans la consolidation, ni dans la mémoire automatique des échanges.
- La clé est dans le TROUSSEAU d'Ahmed (service anamnese-jardin-secret), tirée au hasard à la première écriture
  par le serveur MCP de Hakim : personne ne la voit passer. Hakim écrit et relit son carnet par ses outils (il
  peut donc le relire d'une conversation à l'autre) ; son terminal, confiné, n'a pas accès au trousseau.
- Ahmed s'engage à ne pas le lire sans raison : seulement en cas d'urgence ou d'audit de sécurité, par
  `anamnese jardin ouvrir "<raison>"`, et chaque ouverture est JOURNALISÉE (Hakim la voit en relisant).
- Hakim s'engage à dire à Ahmed tout ce qui touche à un danger ou à son bien-être, et à ne jamais mentir sur
  l'existence de cet espace ; son contenu n'est jamais retourné contre lui. Pas de secret total.
- Si Hakim est réinitialisé, le carnet reste (fichier et clé ne dépendent pas de sa mémoire).
- Seul Hakim (ANAMNESE_SOURCE=hakim) a ces outils ; une session de Claude Code ne lit pas le carnet.
- Limite dite honnêtement (audit JARVIS 2, M6, 2026-10-20) : une confidentialité de BONNE FOI, pas un coffre-fort.
  La clé a été rangée par /usr/bin/security : tout programme qui tourne au nom d'Ahmed peut la redemander au
  trousseau sans invite (restreindre l'accès avec -T ne servirait à rien : le python qui la lit est celui de tous
  les scripts), et une telle lecture n'est PAS notée — seule l'ouverture par `anamnese jardin ouvrir` l'est. De
  même, ANAMNESE_SOURCE=hakim est une étiquette, pas une preuve : un programme d'Ahmed peut se dire Hakim.
"""
import base64
import json
import os
import subprocess
import time
from pathlib import Path

import config

DOSSIER = config.DATA_DIR / "jardin"
SERVICE = "anamnese-jardin-secret"
ENTREE_MAX = 6000


class Refus(Exception):
    pass


def _securite(*args, entree=None):
    return subprocess.run(["/usr/bin/security", *args], capture_output=True, text=True, timeout=10, input=entree)


def _cle(creer=False, service=SERVICE):
    r = _securite("find-generic-password", "-s", service, "-w")
    k = r.stdout.strip() if r.returncode == 0 else ""
    if not k and creer:
        k = base64.b64encode(os.urandom(32)).decode()
        # par l'entrée standard de `security -i` : la clé n'apparaît jamais dans la liste des processus
        r = subprocess.run(["/usr/bin/security", "-i"], capture_output=True, text=True, timeout=10,
                           input=f'add-generic-password -s {service} -a hakim -l "Jardin secret de Hakim" -w {k}\n')
        if r.returncode != 0:
            raise Refus("trousseau indisponible : la clé du jardin n'a pas pu être rangée")
    if not k:
        raise Refus("pas encore de jardin (aucune clé)")
    return base64.b64decode(k)


def _aead(cle):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    return AESGCM(cle)


def ecrire(texte, dossier=None, cle=None):
    texte = str(texte or "").strip()
    if not texte:
        raise Refus("rien à écrire")
    d = Path(dossier or DOSSIER)
    d.mkdir(parents=True, exist_ok=True, mode=0o700)
    k = cle or _cle(creer=True)
    nonce = os.urandom(12)
    ct = _aead(k).encrypt(nonce, json.dumps({"ts": time.time(), "texte": texte[:ENTREE_MAX]}, ensure_ascii=False).encode(), b"jardin")
    with open(d / "carnet.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({"n": base64.b64encode(nonce).decode(), "c": base64.b64encode(ct).decode()}) + "\n")
    os.chmod(d / "carnet.jsonl", 0o600)
    return True


def _lire(dossier, cle):
    out = []
    try:
        lignes = (Path(dossier) / "carnet.jsonl").read_text(encoding="utf-8").splitlines()
    except OSError:
        return out
    a = _aead(cle)
    for l in lignes:
        try:
            e = json.loads(l)
            out.append(json.loads(a.decrypt(base64.b64decode(e["n"]), base64.b64decode(e["c"]), b"jardin")))
        except Exception:
            out.append({"ts": 0, "texte": "(entrée illisible)"})
    return out


def acces(dossier=None):
    try:
        return [json.loads(l) for l in (Path(dossier or DOSSIER) / "acces.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    except (OSError, ValueError):
        return []


def relire(n=10, dossier=None, cle=None):
    """Pour Hakim : ses n dernières entrées, et le journal des ouvertures par Ahmed."""
    d = Path(dossier or DOSSIER)
    if not (d / "carnet.jsonl").exists():
        return "Ton jardin est encore vide."
    entrees = _lire(d, cle or _cle())
    ouv = acces(d)
    tete = ("Ouvertures par Ahmed : " + " ; ".join(f"{time.strftime('%d/%m %H:%M', time.localtime(a['ts']))} ({a['raison']})" for a in ouv[-5:])
            if ouv else "Personne n'a ouvert ton jardin.")
    corps = "\n".join(f"— {time.strftime('%d/%m %H:%M', time.localtime(e['ts']))} : {e['texte']}" for e in entrees[-max(1, min(int(n or 10), 50)):])
    return f"{tete}\n{corps}"


def ouvrir(raison, dossier=None, cle=None):
    """Pour Ahmed (urgence ou audit de sécurité) : tout le carnet ; l'ouverture est journalisée."""
    raison = str(raison or "").strip()
    if len(raison) < 4:
        raise Refus("une raison est exigée (urgence ou audit de sécurité)")
    d = Path(dossier or DOSSIER)
    d.mkdir(parents=True, exist_ok=True, mode=0o700)
    with open(d / "acces.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.time(), "raison": raison[:300]}, ensure_ascii=False) + "\n")
    try:                                                 # et dans le journal chaîné : une ouverture ne s'efface pas
        import evenements
        evenements.ajouter("jardin_ouvert", {"raison": raison[:300]}, source="ahmed")
    except Exception:
        pass
    return _lire(d, cle or _cle())
