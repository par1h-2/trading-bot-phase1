# Trading Bot - Phase 1

Automated cryptocurrency paper trading bot built with FastAPI and Binance API.

## Project Structure
- `trading-bot-phase1/`
  - `backend/`
    - `app/`
      - `api/`: API routes (endpoints for bot control, portfolio, trades)
      - `core/`: Configuration, settings, constants
      - `models/`: Database models and schemas
      - `services/`: Market data fetching, trading engine, portfolio management
      - `main.py`: FastAPI application entrypoint
    - `requirements.txt`: Python dependencies
    - `.env.example`: Environment variables template

## Setup & Running

1. Navigate to the backend directory:
   ```bash
   cd trading-bot-phase1/backend
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # On Windows:
   .\venv\Scripts\activate
   # On Linux/macOS:
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment variables:
   - Copy `.env.example` to `.env`
   - Fill in your API keys (Binance testnet, NewsAPI, etc.)

5. Run the server:
   ```bash
   uvicorn app.main:app --reload
   ```
