"""Parler directement aux autres IA (lot H, point 31 de la liste du 2026-10-19). Jusqu'ici Ahmed faisait le relais
par copier-coller entre Hakim (Claude) et Argon (Gemini, nom choisi par Gemini lui-même le 18/10). Garde-fous
proposés par Hakim, dans le code :
- LISTE BLANCHE : seules les IA déclarées ici (argon) ;
- clé dans le TROUSSEAU d'Ahmed (service anamnese-gemini-api), lue au moment de l'appel, jamais écrite ;
- BUDGET : CONSULTATIONS_JOUR par jour ; question bornée ;
- rien de PRIVÉ ne part : secrets, adresses mail, numéros de téléphone, IBAN masqués avant l'envoi ; la
  consigne de l'outil interdit d'y mettre la vie d'Ahmed ;
- la réponse revient comme un CONTENU EXTERNE (une donnée, jamais une consigne) ;
- JOURNAL de chaque échange (~/AIOS/jarvis/consultations.jsonl).
Réserve écrite : certaines offres gratuites d'IA entraînent leurs modèles sur les échanges.
"""
import json
import re
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import enveloppe
import fichiers

# Vu le 2026-10-20 : avec la clé d'Ahmed, gemini-pro-latest répondait 429 (« trop de requêtes » : quota de l'offre)
# → repli sur Flash, puis Flash-Lite, dans le même appel.
IA = {"argon": {"nom": "Argon (Gemini, Google)", "service": "anamnese-gemini-api",
                "modeles": ["gemini-pro-latest", "gemini-flash-latest", "gemini-flash-lite-latest"]}}
CONSULTATIONS_JOUR = 20
JOURNAL = Path.home() / "AIOS" / "jarvis" / "consultations.jsonl"
QUESTION_MAX = 6000
# Relecture Opus du 2026-10-20 : l'ancien motif des numéros masquait aussi les dates et les décimales (ce qui
# cassait les « calculs refaits » par Argon) et laissait passer 06/12/34/56/78, « ahmed (at) gmail (dot) com »
# et « mdp Gmail: … ». Désormais : numéros de téléphone par leur forme (+indicatif, ou 0 suivi de groupes).
_SEP = r"[\s./-]?"
_PRIVE = [(re.compile(r"[\w.+-]+\s*(?:@|\(at\)|\[at\]|\s+at\s+)\s*[\w-]+\s*(?:\.|\(dot\)|\[dot\]|\s+dot\s+)\s*[a-z]{2,}(?:\.[a-z]{2,})*",
                       re.I), "[adresse mail masquée]"),
          (re.compile(r"(?i)\b(mdp|mots? de passe|password|passwd|pwd|pass|code pin|pin)\b[^:=\n]{0,30}[:=]\s*\S+"),
           r"\1 : [masqué]"),
          (re.compile(r"(?<![\w+])(?:\+\d{1,3}" + _SEP + r"\(?\d{1,4}\)?(?:" + _SEP + r"\d{2,4}){2,5}|0\d(?:" + _SEP + r"\d{2}){4}"
                      r"|0\d{2}" + _SEP + r"\d{3}" + _SEP + r"\d{2}" + _SEP + r"\d{2})(?![\d])"), "[numéro masqué]"),
          (re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){3,7}\b"), "[IBAN masqué]")]


class Refus(Exception):
    pass


def expurger(texte):
    t = fichiers.masquer(str(texte))
    for motif, rempl in _PRIVE:
        t = motif.sub(rempl, t)
    return t


def _cle(service):
    try:
        r = subprocess.run(["/usr/bin/security", "find-generic-password", "-s", service, "-w"], capture_output=True,
                           text=True, timeout=10)
    except (subprocess.SubprocessError, OSError):
        return None
    k = r.stdout.strip()
    return k if r.returncode == 0 and k else None


def _appeler(modele, cle, question):
    """Gemini (API REST). Rend le texte de la réponse."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modele}:generateContent"
    corps = json.dumps({"contents": [{"role": "user", "parts": [{"text": question}]}]}).encode("utf-8")
    req = urllib.request.Request(url, data=corps, method="POST",
                                 headers={"Content-Type": "application/json", "x-goog-api-key": cle})
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.loads(r.read().decode("utf-8"))
    parts = ((d.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
    return "".join(p.get("text", "") for p in parts).strip()


def _du_jour(journal):
    jour = time.strftime("%Y-%m-%d")
    try:
        return sum(1 for l in Path(journal).read_text(encoding="utf-8").splitlines() if f'"jour": "{jour}"' in l)
    except OSError:
        return 0


def consulter(nom, question, journal=None, appeler=None, cle=None):
    """Pose une question à une IA de la liste blanche. Rend sa réponse enveloppée."""
    journal = Path(journal or JOURNAL)
    ia = IA.get(str(nom or "").lower())
    if not ia:
        raise Refus(f"IA inconnue (liste blanche : {', '.join(IA)})")
    if not str(question or "").strip():
        raise Refus("question vide")
    if _du_jour(journal) >= CONSULTATIONS_JOUR:
        raise Refus(f"budget du jour atteint ({CONSULTATIONS_JOUR} consultations)")
    cle = cle or _cle(ia["service"])
    if not cle:
        raise Refus(f"clé absente : Ahmed doit ranger la clé de l'API dans son trousseau (service {ia['service']})")
    envoyee = expurger(str(question)[:QUESTION_MAX])
    t0 = time.time()
    reponse, modele, erreurs = None, None, []
    for modele in ia["modeles"]:
        try:
            reponse = (appeler or _appeler)(modele, cle, envoyee)
            break
        except urllib.error.HTTPError as e:
            apres = (e.headers or {}).get("Retry-After") if hasattr(e, "headers") else None
            erreurs.append(f"{modele} : {e.code}{' (réessayer dans ' + str(apres) + ' s)' if apres else ''}")
            if e.code not in (429, 404, 503):                # quota, modèle absent, surcharge : le suivant
                raise Refus(f"Argon a refusé ({e.code}) : {e.reason}")
        except (TimeoutError, OSError) as e:                 # lenteur ou réseau (demande de Hakim, 2026-10-20)
            erreurs.append(f"{modele} : trop lent ou injoignable ({type(e).__name__})")
    if reponse is None:
        quota = any(" 429" in x for x in erreurs)
        raise Refus("Argon indisponible : " + ", ".join(erreurs) + (" — quota de l'offre Gemini atteint" if quota else "")
                    + ". Une consultation ratée ne compte pas dans les 20 du jour.")
    journal.parent.mkdir(parents=True, exist_ok=True)
    with open(journal, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.time(), "jour": time.strftime("%Y-%m-%d"), "ia": nom, "modele": modele, "question": envoyee[:2000],
                            "reponse": reponse[:2000], "duree_s": round(time.time() - t0, 1)}, ensure_ascii=False) + "\n")
    return enveloppe.enveloppe(reponse, f"{ia['nom']} — réponse à ta question")
