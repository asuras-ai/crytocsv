# Crypto OHLCV CSV Downloader

Simple Flask webapp to fetch OHLCV data from CCXT (Binance) and download as CSV.

Features:
- Enter symbol (e.g. BTC/USDT or BTC)
- Choose timeframe (1m, 5m, 15m, 30m, 1h, 4h, 1d)
- Pick start and end datetimes
- Shows progress and provides CSV for download

Run locally:

1. Create a virtualenv and install requirements

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt
python app.py
```

2. Open http://localhost:5000

Run with Docker:

```powershell
docker build -t crytocsv .
docker run -p 5000:5000 crytocsv
```

Run with docker-compose:

```powershell
docker-compose up --build -d
# then open http://localhost:5000
```

Notes:
- This app uses in-memory job tracking. For multiple users or production, replace with Redis or a database.
- The app tries symbol variants if the provided symbol isn't accepted by the exchange.
- Rate limits are handled by ccxt when enableRateLimit=True, but long ranges may take time.
