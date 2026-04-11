# Options API

A production-style REST API for querying and analyzing options market data in real time. Built with FastAPI, SQLAlchemy, and Python — featuring an automated data pipeline that fetches options chains, computes Greeks using the Black-Scholes model, and persists snapshots for historical analysis.

## Features

- **Automated Data Pipeline** — Fetches full options chains every 60 seconds during market hours (9:30 AM - 4:00 PM ET, Mon-Fri)
- **Black-Scholes Greek Calculations** — Computes delta, gamma, theta, and vega for each contract as data flows through the pipeline
- **Flexible Querying** — Filter by ticker, strike range, volume, open interest, implied volatility, and more
- **Historical Snapshots** — Query options data across time ranges to analyze how contracts evolved
- **Summary Analytics** — Get aggregated stats like put/call ratio, average IV, average delta, and volume leaders
- **API Key Authentication** — All endpoints protected via `X-API-Key` header

## Tech Stack

| Layer | Technology |
|-------|------------|
| Framework | FastAPI |
| ORM | SQLAlchemy 2.0 |
| Validation | Pydantic |
| Scheduler | APScheduler |
| Data Source | yfinance |
| Greeks | scipy (Black-Scholes) |
| Logging | structlog |
| Database | SQLite (swappable) |

## API Endpoints

All `/options/*` endpoints require `X-API-Key` header.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/options/chain` | Full options chain for a ticker, optionally filtered by expiry |
| `GET` | `/options/filter` | Multi-criteria search across tickers with strike/volume/IV filters |
| `GET` | `/options/history` | Historical snapshots within a date range |
| `GET` | `/options/summary` | Aggregated stats: put/call ratio, avg IV, avg delta, volume leader |
| `GET` | `/options/expirations` | List available expiration dates for a ticker |

## Architecture

```
app/
├── api/options.py       # Route handlers
├── core/
│   ├── config.py        # Settings via pydantic-settings
│   ├── database.py      # SQLAlchemy engine + session
│   └── auth.py          # API key verification
├── models/options.py    # ORM models (OptionsContract, WatchedTicker)
├── schemas/options.py   # Pydantic request/response schemas
└── services/
    ├── fetcher.py       # yfinance data retrieval
    └── snapshot.py      # Pipeline orchestration + Greek calculations
```

### Data Pipeline

```
APScheduler (every 60s, market hours only)
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  For each watched ticker:                           │
│    1. fetch_stock_price(ticker)                     │
│    2. fetch_options_chain(ticker)                   │
│    3. For each contract:                            │
│         → calculate_greeks(S, K, T, r, σ)           │
│    4. Upsert to database                            │
└─────────────────────────────────────────────────────┘
```

The pipeline is market-hours-aware — it checks Eastern Time and skips weekends automatically.

## Greek Calculations

Implements the Black-Scholes model for European options:

```
d₁ = [ln(S/K) + (r + σ²/2)T] / (σ√T)
d₂ = d₁ - σ√T

Delta:  call = N(d₁)           put = N(d₁) - 1
Gamma:  N'(d₁) / (Sσ√T)
Theta:  [...] / 365            (per calendar day)
Vega:   SN'(d₁)√T / 100        (per 1% IV move)
```

Parameters: S = underlying price, K = strike, T = time to expiry (years), r = risk-free rate (4.3%), σ = implied volatility.

## Quick Start

```bash
# Setup
git clone https://github.com/AkshajC/options-api.git
cd options-api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure
cat > .env << EOF
DATABASE_URL=sqlite:///./options.db
API_KEY=your-secret-key
DATA_PROVIDER_API_KEY=unused
EOF

# Run
uvicorn app.main:app --reload
```

Interactive API docs at `http://localhost:8000/docs`

## Example Requests

```bash
# Get AAPL options chain
curl -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/options/chain?ticker=AAPL"

# Filter high-volume calls with elevated IV
curl -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/options/filter?ticker=AAPL,TSLA&option_type=call&min_volume=1000&min_iv=0.4"

# Summary statistics
curl -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/options/summary?ticker=TSLA"

# Historical data
curl -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/options/history?ticker=AAPL&start_date=2024-01-01"
```

## Data Model

**OptionsContract**
| Field | Type | Description |
|-------|------|-------------|
| `ticker` | string | Underlying symbol (e.g., AAPL) |
| `contract_symbol` | string | OCC contract symbol |
| `option_type` | string | "call" or "put" |
| `strike_price` | float | Strike price |
| `expiry_date` | datetime | Expiration date |
| `bid`, `ask`, `last_price` | float | Quote data |
| `volume`, `open_interest` | int | Activity metrics |
| `implied_volatility` | float | IV from market |
| `delta`, `gamma`, `theta`, `vega` | float | Computed Greeks |
| `snapshot_time` | datetime | When data was captured |

## Author

**Akshaj Challa** — Built during undergrad as a production-level evolution of a prototype developed at ThinkSabio.

## License

MIT
