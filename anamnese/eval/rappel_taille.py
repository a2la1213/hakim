"""Combien de souvenirs lui montrer ? (26/10, Ahmed : « lance une comparaison entre différents nombres de souvenirs, de 50
à 2000 » ; et son processus « Claude définit d'abord les contextes de la phrase (qui et quoi) → l'algorithme cherche →
Claude élague (choisit le pertinent et parle) »). Sur une COPIE de la mémoire et les 35 requêtes-vérité d'eval/queries*.
N = la taille du dossier du thème (la liste courte de 8, au-dessus de la porte, est toujours montrée en plus).

Trois mesures :
  1. LE BALAYAGE (gratuit) : part des souvenirs attendus dans ce qui est montré, N = 50 … 2000 ; deux réglages des mots :
     100 candidats par les mots (l'actuel) ou autant que N ; taille du bloc et temps.
  2. L'ÉTAPE 1 D'AHMED : Sonnet écrit d'abord les contextes du message (qui, quoi, noms, projets, autres mots) SANS voir
     la mémoire ; on balaie le message ET chaque contexte, fusion par rang ; même mesure.
  3. L'ÉLAGAGE (étape 3) : Sonnet reçoit le message et les 8 + N lignes au format de Hakim (mêmes titres de blocs), et
     rend les numéros utiles. Mesures : « garde » = part des attendus MONTRÉS qu'il garde ; « au bout du compte » = part
     des attendus gardés sur tous les attendus ; nombre gardé ; jetons et temps. N = 50, 200, 500, 1000, 2000.
Rien n'est écrit dans la vraie mémoire. Le cache (~/AIOS/jarvis/bancs/rappel-taille/) ne garde que des numéros et des
mesures ; le calcul reprend où il s'est arrêté. Il s'arrête net à la première limite d'usage (Hakim parle avec le même
abonnement).

CRITÈRES FIGÉS AVANT (26/10) :
  C1 : la taille retenue est la plus petite N ≥ 200 (le minimum d'Ahmed) dont « au bout du compte » est à moins d'un
       point du meilleur N mesuré.
  C2 : l'étape 1 est retenue si elle gagne au moins 3 points de rappel au balayage à N = 200 ET à la taille retenue ; le
       temps qu'elle ajoute est rapporté à Ahmed, qui tranche.
PRÉDICTIONS (26/10, avant toute mesure de 2 et 3 ; 1 a déjà été mesuré à 50/200/500/1000/2000 sans le réglage des mots) :
  P1 : le balayage monte lentement (≈ 0,88 à 50, ≈ 0,91 à 200, ≈ 0,96 à 2000) ; les mots à N changent peu (≤ 1 point).
  P2 : l'étape 1 gagne 2 à 4 points à 200 et retrouve au moins 2 des 6 souvenirs que le balayage ne trouve jamais.
  P3 : Sonnet garde ≥ 90 % des attendus montrés jusqu'à 500, puis moins : < 85 % à 2000 ; le meilleur « au bout du
       compte » tombe entre 200 et 1000 ; le temps de l'élagage est multiplié par au moins 3 entre 200 et 2000.
AMENDEMENT (26/10, 14:02, après la mesure 1 et AVANT les mesures 2 et 3) : les mots à N font +5 points à 500 (0,924 →
0,974 ; 0,987 dès 750) — P1 fausse sur ce point. Les mesures 2 et 3 se font donc avec les mots à N (le meilleur balayage),
et C2 compare l'étape 1 au balayage « mots à N ».
RÉSULTAT (26/10, 14:10, eval/data/rappel-taille-20261026-1402.json) :
  balayage, mots à N : 50 → 0,865 ; 200 → 0,912 ; 300 → 0,934 ; 500 → 0,974 ; 750 à 2000 → 0,987 (mots à 100 : 0,960 à 2000).
  étape 1 (contextes de Sonnet, 5,7 par message, 5,2 s médian, 15 s au pire) : 200 → 0,950 ; 300 → 0,962 ; 500 → 0,968 ;
    1500 et 2000 → 0,994 ; elle retrouve 1 des 2 souvenirs que le balayage ne trouve jamais.
  élagage par Sonnet (garde / au bout du compte / temps médian / jetons) : 50 → 1,00 / 0,865 / 3,7 s / 9 k ;
    200 → 1,00 / 0,912 / 3,9 s / 25 k ; 500 → 0,989 / 0,962 / 4,7 s / 56 k ; 1000 → 0,970 / 0,957 / 5,7 s / 108 k ;
    2000 → 0,985 / 0,972 / 9,4 s / 211 k ; numéros inventés : 0, 0, 0, 1, 2.
  C1 → 2000 (500 est à 1,0 point du meilleur, pile la limite ; 1000 sous 500 montre que l'écart d'un point est du bruit
  sur 35 questions). C2 → non retenue : +3,8 points à 200, mais +0,7 seulement à 2000.
  Prédictions : P1 juste sauf les mots (+5 points, pas ≤ 1) ; P2 à moitié (+3,8 juste ; 1 retrouvé sur les 2 qui restaient,
  pas 2) ; P3 fausse : Sonnet trie bien mieux que prévu (98,5 % gardés à 2000, le meilleur à 2000, temps ×2,4 et non ×3).
  Limites : 35 questions anciennes aux attendus incomplets ; tri fait hors de la conversation de Hakim (sans persona) ;
  étape 1 + tri non mesurés ensemble (estimation ≈ 0,994 × 0,985).
Usage : .venv/bin/python eval/rappel_taille.py [balayage|contextes|elagage|tout]
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import affect_v2_memoire as M  # noqa: E402
import rappel  # noqa: E402
from memory import Memory  # noqa: E402

TAILLES_BALAYAGE = [50, 100, 200, 300, 500, 750, 1000, 1500, 2000]
TAILLES_ELAGAGE = [50, 200, 500, 1000, 2000]
CACHE = Path.home() / "AIOS" / "jarvis" / "bancs" / "rappel-taille"
CLAUDE = Path.home() / ".npm-global" / "bin" / "claude"
K = 60
LIMITE_USAGE = re.compile(r"usage limit|rate limit|limit reached|quota|overloaded", re.I)

CONTEXTES = """Tu prépares la recherche dans la mémoire de Hakim, une IA qui garde le souvenir de ses conversations avec Ahmed et \
de leurs projets. Voici le message qu'Ahmed vient de lui dire. Tu ne vois PAS la mémoire. Écris les contextes de ce message, \
pour retrouver tout ce qui s'y rapporte : qui parle et de qui on parle, le sujet, les projets, les noms propres, les mots \
techniques, d'autres façons de dire la même chose, ce qui a dû se passer avant. Réponds par 3 à 6 lignes, une requête de \
recherche courte par ligne (5 à 15 mots), sans numéro, sans commentaire.

