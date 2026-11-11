"""analyser_avis : sentiment, mots-clés, alerte et e-mail. Azure AI Language et les API sont simulés."""
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
    UTILISATEURS_API_URL="https://utilisateurs.test",
)

import function_app  # noqa: E402

analyser_avis = function_app.analyser_avis.build().get_user_function()


class LangueFactice:
    def __init__(self, sentiment="negative", negatif=0.95, phrases=("attente", "café froid"), erreur_phrases=False):
        self.sentiment, self.negatif, self.phrases, self.erreur_phrases = sentiment, negatif, phrases, erreur_phrases
        self.langues = []

    def analyze_sentiment(self, documents, language):
        self.langues.append(language)
        scores = SimpleNamespace(positive=round(1 - self.negatif, 2), neutral=0.0, negative=self.negatif)
        return [SimpleNamespace(is_error=False, sentiment=self.sentiment, confidence_scores=scores)]

    def extract_key_phrases(self, documents, language):
        if self.erreur_phrases:
            return [SimpleNamespace(is_error=True, error="quota")]
        return [SimpleNamespace(is_error=False, key_phrases=list(self.phrases))]

    def detect_language(self, documents):
        return [SimpleNamespace(is_error=False, primary_language=SimpleNamespace(iso6391_name="fr"))]


class Services:
    """Simule service-analyses, service-collecte et service-utilisateurs."""

    def __init__(self, alerte_creee=True):
        self.appels, self.alerte_creee = [], alerte_creee

    def __call__(self, methode, url, corps=None):
        self.appels.append((methode, url, corps))
        if url.endswith("/analyses/interne/alertes"):
            return {"creee": self.alerte_creee}
        if url.endswith("/admins"):
            return [{"email": "gerant@atlas.ma", "nom": None}]
        return {}

    def vers(self, fin):
        return [c for m, u, c in self.appels if u.endswith(fin)]


@pytest.fixture
def services(monkeypatch):
    s = Services()
    monkeypatch.setattr(function_app, "_appel_interne", s)
    return s


@pytest.fixture
def emails(monkeypatch):
    envoyes = []
    monkeypatch.setattr(function_app, "envoyer_email", lambda dest, sujet, texte: envoyes.append((dest, sujet, texte)))
    return envoyes


def langue(monkeypatch, **options):
    l = LangueFactice(**options)
    monkeypatch.setattr(function_app, "_language_client", lambda: l)
    return l


def message(**corps):
    base = {"avis_id": 7, "organisation_id": 3, "etablissement_id": 12, "texte": "Attente interminable, café froid",
            "langue": "fr", "date_avis": None}
    return func.QueueMessage(body=json.dumps(base | corps).encode())


def test_analyse_et_mots_cles_envoyes(monkeypatch, services, emails):
    langue(monkeypatch, sentiment="positive", negatif=0.1, phrases=("terrasse", "accueil"))
    analyser_avis(message(date_avis="2026-03-01T12:00:00+00:00"))
    (analyse,) = services.vers("/analyses/interne")
    assert analyse["organisation_id"] == 3 and analyse["etablissement_id"] == 12
    assert analyse["mots_cles"] == ["terrasse", "accueil"] and analyse["date_avis"].startswith("2026-03-01")
    assert services.vers("/avis/7/statut") == [{"statut": "analyse"}]
    assert services.vers("/analyses/interne/alertes") == [] and emails == []
    # L'ordre compte : le statut 'analyse' est posé en dernier, une fois tout enregistré.
    assert services.appels[-1][1] == "https://collecte.test/avis/7/statut"


def test_avis_tres_negatif_cree_une_alerte_et_previent_les_admins(monkeypatch, services, emails):
    langue(monkeypatch, negatif=0.95)
    analyser_avis(message())
    (alerte,) = services.vers("/analyses/interne/alertes")
    assert alerte == {"avis_id": 7, "organisation_id": 3, "etablissement_id": 12, "score_negatif": 0.95,
                      "extrait": "Attente interminable, café froid"}
    (dest, sujet, texte), = emails
    assert dest == ["gerant@atlas.ma"] and "très négatif" in sujet and "café froid" in texte


