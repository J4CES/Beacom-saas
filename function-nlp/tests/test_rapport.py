"""rapport_hebdomadaire : calcul délégué à service-analyses, puis un e-mail par organisation."""
import os

import pytest
from test_function import Services

import function_app

rapport_hebdomadaire = function_app.rapport_hebdomadaire.build().get_user_function()

CONTENU = {
    "semaine_debut": "2026-11-02",
    "semaine_fin": "2026-11-08",
    "total": 8,
    "par_sentiment": {"positive": 5, "neutral": 1, "negative": 2, "mixed": 0},
    "part_negative": 0.25,
    "semaine_precedente": {"total": 4, "par_sentiment": {}, "part_negative": 0.5},
    "themes_negatifs": [{"mot_cle": "attente", "total": 2}],
    "alertes": 1,
    "etablissements": [{"etablissement_id": 10, "total": 6, "negative": 1}, {"etablissement_id": 11, "total": 2, "negative": 1}],
}


class ServicesRapport(Services):
    def __init__(self, organisations=(3, 4), panne_admins=()):
        super().__init__()
        self.organisations, self.panne_admins = organisations, panne_admins

    def __call__(self, methode, url, corps=None):
        self.appels.append((methode, url, corps))
        if url.endswith("/analyses/interne/rapports-hebdomadaires"):
            return {"semaine_debut": "2026-11-02",
                    "rapports": [{"organisation_id": o, "contenu": CONTENU} for o in self.organisations]}
        if url.endswith("/admins"):
            org = int(url.split("/")[-2])
            if org in self.panne_admins:
                raise RuntimeError("service-utilisateurs indisponible")
            return [{"email": f"admin@org{org}.ma", "nom": None}]
        if url.endswith("/etablissements"):
            return [{"id": 10, "nom": "Café Atlas"}]
        raise AssertionError(url)


@pytest.fixture
def emails(monkeypatch):
    envoyes = []

    def envoyer(dest, sujet, texte):
        envoyes.append((dest, sujet, texte))
        return True

    monkeypatch.setattr(function_app, "envoyer_email", envoyer)
    return envoyes


def test_un_email_par_organisation(monkeypatch, emails):
    s = ServicesRapport()
    monkeypatch.setattr(function_app, "_appel_interne", s)
    monkeypatch.setenv("ETABLISSEMENTS_API_URL", "https://etablissements.test")
    rapport_hebdomadaire(None)
    assert [d for d, _, _ in emails] == [["admin@org3.ma"], ["admin@org4.ma"]]
    texte = emails[0][2]
    assert "8 avis analysés (semaine précédente : 4)" in texte
    assert "Part d'avis négatifs : 25% (-25 points sur une semaine)" in texte
    assert "attente (2)" in texte
    assert "Café Atlas : 6 avis dont 1 négatif(s)" in texte
    assert "Établissement n° 11 : 2 avis" in texte  # nom inconnu : numéro


def test_une_organisation_en_erreur_n_empeche_pas_les_autres(monkeypatch, emails):
    monkeypatch.setattr(function_app, "_appel_interne", ServicesRapport(panne_admins=(3,)))
    rapport_hebdomadaire(None)
    assert [d for d, _, _ in emails] == [["admin@org4.ma"]]


def test_echec_du_calcul_remonte(monkeypatch):
    def panne(methode, url, corps=None):
        raise RuntimeError("service-analyses indisponible")

    monkeypatch.setattr(function_app, "_appel_interne", panne)
    with pytest.raises(RuntimeError):
        rapport_hebdomadaire(None)


def test_planification_le_lundi_a_7h():
    (declencheur,) = [b for b in function_app.rapport_hebdomadaire.build().get_bindings() if b.type == "timerTrigger"]
    assert declencheur.schedule == "0 0 7 * * 1"
    assert os.environ.get("ANALYSES_API_URL")
