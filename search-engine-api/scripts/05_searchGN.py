import json
import re

# Load metadata and documents
with open("data/processed/nco_metadata.json", "r", encoding="utf-8") as f:
    metadata = json.load(f)

with open("data/processed/nco_documents.json", "r", encoding="utf-8") as f:
    documents = json.load(f)

gn = {}

# Match metadata with documents by index (row_id matches document index)
for idx, item in enumerate(metadata):
    code = item["nco_2015"]
    # Use the document text as description
    desc = documents[idx].lower() if idx < len(documents) else ""

    # Simple keyword extraction: top frequent nouns/verbs
    words = re.findall(r'\b[a-z]{3,}\b', desc)
    keywords = list(set(words))  # remove duplicates

    # Extract sector from division if available (from document text)
    sector = "unknown"
    if "division:" in desc:
        lines = desc.split("\n")
        for line in lines:
            if line.strip().startswith("division:"):
                sector = line.split(":", 1)[1].strip().title()
                break

    gn[code] = {
        "sector": sector,
        "keywords": keywords
    }

# Save GN
with open("data/processed/nco_graph.json", "w", encoding="utf-8") as f:
    json.dump(gn, f, indent=2)

print(f"✅ Created graph with {len(gn)} nodes")
