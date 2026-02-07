import { useState, useEffect } from 'react'
import axios from 'axios'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import './StockChart.css'

const API_BASE = '/api'

const PERIODS = [
  { label: '1 Day', value: '1d' },
  { label: '1 Week', value: '1w' },
  { label: '3 Months', value: '3m' },
  { label: '1 Year', value: '1y' }
]

function StockChart({ ticker, stockData }) {
  const [chartData, setChartData] = useState([])
  const [selectedPeriod, setSelectedPeriod] = useState('1d')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetchChartData(selectedPeriod)
  }, [ticker, selectedPeriod])

  const fetchChartData = async (period) => {
    setLoading(true)
    setError(null)

    try {
      const response = await axios.get(`${API_BASE}/stock/${ticker}/history`, {
        params: { period }
      })
      
      const formattedData = response.data.data.map(item => ({
        date: new Date(item.date).toLocaleDateString(),
        price: item.close,
        fullDate: item.date
      }))
      
      setChartData(formattedData)
    } catch (err) {
      setError('Failed to load chart data')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const formatPrice = (value) => {
    return `$${value.toFixed(2)}`
  }

  const formatDate = (tickItem) => {
    if (!tickItem) return ''
    const date = new Date(tickItem)
    if (selectedPeriod === '1d') {
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }
    return date.toLocaleDateString([], { month: 'short', day: 'numeric' })
  }

  return (
    <div className="stock-chart-container">
      <div className="stock-info-card">
        <div className="stock-header">
          <h2>{stockData.name}</h2>
          <span className="ticker">{ticker}</span>
        </div>
        <div className="stock-metrics">
          <div className="metric">
            <span className="metric-label">Current Price</span>
            <span className="metric-value">${stockData.close?.toFixed(2) || 'N/A'}</span>
          </div>
          <div className="metric">
            <span className="metric-label">Daily Return</span>
            <span className={`metric-value ${stockData.daily_return_percentage >= 0 ? 'positive' : 'negative'}`}>
              {stockData.daily_return_percentage?.toFixed(2) || '0.00'}%
            </span>
          </div>
          <div className="metric">
            <span className="metric-label">Volume</span>
            <span className="metric-value">
              {stockData.volume?.toLocaleString() || 'N/A'}
            </span>
          </div>
          <div className="metric">
            <span className="metric-label">Market Cap</span>
            <span className="metric-value">
              ${stockData.market_cap_basic ? (stockData.market_cap_basic / 1e9).toFixed(2) + 'B' : 'N/A'}
            </span>
          </div>
        </div>
      </div>

      <div className="chart-card">
        <div className="chart-header">
          <h3>Price Chart</h3>
          <div className="period-selector">
            {PERIODS.map(period => (
              <button
                key={period.value}
                className={`period-button ${selectedPeriod === period.value ? 'active' : ''}`}
                onClick={() => setSelectedPeriod(period.value)}
              >
                {period.label}
              </button>
            ))}
          </div>
        </div>

        {loading ? (
          <div className="loading">Loading chart data...</div>
        ) : error ? (
          <div className="error">{error}</div>
        ) : chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height={400}>
            <LineChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
              <XAxis 
                dataKey="date" 
                stroke="#666"
                tick={{ fill: '#666' }}
              />
              <YAxis 
                stroke="#666"
                tick={{ fill: '#666' }}
                tickFormatter={formatPrice}
              />
              <Tooltip 
                formatter={(value) => formatPrice(value)}
                contentStyle={{ 
                  backgroundColor: '#fff', 
                  border: '1px solid #ccc',
                  borderRadius: '8px'
                }}
              />
              <Line 
                type="monotone" 
                dataKey="price" 
                stroke="#667eea" 
                strokeWidth={2}
                dot={{ fill: '#667eea', r: 4 }}
                activeDot={{ r: 6 }}
              />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="no-data">No chart data available</div>
        )}
      </div>
    </div>
  )
}

export default StockChart

