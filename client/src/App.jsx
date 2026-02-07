import { useState } from 'react'
import StockSearch from './components/StockSearch'
import StockChart from './components/StockChart'
import './App.css'

function App() {
  const [selectedTicker, setSelectedTicker] = useState(null)
  const [stockData, setStockData] = useState(null)

  const handleTickerSelect = (ticker, data) => {
    setSelectedTicker(ticker)
    setStockData(data)
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>InvestorRadar</h1>
        <p>Stock Market Analysis Platform</p>
      </header>
      <main className="app-main">
        <StockSearch onTickerSelect={handleTickerSelect} />
        {selectedTicker && stockData && (
          <StockChart ticker={selectedTicker} stockData={stockData} />
        )}
      </main>
    </div>
  )
}

export default App

