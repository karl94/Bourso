"""Écriture dans Supabase via son API REST (aucune bibliothèque supplémentaire)."""
from __future__ import annotations

import os
import requests


class Supabase:
    def __init__(self, url: str | None = None, cle: str | None = None):
        self.url = (url or os.environ["SUPABASE_URL"]).rstrip("/") + "/rest/v1"
        cle = cle or os.environ["SUPABASE_SERVICE_KEY"]
        self.h = {"apikey": cle, "Authorization": f"Bearer {cle}", "Content-Type": "application/json"}

    def _req(self, methode, table, params=None, json=None, prefer=None):
        h = dict(self.h)
        if prefer:
            h["Prefer"] = prefer
        r = requests.request(methode, f"{self.url}/{table}", headers=h, params=params, json=json, timeout=45)
        if r.status_code >= 400:
            raise RuntimeError(f"Supabase {methode} {table} : {r.status_code} {r.text[:300]}")
        return r.json() if r.text else None

    def lire(self, table, **params):
        return self._req("GET", table, params=params)

    def upsert(self, table, lignes, conflit):
        if not lignes:
            return
        for i in range(0, len(lignes), 500):
            self._req("POST", table, params={"on_conflict": conflit}, json=lignes[i:i + 500],
                      prefer="resolution=merge-duplicates,return=minimal")

    def inserer(self, table, ligne):
        self._req("POST", table, json=ligne, prefer="return=minimal")

    # --- raccourcis métier ---
    def derniers_cours(self) -> tuple[dict, str | None]:
        lignes = self.lire("dernier_cours", select="code_titre,date,cloture")
        d = {l["code_titre"]: float(l["cloture"]) for l in lignes or []}
        derniere = max((l["date"] for l in lignes or []), default=None)
        return d, derniere

    def codes_actifs(self) -> set[str]:
        return {l["code"] for l in self.lire("titres", select="code", actif="eq.true") or []}
