import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
import brvm, boc
from controle import controler

ICI = os.path.dirname(__file__)

def page():
    return open(os.path.join(ICI, "page_exemple.html"), encoding="utf-8").read()

def test_parse_page():
    cours = {c.code: c for c in brvm.parser_cours(page())}
    assert set(cours) == {"SOGC", "PALC", "UNXC", "ETIT", "SNTS"}
    assert cours["SOGC"].cloture == 7200 and cours["SOGC"].volume == 1061
    assert cours["UNXC"].variation_pct == -2.03
    assert cours["ETIT"].cloture == 31 and cours["SNTS"].cours_veille == 25000

def test_date_seance():
    assert str(brvm.trouver_date_seance(page())) == "2026-11-14"

def test_colonnes_dans_un_autre_ordre():
    html = "<table><tr><th>Variation</th><th>Dernier cours</th><th>Code</th></tr><tr><td>7,14%</td><td>2 250</td><td>STAC</td></tr></table>"
    c = brvm.parser_cours(html)[0]
    assert (c.code, c.cloture, c.variation_pct) == ("STAC", 2250, 7.14)

def test_page_sans_tableau():
    assert brvm.parser_cours("<html><p>Maintenance</p></html>") == []

def test_controle_variation_hors_limite():
    cours = brvm.parser_cours(page())
    cours[0].variation_pct = 12.0
    r = controler(cours, veille={"SOGC": 7075})
    statuts = {c.code: s for c, s in r.valides}
    assert statuts["SOGC"] == "a_verifier" and statuts["PALC"] == "ok"
    assert any("SOGC" in a for a in r.anomalies)

def test_controle_titre_manquant():
    r = controler(brvm.parser_cours(page()), codes_attendus={"SOGC", "SIBC"})
    assert r.manquants == ["SIBC"]

def test_controle_recalcule_variation():
    cours = brvm.parser_cours(page())
    for c in cours: c.variation_pct = None
    r = controler(cours)
    sogc = [c for c, _ in r.valides if c.code == "SOGC"][0]
    assert sogc.variation_pct == 1.77

def test_boc_texte():
    texte = "BULLETIN OFFICIEL DE LA COTE\nSOGC SOGB COTE D'IVOIRE 7 075 7 200 1,77% 1 061\nPALC PALM CI 7 755 7 800 0,58% 842\nTotal 12"
    c = {x.code: x for x in boc.parser_texte_boc(texte)}
    assert c["SOGC"].cloture == 7200 and c["SOGC"].volume == 1061 and c["PALC"].cours_veille == 7755

def test_boc_lien():
    html = '<a href="/sites/default/files/boc_20261114.pdf">BOC</a><a href="/autre.pdf">x</a>'
    assert boc.trouver_lien_boc(html).endswith("boc_20261114.pdf")

def test_import_csv():
    import import_csv
    chemin = os.path.join(ICI, "..", "..", "donnees", "modele_transactions.csv")
    lignes, erreurs = import_csv.lire(chemin)
    assert not erreurs and len(lignes) == 3 and lignes[0]["poche"] == "dividendes"
