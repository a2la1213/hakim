"""(10/11, agent paroles) Ce qui arrive à Hakim des PAROLES que joue le téléphone (un live, une musique), étape par étape, en lecture seule :
le bloc de 8 s, la séparation (voix séparée prête ou non), la file et la transcription (Whisper partagé avec sa voix, ou Azure), les
blocs sautés ou vides, le fil, ses pensées de piste (entendu.jsonl), et ce que son message en voit (le « vécu » de ses échanges).
Usage : python3 -I paroles-telephone.py AAAA-MM-JJTHH:MM AAAA-MM-JJTHH:MM [nom]
Rien n'est écrit : seulement lu (~/AIOS/jarvis)."""
import collections
import datetime
import json
import os
import re
import sys

JARVIS = os.path.expanduser(os.environ.get("JARVIS_DIR", "~/AIOS/jarvis"))
BLOC_MS = 8000


def lignes(nom, filtre=None):
    try:
        with open(os.path.join(JARVIS, nom), encoding="utf-8") as h:
            for l in h:
                if not l.startswith("{") or (filtre and filtre not in l):
                    continue
                try:
                    yield json.loads(l)
                except ValueError:
                    pass
    except OSError:
        return


def q(v, p):
    v = sorted(x for x in v if isinstance(x, (int, float)))
    return v[min(len(v) - 1, int(p * len(v)))] if v else None


def s(ms):
    return "-" if ms is None else f"{ms / 1000:.1f} s"


def stats(nom, v, unite="ms"):
    v = [x for x in v if isinstance(x, (int, float))]
    if not v:
        return f"{nom} : aucune mesure"
    if unite == "ms":
        return f"{nom} : n={len(v)}, médiane {s(q(v, .5))}, p90 {s(q(v, .9))}"
    return f"{nom} : n={len(v)}, médiane {q(v, .5)}, p90 {q(v, .9)}"


def heure(t):
    return datetime.datetime.fromtimestamp(t / 1000).strftime("%d/%m %H:%M:%S")


