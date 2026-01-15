def create_portfolio_stock_model(db, Portfolio, Stock):
    class PortfolioStock(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        portfolio_id = db.Column(db.Integer, db.ForeignKey('portfolio.id'), nullable=False)
        stock_id = db.Column(db.Integer, db.ForeignKey('stock.id'), nullable=False)
        allocation_percentage = db.Column(db.Float, nullable=False)
        initial_investment = db.Column(db.Float, nullable=False)
        purchase_price = db.Column(db.Float, nullable=False)
        purchase_date = db.Column(db.DateTime, nullable=False, default=db.func.now())
        previous_close = db.Column(db.Float)
        
        portfolio = db.relationship('Portfolio', backref='portfolio_stocks')
        stock = db.relationship('Stock', backref='portfolio_stocks')
        
        def __repr__(self):
            return f"PortfolioStock(portfolio_id={self.portfolio_id}, stock_id={self.stock_id}, allocation={self.allocation_percentage}%)"
        
        @property
        def current_value(self):
            price_change_ratio = self.stock.close / self.purchase_price if self.purchase_price > 0 else 1.0
            return self.initial_investment * price_change_ratio
        
        @property
        def cost_basis(self):
            return self.initial_investment
        
        @property
        def total_return(self):
            return self.current_value - self.cost_basis
        
        @property
        def total_return_percentage(self):
            if self.cost_basis == 0:
                return 0.0
            return (self.total_return / self.cost_basis) * 100
        
        @property
        def daily_return(self):
            if not self.previous_close:
                return 0.0
            return self.stock.close - self.previous_close
        
        @property
        def daily_return_percentage(self):
            if not self.previous_close or self.previous_close == 0:
                return 0.0
            return ((self.stock.close - self.previous_close) / self.previous_close) * 100
        
        @property
        def daily_return_value(self):
            if not self.previous_close:
                return 0.0
            price_change_ratio = self.daily_return / self.previous_close if self.previous_close > 0 else 0.0
            return self.initial_investment * price_change_ratio
        
        @property
        def current_allocation_percentage(self):
            if not self.portfolio or self.portfolio.portfolio_value == 0:
                return 0.0
            return (self.current_value / self.portfolio.portfolio_value) * 100
        
        def to_dict(self):
            return {
                'id': self.id,
                'stock': self.stock.to_dict(),
                'allocation_percentage': self.allocation_percentage,
                'current_allocation_percentage': self.current_allocation_percentage,
                'initial_investment': self.initial_investment,
                'purchase_price': self.purchase_price,
                'purchase_date': self.purchase_date.isoformat() if self.purchase_date else None,
                'current_value': self.current_value,
                'cost_basis': self.cost_basis,
                'total_return': self.total_return,
                'total_return_percentage': self.total_return_percentage,
                'daily_return': self.daily_return,
                'daily_return_percentage': self.daily_return_percentage,
                'daily_return_value': self.daily_return_value
            }
    
    return PortfolioStock

