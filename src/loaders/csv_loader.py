"""
CSV data loader for importing existing researched grants.

Loads the manually-researched grant data from CSV files in the research/
directory and converts them into Grant objects for the pipeline.
Handles the various CSV formats used across our research files.
"""

import csv
import logging
import os
import re
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from src.models.grant import Grant, GrantStatus, GrantType, Priority

logger = logging.getLogger(__name__)

# Base path for research data
RESEARCH_DIR = Path(__file__).parent.parent.parent / "research"


def parse_amount(amount_text: str) -> tuple[float, float, str]:
    """
    Parse an amount string into min, max, and display text.

    Handles formats like:
        "Up to $30,000/yr (2 years)"
        "$75,000 - $115,000"
        "$250 - $5,000"
        "Varies"
        "In-kind (food/beverage)"

    Returns:
        Tuple of (min_amount, max_amount, display_text)
    """
    if not amount_text or amount_text.strip().lower() in ("varies", "tbd", "n/a", ""):
        return 0.0, 0.0, amount_text.strip() if amount_text else "Varies"

    # Clean the text
    clean = amount_text.strip()

    # Find all dollar amounts in the string
    amounts = re.findall(r'\$[\d,]+(?:\.\d{2})?', clean)
    parsed_amounts = []
    for amt in amounts:
        try:
            value = float(amt.replace('$', '').replace(',', ''))
            parsed_amounts.append(value)
        except ValueError:
            continue

    if len(parsed_amounts) >= 2:
        return min(parsed_amounts), max(parsed_amounts), clean
    elif len(parsed_amounts) == 1:
        if "up to" in clean.lower():
            return 0.0, parsed_amounts[0], clean
        return parsed_amounts[0], parsed_amounts[0], clean

    return 0.0, 0.0, clean


def parse_deadline(deadline_text: str, reference_year: int = 2026) -> Optional[date]:
    """
    Parse a deadline string into a date object.

    Handles formats like:
        "Feb 18 2026"
        "Mar 1 2026"
        "Apr 15 2026"
        "Rolling"
        "Check website"
        "2026 app open now"
        "Mar 10-31 2026"

    Returns:
        date object or None if unparseable/rolling
    """
    if not deadline_text:
        return None

    text = deadline_text.strip().lower()

    # Skip non-date deadlines
    skip_patterns = [
        "rolling", "check", "tbd", "varies", "invitation",
        "nominated", "contact", "open", "ongoing"
    ]
    if any(pattern in text for pattern in skip_patterns):
        return None

    # Try direct date parsing with common formats
    date_formats = [
        "%b %d %Y",       # "Feb 18 2026"
        "%B %d %Y",       # "February 18 2026"
        "%b %d, %Y",      # "Feb 18, 2026"
        "%B %d, %Y",      # "February 18, 2026"
        "%m/%d/%Y",       # "02/18/2026"
        "%Y-%m-%d",       # "2026-02-18"
    ]

    # Clean up common patterns before parsing
    clean = deadline_text.strip()
    # Handle "Mar 10-31 2026" -> take the last date
    range_match = re.search(r'(\w+)\s+\d+-(\d+)\s+(\d{4})', clean)
    if range_match:
        clean = f"{range_match.group(1)} {range_match.group(2)} {range_match.group(3)}"

    # Handle "Apr 2026" (month + year only) -> use last day of month
    month_year = re.match(r'^(\w+)\s+(\d{4})$', clean)
    if month_year:
        try:
            dt = datetime.strptime(f"{month_year.group(1)} 1 {month_year.group(2)}", "%b %d %Y")
            # Get last day of month
            if dt.month == 12:
                last_day = date(dt.year + 1, 1, 1)
            else:
                last_day = date(dt.year, dt.month + 1, 1)
            from datetime import timedelta
            return last_day - timedelta(days=1)
        except ValueError:
            pass

    for fmt in date_formats:
        try:
            return datetime.strptime(clean, fmt).date()
        except ValueError:
            continue

    # Try extracting a date from within a longer string
    date_pattern = re.search(
        r'(\w{3,9})\s+(\d{1,2}),?\s+(\d{4})', deadline_text
    )
    if date_pattern:
        try:
            return datetime.strptime(
                f"{date_pattern.group(1)} {date_pattern.group(2)} {date_pattern.group(3)}",
                "%b %d %Y"
            ).date()
        except ValueError:
            try:
                return datetime.strptime(
                    f"{date_pattern.group(1)} {date_pattern.group(2)} {date_pattern.group(3)}",
                    "%B %d %Y"
                ).date()
            except ValueError:
                pass

    logger.debug(f"Could not parse deadline: '{deadline_text}'")
    return None


