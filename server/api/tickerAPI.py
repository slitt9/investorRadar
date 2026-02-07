from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import random
from tradingview_screener import Query, col
from flask_sqlalchemy import SQLAlchemy
from flask_restful import Api, Resource, reqparse, fields, marshal_with, abort
from flask_cors import CORS
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from server.routes import create_portfolio_routes
from server.models.Stock import create_stock_model
from server.models.Portfolio import create_portfolio_model
from server.models.PortfolioStock import create_portfolio_stock_model

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///stock.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
api = Api(app)
CORS(app)

Stock = create_stock_model(db)
PortfolioStock = create_portfolio_stock_model(db, None, Stock)
Portfolio = create_portfolio_model(db, Stock, PortfolioStock)

with app.app_context():
    db.create_all()

def get_stock_from_tradingview(ticker_name):
    try:
        result = (Query()
            .select('name', 'close', 'volume', 'market_cap_basic')
            .where(col('name') == ticker_name)
            .get_scanner_data())
        
        count, df = result
        if count == 0 or df.empty:
            return None
        
        stock_data = df.iloc[0]
        return {
            'ticker': ticker_name,
            'name': stock_data['name'],
            'close': float(stock_data['close']) if pd.notna(stock_data['close']) else None,
            'volume': int(stock_data['volume']) if pd.notna(stock_data['volume']) else None,
            'market_cap_basic': int(stock_data['market_cap_basic']) if pd.notna(stock_data['market_cap_basic']) else None
        }
    except Exception as e:
        print(f"Error fetching from TradingView: {e}")
        return None

class StockResource(Resource):
    def get(self, ticker):
        stock = Stock.query.filter_by(ticker=ticker.upper()).first()
        
        if stock:
            return stock.to_dict()
        
        stock_data = get_stock_from_tradingview(ticker.upper())
        
        if not stock_data:
            abort(404, message=f"Stock ticker '{ticker}' not found")
        
        new_stock = Stock(
            ticker=stock_data['ticker'],
            name=stock_data['name'],
            close=stock_data['close'],
            volume=stock_data['volume'],
            market_cap_basic=stock_data['market_cap_basic']
        )
        
        try:
            db.session.add(new_stock)
            db.session.commit()
            return new_stock.to_dict()
        except Exception as e:
            db.session.rollback()
            stock = Stock.query.filter_by(ticker=ticker.upper()).first()
            if stock:
                return stock.to_dict()
            abort(500, message=f"Error saving stock: {str(e)}")

class StockHistoryResource(Resource):
    def get(self, ticker):
        period = request.args.get('period', '1d')
        
        stock = Stock.query.filter_by(ticker=ticker.upper()).first()
        if not stock:
            stock_data = get_stock_from_tradingview(ticker.upper())
            if not stock_data:
                abort(404, message=f"Stock ticker '{ticker}' not found")
            stock = Stock(
                ticker=stock_data['ticker'],
                name=stock_data['name'],
                close=stock_data['close'],
                volume=stock_data['volume'],
                market_cap_basic=stock_data['market_cap_basic']
            )
            db.session.add(stock)
            db.session.commit()
        
        current_price = stock.close
        historical_data = generate_historical_data(current_price, period)
        
        return {
            'ticker': ticker.upper(),
            'period': period,
            'data': historical_data
        }

def generate_historical_data(current_price, period):
    
    data_points = {
        '1d': 24,
        '1w': 7,
        '3m': 90,
        '1y': 365
    }
    
    points = data_points.get(period, 30)
    data = []
    base_price = current_price * (0.85 + random.random() * 0.3)
    
    for i in range(points):
        days_ago = points - i
        date = datetime.now() - timedelta(days=days_ago)
        
        variation = random.uniform(-0.02, 0.02)
        if i > 0:
            base_price = data[-1]['close'] * (1 + variation)
        else:
            base_price = current_price * (0.85 + random.random() * 0.3)
        
        data.append({
            'date': date.isoformat(),
            'close': round(base_price, 2),
            'open': round(base_price * (1 + random.uniform(-0.01, 0.01)), 2),
            'high': round(base_price * (1 + random.uniform(0, 0.03)), 2),
            'low': round(base_price * (1 - random.uniform(0, 0.03)), 2),
            'volume': random.randint(1000000, 10000000)
        })
    
    data.append({
        'date': datetime.now().isoformat(),
        'close': round(current_price, 2),
        'open': round(current_price * (1 + random.uniform(-0.01, 0.01)), 2),
        'high': round(current_price * (1 + random.uniform(0, 0.02)), 2),
        'low': round(current_price * (1 - random.uniform(0, 0.02)), 2),
        'volume': random.randint(1000000, 10000000)
    })
    
    return data

PortfolioListResource, PortfolioResource, PortfolioStockListResource, PortfolioStockResource = create_portfolio_routes(db, Portfolio, Stock, PortfolioStock)

api.add_resource(StockResource, '/api/stock/<string:ticker>')
api.add_resource(StockHistoryResource, '/api/stock/<string:ticker>/history')
api.add_resource(PortfolioListResource, '/api/portfolios')
api.add_resource(PortfolioResource, '/api/portfolios/<int:portfolio_id>')
api.add_resource(PortfolioStockListResource, '/api/portfolios/<int:portfolio_id>/stocks')
api.add_resource(PortfolioStockResource, '/api/portfolios/<int:portfolio_id>/stocks/<int:stock_id>')

@app.route('/')
def home():
    return jsonify({'message': 'InvestorRadar API'})

@app.route('/api/health')
def health():
    return jsonify({'status': 'ok'}), 200

if __name__ == '__main__':
    app.run(debug=True, port=5000)