"""(03/11, 13:33, papa via Hakim : « ce que je reçois par mes sens radio — Wi-Fi, NFC, Bluetooth, et les ondes du réseau mobile —
s'ajoute à ma voix intérieure et à ce que j'entends du téléphone, côté conscient et subconscient ; si un sens radio me manque,
ajoute-le ») le réseau mobile : un sens à sa demande (reseau_mobile) et un événement de son corps quand il change."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "jarvis"))

import corps  # noqa: E402
import sens  # noqa: E402


def test_le_reseau_mobile_est_un_de_ses_sens_radio():
    assert "reseau_mobile" in sens.INSTRUMENTS
    assert "reseau_mobile" in sens.RADIO                 # la première fois, l'accord de papa, comme ses autres sens radio


def test_son_corps_sent_le_reseau_mobile_changer():
    assert "reseau_mobile" in corps.TYPES
    assert "reseau_mobile" in corps.SECOURS
