"""Le scan des dépendances de la semaine (validé par Ahmed le 2026-10-20) : il trouve, il signale, il ne met rien à jour."""
import json
import subprocess

import audit_dependances as A
import daemon


class _R:
    def __init__(self, sortie, code=0):
        self.stdout, self.stderr, self.returncode = sortie, "", code


def _lancer(vuln):
    def lancer(cmd, **kw):
        if cmd[1:3] == ["pip", "freeze"]:
            return _R("aiohttp==3.14.1\nnumpy==2.0.0\n-e file:///x\n")
        if "pip-audit" in cmd:
            deps = [{"name": "aiohttp", "version": "3.14.1",
                     "vulns": [{"id": "PYSEC-1", "fix_versions": ["3.14.4"]}] if vuln else []},
                    {"name": "numpy", "version": "2.0.0", "vulns": []}]
            return _R(json.dumps({"dependencies": deps}))
        if cmd[1:] == ["audit", "--json"]:
            return _R(json.dumps({"vulnerabilities": {}}))
        raise AssertionError(cmd)
    return lancer


def test_une_faille_est_signalee(tmp_path, monkeypatch):
    monkeypatch.setattr(A, "VENVS", {"anamnese": tmp_path / "py"})
    (tmp_path / "py").write_text("")
    monkeypatch.setattr(A, "COCKPIT", tmp_path)
    (tmp_path / "package-lock.json").write_text("{}")
    res = A.auditer(_lancer(True), sortie=tmp_path)
    assert res["failles"] == 1 and "aiohttp 3.14.1" in A.resume(res) and "3.14.4" in A.resume(res)
    assert json.loads((tmp_path / "audit-dependances.json").read_text())["failles"] == 1
    vus = []
    assert A.signaler(res, notifier=lambda t, m: vus.append(t), ecrire=lambda *a, **k: vus.append(a[0]))
    assert vus[0].startswith("Anamnèse — Dépendances : 1 faille") and vus[1] == "hakim"
    propre = A.auditer(_lancer(False), sortie=tmp_path)
    assert propre["failles"] == 0 and not A.signaler(propre, notifier=lambda *a: 1 / 0, ecrire=lambda *a, **k: 1 / 0)


def test_le_demon_le_lance_une_fois_par_semaine_la_nuit(tmp_path):
    class M:
        kv = {}
        def kv_get(self, k, d=None): return self.kv.get(k, d)
        def kv_set(self, k, v): self.kv[k] = v
    m, appels = M(), []
    fake = lambda: appels.append(1) or {"failles": 0, "erreurs": []}
    import time
    nuit = time.mktime((2026, 10, 21, 4, 30, 0, 0, 0, -1))
    daemon._audit_dependances_pass(m, now=nuit - 6 * 3600, auditer=fake, signaler=lambda r: None)   # 22 h 30 : non
    daemon._audit_dependances_pass(m, now=nuit, auditer=fake, signaler=lambda r: None)
    daemon._audit_dependances_pass(m, now=nuit + 3 * 24 * 3600, auditer=fake, signaler=lambda r: None)
    semaine_suivante = time.mktime((2026, 10, 28, 4, 45, 0, 0, 0, -1))           # (le changement d'heure du 25/10)
    daemon._audit_dependances_pass(m, now=semaine_suivante, auditer=fake, signaler=lambda r: None)
    assert len(appels) == 2
