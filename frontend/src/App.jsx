import { BrowserRouter, Routes, Route } from 'react-router-dom';
import MainLayout from './app/components/layout/MainLayout';
import DatasetList from './app/pages/DatasetList';
import Upload from './app/pages/Upload';
import DataPreparation from './app/pages/DataPreparation';
import AnalysisSelection from './app/pages/AnalysisSelection';
import ResultsTable from './app/pages/ResultsTable';
import ChartsPage from './app/pages/ChartsPage';
import ReportPreview from './app/pages/ReportPreview';
import Analyze from './app/pages/Analyze';

function App() {
  return (
    <BrowserRouter>
      <MainLayout>
        <Routes>
          {/* Page 1: Dataset Selection */}
          <Route path="/" element={<DatasetList />} />
          <Route path="/datasets" element={<DatasetList />} />
          <Route path="/upload" element={<Upload />} />

          {/* Page 2: Data Preparation */}
          <Route path="/data/:id" element={<DataPreparation />} />

          {/* Page 3: Analysis Selection */}
          <Route path="/analyze/:id" element={<AnalysisSelection />} />

          {/* Page 4: Results Table */}
          <Route path="/results/:id" element={<ResultsTable />} />

          {/* Page 5: Charts Customization */}
          <Route path="/charts/:id" element={<ChartsPage />} />

          {/* Page 6: Report Preview */}
          <Route path="/report-preview/:id" element={<ReportPreview />} />

          {/* Legacy: Manual analysis page */}
          <Route path="/manual/:id" element={<Analyze />} />
        </Routes>
      </MainLayout>
    </BrowserRouter>
  );
}

export default App
