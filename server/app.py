from flask import Flask, request, jsonify
from flask_cors import CORS
from stockScreener import get_stock_data

app = Flask(__name__)
CORS(app)  # Enable CORS to allow frontend to make requests

@app.route('/api/stock', methods=['GET'])
def get_stock():
    """
    API endpoint to get stock data by ticker name.
    Query parameter: ticker (e.g., /api/stock?ticker=AAPL)
    """
    ticker = request.args.get('ticker', '').upper().strip()
    
    if not ticker:
        return jsonify({'error': 'Ticker parameter is required'}), 400
    
    try:
        count, df = get_stock_data(ticker)
        
        if count == 0:
            return jsonify({
                'error': f'No data found for ticker: {ticker}',
                'count': 0
            }), 404
        
        # Convert dataframe to dictionary for JSON response
        result = {
            'ticker': ticker,
            'count': count,
            'data': df.to_dict('records')  # Convert to list of dictionaries
        }
        
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'ok'}), 200

if __name__ == '__main__':
    app.run(debug=True, port=5000)

