import { useState } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Upload from './app/pages/Upload';
import Profile from './app/pages/Profile';
import Analyze from './app/pages/Analyze';

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-slate-50">
        <header className="bg-white shadow-sm border-b border-slate-200">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center">
            <h1 className="text-xl font-bold text-slate-800">📊 Stat Analyzer MVP</h1>
          </div>
        </header>
        <main className="py-10">
          <Routes>
            <Route path="/" element={<Upload />} />
            <Route path="/profile/:id" element={<Profile />} />
            <Route path="/analyze/:id" element={<Analyze />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}

export default App
