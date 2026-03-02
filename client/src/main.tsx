import React from 'react'
import ReactDOM from 'react-dom/client'
import Discovery from './pages/Discovery'
import './index.css'

function App() {
  return <Discovery />
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
