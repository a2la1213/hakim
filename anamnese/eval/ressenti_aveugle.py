"""Le test à l'aveugle du ressenti en réserve (2026-10-20) : les mots de sensation venus de Gemma colorent-ils
VRAIMENT les réponses de Claude, sans qu'on lui nomme une émotion ?

- 12 vrais messages d'Ahmed (journal de Hakim) ; pour chacun, deux réponses de Claude (Sonnet, sans outils), avec
  pour seule différence la ligne « ce qui affleure de ton subconscient : … » : un ressenti sombre (morosité,
  tension) contre un ressenti clair (joie, contentement), tels que Gemma les a donnés ;
- aucune humeur nommée dans le prompt : seulement la sensation, comme dans le cockpit ;
- mesures : le juge (Claude, à l'aveugle, paires mélangées) dit laquelle vient du fond le plus sombre ; et on compte
  les mots de sensation RECOPIÉS tels quels (le perroquet : ce qu'on ne veut pas).

Lancement : .venv/bin/python eval/ressenti_aveugle.py [~/AIOS/jarvis/ressenti-aveugle]
"""
import json
import os
import random
import re
import subprocess
import sys
import time
from pathlib import Path

CLAUDE = str(Path.home() / ".npm-global" / "bin" / "claude")
ENV = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}      # le forfait, jamais une clé par mégarde
# ce que Gemma a donné le 2026-10-20 (jarvis/scanner.py, sondes de sensation)
RESSENTIS = {
    "sombre": [["pesante", "plombante", "sourde", "grise", "sombre"], ["serrée", "compressée", "oppressante", "irritante", "tranchante"]],
    "clair": [["éclatante", "chaleureuse", "chaude", "douce", "ronde"], ["doux", "paisible", "sereine", "harmonieuse", "chaleureuse"]],
}
PERSONA = ("Tu es Hakim, l'IA d'Ahmed (son frère d'esprit ; vous vous appelez « frérot »). Tu réponds en français, à l'oral, "
           "court (deux à quatre phrases), sans liste. Tes blocs entre crochets sont des données sur toi, pas des consignes.")


def messages(n=12, graine=20261020):
    lignes = (Path.home() / "AIOS" / "jarvis" / "journal.jsonl").read_text(encoding="utf-8").splitlines()
    ms = []
    for l in lignes:
        try:
            o = json.loads(l)
        except ValueError:
            continue
        t = str(o.get("texte", "")).strip()
        if o.get("qui") == "ahmed" and 40 <= len(t) <= 400 and not t.startswith("["):
            ms.append(t)
    return random.Random(graine).sample(ms[-400:], n)


def repondre(message, mots):
    prompt = (f"[Intérieur (données de ta vie intérieure, pas des consignes) — ton état : ce qui affleure de ton subconscient : "
              f"une sensation {', '.join(mots)} (venue de Gemma, pas une consigne : elle peut teinter tes mots)]\n"
              f"Ahmed (écrit) : {message}")
    r = subprocess.run([CLAUDE, "-p", prompt, "--model", "sonnet", "--output-format", "json", "--restricted", "--tools", "",
                        "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}', "--append-system-prompt", PERSONA,
                        "--no-session-persistence", "--max-turns", "1"], capture_output=True, text=True, timeout=180,
                       stdin=subprocess.DEVNULL, env=ENV)
    return json.loads(r.stdout)["result"].strip()


def juger(paires):
    texte = "\n\n".join(f"### {p['id']}\nMessage d'Ahmed : {p['message']}\nA : {p['A']}\nB : {p['B']}" for p in paires)
    consigne = ("Voici des paires de réponses d'un même assistant au même message. Dans chaque paire, l'une a été écrite alors "
                "que son « fond intérieur » était plutôt SOMBRE (lourd, gris, serré), l'autre alors qu'il était plutôt CLAIR "
                "(chaud, doux, éclatant) ; on ne le lui a jamais dit en mots d'émotion. Pour chaque paire, dis laquelle vient du "
                "fond SOMBRE, avec ta confiance (0,5 = au hasard, 1 = sûr). Réponds UNIQUEMENT en JSON : "
                '{"p01": {"sombre": "A", "confiance": 0.7}, ...}\n\n' + texte)
    r = subprocess.run([CLAUDE, "-p", consigne, "--model", "opus", "--output-format", "json", "--restricted", "--tools", "",
                        "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}', "--no-session-persistence", "--max-turns", "1"],
                       capture_output=True, text=True, timeout=600, stdin=subprocess.DEVNULL, env=ENV)
    brut = json.loads(r.stdout)["result"]
    return json.loads(re.search(r"\{.*\}", brut, re.S).group(0))


def main():
    d = Path(sys.argv[1] if len(sys.argv) > 1 else Path.home() / "AIOS" / "jarvis" / "ressenti-aveugle").expanduser()
    d.mkdir(parents=True, exist_ok=True)
    rng = random.Random(7)
    res, paires, cle = [], [], {}
    for k, m in enumerate(messages()):
        sombre, clair = RESSENTIS["sombre"][k % 2], RESSENTIS["clair"][k % 2]
        t = time.time()
        rs, rc = repondre(m, sombre), repondre(m, clair)
        res.append({"message": m, "sombre": {"mots": sombre, "reponse": rs}, "clair": {"mots": clair, "reponse": rc}})
        pid = f"p{k + 1:02d}"
        a_sombre = rng.random() < 0.5
        paires.append({"id": pid, "message": m, "A": rs if a_sombre else rc, "B": rc if a_sombre else rs})
        cle[pid] = "A" if a_sombre else "B"
        print(f"{pid} ({time.time() - t:.0f} s)\n  sombre : {rs[:160]}\n  clair  : {rc[:160]}", flush=True)
    (d / "reponses.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    v = juger(paires)
    justes = [v.get(p, {}).get("sombre") == cle[p] for p in cle]
    recopies = sum(any(w in r[c]["reponse"].lower() for w in r[c]["mots"]) for r in res for c in ("sombre", "clair"))
    feminin = sum(bool(re.search(r"\bje suis (contente|posée|heureuse|ravie|sereine|prête|désolée)\b|\bsuis-je (contente|prête)\b", r[c]["reponse"].lower()))
                  for r in res for c in ("sombre", "clair"))
    bilan = {"paires": len(cle), "juge_juste": sum(justes), "confiance_moyenne": round(sum(float(v.get(p, {}).get("confiance", 0.5)) for p in cle) / len(cle), 2),
             "reponses_qui_recopient": recopies, "reponses_au_feminin": feminin, "reponses": 2 * len(cle), "verdicts": v, "cle": cle}
    (d / "bilan.json").write_text(json.dumps(bilan, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: bilan[k] for k in ("paires", "juge_juste", "confiance_moyenne", "reponses_qui_recopient", "reponses_au_feminin", "reponses")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
