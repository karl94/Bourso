"""Exporte chaque table Supabase en CSV dans le dossier donné."""
import csv, os, sys
import requests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "collecte"))
from stockage import Supabase

TABLES = ["titres", "cours_journaliers", "transactions", "dividendes", "objectifs",
          "signaux", "veille", "alertes", "collectes", "parametres"]

if __name__ == "__main__":
    dossier = sys.argv[1] if len(sys.argv) > 1 else "sauvegarde"
    os.makedirs(dossier, exist_ok=True)
    db = Supabase()
    for t in TABLES:
        lignes, debut = [], 0
        while True:
            lot = requests.get(f"{db.url}/{t}", headers={**db.h, "Range": f"{debut}-{debut+999}"},
                               params={"select": "*"}, timeout=60).json()
            lignes += lot
            if len(lot) < 1000: break
            debut += 1000
        with open(os.path.join(dossier, f"{t}.csv"), "w", newline="", encoding="utf-8") as f:
            if lignes:
                w = csv.DictWriter(f, fieldnames=list(lignes[0].keys())); w.writeheader(); w.writerows(lignes)
        print(f"{t} : {len(lignes)} lignes")