def classify_grant_type(type_text: str, name: str = "") -> GrantType:
    """Map a grant type string to a GrantType enum."""
    if not type_text:
        return GrantType.UNKNOWN

    text = type_text.lower()
    combined = f"{text} {name.lower()}"

    if "federal" in text or "government" in text:
        return GrantType.FEDERAL_GRANT
    if "state" in text:
        return GrantType.STATE_GRANT
    if "mini" in combined:
        return GrantType.MINI_GRANT
    if "foundation" in text:
        return GrantType.FOUNDATION_GRANT
    if "corporate" in text or "retail" in text or "bank" in text or "utility" in text:
        return GrantType.CORPORATE_GRANT
    if "community" in text or "credit union" in text:
        return GrantType.COMMUNITY_GRANT
    if "in-kind" in text or "donation" in text or "in kind" in text:
        return GrantType.IN_KIND
    if "sponsorship" in text:
        return GrantType.SPONSORSHIP
    if "fundraiser" in text or "restaurant" in text:
        return GrantType.FUNDRAISER

    return GrantType.UNKNOWN


def classify_status(status_text: str, category_text: str = "") -> GrantStatus:
    """Map a status string to a GrantStatus enum."""
    combined = f"{status_text} {category_text}".lower()

    if "apply now" in combined or "open" in combined:
        return GrantStatus.OPEN
    if "closing" in combined or "urgent" in combined:
        return GrantStatus.CLOSING_SOON
    if "upcoming" in combined or "opens soon" in combined:
        return GrantStatus.UPCOMING
    if "closed" in combined or "expired" in combined:
        return GrantStatus.CLOSED
    if "rolling" in combined:
        return GrantStatus.ROLLING
    if "monitor" in combined:
        return GrantStatus.MONITOR

    return GrantStatus.UNKNOWN


def classify_priority(category: str, status_text: str) -> Priority:
    """Determine priority from category and status text."""
    combined = f"{category} {status_text}".lower()

    if "urgent" in combined:
        return Priority.URGENT
    if "high" in combined:
        return Priority.HIGH
    if "medium" in combined or "fundraiser" in combined:
        return Priority.MEDIUM
    if "low" in combined:
        return Priority.LOW
    if "monitor" in combined:
        return Priority.MONITOR

    return Priority.MEDIUM


def load_all_grants_csv(filepath: Optional[str] = None) -> list[Grant]:
    """
    Load the master grant list (Delta_Rising_ALL_Grants_Feb2026.csv).

    This CSV has columns:
    Category, Grant Name, Amount, Deadline, Status, Type, Focus Area,
    Geographic Scope, Eligibility Notes, How to Apply, URL

    Returns:
        List of Grant objects
    """
    if filepath is None:
        filepath = str(RESEARCH_DIR / "Delta_Rising_ALL_Grants_Feb2026.csv")

    grants = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                amount_min, amount_max, amount_text = parse_amount(
                    row.get("Amount", "")
                )
                deadline = parse_deadline(row.get("Deadline", ""))
                status = classify_status(
                    row.get("Status", ""), row.get("Category", "")
                )
                grant_type = classify_grant_type(
                    row.get("Type", ""), row.get("Grant Name", "")
                )

                grant = Grant(
                    name=row.get("Grant Name", "").strip(),
                    source="research_csv",
                    url=row.get("URL", "").strip(),
                    amount_min=amount_min,
                    amount_max=amount_max,
                    amount_text=amount_text,
                    deadline=deadline,
                    deadline_text=row.get("Deadline", "").strip(),
                    status=status,
                    grant_type=grant_type,
                    description=row.get("Focus Area", "").strip(),
                    focus_areas=[
                        fa.strip()
                        for fa in row.get("Focus Area", "").split("+")
                        if fa.strip()
                    ],
                    geographic_scope=row.get("Geographic Scope", "").strip(),
                    eligibility_notes=row.get("Eligibility Notes", "").strip(),
                    how_to_apply=row.get("How to Apply", "").strip(),
                    funder=row.get("Grant Name", "").split("—")[0].strip()
                    if "—" in row.get("Grant Name", "")
                    else row.get("Grant Name", "").strip(),
                    priority=classify_priority(
                        row.get("Category", ""), row.get("Status", "")
                    ),
                )
                grants.append(grant)

        logger.info(f"Loaded {len(grants)} grants from {filepath}")
    except FileNotFoundError:
        logger.error(f"CSV file not found: {filepath}")
    except Exception as e:
        logger.error(f"Error loading CSV {filepath}: {e}")

    return grants


