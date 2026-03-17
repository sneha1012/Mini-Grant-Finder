"""
Grant data model for the Mini-Grant Finder.

Defines the core Grant dataclass that represents a single grant opportunity
throughout the pipeline — from discovery through scoring to display.
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
from typing import Optional


class GrantStatus(Enum):
    """Current status of a grant opportunity."""
    OPEN = "open"
    CLOSING_SOON = "closing_soon"
    UPCOMING = "upcoming"
    CLOSED = "closed"
    ROLLING = "rolling"
    MONITOR = "monitor"
    UNKNOWN = "unknown"


class GrantType(Enum):
    """Type of grant or funding opportunity."""
    FEDERAL_GRANT = "federal_grant"
    STATE_GRANT = "state_grant"
    FOUNDATION_GRANT = "foundation_grant"
    CORPORATE_GRANT = "corporate_grant"
    MINI_GRANT = "mini_grant"
    COMMUNITY_GRANT = "community_grant"
    IN_KIND = "in_kind"
    SPONSORSHIP = "sponsorship"
    FUNDRAISER = "fundraiser"
    UNKNOWN = "unknown"


class Priority(Enum):
    """Priority level for a grant opportunity."""
    URGENT = "urgent"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    MONITOR = "monitor"


@dataclass
class Grant:
    """
    Represents a single grant or funding opportunity.

    This is the core data structure that flows through the entire pipeline:
    scrapers create Grant objects, the scoring engine adds relevance scores,
    and the dashboard displays them.

    Attributes:
        name: Official name of the grant program
        source: Where this grant was discovered (e.g., 'grants.gov', 'rss_pnd')
        url: Direct link to the grant application or information page
        amount_min: Minimum award amount in USD (0 if unknown)
        amount_max: Maximum award amount in USD (0 if unknown)
        amount_text: Original amount text (e.g., "Up to $30,000/yr")
        deadline: Application deadline date
        deadline_text: Original deadline text (e.g., "Rolling", "Mar 1 2026")
        status: Current status of the grant
        grant_type: Type of funding opportunity
        description: Full description or summary of the grant
        focus_areas: List of focus area tags
        geographic_scope: Geographic eligibility (e.g., "National", "California")
        eligibility_notes: Key eligibility requirements
        how_to_apply: Application instructions
        funder: Name of the funding organization
        relevance_score: TF-IDF relevance score (0-100), set by scoring engine
        matched_programs: Delta programs this grant matches
        priority: Priority level based on deadline and relevance
        discovered_date: When the scraper first found this grant
        last_updated: When the grant info was last refreshed
        grant_id: Unique identifier (hash of name + funder + source)
    """

    name: str
    source: str = ""
    url: str = ""
    amount_min: float = 0.0
    amount_max: float = 0.0
    amount_text: str = ""
    deadline: Optional[date] = None
    deadline_text: str = ""
    status: GrantStatus = GrantStatus.UNKNOWN
    grant_type: GrantType = GrantType.UNKNOWN
    description: str = ""
    focus_areas: list[str] = field(default_factory=list)
    geographic_scope: str = ""
    eligibility_notes: str = ""
    how_to_apply: str = ""
    funder: str = ""
    relevance_score: float = 0.0
    matched_programs: list[str] = field(default_factory=list)
    priority: Priority = Priority.MEDIUM
    discovered_date: Optional[datetime] = None
    last_updated: Optional[datetime] = None
    grant_id: str = ""

    def __post_init__(self):
        """Generate grant_id if not provided and set defaults."""
        if not self.grant_id:
            self.grant_id = self._generate_id()
        if self.discovered_date is None:
            self.discovered_date = datetime.now()
        if self.last_updated is None:
            self.last_updated = datetime.now()

    def _generate_id(self) -> str:
        """Generate a unique ID from grant name and source."""
        import hashlib
        raw = f"{self.name}|{self.funder}|{self.source}".lower().strip()
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    @property
    def days_until_deadline(self) -> Optional[int]:
        """Calculate days remaining until the deadline."""
        if self.deadline is None:
            return None
        today = date.today()
        delta = self.deadline - today
        return delta.days

    @property
    def is_expired(self) -> bool:
        """Check if the grant deadline has passed."""
        if self.deadline is None:
            return False  # No deadline = might still be open
        return self.deadline < date.today()

    @property
    def urgency_label(self) -> str:
        """Get a human-readable urgency label based on deadline proximity."""
        days = self.days_until_deadline
        if days is None:
            return "No deadline"
        if days < 0:
            return "Expired"
        if days <= 7:
            return "This week"
        if days <= 14:
            return "Next 2 weeks"
        if days <= 30:
            return "This month"
        if days <= 60:
            return "Next 2 months"
        return "Upcoming"

    @property
    def amount_display(self) -> str:
        """Format the grant amount for display."""
        if self.amount_text:
            return self.amount_text
        if self.amount_max > 0 and self.amount_min > 0:
            if self.amount_min == self.amount_max:
                return f"${self.amount_max:,.0f}"
            return f"${self.amount_min:,.0f} - ${self.amount_max:,.0f}"
        if self.amount_max > 0:
            return f"Up to ${self.amount_max:,.0f}"
        return "Varies"

    def update_priority(self) -> None:
        """Update priority based on deadline urgency and relevance score."""
        days = self.days_until_deadline

        if days is not None and days <= 14 and self.relevance_score >= 50:
            self.priority = Priority.URGENT
        elif self.relevance_score >= 70:
            self.priority = Priority.HIGH
        elif days is not None and days <= 30:
            self.priority = Priority.HIGH
        elif self.relevance_score >= 40:
            self.priority = Priority.MEDIUM
        else:
            self.priority = Priority.LOW

        if self.status == GrantStatus.MONITOR:
            self.priority = Priority.MONITOR

    def to_dict(self) -> dict:
        """Convert to a dictionary for serialization."""
        return {
            "grant_id": self.grant_id,
            "name": self.name,
            "source": self.source,
            "url": self.url,
            "amount_min": self.amount_min,
            "amount_max": self.amount_max,
            "amount_text": self.amount_text,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "deadline_text": self.deadline_text,
            "status": self.status.value,
            "grant_type": self.grant_type.value,
            "description": self.description,
            "focus_areas": self.focus_areas,
            "geographic_scope": self.geographic_scope,
            "eligibility_notes": self.eligibility_notes,
            "how_to_apply": self.how_to_apply,
            "funder": self.funder,
            "relevance_score": self.relevance_score,
            "matched_programs": self.matched_programs,
            "priority": self.priority.value,
            "discovered_date": self.discovered_date.isoformat() if self.discovered_date else None,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Grant":
        """Create a Grant instance from a dictionary."""
        # Parse dates
        deadline = None
        if data.get("deadline"):
            try:
                deadline = date.fromisoformat(data["deadline"])
            except (ValueError, TypeError):
                pass

        discovered = None
        if data.get("discovered_date"):
            try:
                discovered = datetime.fromisoformat(data["discovered_date"])
            except (ValueError, TypeError):
                pass

        updated = None
        if data.get("last_updated"):
            try:
                updated = datetime.fromisoformat(data["last_updated"])
            except (ValueError, TypeError):
                pass

        # Parse enums safely
        try:
            status = GrantStatus(data.get("status", "unknown"))
        except ValueError:
            status = GrantStatus.UNKNOWN

        try:
            grant_type = GrantType(data.get("grant_type", "unknown"))
        except ValueError:
            grant_type = GrantType.UNKNOWN

        try:
            priority = Priority(data.get("priority", "medium"))
        except ValueError:
            priority = Priority.MEDIUM

        return cls(
            name=data.get("name", ""),
            source=data.get("source", ""),
            url=data.get("url", ""),
            amount_min=float(data.get("amount_min", 0)),
            amount_max=float(data.get("amount_max", 0)),
            amount_text=data.get("amount_text", ""),
            deadline=deadline,
            deadline_text=data.get("deadline_text", ""),
            status=status,
            grant_type=grant_type,
            description=data.get("description", ""),
            focus_areas=data.get("focus_areas", []),
            geographic_scope=data.get("geographic_scope", ""),
            eligibility_notes=data.get("eligibility_notes", ""),
            how_to_apply=data.get("how_to_apply", ""),
            funder=data.get("funder", ""),
            relevance_score=float(data.get("relevance_score", 0)),
            matched_programs=data.get("matched_programs", []),
            priority=priority,
            discovered_date=discovered,
            last_updated=updated,
            grant_id=data.get("grant_id", ""),
        )

    def __repr__(self) -> str:
        return (
            f"Grant(name='{self.name[:50]}', "
            f"score={self.relevance_score:.0f}, "
            f"deadline={self.deadline}, "
            f"amount={self.amount_display})"
        )
