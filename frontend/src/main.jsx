import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

if (import.meta.env.DEV) {
  window.addEventListener('error', (event) => {
    const message = event?.error?.message || event?.message || 'Unknown global error'
    console.error('[global-error]', message, event?.error || '')
  })
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
