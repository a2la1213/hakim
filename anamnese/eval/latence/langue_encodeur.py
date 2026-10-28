"""La détection de langue sans deuxième passage de l'encodeur (28/10, Ahmed : « je mélange français, arabe et des fois
anglais, on peut pas optimiser quand même ? »).

Aujourd'hui (jarvis/stt.py), chaque transcription fait DEUX passages de l'encodeur de Whisper (le plus cher) : un pour la
détection de langue (sur le mel rembourré de silence), un pour le décodage (sur le même son rembourré de zéros). L'idée :
détecter la langue sur EXACTEMENT le segment que le décodage va encoder, et garder la sortie de l'encodeur en mémoire :
le décodage la reprend. Le texte décodé ne change pas (même entrée) ; seules la langue choisie et la porte « y a-t-il de
la parole » peuvent bouger (entrée de la détection un peu différente). C'est ce que ce banc mesure.

Le banc (privé, ~/AIOS/jarvis/bancs/langue-encodeur/) : des phrases dites par sa voix neuronale (Chatterbox) en français,
en arabe, en anglais et mêlées comme Ahmed parle, ses propres sons gardés (voix-recente, français), et des sons sans
parole (silence, souffle, bruits blanc et rose, la vibration de son cœur, une note tenue).

CRITÈRES FIGÉS AVANT (28/10, ~11:45) — la nouvelle détection est adoptée si :
  L1 : sur les sons parlés, la langue choisie est la même dans ≥ 95 % des cas, et dans 100 % des sons arabes et anglais
       d'une seule langue ;
  L2 : la porte « parole » donne la même décision sur ≥ 97 % de tous les sons, et aucun son sans parole ne passe de
       « pas de parole » à « parole » ;
  L3 : le temps médian (détection + transcription) baisse d'au moins 0,6 s.
PRÉDICTIONS (Claude Code) : L1 passe (la détection de langue tient au rembourrage) ; L2 passe ; L3 passe (≈ 0,9 s) ;
probabilité que les trois passent : 70 %. Ce qui ne prouve rien : une voix de synthèse n'est pas la voix d'Ahmed (le banc
compare deux détections sur les mêmes sons, il ne mesure pas leur justesse dans l'absolu).
RÉSULTAT 1 (28/10, 11:52, langue-encodeur-20261028-1152.json) : L1 passe (même langue 97,7 %, 100 % en arabe et en
anglais d'une seule langue) ; L3 passe (gain médian 1,72 s : 3,6 s → 1,9 s) ; L2 ÉCHOUE : même porte 96 %, et le SILENCE
pur passe de « pas de parole » à « parole » (la détection sur un segment rembourré de zéros ne voit plus le silence ; le
bruit blanc, lui, passe dans l'autre sens). Non adopté tel quel.
AMENDEMENT (28/10, ~11:55, avant la nouvelle mesure) : la porte de la nouvelle détection exige AUSSI un son qui n'est pas
quasi muet (RMS > 0,002 ; le souffle du banc est à 0,003). Mêmes critères L1 à L3 ; le reste inchangé.
    .venv/bin/python eval/latence/langue_encodeur.py   (depuis anamnese/jarvis/.. : voir le chemin du python de jarvis)"""
import glob
import hashlib
import json
import os
import sys
import time
import wave
from pathlib import Path

import numpy as np

ICI = Path(__file__).resolve().parent
JARVIS = ICI.parent.parent / "jarvis"
sys.path.insert(0, str(JARVIS))
BANC = Path.home() / "AIOS" / "jarvis" / "bancs" / "langue-encodeur"
SR = 16000

