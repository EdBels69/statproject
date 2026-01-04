import { useState } from 'react';
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import Upload from './app/pages/Upload';
import Profile from './app/pages/Profile';
import Analyze from './app/pages/Analyze';
import ProtocolWizard from './app/pages/ProtocolWizard';

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen flex flex-col" style={{ background: 'var(--bg-primary)' }}>
        {/* Header */}
        <header style={{
          background: 'var(--bg-secondary)',
          borderBottom: '1px solid var(--border-color)',
          height: '56px',
          display: 'flex',
          alignItems: 'center',
          padding: '0 24px',
          justifyContent: 'space-between'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{
              width: '32px',
              height: '32px',
              background: 'var(--accent)',
              borderRadius: '6px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 'bold',
              color: '#000',
              fontSize: '14px'
            }}>SA</div>
            <span style={{ fontWeight: '600', color: 'var(--text-primary)', fontSize: '15px' }}>
              Stat Analyzer
            </span>
          </div>

          <nav style={{ display: 'flex', gap: '8px' }}>
            <NavLink
              to="/"
              style={({ isActive }) => ({
                padding: '8px 16px',
                borderRadius: '6px',
                fontSize: '14px',
                fontWeight: '500',
                textDecoration: 'none',
                color: isActive ? 'var(--accent)' : 'var(--text-secondary)',
                background: isActive ? 'rgba(249, 115, 22, 0.1)' : 'transparent',
                transition: 'all 0.15s'
              })}
            >
              Upload
            </NavLink>
            <NavLink
              to="/wizard"
              style={({ isActive }) => ({
                padding: '8px 16px',
                borderRadius: '6px',
                fontSize: '14px',
                fontWeight: '500',
                textDecoration: 'none',
                color: isActive ? 'var(--accent)' : 'var(--text-secondary)',
                background: isActive ? 'rgba(249, 115, 22, 0.1)' : 'transparent',
                transition: 'all 0.15s'
              })}
            >
              Protocol Wizard
            </NavLink>
          </nav>
        </header>

        {/* Main Content */}
        <main style={{ flex: 1, padding: '32px' }}>
          <Routes>
            <Route path="/" element={<Upload />} />
            <Route path="/profile/:id" element={<Profile />} />
            <Route path="/analyze/:id" element={<Analyze />} />
            <Route path="/wizard" element={<ProtocolWizard />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}

export default App
