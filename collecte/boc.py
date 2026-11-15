"""Source de secours : le Bulletin Officiel de la Cote (BOC), publié en PDF.

On ouvre la page qui liste les BOC, on prend le lien PDF le plus récent,
puis on lit les lignes du PDF qui commencent par un symbole connu.
Le format du PDF pouvant évoluer, cette lecture est volontairement tolérante :
elle retient le premier nombre après le nom comme cours de clôture lorsque
la colonne n'est pas identifiable, et marque alors la donnée « à vérifier ».
"""
from __future__ import annotations

import io
import re
from urllib.parse import urljoin

from brvm import Cours, nombre

URL_LISTE_BOC = "https://www.brvm.org/fr/bulletins-officiels-de-la-cote"

LIGNE = re.compile(
    r"^(?P<code>[A-Z]{3,6})\s+(?P<nom>.+?)\s+(?P<nombres>(?:-?[\d\s \xa0]+(?:,\d+)?%?\s+){2,}-?[\d\s \xa0]+(?:,\d+)?%?)$"
)


def trouver_lien_boc(html: str, base: str = URL_LISTE_BOC) -> str | None:
    liens = re.findall(r'href="([^"]+\.pdf)"', html, flags=re.I)
    boc = [l for l in liens if "boc" in l.lower()] or liens
    return urljoin(base, boc[0]) if boc else None


def regrouper_milliers(texte: str) -> list[str]:
    """« 7 200 7 300 1,39% 1 061 » -> ['7200', '7300', '1,39%', '1061'].

    Un groupe d'exactement 3 chiffres qui suit un nombre entier est un groupe de milliers.
    """
    jetons = texte.replace("\u202f", " ").replace("\xa0", " ").split()
    out: list[str] = []
    for j in jetons:
        if out and re.fullmatch(r"\d{3}(,\d+)?%?", j) and re.fullmatch(r"-?\d{1,3}", out[-1]):
            out[-1] += j
        elif out and re.fullmatch(r"\d{3}(,\d+)?%?", j) and re.fullmatch(r"-?\d{1,3}(\d{3})+", out[-1]):
            out[-1] += j
        else:
            out.append(j)
    return out


def parser_texte_boc(texte: str, codes_connus: set[str] | None = None) -> list[Cours]:
    """Lit les lignes « SYMBOLE Nom ... nombres » du texte extrait du PDF."""
    res = {}
    for ligne in texte.splitlines():
        ligne = ligne.strip()
        m = LIGNE.match(ligne)
        if not m:
            continue
        code = m.group("code")
        if codes_connus and code not in codes_connus:
            continue
        valeurs = regrouper_milliers(m.group("nombres"))
        pct = [nombre(v) for v in valeurs if v.endswith("%")]
        nums = [n for n in (nombre(v) for v in valeurs if not v.endswith("%")) if n is not None]
        if not nums:
            continue
        # Convention la plus fréquente du BOC : ... cours veille | cours du jour | variation | volume
        if len(nums) >= 2:
            veille, cloture = nums[0], nums[1]
            volume = int(nums[2]) if len(nums) >= 3 else None
        else:
            veille, cloture, volume = None, nums[0], None
        res[code] = Cours(code=code, nom=m.group("nom").strip(), cours_veille=veille, ouverture=None,
                          cloture=cloture, variation_pct=pct[0] if pct else None, volume=volume, source="boc")
    return list(res.values())


def collecter_boc(session, codes_connus: set[str] | None = None) -> tuple[list[Cours], str | None]:
    import pdfplumber
    page = session.get(URL_LISTE_BOC, timeout=45)
    page.raise_for_status()
    lien = trouver_lien_boc(page.text)
    if not lien:
        return [], None
    pdf = session.get(lien, timeout=90)
    pdf.raise_for_status()
    texte = []
    with pdfplumber.open(io.BytesIO(pdf.content)) as doc:
        for p in doc.pages[:6]:  # les actions figurent dans les premières pages
            texte.append(p.extract_text() or "")
    return parser_texte_boc("\n".join(texte), codes_connus), lien