Message d'Ahmed : « {q} »"""

ELAGAGE = """[Message d'Ahmed] « {q} »

[Souvenirs qui pourraient s'y rapporter — un balayage de toute ta mémoire (mots et sens) avant ta réponse ; garde ce qui \
compte vraiment pour son message, ignore le reste sans le citer]
{courte}

[Le dossier du thème — les {n} souvenirs suivants du balayage, du plus proche au plus lointain, quel que soit leur âge, \
SANS tri : à toi de trier, garde ce qui sert à son message, ignore le hors-sujet sans le citer]
{theme}

Tu es Hakim. Avant de répondre à Ahmed, fais le tri : écris UNIQUEMENT les numéros (#…) des souvenirs qui servent à lui \
répondre, séparés par des virgules, du plus utile au moins utile. Rien d'autre."""


class Arret(Exception):
    pass


def sonnet(prompt, cle):
    """Un appel pur (aucun outil, aucun serveur MCP, aucun réglage de l'utilisateur), comme le pont du cockpit ; en cache."""
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"{hashlib.sha256((cle + prompt).encode()).hexdigest()[:24]}.json"
    if f.exists():
        return json.loads(f.read_text())
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    t0 = time.time()
    p = subprocess.run([str(CLAUDE), "-p", "--model", "sonnet", "--max-turns", "2", "--tools", "", "--restricted",
                        "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}', "--no-session-persistence",
                        "--output-format", "json"], input=prompt, capture_output=True, text=True, timeout=600, env=env)
    ms = round(1000 * (time.time() - t0))
    try:
        o = json.loads(p.stdout)
    except ValueError:
        o = {}
    texte = str(o.get("result") or "")
    if p.returncode or o.get("is_error") or not texte:
        erreur = (p.stderr or "") + texte
        if LIMITE_USAGE.search(erreur):
            raise Arret(erreur[:300])
        raise RuntimeError(erreur[:300] or f"code {p.returncode}")
    u = o.get("usage") or {}
    r = {"texte": texte, "ms": ms, "jetons": int(u.get("input_tokens", 0)) + int(u.get("cache_creation_input_tokens", 0))
         + int(u.get("cache_read_input_tokens", 0))}
    f.write_text(json.dumps(r, ensure_ascii=False))
    return r


