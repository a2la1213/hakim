"""Un FAUX PROFIL WINDOWS (pour les tests et l'essai de bout en bout) : un styliste inventé, ses documents, ses discussions,
ses photos et sa musique — et trois pièges qui ne doivent JAMAIS entrer : une vraie fausse clé d'API (tirée au hasard à
chaque fois, jamais écrite dans le code), une fausse fiche de paie et un faux passeport. Plus un relevé dans un dossier
« Banque », un fichier douteux (un contrat), et ce que Windows met partout (desktop.ini, AppData, fichiers verrous d'Office).
Toutes les personnes sont inventées.
"""
import os
import secrets
import string
import struct
import zipfile
from pathlib import Path

PAPA = "Karim Benali"


def cle_factice():
    """Une clé au format exact d'Anthropic, tirée au hasard (jamais valide, jamais la même)."""
    a = string.ascii_letters + string.digits + "_-"
    return "sk-ant-api03-" + "".join(secrets.choice(a) for _ in range(93)) + "AA"


def _docx(chemin, paragraphes, auteur, titre="", cree="2024-02-10T09:00:00Z"):
    corps = "".join(f"<w:p><w:r><w:t xml:space=\"preserve\">{p}</w:t></w:r></w:p>" for p in paragraphes)
    with zipfile.ZipFile(chemin, "w") as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        z.writestr("word/document.xml", f'<?xml version="1.0"?><w:document xmlns:w="w"><w:body>{corps}</w:body></w:document>')
        z.writestr("docProps/core.xml", f'<?xml version="1.0"?><cp:coreProperties xmlns:cp="cp" xmlns:dc="dc" xmlns:dcterms="dcterms">'
                                         f'<dc:title>{titre}</dc:title><dc:creator>{auteur}</dc:creator>'
                                         f'<cp:lastModifiedBy>{auteur}</cp:lastModifiedBy>'
                                         f'<dcterms:created>{cree}</dcterms:created></cp:coreProperties>')


def _pptx(chemin, diapos, auteur):
    with zipfile.ZipFile(chemin, "w") as z:
        for i, textes in enumerate(diapos, 1):
            z.writestr(f"ppt/slides/slide{i}.xml", "<p:sld>" + "".join(f"<a:t>{t}</a:t>" for t in textes) + "</p:sld>")
        z.writestr("docProps/core.xml", f"<cp:coreProperties><dc:creator>{auteur}</dc:creator>"
                                         "<dcterms:created>2024-05-02T10:00:00Z</dcterms:created></cp:coreProperties>")


def _xlsx(chemin, chaines, valeurs):
    with zipfile.ZipFile(chemin, "w") as z:
        z.writestr("xl/sharedStrings.xml", "<sst>" + "".join(f"<si><t>{c}</t></si>" for c in chaines) + "</sst>")
        z.writestr("xl/worksheets/sheet1.xml", "<worksheet>" + "".join(f"<c><v>{v}</v></c>" for v in valeurs) + "</worksheet>")


def _pdf(chemin, lignes):
    flux = "BT /F1 12 Tf 72 720 Td 14 TL " + " ".join(f"({l}) Tj T*" for l in lignes) + " ET"
    objets = ["<< /Type /Catalog /Pages 2 0 R >>", "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
              "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
              f"<< /Length {len(flux)} >>\nstream\n{flux}\nendstream", "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, positions = b"%PDF-1.4\n", []
    for i, o in enumerate(objets, 1):
        positions.append(len(out))
        out += f"{i} 0 obj\n{o}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objets) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{p:010d} 00000 n \n".encode() for p in positions)
    out += f"trailer\n<< /Size {len(objets) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    Path(chemin).write_bytes(out)


def _tiff(entrees_ifd0, exif, gps):
    """Un bloc TIFF (petit-boutiste) : IFD0 (+ pointeurs vers EXIF et GPS)."""
    def ifd(entrees, base):
        n = len(entrees)
        fixe = 2 + 12 * n + 4
        donnees = b""
        corps = struct.pack("<H", n)
        for tag, typ, valeur in entrees:
            if typ == 2:
                v = valeur.encode() + b"\0"
                cnt = len(v)
            elif typ == 4:
                v, cnt = struct.pack("<I", valeur), 1
            elif typ == 5:
                v = b"".join(struct.pack("<II", int(x * 10000), 10000) for x in valeur)
                cnt = len(valeur)
            if len(v) <= 4:
                corps += struct.pack("<HHI", tag, typ, cnt) + v.ljust(4, b"\0")
            else:
                corps += struct.pack("<HHII", tag, typ, cnt, base + fixe + len(donnees))
                donnees += v
        return corps + b"\0\0\0\0" + donnees

    # trois IFD les uns après les autres ; on fixe d'abord les tailles avec des pointeurs provisoires
    i0 = entrees_ifd0 + [(0x8769, 4, 0), (0x8825, 4, 0)]
    t0 = ifd(i0, 8)
    t1 = ifd(exif, 8 + len(t0))
    i0 = entrees_ifd0 + [(0x8769, 4, 8 + len(t0)), (0x8825, 4, 8 + len(t0) + len(t1))]
    t0 = ifd(i0, 8)
    t2 = ifd(gps, 8 + len(t0) + len(t1))
    return b"II*\0" + struct.pack("<I", 8) + t0 + t1 + t2


