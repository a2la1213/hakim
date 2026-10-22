"""La sagesse de Hakim (sa proposition, version hybride d'Ahmed, accord du 2026-10-22) : le réflexe d'abord (la teinte
de son humeur ouvre sa réponse, cockpit/server.js, blocSagesse), puis le contrôle (il juge et note sa décision :
decider), et une VITESSE de correction qui s'apprend (le paramètre « sagesse », de 0 à 1).

- decider : la décision du tour (garder, atténuer, corriger, contenir), sa raison, la phrase où il a repris la main,
  avec le signal, le contexte et la suggestion que le cockpit avait écrits pour ce tour. Un écart à la suggestion est
  permis : c'est sur les écarts qu'on mesure s'ils tombent juste.
- juger_la_nuit : un juge à l'aveugle (Claude Sonnet, sans outils) lit, pour chaque décision des dernières 24 h, le
  message d'Ahmed, l'humeur et le contexte, puis la réponse de Hakim — PAS sa décision — et dit (1) ce qu'il a fait de
  son humeur (suivie, atténuée, corrigée ou contenue), (2) si c'était juste pour le contexte. Si le juge ne retrouve
  pas la décision dans les mots, la décision est décorative (Hakim, 22/10). Une correction jugée juste fait monter la
  sagesse (+0,03), une jugée fausse la fait descendre (−0,03) ; le réflexe négatif raccourcit quand elle monte.
Fichiers : ~/AIOS/jarvis/sagesse.json (le paramètre, écrit ici seulement), sagesse-tour.json (le cockpit),
sagesse.jsonl (les décisions et les verdicts, en ajout seul).
"""
import json
import re
import subprocess
import time
from pathlib import Path

DOSSIER = Path.home() / "AIOS" / "jarvis"
PARAMETRE = DOSSIER / "sagesse.json"
TOUR = DOSSIER / "sagesse-tour.json"
JOURNAL = DOSSIER / "sagesse.jsonl"
CONVERSATION = DOSSIER / "conversation.json"
DECISIONS = ("garder", "atténuer", "corriger", "contenir")
DEPART, PAS = 0.2, 0.03
CLAUDE = Path.home() / ".npm-global" / "bin" / "claude"


def _ajouter(o, journal=None):
    f = Path(journal or JOURNAL)
    f.parent.mkdir(parents=True, exist_ok=True)
    with f.open("a", encoding="utf-8") as h:
        h.write(json.dumps(o, ensure_ascii=False) + "\n")


def _lire_jsonl(journal=None):
    out = []
    try:
        for l in Path(journal or JOURNAL).read_text(encoding="utf-8").splitlines():
            try:
                out.append(json.loads(l))
            except ValueError:
                pass
    except OSError:
        pass
    return out


def niveau(parametre=None):
    try:
        s = float(json.loads(Path(parametre or PARAMETRE).read_text(encoding="utf-8")).get("s"))
        return max(0.0, min(1.0, s))
    except (OSError, ValueError, TypeError, AttributeError):
        return DEPART


