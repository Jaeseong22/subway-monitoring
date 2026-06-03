# Seoul Subway Monitoring

Real-time Seoul Subway Line 1 monitoring platform with Spring Boot, React, ELK, and AI anomaly detection.

## Repository

- Recommended name: `seoul-subway-monitoring`
- GitHub description: `Real-time Seoul Subway Line 1 monitoring platform with Spring Boot, React, ELK, and AI anomaly detection.`

## Overview

This project collects Seoul subway real-time arrival data, stores the latest Line 1 arrival state, streams structured service logs into Elasticsearch, and publishes AI-generated anomaly summaries to an admin dashboard.

```text
Seoul Open API
  -> Spring Boot scheduler
     -> MySQL latest arrival snapshot
     -> Logstash JSON logs
        -> Elasticsearch daily log indices
           -> Python AI anomaly service
              -> Elasticsearch anomaly result index
                 -> Spring Boot admin API
                    -> React dashboard
```

## Features

- Real-time Seoul Subway Line 1 arrival collection
- Station search and arrival status UI
- Spring Boot backend with MySQL persistence
- Structured API, scheduler, and metric logs
- Logstash to Elasticsearch ingestion
- Kibana access for log inspection
- Python AI anomaly analysis service using LangGraph and OpenAI
- Deterministic anomaly demo scenarios for presentations
- Elasticsearch snapshot script for log and anomaly-result backup
- Local-only Docker port binding for safer development

## Tech Stack

- Frontend: React, TypeScript, Vite, Tailwind CSS, Recharts
- Backend: Spring Boot, Java, JPA, MySQL
- Logs: Logstash, Elasticsearch, Kibana
- AI service: Python, LangGraph, LangChain, OpenAI API
- Runtime: Docker Compose

## Services

| Service | Local URL | Notes |
|---|---|---|
| Frontend | `http://localhost:3000` | React app served by Nginx |
| Backend API | `http://localhost:8080` | Spring Boot API |
| Elasticsearch | `http://localhost:9200` | Bound to `127.0.0.1` only |
| Kibana | `http://localhost:5601` | Bound to `127.0.0.1` only |
| MySQL | `localhost:3307` | Docker MySQL port |
| Logstash TCP | `localhost:50000` | JSON log ingestion |

## Security Note

Elasticsearch and Kibana are intentionally bound to `127.0.0.1` in `docker-compose.yml`.
Do not expose `9200` or `5601` to the public internet without enabling proper authentication, TLS, and network restrictions.

The `.env` file is ignored by Git. Use `.env.example` as a template and keep real API keys out of the repository.

## Prerequisites

- Docker Desktop
- Java 25 for local backend development
- Node.js 20 or newer for local frontend development
- Python 3.9 or newer for local AI service development
- Seoul Open API subway key
- OpenAI API key for LLM-based anomaly analysis

## Environment

Create a local `.env` file from the example:

```bash
cp .env.example .env
```

Then fill in the required keys:

```bash
SUBWAY_API_KEY=your_seoul_open_api_key
SUBWAY_API_KEY_SECONDARY=optional_second_key
OPENAI_API_KEY=your_openai_api_key
```

## Run With Docker Compose

```bash
docker compose up -d --build
```

Open:

```text
http://localhost:3000
```

Kibana:

```text
http://localhost:5601
```

Check containers:

```bash
docker compose ps
```

Stop services:

```bash
docker compose down
```

## Local Development

Backend:

```bash
cd backend
./gradlew bootRun
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

AI service:

```bash
cd ai_service
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Anomaly Demo

The demo script writes synthetic logs into `subway-demo-logs` and publishes a result to `subway-anomaly-results`.
It does not modify production `subway-logs-*` indices.

```bash
scripts/run_anomaly_demo.sh normal
scripts/run_anomaly_demo.sh api-failure
scripts/run_anomaly_demo.sh traffic-spike
scripts/run_anomaly_demo.sh scheduler-failure
scripts/run_anomaly_demo.sh restore
```

Use `restore` after a presentation to return the dashboard to live-log analysis.

## Backup

Create an Elasticsearch snapshot:

```bash
scripts/elk_snapshot.sh
```

The snapshot script includes:

- `subway-logs-*`
- `subway-anomaly-results`

## Current Data Model

MySQL stores the latest arrival state, not historical arrival records.
The backend refreshes `arrival_info` by deleting the previous rows and inserting the latest API result.

Elasticsearch stores time-series operational logs and AI anomaly result documents.

## Project Structure

```text
backend/        Spring Boot API and scheduler
frontend/       React dashboard
ai_service/     Python AI anomaly analysis service
logstash/       Logstash pipeline configuration
scripts/        Demo and snapshot scripts
docker-compose.yml
```

