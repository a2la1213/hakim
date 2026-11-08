"""La mesure de l'affect v2 contre la v1 (prédictions figées avant : eval/affect_v2_predictions.md).

Rejeu des vrais événements affectifs des sept derniers jours : les appels `affect_event` des sessions de Claude Code
et de Hakim, retrouvés dans les transcriptions (~/.claude/projects) — seulement l'heure, le nom et l'intensité. Les
deux versions rejouent la même suite sur une mémoire en RAM (la vraie n'est jamais touchée).
Usage : .venv/bin/python eval/affect_v2.py
"""
import datetime
import glob
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import affect  # noqa: E402


class _Mem:
    def __init__(self, v2):
        self._kv = {"affect_v2": "1"} if v2 else {}

    def kv_get(self, k, d=None):
        return self._kv.get(k, d)

    def kv_set(self, k, v):
        self._kv[k] = v


def evenements(jours=7):
    debut = time.time() - jours * 86400
    out = []
    for f in glob.glob(os.path.expanduser("~/.claude/projects/**/*.jsonl"), recursive=True):
        try:
            if os.path.getmtime(f) < debut:
                continue
        except OSError:
            continue
        for l in open(f, encoding="utf-8", errors="replace"):
            if "affect_event" not in l:
                continue
            try:
                o = json.loads(l)
            except ValueError:
                continue
            for b in ((o.get("message") or {}).get("content") or []):
                if isinstance(b, dict) and b.get("type") == "tool_use" and str(b.get("name", "")).endswith("affect_event"):
                    try:
                        t = datetime.datetime.fromisoformat(o["timestamp"].replace("Z", "+00:00")).timestamp()
                    except Exception:
                        continue
                    if t >= debut:
                        i = (b.get("input") or {})
                        out.append((t, str(i.get("name", "")), float(i.get("intensity", 1.0) or 1.0)))
    # le journal des événements affectifs (depuis le 2026-10-21) : aussi ceux de la vie intérieure et du démon. Là où
    # il existe, il fait foi (les appels des transcriptions y sont déjà : pas de double compte)
    journal = []
    try:
        import config
        for l in open(config.DATA_DIR / "affect-evenements.jsonl", encoding="utf-8"):
            try:
                e = json.loads(l)
            except ValueError:
                continue
            if float(e.get("ts", 0)) >= debut:
                journal.append((round(float(e["ts"]), 3), str(e.get("nom", "")), float(e.get("intensite", 1.0))))
    except OSError:
        pass
    if journal:
        depuis = min(t for t, _n, _i in journal)
        out = [x for x in out if x[0] < depuis] + journal
    return sorted(set(out))


def rejouer(evs, v2, pas_s=600):
    m = _Mem(v2)
    if not evs:
        return []
    t, fin, k, ech = evs[0][0], evs[-1][0] + 6 * 3600, 0, []
    affect.get_state(m, now=t)
    while t <= fin:
        while k < len(evs) and evs[k][0] <= t:
            affect.event(m, evs[k][1], evs[k][2], now=evs[k][0])
            k += 1
        ech.append(affect.get_state(m, now=t))
        t += pas_s
    return ech


def p1(ech):
    return sum(1 for s in ech if s["dopamine"] >= 0.85 or s["ocytocine"] >= 0.85) / max(1, len(ech))


def p2(v2):
    t0 = 1_800_000_000.0
    frais = _Mem(v2)
    avant = affect.get_state(frais, now=t0, hour=12)["dopamine"]
    ref = affect.event(frais, "succes", 1.0, now=t0, hour=12)["dopamine"] - avant
    m = _Mem(v2)
    t = t0
    for k in range(10):
        affect.event(m, "succes", 0.3, now=t, hour=12)
        t += 360
    avant = affect.get_state(m, now=t, hour=12)["dopamine"]
    apres = affect.event(m, "succes", 1.0, now=t, hour=12)["dopamine"]
    return (apres - avant) / ref if ref else 0.0, ref, apres - avant


