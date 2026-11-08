"""Le tri des souvenirs : Haiku aussi bon que Sonnet, et plus rapide ? (28/10, Ahmed : « accélérer le tri sans rien couper »)

Le tri (cockpit, trierSouvenirs) est un `claude -p` à part qui lit le dossier du thème (~500 lignes en direct) et rend les
numéros utiles : 7 s en médiane, 90 % du temps de préparation d'un tour (backtest_preparation.py). Même banc que le 26/10
(eval/rappel_taille.py : copie de la mémoire, 35 requêtes-vérité, même consigne d'élagage), à N = 500 (la taille du
direct), Sonnet contre Haiku, le même jour, sur la même copie.

CRITÈRES FIGÉS AVANT (28/10, ~11:00) — Haiku remplace Sonnet pour le tri seulement si, à N = 500 :
  T1 : « garde » de Haiku ≥ celle de Sonnet − 0,02 ;
  T2 : « au bout du compte » de Haiku ≥ celui de Sonnet − 0,02 ;
  T3 : numéros inventés par Haiku ≤ ceux de Sonnet + 1 ;
  T4 : temps médian de Haiku ≤ 0,7 × celui de Sonnet.
PRÉDICTIONS (Claude Code, avant la mesure) : Sonnet garde ≈ 0,99 (comme le 26/10) en ≈ 5 s ; Haiku garde 0,95 à 0,99 en ≈ 3,5 s ;
T4 passe de justesse (l'aller-retour fixe de ~3 s pèse sur les deux) ; probabilité que les quatre passent : 45 %.
RÉSULTAT (28/10, 10:54, tri-modeles-20261028-1054.json) : Sonnet garde 0,981 / au bout du compte 0,949 / 0 inventé / 5,4 s ;
Haiku 0,904 / 0,874 / 18 inventés / 4,8 s. T1 à T4 échouent : Sonnet reste. Prédiction (45 % que tout passe) : fausse.
AMENDEMENT (28/10, ~11:20, avant la mesure) : un troisième essai, Sonnet en effort bas (--effort low), avec les mêmes critères
T1 à T4 contre Sonnet par défaut (la mesure de 10:54, en cache). Prédiction : garde ≥ 0,96, temps médian ≈ 4,5 s, T4 échoue
(le temps tient surtout à la lecture des ~56 k jetons, pas à la réflexion) ; probabilité que les quatre passent : 25 %.
Rien n'est écrit dans la vraie mémoire ; le cache (bancs/rappel-taille) garde numéros et mesures, par modèle.
    python eval/latence/tri_modeles.py"""
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

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent))
sys.path.insert(0, str(ICI.parent.parent))
import rappel  # noqa: E402
import rappel_taille as RT  # noqa: E402

N = 500
MODELES = ("sonnet", "haiku")
CONFIGS = {"sonnet": ["--model", "sonnet"], "haiku": ["--model", "haiku"], "sonnet-bas": ["--model", "sonnet", "--effort", "low"]}


def appel(prompt, modele):
    RT.CACHE.mkdir(parents=True, exist_ok=True)
    f = RT.CACHE / f"tri-{modele}-{hashlib.sha256(prompt.encode()).hexdigest()[:24]}.json"
    if f.exists():
        return json.loads(f.read_text())
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    t0 = time.time()
    p = subprocess.run([str(RT.CLAUDE), "-p", *CONFIGS[modele], "--max-turns", "2", "--tools", "", "--restricted",
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
        if RT.LIMITE_USAGE.search(erreur):
            raise RT.Arret(erreur[:300])
        raise RuntimeError(erreur[:300] or f"code {p.returncode}")
    u = o.get("usage") or {}
    r = {"texte": texte, "ms": ms, "jetons": int(u.get("input_tokens", 0)) + int(u.get("cache_creation_input_tokens", 0))
         + int(u.get("cache_read_input_tokens", 0))}
    f.write_text(json.dumps(r, ensure_ascii=False))
    return r


def mesurer(taches, sorties):
    garde, bout, gardes, faux, ms, n_garde = 0.0, 0.0, 0, 0, [], 0
    for (q, e, vu, _p), s in zip(taches, sorties):
        choisis = {int(x) for x in re.findall(r"#?(\d{1,6})", s["texte"])}
        faux += len(choisis - vu)
        choisis &= vu
        if e & vu:
            garde += len(choisis & e) / len(e & vu)
            n_garde += 1
        bout += len(choisis & e) / len(e)
        gardes += len(choisis)
        ms.append(s["ms"])
    ms.sort()
    return {"garde": round(garde / max(1, n_garde), 3), "au_bout_du_compte": round(bout / len(taches), 3),
            "gardes_moy": round(gardes / len(taches), 1), "numeros_inventes": faux, "ms_median": ms[len(ms) // 2],
            "ms_p90": ms[int(0.9 * len(ms))]}


def main():
    out = {"n": N}
    with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as d:
        mem, now, index, qs = RT.preparer(d)
        try:
            taches = []
            for q, e in qs:
                larges = RT.ordre(mem, q, now, index, N, max(100, N))
                courte, theme = RT.montres(larges, N)
                prompt = RT.ELAGAGE.format(q=q, n=len(theme), courte="\n".join("- " + l for l in rappel.lignes_courtes(mem, courte, 160)),
                                           theme="\n".join("- " + l for l in rappel.lignes_courtes(mem, theme, 160)))
                taches.append((q, e, set(courte) | set(theme), prompt))
            for modele in (sys.argv[1:] or MODELES):
                with ThreadPoolExecutor(3) as ex:
                    sorties = list(ex.map(lambda t: appel(t[3], modele), taches))
                out[modele] = mesurer(taches, sorties)
                print(modele, json.dumps(out[modele]), flush=True)
            s, h = out["sonnet"], out.get("haiku") or out.get("sonnet-bas")
            out["criteres"] = {"T1": h["garde"] >= s["garde"] - 0.02, "T2": h["au_bout_du_compte"] >= s["au_bout_du_compte"] - 0.02,
                               "T3": h["numeros_inventes"] <= s["numeros_inventes"] + 1, "T4": h["ms_median"] <= 0.7 * s["ms_median"]}
        except RT.Arret as a:
            out["arret"] = f"limite d'usage : {a}"
        finally:
            mem.db.close()
    sortie = ICI / f"tri-modeles-{time.strftime('%Y%m%d-%H%M')}.json"
    sortie.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(json.dumps(out.get("criteres"), ensure_ascii=False), "écrit :", sortie)


if __name__ == "__main__":
    main()
