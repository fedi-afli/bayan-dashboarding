def review_uncertain_mappings(mapper, result, schema):
    """
    Terminal-based human-in-the-loop review for mappings the pipeline
    isn't fully confident about. For each entry in needs_confirmation:
      - if there's a suggested_field: ask yes/no/correct
      - if there's none (reason == "unresolved"): ask the user to pick
        a field from the schema, or skip
    Confirmed/corrected mappings are written to learned_synonyms.json via
    mapper.confirm_field(), and the in-memory result is updated so the
    final mapping reflects the session's decisions immediately.
    """
    field_names = list(schema["fields"].keys())

    for item in result["needs_confirmation"]:
        source = item["source"]
        suggested = item["suggested_field"]

        if suggested:
            answer = input(
                f"\nColonne '{source}' -> suggestion : '{suggested}'. Correct ? [o]ui / [n]on / [s]auter : "
            ).strip().lower()

            if answer in ("o", "oui", "y", "yes"):
                mapper.confirm_field(source, suggested)
                result["mapping"][source] = suggested
                print(f"  -> confirmé et ajouté aux synonymes appris.")
                continue

            if answer in ("s", "skip", ""):
                print("  -> ignoré, restera 'needs_review'.")
                continue

            # "non" : proposer de corriger manuellement
            corrected = _prompt_field_choice(field_names)
            if corrected:
                mapper.confirm_field(source, corrected)
                result["mapping"][source] = corrected
                result["errors"] = [e for e in result["errors"] if source not in e]
                print(f"  -> corrigé en '{corrected}' et ajouté aux synonymes appris.")
            else:
                # l'utilisateur a explicitement rejeté sans corriger : le
                # mapping suggéré ne doit pas rester dans le résultat final
                result["mapping"].pop(source, None)
                if source not in result["unresolved_columns"]:
                    result["unresolved_columns"].append(source)
                print("  -> rejeté, colonne laissée non résolue.")

        else:
            # reason == "unresolved" : pas de suggestion du tout
            print(f"\nColonne '{source}' n'a pas pu être mappée automatiquement.")
            corrected = _prompt_field_choice(field_names)
            if corrected:
                mapper.confirm_field(source, corrected)
                result["mapping"][source] = corrected
                if source in result["unresolved_columns"]:
                    result["unresolved_columns"].remove(source)
                print(f"  -> mappé en '{corrected}' et ajouté aux synonymes appris.")
            else:
                print("  -> laissé non résolu.")

    # Recalcule le statut final après la session de revue
    remaining_unresolved = result["unresolved_columns"]
    remaining_flagged = [
        c for c in result["needs_confirmation"]
        if c["source"] in result["mapping"] or c["source"] in remaining_unresolved
    ]
    if result["errors"]:
        result["status"] = "error"
    elif remaining_unresolved:
        result["status"] = "needs_review"
    else:
        result["status"] = "ok"

    return result


def _prompt_field_choice(field_names):
    """
    Lets the user pick a schema field by number, or leave blank to skip.
    Returns the field name, or None if skipped.
    """
    print("  Champs disponibles :")
    for i, f in enumerate(field_names, 1):
        print(f"    {i}. {f}")

    raw = input("  Numéro du champ correct (Entrée pour laisser non résolu) : ").strip()
    if not raw:
        return None

    try:
        idx = int(raw) - 1
        if 0 <= idx < len(field_names):
            return field_names[idx]
    except ValueError:
        pass

    print("  Entrée invalide, colonne laissée non résolue.")
    return None