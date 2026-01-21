import os
import io
import uuid
import threading
import time
import csv
from datetime import datetime, timezone

from flask import Flask, render_template, request, jsonify, send_file, abort
import ccxt

app = Flask(__name__, template_folder='templates', static_folder='static')

DOWNLOAD_DIR = os.path.join(os.path.dirname(__file__), 'downloads')
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Simple in-memory job store. For production use a persistent store.
JOBS = {}


def ms_from_iso(dt_str):
    # Expecting HTML datetime-local value like '2026-01-21T15:30'
    if not dt_str:
        return None
    # Python 3.7+ supports fromisoformat for this format
    dt = datetime.fromisoformat(dt_str)
    # treat as local time -> convert to UTC timestamp
    # Assume user-provided times are local; convert to UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def timeframe_ms(tf: str) -> int:
    mapping = {
        '1m': 60_000,
        '5m': 5 * 60_000,
        '15m': 15 * 60_000,
        '30m': 30 * 60_000,
        '1h': 60 * 60_000,
        '4h': 4 * 60 * 60_000,
        '1d': 24 * 60 * 60_000,
    }
    return mapping.get(tf)


def safe_symbol_attempts(symbol: str):
    s = symbol.strip()
    yield s
    if '/' not in s:
        yield f"{s}/USDT"
        yield s.upper()
        yield f"{s.upper()}/USDT"
    else:
        yield s.replace(' ', '')


def fetch_ohlcv_job(job_id, symbol, timeframe, start_ms, end_ms):
    JOBS[job_id] = {'status': 'running', 'progress': 0, 'filename': None, 'error': None}

    try:
        exchange = ccxt.binance({'enableRateLimit': True})
        tf_ms = timeframe_ms(timeframe)
        if tf_ms is None:
            raise ValueError('Unsupported timeframe')

        # Try symbol variants until one works
        chosen_symbol = None
        for s in safe_symbol_attempts(symbol):
            try:
                # Test a tiny fetch to validate symbol
                exchange.fetch_ohlcv(s, timeframe, limit=1)
                chosen_symbol = s
                break
            except Exception:
                continue

        if chosen_symbol is None:
            raise ValueError(f'Symbol not recognized by the exchange: {symbol}')

        limit = 1000
        since = int(start_ms)
        all_rows = []
        last_ts = since

        total_span = max(1, end_ms - start_ms)
        # iterative fetch loop
        while since < end_ms:
            JOBS[job_id]['progress'] = int(min(99, (since - start_ms) / total_span * 100))
            try:
                chunk = exchange.fetch_ohlcv(chosen_symbol, timeframe, since, limit)
            except Exception as e:
                JOBS[job_id]['error'] = f'Error fetching data: {str(e)}'
                JOBS[job_id]['status'] = 'error'
                return

            if not chunk:
                # no more data
                break

            # Append new bars, avoid duplication
            for row in chunk:
                ts = int(row[0])
                if ts < start_ms:
                    continue
                if ts > end_ms:
                    continue
                if not all_rows or ts > int(all_rows[-1][0]):
                    all_rows.append(row)

            last_ts = int(chunk[-1][0])
            # advance since to just after last received candle
            since = last_ts + tf_ms
            # Respect rate limits, ccxt will sleep automatically when enableRateLimit=True, but be polite
            time.sleep(0.05)

            # safety: if the last_ts did not advance, break to avoid infinite loop
            if last_ts >= end_ms:
                break

        # Final progress
        JOBS[job_id]['progress'] = 100

        # Write CSV to file
        filename = f"{job_id}.csv"
        filepath = os.path.join(DOWNLOAD_DIR, filename)
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            for r in all_rows:
                ts = int(r[0])
                t_iso = datetime.utcfromtimestamp(ts / 1000).isoformat() + 'Z'
                writer.writerow([t_iso, r[1], r[2], r[3], r[4], r[5]])

        JOBS[job_id]['status'] = 'done'
        JOBS[job_id]['filename'] = filename
    except Exception as exc:
        JOBS[job_id]['status'] = 'error'
        JOBS[job_id]['error'] = str(exc)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/start_download', methods=['POST'])
def start_download():
    data = request.json or {}
    symbol = data.get('symbol')
    timeframe = data.get('timeframe')
    start = data.get('start')
    end = data.get('end')

    if not symbol or not timeframe or not start or not end:
        return jsonify({'error': 'Missing required parameters'}), 400

    try:
        start_ms = ms_from_iso(start)
        end_ms = ms_from_iso(end)
    except Exception:
        return jsonify({'error': 'Invalid date format'}), 400

    if start_ms >= end_ms:
        return jsonify({'error': 'Start must be before end'}), 400

    job_id = str(uuid.uuid4())
    # spawn background thread
    thread = threading.Thread(target=fetch_ohlcv_job, args=(job_id, symbol, timeframe, start_ms, end_ms), daemon=True)
    thread.start()

    JOBS[job_id] = {'status': 'starting', 'progress': 0, 'filename': None, 'error': None}
    return jsonify({'job_id': job_id})


@app.route('/progress/<job_id>')
def progress(job_id):
    job = JOBS.get(job_id)
    if not job:
        return jsonify({'error': 'job not found'}), 404
    return jsonify(job)


@app.route('/download/<job_id>')
def download(job_id):
    job = JOBS.get(job_id)
    if not job:
        return jsonify({'error': 'job not found'}), 404
    if job.get('status') != 'done' or not job.get('filename'):
        return jsonify({'error': 'file not ready'}), 400
    filepath = os.path.join(DOWNLOAD_DIR, job['filename'])
    if not os.path.exists(filepath):
        return jsonify({'error': 'file missing'}), 404
    return send_file(filepath, as_attachment=True, download_name=job['filename'], mimetype='text/csv')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
