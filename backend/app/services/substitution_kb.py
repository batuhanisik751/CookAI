"""Knowledge base lookup service for ingredient substitutions."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.substitution import SubstitutionKnowledgeBase

logger = logging.getLogger(__name__)


async def lookup_substitutions(
    db: AsyncSession,
    ingredient_name: str,
    category: str | None = None,
) -> list[SubstitutionKnowledgeBase]:
    """Look up known substitutions from the knowledge base."""
    stmt = select(SubstitutionKnowledgeBase).where(
        SubstitutionKnowledgeBase.original_ingredient.ilike(f"%{ingredient_name}%")
    )
    if category:
        stmt = stmt.where(SubstitutionKnowledgeBase.category == category)

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def lookup_bulk_substitutions(
    db: AsyncSession,
    ingredient_names: list[str],
    categories: list[str] | None = None,
) -> dict[str, list[SubstitutionKnowledgeBase]]:
    """Bulk lookup substitutions for all ingredients in a recipe.

    Returns a dict mapping ingredient name to matching KB entries.
    """
    results: dict[str, list[SubstitutionKnowledgeBase]] = {}

    for name in ingredient_names:
        stmt = select(SubstitutionKnowledgeBase).where(
            SubstitutionKnowledgeBase.original_ingredient.ilike(f"%{name}%")
        )
        if categories:
            stmt = stmt.where(SubstitutionKnowledgeBase.category.in_(categories))

        result = await db.execute(stmt)
        entries = list(result.scalars().all())
        if entries:
            results[name] = entries

    return results
