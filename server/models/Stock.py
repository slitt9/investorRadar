def create_stock_model(db):
    class Stock(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        ticker = db.Column(db.String(10), unique=True, nullable=False)
        name = db.Column(db.String(100), nullable=False)
        close = db.Column(db.Float, nullable=False)
        volume = db.Column(db.Integer, nullable=False)
        market_cap_basic = db.Column(db.Integer, nullable=False)
        previous_close = db.Column(db.Float)
        last_updated = db.Column(db.DateTime, default=db.func.now())
        
        def __repr__(self):
            return f"Stock(ticker={self.ticker}, name={self.name}, close={self.close})"
        
        @property
        def daily_return(self):
            if not self.previous_close:
                return 0.0
            return self.close - self.previous_close
        
        @property
        def daily_return_percentage(self):
            if not self.previous_close or self.previous_close == 0:
                return 0.0
            return ((self.close - self.previous_close) / self.previous_close) * 100
        
        def update_price(self, new_price, db_session):
            self.previous_close = self.close
            self.close = new_price
            self.last_updated = db.func.now()
            db_session.commit()
        
        def to_dict(self):
            return {
                'id': self.id,
                'ticker': self.ticker,
                'name': self.name,
                'close': self.close,
                'volume': self.volume,
                'market_cap_basic': self.market_cap_basic,
                'previous_close': self.previous_close,
                'daily_return': self.daily_return,
                'daily_return_percentage': self.daily_return_percentage,
                'last_updated': self.last_updated.isoformat() if self.last_updated else None
            }
    
    return Stock