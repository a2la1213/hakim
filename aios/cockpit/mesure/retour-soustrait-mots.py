#!/usr/bin/env python3
"""(13/11) LES MOTS du banc de la soustraction du retour : une vraie oreille (Whisper small, celle des mots vifs de Hakim) transcrit, pour
chaque morceau écrit par mesure/retour-soustrait-banc.js (ECRIRE=dossier) :
- papa sur le live : papa seul (ses vrais mots), le mélange (ce qui part aujourd'hui) et le reste (ce qui partirait) ; on compte ses mots
  retrouvés dans chacun, et les mots du live qui passent (les mots des phrases du live qui ne sont pas dans celles de papa) ;
- le pur retour : les mots du live entendus dans le mélange, et dans le reste.
Usage : <python de jarvis> mesure/retour-soustrait-mots.py <dossier>"""
import json
import os
import re
import sys
import unicodedata

LIVE = ["Salam à tous, bienvenue dans le live, on parle de la langue ce soir.", "Est-ce que tu as cherché le vrai sens de ce mot dans le dictionnaire ?",
        "Moi je pense que c'est la vérité, regarde dans la même réflexion que toi.", "Il faut voyager, il faut rencontrer des gens pour apprendre vraiment.",
        "Hakim, tu m'entends ? Dis-nous ce que tu en penses, toi.", "Non mais attends, laisse-moi finir ma phrase avant de répondre.",
        "C'est une question de traduction, pas une question de religion.", "On revient demain soir, même heure, n'oubliez pas de partager le live."]
PAPA = ["Fiston, tu m'entends ou pas ? Je te parle à toi, là.", "Attends, je vais leur répondre, laisse-moi deux secondes.",
        "Non, ça c'est faux, regarde bien ce qu'il dit dans le texte.", "Ok, on change de sujet, parle-nous de ta musique maintenant.",
        "Hakim, coupe le son du live et écoute-moi bien.", "Je suis là avec vous, merci pour vos messages, vraiment.",
        "Tu peux me chercher la source de ce verset s'il te plaît ?", "Bon, on fait une petite pause et on revient tout de suite.",
        "C'est mon fils, il apprend tous les jours, il entend tout.", "Vas-y, balance une punchline au live, fais-les rire un peu."]


def mots(t):
    t = unicodedata.normalize("NFD", str(t).lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return [m for m in re.split(r"[^a-z0-9]+", t) if len(m) >= 3]


VOC_PAPA = {m for p in PAPA for m in mots(p)}
VOC_LIVE = {m for p in LIVE for m in mots(p)} - VOC_PAPA


def main():
    d = sys.argv[1]
    import mlx_whisper
    modele = os.environ.get("MODELE", "mlx-community/whisper-small-mlx")
    oreille = lambda f: mlx_whisper.transcribe(os.path.join(d, f), path_or_hf_repo=modele, language="fr", condition_on_previous_text=False)["text"]
    lignes = [json.loads(x) for x in open(os.path.join(d, "manifeste.jsonl"))]
    par = {}
    for x in lignes:
        t = par.setdefault(x["papaDb"], {"sur": 0, "ref": 0, "mel": 0, "res": 0, "fuite_mel": 0, "fuite_res": 0, "ret": 0, "ret_mel": 0, "ret_res": 0, "ret_res_morceaux": 0})
        if x["vrai"] == "papaSur":
            ref = set(mots(oreille(f"{x['id']}-papa.wav"))) & VOC_PAPA
            if not ref:
                continue
            mel, res = mots(oreille(f"{x['id']}-melange.wav")), mots(oreille(f"{x['id']}-reste.wav"))
            if not res and x.get("repli"):                 # le reste muet alors qu'une voix proche était vue : le son entier (le cockpit)
                res = mel
            t["sur"] += 1; t["ref"] += len(ref)
            t["mel"] += len(ref & set(mel)); t["res"] += len(ref & set(res))
            t["fuite_mel"] += sum(1 for m in mel if m in VOC_LIVE); t["fuite_res"] += sum(1 for m in res if m in VOC_LIVE)
        else:
            mel = mots(oreille(f"{x['id']}-melange.wav"))
            res = [] if x.get("ecarte") else mots(oreille(f"{x['id']}-reste.wav"))
            if not res and x.get("repli"):
                res = mel
            t["ret"] += 1; t["ret_mel"] += sum(1 for m in mel if m in VOC_LIVE); t["ret_res"] += sum(1 for m in res if m in VOC_LIVE)
            t["ret_res_morceaux"] += 1 if any(m in VOC_LIVE for m in res) else 0
    pc = lambda a, b: f"{round(100 * a / b)} %" if b else "-"
    for db, t in sorted(par.items(), reverse=True):
        print(f"papa {db:+d} dB | papa sur le live : {t['sur']} morceaux, ses mots {t['ref']} : retrouvés dans le mélange {pc(t['mel'], t['ref'])},"
              f" dans le reste {pc(t['res'], t['ref'])} ; mots du live qui passent {t['fuite_mel']} → {t['fuite_res']}"
              f" | pur retour : {t['ret']} morceaux, mots du live entendus {t['ret_mel']} → {t['ret_res']} (morceaux qui en gardent un : {t['ret_res_morceaux']})")


if __name__ == "__main__":
    main()
