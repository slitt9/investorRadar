def create_portfolio_model(db, Stock, PortfolioStock):
    class Portfolio(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String(100), nullable=False)
        created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())
        
        def __repr__(self):
            return f"Portfolio(name={self.name}, stocks_count={len(self.portfolio_stocks)})"
        
        @property
        def portfolio_value(self):
            if not self.portfolio_stocks:
                return 0.0
            return sum(ps.current_value for ps in self.portfolio_stocks)
        
        @property
        def cost_basis(self):
            if not self.portfolio_stocks:
                return 0.0
            return sum(ps.cost_basis for ps in self.portfolio_stocks)
        
        @property
        def total_return(self):
            return self.portfolio_value - self.cost_basis
        
        @property
        def total_return_percentage(self):
            if self.cost_basis == 0:
                return 0.0
            return (self.total_return / self.cost_basis) * 100
        
        @property
        def daily_return(self):
            if not self.portfolio_stocks:
                return 0.0
            return sum(ps.daily_return_value for ps in self.portfolio_stocks)
        
        @property
        def daily_return_percentage(self):
            previous_value = self.portfolio_value - self.daily_return
            if previous_value == 0:
                return 0.0
            return (self.daily_return / previous_value) * 100
        
        def to_dict(self):
            return {
                'id': self.id,
                'name': self.name,
                'created_at': self.created_at.isoformat() if self.created_at else None,
                'portfolio_stocks': [ps.to_dict() for ps in self.portfolio_stocks],
                'portfolio_value': self.portfolio_value,
                'cost_basis': self.cost_basis,
                'total_return': self.total_return,
                'total_return_percentage': self.total_return_percentage,
                'daily_return': self.daily_return,
                'daily_return_percentage': self.daily_return_percentage
            }
        
        def add_stock(self, stock, allocation_percentage, initial_investment, purchase_price, purchase_date, db_session, previous_close=None):
            portfolio_stock = PortfolioStock(
                portfolio_id=self.id,
                stock_id=stock.id,
                allocation_percentage=allocation_percentage,
                initial_investment=initial_investment,
                purchase_price=purchase_price,
                purchase_date=purchase_date,
                previous_close=previous_close or stock.close
            )
            db_session.add(portfolio_stock)
            db_session.commit()
        
        def remove_stock(self, portfolio_stock_id, db_session):
            portfolio_stock = PortfolioStock.query.filter_by(
                id=portfolio_stock_id,
                portfolio_id=self.id
            ).first()
            if portfolio_stock:
                db_session.delete(portfolio_stock)
                db_session.commit()
    
    return Portfolio