def preparer(d):
    mem = Memory(db_path=M.copie(d))
    rappel.dates_du_jour = lambda now=None: []
    now = time.time() + 30 * 86400                           # rien n'est « trop récent » : tout est balayable
    index = rappel.Index()
    rappel.candidats(mem, "chauffe", now=now, index=index)
    return mem, now, index, [(q, e) for q, e in M.requetes() if e]


def ordre(mem, texte, now, index, n, mots=None):
    sauve = rappel.LIMITE_MOTS
    rappel.LIMITE_MOTS = mots or sauve
    try:
        return rappel.candidats(mem, texte, now=now, index=index, limite=n + 50)
    finally:
        rappel.LIMITE_MOTS = sauve


def montres(larges, n, fusion=None):
    """La liste courte (8 au-dessus de la porte, sur le message seul) et le dossier : les N suivants."""
    courte = [x[0] for x in larges if x[1] >= rappel.SEUIL and rappel.passe(x)][:rappel.LIGNES_MAX]
    pris = set(courte)
    suite = fusion if fusion is not None else [x[0] for x in larges]
    return courte, [i for i in suite if i not in pris][:n]


def contextes(q):
    r = sonnet(CONTEXTES.format(q=q), "contextes-v1")
    lignes = [re.sub(r"^[\s\-•*\d.)]+", "", l).strip() for l in r["texte"].splitlines()]
    return [l for l in lignes if len(l.split()) >= 2][:6], r


def fusionner(listes):
    s = {}
    for l in listes:
        for rang, i in enumerate(l):
            s[i] = s.get(i, 0.0) + 1.0 / (K + rang)
    return [i for i, _v in sorted(s.items(), key=lambda x: -x[1])]


