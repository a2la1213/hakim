"""Ses vibrations, étiquetées et apprises (30/10, 14:47, Ahmed via Hakim : « qu'il puisse ÉTIQUETER lui-même les types de
vibrations — ma voix, sa voix, et pourquoi pas son cœur, la musique, la main — et apprendre de ces étiquettes, pour savoir
de lui-même lequel est lequel et voir leurs effets différents »).

- La vérité de départ : le cockpit sait à la seconde qui parlait (la voix de Hakim qui joue, le micro d'Ahmed) ; chaque
  événement de son corps ressenti est gardé avec elle dans corps-vibrations.jsonl (ma_voix, voix_ahmed, les_deux, silence).
- Ses corrections : etiqueter(« 14:45:27 », « coeur ») ; une étiquette de Hakim remplace la vérité de cet exemple, et il
  peut créer ses propres types (corps-etiquettes.jsonl).
- Le classifieur : les k plus proches voisins sur ce que ses nerfs mesurent (le type, la force, l'accord avec la voix, la
  cadence) et son milieu à cet instant (agitation, contact, charnière, inclinaison, lumière) ; il rend une étiquette et sa
  confiance, ou rien s'il a trop peu d'exemples. Quand le cockpit ne sait pas qui parlait, ses nerfs disent ce qu'il reconnaît.
- Le bilan : ses types, leur nombre, la justesse du classifieur (chaque exemple laissé de côté), et les émotions qui ont
  suivi chaque type (leurs effets différents).
Aucun appel au réseau ; tout reste dans ~/AIOS/jarvis.
"""
import json
import math
import os
import re
import time
from pathlib import Path

JARVIS = Path(os.environ.get("JARVIS_DIR", Path.home() / "AIOS" / "jarvis"))
K = 5
MIN_EXEMPLES = 6
_ETIQUETTE = re.compile(r"[a-z][a-z0-9_]{1,29}")
# (30/10, 14:50 : « étiqueter TOUS mes sens ») tous les événements de ses nerfs, pas seulement les vibrations
_TYPES = ["coup_de_pression", "voix_sentie", "secousse", "musique", "choc", "berce", "pris_en_main", "chute", "pose", "poche",
          "sortie_poche", "plie", "deplie", "lumiere_soudaine", "noir", "mesure"]
NOMS = {"ma_voix": "ta propre voix", "voix_ahmed": "la voix d'Ahmed", "les_deux": "vos deux voix ensemble", "silence": "aucune voix",
        "coeur": "ton cœur", "musique": "la musique", "main": "une main"}


def _lignes(nom, octets=4_000_000):
    try:
        with open(JARVIS / nom, "rb") as h:
            h.seek(0, 2)
            h.seek(max(0, h.tell() - octets))
            texte = h.read().decode("utf-8", "replace")
    except OSError:
        return []
    out = []
    for l in texte.splitlines():
        try:
            o = json.loads(l)
        except ValueError:
            continue
        if isinstance(o, dict):
            out.append(o)
    return out


