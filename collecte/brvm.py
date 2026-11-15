"""Lecture des cours des actions sur brvm.org.

La page publique des cours affiche un tableau HTML. Le parseur ne dépend pas
de l'ordre exact des colonnes : il repère chaque colonne par des mots-clés
(« symbole », « clôture », « variation »...), ce qui le rend plus résistant
aux petites évolutions du site.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, asdict
from datetime import date, datetime
from io import StringIO

import pandas as pd

URL_COURS = "https://www.brvm.org/fr/cours-actions/0"


@dataclass
class Cours:
    code: str
    nom: str
    cours_veille: float | None
    ouverture: float | None
    cloture: float
    variation_pct: float | None
    volume: int | None
    source: str = "brvm.org"

    def dict(self):
        return asdict(self)


def _sans_accents(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def nombre(v) -> float | None:
    """Convertit « 7 200 », « 7 200,50 », « -2,14% », « 1 061 » en nombre."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace("\xa0", "").replace(" ", "").replace(" ", "").replace("%", "")
    s = s.replace(",", ".")
    if s in ("", "-", "--", "nan"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


# mot-clé recherché dans l'en-tête -> nom interne (l'ordre compte : le plus précis d'abord)
REGLES_COLONNES = [
    ("symbole", "code"),
    ("code", "code"),
    ("veille", "cours_veille"),
    ("ouverture", "ouverture"),
    ("cloture", "cloture"),
    ("dernier", "cloture"),
    ("variation", "variation_pct"),
    ("var", "variation_pct"),
    ("volume", "volume"),
    ("nom", "nom"),
    ("societe", "nom"),
    ("titre", "nom"),
]


def _mapper_colonnes(colonnes) -> dict:
    mapping = {}
    for col in colonnes:
        c = _sans_accents(col if not isinstance(col, tuple) else " ".join(map(str, col)))
        for mot, interne in REGLES_COLONNES:
            if mot in c and interne not in mapping.values():
                mapping[col] = interne
                break
    return mapping


def trouver_date_seance(html: str) -> date | None:
    """Cherche une date JJ/MM/AAAA dans la page (date de la séance affichée)."""
    dates = []
    for j, m, a in re.findall(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", html):
        try:
            dates.append(date(int(a), int(m), int(j)))
        except ValueError:
            pass
    return max(dates) if dates else None


def parser_cours(html: str) -> list[Cours]:
    """Extrait la liste des cours depuis le HTML de la page des cours."""
    try:
        tables = pd.read_html(StringIO(html), flavor="lxml", thousands=None)
    except ValueError:
        return []
    meilleure, mapping = None, {}
    for t in tables:
        m = _mapper_colonnes(t.columns)
        if "code" in m.values() and "cloture" in m.values() and len(t) > len(meilleure if meilleure is not None else []):
            meilleure, mapping = t, m
    if meilleure is None:
        return []
    df = meilleure.rename(columns=mapping)
    resultats = []
    for _, r in df.iterrows():
        code = str(r.get("code", "")).strip().upper()
        if not re.fullmatch(r"[A-Z]{3,6}", code):
            continue  # ligne de total, d'en-tête répété, etc.
        cloture = nombre(r.get("cloture"))
        if cloture is None:
            continue
        vol = nombre(r.get("volume"))
        resultats.append(Cours(
            code=code,
            nom=str(r.get("nom", code)).strip() if "nom" in df.columns else code,
            cours_veille=nombre(r.get("cours_veille")),
            ouverture=nombre(r.get("ouverture")),
            cloture=cloture,
            variation_pct=nombre(r.get("variation_pct")),
            volume=int(vol) if vol is not None else None,
        ))
    return resultats


def telecharger(session, url: str = URL_COURS) -> str:
    rep = session.get(url, timeout=45)
    rep.raise_for_status()
    rep.encoding = rep.apparent_encoding or "utf-8"
    return rep.text
