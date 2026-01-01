from tradingview_screener import Query, col

def get_stock_data(ticker_name):
    """
    Get stock data for a given ticker name.
    
    Args:
        ticker_name (str): The stock ticker symbol (e.g., 'AAPL', 'HIVE')
    
    Returns:
        tuple: (count, dataframe) containing the stock data
    """
    result = (Query()
        .select('name', 'close', 'volume', 'market_cap_basic')
        .where(col('name') == ticker_name)
        .get_scanner_data())
    return result

if __name__ == "__main__":
    # For testing
    x = get_stock_data('HIVE')
    print(x)