import React, { useState, useEffect } from 'react'
import ReactDOM from 'react-dom/client'
import Overview from './pages/Overview'
import Pipeline from './pages/Pipeline'
import PipelineTopology from './pages/PipelineTopology'
import './index.css'

function App() {
  const getPage = () => {
    const hash = window.location.hash
    if (hash === '#/overview') return 'overview'
    if (hash === '#/topology') return 'topology'
    return 'pipeline'
  }

  const [page, setPage] = useState(getPage)

  useEffect(() => {
    const onHash = () => setPage(getPage())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  return page === 'topology' ? <PipelineTopology /> : page === 'overview' ? <Overview /> : <Pipeline />
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