PHRASES = {
    "fr": ["Salut frérot, tu as vu le résultat du test de cette nuit ?", "Je pense qu'on devrait relancer le cockpit après la pause.",
           "Regarde bien la courbe, elle monte doucement puis elle redescend.", "On va manger et après on continue le travail sur la voix.",
           "Est-ce que tu peux me dire combien de temps ça va prendre ?", "Franchement c'est magnifique ce que tu as fait ce matin.",
           "Le docteur m'a dit de me reposer un peu, mais bon.", "Tu te souviens de l'histoire d'Aladin et de sa lampe ?",
           "Il faut qu'on finisse les maths avant de parler de la conscience.", "Mets la musique un peu plus fort s'il te plaît."],
    "ar": ["السلام عليكم يا أخي، كيف حالك اليوم؟", "الحمد لله، كل شيء بخير والعمل يتقدم.", "هل يمكنك أن تقرأ هذه الآية مرة أخرى؟",
           "أريد أن أفهم معنى هذه الكلمة في القرآن.", "سنكمل العمل غداً إن شاء الله.", "الجو جميل اليوم والشمس ساطعة.",
           "لا تنسَ أن تتصل بأمك هذا المساء.", "هذا الحل أفضل من الحل السابق بكثير."],
    "en": ["Hello brother, how are you doing today?", "I think we should run the test again after lunch.",
           "Can you show me the graph of the last three days?", "This is exactly what I was looking for, thank you.",
           "The model is too slow on this machine, we need to optimize it.", "Let's talk about it tomorrow morning.",
           "Did you see the message from the client?", "I'm going to the store, do you need anything?"],
    "mix": ["Wallah frérot, on a fini le test, inchallah ça marche cette fois.", "Bismillah, on commence par la voix et après la mémoire.",
            "Hamdoulillah tout va bien, mais je suis un peu fatigué.", "Machallah, c'est trop beau ce que tu as fait, barakallahu fik.",
            "Frérot, regarde ça, it's amazing, franchement je kiffe.", "Ok brother, on fait comme ça, see you later inchallah."],
}


