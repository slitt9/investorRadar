import { useState } from 'react'
import axios from 'axios'
import './StockSearch.css'

const API_BASE = '/api'

function StockSearch({ onTickerSelect }) {
  const [ticker, setTicker] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!ticker.trim()) return

    setLoading(true)
    setError(null)

    try {
      const response = await axios.get(`${API_BASE}/stock/${ticker.toUpperCase()}`)
      onTickerSelect(ticker.toUpperCase(), response.data)
    } catch (err) {
      setError(err.response?.data?.message || 'Stock not found. Please try another ticker.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="stock-search">
      <form onSubmit={handleSubmit} className="search-form">
        <input
          type="text"
          value={ticker}
          onChange={(e) => setTicker(e.target.value.toUpperCase())}
          placeholder="Enter stock ticker (e.g., AAPL, MSFT, GOOGL)"
          className="search-input"
          disabled={loading}
        />
        <button type="submit" className="search-button" disabled={loading}>
          {loading ? 'Loading...' : 'Search'}
        </button>
      </form>
      {error && <div className="error-message">{error}</div>}
    </div>
  )
}

export default StockSearch

