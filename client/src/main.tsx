import React from 'react'
import ReactDOM from 'react-dom/client'
import PipelineTopology from './pages/PipelineTopology'
import './index.css'

function App() {
  return <PipelineTopology />
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
