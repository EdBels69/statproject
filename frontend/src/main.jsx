import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

// Debug Logger
window.onerror = function (msg, url, line, col, error) {
  const div = document.createElement('div');
  div.style.position = 'fixed';
  div.style.top = '0';
  div.style.left = '0';
  div.style.backgroundColor = 'red';
  div.style.color = 'white';
  div.style.zIndex = '99999';
  div.style.padding = '20px';
  div.innerText = `Global Error: ${msg} at ${line}:${col}`;
  document.body.appendChild(div);
};

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
