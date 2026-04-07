# InvestorRadar 📡

A modern, fast, and feature-rich stock analyzer dashboard built entirely with Python and Streamlit.

This professional app uses data directly from the **US Securities and Exchange Commission (SEC) EDGAR API** to calculate fundamental financial metrics manually, and utilizes the free `yfinance` library for real-time price quotes and historical charts. 

**Zero API keys are required to run this app!**

## Features
- **Zero API Keys**: No rate limits, no subscriptions, no complicated setups!
- **True Local Calculation**: Financial metrics (like Market Cap, PE Ratio, Book Value) are calculated mathematically on-the-fly using raw SEC XBRL GAAP facts.
- **Dark Mode UI**: Clean, professional design out of the box using Streamlit's robust UI kit and Plotly template styling.
- **Interactive Timeframes Charts**: 1D to Max charting, customized with Candlestick and Volume subplots via `plotly`.
- **Market Dashboard**: Dynamic top movers and major indices loaded from Yahoo Finance.
- **Deep Dive Views**: Direct SEC Fundamentals, Recent News, and beautifully responsive layout.

## Requirements & Setup

1. **Clone or Download** the folder contents.
2. **Install Dependencies**:
```bash
pip install -r requirements.txt
```

3. **Run the application**:
```bash
streamlit run investorradar.py
```
