import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import json
from dataclasses import dataclass
from typing import Dict, List, Tuple

import pandas as pd

from src.utils.config import (
    NCO_CSV_PATH,
    PROCESSED_DATA_DIR,
    DOCUMENTS_PATH,
    METADATA_PATH,
)


REQUIRED_COLUMNS = [
    "S No",
    "Occupational Title",
    "NCO 2015",
    "NCO 2004",
    "Division",
    "Sub Division",
    "Group",
    "Family",
    "Division Description",
    "Sub Division Description",
    "Group Description",
    "Family Description",
    "Occupation Description",
]


@dataclass(frozen=True)
class PreparationStats:
    total_rows: int
    documents_created: int
    metadata_created: int
    missing_nco_codes: int
    missing_titles: int


class DocumentPreparationService:
    """
    Converts the raw NCO CSV into:
    1. nco_documents.json - rich text documents for embedding/search
    2. nco_metadata.json  - structured metadata for result lookup
    """

    def __init__(self, input_csv: Path = NCO_CSV_PATH):
        self.input_csv = Path(input_csv)

    @staticmethod
    def clean_text(value) -> str:
        if pd.isna(value):
            return ""

        text = str(value).strip()
        text = " ".join(text.split())
        return text

    def load_dataset(self) -> pd.DataFrame:
        if not self.input_csv.exists():
            raise FileNotFoundError(f"CSV file not found: {self.input_csv}")

        df = pd.read_csv(
            self.input_csv,
            dtype=str,
            keep_default_na=False,
        )

        return df

    def validate_schema(self, df: pd.DataFrame) -> None:
        missing_columns = [
            col for col in REQUIRED_COLUMNS
            if col not in df.columns
        ]

        if missing_columns:
            raise ValueError(
                "CSV schema validation failed. "
                f"Missing columns: {missing_columns}"
            )

    def build_document(self, row: pd.Series) -> str:
        occupation_title = self.clean_text(row["Occupational Title"])
        nco_2015 = self.clean_text(row["NCO 2015"])
        nco_2004 = self.clean_text(row["NCO 2004"])

        division = self.clean_text(row["Division"])
        subdivision = self.clean_text(row["Sub Division"])
        group = self.clean_text(row["Group"])
        family = self.clean_text(row["Family"])

        division_description = self.clean_text(row["Division Description"])
        subdivision_description = self.clean_text(row["Sub Division Description"])
        group_description = self.clean_text(row["Group Description"])
        family_description = self.clean_text(row["Family Description"])
        occupation_description = self.clean_text(row["Occupation Description"])

        return f"""
Occupation Title:
{occupation_title}

NCO 2015 Code:
{nco_2015}

NCO 2004 Code:
{nco_2004}

Hierarchy:
Division: {division}
Sub Division: {subdivision}
Group: {group}
Family: {family}

Occupation Description:
{occupation_description}

Family Description:
{family_description}

Group Description:
{group_description}

Sub Division Description:
{subdivision_description}

Division Description:
{division_description}
""".strip()

    def build_metadata(self, row: pd.Series, row_id: int) -> Dict:
        return {
            "row_id": row_id,
            "serial_no": self.clean_text(row["S No"]),
            "occupation_title": self.clean_text(row["Occupational Title"]),
            "nco_2015": self.clean_text(row["NCO 2015"]),
            "nco_2004": self.clean_text(row["NCO 2004"]),
            "division": self.clean_text(row["Division"]),
            "sub_division": self.clean_text(row["Sub Division"]),
            "group": self.clean_text(row["Group"]),
            "family": self.clean_text(row["Family"]),
            "division_description": self.clean_text(row["Division Description"]),
            "sub_division_description": self.clean_text(row["Sub Division Description"]),
            "group_description": self.clean_text(row["Group Description"]),
            "family_description": self.clean_text(row["Family Description"]),
            "occupation_description": self.clean_text(row["Occupation Description"]),
        }

    def create_outputs(self, df: pd.DataFrame) -> Tuple[List[str], List[Dict]]:
        documents = []
        metadata = []

        for row_id, row in df.iterrows():
            documents.append(
                self.build_document(row)
            )

            metadata.append(
                self.build_metadata(row, row_id)
            )

        return documents, metadata

    def save_json(self, data, path: Path) -> None:
        path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                data,
                f,
                indent=2,
                ensure_ascii=False
            )

    def validate_outputs(
        self,
        documents: List[str],
        metadata: List[Dict],
        total_rows: int
    ) -> None:
        if len(documents) != total_rows:
            raise ValueError(
                f"Document count mismatch. "
                f"Expected {total_rows}, got {len(documents)}"
            )

        if len(metadata) != total_rows:
            raise ValueError(
                f"Metadata count mismatch. "
                f"Expected {total_rows}, got {len(metadata)}"
            )

        if len(documents) != len(metadata):
            raise ValueError(
                "Documents and metadata length mismatch."
            )

    def process(self) -> PreparationStats:
        print("Loading NCO CSV...")
        df = self.load_dataset()

        print("Validating schema...")
        self.validate_schema(df)

        print("Creating documents and metadata...")
        documents, metadata = self.create_outputs(df)

        print("Validating generated outputs...")
        self.validate_outputs(
            documents=documents,
            metadata=metadata,
            total_rows=len(df)
        )

        print("Saving processed files...")
        PROCESSED_DATA_DIR.mkdir(
            parents=True,
            exist_ok=True
        )

        self.save_json(
            documents,
            DOCUMENTS_PATH
        )

        self.save_json(
            metadata,
            METADATA_PATH
        )

        stats = PreparationStats(
            total_rows=len(df),
            documents_created=len(documents),
            metadata_created=len(metadata),
            missing_nco_codes=sum(
                1 for item in metadata
                if not item["nco_2015"]
            ),
            missing_titles=sum(
                1 for item in metadata
                if not item["occupation_title"]
            ),
        )

        print("\nPreparation Complete")
        print("-" * 50)
        print(f"Total Rows        : {stats.total_rows}")
        print(f"Documents Created : {stats.documents_created}")
        print(f"Metadata Created  : {stats.metadata_created}")
        print(f"Missing NCO Codes : {stats.missing_nco_codes}")
        print(f"Missing Titles    : {stats.missing_titles}")
        print(f"Documents Path    : {DOCUMENTS_PATH}")
        print(f"Metadata Path     : {METADATA_PATH}")

        return stats


if __name__ == "__main__":
    service = DocumentPreparationService()
    service.process()