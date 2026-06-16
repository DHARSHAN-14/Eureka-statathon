import pandas as pd
import json
import os

INPUT_CSV = "data/raw/nco_dataset_v3.csv"
OUTPUT_JSON = "data/processed/nco_documents.json"

def load_data(path):
    return pd.read_csv(path)

def safe_text(value):
    if pd.isna(value):
        return ""
    return str(value).strip()

def create_documents(df):
    documents = []
    metadata = []

    for idx, row in df.iterrows():
        doc = f"""
Occupation Title: {safe_text(row['Occupational Title'])}
NCO 2015 Code: {safe_text(row['NCO 2015'])}

Hierarchy:
Division: {safe_text(row['Division'])}
Sub Division: {safe_text(row['Sub Division'])}
Group: {safe_text(row['Group'])}
Family: {safe_text(row['Family'])}

Occupation Description:
{safe_text(row['Occupation Description'])}

Family Description:
{safe_text(row['Family Description'])}

Group Description:
{safe_text(row['Group Description'])}
""".strip()

        documents.append(doc)

        metadata.append({
            "row_id": idx,
            "nco_2015": safe_text(row['NCO 2015']),
            "occupation_title": safe_text(row['Occupational Title'])
        })

    return documents, metadata

def save_output(documents, metadata):
    os.makedirs("data/processed", exist_ok=True)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(documents, f, indent=2, ensure_ascii=False)

    with open("data/processed/nco_metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    df = load_data(INPUT_CSV)
    documents, metadata = create_documents(df)
    save_output(documents, metadata)

    print(f"✅ Created {len(documents)} semantic documents")
