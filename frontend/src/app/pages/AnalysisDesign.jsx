import { lazy, Suspense } from 'react';

const AnalysisAIDesign = lazy(() => import('./analysis-design/AnalysisAIDesign'));
const AnalysisDesignLegacy = lazy(() => import('./AnalysisDesignLegacy'));

function LoadingShell() {
  return (
    <div className="min-h-[calc(100vh-120px)] flex items-center justify-center text-sm text-[color:var(--text-secondary)]">
      Загрузка конструктора...
    </div>
  );
}

const AnalysisDesign = ({ mode = 'design' }) => {
  return (
    <Suspense fallback={<LoadingShell />}>
      {mode === 'ai' ? (
        <AnalysisAIDesign />
      ) : mode === 'tests' ? (
        <AnalysisDesignLegacy mode="tests" />
      ) : mode === 'protocol' ? (
        <AnalysisDesignLegacy mode="protocol" />
      ) : (
        <AnalysisDesignLegacy mode="design" />
      )}
    </Suspense>
  );
};

export default AnalysisDesign;
