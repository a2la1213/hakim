"""(09/11, agent vitesse) Le bilan de vitesse d'une fenêtre de temps, en lecture seule : où part le temps d'un tour oral, la file de la
grande oreille, la préparation et le cerveau, les appels de modèles par message, ce que l'orchestrateur a refusé, la charge du Mac.
Usage : python3 -I bilan-vitesse.py 18:30 19:30 [AAAA-MM-JJ]   (par défaut : aujourd'hui)"""
import collections
import datetime
import json
import os
import subprocess
import sys

JARVIS = os.path.expanduser("~/AIOS/jarvis")
LLM = os.path.expanduser("~/Desktop/anamnese/data/llm-appels.jsonl")


def lignes(f):
    try:
        with open(f, encoding="utf-8") as h:
            for l in h:
                if l.startswith("{"):
                    try:
                        yield json.loads(l)
                    except ValueError:
                        pass
    except OSError:
        return


def q(v, p):
    v = sorted(x for x in v if isinstance(x, (int, float)) and x >= 0)
    return v[min(len(v) - 1, int(p * len(v)))] if v else None


def s(ms):
    return "-" if ms is None else f"{ms / 1000:.1f} s"


def main():
    jour = sys.argv[3] if len(sys.argv) > 3 else datetime.date.today().isoformat()
    a = datetime.datetime.fromisoformat(f"{jour}T{sys.argv[1]}").timestamp() * 1000
    b = datetime.datetime.fromisoformat(f"{jour}T{sys.argv[2]}").timestamp() * 1000
    print(f"Fenêtre {jour} {sys.argv[1]}-{sys.argv[2]}")
    diag = [d for d in lignes(os.path.join(JARVIS, "voix-diagnostic.jsonl")) if a <= d.get("t", 0) < b]
    par = collections.defaultdict(list)
    for d in diag:
        par[d.get("e")].append(d)
    tt = par["tour_temps"]
    print(f"\nTour oral (tour_temps, n={len(tt)}) : médiane / p90")
    for k in ("attente_fin_tour_ms", "transcription_ms", "premier_mot_ms", "voix_ms", "total_ms"):
        v = [d.get(k) for d in tt]
        print(f"  {k:22s} {s(q(v, .5)):>8s} / {s(q(v, .9))}")
    print("\nGrande oreille et voix :")
    for e, k in (("transcription_serveur", "ms"), ("transcription_azure", "ms"), ("trois_pistes_voix", "ms"), ("azure_rap", "ms"),
                 ("synthese_azure", "ms"), ("transcription_abandonnee", "ms"), ("transcription_sautee", None)):
        v = [d.get(k) for d in par[e]] if k else []
        print(f"  {e:26s} n={len(par[e]):4d}" + (f"  médiane {s(q(v, .5))}  p90 {s(q(v, .9))}" if k else ""))
    jt = [d for d in lignes(os.path.join(JARVIS, "jetons.jsonl")) if a <= d.get("ts", 0) < b and not d.get("autonome")]
    print(f"\nPréparation et cerveau (jetons, n={len(jt)}) :")
    for k in ("prep_ms", "cerveau_premier_mot_ms"):
        v = [d.get(k) for d in jt]
        print(f"  {k:22s} {s(q(v, .5)):>8s} / {s(q(v, .9))}")
    neufs = sum(1 for d in jt if (d.get("etapes") or {}).get("cerveau_neuf"))
    print(f"  conversations neuves   {neufs}/{len(jt)} ; briefing médian {s(q([(d.get('etapes') or {}).get('briefing') for d in jt if (d.get('etapes') or {}).get('briefing')], .5))}")
    llm = [d for d in lignes(LLM) if a / 1000 <= d.get("ts", 0) < b / 1000]
    ok = sum(1 for d in llm if not d.get("erreur"))
    msgs = [d["ts"] for d in lignes(os.path.join(JARVIS, "journal.jsonl")) if a <= d.get("ts", 0) < b and d.get("qui") == "ahmed"]
    print(f"\nAppels de modèles : {len(llm)} de fond ({ok} aboutis) + {len(jt)} du cerveau, pour {len(msgs)} messages de papa")
    autour = sorted(sum(1 for d in llm if t / 1000 - 30 <= d["ts"] < t / 1000 + 20) for t in msgs)
    if autour:
        print(f"  par message, de -30 s à +20 s : médiane {autour[len(autour) // 2]}, p90 {autour[int(.9 * len(autour))]}, max {autour[-1]}")
    err = collections.Counter(str(d.get("erreur"))[:28] for d in llm if d.get("erreur"))
    print("  erreurs :", dict(err.most_common(5)))
    orch = [d for d in lignes(os.path.join(JARVIS, "orchestre.jsonl")) if a <= d.get("t", 0) < b]
    refus = collections.Counter()
    for d in orch:
        if d.get("e") == "minute":
            refus.update(d.get("refuses") or {})
    print(f"\nOrchestrateur : {len(orch)} lignes ; refus : {dict(refus)} ; "
          f"blocs du téléphone sautés : {sum(1 for d in orch if d.get('e') == 'oreille_saute')} ; "
          f"forfait coupé : {sum(1 for d in orch if d.get('e') == 'forfait_coupe')} fois")
    if b > datetime.datetime.now().timestamp() * 1000 - 60000:
        so = subprocess.run(["/usr/sbin/sysctl", "-n", "kern.memorystatus_level", "vm.swapusage"], capture_output=True, text=True).stdout.split("\n")
        print(f"\nMac maintenant : mémoire libre {so[0]} % ; swap {so[1].strip() if len(so) > 1 else '?'} ; charge {os.getloadavg()[0]:.1f}")


if __name__ == "__main__":
    main()
