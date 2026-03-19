"""
Local JSON file storage for grant data.

Provides a file-based storage backend that works without any
external services. Used as the primary storage during development
and as a fallback when Google Sheets is not configured.

Data is stored in data/processed/ as timestamped JSON files.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.models.grant import Grant

logger = logging.getLogger(__name__)

# Default storage directory
DATA_DIR = Path(__file__).parent.parent.parent / "data" / "processed"


class LocalStorage:
    """
    Local file-based storage backend for grant data.

    Saves grants as JSON files in data/processed/ with timestamps.
    Maintains a 'latest.json' symlink/copy for easy access to the
    most recent data.

    File structure:
        data/processed/
            grants_2026-03-19.json    # Daily snapshots
            grants_2026-03-20.json
            latest.json               # Always points to most recent
    """

    def __init__(self, storage_dir: Optional[str] = None):
        """
        Initialize local storage.

        Args:
            storage_dir: Directory path for JSON files.
                        Defaults to data/processed/
        """
        self.storage_dir = Path(storage_dir) if storage_dir else DATA_DIR
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def save_grants(self, grants: list[Grant], tag: str = "") -> str:
        """
        Save grants to a timestamped JSON file.

        Args:
            grants: List of Grant objects to save
            tag: Optional tag for the filename (e.g., 'daily', 'weekly')

        Returns:
            Path to the saved file
        """
        timestamp = datetime.now().strftime("%Y-%m-%d")

        if tag:
            filename = f"grants_{tag}_{timestamp}.json"
        else:
            filename = f"grants_{timestamp}.json"

        filepath = self.storage_dir / filename

        data = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "total_grants": len(grants),
                "tag": tag,
                "version": "1.0",
            },
            "grants": [grant.to_dict() for grant in grants],
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)

        # Update the 'latest.json' file
        latest_path = self.storage_dir / "latest.json"
        with open(latest_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)

        logger.info(f"Saved {len(grants)} grants to {filepath}")
        return str(filepath)

    def load_grants(self, filepath: Optional[str] = None) -> list[Grant]:
        """
        Load grants from a JSON file.

        Args:
            filepath: Specific file to load. Defaults to latest.json.

        Returns:
            List of Grant objects
        """
        if filepath is None:
            filepath = str(self.storage_dir / "latest.json")

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            logger.warning(f"No data file found at {filepath}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {filepath}: {e}")
            return []

        grants_data = data.get("grants", [])
        grants = []

        for gd in grants_data:
            try:
                grant = Grant.from_dict(gd)
                grants.append(grant)
            except Exception as e:
                logger.warning(f"Failed to parse grant: {e}")

        logger.info(
            f"Loaded {len(grants)} grants from {filepath}"
        )
        return grants

    def load_latest(self) -> list[Grant]:
        """Load the most recent grant data."""
        return self.load_grants()

    def list_snapshots(self) -> list[dict]:
        """
        List all available data snapshots.

        Returns:
            List of dicts with 'filename', 'date', 'size', 'grant_count'
        """
        snapshots = []

        for filepath in sorted(self.storage_dir.glob("grants_*.json")):
            if filepath.name == "latest.json":
                continue

            stat = filepath.stat()

            # Try to get grant count from metadata
            grant_count = 0
            try:
                with open(filepath, "r") as f:
                    data = json.load(f)
                    grant_count = data.get("metadata", {}).get(
                        "total_grants", len(data.get("grants", []))
                    )
            except Exception:
                pass

            snapshots.append({
                "filename": filepath.name,
                "path": str(filepath),
                "date": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "size_bytes": stat.st_size,
                "grant_count": grant_count,
            })

        return snapshots

    def get_new_grants(
        self, current: list[Grant], previous_file: Optional[str] = None
    ) -> list[Grant]:
        """
        Find grants that are new compared to a previous snapshot.

        Args:
            current: Current list of grants
            previous_file: Path to the previous snapshot file.
                         If None, uses the second-most-recent file.

        Returns:
            List of grants that were not in the previous snapshot
        """
        if previous_file:
            previous = self.load_grants(previous_file)
        else:
            snapshots = self.list_snapshots()
            if len(snapshots) < 2:
                return current  # No previous data, all are "new"
            previous = self.load_grants(snapshots[-2]["path"])

        previous_ids = {g.grant_id for g in previous}
        new_grants = [g for g in current if g.grant_id not in previous_ids]

        logger.info(
            f"Found {len(new_grants)} new grants "
            f"(vs {len(previous)} previous)"
        )
        return new_grants

    def cleanup_old(self, keep_days: int = 30) -> int:
        """
        Remove snapshot files older than keep_days.

        Args:
            keep_days: Number of days of history to keep

        Returns:
            Number of files removed
        """
        cutoff = datetime.now().timestamp() - (keep_days * 86400)
        removed = 0

        for filepath in self.storage_dir.glob("grants_*.json"):
            if filepath.name == "latest.json":
                continue
            if filepath.stat().st_mtime < cutoff:
                filepath.unlink()
                removed += 1
                logger.debug(f"Removed old snapshot: {filepath.name}")

        if removed:
            logger.info(f"Cleaned up {removed} old snapshot files")

        return removed

    def export_csv(
        self, grants: Optional[list[Grant]] = None, filepath: Optional[str] = None
    ) -> str:
        """
        Export grants to CSV format for easy sharing.

        Args:
            grants: Grants to export. Loads latest if not provided.
            filepath: Output path. Defaults to data/processed/export.csv.

        Returns:
            Path to the exported CSV file
        """
        import csv

        if grants is None:
            grants = self.load_latest()

        if filepath is None:
            filepath = str(self.storage_dir / "export.csv")

        headers = [
            "Name", "Funder", "Amount", "Deadline", "Status",
            "Relevance Score", "Programs", "Priority", "URL",
            "Geographic Scope", "Focus Areas",
        ]

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)

            for grant in grants:
                writer.writerow([
                    grant.name,
                    grant.funder,
                    grant.amount_display,
                    grant.deadline.isoformat() if grant.deadline else grant.deadline_text,
                    grant.status.value,
                    f"{grant.relevance_score:.0f}",
                    ", ".join(grant.matched_programs),
                    grant.priority.value,
                    grant.url,
                    grant.geographic_scope,
                    ", ".join(grant.focus_areas),
                ])

        logger.info(f"Exported {len(grants)} grants to {filepath}")
        return filepath
