import { BrowserRouter, Routes, Route, Navigate, useLocation, useParams } from 'react-router-dom';
import { I18nextProvider } from 'react-i18next';
import i18n from './lib/i18n';
import { LanguageProvider } from './contexts/LanguageContext';
import MainLayout from './app/components/layout/MainLayout';
import AnalysisErrorBoundary from './app/components/ErrorBoundary';
import DatasetList from './app/pages/DatasetList';
import Upload from './app/pages/Upload';
import AnalysisDesign from './app/pages/AnalysisDesign';
import ProtocolWizard from './app/pages/ProtocolWizard';
import Settings from './app/pages/Settings';
import Profile from './app/pages/Profile';
import StepResults from './app/pages/steps/StepResults';
import SampleSizeCalculator from './app/pages/SampleSizeCalculator';
import StatWiki from './app/pages/StatWiki';

function AnalyzeRedirect() {
  const { id } = useParams();
  const location = useLocation();
  return <Navigate to={`/results/${id}`} replace state={location.state} />;
}

function ProtocolRunRoute({ mode }) {
  const { id } = useParams();
  const location = useLocation();

  const runIdFromState = location.state?.runId;
  const params = new URLSearchParams(location.search);
  const runIdFromQuery = params.get('run') || params.get('run_id');
  const runId = runIdFromQuery || runIdFromState || null;

  const localKey = params.get('local');
  let localPayload = null;
  if (!runId && localKey) {
    try {
      const raw = sessionStorage.getItem(`statproject_wizard_run_${localKey}`);
      localPayload = raw ? JSON.parse(raw) : null;
    } catch {
      localPayload = null;
    }
  }

  if (!runId && !localPayload) {
    return <Navigate to={`/design/${id}`} replace state={location.state} />;
  }

  return (
    <StepResults
      runId={runId}
      datasetId={id}
      mode={mode}
      localKey={localKey}
      initialResults={localPayload?.results || null}
      wizardContext={localPayload?.wizard || null}
    />
  );
}

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
                <Route path="/prep/:id" element={<Profile />} />
                <Route path="/prepare/:id" element={<Profile />} />
                <Route path="/profile/:id" element={<Profile />} />
                <Route path="/analyze/:id" element={<AnalyzeRedirect />} />
                <Route path="/results/:id" element={<ProtocolRunRoute mode="results" />} />
                <Route path="/graphs/:id" element={<ProtocolRunRoute mode="graphs" />} />
                <Route path="/report/:id" element={<ProtocolRunRoute mode="report" />} />
                <Route path="/tests" element={<AnalysisDesign mode="tests" />} />
                <Route path="/tests/:id" element={<AnalysisDesign mode="tests" />} />
                <Route path="/wizard" element={<AnalysisDesign />} />
                <Route path="/design" element={<AnalysisDesign />} />
                <Route path="/design/:id" element={<AnalysisDesign />} />
                <Route path="/ai" element={<ProtocolWizard />} />
                <Route path="/protocol" element={<ProtocolWizard />} />
                <Route path="/calculator" element={<SampleSizeCalculator />} />
                <Route path="/wiki" element={<StatWiki />} />
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
