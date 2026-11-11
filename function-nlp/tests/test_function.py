"""analyser_avis transmet l'organisation à service-analyses ; Azure AI Language et les API sont simulés."""
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import azure.functions as func
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.update(
    LANGUAGE_ENDPOINT="https://langue.test",
    LANGUAGE_KEY="cle",
    INTERNAL_API_KEY="cle-interne",
    ANALYSES_API_URL="https://analyses.test",
    COLLECTE_API_URL="https://collecte.test/",
)

import function_app  # noqa: E402

analyser_avis = function_app.analyser_avis.build().get_user_function()


class LangueFactice:
    def analyze_sentiment(self, documents, language):
        scores = SimpleNamespace(positive=0.1, neutral=0.1, negative=0.8)
        return [SimpleNamespace(is_error=False, sentiment="negative", confidence_scores=scores)]

    def detect_language(self, documents):
        return [SimpleNamespace(is_error=False, primary_language=SimpleNamespace(iso6391_name="fr"))]


@pytest.fixture
def appels(monkeypatch):
    liste = []
    monkeypatch.setattr(function_app, "_language_client", lambda: LangueFactice())
    monkeypatch.setattr(function_app, "_appel_interne", lambda m, url, corps: liste.append((m, url, corps)))
    return liste


def message(**corps):
    return func.QueueMessage(body=json.dumps(corps).encode())


def test_resultat_envoye_avec_l_organisation(appels):
    analyser_avis(message(avis_id=7, organisation_id=3, texte="Service lent", langue=None))
    (m1, url1, corps1), (m2, url2, corps2) = appels
    assert (m1, url1) == ("POST", "https://analyses.test/analyses/interne")
    assert corps1["organisation_id"] == 3 and corps1["avis_id"] == 7 and corps1["sentiment"] == "negative"
    assert (m2, url2, corps2) == ("PATCH", "https://collecte.test/avis/7/statut", {"statut": "analyse"})


def test_message_sans_organisation_rejete(appels):
    with pytest.raises(KeyError):
        analyser_avis(message(avis_id=7, texte="Bien", langue="fr"))
    assert appels == []


def test_avis_vide_ignore(appels):
    analyser_avis(message(avis_id=7, organisation_id=3, texte="  ", langue="fr"))
    assert appels == []
