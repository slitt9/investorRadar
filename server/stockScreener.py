from tradingview_screener import Query, col

x = (Query()
 .select('name', 'close', 'volume', 'market_cap_basic')
 .where(col('name') == 'HIVE')
 .get_scanner_data())
print(x)