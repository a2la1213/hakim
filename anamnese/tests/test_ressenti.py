"""Le ressenti en réserve (choix d'Ahmed, 2026-10-20) : quand le démon le recalcule, et avec quoi."""
import json
import time
import types

import daemon


class Mem:
    def __init__(self, humeur):
        self.humeur = humeur

    def kv_get(self, cle):
        return json.dumps({"humeur": self.humeur}) if self.humeur else None


def _journal(tmp_path, maintenant):
    j = tmp_path / "journal.jsonl"
    lignes = [{"ts": (maintenant - 90000) * 1000, "qui": "ahmed", "texte": "vieux message d'avant-hier"},
              {"ts": (maintenant - 600) * 1000, "qui": "ahmed", "texte": "toujours rien frero ?"},
              {"ts": (maintenant - 590) * 1000, "qui": "jarvis", "texte": "pas encore"},
              {"ts": (maintenant - 300) * 1000, "qui": "ahmed", "texte": "incroyable, bon signe"}]
    j.write_text("\n".join(json.dumps(l, ensure_ascii=False) for l in lignes) + "\n")
    return j


def test_ressenti_recalcule_seulement_si_neuf(tmp_path):
    now = time.time()
    j, sortie, appels = _journal(tmp_path, now), tmp_path / "ressenti.json", []

    def lancer(q):
        appels.append(q)
        sortie.write_text(json.dumps({"ts": now, "humeur": q["humeur"], "dernier_ts": q["dernier_ts"], "mots": ["grise", "pesante"]}))
        return types.SimpleNamespace(returncode=0, stdout='{"mots": ["grise"]}', stderr="")

    assert daemon._ressenti_pass(Mem(None), now, lancer, j, sortie) is False          # pas d'humeur : rien
    assert daemon._ressenti_pass(Mem("morosité"), now, lancer, j, sortie) is True
    q = appels[0]
    assert q["humeur"] == "morosité" and "toujours rien frero" in q["contexte"] and "incroyable" in q["contexte"]
    assert "avant-hier" not in q["contexte"]                                            # plus de 24 h : écarté
    assert daemon._ressenti_pass(Mem("morosité"), now + 3600, lancer, j, sortie) is False   # rien de neuf
    assert daemon._ressenti_pass(Mem("tension"), now + 60, lancer, j, sortie) is False      # trop tôt (20 min)
    assert daemon._ressenti_pass(Mem("tension"), now + 1300, lancer, j, sortie) is True     # humeur changée
    assert len(appels) == 2


def test_sans_message_recent_pas_de_ressenti(tmp_path):
    j = tmp_path / "journal.jsonl"
    j.write_text(json.dumps({"ts": 1000, "qui": "ahmed", "texte": "très vieux"}) + "\n")
    assert daemon._ressenti_pass(Mem("calme"), time.time(), lambda q: None, j, tmp_path / "r.json") is False