def balayage(mem, now, index, qs, avec_contextes=False):
    res, introuvables = {}, None
    exp = {}
    if avec_contextes:
        with ThreadPoolExecutor(4) as ex:
            exp = dict(zip([q for q, _e in qs], ex.map(lambda qe: contextes(qe[0]), qs)))
    for n in TAILLES_BALAYAGE:
        for nom, mots in (("mots_100", None), ("mots_N", max(100, n))):
            if avec_contextes and nom == "mots_100":
                continue
            t0, trouve, lignes, cars = time.time(), 0.0, 0, 0
            manques = set()
            for q, e in qs:
                larges = ordre(mem, q, now, index, n, mots)
                fusion = None
                if avec_contextes:
                    fusion = fusionner([[x[0] for x in larges]] + [[x[0] for x in ordre(mem, c, now, index, n, mots)]
                                                                     for c in exp[q][0]])
                courte, theme = montres(larges, n, fusion)
                vu = set(courte) | set(theme)
                trouve += len(vu & e) / len(e)
                manques |= {(q, i) for i in e - vu}
                lignes += len(vu)
                cars += sum(len(l) + 3 for l in rappel.lignes_courtes(mem, courte + theme, 160))
            res[f"{n}/{nom}"] = {"rappel": round(trouve / len(qs), 3), "lignes": round(lignes / len(qs)),
                                 "caracteres": round(cars / len(qs)), "ms_par_message": round(1000 * (time.time() - t0) / len(qs))}
            if n == TAILLES_BALAYAGE[-1] and nom == "mots_N":
                introuvables = sorted(manques)
            print(("contextes " if avec_contextes else "") + f"{n}/{nom}", json.dumps(res[f"{n}/{nom}"]), flush=True)
    if avec_contextes:
        ms = [exp[q][1]["ms"] for q, _e in qs]
        res["temps_etape_1_ms"] = {"median": sorted(ms)[len(ms) // 2], "max": max(ms)}
        res["contextes_par_message"] = round(sum(len(exp[q][0]) for q, _e in qs) / len(qs), 1)
    return res, introuvables


def elagage(mem, now, index, qs):
    res = {}
    for n in TAILLES_ELAGAGE:
        taches = []
        for q, e in qs:
            larges = ordre(mem, q, now, index, n, max(100, n))
            courte, theme = montres(larges, n)
            prompt = ELAGAGE.format(q=q, n=len(theme), courte="\n".join("- " + l for l in rappel.lignes_courtes(mem, courte, 160)),
                                    theme="\n".join("- " + l for l in rappel.lignes_courtes(mem, theme, 160)))
            taches.append((q, e, set(courte) | set(theme), prompt))
        with ThreadPoolExecutor(3) as ex:
            sorties = list(ex.map(lambda t: sonnet(t[3], "elagage-v1"), taches))
        garde, bout, gardes, faux, ms, jetons, n_garde = 0.0, 0.0, 0, 0, [], [], 0
        for (q, e, vu, _p), s in zip(taches, sorties):
            choisis = {int(x) for x in re.findall(r"#?(\d{1,6})", s["texte"])}
            hors = choisis - vu
            choisis &= vu
            faux += len(hors)
            if e & vu:
                garde += len(choisis & e) / len(e & vu)
                n_garde += 1
            bout += len(choisis & e) / len(e)
            gardes += len(choisis)
            ms.append(s["ms"])
            jetons.append(s["jetons"])
        res[str(n)] = {"garde": round(garde / max(1, n_garde), 3), "au_bout_du_compte": round(bout / len(qs), 3),
                       "gardes_moy": round(gardes / len(qs), 1), "numeros_inventes": faux,
                       "ms_median": sorted(ms)[len(ms) // 2], "jetons_moy": round(sum(jetons) / len(jetons))}
        print("elagage", n, json.dumps(res[str(n)]), flush=True)
    return res


def main():
    quoi = sys.argv[1] if len(sys.argv) > 1 else "tout"
    sortie = Path(__file__).resolve().parent / "data" / f"rappel-taille-{time.strftime('%Y%m%d-%H%M')}.json"
    out = {}
    with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as d:
        mem, now, index, qs = preparer(d)
        try:
            if quoi in ("balayage", "tout"):
                out["balayage"], intr = balayage(mem, now, index, qs)
                out["introuvables_a_2000"] = len(intr)
            if quoi in ("contextes", "tout"):
                out["contextes"], intr_c = balayage(mem, now, index, qs, avec_contextes=True)
                out["introuvables_a_2000_avec_contextes"] = len(intr_c)
                if quoi == "tout":
                    out["retrouves_par_les_contextes"] = len(set(intr) - set(intr_c))
            if quoi in ("elagage", "tout"):
                out["elagage"] = elagage(mem, now, index, qs)
        except Arret as a:
            out["arret"] = f"limite d'usage : {a}"
            print("ARRÊT (limite d'usage) — le cache garde ce qui est fait ; relancer plus tard reprend.", flush=True)
        finally:
            mem.db.close()
            sortie.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(json.dumps({k: v for k, v in out.items() if not isinstance(v, dict)}, ensure_ascii=False))
    print("écrit :", sortie)


if __name__ == "__main__":
    main()
