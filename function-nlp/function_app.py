"""Azure Function déclenchée par la file `avis-a-analyser`.

Entrée  : message JSON {avis_id, organisation_id, texte, langue}
Traitement : analyse de sentiment avec Azure AI Language
Sortie  : résultat envoyé à service-analyses (qui possède db_analyses), puis statut de l'avis mis à jour
          dans service-collecte (qui possède db_collecte). La Function n'accède à aucune base directement.
"""
import json
import logging
import os
import urllib.request

import azure.functions as func
from azure.ai.textanalytics import TextAnalyticsClient
from azure.core.credentials import AzureKeyCredential

app = func.FunctionApp()


def _language_client() -> TextAnalyticsClient:
    return TextAnalyticsClient(
        endpoint=os.environ["LANGUAGE_ENDPOINT"],
        credential=AzureKeyCredential(os.environ["LANGUAGE_KEY"]),
    )


def _appel_interne(methode: str, url: str, corps: dict) -> None:
    """Appel HTTP authentifié par clé interne. Toute erreur HTTP lève une exception (-> nouvelle tentative)."""
    req = urllib.request.Request(
        url,
        data=json.dumps(corps).encode(),
        method=methode,
        headers={"Content-Type": "application/json", "X-API-Key": os.environ["INTERNAL_API_KEY"]},
    )
    with urllib.request.urlopen(req, timeout=15) as reponse:
        reponse.read()


@app.queue_trigger(arg_name="msg", queue_name="avis-a-analyser", connection="AzureWebJobsStorage")
def analyser_avis(msg: func.QueueMessage) -> None:
    payload = json.loads(msg.get_body().decode("utf-8"))
    avis_id = payload["avis_id"]
    # Un message sans organisation (antérieur au multi-clients) lève KeyError : il part en poison queue.
    organisation_id = payload["organisation_id"]
    texte = (payload.get("texte") or "").strip()
    if not texte:
        logging.warning("Avis %s sans texte : message ignoré", avis_id)
        return

    client = _language_client()
    langue = payload.get("langue")
    if not langue:
        detection = client.detect_language(documents=[texte])[0]
        langue = None if detection.is_error else detection.primary_language.iso6391_name

    resultat = client.analyze_sentiment(documents=[texte], language=langue)[0]
    if resultat.is_error:
        # Lève une exception : la file réessaiera, puis passera en poison queue.
        raise RuntimeError(f"Azure AI Language a échoué pour l'avis {avis_id}: {resultat.error}")

    scores = resultat.confidence_scores
    analyses_url = os.environ["ANALYSES_API_URL"].rstrip("/")
    collecte_url = os.environ["COLLECTE_API_URL"].rstrip("/")

    # Les deux appels sont idempotents : rejouer le message est sans danger.
    _appel_interne(
        "POST",
        f"{analyses_url}/analyses/interne",
        {
            "avis_id": avis_id,
            "organisation_id": organisation_id,
            "sentiment": resultat.sentiment,
            "score_positif": scores.positive,
            "score_neutre": scores.neutral,
            "score_negatif": scores.negative,
        },
    )
    _appel_interne("PATCH", f"{collecte_url}/avis/{avis_id}/statut", {"statut": "analyse"})
    logging.info("Avis %s analysé : %s", avis_id, resultat.sentiment)
