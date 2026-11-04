"""(04/11) la vérification des styles d'émotion de sa voix du téléphone (Supertonic 3, M1), avant toute écoute d'Ahmed.

Pour chaque famille et chaque force (styles_supertonic.appliquer), Supertonic dit les mêmes quatre phrases NEUTRES (le style seul
doit porter l'émotion), à 5 étapes comme le téléphone, chaque phrase avec le même bruit pour toutes les voix. Mesures : la
ressemblance à M1 (empreinte_vocale, ResNet34 VoxCeleb), la hauteur moyenne et son étendue (demi-tons), l'énergie (dB), la
durée ; la diction relue par Whisper (diction.py, venv de jarvis). Les mêmes mesures sur les références de Chatterbox donnent
le sens de chaque émotion (famille − neutre).

Critères FIGÉS avant la mesure :
  1. sa voix : ressemblance(style, M1) ≥ b − 0,10, où b = ressemblance de M1 à lui-même avec un autre bruit ;
  2. sa diction : CER moyen ≤ CER(M1) + 0,03, et aucune phrase au-delà de 0,15 ;
  3. l'émotion portée : sur la hauteur moyenne, l'étendue et l'énergie, là où Chatterbox bouge nettement (≥ 0,5 demi-ton,
     ≥ 0,3 demi-ton, ≥ 0,5 dB), le style bouge dans le même sens sur au moins deux, et dans le sens contraire sur aucune.
La force retenue d'une famille : la plus haute qui tient 1 et 2 ; 3 est rapporté tel quel. Puis l'écoute à l'aveugle d'Ahmed,
dans les deux ordres, juge seule (l'émotion entendue n'a pas de mesure automatique).

Usage : <venv supertonic>/bin/python -I eval/supertonic_emotions/verifier.py <modèle supertonic-3> <dossier des styles>
  <dossier des styles> : neutre.json et <famille>.json retrouvés des références ; écrit verification.json à côté."""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parents[1] / "jarvis"))
sys.path.insert(0, str(ICI))
import empreinte_vocale as EV  # noqa: E402
import styles_supertonic as S  # noqa: E402
from phrases import PHRASES  # noqa: E402

FORCES = (0.5, 1.0, 1.5, 2.0, 3.0)
ETAPES, VITESSE = 5, 1.05
NET = {"f0_st": 0.5, "etendue_st": 0.3, "energie_db": 0.5}
JARVIS_PY = ICI.parents[1] / "jarvis" / ".venv" / "bin" / "python"
REFS = Path.home() / "AIOS" / "jarvis" / "supertonic-emotions" / "references"


