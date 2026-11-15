"""Collecte quotidienne des cours BRVM.

Usage :
  python main.py                 # collecte réelle (variables SUPABASE_* et TELEGRAM_* requises)
  python main.py --essai         # collecte sans rien écrire : affiche ce qui serait enregistré
  python main.py --essai --html page.html   # teste le parseur sur une page enregistrée
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import date, datetime, timezone

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import boc
import brvm
from controle import collecte_complete, controler

UA = "BRVM-Mon-Portefeuille/1.0 (usage personnel, 1 requete par jour)"


def session_http() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "fr-FR,fr;q=0.9"})
    s.mount("https://", HTTPAdapter(max_retries=Retry(total=3, backoff_factor=5, status_forcelist=[429, 500, 502, 503, 504])))
    return s


def fmt(n, dec=0):
    return f"{n:,.{dec}f}".replace(",", " ").replace(".", ",")


def resume_telegram(date_seance, rapport, source, positions):
    lignes = [f"<b>Collecte BRVM du {date_seance:%d/%m/%Y}</b>",
              f"{len(rapport.valides)} titres lus ({source})"]
    if rapport.nb_a_verifier:
        lignes.append(f"⚠️ {rapport.nb_a_verifier} cours à vérifier")
    if positions:
        lignes.append("\n<b>Mes titres</b>")
        cours = {c.code: c for c, _ in rapport.valides}
        for p in positions:
            c = cours.get(p["code_titre"])
            if c:
                v = f" ({c.variation_pct:+.2f} %)".replace(".", ",") if c.variation_pct is not None else ""
                lignes.append(f"{p['nom']} : {fmt(c.cloture)} FCFA{v}")
    if rapport.anomalies:
        lignes.append("\n<b>Anomalies</b>")
        lignes += rapport.anomalies[:8]
    return "\n".join(lignes)


def executer(essai: bool = False, html_local: str | None = None) -> int:
    debut = time.time()
    db = None
    veille, derniere_date, codes = {}, None, set()
    if not essai:
        from stockage import Supabase
        db = Supabase()
        veille, derniere_date = db.derniers_cours()
        codes = db.codes_actifs()

    s = session_http()
    source, erreurs = "brvm.org", []
    cours, date_seance = [], None

    # 1. Source principale : page des cours
    try:
        html = open(html_local, encoding="utf-8").read() if html_local else brvm.telecharger(s)
        cours = brvm.parser_cours(html)
        date_seance = brvm.trouver_date_seance(html)
    except Exception as e:  # noqa: BLE001
        erreurs.append(f"brvm.org : {e}")

    rapport = controler(cours, veille, codes)

    # 2. Secours : BOC si la page est vide ou incomplète
    if not collecte_complete(rapport) and not html_local:
        time.sleep(4)
        try:
            cours_boc, lien = boc.collecter_boc(s, codes or None)
            if len(cours_boc) > len(cours):
                source, cours = f"boc ({lien})", cours_boc
                rapport = controler(cours, veille, codes, source_secours=True)
        except Exception as e:  # noqa: BLE001
            erreurs.append(f"BOC : {e}")

    date_seance = date_seance or datetime.now(timezone.utc).date()
    statut = "ok" if collecte_complete(rapport) and not rapport.nb_a_verifier else ("partiel" if rapport.valides else "echec")

    # 3. Jour sans séance (férié) : mêmes cours que la dernière date connue
    if derniere_date and str(date_seance) <= derniere_date and rapport.valides:
        identiques = all(abs(veille.get(c.code, -1) - c.cloture) < 0.01 for c, _ in rapport.valides)
        if identiques:
            statut = "pas_de_seance"

    if essai:
        print(f"Séance : {date_seance} · source : {source} · statut : {statut}")
        for c, st in rapport.valides:
            print(f"  {c.code:<7} {c.cloture:>10,.0f}  {c.variation_pct if c.variation_pct is not None else '':>6}  vol {c.volume or 0:>8}  {st}")
        for a in rapport.anomalies + erreurs:
            print("  !", a)
        return 0 if rapport.valides else 1

    from telegram import envoyer

    if statut == "pas_de_seance":
        db.inserer("collectes", {"source": source, "date_seance": str(date_seance), "nb_titres": 0,
                                 "nb_erreurs": 0, "duree_s": round(time.time() - debut, 1),
                                 "statut": statut, "message": "Pas de nouvelle séance (jour férié ?)"})
        return 0

    if rapport.valides:
        nouveaux = [{"code": c.code, "nom": c.nom} for c, _ in rapport.valides if c.code not in codes]
        db.upsert("titres", nouveaux, "code")
        db.upsert("cours_journaliers", [{
            "code_titre": c.code, "date": str(date_seance), "cours_veille": c.cours_veille,
            "ouverture": c.ouverture, "cloture": c.cloture, "variation_pct": c.variation_pct,
            "volume": c.volume, "statut": st, "source": c.source} for c, st in rapport.valides],
            "code_titre,date")

    db.inserer("collectes", {
        "source": source, "date_seance": str(date_seance), "nb_titres": len(rapport.valides),
        "nb_erreurs": len(rapport.anomalies) + len(erreurs), "duree_s": round(time.time() - debut, 1),
        "statut": statut, "message": " | ".join((erreurs + rapport.anomalies)[:20]) or None})

    if statut == "echec":
        msg = "❌ <b>Collecte BRVM en échec</b>\n" + "\n".join(erreurs or ["Aucun cours lu."])
        db.inserer("alertes", {"type": "collecte", "message": msg, "envoyee": envoyer(msg)})
        return 1

    positions = db.lire("positions", select="code_titre,nom") or []
    msg = resume_telegram(date_seance, rapport, source, positions)
    if statut == "partiel":
        msg = "⚠️ " + msg
        db.inserer("alertes", {"type": "collecte", "message": msg, "envoyee": False})
    envoyer(msg)
    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--essai", action="store_true", help="n'écrit rien, affiche le résultat")
    p.add_argument("--html", help="fichier HTML local à analyser à la place du site")
    a = p.parse_args()
    sys.exit(executer(a.essai, a.html))