def test_pas_de_second_email_si_l_alerte_existait(monkeypatch, services, emails):
    langue(monkeypatch, negatif=0.95)
    services.alerte_creee = False  # message rejoué
    analyser_avis(message())
    assert len(services.vers("/analyses/interne/alertes")) == 1 and emails == []


def test_seuil_d_alerte_configurable(monkeypatch, services, emails):
    langue(monkeypatch, negatif=0.7)
    analyser_avis(message())
    assert services.vers("/analyses/interne/alertes") == []
    monkeypatch.setenv("SEUIL_ALERTE", "0.6")
    analyser_avis(message())
    assert len(services.vers("/analyses/interne/alertes")) == 1


def test_echec_email_ne_relance_pas_le_message(monkeypatch, services):
    langue(monkeypatch, negatif=0.99)

    def panne(*a):
        raise RuntimeError("ACS indisponible")

    monkeypatch.setattr(function_app, "envoyer_email", panne)
    analyser_avis(message())  # pas d'exception
    assert services.vers("/avis/7/statut") == [{"statut": "analyse"}]


def test_extrait_tronque(monkeypatch, services, emails):
    langue(monkeypatch, negatif=0.99)
    analyser_avis(message(texte="mauvais " * 100))
    (alerte,) = services.vers("/analyses/interne/alertes")
    assert len(alerte["extrait"]) == 300 and alerte["extrait"].endswith("...")


def test_mots_cles_indisponibles_n_empechent_pas_l_analyse(monkeypatch, services, emails):
    langue(monkeypatch, sentiment="neutral", negatif=0.1, erreur_phrases=True)
    analyser_avis(message())
    assert services.vers("/analyses/interne")[0]["mots_cles"] == []


def test_langue_detectee_si_absente(monkeypatch, services, emails):
    l = langue(monkeypatch, sentiment="positive", negatif=0.0)
    analyser_avis(message(langue=None))
    assert l.langues == ["fr"]


@pytest.mark.parametrize("manquant", ["organisation_id", "etablissement_id"])
def test_message_ancien_format_rejete(monkeypatch, services, manquant):
    langue(monkeypatch)
    corps = json.loads(message().get_body())
    del corps[manquant]
    with pytest.raises(KeyError):
        analyser_avis(func.QueueMessage(body=json.dumps(corps).encode()))
    assert services.appels == []


def test_avis_vide_ignore(monkeypatch, services):
    langue(monkeypatch)
    analyser_avis(message(texte="  "))
    assert services.appels == []


def test_email_sans_acs_est_un_simple_journal(monkeypatch):
    monkeypatch.delenv("ACS_CONNECTION_STRING", raising=False)
    assert function_app.envoyer_email(["a@b.ma"], "Sujet", "Texte") is False


def test_email_par_acs(monkeypatch):
    import azure.communication.email as acs

    envoyes = []

    class ClientFactice:
        @classmethod
        def from_connection_string(cls, chaine):
            return cls()

        def begin_send(self, message):
            envoyes.append(message)
            return SimpleNamespace(result=lambda: {"status": "Succeeded"})

    monkeypatch.setattr(acs, "EmailClient", ClientFactice)
    monkeypatch.setenv("ACS_CONNECTION_STRING", "endpoint=https://acs.test/;accesskey=x")
    monkeypatch.setenv("ACS_EXPEDITEUR", "DoNotReply@beacom.test")
    assert function_app.envoyer_email(["a@b.ma"], "Sujet", "<script>") is True
    assert envoyes[0]["recipients"] == {"to": [{"address": "a@b.ma"}]}
    assert "&lt;script&gt;" in envoyes[0]["content"]["html"]
