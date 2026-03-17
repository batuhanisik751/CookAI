"""Match ingredients against user dietary preferences and allergies."""

DIETARY_INGREDIENT_MAP: dict[str, list[str]] = {
    "dairy-free": [
        "milk",
        "cream",
        "butter",
        "cheese",
        "yogurt",
        "whey",
        "casein",
        "ghee",
        "sour cream",
        "cream cheese",
        "cottage cheese",
        "ricotta",
        "mozzarella",
        "parmesan",
        "cheddar",
        "brie",
        "gouda",
        "feta",
        "half-and-half",
        "heavy cream",
        "whipped cream",
        "buttermilk",
        "ice cream",
        "custard",
    ],
    "vegan": [
        "milk",
        "cream",
        "butter",
        "cheese",
        "yogurt",
        "whey",
        "casein",
        "ghee",
        "sour cream",
        "cream cheese",
        "cottage cheese",
        "ricotta",
        "egg",
        "eggs",
        "honey",
        "gelatin",
        "lard",
        "tallow",
        "suet",
        "anchovy",
        "anchovies",
        "fish sauce",
        "oyster sauce",
        "heavy cream",
        "buttermilk",
        "whipped cream",
    ],
    "gluten-free": [
        "flour",
        "all-purpose flour",
        "bread flour",
        "cake flour",
        "wheat",
        "barley",
        "rye",
        "semolina",
        "couscous",
        "bulgur",
        "breadcrumbs",
        "panko",
        "pasta",
        "noodles",
        "spaghetti",
        "soy sauce",
        "malt",
        "seitan",
        "orzo",
        "farro",
    ],
    "nut-free": [
        "almond",
        "almonds",
        "almond flour",
        "almond milk",
        "almond butter",
        "walnut",
        "walnuts",
        "pecan",
        "pecans",
        "cashew",
        "cashews",
        "pistachio",
        "pistachios",
        "hazelnut",
        "hazelnuts",
        "macadamia",
        "pine nut",
        "pine nuts",
        "peanut",
        "peanuts",
        "peanut butter",
        "peanut oil",
        "nut",
        "nuts",
        "mixed nuts",
    ],
    "egg-free": [
        "egg",
        "eggs",
        "egg white",
        "egg whites",
        "egg yolk",
        "egg yolks",
        "mayonnaise",
        "meringue",
        "custard",
        "aioli",
    ],
}

ALLERGEN_KEYWORD_MAP: dict[str, list[str]] = {
    "peanuts": ["peanut", "peanuts", "peanut butter", "peanut oil"],
    "tree nuts": [
        "almond",
        "almonds",
        "walnut",
        "walnuts",
        "pecan",
        "pecans",
        "cashew",
        "cashews",
        "pistachio",
        "pistachios",
        "hazelnut",
        "hazelnuts",
        "macadamia",
        "pine nut",
        "pine nuts",
    ],
    "dairy": [
        "milk",
        "cream",
        "butter",
        "cheese",
        "yogurt",
        "whey",
        "ghee",
        "buttermilk",
        "heavy cream",
        "sour cream",
    ],
    "eggs": ["egg", "eggs", "egg white", "egg whites", "egg yolk", "mayonnaise"],
    "wheat": ["flour", "wheat", "bread", "breadcrumbs", "panko", "pasta", "semolina"],
    "soy": ["soy sauce", "tofu", "tempeh", "edamame", "soy milk", "soybean"],
    "shellfish": [
        "shrimp",
        "crab",
        "lobster",
        "crawfish",
        "prawn",
        "prawns",
        "scallop",
        "scallops",
        "clam",
        "clams",
        "mussel",
        "mussels",
        "oyster",
        "oysters",
    ],
    "fish": [
        "salmon",
        "tuna",
        "cod",
        "tilapia",
        "halibut",
        "anchovy",
        "anchovies",
        "sardine",
        "sardines",
        "fish sauce",
        "fish",
    ],
    "sesame": ["sesame", "sesame oil", "sesame seeds", "tahini"],
}


def check_ingredient_conflicts(
    ingredient_names: list[str],
    dietary_restrictions: list[str],
    allergies: list[str],
    disliked_ingredients: list[str],
) -> dict[str, list[str]]:
    """Check which ingredients conflict with user preferences.

    Returns a dict mapping ingredient name to a list of conflict reasons.
    Only ingredients with conflicts are included.
    """
    conflicts: dict[str, list[str]] = {}

    for name in ingredient_names:
        name_lower = name.lower()
        reasons: list[str] = []

        # Check dietary restrictions
        for restriction, keywords in DIETARY_INGREDIENT_MAP.items():
            if restriction in dietary_restrictions:
                for keyword in keywords:
                    if keyword in name_lower or name_lower in keyword:
                        reasons.append(f"conflicts with {restriction} diet")
                        break

        # Check allergies
        for allergen, keywords in ALLERGEN_KEYWORD_MAP.items():
            if allergen in allergies:
                for keyword in keywords:
                    if keyword in name_lower or name_lower in keyword:
                        reasons.append(f"contains allergen: {allergen}")
                        break

        # Check disliked ingredients
        for disliked in disliked_ingredients:
            if disliked.lower() in name_lower or name_lower in disliked.lower():
                reasons.append(f"disliked ingredient: {disliked}")

        if reasons:
            conflicts[name] = reasons

    return conflicts