def mesurer(a, b, nom=""):
    out = [f"== {nom} {heure(a)} → {heure(b)}"]
    # 1) les blocs confirmés (son_ecoute : le téléphone le dit quand la grande oreille a rendu un texte d'au moins 3 caractères)
    blocs = []
    for o in lignes("corps-evenements.jsonl", '"son_ecoute"'):
        d = o.get("details") or {}
        t, deb = o.get("t") or o.get("ts"), d.get("debut_ms")
        if isinstance(t, (int, float)) and isinstance(deb, (int, float)) and a <= deb <= b:
            blocs.append({"t": t, "debut": deb, "texte": str(d.get("texte") or ""), "air": d.get("par") == "air"})
    blocs.sort(key=lambda x: x["debut"])
    out.append(f"blocs du téléphone confirmés (son_ecoute) : {len(blocs)}, {sum(len(x['texte'].split()) for x in blocs)} mots")
    out.append("  " + stats("confirmé après le DÉBUT du bloc", [x["t"] - x["debut"] for x in blocs]))
    out.append("  " + stats("confirmé après la FIN du bloc (8 s)", [x["t"] - x["debut"] - BLOC_MS for x in blocs]))
    # continuité : dans une suite de blocs à moins de 60 s l'un de l'autre, combien de blocs de 8 s manquent (sautés, vides ou muets)
    attendus = manquants = 0
    for x, y in zip(blocs, blocs[1:]):
        ecart = y["debut"] - x["debut"]
        if ecart <= 60000:
            k = max(1, round(ecart / BLOC_MS))
            attendus += k
            manquants += k - 1
    if attendus:
        out.append(f"  continuité (suites de blocs à < 60 s) : {manquants} blocs de 8 s sans texte sur {attendus} ({100 * manquants / attendus:.0f} %)")
    # 2) le diagnostic du Mac (tronqué à 2 000 lignes : seulement la dernière heure environ)
    diag = [o for o in lignes("voix-diagnostic.jsonl") if a <= (o.get("t") or 0) <= b]
    if diag:
        out.append(f"diagnostic du Mac couvert de {heure(diag[0]['t'])} à {heure(diag[-1]['t'])}")
        tp = [o for o in diag if o.get("e") == "trois_pistes_voix"]
        sautes = [o for o in diag if o.get("e") == "transcription_sautee" and o.get("source") == "telephone"]
        tel = [o for o in diag if o.get("e") == "transcription_serveur" and o.get("octets") == 256044]
        if tp or sautes:
            n = len(tp) + len(sautes)
            out.append(f"  blocs de 8 s reçus : {n} ; sautés par la file (trop vieux ou de trop) : {len(sautes)} ({100 * len(sautes) / n:.0f} %)")
            sep = [o for o in tp if o.get("separee")]
            out.append(f"  voix séparée prête à temps : {len(sep)}/{len(tp)} ; " + stats("attente de la voix séparée", [o.get("attente_ms") for o in tp]))
            vides = [o for o in tp if not o.get("mots")]
            out.append(f"  transcrits sans un mot (silence de Whisper, filtres) : {len(vides)}/{len(tp)}")
            out.append("  " + stats("file + transcription après la séparation", [o.get("ms") for o in tp]))
            out.append("  " + stats("mots par bloc transcrit", [o.get("mots") for o in tp if o.get("mots")], "n"))
        if tel:
            out.append("  " + stats("attente dans la file de l'oreille (bloc du téléphone)", [o.get("attente_file_ms") for o in tel]))
            out.append(f"  pendant une synthèse de sa voix : {sum(1 for o in tel if o.get('synthese_en_cours'))}/{len(tel)}")
        vif = [o for o in diag if o.get("e") == "vif_reseau" and o.get("appareil") == "telephone"]
        if vif:
            out.append("  " + stats("mots vifs (oreille vive) aller-retour", [o.get("aller_retour_ms") for o in vif]))
            out.append("  " + stats("mots vifs, calcul seul", [o.get("calcul_ms") for o in vif]))
        az = [o for o in diag if o.get("e") == "transcription_azure"]
        if az:
            out.append("  " + stats("Azure (morceaux de papa)", [o.get("ms") for o in az]))
        azp = [o for o in diag if o.get("e") == "paroles_azure"]
        if azp:
            out.append("  " + stats("Azure (paroles du téléphone)", [o.get("ms") for o in azp]) + f" ; repli Whisper {sum(1 for o in azp if o.get('repli'))}/{len(azp)}"
                       f" ; voix séparée {sum(1 for o in azp if o.get('separee'))}/{len(azp)} ; vides {sum(1 for o in azp if not o.get('mots'))}/{len(azp)}"
                       f" ; facturé {sum(o.get('facture_s') or 0 for o in azp) / 60:.1f} min")
        vd = [o for o in diag if o.get("e") == "voix_telephone_direct"]
        if vd:
            out.append("  " + stats("qui parle au téléphone (retard)", [o.get("retard_ms") for o in vd]))
    # 3) ses pensées de piste (entendu.jsonl) : ce que son subconscient a pu penser de chaque phrase du téléphone
    ent = [o for o in lignes("entendu.jsonl", '"telephone"') if a <= (o.get("t") or 0) <= b and o.get("source") == "telephone"]
    if ent:
        err = collections.Counter(("limite de la semaine" if "limit" in str(o.get("erreur")) else str(o.get("erreur"))[:30]) for o in ent if o.get("erreur"))
        comp = [o for o in ent if o.get("comprend")]
        out.append(f"phrases du téléphone pensées (entendu) : {len(ent)} ; comprises : {len(comp)} ; erreurs : {dict(err)}")
        out.append("  " + stats("mots par phrase", [len(str(o.get('morceau') or '').split()) for o in ent], "n"))
    # 4) son garde du live (live.jsonl)
    lv = [o for o in lignes("live.jsonl") if a <= (o.get("t") or 0) <= b]
    if lv:
        mins = [o for o in lv if o.get("e") == "minute"]
        out.append(f"garde du live : {len(mins)} minutes, {sum(o.get('phrases') or 0 for o in mins)} phrases, "
                   f"{sum(o.get('appels_total') or 0 for o in mins)} appels, {sum(o.get('dits') or 0 for o in mins)} dits")
    # 5) ce que son message en voit (le vécu de chaque échange pendant que le téléphone joue)
    vus = []
    for o in lignes("echanges-a-memoriser.jsonl"):
        ts = o.get("ts") or 0
        if not (a <= ts <= b):
            continue
        v = str(o.get("vecu") or "")
        m = re.search(r"Le téléphone \(dedans\) · parole : (.*?) · musique :", v)
        if not m:
            continue
        ph = re.findall(r"([−+-]\d+,\d) s(?: [^«]*)?« ([^»]*) »", m.group(1))
        if not ph:
            continue
        vieux = min(float(x[0].replace("−", "-").replace(",", ".")) for x in ph)
        vus.append({"phrases": len(ph), "mots": sum(len(x[1].split()) for x in ph), "vieux_s": vieux})
    if vus:
        out.append(f"messages de papa pendant que le téléphone parlait : {len(vus)}")
        out.append("  " + stats("phrases du téléphone vues par message", [x["phrases"] for x in vus], "n"))
        out.append("  " + stats("mots du téléphone vus par message", [x["mots"] for x in vus], "n"))
        out.append(f"  la plus ancienne phrase vue : {min(x['vieux_s'] for x in vus):.1f} s (fenêtre de ses trois pistes : 30 s)")
    return "\n".join(out)


def main():
    a = datetime.datetime.fromisoformat(sys.argv[1]).timestamp() * 1000
    b = datetime.datetime.fromisoformat(sys.argv[2]).timestamp() * 1000
    print(mesurer(a, b, sys.argv[3] if len(sys.argv) > 3 else ""))
    try:
        d = json.load(open(os.path.join(JARVIS, "delais-fil.json"))).get("delais") or {}
        print("délais du fil (les 200 derniers, au moment de la lecture) : " + " ; ".join(
            f"{k} médiane {s(d[k]['mediane'])} p90 {s(d[k]['p90'])}" for k in ("telephone", "qui_telephone", "musique_telephone", "papa") if k in d))
    except (OSError, ValueError):
        pass


if __name__ == "__main__":
    main()
