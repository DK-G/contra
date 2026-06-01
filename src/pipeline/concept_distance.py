"""Objective domain-distance scoring from OpenAlex concept tags.

Uses OpenAlex concept hierarchy levels (L0–L4) to compute a domain-distance signal
without requiring exact string matching or external embeddings.

KEY INSIGHT (spec §7 Step 9 / bynote survey, element B):
  L0/L1 concepts = BROAD DOMAIN (e.g. "Computer Science" / "Machine Learning")
  L2/L3/L4 concepts = SPECIFIC TOPIC

Wu-Palmer-inspired approximation (without the full taxonomy tree):
  domain_sim  = L01_jaccard * 0.7 + L234_recall * 0.3
  domain_dist = 1 - domain_sim

near_domain_signal(work, profile) -> True when L01 Jaccard > _NEAR_L01_THRESHOLD,
meaning the paper is in the SAME BROAD DOMAIN as the theme (myopia guard).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set

from src.core.models import Work

_NEAR_L01_THRESHOLD = 0.30   # Jaccard: >30% shared L0/L1 -> same domain (near-domain signal)
_PROFILE_MIN_LEVEL = 1       # L0 roots are near-universal; weight L1+ only
_PROFILE_SIZE = 20           # keep top-N concepts by aggregated weight


@dataclass
class ThemeProfile:
    """Aggregated concept fingerprint for the theme's near-field.

    l01  : L0/L1 concept names that appear in the near-field collection (broad domain set).
    l234 : Top-_PROFILE_SIZE L2-L4 concept names by weight (specific topic set).
    weights: name -> aggregated weight for L1+ concepts (frequency * relevance).
    """
    l01: Set[str] = field(default_factory=set)
    l234: Set[str] = field(default_factory=set)
    weights: Dict[str, float] = field(default_factory=dict)

    def is_empty(self) -> bool:
        return not self.l01 and not self.l234


def build_theme_profile(works: List[Work]) -> ThemeProfile:
    """Aggregate near-field papers' concept tags into a ThemeProfile.

    Collects ALL L0/L1 names (domain fingerprint) and the top-_PROFILE_SIZE L1+ names
    by aggregated weight (topic fingerprint).
    """
    l01: Set[str] = set()
    l234_all: Set[str] = set()
    weights: Dict[str, float] = {}

    for work in works:
        for tag in work.concept_tags:
            if not tag.name:
                continue
            if tag.level <= 1:
                l01.add(tag.name)
            else:
                l234_all.add(tag.name)
            if tag.level >= _PROFILE_MIN_LEVEL:
                weights[tag.name] = weights.get(tag.name, 0.0) + tag.score

    # Trim topic names to top-N by weight
    top = sorted(weights.items(), key=lambda kv: kv[1], reverse=True)[:_PROFILE_SIZE]
    top_names = {name for name, _ in top}
    l234 = l234_all & top_names

    return ThemeProfile(l01=l01, l234=l234, weights=dict(top))



def near_domain_signal(work: Work, profile: ThemeProfile) -> bool:
    """True if the work is in the SAME BROAD DOMAIN as the theme (L0/L1 Jaccard > threshold).

    Used in classify.py to cap mechanism_dist for same-domain papers, preventing
    false-serendipity where the LLM scores mechanism as "different" but the paper is
    objectively in the theme's own field.
    """
    if profile.is_empty() or not profile.l01:
        return False
    work_l01 = {tag.name for tag in work.concept_tags if tag.level <= 1 and tag.name}
    union = work_l01 | profile.l01
    if not union:
        return False
    return (len(work_l01 & profile.l01) / len(union)) > _NEAR_L01_THRESHOLD


__all__ = [
    "ThemeProfile",
    "build_theme_profile",
    "near_domain_signal",
]
