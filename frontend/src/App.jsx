import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { I18nextProvider } from 'react-i18next';
import i18n from './lib/i18n';
import { LanguageProvider } from './contexts/LanguageContext';
import MainLayout from './app/components/layout/MainLayout';
import AnalysisErrorBoundary from './app/components/ErrorBoundary';
import DatasetList from './app/pages/DatasetList';
import Upload from './app/pages/Upload';
import Analyze from './app/pages/Analyze';
import AnalysisDesign from './app/pages/AnalysisDesign';
import Settings from './app/pages/Settings';
import Profile from './app/pages/Profile';

function App() {
  return (
    <I18nextProvider i18n={i18n}>
      <LanguageProvider>
        <BrowserRouter>
          <AnalysisErrorBoundary>
            <MainLayout>
              <Routes>
                <Route path="/" element={<DatasetList />} />
                <Route path="/datasets" element={<DatasetList />} />
                <Route path="/upload" element={<Upload />} />
                <Route path="/profile/:id" element={<Profile />} />
                <Route path="/analyze/:id" element={<Analyze />} />
                <Route path="/report/:id" element={<Analyze />} />
                <Route path="/wizard" element={<AnalysisDesign />} />
                <Route path="/design" element={<AnalysisDesign />} />
                <Route path="/design/:id" element={<AnalysisDesign />} />
                <Route path="/settings" element={<Settings />} />
              </Routes>
            </MainLayout>
          </AnalysisErrorBoundary>
        </BrowserRouter>
      </LanguageProvider>
    </I18nextProvider>
  );
}

export default App
