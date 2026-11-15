"""Importe vos transactions depuis un fichier CSV dans Supabase.

Usage : python scripts/import_csv.py donnees/mes_transactions.csv [--essai]
Colonnes : code_titre,date,sens,quantite,cours,frais,poche,note
  - code_titre : symbole BRVM (SOGC, PALC, SNTS, UNXC...)
  - date : AAAA-MM-JJ   - sens : achat | vente   - poche : dividendes | swing
"""
import csv, os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "collecte"))

def lire(chemin):
    lignes, erreurs = [], []
    with open(chemin, encoding="utf-8-sig") as f:
        for i, r in enumerate(csv.DictReader(f), start=2):
            try:
                code = r["code_titre"].strip().upper()
                assert re.fullmatch(r"[A-Z]{3,6}", code), "symbole invalide"
                assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["date"].strip()), "date au format AAAA-MM-JJ attendue"
                sens = r["sens"].strip().lower(); assert sens in ("achat", "vente"), "sens : achat ou vente"
                poche = r["poche"].strip().lower(); assert poche in ("dividendes", "swing"), "poche : dividendes ou swing"
                q = int(r["quantite"]); assert q > 0, "quantité > 0"
                c = float(r["cours"].replace(" ", "").replace(",", ".")); assert c > 0, "cours > 0"
                fr = float((r.get("frais") or "0").replace(" ", "").replace(",", "."))
                lignes.append({"code_titre": code, "date": r["date"].strip(), "sens": sens, "quantite": q,
                               "cours": c, "frais": fr, "poche": poche, "note": (r.get("note") or "").strip() or None})
            except Exception as e:
                erreurs.append(f"ligne {i} : {e}")
    return lignes, erreurs

if __name__ == "__main__":
    chemin = sys.argv[1]
    lignes, erreurs = lire(chemin)
    for e in erreurs: print("ERREUR", e)
    if erreurs: sys.exit(1)
    print(f"{len(lignes)} transactions valides")
    if "--essai" in sys.argv: sys.exit(0)
    from stockage import Supabase
    db = Supabase()
    connus = db.codes_actifs()
    nouveaux = sorted({l["code_titre"] for l in lignes} - connus)
    if nouveaux:
        db.upsert("titres", [{"code": c, "nom": c} for c in nouveaux], "code")
        print("Titres ajoutés (le nom sera complété par la prochaine collecte) :", ", ".join(nouveaux))
    for i in range(0, len(lignes), 200):
        db._req("POST", "transactions", json=lignes[i:i+200], prefer="return=minimal")
    print("Import terminé.")
