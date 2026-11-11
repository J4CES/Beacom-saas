"""Azure Functions de Beacom. Elles n'accèdent à aucune base : elles passent par les API des services propriétaires,
authentifiées par la clé interne X-API-Key.

analyser_avis (trigger : file `avis-a-analyser`)
  Entrée     : message JSON {avis_id, organisation_id, etablissement_id, texte, langue, date_avis}
  Traitement : langue détectée si absente, sentiment et mots-clés (Azure AI Language)
  Sortie     : analyse et mots-clés -> service-analyses ; alerte si l'avis est très négatif (+ e-mail si Azure
               Communication Services est configuré) ; statut 'analyse' -> service-collecte.

rapport_hebdomadaire (trigger : minuteur, chaque lundi à 7 h UTC, soit 8 h au Maroc hors ramadan)
  Entrée     : aucune (la semaine écoulée)
  Traitement : service-analyses calcule et enregistre un rapport par organisation active
  Sortie     : rapports visibles au tableau de bord ; e-mail de synthèse aux admins de chaque organisation
"""
import html
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


def _url(variable: str, chemin: str) -> str:
    return os.environ[variable].rstrip("/") + chemin


def _appel_interne(methode: str, url: str, corps: dict | None = None):
    """Appel HTTP authentifié par clé interne, réponse JSON décodée.
    Toute erreur HTTP lève une exception : le message est réessayé, puis isolé en poison queue."""
    req = urllib.request.Request(
        url,
        data=json.dumps(corps).encode() if corps is not None else None,
        method=methode,
        headers={"Content-Type": "application/json", "X-API-Key": os.environ["INTERNAL_API_KEY"]},
    )
    with urllib.request.urlopen(req, timeout=15) as reponse:
        contenu = reponse.read()
    return json.loads(contenu) if contenu else None


def _seuil_alerte() -> float:
    """Score négatif à partir duquel un avis négatif déclenche une alerte (SEUIL_ALERTE, 0.8 par défaut)."""
    return float(os.getenv("SEUIL_ALERTE", "0.8"))


def envoyer_email(destinataires: list[str], sujet: str, texte: str) -> bool:
    """E-mail par Azure Communication Services si ACS_CONNECTION_STRING et ACS_EXPEDITEUR sont définis ;
    sinon, simple journal. Renvoie True si l'e-mail est parti."""
    chaine, expediteur = os.getenv("ACS_CONNECTION_STRING"), os.getenv("ACS_EXPEDITEUR")
    if not (chaine and expediteur and destinataires):
        logging.info("E-mail non envoyé (ACS non configuré ou aucun destinataire) : %s", sujet)
        return False
    from azure.communication.email import EmailClient  # import tardif : dépendance utile seulement ici

    message = {
        "senderAddress": expediteur,
        "recipients": {"to": [{"address": d} for d in destinataires]},
        "content": {
            "subject": sujet,
            "plainText": texte,
            "html": "<pre style='font-family:sans-serif;white-space:pre-wrap'>" + html.escape(texte) + "</pre>",
        },
    }
    EmailClient.from_connection_string(chaine).begin_send(message).result()
    return True


def signaler(payload: dict, score_negatif: float, texte: str) -> None:
    """Enregistre l'alerte dans service-analyses, puis prévient les admins de l'organisation.

    L'alerte est idempotente (une par avis) : un message rejoué ne renvoie pas d'e-mail. Un échec d'e-mail est
    journalisé sans relancer le message : l'alerte reste visible au tableau de bord.
    """
    extrait = texte if len(texte) <= 300 else texte[:297] + "..."
    reponse = _appel_interne(
        "POST",
        _url("ANALYSES_API_URL", "/analyses/interne/alertes"),
        {
            "avis_id": payload["avis_id"],
            "organisation_id": payload["organisation_id"],
            "etablissement_id": payload["etablissement_id"],
            "score_negatif": score_negatif,
            "extrait": extrait,
        },
    )
    if not reponse or not reponse.get("creee"):
        return
    logging.warning(
        "Alerte : avis %s très négatif (score %.2f) pour l'organisation %s",
        payload["avis_id"], score_negatif, payload["organisation_id"],
    )
    try:
        admins = []
        if os.getenv("UTILISATEURS_API_URL"):
            admins = _appel_interne(
                "GET", _url("UTILISATEURS_API_URL", f"/interne/organisations/{payload['organisation_id']}/admins")
            ) or []
        lien = os.getenv("FRONTEND_URL", "").rstrip("/")
        envoyer_email(
            [a["email"] for a in admins],
            "Beacom : un avis très négatif vient d'arriver",
            f"Un client a laissé un avis très négatif (score {score_negatif:.0%}) :\n\n« {extrait} »\n\n"
            + (f"Tableau de bord : {lien}/tableau-de-bord\n" if lien else ""),
        )
    except Exception:
        logging.exception("Notification de l'alerte %s non envoyée", payload["avis_id"])


