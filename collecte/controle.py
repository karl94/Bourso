"""Contrôle de cohérence : aucune donnée douteuse ne doit produire un signal."""
from __future__ import annotations

from dataclasses import dataclass, field

LIMITE_VARIATION_PCT = 7.5   # variation quotidienne maximale autorisée à la BRVM
MIN_TITRES_ATTENDUS = 30     # en dessous, la collecte est jugée incomplète


@dataclass
class Rapport:
    valides: list = field(default_factory=list)       # (Cours, statut)
    anomalies: list = field(default_factory=list)     # messages lisibles
    manquants: list = field(default_factory=list)     # codes absents par rapport à la veille

    @property
    def nb_a_verifier(self):
        return sum(1 for _, s in self.valides if s == "a_verifier")


def controler(cours: list, veille: dict[str, float] | None = None,
              codes_attendus: set[str] | None = None, source_secours: bool = False) -> Rapport:
    """Classe chaque cours en « ok » ou « a_verifier ».

    veille : dernier cours connu par code (pour recalculer la variation si besoin).
    source_secours : données issues du BOC -> toujours « a_verifier » sauf si cohérentes avec la veille.
    """
    veille = veille or {}
    r = Rapport()
    vus = set()
    for c in cours:
        if c.code in vus:
            continue
        vus.add(c.code)
        problemes = []
        if c.cloture is None or c.cloture <= 0:
            problemes.append("cours nul ou négatif")
        ref = c.cours_veille or veille.get(c.code)
        var = c.variation_pct
        if var is None and ref:
            var = round(100 * (c.cloture / ref - 1), 2)
            c.variation_pct = var
        if var is not None and abs(var) > LIMITE_VARIATION_PCT + 0.05:
            problemes.append(f"variation de {var:+.2f} % au-delà de la limite de ±{LIMITE_VARIATION_PCT} %")
        if ref and c.cours_veille and c.code in veille and abs(c.cours_veille - veille[c.code]) > 0.5:
            problemes.append(f"cours veille {c.cours_veille:g} différent de la base ({veille[c.code]:g})")
        if source_secours and not ref:
            problemes.append("source de secours sans cours de référence")
        statut = "a_verifier" if problemes else "ok"
        if problemes:
            r.anomalies.append(f"{c.code} : " + " ; ".join(problemes))
        r.valides.append((c, statut))
    if codes_attendus:
        r.manquants = sorted(codes_attendus - vus)
    return r


def collecte_complete(rapport: Rapport) -> bool:
    return len(rapport.valides) >= MIN_TITRES_ATTENDUS
