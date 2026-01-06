import { useState } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import MainLayout from './app/components/layout/MainLayout';
import DatasetList from './app/pages/DatasetList';
import Upload from './app/pages/Upload';
import Analyze from './app/pages/Analyze';
import NewWizard from './app/pages/NewWizard';

function App() {
  return (
    <BrowserRouter>
      <MainLayout>
        <Routes>
          <Route path="/" element={<DatasetList />} />
          <Route path="/datasets" element={<DatasetList />} />
          <Route path="/upload" element={<Upload />} />
          <Route path="/analyze/:id" element={<Analyze />} />
          <Route path="/wizard" element={<NewWizard />} />
        </Routes>
      </MainLayout>
    </BrowserRouter>
  );
}

export default App