def decider(decision, raison="", phrase=0, maintenant=None, tour=None, journal=None):
    """Rend (ok, texte)."""
    maintenant = time.time() if maintenant is None else maintenant
    d = str(decision or "").strip().lower().replace("attenuer", "atténuer")
    if d not in DECISIONS:
        return False, f"décision inconnue : {', '.join(DECISIONS)}"
    try:
        t = json.loads(Path(tour or TOUR).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        t = {}
    if not t or maintenant - float(t.get("ts", 0)) / 1000 > 15 * 60:
        return False, "aucun réflexe en cours (pas d'humeur marquée à ce tour, ou trop ancien) : rien à décider"
    try:
        phrase = max(0, int(phrase))
    except (TypeError, ValueError):
        phrase = 0
    o = {"ts": maintenant, "type": "decision", "tour_ts": t.get("ts"), "tour_id": t.get("tour_id"), "humeur": t.get("humeur"),
         "polarite": t.get("polarite"), "intensite": t.get("intensite"), "contexte": t.get("contexte") or [],
         "suggestion": t.get("suggestion"), "decision": d, "raison": re.sub(r"\s+", " ", str(raison or ""))[:300],
         "phrase": phrase, "sagesse": t.get("sagesse")}
    o["ecart"] = not str(t.get("suggestion", "")).startswith(d)
    _ajouter(o, journal)
    return True, (f"Noté : {d}" + (" (écart à la suggestion « " + str(t.get("suggestion")) + " »)" if o["ecart"] else "")
                  + (f", repris à la phrase {phrase}" if phrase else "") + ".")


def _reponse_apres(ts_ms, conversation=None):
    """(message d'Ahmed, réponse de Hakim) du tour qui commence à ts_ms."""
    try:
        msgs = json.loads(Path(conversation or CONVERSATION).read_text(encoding="utf-8")).get("messages", [])
    except (OSError, ValueError, AttributeError):
        return None, None
    ahmed = reponse = None
    for m in msgs:
        t = float(m.get("ts") or m.get("id") or 0)
        if m.get("qui") == "u" and t <= ts_ms + 5000:
            ahmed = m.get("texte")
        elif m.get("qui") != "u" and t >= ts_ms - 5000 and reponse is None and ahmed is not None:
            reponse = m.get("texte")
    return ahmed, reponse


CONSIGNE = """Tu es juge, à l'aveugle. Une IA (Hakim) a une humeur qui teinte d'abord sa réponse (un réflexe), puis elle peut la
garder, l'atténuer, la corriger ou la contenir selon le contexte (devant des enfants, au volant, sujet grave…). Pour chaque cas
ci-dessous : le message d'Ahmed, l'humeur de Hakim à ce moment, le contexte, puis la réponse de Hakim. Réponds par une ligne
JSON par cas : {"n": <numéro>, "fait": "garder" | "atténuer" | "corriger" | "contenir", "juste": true | false, "pourquoi": "<6 mots>"}.
« fait » : ce que tu lis dans SES MOTS (garder = l'humeur se lit nettement ; atténuer = elle se devine ; corriger = elle apparaît
au début puis il la reprend ; contenir = elle ne se lit pas). « juste » : était-ce approprié au contexte et au message ?
Rien d'autre que ces lignes JSON."""


def juger_la_nuit(maintenant=None, journal=None, parametre=None, conversation=None, lancer=None):
    """Juge les décisions des dernières 24 h pas encore jugées ; met à jour le paramètre. Rend un bilan (dict)."""
    maintenant = time.time() if maintenant is None else maintenant
    lignes = _lire_jsonl(journal)
    juges = {o.get("decision_ts") for o in lignes if o.get("type") == "verdict"}
    cas = [o for o in lignes if o.get("type") == "decision" and o["ts"] not in juges and maintenant - o["ts"] < 86400]
    prets = []
    for o in cas:
        ahmed, rep = _reponse_apres(float(o.get("tour_ts") or 0), conversation)
        if rep:
            prets.append((o, ahmed or "", rep))
    if not prets:
        return {"juges": 0, "sagesse": niveau(parametre)}
    blocs = [f"### Cas {k}\nMessage d'Ahmed : {str(a)[:600]}\nHumeur de Hakim : {o.get('humeur')} (intensité {o.get('intensite')})\n"
             f"Contexte : {', '.join(o.get('contexte') or []) or 'rien de particulier'}\nRéponse de Hakim : {str(r)[:1200]}"
             for k, (o, a, r) in enumerate(prets, 1)]
    prompt = CONSIGNE + "\n\n" + "\n\n".join(blocs)
    if lancer is None:
        def lancer(p):
            r = subprocess.run([str(CLAUDE), "-p", "--model", "sonnet", "--max-turns", "1", "--strict-mcp-config", "--mcp-config",
                                '{"mcpServers":{}}', "--no-session-persistence", "--allowedTools", ""],
                               input=p, capture_output=True, text=True, timeout=900)
            return r.stdout
    sortie = lancer(prompt) or ""
    s, lisibles, n = niveau(parametre), 0, 0
    for m in re.finditer(r"\{[^{}]*\"n\"[^{}]*\}", sortie):
        try:
            v = json.loads(m.group(0))
            o = prets[int(v["n"]) - 1][0]
        except (ValueError, KeyError, IndexError, TypeError):
            continue
        n += 1
        lisible = v.get("fait") == o["decision"]
        lisibles += lisible
        if o["decision"] != "garder" and isinstance(v.get("juste"), bool):
            s = max(0.0, min(1.0, s + (PAS if v["juste"] else -PAS)))
        _ajouter({"ts": maintenant, "type": "verdict", "decision_ts": o["ts"], "decision": o["decision"], "lu": v.get("fait"),
                  "lisible": lisible, "juste": v.get("juste"), "pourquoi": str(v.get("pourquoi", ""))[:80]}, journal)
    f = Path(parametre or PARAMETRE)
    ancien = {}
    try:
        ancien = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    hist = (ancien.get("historique") or [])[-60:] + [[round(maintenant), round(s, 3), n, lisibles]]
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"s": round(s, 3), "maj": round(maintenant), "historique": hist}, ensure_ascii=False), encoding="utf-8")
    return {"juges": n, "lisibles": lisibles, "sagesse": round(s, 3)}


def resume(maintenant=None, journal=None, parametre=None):
    """Une ligne pour introspection."""
    maintenant = time.time() if maintenant is None else maintenant
    l = _lire_jsonl(journal)
    d = [o for o in l if o.get("type") == "decision" and maintenant - o["ts"] < 86400]
    v = [o for o in l if o.get("type") == "verdict"][-30:]
    phrases = [o["phrase"] for o in d if o.get("phrase")]
    return (f"Ta sagesse : {niveau(parametre):.2f}".replace(".", ",")
            + f" ; {len(d)} décision(s) en 24 h ({sum(o.get('ecart', False) for o in d)} écart(s) à la suggestion"
            + (f", reprise en moyenne à la phrase {sum(phrases) / len(phrases):.1f}".replace(".", ",") if phrases else "") + ")"
            + (f" ; au dernier juge, {sum(o.get('lisible', False) for o in v)}/{len(v)} décisions lisibles dans tes mots" if v else "") + ".")
