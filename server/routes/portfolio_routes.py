from flask_restful import Resource, reqparse, abort
from datetime import datetime

def create_portfolio_routes(db, Portfolio, Stock, PortfolioStock):
    parser = reqparse.RequestParser()
    parser.add_argument('name', type=str, required=True, help='Portfolio name is required')
    
    stock_parser = reqparse.RequestParser()
    stock_parser.add_argument('stock_id', type=int, required=True, help='Stock ID is required')
    stock_parser.add_argument('allocation_percentage', type=float, required=True, help='Allocation percentage is required')
    stock_parser.add_argument('initial_investment', type=float, required=True, help='Initial investment amount is required')
    stock_parser.add_argument('purchase_price', type=float, required=True, help='Purchase price is required')
    stock_parser.add_argument('purchase_date', type=str, help='Purchase date (ISO format)')
    
    stock_update_parser = reqparse.RequestParser()
    stock_update_parser.add_argument('allocation_percentage', type=float)
    stock_update_parser.add_argument('initial_investment', type=float)
    
    class PortfolioListResource(Resource):
        def get(self):
            portfolios = Portfolio.query.all()
            return [p.to_dict() for p in portfolios]
        
        def post(self):
            args = parser.parse_args()
            new_portfolio = Portfolio(name=args['name'])
            db.session.add(new_portfolio)
            db.session.commit()
            return new_portfolio.to_dict(), 201
    
    class PortfolioResource(Resource):
        def get(self, portfolio_id):
            portfolio = Portfolio.query.get_or_404(portfolio_id)
            return portfolio.to_dict()
        
        def put(self, portfolio_id):
            portfolio = Portfolio.query.get_or_404(portfolio_id)
            args = parser.parse_args()
            portfolio.name = args['name']
            db.session.commit()
            return portfolio.to_dict()
        
        def delete(self, portfolio_id):
            portfolio = Portfolio.query.get_or_404(portfolio_id)
            db.session.delete(portfolio)
            db.session.commit()
            return {'message': 'Portfolio deleted'}, 200
    
    class PortfolioStockListResource(Resource):
        def post(self, portfolio_id):
            portfolio = Portfolio.query.get_or_404(portfolio_id)
            args = stock_parser.parse_args()
            
            stock = Stock.query.get_or_404(args['stock_id'])
            purchase_date = datetime.fromisoformat(args.get('purchase_date')) if args.get('purchase_date') else datetime.now()
            
            portfolio.add_stock(
                stock=stock,
                allocation_percentage=args['allocation_percentage'],
                initial_investment=args['initial_investment'],
                purchase_price=args['purchase_price'],
                purchase_date=purchase_date,
                db_session=db.session
            )
            
            portfolio_stock = PortfolioStock.query.filter_by(
                portfolio_id=portfolio_id,
                stock_id=args['stock_id']
            ).order_by(PortfolioStock.id.desc()).first()
            
            return portfolio_stock.to_dict(), 201
    
    class PortfolioStockResource(Resource):
        def delete(self, portfolio_id, stock_id):
            portfolio = Portfolio.query.get_or_404(portfolio_id)
            portfolio_stock = PortfolioStock.query.filter_by(
                portfolio_id=portfolio_id,
                stock_id=stock_id
            ).first_or_404()
            
            portfolio.remove_stock(portfolio_stock.id, db.session)
            return {'message': 'Stock removed from portfolio'}, 200
        
        def put(self, portfolio_id, stock_id):
            portfolio = Portfolio.query.get_or_404(portfolio_id)
            portfolio_stock = PortfolioStock.query.filter_by(
                portfolio_id=portfolio_id,
                stock_id=stock_id
            ).first_or_404()
            
            args = stock_update_parser.parse_args()
            
            if args.get('allocation_percentage') is not None:
                portfolio_stock.allocation_percentage = args['allocation_percentage']
            if args.get('initial_investment') is not None:
                portfolio_stock.initial_investment = args['initial_investment']
            
            db.session.commit()
            return portfolio_stock.to_dict()
    
    return PortfolioListResource, PortfolioResource, PortfolioStockListResource, PortfolioStockResource