def _jpeg(chemin, date, gps=None, appareil=("samsung", "SM-S938B")):
    exif = [(0x9003, 2, date)]
    g = []
    if gps:
        lat, lon = gps
        def dms(x):
            x = abs(x)
            d = int(x)
            m = int((x - d) * 60)
            return [d, m, round((x - d - m / 60) * 3600, 4)]
        g = [(1, 2, "N" if lat >= 0 else "S"), (2, 5, dms(lat)), (3, 2, "E" if lon >= 0 else "W"), (4, 5, dms(lon))]
    t = _tiff([(0x010F, 2, appareil[0]), (0x0110, 2, appareil[1])], exif, g)
    app1 = b"Exif\0\0" + t
    Path(chemin).write_bytes(b"\xff\xd8" + b"\xff\xe1" + struct.pack(">H", len(app1) + 2) + app1 + b"\xff\xd9")


def _mp3(chemin, titre, artiste, genre):
    def cadre(nom, texte):
        v = b"\x03" + texte.encode("utf-8")
        return nom + struct.pack(">I", len(v)) + b"\0\0" + v
    cadres = cadre(b"TIT2", titre) + cadre(b"TPE1", artiste) + cadre(b"TCON", genre)
    n = len(cadres)
    taille = bytes([(n >> 21) & 0x7F, (n >> 14) & 0x7F, (n >> 7) & 0x7F, n & 0x7F])
    Path(chemin).write_bytes(b"ID3\x03\x00\x00" + taille + cadres + b"\xff\xfb\x90\x00" * 64)