@app.queue_trigger(arg_name="msg", queue_name="avis-a-analyser", connection="AzureWebJobsStorage")
def analyser_avis(msg: func.QueueMessage) -> None:
    payload = json.loads(msg.get_body().decode("utf-8"))
    avis_id = payload["avis_id"]
    # Un message sans organisation ni établissement (ancien format) lève KeyError : il part en poison queue.
    organisation_id = payload["organisation_id"]
    etablissement_id = payload["etablissement_id"]
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

    phrases = client.extract_key_phrases(documents=[texte], language=langue)[0]
    # Les mots-clés enrichissent le tableau de bord sans être indispensables : une erreur ici n'en est pas une pour l'avis.
    mots_cles = [] if phrases.is_error else list(phrases.key_phrases)[:30]
    if phrases.is_error:
        logging.warning("Mots-clés indisponibles pour l'avis %s : %s", avis_id, phrases.error)

    scores = resultat.confidence_scores
    # Toutes les écritures sont idempotentes : rejouer le message est sans danger.
    _appel_interne(
        "POST",
        _url("ANALYSES_API_URL", "/analyses/interne"),
        {
            "avis_id": avis_id,
            "organisation_id": organisation_id,
            "etablissement_id": etablissement_id,
            "sentiment": resultat.sentiment,
            "score_positif": scores.positive,
            "score_neutre": scores.neutral,
            "score_negatif": scores.negative,
            "date_avis": payload.get("date_avis"),
            "mots_cles": mots_cles,
        },
    )
    if resultat.sentiment == "negative" and scores.negative >= _seuil_alerte():
        signaler(payload, scores.negative, texte)
    _appel_interne("PATCH", _url("COLLECTE_API_URL", f"/avis/{avis_id}/statut"), {"statut": "analyse"})
    logging.info("Avis %s analysé : %s, %d mot(s)-clé(s)", avis_id, resultat.sentiment, len(mots_cles))


LIBELLES = {"positive": "positifs", "neutral": "neutres", "negative": "négatifs", "mixed": "mitigés"}


def texte_du_rapport(contenu: dict, noms: dict[int, str]) -> str:
    """Rapport en texte simple, lisible dans n'importe quel client de messagerie."""
    lignes = [f"Semaine du {contenu['semaine_debut']} au {contenu['semaine_fin']}", ""]
    lignes.append(f"{contenu['total']} avis analysés (semaine précédente : {contenu['semaine_precedente']['total']})")
    lignes += [f"  - {n} {LIBELLES[s]}" for s, n in contenu["par_sentiment"].items() if n]
    part, avant = contenu["part_negative"], contenu["semaine_precedente"]["part_negative"]
    if part is not None:
        evolution = "" if avant is None else f" ({(part - avant) * 100:+.0f} points sur une semaine)"
        lignes.append(f"Part d'avis négatifs : {part:.0%}{evolution}")
    if contenu["alertes"]:
        lignes.append(f"Alertes (avis très négatifs) : {contenu['alertes']}")
    if contenu["themes_negatifs"]:
        lignes += ["", "Ce qui revient dans les avis négatifs :"]
        lignes += [f"  - {t['mot_cle']} ({t['total']})" for t in contenu["themes_negatifs"]]
    if contenu["etablissements"]:
        lignes += ["", "Par établissement :"]
        for e in contenu["etablissements"]:
            nom = noms.get(e["etablissement_id"], f"Établissement n° {e['etablissement_id']}")
            lignes.append(f"  - {nom} : {e['total']} avis dont {e['negative']} négatif(s)")
    lien = os.getenv("FRONTEND_URL", "").rstrip("/")
    if lien:
        lignes += ["", f"Tableau de bord : {lien}/tableau-de-bord"]
    return "\n".join(lignes)


def noms_des_etablissements(organisation_id: int) -> dict[int, str]:
    """Noms des établissements (service-etablissements). Facultatif : à défaut, le rapport affiche les numéros."""
    if not os.getenv("ETABLISSEMENTS_API_URL"):
        return {}
    try:
        liste = _appel_interne(
            "GET", _url("ETABLISSEMENTS_API_URL", f"/interne/organisations/{organisation_id}/etablissements")
        )
        return {e["id"]: e["nom"] for e in liste or []}
    except Exception:
        logging.exception("Noms des établissements indisponibles pour l'organisation %s", organisation_id)
        return {}


@app.timer_trigger(arg_name="minuteur", schedule="0 0 7 * * 1", run_on_startup=False)
def rapport_hebdomadaire(minuteur: func.TimerRequest) -> None:
    # Si le calcul échoue, l'exception remonte : l'exécution apparaît en échec dans le suivi (et déclenche l'alerte
    # d'exploitation). Relancer est sans danger : la route remplace les rapports de la semaine.
    resultat = _appel_interne("POST", _url("ANALYSES_API_URL", "/analyses/interne/rapports-hebdomadaires"))
    envoyes = 0
    for rapport in resultat["rapports"]:
        org = rapport["organisation_id"]
        # Une organisation en erreur n'empêche pas d'envoyer le rapport des autres.
        try:
            admins = []
            if os.getenv("UTILISATEURS_API_URL"):
                admins = _appel_interne("GET", _url("UTILISATEURS_API_URL", f"/interne/organisations/{org}/admins")) or []
            texte = texte_du_rapport(rapport["contenu"], noms_des_etablissements(org))
            if envoyer_email([a["email"] for a in admins], "Beacom : votre rapport de la semaine", texte):
                envoyes += 1
        except Exception:
            logging.exception("Rapport hebdomadaire non envoyé à l'organisation %s", org)
    logging.info(
        "Rapports de la semaine du %s : %d calculé(s), %d envoyé(s) par e-mail",
        resultat["semaine_debut"], len(resultat["rapports"]), envoyes,
    )