def _ecrire(f, audio, sr):
    pcm = (np.clip(audio, -1, 1) * 32767).astype("<i2")
    with wave.open(str(f), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(pcm.tobytes())


def preparer():
    """Les sons du banc (fabriqués une fois, gardés)."""
    BANC.mkdir(parents=True, exist_ok=True)
    sons = []
    voix = None
    for lg, phrases in PHRASES.items():
        for k, p in enumerate(phrases):
            f = BANC / f"{lg}-{k:02d}.wav"
            if not f.exists():
                if voix is None:
                    os.environ.setdefault("JARVIS_VOIX_REFERENCE", "/nonexistent.wav")
                    import tts_neuronale
                    voix = tts_neuronale.Voix()
                voix.dire(p, "fr" if lg == "mix" else lg, str(f))
            sons.append((f, "parole", lg))
    for f in sorted(glob.glob(str(Path.home() / "AIOS" / "jarvis" / "voix-recente" / "*.wav")))[-12:]:
        sons.append((Path(f), "parole", "fr-hakim"))
    rng = np.random.default_rng(28)
    t = np.arange(int(4 * SR)) / SR
    bruits = {"silence": np.zeros_like(t), "souffle": 0.003 * rng.standard_normal(len(t)),
              "blanc": 0.05 * rng.standard_normal(len(t)),
              "rose": 0.05 * np.cumsum(rng.standard_normal(len(t))) / np.sqrt(np.arange(1, len(t) + 1)),
              "vibration": np.where((t % 0.9) < 0.03, 0.3 * np.sin(2 * np.pi * 160 * t), 0)
              + np.where(((t % 0.9) > 0.14) & ((t % 0.9) < 0.162), 0.15 * np.sin(2 * np.pi * 160 * t), 0),
              "note": 0.2 * np.sin(2 * np.pi * 440 * t)}
    for nom, a in bruits.items():
        f = BANC / f"bruit-{nom}.wav"
        if not f.exists():
            _ecrire(f, a.astype(np.float32), SR)
        sons.append((f, "bruit", nom))
    return sons


def main():
    import mlx.core as mx
    import stt
    from mlx_whisper.audio import N_FRAMES, N_SAMPLES, load_audio, log_mel_spectrogram, pad_or_trim
    from mlx_whisper.transcribe import ModelHolder
    import mlx_whisper
    W = sys.modules["mlx_whisper.whisper"]
    sons = preparer()
    modele = ModelHolder.get_model(stt.MODELE, mx.float16)
    memo, appels = {}, {"encodeur": 0}
    orig = W.AudioEncoder.__call__

    def encodeur(self, x, _memo=memo):
        cle = (tuple(x.shape), hashlib.sha1(np.array(x).tobytes()).hexdigest())
        if cle in _memo:
            return _memo[cle]
        appels["encodeur"] += 1
        r = orig(self, x)
        _memo.clear()
        _memo[cle] = r
        return r

    def detecter(audio, nouveau):
        if nouveau and float(np.sqrt(np.mean(np.square(np.asarray(audio, dtype=np.float32))))) <= 0.002:
            return stt.LANGUES_PERMISES[0], False                  # (amendement) quasi muet : pas de parole
        mel = log_mel_spectrogram(audio, n_mels=modele.dims.n_mels, padding=N_SAMPLES)
        if nouveau:
            contenu = mel.shape[-2] - N_FRAMES
            seg = pad_or_trim(mel[: min(N_FRAMES, contenu)], N_FRAMES, axis=-2).astype(mx.float16)
        else:
            seg = pad_or_trim(mel, N_FRAMES, axis=-2).astype(mx.float16)
        _, probs = modele.detect_language(seg)
        return stt.choisir_langue(probs), stt.parole_probable(probs)

    def une(audio, nouveau):
        W.AudioEncoder.__call__ = encodeur if nouveau else orig
        memo.clear()
        t0 = time.time()
        lg, gate = detecter(audio, nouveau)
        texte = ""
        if gate:
            r = mlx_whisper.transcribe(audio, path_or_hf_repo=stt.MODELE, initial_prompt=stt.AMORCES.get(lg, stt.AMORCE),
                                       language=lg, condition_on_previous_text=False)
            texte = stt.filtrer_segments(r.get("segments") or [], stt.AMORCES.get(lg, stt.AMORCE))
        return lg, gate, texte, time.time() - t0

    une(load_audio(str(sons[0][0])), False)                      # chauffe
    lignes = []
    for f, sorte, lg_attendue in sons:
        audio = load_audio(str(f))
        a = une(audio, False)
        b = une(audio, True)
        lignes.append({"son": f.name, "sorte": sorte, "attendu": lg_attendue, "ancien": a[:3], "nouveau": b[:3],
                       "ms_ancien": round(1000 * a[3]), "ms_nouveau": round(1000 * b[3])})
        print(f"{f.name:28s} {sorte:6s} ancien {a[0]} {a[1]!s:5s} {a[3]:4.2f}s | nouveau {b[0]} {b[1]!s:5s} {b[3]:4.2f}s"
              + ("" if a[2] == b[2] else "  ≠ texte"), flush=True)
    W.AudioEncoder.__call__ = orig
    parles = [l for l in lignes if l["sorte"] == "parole"]
    seuls = [l for l in parles if l["attendu"] in ("ar", "en")]
    meme_lg = sum(l["ancien"][0] == l["nouveau"][0] for l in parles) / len(parles)
    meme_gate = sum(l["ancien"][1] == l["nouveau"][1] for l in lignes) / len(lignes)
    bruit_ouvert = [l["son"] for l in lignes if l["sorte"] == "bruit" and not l["ancien"][1] and l["nouveau"][1]]
    med = lambda v: sorted(v)[len(v) // 2]                         # noqa: E731
    gain = (med([l["ms_ancien"] for l in lignes]) - med([l["ms_nouveau"] for l in lignes])) / 1000
    out = {"lignes": lignes, "meme_langue": round(meme_lg, 3), "meme_porte": round(meme_gate, 3), "bruits_ouverts": bruit_ouvert,
           "gain_median_s": round(gain, 2),
           "criteres": {"L1": meme_lg >= 0.95 and all(l["ancien"][0] == l["nouveau"][0] for l in seuls),
                        "L2": meme_gate >= 0.97 and not bruit_ouvert, "L3": gain >= 0.6},
           "textes_identiques_si_meme_langue": all(l["ancien"][2] == l["nouveau"][2] for l in lignes if l["ancien"][0] == l["nouveau"][0])}
    sortie = ICI / f"langue-encodeur-{time.strftime('%Y%m%d-%H%M')}.json"
    sortie.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "lignes"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