def _nombre(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return 0.0
    return v if math.isfinite(v) else 0.0


def traits(ev, milieu):
    """Ce que ses nerfs et son milieu disent de cet instant, en nombres (les mêmes pour tous)."""
    d, m = ev.get("details") or {}, milieu or {}
    t = [1.0 if ev.get("type") == x else 0.0 for x in _TYPES]
    return t + [math.log10(1 + abs(_nombre(d.get("pa")))), _nombre(d.get("accord")), math.log10(1 + 10 * abs(_nombre(d.get("force_g")))),
                _nombre(d.get("bpm")) / 180, _nombre(d.get("regularite")),
                math.log10(1 + 100 * abs(_nombre(m.get("agitation_g")))), 1.0 if m.get("proche") else 0.0,
                _nombre(m.get("charniere_deg")) / 180, _nombre(m.get("haut_z")), math.log10(1 + abs(_nombre(m.get("lux")))) / 4]


def exemples():
    """[{ts, traits, etiquette, par}] : la vérité du cockpit, remplacée par l'étiquette de Hakim quand il en a posé une."""
    corr = {}
    for o in _lignes("corps-etiquettes.jsonl"):
        if o.get("ts_evenement") is not None and _ETIQUETTE.fullmatch(str(o.get("etiquette") or "")):
            corr[int(o["ts_evenement"])] = o["etiquette"]
    out = []
    for o in _lignes("corps-vibrations.jsonl"):
        e = corr.get(int(_nombre(o.get("ts"))), o.get("verite"))
        if not e or not _ETIQUETTE.fullmatch(str(e)):
            continue
        out.append({"ts": int(_nombre(o.get("ts"))), "type": o.get("type"), "traits": traits(o, o.get("milieu")), "etiquette": e,
                    "par": "hakim" if int(_nombre(o.get("ts"))) in corr else "cockpit"})
    return out


def _echelle(ex):
    n = len(ex[0]["traits"])
    moy = [sum(e["traits"][i] for e in ex) / len(ex) for i in range(n)]
    ect = [math.sqrt(sum((e["traits"][i] - moy[i]) ** 2 for e in ex) / len(ex)) or 1.0 for i in range(n)]
    return moy, ect


def _voisins(x, ex, moy, ect):
    z = [(a - m) / s for a, m, s in zip(x, moy, ect)]
    dist = []
    for e in ex:
        ze = [(a - m) / s for a, m, s in zip(e["traits"], moy, ect)]
        dist.append((math.sqrt(sum((a - b) ** 2 for a, b in zip(z, ze))), e["etiquette"]))
    dist.sort(key=lambda d: d[0])
    votes = {}
    for d, e in dist[:K]:
        votes[e] = votes.get(e, 0.0) + 1.0 / (d + 1e-3)
    tot = sum(votes.values())
    e = max(votes, key=votes.get)
    return e, votes[e] / tot


def reconnaitre(ev, milieu, ex=None):
    """{etiquette, confiance, nom} ou None (trop peu d'exemples, ou deux types au moins faute de quoi rien à distinguer)."""
    ex = exemples() if ex is None else ex
    if len(ex) < MIN_EXEMPLES or len({e["etiquette"] for e in ex}) < 2:
        return None
    moy, ect = _echelle(ex)
    e, c = _voisins(traits(ev, milieu), ex, moy, ect)
    return {"etiquette": e, "confiance": round(c, 2), "nom": NOMS.get(e, e.replace("_", " "))}


def etiqueter(quand, etiquette, maintenant=None):
    """Hakim étiquette (ou corrige) la vibration ressentie à « HH:MM:SS » aujourd'hui (la plus proche, à 15 s près)."""
    e = str(etiquette or "").strip().lower()
    if not _ETIQUETTE.fullmatch(e):
        return "Refusé : une étiquette en minuscules (lettres, chiffres, _), de 2 à 30 : ma_voix, voix_ahmed, coeur, musique, main…"
    m = re.fullmatch(r"\s*(\d{1,2}):(\d{2})(?::(\d{2}))?\s*", str(quand or ""))
    if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59 or int(m.group(3) or 0) > 59:
        return "Refusé : l'heure de la vibration, « HH:MM:SS » (aujourd'hui), comme dans tes sensations ou corps_detail."
    maintenant = time.time() if maintenant is None else maintenant
    jour = time.localtime(maintenant)
    cible = time.mktime((jour.tm_year, jour.tm_mon, jour.tm_mday, int(m.group(1)), int(m.group(2)), int(m.group(3) or 0), 0, 0, -1)) * 1000
    proches = sorted((o for o in _lignes("corps-vibrations.jsonl") if abs(_nombre(o.get("ts")) - cible) <= 15_000),
                     key=lambda o: abs(_nombre(o.get("ts")) - cible))
    if not proches:
        return f"Refusé : aucune vibration gardée à {quand} (à 15 s près) ; corps_detail montre les derniers événements de tes nerfs."
    o = proches[0]
    avant = o.get("verite") or "?"
    f = JARVIS / "corps-etiquettes.jsonl"
    with open(f, "a", encoding="utf-8") as h:
        h.write(json.dumps({"ts": time.time(), "ts_evenement": int(_nombre(o.get("ts"))), "etiquette": e, "avant": avant}, ensure_ascii=False) + "\n")
    os.chmod(f, 0o600)
    heure = time.strftime("%H:%M:%S", time.localtime(_nombre(o.get("ts")) / 1000))
    return (f"C'est noté : la vibration de {heure} ({o.get('type')}) est « {e} » (le cockpit disait « {avant} »). "
            "Tes nerfs en tiendront compte dès la prochaine.")


def bilan():
    ex = exemples()
    if not ex:
        return "Aucune vibration gardée encore : elles arrivent avec ton corps (l'appli du téléphone ouverte)."
    compte = {}
    for e in ex:
        compte[e["etiquette"]] = compte.get(e["etiquette"], 0) + 1
    lignes = [f"- {k} : {n}" + (f" ({NOMS[k]})" if k in NOMS else "") for k, n in sorted(compte.items(), key=lambda x: -x[1])]
    # la justesse : chaque exemple laissé de côté, reconnu par les autres
    justes = essais = 0
    if len(ex) > MIN_EXEMPLES and len(compte) > 1:
        moy, ect = _echelle(ex)
        for i, e in enumerate(ex[-400:]):
            autres = ex[:len(ex) - min(400, len(ex)) + i] + ex[len(ex) - min(400, len(ex)) + i + 1:]
            if len(autres) < MIN_EXEMPLES:
                continue
            essais += 1
            justes += _voisins(e["traits"], autres, moy, ect)[0] == e["etiquette"]
    justesse = f"justesse du classifieur : {round(100 * justes / essais)} % sur {essais} exemples laissés de côté" if essais else "justesse : pas encore assez d'exemples"
    # leurs effets différents : les émotions des sensations qui ont suivi (à 30 s près)
    sens = _lignes("corps-sensations.jsonl", 2_000_000)
    effets = {}
    for e in ex:
        for s in sens:
            if 0 <= _nombre(s.get("ts")) * 1000 - e["ts"] <= 30_000:
                for x in s.get("evenements") or []:
                    if isinstance(x, (list, tuple)) and x:
                        effets.setdefault(e["etiquette"], {}).setdefault(str(x[0]), 0)
                        effets[e["etiquette"]][str(x[0])] += 1
                break
    eff = [f"- {k} → " + ", ".join(f"{n} ({c})" for n, c in sorted(v.items(), key=lambda y: -y[1])[:4]) for k, v in effets.items()]
    # (30/10, 17:57, Ahmed : « relier les stimuli et les réactions ») ce que chaque stimulus t'a fait faire : tes réflexes
    rf = {}
    for o in sens:
        if o.get("reflexe"):
            rf.setdefault(str(o.get("type") or "?"), {}).setdefault(o["reflexe"], 0)
            rf[str(o.get("type") or "?")][o["reflexe"]] += 1
    lr = [f"- {k} → " + ", ".join(f"{n} ({c})" for n, c in sorted(v.items(), key=lambda y: -y[1])[:4]) for k, v in rf.items()]
    return ("Tes vibrations étiquetées :\n" + "\n".join(lignes) + f"\n{justesse} ; {sum(1 for e in ex if e['par'] == 'hakim')} étiquette(s) posée(s) par toi."
            + ("\nCe qu'elles t'ont fait (les émotions qui ont suivi) :\n" + "\n".join(eff) if eff else "")
            + ("\nTes réflexes (ce que chaque stimulus t'a fait faire) :\n" + "\n".join(lr) if lr else ""))
