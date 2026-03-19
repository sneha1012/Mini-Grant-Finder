"""
Google Sheets integration for grant data storage.

Stores scored grant data in Google Sheets for team access and
collaboration. Uses the Google Sheets API v4 with service account
authentication.

Setup:
1. Create a Google Cloud project (free tier)
2. Enable the Google Sheets API
3. Create a service account and download credentials.json
4. Share your Google Sheet with the service account email
5. Set GOOGLE_SHEETS_CREDENTIALS env var to the path of credentials.json
6. Set GOOGLE_SHEETS_ID env var to your spreadsheet ID
"""

import logging
import os
from datetime import datetime
from typing import Optional

from src.models.grant import Grant

logger = logging.getLogger(__name__)

# Column headers for the grants sheet
SHEET_HEADERS = [
    "Grant ID",
    "Name",
    "Funder",
    "Amount",
    "Deadline",
    "Status",
    "Type",
    "Relevance Score",
    "Matched Programs",
    "Priority",
    "Focus Areas",
    "Geographic Scope",
    "Eligibility",
    "How to Apply",
    "URL",
    "Source",
    "Discovered",
    "Last Updated",
]


class SheetsStorage:
    """
    Google Sheets storage backend for grant data.

    Reads and writes grant data to a shared Google Spreadsheet,
    enabling the whole team to view and collaborate on grant tracking.

    Falls back gracefully if credentials are not configured —
    the pipeline continues with local storage.
    """

    def __init__(
        self,
        credentials_path: Optional[str] = None,
        spreadsheet_id: Optional[str] = None,
        sheet_name: str = "Grants",
    ):
        """
        Initialize the Google Sheets storage.

        Args:
            credentials_path: Path to service account credentials JSON.
                            Reads from GOOGLE_SHEETS_CREDENTIALS env var
                            if not provided.
            spreadsheet_id: Google Spreadsheet ID.
                          Reads from GOOGLE_SHEETS_ID env var if not provided.
            sheet_name: Name of the worksheet tab to use.
        """
        self.credentials_path = credentials_path or os.environ.get(
            "GOOGLE_SHEETS_CREDENTIALS", ""
        )
        self.spreadsheet_id = spreadsheet_id or os.environ.get(
            "GOOGLE_SHEETS_ID", ""
        )
        self.sheet_name = sheet_name
        self._service = None
        self._available = False

        if self.credentials_path and self.spreadsheet_id:
            self._initialize()
        else:
            logger.info(
                "Google Sheets credentials not configured. "
                "Set GOOGLE_SHEETS_CREDENTIALS and GOOGLE_SHEETS_ID "
                "environment variables to enable Sheets storage."
            )

    def _initialize(self) -> None:
        """Initialize the Google Sheets API service."""
        try:
            from google.oauth2.service_account import Credentials
            from googleapiclient.discovery import build

            scopes = ["https://www.googleapis.com/auth/spreadsheets"]
            creds = Credentials.from_service_account_file(
                self.credentials_path, scopes=scopes
            )
            self._service = build("sheets", "v4", credentials=creds)
            self._available = True
            logger.info("Google Sheets API initialized successfully")
        except ImportError:
            logger.warning(
                "Google API libraries not installed. "
                "Run: pip install google-api-python-client google-auth"
            )
        except FileNotFoundError:
            logger.warning(
                f"Credentials file not found: {self.credentials_path}"
            )
        except Exception as e:
            logger.warning(f"Failed to initialize Google Sheets: {e}")

    @property
    def is_available(self) -> bool:
        """Check if Google Sheets is configured and accessible."""
        return self._available and self._service is not None

    def save_grants(self, grants: list[Grant]) -> bool:
        """
        Save grants to Google Sheets, replacing existing data.

        Creates the header row if it doesn't exist, then writes
        all grant data below it.

        Args:
            grants: List of scored Grant objects to save

        Returns:
            True if save was successful, False otherwise
        """
        if not self.is_available:
            logger.warning("Google Sheets not available, skipping save")
            return False

        try:
            sheet = self._service.spreadsheets()

            # Prepare data rows
            rows = [SHEET_HEADERS]  # Header row
            for grant in grants:
                rows.append(self._grant_to_row(grant))

            # Clear existing data and write new
            range_name = f"{self.sheet_name}!A1:R{len(rows) + 1}"

            # Clear
            sheet.values().clear(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
            ).execute()

            # Write
            sheet.values().update(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.sheet_name}!A1",
                valueInputOption="USER_ENTERED",
                body={"values": rows},
            ).execute()

            logger.info(f"Saved {len(grants)} grants to Google Sheets")
            return True

        except Exception as e:
            logger.error(f"Failed to save to Google Sheets: {e}")
            return False

    def append_grants(self, grants: list[Grant]) -> bool:
        """
        Append new grants to the existing sheet data.

        Useful for incremental updates where you don't want to
        overwrite the full dataset.

        Args:
            grants: New grants to append

        Returns:
            True if append was successful
        """
        if not self.is_available:
            return False

        try:
            sheet = self._service.spreadsheets()

            rows = [self._grant_to_row(grant) for grant in grants]

            sheet.values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.sheet_name}!A1",
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body={"values": rows},
            ).execute()

            logger.info(f"Appended {len(grants)} grants to Google Sheets")
            return True

        except Exception as e:
            logger.error(f"Failed to append to Google Sheets: {e}")
            return False

    def load_grants(self) -> list[dict]:
        """
        Load existing grant data from Google Sheets.

        Returns:
            List of grant data dictionaries, or empty list on failure
        """
        if not self.is_available:
            return []

        try:
            sheet = self._service.spreadsheets()
            result = sheet.values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.sheet_name}!A1:R1000",
            ).execute()

            values = result.get("values", [])
            if len(values) < 2:
                return []

            headers = values[0]
            grants = []
            for row in values[1:]:
                # Pad row with empty strings if shorter than headers
                padded = row + [""] * (len(headers) - len(row))
                grant_dict = dict(zip(headers, padded))
                grants.append(grant_dict)

            logger.info(f"Loaded {len(grants)} grants from Google Sheets")
            return grants

        except Exception as e:
            logger.error(f"Failed to load from Google Sheets: {e}")
            return []

    def _grant_to_row(self, grant: Grant) -> list[str]:
        """Convert a Grant object to a spreadsheet row."""
        return [
            grant.grant_id,
            grant.name,
            grant.funder,
            grant.amount_display,
            grant.deadline.isoformat() if grant.deadline else grant.deadline_text,
            grant.status.value,
            grant.grant_type.value,
            f"{grant.relevance_score:.0f}",
            ", ".join(grant.matched_programs),
            grant.priority.value,
            ", ".join(grant.focus_areas),
            grant.geographic_scope,
            grant.eligibility_notes,
            grant.how_to_apply,
            grant.url,
            grant.source,
            grant.discovered_date.strftime("%Y-%m-%d %H:%M")
            if grant.discovered_date
            else "",
            grant.last_updated.strftime("%Y-%m-%d %H:%M")
            if grant.last_updated
            else "",
        ]

    def format_sheet(self) -> bool:
        """
        Apply formatting to the Google Sheet (headers, column widths, etc.).

        Returns:
            True if formatting was applied successfully
        """
        if not self.is_available:
            return False

        try:
            sheet = self._service.spreadsheets()

            requests_list = [
                # Bold header row
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": 0,
                            "startRowIndex": 0,
                            "endRowIndex": 1,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "textFormat": {"bold": True},
                                "backgroundColor": {
                                    "red": 0.2,
                                    "green": 0.5,
                                    "blue": 0.2,
                                },
                                "horizontalAlignment": "CENTER",
                            }
                        },
                        "fields": "userEnteredFormat(textFormat,backgroundColor,horizontalAlignment)",
                    }
                },
                # Freeze header row
                {
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": 0,
                            "gridProperties": {"frozenRowCount": 1},
                        },
                        "fields": "gridProperties.frozenRowCount",
                    }
                },
            ]

            sheet.batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body={"requests": requests_list},
            ).execute()

            logger.info("Applied formatting to Google Sheet")
            return True

        except Exception as e:
            logger.error(f"Failed to format Google Sheet: {e}")
            return False
