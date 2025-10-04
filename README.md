# AtmosAlert

AtmostAlert is a hackathon project that forecasts the **long-term health impacts of air pollution** using **NASA TEMPO data** + **Elastic** + a cloud-hosted app (FastAPI + Next.js).

## Features
- Ingests TEMPO, OpenAQ, and MERRA-2 pollution datasets
- Stores hourly pollutant exposures in Elasticsearch
- Visualizes trends + maps in Kibana
- Models long-term lung health outcomes ("Air Time Capsule")
- Cloud-hosted demo (Azure/Elastic)

## Repo Structure
data/ → CSV/JSON subsets of TEMPO data
ingest/ → Scripts to load data into Elasticsearch
backend/ → FastAPI backend
frontend/ → Next.js frontend
elastic/ → Mappings, bulk templates, queries
notebooks/ → Jupyter notebooks for exploration 

