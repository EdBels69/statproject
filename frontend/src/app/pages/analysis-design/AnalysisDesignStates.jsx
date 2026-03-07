import Button from '../../components/ui/Button';
import ResearchFlowNav from '../../components/ResearchFlowNav';

export function DatasetPickerView({
  t,
  datasets,
  datasetsLoading,
  datasetsError,
  onSelectDataset,
  onUpload,
}) {
  return (
    <div className="min-h-[calc(100vh-120px)] flex items-center justify-center px-6 py-10">
      <div className="w-full max-w-3xl">
        <div className="mb-8">
          <ResearchFlowNav active="data" showMenu={false} />
        </div>
        <div className="mb-8">
          <div className="text-xs font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">{t('analysis_protocol')}</div>
          <h1 className="mt-3 text-3xl font-black text-[color:var(--text-primary)] leading-tight">{t('test_selection')}</h1>
          <p className="mt-2 text-sm text-[color:var(--text-secondary)] max-w-2xl">{t('select_tests_tooltip')}</p>
        </div>

        {datasetsError ? (
          <div className="mb-6 p-4 bg-[color:var(--white)] border border-[color:var(--black)] text-[color:var(--text-primary)] rounded-[2px] text-sm">
            {datasetsError}
          </div>
        ) : null}

        <div className="bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] overflow-hidden">
          <div className="px-6 py-4 border-b border-[color:var(--border-color)] flex items-center justify-between">
            <div className="text-sm font-semibold text-[color:var(--text-primary)]">{t('datasets')}</div>
            <Button onClick={onUpload} variant="primary" size="sm" type="button">
              {t('upload_dataset')}
            </Button>
          </div>

          <div className="p-3">
            {datasetsLoading ? (
              <div className="p-8 text-center text-[color:var(--text-secondary)] text-sm">{t('loading')}</div>
            ) : datasets.length === 0 ? (
              <div className="p-8 text-center text-[color:var(--text-secondary)] text-sm">{t('no_datasets_found')}</div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {datasets.map((ds) => (
                  <button
                    key={ds.id}
                    type="button"
                    onClick={() => onSelectDataset(ds.id)}
                    className="text-left p-4 rounded-[2px] border border-[color:var(--border-color)] hover:border-black hover:bg-[color:var(--bg-tertiary)] transition"
                  >
                    <div className="text-sm font-semibold text-[color:var(--text-primary)] truncate">{ds.filename || ds.name || ds.id}</div>
                    <div className="mt-1 text-xs text-[color:var(--text-secondary)] font-mono truncate">{ds.id}</div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export function DatasetLoadingView({ t }) {
  return (
    <div className="min-h-[calc(100vh-120px)] flex items-center justify-center px-6">
      <div className="w-full max-w-3xl animate-pulse">
        <div className="h-7 w-56 bg-[color:var(--gray-200)] rounded-[2px]" />
        <div className="mt-3 h-4 w-80 bg-[color:var(--gray-200)] rounded-[2px]" />
        <div className="mt-8 grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="h-24 bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px]" />
          <div className="h-24 bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px]" />
          <div className="h-24 bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px]" />
          <div className="h-24 bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px]" />
        </div>
        <div className="sr-only" aria-live="polite">{t('loading_dataset')}</div>
      </div>
    </div>
  );
}

export function DatasetErrorView({ t, error, onBack }) {
  return (
    <div className="min-h-[calc(100vh-120px)] flex items-center justify-center px-6">
      <div className="w-full max-w-xl p-6 bg-[color:var(--white)] border border-[color:var(--black)] rounded-[2px] text-sm text-[color:var(--text-primary)]">
        {error}
        <div className="mt-4">
          <button
            type="button"
            onClick={onBack}
            className="text-[color:var(--text-primary)] font-semibold underline underline-offset-4"
          >
            {t('back')}
          </button>
        </div>
      </div>
    </div>
  );
}
