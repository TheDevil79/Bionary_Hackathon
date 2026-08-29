"""
EvidenceLens — Source Reliability Service (Phase 7).

Deterministic source classification and reliability scoring.

Tiers:
  Tier 1 (High Trust, 1.0):
    Government (.gov, .nic.in, gov.uk, etc.), international bodies (who.int, un.org),
    scientific journals (nature.com, science.org, nejm.org, nih.gov), major authoritative wires (reuters.com, apnews.com, bbc.com).
  Tier 2 (Generally Reliable, 0.8):
    Established journalism, encyclopedic & research portals (wikipedia.org, britannica.com, theguardian.com, nytimes.com).
  Tier 3 (Low Trust / Context Only, 0.4):
    General blogs, unknown news portals, aggregators, forums.
  Tier 4 (Reject, 0.0):
    Known spam, disinformation farms, or blocked domains.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

from app.core.config import settings

logger = logging.getLogger(__name__)

# Known trusted suffixes for Tier 1
_TIER_1_SUFFIXES = (
    ".gov",
    ".gov.uk",
    ".gov.au",
    ".gov.in",
    ".nic.in",
    ".mil",
    ".edu",
    ".ac.uk",
    ".edu.au",
    ".edu.in",
)

# Friendly publisher name overrides
_PUBLISHER_MAP: dict[str, str] = {
    "who.int": "World Health Organization",
    "un.org": "United Nations",
    "unesco.org": "UNESCO",
    "worldbank.org": "World Bank",
    "imf.org": "IMF",
    "wmo.int": "World Meteorological Organization",
    "nasa.gov": "NASA",
    "nih.gov": "National Institutes of Health (NIH)",
    "cdc.gov": "Centers for Disease Control and Prevention (CDC)",
    "nature.com": "Nature",
    "science.org": "Science",
    "nejm.org": "The New England Journal of Medicine",
    "thelancet.com": "The Lancet",
    "ncbi.nlm.nih.gov": "PubMed / NCBI",
    "pubmed.ncbi.nlm.nih.gov": "PubMed",
    "reuters.com": "Reuters",
    "apnews.com": "Associated Press (AP)",
    "bbc.com": "BBC News",
    "bbc.co.uk": "BBC News",
    "weather.gov": "National Weather Service",
    "imd.gov.in": "India Meteorological Department (IMD)",
    "mausam.imd.gov.in": "India Meteorological Department (IMD)",
    "wikipedia.org": "Wikipedia",
    "britannica.com": "Encyclopaedia Britannica",
    "theguardian.com": "The Guardian",
    "nytimes.com": "The New York Times",
    "washingtonpost.com": "The Washington Post",
    "wsj.com": "The Wall Street Journal",
    "bloomberg.com": "Bloomberg",
    "afp.com": "Agence France-Presse (AFP)",
    "aljazeera.com": "Al Jazeera",
    "sciencedirect.com": "ScienceDirect",
    "cell.com": "Cell Press",
    "pnas.org": "PNAS",
    "factcheck.org": "FactCheck.org",
    "snopes.com": "Snopes",
    "politifact.com": "PolitiFact",
    "fullfact.org": "Full Fact",
    "thehindu.com": "The Hindu",
    "indianexpress.com": "The Indian Express",
    "ndtv.com": "NDTV",
}


def extract_domain(url_or_domain: str) -> str:
    """Extract a normalized domain name from a URL or host string."""
    if not url_or_domain:
        return ""

    raw = url_or_domain.strip().lower()
    if "://" not in raw:
        raw = "http://" + raw

    try:
        parsed = urlparse(raw)
        hostname = parsed.hostname or ""
        # Strip leading www. and trailing dots
        hostname = re.sub(r"^www\d*\.", "", hostname)
        return hostname.strip(".")
    except Exception:
        return ""


def _matches_domain_or_parent(domain: str, candidate: str) -> bool:
    """Check if domain equals candidate or is a subdomain of candidate."""
    cand = candidate.lower().strip(".")
    dom = domain.lower().strip(".")
    if dom == cand:
        return True
    if dom.endswith("." + cand):
        return True
    return False


def classify_domain(url_or_domain: str) -> tuple[int, float, str]:
    """
    Classify domain into (tier: int, reliability_score: float, tier_label: str).

    Tier 1 = 1.0 (High Trust)
    Tier 2 = 0.8 (Generally Reliable)
    Tier 3 = 0.4 (Low Trust / Context Only)
    Tier 4 = 0.0 (Reject)
    """
    domain = extract_domain(url_or_domain)
    if not domain:
        return (4, 0.0, "TIER_4_REJECT")

    # 1. Check Tier 4 (Blocked / Spam)
    for blocked in settings.blocked_domains:
        if _matches_domain_or_parent(domain, blocked):
            return (4, 0.0, "TIER_4_REJECT")

    # 2. Check Tier 1 (High Trust Suffixes & Domains)
    for suffix in _TIER_1_SUFFIXES:
        if domain == suffix.strip(".") or domain.endswith(suffix):
            return (1, 1.0, "TIER_1_HIGH_TRUST")

    for trusted in settings.trusted_domains_tier_1:
        if _matches_domain_or_parent(domain, trusted):
            return (1, 1.0, "TIER_1_HIGH_TRUST")

    # 3. Check Tier 2 (Generally Reliable)
    for trusted in settings.trusted_domains_tier_2:
        if _matches_domain_or_parent(domain, trusted):
            return (2, 0.8, "TIER_2_GENERALLY_RELIABLE")

    # 4. Default: Tier 3 (Low Trust / Context Only)
    return (3, 0.4, "TIER_3_LOW_TRUST")


def derive_publisher(url_or_domain: str, provided_title: str | None = None) -> str:
    """Derive clean, authoritative publisher name from domain or metadata."""
    domain = extract_domain(url_or_domain)
    if not domain:
        return "Web Source"

    # Exact or parent match in publisher map
    for cand_domain, name in _PUBLISHER_MAP.items():
        if _matches_domain_or_parent(domain, cand_domain):
            return name

    # Suffix heuristics
    if domain.endswith(".gov") or ".gov." in domain or domain.endswith(".nic.in"):
        return f"Official Government ({domain})"
    if domain.endswith(".edu") or ".edu." in domain or domain.endswith(".ac.uk"):
        return f"Academic / Research ({domain})"

    # Clean domain name fallback
    parts = domain.split(".")
    if len(parts) >= 2:
        main_name = parts[-2]
        return main_name.capitalize()
    return domain


def compute_combined_score(relevance_score: float, source_reliability_score: float) -> float:
    """
    Combined evidence ranking score:
        combined_score = 0.65 * relevance_score + 0.35 * source_reliability_score
    Used exclusively for evidence ranking.
    """
    score = (0.65 * max(0.0, min(1.0, relevance_score))) + (0.35 * max(0.0, min(1.0, source_reliability_score)))
    return round(score, 4)