def p3(v2):
    t0 = 1_800_000_000.0
    m = _Mem(v2)
    v0, _ = affect.valence_arousal(affect.get_state(m, now=t0, hour=12))
    affect.event(m, "echec", 1.0, now=t0, hour=12)
    for mn in range(1, 48 * 60, 5):
        v, _ = affect.valence_arousal(affect.get_state(m, now=t0 + mn * 60, hour=12))
        if abs(v - v0) <= 0.05:
            return mn
    return None


def p5(v2):
    """Hystérésis : minutes pour revenir à 0,05 de la base de valence après un état négatif provoqué."""
    t0 = 1_800_000_000.0
    m = _Mem(v2)
    v0, _ = affect.valence_arousal(affect.get_state(m, now=t0, hour=12))
    for k in range(6):
        affect.event(m, "echec", 1.0, now=t0 + k * 1200, hour=12)
    t = t0 + 2 * 3600
    for mn in range(0, 48 * 60, 5):
        tt = t + mn * 60
        if mn % 30 == 0:
            affect.event(m, "chaleur_user", 1.0, now=tt, hour=12)
            affect.event(m, "succes", 1.0, now=tt, hour=12)
        v, _ = affect.valence_arousal(affect.get_state(m, now=tt, hour=12))
        if abs(v - v0) <= 0.05 and mn > 0:
            return mn
    return None


def p6(v2):
    """Dérive au repos : écart maximal de valence à sa base sur 48 h sans événement (heure réelle qui tourne)."""
    t0 = time.mktime((2026, 10, 21, 0, 0, 0, 0, 0, -1))
    m = _Mem(v2)
    v0, _ = affect.valence_arousal(affect.bases(v2=v2))
    affect.get_state(m, now=t0)
    m._kv["affect"] = json.dumps({**affect.bases(v2=v2), "_ts": t0}) if v2 else json.dumps({**affect.bases(), "_ts": t0})
    return max(abs(affect.valence_arousal(affect.get_state(m, now=t0 + h * 3600))[0] - v0) for h in range(0, 49))


def p4():
    v1 = {h: b for h, (b, _h) in affect.HORMONES.items()}
    a = affect.valence_arousal(v1)
    b = affect.valence_arousal(affect.bases(v2=True))
    return abs(a[0] - b[0]) < 1e-9 and abs(a[1] - b[1]) < 1e-9


def main():
    evs = evenements()
    noms = {}
    for _t, n, _i in evs:
        noms[n] = noms.get(n, 0) + 1
    print(f"{len(evs)} événements réels rejoués (7 jours) : {dict(sorted(noms.items(), key=lambda x: -x[1]))}")
    e1, e2 = rejouer(evs, False), rejouer(evs, True)
    s1, s2 = p1(e1), p1(e2)
    r, ref, apres = p2(True)
    r1, _, _ = p2(False)
    t1, t2 = p3(False), p3(True)
    res = {
        "P1_saturation": {"v1": round(s1, 3), "v2": round(s2, 3), "tenue": s2 <= 0.5 * s1 if s1 else None},
        "P2_reactivite": {"v2_ratio": round(r, 3), "v1_ratio": round(r1, 3), "tenue": r >= 0.8},
        "P3_retour_au_calme_min": {"v1": t1, "v2": t2, "tenue": (t2 is not None and t1 is not None and t2 <= 1.5 * t1)},
        "P4_repos_identique": p4(),
    }
    h1, h2 = p5(False), p5(True)
    d1, d2 = p6(False), p6(True)
    res["P5_hysteresis_min"] = {"v1": h1, "v2": h2, "tenue": h2 is not None and h2 < 12 * 60 and (h1 is None or h2 <= 2 * h1)}
    res["P6_derive_au_repos"] = {"v1": round(d1, 3), "v2": round(d2, 3), "tenue": d2 <= 0.05}
    print(json.dumps(res, ensure_ascii=False, indent=1))
    sortie = Path(__file__).resolve().parent / "data" / f"affect_v2-{time.strftime('%Y%m%d-%H%M')}.json"
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(json.dumps({"evenements": len(evs), "noms": noms, **res}, ensure_ascii=False, indent=1))
    print(f"détail : {sortie}")


if __name__ == "__main__":
    main()