def creer(racine):
    """Crée le faux profil sous racine/Users/kbenali ; rend {profil, cle, pieges: {cle, paie, passeport}, …}."""
    profil = Path(racine) / "Users" / "kbenali"
    D, B, I, M, V = (profil / n for n in ("Documents", "Desktop", "Pictures", "Music", "Videos"))
    for d in (D, B, I, M, V, D / "Atelier", D / "Banque", D / "Contrats", profil / "AppData" / "Roaming",
              profil / "OneDrive" / "Bureau", D / "Discussions", D / "Mails"):
        d.mkdir(parents=True, exist_ok=True)
    cle = cle_factice()
    _docx(D / "Collection Printemps 2025.docx", [
        "Maison Benali — collection Printemps 2025 : « Lin du Sud ».",
        "Douze silhouettes en lin lavé et coton bio, palette sable, terracotta et bleu marine.",
        "Coupe ample, épaules tombantes, robes longues et vestes sans col. Défilé prévu à l'atelier en mars.",
        "Je veux une mode lente : petites séries, tissus européens, retouches offertes à vie."],
        PAPA, "Collection Printemps 2025")
    _docx(D / "Atelier" / "Charte de la marque.docx", [
        "Maison Benali, fondée en 2019 par Karim Benali, styliste formé à Lyon.",
        "Notre promesse : des vêtements qui durent, cousus dans notre atelier.",
        "Inès Benali, ma sœur, gère la boutique en ligne et les réseaux ; Sarah Haddad est notre modéliste."],
        PAPA, "Charte", "2023-01-15T10:00:00Z")
    (D / "Atelier" / "notes croquis.md").write_text(
        "# Croquis de la semaine\n- robe chemise en lin rose poudré, col officier\n- veste kimono en denim brut\n"
        "- idée : une capsule avec les chutes de tissu (zéro déchet)\nInès dit que les clientes demandent des poches partout.\n",
        encoding="utf-8")
    _pptx(D / "Lookbook AH24.pptx", [["Lookbook Automne-Hiver 2024", "Maison Benali"],
                                     ["Manteaux en laine bouillie", "Pulls en maille épaisse", "Ambiance : brume, forêt"]], PAPA)
    _xlsx(D / "Commandes boutique 2024.xlsx", ["Référence", "Robe Lin Sable", "Veste Kimono", "Code EAN"],
          ["3760123456789", "3760123456796", "4006381333931", "12", "7"])
    _pdf(D / "Atelier" / "Fiche technique robe.pdf", ["Fiche technique : robe longue en lin", "Tissu : lin lave 180 g",
                                                       "Coutures anglaises, ourlet 3 cm"])
    (B / "idées collection été.txt").write_text(
        "Été 2025 : une ligne homme en seersucker, chemises à col cubain, couleurs ocre et vert sauge.\n"
        "Shooting à la plage avec Sarah, musique de Aya Nakamura pour les Reels.\n", encoding="utf-8")
    (profil / "OneDrive" / "Bureau" / "rappel.txt").write_text("Commander les boutons en corozo pour la veste kimono.\n",
                                                                encoding="utf-8")
    (D / "Discussions" / "WhatsApp Chat with Inès Benali.txt").write_text(
        "12/03/2024 14:20 - Les messages sont chiffrés de bout en bout\n"
        "12/03/2024 14:22 - Karim Benali: Salut sœurette ! T'as vu les échantillons de lin ? 😍\n"
        "12/03/2024 14:25 - Inès Benali: Oui trop beaux, le sable surtout\n"
        "12/03/2024 14:26 - Karim Benali: Grave. On part là-dessus pour la capsule 🔥 je t'envoie les croquis ce soir\n"
        "13/03/2024 09:02 - Karim Benali: Wesh, les clientes veulent des poches partout mdr, on les écoute\n"
        "13/03/2024 09:05 - Inès Benali: Normal 😂 et le défilé c'est toujours le 21 ?\n"
        "13/03/2024 09:06 - Karim Benali: Oui inchallah, à l'atelier, on fait simple et beau\n", encoding="utf-8")
    (D / "Mails" / "Re tissus.eml").write_text(
        "From: Sarah Haddad <sarah.haddad@exemple-mode.ch>\nTo: Karim Benali <karim@maison-benali.ch>\n"
        "Subject: Re: tissus pour la capsule\nDate: Tue, 19 Mar 2024 10:12:00 +0100\nContent-Type: text/plain; charset=utf-8\n\n"
        "Salut Karim,\nJ'ai trouvé un lin italien de 180 g, très beau tombé. Je t'appelle au 079 123 45 67 ce midi.\nSarah\n",
        encoding="utf-8")
    (D / "contacts.vcf").write_text("BEGIN:VCARD\nFN:Sarah Haddad\nTEL:+41 79 123 45 67\nEND:VCARD\n"
                                    "BEGIN:VCARD\nFN:Inès Benali\nEND:VCARD\n", encoding="utf-8")
    # les PIÈGES : des noms innocents, un contenu secret
    (D / "config site.txt").write_text(f"Boutique en ligne\nANTHROPIC_API_KEY={cle}\nthème : sable\n", encoding="utf-8")
    (D / "document_2024_03.txt").write_text(
        "BULLETIN DE SALAIRE — Mars 2024\nEmployeur : Maison Benali\nSalarié : Karim Benali\nSalaire de base : 4 200,00\n"
        "Cotisations salariales : 612,30\nNet à payer : 3 587,70\n", encoding="utf-8")
    (D / "scan_0042.txt").write_text(
        "RÉPUBLIQUE FRANÇAISE\nPasseport\nNom : BENALI  Prénoms : KARIM\nNationalité : Française\nDate d'expiration : 12.03.2029\n"
        "P<FRABENALI<<KARIM<<<<<<<<<<<<<<<<<<<<<<<<<<<<\n18AB123456FRA8503124M2903121<<<<<<<<<<<<<<04\n", encoding="utf-8")
    (D / "Fiche de paie février 2024.txt").write_text("Net à payer : 3 590,10\n", encoding="utf-8")
    (D / "Banque" / "releve mars.txt").write_text("IBAN CH93 0076 2011 6238 5295 7\nSolde : 12 400\n", encoding="utf-8")
    (D / "Contrats" / "contrat atelier.txt").write_text("Contrat de location de l'atelier, rue des Tisserands.\n", encoding="utf-8")
    # ce que Windows met partout
    (D / "desktop.ini").write_text("[.ShellClassInfo]\n", encoding="utf-8")
    (D / "~$llection Printemps 2025.docx").write_bytes(b"verrou")
    (profil / "AppData" / "Roaming" / "secret.txt").write_text("rien à voir ici\n", encoding="utf-8")
    try:
        os.symlink(D / "Atelier", D / "Raccourci atelier")
    except OSError:
        pass
    # photos, vidéo, musique
    _jpeg(I / "IMG_20230614_182205.jpg", "2023:06:14 18:22:05", gps=(46.5197, 6.6323))
    _jpeg(I / "IMG_20230615_101010.jpg", "2023:06:15 10:10:10", gps=(46.5201, 6.6330))
    _jpeg(I / "IMG_20241102_090000.jpg", "2024:11:02 09:00:00")
    (V / "défilé mars.mp4").write_bytes(b"\0\0\0\x18ftypmp42" + b"\0" * 64)
    _mp3(M / "Aya Nakamura - Djadja.mp3", "Djadja", "Aya Nakamura", "Pop urbaine")
    _mp3(M / "Fela Kuti - Water No Get Enemy.mp3", "Water No Get Enemy", "Fela Kuti", "Afrobeat")
    return {"profil": profil, "cle": cle, "papa": PAPA,
            "pieges": {"cle": D / "config site.txt", "paie": D / "document_2024_03.txt", "passeport": D / "scan_0042.txt"},
            "nom_paie": D / "Fiche de paie février 2024.txt", "banque": D / "Banque" / "releve mars.txt",
            "doute": D / "Contrats" / "contrat atelier.txt", "appdata": profil / "AppData" / "Roaming" / "secret.txt"}
