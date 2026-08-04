import re


def _tokens(name: str) -> set[str]:
    name = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name)
    return set(re.split(r"[^a-zA-Z0-9]+", name.lower())) - {""}


def check_llm_mapping_plausibility(llm_mapping: dict, schema: dict) -> dict:
    """
    Vérification heuristique pour les mappings issus du fallback LLM
    uniquement. Marque un mapping comme suspect si la colonne source ne
    partage aucun token avec le nom du champ cible.

    C'est un filet de sécurité bon marché, pas une validation sémantique :
    ça peut rater de vraies erreurs et signaler à tort des mappings
    corrects mais très abrégés. À traiter comme "à faire vérifier par un
    humain", pas comme une vérité absolue.
    """
    suspicious = {}
    for source, target in llm_mapping.items():
        if not target:
            continue
        if not (_tokens(source) & _tokens(target)):
            suspicious[source] = target
    return suspicious