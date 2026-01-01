# InvestorRadar

A stock market analysis platform that helps you invest in the stock market by providing real-time stock data and screening capabilities.

## Features

- Stock ticker search and analysis
- Real-time stock data retrieval using TradingView API
- Market data including price, volume, and market cap

## Tech Stack

- **Backend**: Python, Flask
- **Frontend**: HTML, CSS, JavaScript
- **Stock Data**: tradingview-screener

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the Flask server:
```bash
cd server
python app.py
```

3. Open `client/pages/homepage.html` in your browser

## Project Structure

```
investorRadar/
├── client/
│   ├── pages/
│   │   └── homepage.html
│   └── styling/
│       └── style.css
├── server/
│   ├── app.py          # Flask API server
│   └── stockScreener.py # Stock data retrieval
├── requirements.txt
└── README.md
```

## API Endpoints

- `GET /api/stock?ticker=<TICKER>` - Get stock data for a given ticker
- `GET /api/health` - Health check endpoint

## License

MIT

