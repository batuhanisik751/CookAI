"""Seed the substitution knowledge base with common ingredient substitutions.

Usage: cd backend && python -m scripts.seed_substitutions
"""

import logging
import sys
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings  # noqa: E402
from app.models.base import Base  # noqa: E402
from app.models.substitution import SubstitutionKnowledgeBase  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SEED_DATA = [
    # --- Dairy-free ---
    {
        "original_ingredient": "butter",
        "substitute_ingredient": "coconut oil",
        "ratio": "1:1",
        "category": "dairy-free",
        "flavor_similarity": "medium",
        "notes": "Works well in baking; adds slight coconut flavor",
        "is_common_pantry": True,
    },
    {
        "original_ingredient": "butter",
        "substitute_ingredient": "olive oil",
        "ratio": "3/4 cup per 1 cup butter",
        "category": "dairy-free",
        "flavor_similarity": "low",
        "notes": "Best for savory dishes; not ideal for baking",
        "is_common_pantry": True,
    },
    {
        "original_ingredient": "butter",
        "substitute_ingredient": "vegan butter",
        "ratio": "1:1",
        "category": "dairy-free",
        "flavor_similarity": "high",
        "notes": "Direct swap in any recipe",
        "is_common_pantry": False,
    },
    {
        "original_ingredient": "heavy cream",
        "substitute_ingredient": "coconut cream",
        "ratio": "1:1",
        "category": "dairy-free",
        "flavor_similarity": "medium",
        "notes": "Rich and thick; adds coconut flavor",
        "is_common_pantry": False,
    },
    {
        "original_ingredient": "heavy cream",
        "substitute_ingredient": "cashew cream",
        "ratio": "1:1",
        "category": "dairy-free",
        "flavor_similarity": "high",
        "notes": "Blend soaked cashews with water; neutral flavor",
        "is_common_pantry": False,
    },
    {
        "original_ingredient": "milk",
        "substitute_ingredient": "oat milk",
        "ratio": "1:1",
        "category": "dairy-free",
        "flavor_similarity": "high",
        "notes": "Creamy texture; works in baking and cooking",
        "is_common_pantry": True,
    },
    {
        "original_ingredient": "milk",
        "substitute_ingredient": "almond milk",
        "ratio": "1:1",
        "category": "dairy-free",
        "flavor_similarity": "medium",
        "notes": "Thinner than dairy milk; mild nutty flavor",
        "is_common_pantry": True,
    },
    {
        "original_ingredient": "milk",
        "substitute_ingredient": "soy milk",
        "ratio": "1:1",
        "category": "dairy-free",
        "flavor_similarity": "high",
        "notes": "Closest protein content to dairy milk",
        "is_common_pantry": True,
    },
    {
        "original_ingredient": "cream cheese",
        "substitute_ingredient": "cashew cream cheese",
        "ratio": "1:1",
        "category": "dairy-free",
        "flavor_similarity": "high",
        "notes": "Available at most grocery stores",
        "is_common_pantry": False,
    },
    {
        "original_ingredient": "sour cream",
        "substitute_ingredient": "coconut yogurt",
        "ratio": "1:1",
        "category": "dairy-free",
        "flavor_similarity": "medium",
        "notes": "Add a squeeze of lemon for tanginess",
        "is_common_pantry": False,
    },
    {
        "original_ingredient": "parmesan",
        "substitute_ingredient": "nutritional yeast",
        "ratio": "2 tbsp per 1/4 cup parmesan",
        "category": "dairy-free",
        "flavor_similarity": "medium",
        "notes": "Provides umami/cheesy flavor; won't melt",
        "is_common_pantry": False,
    },
    {
        "original_ingredient": "yogurt",
        "substitute_ingredient": "coconut yogurt",
        "ratio": "1:1",
        "category": "dairy-free",
        "flavor_similarity": "medium",
        "notes": "Works in marinades, dressings, and baking",
        "is_common_pantry": False,
    },
    {
        "original_ingredient": "buttermilk",
        "substitute_ingredient": "oat milk with lemon juice",
        "ratio": "1 cup oat milk + 1 tbsp lemon juice",
        "category": "dairy-free",
        "flavor_similarity": "high",
        "notes": "Let sit 10 minutes before using",
        "is_common_pantry": True,
    },
    {
        "original_ingredient": "cheese",
        "substitute_ingredient": "vegan cheese",
        "ratio": "1:1",
        "category": "dairy-free",
        "flavor_similarity": "medium",
        "notes": "Melting properties vary by brand",
        "is_common_pantry": False,
    },
    # --- Egg-free ---
    {
        "original_ingredient": "eggs",
        "substitute_ingredient": "flax eggs",
        "ratio": "1 tbsp ground flax + 3 tbsp water per egg",
        "category": "egg-free",
        "flavor_similarity": "medium",
        "notes": "Best for binding in baking; let gel 5 minutes",
        "is_common_pantry": False,
    },
    {
        "original_ingredient": "eggs",
        "substitute_ingredient": "chia eggs",
        "ratio": "1 tbsp chia seeds + 3 tbsp water per egg",
        "category": "egg-free",
        "flavor_similarity": "medium",
        "notes": "Good binding; visible seeds in final product",
        "is_common_pantry": False,
    },
    {
        "original_ingredient": "eggs",
        "substitute_ingredient": "applesauce",
        "ratio": "1/4 cup per egg",
        "category": "egg-free",
        "flavor_similarity": "low",
        "notes": "Adds moisture and mild sweetness; best in sweet baking",
        "is_common_pantry": True,
    },
    {
        "original_ingredient": "eggs",
        "substitute_ingredient": "mashed banana",
        "ratio": "1/4 cup per egg",
        "category": "egg-free",
        "flavor_similarity": "low",
        "notes": "Adds banana flavor; best in pancakes, muffins, quick breads",
        "is_common_pantry": True,
    },
    {
        "original_ingredient": "eggs",
        "substitute_ingredient": "silken tofu",
        "ratio": "1/4 cup blended per egg",
        "category": "egg-free",
        "flavor_similarity": "medium",
        "notes": "Neutral flavor; good for dense baked goods and quiches",
        "is_common_pantry": False,
    },
    {
        "original_ingredient": "egg whites",
        "substitute_ingredient": "aquafaba",
        "ratio": "3 tbsp per egg white",
        "category": "egg-free",
        "flavor_similarity": "high",
        "notes": "Liquid from canned chickpeas; whips like egg whites",
        "is_common_pantry": True,
    },
    {
        "original_ingredient": "eggs",
        "substitute_ingredient": "baking soda and vinegar",
        "ratio": "1 tsp baking soda + 1 tbsp vinegar per egg",
        "category": "egg-free",
        "flavor_similarity": "medium",
        "notes": "For leavening only; use in cakes and quick breads",
        "is_common_pantry": True,
    },
    {
        "original_ingredient": "mayonnaise",
        "substitute_ingredient": "vegan mayonnaise",
        "ratio": "1:1",
        "category": "egg-free",
        "flavor_similarity": "high",
        "notes": "Direct swap; many brands available",
        "is_common_pantry": False,
    },
    # --- Gluten-free ---
    {
        "original_ingredient": "all-purpose flour",
        "substitute_ingredient": "gluten-free flour blend",
        "ratio": "1:1",
        "category": "gluten-free",
        "flavor_similarity": "high",
        "notes": "Look for blends with xanthan gum included",
        "is_common_pantry": False,
    },
    {
        "original_ingredient": "all-purpose flour",
        "substitute_ingredient": "almond flour",
        "ratio": "1:1 but add extra binding",
        "category": "gluten-free",
        "flavor_similarity": "medium",
        "notes": "Denser result; works best in cookies and cakes",
        "is_common_pantry": False,
    },
    {
        "original_ingredient": "all-purpose flour",
        "substitute_ingredient": "oat flour",
        "ratio": "1:1",
        "category": "gluten-free",
        "flavor_similarity": "high",
        "notes": "Use certified GF oats; slightly nutty flavor",
        "is_common_pantry": False,
    },
    {
        "original_ingredient": "all-purpose flour",
        "substitute_ingredient": "rice flour",
        "ratio": "3/4 cup per 1 cup AP flour",
        "category": "gluten-free",
        "flavor_similarity": "high",
        "notes": "Lighter texture; combine with tapioca starch for best results",
        "is_common_pantry": False,
    },
    {
        "original_ingredient": "breadcrumbs",
        "substitute_ingredient": "gluten-free breadcrumbs",
        "ratio": "1:1",
        "category": "gluten-free",
        "flavor_similarity": "high",
        "notes": "Available pre-made or make from GF bread",
        "is_common_pantry": False,
    },
    {
        "original_ingredient": "breadcrumbs",
        "substitute_ingredient": "crushed rice crackers",
        "ratio": "1:1",
        "category": "gluten-free",
        "flavor_similarity": "medium",
        "notes": "Crispy coating; slightly different texture",
        "is_common_pantry": False,
    },
    {
        "original_ingredient": "breadcrumbs",
        "substitute_ingredient": "almond meal",
        "ratio": "1:1",
        "category": "gluten-free",
        "flavor_similarity": "medium",
        "notes": "Adds nutty flavor; browns nicely",
        "is_common_pantry": False,
    },
    {
        "original_ingredient": "soy sauce",
        "substitute_ingredient": "tamari",
        "ratio": "1:1",
        "category": "gluten-free",
        "flavor_similarity": "high",
        "notes": "Check label for certified GF; nearly identical flavor",
        "is_common_pantry": True,
    },
    {
        "original_ingredient": "soy sauce",
        "substitute_ingredient": "coconut aminos",
        "ratio": "1:1",
        "category": "gluten-free",
        "flavor_similarity": "medium",
        "notes": "Slightly sweeter and milder; lower sodium",
        "is_common_pantry": False,
    },
    {
        "original_ingredient": "pasta",
        "substitute_ingredient": "rice noodles",
        "ratio": "1:1 by weight",
        "category": "gluten-free",
        "flavor_similarity": "medium",
        "notes": "Different texture; cook according to package directions",
        "is_common_pantry": False,
    },
    {
        "original_ingredient": "pasta",
        "substitute_ingredient": "gluten-free pasta",
        "ratio": "1:1",
        "category": "gluten-free",
        "flavor_similarity": "high",
        "notes": "Made from rice, corn, or quinoa flour",
        "is_common_pantry": False,
    },
    # --- Nut-free ---
    {
        "original_ingredient": "almond flour",
        "substitute_ingredient": "oat flour",
        "ratio": "1:1",
        "category": "nut-free",
        "flavor_similarity": "medium",
        "notes": "Lighter texture; slightly different flavor",
        "is_common_pantry": False,
    },
    {
        "original_ingredient": "almond flour",
        "substitute_ingredient": "sunflower seed flour",
        "ratio": "1:1",
        "category": "nut-free",
        "flavor_similarity": "medium",
        "notes": "May turn green with baking soda; add lemon juice to prevent",
        "is_common_pantry": False,
    },
    {
        "original_ingredient": "peanut butter",
        "substitute_ingredient": "sunflower seed butter",
        "ratio": "1:1",
        "category": "nut-free",
        "flavor_similarity": "medium",
        "notes": "Similar texture; slightly different taste",
        "is_common_pantry": False,
    },
    {
        "original_ingredient": "peanut butter",
        "substitute_ingredient": "tahini",
        "ratio": "1:1",
        "category": "nut-free",
        "flavor_similarity": "medium",
        "notes": "Sesame-based; richer flavor, slightly bitter",
        "is_common_pantry": True,
    },
    {
        "original_ingredient": "almond milk",
        "substitute_ingredient": "oat milk",
        "ratio": "1:1",
        "category": "nut-free",
        "flavor_similarity": "high",
        "notes": "Creamy and neutral; widely available",
        "is_common_pantry": True,
    },
    {
        "original_ingredient": "almond milk",
        "substitute_ingredient": "soy milk",
        "ratio": "1:1",
        "category": "nut-free",
        "flavor_similarity": "high",
        "notes": "Higher protein than most plant milks",
        "is_common_pantry": True,
    },
    # --- Vegan ---
    {
        "original_ingredient": "honey",
        "substitute_ingredient": "maple syrup",
        "ratio": "1:1",
        "category": "vegan",
        "flavor_similarity": "medium",
        "notes": "Distinct maple flavor; works in most recipes",
        "is_common_pantry": True,
    },
    {
        "original_ingredient": "honey",
        "substitute_ingredient": "agave nectar",
        "ratio": "2/3 cup per 1 cup honey",
        "category": "vegan",
        "flavor_similarity": "high",
        "notes": "Milder flavor; slightly thinner consistency",
        "is_common_pantry": False,
    },
    {
        "original_ingredient": "gelatin",
        "substitute_ingredient": "agar-agar",
        "ratio": "1 tsp agar per 1 tsp gelatin",
        "category": "vegan",
        "flavor_similarity": "high",
        "notes": "Sets firmer; dissolve in hot liquid first",
        "is_common_pantry": False,
    },
    {
        "original_ingredient": "fish sauce",
        "substitute_ingredient": "soy sauce with seaweed",
        "ratio": "1:1 soy sauce + pinch of seaweed",
        "category": "vegan",
        "flavor_similarity": "medium",
        "notes": "Provides umami; slightly different flavor profile",
        "is_common_pantry": True,
    },
    {
        "original_ingredient": "oyster sauce",
        "substitute_ingredient": "mushroom oyster sauce",
        "ratio": "1:1",
        "category": "vegan",
        "flavor_similarity": "high",
        "notes": "Widely available; very similar flavor",
        "is_common_pantry": False,
    },
    {
        "original_ingredient": "chicken broth",
        "substitute_ingredient": "vegetable broth",
        "ratio": "1:1",
        "category": "vegan",
        "flavor_similarity": "medium",
        "notes": "Lighter flavor; add soy sauce or miso for depth",
        "is_common_pantry": True,
    },
    {
        "original_ingredient": "beef broth",
        "substitute_ingredient": "mushroom broth",
        "ratio": "1:1",
        "category": "vegan",
        "flavor_similarity": "medium",
        "notes": "Rich umami flavor; closest to beef broth",
        "is_common_pantry": False,
    },
    {
        "original_ingredient": "lard",
        "substitute_ingredient": "vegetable shortening",
        "ratio": "1:1",
        "category": "vegan",
        "flavor_similarity": "medium",
        "notes": "Works for pie crusts and frying; different flavor",
        "is_common_pantry": True,
    },
    {
        "original_ingredient": "whipped cream",
        "substitute_ingredient": "coconut whipped cream",
        "ratio": "1:1",
        "category": "vegan",
        "flavor_similarity": "medium",
        "notes": "Chill coconut cream overnight; whip with sugar",
        "is_common_pantry": False,
    },
    {
        "original_ingredient": "anchovies",
        "substitute_ingredient": "capers with seaweed",
        "ratio": "1 tbsp capers per 2 anchovy fillets",
        "category": "vegan",
        "flavor_similarity": "medium",
        "notes": "Provides brininess and umami",
        "is_common_pantry": False,
    },
    # --- General / availability ---
    {
        "original_ingredient": "buttermilk",
        "substitute_ingredient": "milk with vinegar",
        "ratio": "1 cup milk + 1 tbsp white vinegar",
        "category": "general",
        "flavor_similarity": "high",
        "notes": "Let sit 10 minutes to curdle; works in all recipes",
        "is_common_pantry": True,
    },
    {
        "original_ingredient": "buttermilk",
        "substitute_ingredient": "milk with lemon juice",
        "ratio": "1 cup milk + 1 tbsp lemon juice",
        "category": "general",
        "flavor_similarity": "high",
        "notes": "Let sit 10 minutes; slightly more citrus flavor",
        "is_common_pantry": True,
    },
    {
        "original_ingredient": "wine",
        "substitute_ingredient": "broth with vinegar",
        "ratio": "1 cup broth + 1 tbsp vinegar per 1 cup wine",
        "category": "general",
        "flavor_similarity": "medium",
        "notes": "Use chicken broth for white wine, beef broth for red",
        "is_common_pantry": True,
    },
    {
        "original_ingredient": "wine",
        "substitute_ingredient": "grape juice",
        "ratio": "1:1",
        "category": "general",
        "flavor_similarity": "medium",
        "notes": "Sweeter; reduce other sugars in recipe",
        "is_common_pantry": True,
    },
    {
        "original_ingredient": "brown sugar",
        "substitute_ingredient": "white sugar with molasses",
        "ratio": "1 cup white sugar + 1 tbsp molasses",
        "category": "general",
        "flavor_similarity": "high",
        "notes": "Mix well; identical result to brown sugar",
        "is_common_pantry": True,
    },
    {
        "original_ingredient": "cornstarch",
        "substitute_ingredient": "arrowroot powder",
        "ratio": "1:1",
        "category": "general",
        "flavor_similarity": "high",
        "notes": "Clear finish; don't overheat or it thins out",
        "is_common_pantry": False,
    },
    {
        "original_ingredient": "cornstarch",
        "substitute_ingredient": "tapioca starch",
        "ratio": "2 tbsp tapioca per 1 tbsp cornstarch",
        "category": "general",
        "flavor_similarity": "high",
        "notes": "Slightly chewier texture; good for pies",
        "is_common_pantry": False,
    },
    {
        "original_ingredient": "self-rising flour",
        "substitute_ingredient": "all-purpose flour with baking powder",
        "ratio": "1 cup AP flour + 1.5 tsp baking powder + 1/4 tsp salt",
        "category": "general",
        "flavor_similarity": "high",
        "notes": "Identical result; most common substitution",
        "is_common_pantry": True,
    },
    {
        "original_ingredient": "cake flour",
        "substitute_ingredient": "all-purpose flour with cornstarch",
        "ratio": "1 cup AP flour minus 2 tbsp + 2 tbsp cornstarch",
        "category": "general",
        "flavor_similarity": "high",
        "notes": "Sift together twice for best results",
        "is_common_pantry": True,
    },
    {
        "original_ingredient": "fresh herbs",
        "substitute_ingredient": "dried herbs",
        "ratio": "1 tsp dried per 1 tbsp fresh",
        "category": "general",
        "flavor_similarity": "medium",
        "notes": "Add earlier in cooking; more concentrated flavor",
        "is_common_pantry": True,
    },
    {
        "original_ingredient": "lemon juice",
        "substitute_ingredient": "lime juice",
        "ratio": "1:1",
        "category": "general",
        "flavor_similarity": "high",
        "notes": "Slightly different citrus flavor; works in most recipes",
        "is_common_pantry": True,
    },
    {
        "original_ingredient": "white sugar",
        "substitute_ingredient": "honey",
        "ratio": "3/4 cup honey per 1 cup sugar",
        "category": "general",
        "flavor_similarity": "medium",
        "notes": "Reduce other liquids by 1/4 cup; lower oven temp by 25°F",
        "is_common_pantry": True,
    },
    {
        "original_ingredient": "balsamic vinegar",
        "substitute_ingredient": "red wine vinegar with sugar",
        "ratio": "1 tbsp red wine vinegar + 1/2 tsp sugar",
        "category": "general",
        "flavor_similarity": "medium",
        "notes": "Less complex flavor; works for dressings and marinades",
        "is_common_pantry": True,
    },
    {
        "original_ingredient": "rice vinegar",
        "substitute_ingredient": "apple cider vinegar",
        "ratio": "1:1",
        "category": "general",
        "flavor_similarity": "medium",
        "notes": "Slightly stronger; add pinch of sugar to mellow",
        "is_common_pantry": True,
    },
    {
        "original_ingredient": "half-and-half",
        "substitute_ingredient": "milk with butter",
        "ratio": "3/4 cup milk + 1/4 cup melted butter",
        "category": "general",
        "flavor_similarity": "high",
        "notes": "Good for sauces and soups; not ideal for whipping",
        "is_common_pantry": True,
    },
]


def seed_substitutions() -> None:
    """Seed the substitution knowledge base. Idempotent — skips existing entries."""
    engine = create_engine(settings.database_url_sync)
    Base.metadata.create_all(engine, checkfirst=True)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()

    added = 0
    skipped = 0

    try:
        for entry in SEED_DATA:
            existing = session.execute(
                select(SubstitutionKnowledgeBase).where(
                    SubstitutionKnowledgeBase.original_ingredient
                    == entry["original_ingredient"],
                    SubstitutionKnowledgeBase.substitute_ingredient
                    == entry["substitute_ingredient"],
                )
            ).scalar_one_or_none()

            if existing:
                skipped += 1
                continue

            row = SubstitutionKnowledgeBase(**entry)
            session.add(row)
            added += 1

        session.commit()
        logger.info(
            "Seed complete: %d added, %d skipped (already exist)", added, skipped
        )
    except Exception:
        session.rollback()
        logger.exception("Seed failed")
        raise
    finally:
        session.close()
        engine.dispose()


if __name__ == "__main__":
    seed_substitutions()
