from mapper.mapper import BayanMapper

test_profiles = {

    # baseline — should resolve fully via fuzzy/embedding, no LLM needed
    "baseline_french": {
        "columns": [
            {"name": "Article", "type": "string", "examples": ["iPhone"]},
            {"name": "QTE", "type": "integer", "examples": [1]},
            {"name": "Montant HT", "type": "float", "examples": [2500]},
        ]
    },

    # every field present at once, mixed FR/EN naming
    "full_schema_coverage": {
        "columns": [
            {"name": "Article", "type": "string", "examples": ["iPhone"]},
            {"name": "QTE", "type": "integer", "examples": [1]},
            {"name": "Montant HT", "type": "float", "examples": [2500]},
            {"name": "Date Vente", "type": "date", "examples": ["2024-01-01"]},
            {"name": "Prix Unitaire", "type": "float", "examples": [500]},
            {"name": "Nom Client", "type": "string", "examples": ["Ahmed"]},
            {"name": "ID Client", "type": "string", "examples": ["C-001"]},
            {"name": "Categorie", "type": "string", "examples": ["Electronics"]},
            {"name": "Remise", "type": "float", "examples": [0.1]},
            {"name": "TVA", "type": "float", "examples": [475]},
            {"name": "Mode Paiement", "type": "string", "examples": ["Cash"]},
            {"name": "Magasin", "type": "string", "examples": ["Tunis Centre"]},
            {"name": "Vendeur", "type": "string", "examples": ["Fedi"]},
            {"name": "Numero Facture", "type": "string", "examples": ["INV-0012"]},
            {"name": "Devise", "type": "string", "examples": ["TND"]},
        ]
    },

    # same coverage but pure English naming — checks matcher isn't overfit to French
    "full_schema_english": {
        "columns": [
            {"name": "Product", "type": "string", "examples": ["iPhone"]},
            {"name": "Qty", "type": "integer", "examples": [1]},
            {"name": "Total Revenue", "type": "float", "examples": [2500]},
            {"name": "Order Date", "type": "date", "examples": ["2024-01-01"]},
            {"name": "Unit Cost", "type": "float", "examples": [500]},
            {"name": "Buyer", "type": "string", "examples": ["Ahmed"]},
            {"name": "Customer ID", "type": "string", "examples": ["C-001"]},
            {"name": "Category", "type": "string", "examples": ["Electronics"]},
            {"name": "Discount", "type": "float", "examples": [0.1]},
            {"name": "Tax", "type": "float", "examples": [475]},
            {"name": "Payment Type", "type": "string", "examples": ["Cash"]},
            {"name": "Store", "type": "string", "examples": ["Downtown"]},
            {"name": "Sales Rep", "type": "string", "examples": ["John"]},
            {"name": "Invoice #", "type": "string", "examples": ["INV-0012"]},
            {"name": "Currency", "type": "string", "examples": ["USD"]},
        ]
    },

    # heavily abbreviated / cryptic real-world export style
    "cryptic_full": {
        "columns": [
            {"name": "Art", "type": "string", "examples": ["iPhone"]},
            {"name": "Qte", "type": "integer", "examples": [1]},
            {"name": "MT_HT", "type": "float", "examples": [2500]},
            {"name": "Dt", "type": "date", "examples": ["01/01/2024"]},
            {"name": "PU", "type": "float", "examples": [500]},
            {"name": "Cust_ID", "type": "string", "examples": ["C-001"]},
            {"name": "Cat", "type": "string", "examples": ["Elec"]},
            {"name": "Curr", "type": "string", "examples": ["TND"]},
        ]
    },

    # near-duplicate fields that should NOT collapse into each other
    # (unit_price vs revenue vs tax_amount all involve money but are distinct)
    "financial_disambiguation": {
        "columns": [
            {"name": "Article", "type": "string", "examples": ["iPhone"]},
            {"name": "QTE", "type": "integer", "examples": [1]},
            {"name": "Prix Unitaire", "type": "float", "examples": [500]},
            {"name": "Montant TVA", "type": "float", "examples": [95]},
            {"name": "Montant Total TTC", "type": "float", "examples": [2595]},  # ambiguous vs revenue
        ]
    },

    # genuinely unresolvable columns — should stay null, not force-matched
    "truly_unmatched": {
        "columns": [
            {"name": "Article", "type": "string", "examples": ["iPhone"]},
            {"name": "QTE", "type": "integer", "examples": [1]},
            {"name": "Montant HT", "type": "float", "examples": [2500]},
            {"name": "Commentaire Interne", "type": "string", "examples": ["urgent"]},
            {"name": "Code Barre", "type": "string", "examples": ["8801643"]},
            {"name": "Poids KG", "type": "float", "examples": [1.2]},
        ]
    },

    # typos — tests fuzzy threshold specifically
    "typos": {
        "columns": [
            {"name": "Artcle", "type": "string", "examples": ["iPhone"]},
            {"name": "Qauntity", "type": "integer", "examples": [1]},
            {"name": "Reveune", "type": "float", "examples": [2500]},
        ]
    },

    # generic/meaningless headers from a raw CSV export
    "meaningless_headers": {
        "columns": [
            {"name": "col_1", "type": "string", "examples": ["iPhone"]},
            {"name": "Unnamed: 2", "type": "integer", "examples": [1]},
            {"name": "field3", "type": "float", "examples": [2500]},
        ]
    },
}


if __name__ == "__main__":
    mapper = BayanMapper()

    for name, profile in test_profiles.items():
        print(f"\n{'='*60}\nTEST: {name}\n{'='*60}")
        try:
            mapping = mapper.map(profile)
            print(f"✅ SUCCESS: {mapping}")
        except Exception as e:
            print(f"❌ FAILED: {e}")