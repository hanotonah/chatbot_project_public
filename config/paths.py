"""
Path configuration (stable, rarely changed).
"""

from pathlib import Path

# Project root
PROJECT_ROOT: Path = Path(__file__).parent.parent

# Database and context file paths
CONTEXT_PATH: Path = PROJECT_ROOT / "data_sources" / "Data" / "Context"

CHUNK_OVERVIEW_PATH_ALL: Path = PROJECT_ROOT / "data_sources" / "Database" / "all_chunks.md"
CHUNK_OVERVIEW_PATH_STUDY_ADVISER: Path = PROJECT_ROOT / "data_sources" / "Database" / "study_adviser_chunks.md"
CHUNK_OVERVIEW_PATH_TEACHER: Path = PROJECT_ROOT / "data_sources" / "Database" / "teacher_chunks.md"

CHROMA_DB_PATH_ALL: Path = PROJECT_ROOT / "data_sources" / "Database" / "Chroma_database_all"
CHROMA_DB_PATH_STUDY_ADVISER: Path = PROJECT_ROOT / "data_sources" / "Database" / "Chroma_database_study_adviser"
CHROMA_DB_PATH_TEACHER: Path = PROJECT_ROOT / "data_sources" / "Database" / "Chroma_database_teacher"

# Abbreviation JSON path
ABBREVIATIONS_PATH: Path = PROJECT_ROOT / "src" / "chat" / "preprocessing" / "abbreviations.json"
