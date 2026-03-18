"""Data processing pipeline for grant cleaning and deduplication."""

from src.pipeline.processor import GrantProcessor, process_grants

__all__ = ["GrantProcessor", "process_grants"]