def load_mini_grants_csv(filepath: Optional[str] = None) -> list[Grant]:
    """
    Load the mini-grants list (MINI_GRANTS_ONLY.csv).

    This CSV has columns:
    Priority, Grant/Sponsor Name, Amount, Type, Deadline, Effort Level,
    How to Apply, Location, Eligibility, URL, Notes, Assigned To, Status,
    Date Applied, Follow-Up

    Returns:
        List of Grant objects
    """
    if filepath is None:
        filepath = str(RESEARCH_DIR / "MINI_GRANTS_ONLY.csv")

    grants = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                amount_min, amount_max, amount_text = parse_amount(
                    row.get("Amount", "")
                )
                deadline = parse_deadline(row.get("Deadline", ""))

                # Map type column
                type_text = row.get("Type", "")
                if type_text.upper() == "CASH":
                    grant_type = GrantType.MINI_GRANT
                elif type_text.upper() in ("IN-KIND", "IN_KIND"):
                    grant_type = GrantType.IN_KIND
                elif "GIFT" in type_text.upper():
                    grant_type = GrantType.IN_KIND
                else:
                    grant_type = classify_grant_type(type_text)

                # Map priority number to Priority enum
                priority_val = row.get("Priority", "")
                try:
                    p_num = int(priority_val)
                    if p_num <= 5:
                        priority = Priority.HIGH
                    elif p_num <= 12:
                        priority = Priority.MEDIUM
                    else:
                        priority = Priority.LOW
                except (ValueError, TypeError):
                    priority = Priority.MEDIUM

                grant = Grant(
                    name=row.get("Grant/Sponsor Name", "").strip(),
                    source="mini_grants_csv",
                    url=row.get("URL", "").strip(),
                    amount_min=amount_min,
                    amount_max=amount_max,
                    amount_text=amount_text,
                    deadline=deadline,
                    deadline_text=row.get("Deadline", "").strip(),
                    status=GrantStatus.OPEN,
                    grant_type=grant_type,
                    description=row.get("Notes", "").strip(),
                    focus_areas=[],
                    geographic_scope=row.get("Location", "").strip(),
                    eligibility_notes=row.get("Eligibility", "").strip(),
                    how_to_apply=row.get("How to Apply", "").strip(),
                    funder=row.get("Grant/Sponsor Name", "").split("(")[0].strip(),
                    priority=priority,
                )
                grants.append(grant)

        logger.info(f"Loaded {len(grants)} mini-grants from {filepath}")
    except FileNotFoundError:
        logger.error(f"CSV file not found: {filepath}")
    except Exception as e:
        logger.error(f"Error loading CSV {filepath}: {e}")

    return grants


def load_active_grants_csv(filepath: Optional[str] = None) -> list[Grant]:
    """
    Load the active grants for Sarah (FOR_SARAH_Active_Grants_Feb2026.csv).

    This CSV has columns:
    Priority, Grant Name, Amount, Deadline, Cash or In-Kind, Focus Area,
    Location Restriction, Key Eligibility, How to Apply, Link, Notes,
    Assigned To, Status, Date Applied, Follow-Up Notes

    Returns:
        List of Grant objects
    """
    if filepath is None:
        filepath = str(RESEARCH_DIR / "FOR_SARAH_Active_Grants_Feb2026.csv")

    grants = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                amount_min, amount_max, amount_text = parse_amount(
                    row.get("Amount", "")
                )
                deadline = parse_deadline(row.get("Deadline", ""))
                priority = classify_priority(
                    row.get("Priority", ""), row.get("Status", "")
                )

                cash_type = row.get("Cash or In-Kind", "").upper()
                if "CASH" in cash_type:
                    grant_type = GrantType.FOUNDATION_GRANT
                elif "IN-KIND" in cash_type or "IN KIND" in cash_type:
                    grant_type = GrantType.IN_KIND
                else:
                    grant_type = GrantType.UNKNOWN

                grant = Grant(
                    name=row.get("Grant Name", "").strip(),
                    source="active_grants_csv",
                    url=row.get("Link", "").strip(),
                    amount_min=amount_min,
                    amount_max=amount_max,
                    amount_text=amount_text,
                    deadline=deadline,
                    deadline_text=row.get("Deadline", "").strip(),
                    status=GrantStatus.OPEN,
                    grant_type=grant_type,
                    description=row.get("Focus Area", "").strip(),
                    focus_areas=[
                        fa.strip()
                        for fa in row.get("Focus Area", "").split(",")
                        if fa.strip()
                    ],
                    geographic_scope=row.get("Location Restriction", "").strip(),
                    eligibility_notes=row.get("Key Eligibility", "").strip(),
                    how_to_apply=row.get("How to Apply", "").strip(),
                    funder=row.get("Grant Name", "").split("—")[0].strip()
                    if "—" in row.get("Grant Name", "")
                    else row.get("Grant Name", "").strip(),
                    priority=priority,
                )
                grants.append(grant)

        logger.info(f"Loaded {len(grants)} active grants from {filepath}")
    except FileNotFoundError:
        logger.error(f"CSV file not found: {filepath}")
    except Exception as e:
        logger.error(f"Error loading CSV {filepath}: {e}")

    return grants


def load_all_research_data() -> list[Grant]:
    """
    Load grants from all research CSV files and merge them.

    Prioritizes the master list (ALL_Grants) and supplements with
    data from the mini-grants and active grants files. Deduplication
    is handled downstream by the pipeline processor.

    Returns:
        Combined list of Grant objects from all CSV sources
    """
    all_grants = []

    # Primary source: master grant list
    master = load_all_grants_csv()
    all_grants.extend(master)
    logger.info(f"Master list: {len(master)} grants")

    # Secondary: mini-grants (may overlap with master)
    mini = load_mini_grants_csv()
    all_grants.extend(mini)
    logger.info(f"Mini-grants: {len(mini)} grants")

    # Tertiary: active grants for Sarah (may overlap)
    active = load_active_grants_csv()
    all_grants.extend(active)
    logger.info(f"Active grants: {len(active)} grants")

    logger.info(f"Total loaded (before dedup): {len(all_grants)} grants")
    return all_grants
