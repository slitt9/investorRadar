# InvestorRadar

A stock market analysis platform that helps you invest in the stock market by providing real-time stock data and screening capabilities. Provides stock news and advanced analysis, as well as portfolio analysis and recommendations.

## Features

- Stock ticker search and analysis
- Real-time stock data retrieval using TradingView API
- Interactive price charts with multiple time periods (1 Day, 1 Week, 3 Months, 1 Year)
- Market data including price, volume, and market cap
- Daily return calculations

## Tech Stack

- **Backend**: Python, Flask-RESTful
- **Frontend**: React, Vite, Recharts
- **Stock Data**: tradingview-screener

## Setup

### Backend

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Start the Flask server:
```bash
cd server/api
python tickerAPI.py
```

The API will be available at `http://localhost:5000`

### Frontend

1. Navigate to client directory:
```bash
cd client
```

2. Install Node dependencies:
```bash
npm install
```

3. Start the development server:
```bash
npm run dev
```

The frontend will be available at `http://localhost:3000`

## Usage

1. Start the backend server (Flask API) - `python server/api/tickerAPI.py`
2. Start the frontend server (React app) - `cd client && npm run dev`
3. Open `http://localhost:3000` in your browser
4. Enter a stock ticker (e.g., AAPL, MSFT, GOOGL) and click Search
5. View the stock's price chart and select different time periods (1 Day, 1 Week, 3 Months, 1 Year)

## API Endpoints

- `GET /api/stock/<ticker>` - Get stock data
- `GET /api/stock/<ticker>/history?period=<1d|1w|3m|1y>` - Get historical price data
- `GET /api/portfolios` - Portfolio management endpoints
- `GET /api/health` - Health check

## License

MIT
