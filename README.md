# JP Stock Analyzer

A full-stack application for analyzing Japanese stocks using fundamentals, news, and technical indicators.  
Built with FastAPI (backend), PostgreSQL (database), and React + Vite + TypeScript + React Bootstrap (frontend).

---

## 📁 Project Structure
```
jp-stock-analyzer/
├── backend/ # FastAPI app
│ └── app/
│ └── db/ # DB engine and init script
├── frontend/ # React + Vite app
├── docker-compose.yml # Service orchestration
├── .env # Environment variables
└── README.md
```
---

## 🛠️ Prerequisites

- [Docker](https://www.docker.com/) + Docker Compose
- Node.js and npm (if running frontend locally without Docker)

---

## 🚀 Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/your-username/jp-stock-analyzer.git
cd jp-stock-analyzer
```
### 2. Start all services
```
docker compose up --build
```
FastAPI backend: http://localhost:8002
React frontend: http://localhost:3000
PostgreSQL: exposed at port 5434 (locally)
### 3. Initialize the database
Once containers are running, open another terminal:
```
docker compose exec backend python -m app.db.init_db
```
This will create required tables in the PostgreSQL database.
### 4. Test the backend API
Visit or curl:
```
curl http://localhost:8002/health
```
📚 Coming Soon
- Yahoo Finance JP scraping
- GPT-based news analysis
- Technical indicator visualizations
- Screener for undervalued stocks

