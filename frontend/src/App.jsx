import { BrowserRouter, Routes, Route, Navigate, useLocation, useParams } from 'react-router-dom';
import { Suspense, lazy } from 'react';
import { I18nextProvider } from 'react-i18next';
import i18n from './lib/i18n';
import { LanguageProvider } from './contexts/LanguageContext';
import MainLayout from './app/components/layout/MainLayout';
import AnalysisErrorBoundary from './app/components/ErrorBoundary';

const DatasetList = lazy(() => import('./app/pages/DatasetList'));
const Upload = lazy(() => import('./app/pages/Upload'));
const AnalysisDesign = lazy(() => import('./app/pages/AnalysisDesign'));
const Analyze = lazy(() => import('./app/pages/Analyze'));
const ProtocolSorcerer = lazy(() => import('./app/pages/ProtocolSorcerer'));
const Settings = lazy(() => import('./app/pages/Settings'));
const Profile = lazy(() => import('./app/pages/Profile'));
const StudySetup = lazy(() => import('./app/pages/StudySetup'));
const SampleSizeCalculator = lazy(() => import('./app/pages/SampleSizeCalculator'));
const StatWiki = lazy(() => import('./app/pages/StatWiki'));
const CopilotPage = lazy(() => import('./features/copilot/CopilotPage'));
const PromptBuilder = lazy(() => import('./app/pages/PromptBuilder'));

function AnalyzeRedirect() {
  const { id } = useParams();
  const location = useLocation();
  return <Navigate to={`/results/${id}`} replace state={location.state} />;
}

function AutoAnalystRedirect() {
  return <Navigate to="/copilot" replace />;
}

function PrepareRedirect() {
  const { id } = useParams();
  const location = useLocation();
  return <Navigate to={`/prepare/${id}`} replace state={location.state} />;
}

function App() {
  return (
    <I18nextProvider i18n={i18n}>
      <LanguageProvider>
        <BrowserRouter>
          <AnalysisErrorBoundary>
            <MainLayout>
              <Suspense fallback={<div className="px-6 py-10 text-sm text-zinc-500">Загрузка…</div>}>
                <Routes>
                  <Route path="/" element={<DatasetList />} />
                  <Route path="/datasets" element={<DatasetList />} />
                  <Route path="/upload" element={<Upload />} />
                  <Route path="/prep/:id" element={<PrepareRedirect />} />
                  <Route path="/prepare/:id" element={<Profile />} />
                  <Route path="/profile/:id" element={<Profile />} />
                  <Route path="/study-setup/:id" element={<StudySetup />} />
                  <Route path="/analyze/:id" element={<AnalyzeRedirect />} />
                  <Route path="/results/:id" element={<Analyze />} />
                  <Route path="/graphs/:id" element={<Analyze />} />
                  <Route path="/report/:id" element={<Analyze />} />
                  <Route path="/tests" element={<AnalysisDesign mode="tests" />} />
                  <Route path="/tests/:id" element={<AnalysisDesign mode="tests" />} />
                  <Route path="/sorcerer" element={<ProtocolSorcerer />} />
                  <Route path="/design" element={<AnalysisDesign />} />
                  <Route path="/design/:id" element={<AnalysisDesign />} />
                  <Route path="/ai" element={<AnalysisDesign mode="ai" />} />
                  <Route path="/ai/:id" element={<AnalysisDesign mode="ai" />} />
                  <Route path="/protocol" element={<AnalysisDesign mode="protocol" />} />
                  <Route path="/protocol/:id" element={<AnalysisDesign mode="protocol" />} />
                  <Route path="/calculator" element={<SampleSizeCalculator />} />
                  <Route path="/wiki" element={<StatWiki />} />
                  <Route path="/settings" element={<Settings />} />
                  <Route path="/prompt-builder" element={<PromptBuilder />} />
                  <Route path="/auto-analyst" element={<AutoAnalystRedirect />} />
                  <Route path="/copilot" element={<CopilotPage />} />
                </Routes>
              </Suspense>
            </MainLayout>
          </AnalysisErrorBoundary>
        </BrowserRouter>
      </LanguageProvider>
    </I18nextProvider>
  );
}

export default App