def reechantillonner(x, sr, cible=16000):
    """par la transformée de Fourier : rien au-dessus de la moitié de la cible ne se replie"""
    n = int(round(len(x) * cible / sr))
    X = np.fft.rfft(np.asarray(x, dtype=np.float64))
    return (np.fft.irfft(X[: n // 2 + 1], n=n) * n / len(x)).astype(np.float32)


def hauteur(x, sr=16000):
    """hauteur (Hz) par trames de 40 ms, autocorrélation 70-400 Hz, trames voisées seulement (comme voix_plage)"""
    n, pas, f0 = int(0.04 * sr), int(0.01 * sr), []
    lo, hi = int(sr / 400), int(sr / 70)
    for i in range(0, len(x) - n, pas):
        t = x[i:i + n] - x[i:i + n].mean()
        if np.sqrt((t ** 2).mean()) < 0.02:
            continue
        ac = np.correlate(t, t, "full")[n - 1:]
        k = lo + int(np.argmax(ac[lo:hi]))
        if ac[k] > 0.3 * ac[0]:
            f0.append(sr / k)
    return np.array(f0)


def mesures(x16):
    f0 = hauteur(x16)
    st = 12 * np.log2(f0 / 100.0) if f0.size else np.array([np.nan])
    trames = x16[: len(x16) // 320 * 320].reshape(-1, 320)
    db = 20 * np.log10(np.sqrt((trames ** 2).mean(axis=1)) + 1e-9)
    voix = db[db > db.max() - 30]
    return {"f0_st": float(np.median(st)), "etendue_st": float(np.percentile(st, 90) - np.percentile(st, 10)),
            "energie_db": float(voix.mean()), "duree_s": len(x16) / 16000}


def moyenne(ms):
    return {k: float(np.nanmean([m[k] for m in ms])) for k in ms[0]}


def ressemblance(a, b):
    ea, eb = EV.embedding(a, min_s=1.0), EV.embedding(b, min_s=1.0)
    return float(ea @ eb) if ea is not None and eb is not None else float("nan")


def emotion_portee(d_style, d_chatterbox):
    nets = [k for k, s in NET.items() if abs(d_chatterbox[k]) >= s]
    memes = [k for k in nets if np.sign(d_style[k]) == np.sign(d_chatterbox[k])]
    contraires = [k for k in nets if np.sign(d_style[k]) == -np.sign(d_chatterbox[k])]
    return {"nets": nets, "memes": memes, "contraires": contraires, "tenu": len(memes) >= min(2, len(nets)) and not contraires}


def main(modele, dossier):
    from supertonic import TTS
    from supertonic.core import Style
    dossier = Path(dossier)
    sortie = dossier / "ecoute-verification"
    sortie.mkdir(exist_ok=True)
    tts = TTS(model_dir=modele, auto_download=False, intra_op_num_threads=2)
    sr = tts.sample_rate
    m1 = S.lire(Path(modele) / "voice_styles" / "M1.json")
    neutre = S.lire(dossier / "neutre.json")

    def dire(style, nom, graine):
        st = Style(np.asarray(style["ttl"], np.float32)[None], np.asarray(style["dp"], np.float32)[None])
        audios = []
        for i, p in enumerate(PHRASES):
            np.random.seed(graine + i)
            w, _ = tts.synthesize(p, voice_style=st, lang="fr", total_steps=ETAPES, speed=VITESSE)
            w = np.asarray(w, dtype=np.float32).squeeze()
            sf.write(sortie / f"{nom}-{i}.wav", w, sr)
            audios.append(reechantillonner(w, sr))
        return audios

    base = dire(m1, "M1", 100)
    autre = dire(m1, "M1-autre-bruit", 200)
    b = float(np.nanmean([ressemblance(x, y) for x, y in zip(base, autre)]))
    m_base = moyenne([mesures(x) for x in base])

    refs = REFS

    def mesures_ref(nom):
        x, r = sf.read(refs / f"{nom}.wav", dtype="float32")
        return mesures(reechantillonner(x, r))
    c_neutre = mesures_ref("neutre")

    resultats = {"b": b, "M1": m_base, "familles": {}}
    for f in sorted(dossier.glob("*.json")):
        nom = f.stem
        if nom in ("neutre", "verification") or not (refs / f"{nom}.wav").exists():
            continue
        emo = S.lire(f)
        c = mesures_ref(nom)
        d_c = {k: c[k] - c_neutre[k] for k in NET}
        par_force = {}
        for force in FORCES:
            st = S.appliquer(m1, emo, neutre, force)
            audios = dire(st, f"{nom}-{force}", 100)
            m = moyenne([mesures(x) for x in audios])
            d_s = {k: m[k] - m_base[k] for k in NET}
            par_force[force] = {"ressemblance": float(np.nanmean([ressemblance(x, y) for x, y in zip(base, audios)])),
                                "mesures": m, "ecart": d_s, "emotion": emotion_portee(d_s, d_c)}
            S.ecrire(st, dossier / f"M1-{nom}-{force}.json", source=f"M1 + {force} × ({nom} − neutre)")
            print(nom, force, json.dumps(par_force[force], ensure_ascii=False), flush=True)
        resultats["familles"][nom] = {"chatterbox": d_c, "forces": par_force}

    # 2. la diction : Whisper dans le venv de jarvis
    lu = subprocess.run([str(JARVIS_PY), str(ICI / "diction.py"), str(sortie)], capture_output=True, text=True, check=True)
    cers = json.loads(lu.stdout.strip().splitlines()[-1])
    def cer_de(prefixe):
        v = [c for n, c in cers.items() if n.rsplit("-", 1)[0] == prefixe]
        return (float(np.mean(v)), float(max(v))) if v else (float("nan"), float("nan"))
    cer_m1 = cer_de("M1")[0]
    resultats["cer_M1"] = cer_m1
    for nom, r in resultats["familles"].items():
        retenue = None
        for force, x in r["forces"].items():
            moy, pire = cer_de(f"{nom}-{force}")
            x["cer"] = {"moyen": moy, "pire": pire}
            x["voix_tenue"] = x["ressemblance"] >= b - 0.10
            x["diction_tenue"] = moy <= cer_m1 + 0.03 and pire <= 0.15
            if x["voix_tenue"] and x["diction_tenue"]:
                retenue = force
        r["force_retenue"] = retenue
    (dossier / "verification.json").write_text(json.dumps(resultats, ensure_ascii=False, indent=1))
    print(json.dumps({n: {"force": r["force_retenue"], "emotion": r["forces"][r["force_retenue"]]["emotion"]["tenu"] if r["force_retenue"] else None}
                      for n, r in resultats["familles"].items()}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
