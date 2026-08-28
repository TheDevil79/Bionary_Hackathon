# EvidenceLens — Evidence Corpus

This directory contains verified source documents and metadata for the multimodal claim verification workbench.

> ⚠️ **DEVELOPMENT DEMO DATA NOTICE:**  
> The documents in this corpus are synthetic or curated reference articles created for testing and demonstrating the EvidenceLens RAG and claim-verification pipeline.

---

## Structure

```
evidence_corpus/
├── README.md
├── sources/          # Metadata for each source document (JSON)
│   ├── source_001.json
│   ├── source_002.json
│   └── ...
└── documents/        # Raw full-text articles and reports (.txt)
    ├── source_001.txt
    ├── source_002.txt
    └── ...
```

---

## Document Inventory

| ID | Title | Publisher | Source Type | Language |
|---|---|---|---|---|
| `source_001` | IMD Weather Bulletin: Heavy Rain and Flash Floods in Chennai | National Meteorological Centre | news | en |
| `source_002` | Fact Check: 2015 Marina Beach Car Submersion Clip Resurfaces | National FactCheck Council | fact-check | en |
| `source_003` | Disaster Response Deployment Report: Chennai Districts | State Disaster Management Authority | government | en |
| `source_004` | NASA Webb Telescope Discovers Carbon Molecules on Exoplanet K2-18 b | NASA Astrophysics Directorate | academic | en |
| `source_005` | SETE Paris: Official Statement Regarding Viral Eiffel Tower Hoax | Société d'Exploitation de la Tour Eiffel | fact-check | en |
| `source_006` | Global Renewable Energy Adoption Trends & Grid Reliability | Energy Transition Institute | academic | en |
| `source_007` | Clinical Trial Results: Novel mRNA Vaccine Efficacy for Respiratory Pathogens | Global Health Research Journal | academic | en |
| `source_008` | Geological Survey: Subsea Infrastructure Feasibility in Palk Strait | Maritime Geotechnical Institute | government | en |

---

## How to Ingest the Corpus

From the `backend/` directory with your virtual environment activated:

```bash
python -m app.ingestion.ingest
```

Or run via the root CLI:
```bash
python -m app.ingestion.ingest --corpus ../evidence_corpus
```
