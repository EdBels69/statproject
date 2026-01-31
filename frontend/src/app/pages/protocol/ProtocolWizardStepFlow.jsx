import ProtocolWizardOptionCard from './ProtocolWizardOptionCard';
import Button from '../../components/ui/Button';
import { useTranslation } from '../../../hooks/useTranslation';

export default function ProtocolWizardStepFlow({
  step,
  datasets,
  manualMethodOptions,
  onSelect,
  onPickMethod,
  onDatasetSelect,
  onBack,
  onOpenDesign,
  loading,
  aiMode = false,
}) {
  const { t } = useTranslation();

  return (
    <div className="bg-[color:var(--white)] p-8 border border-[color:var(--border-color)] rounded-[2px] relative overflow-hidden min-h-[400px]">
      {loading && (
        <div className="absolute inset-0 z-50 bg-[color:color-mix(in_oklab,var(--white)_90%,transparent)] backdrop-blur-sm flex flex-col items-center justify-center animate-in fade-in duration-300">
          <div className="relative w-24 h-24 mb-8">
            <div className="absolute inset-0 border-4 border-[color:var(--bg-secondary)] rounded-full"></div>
            <div className="absolute inset-0 border-4 border-[color:var(--accent)] rounded-full border-t-transparent animate-spin"></div>
            <div className="absolute inset-4 bg-gradient-to-tr from-purple-500 to-[color:var(--accent)] rounded-full blur-xl opacity-20 animate-pulse"></div>
            <div className="absolute inset-0 flex items-center justify-center text-2xl animate-bounce">
              🧠
            </div>
          </div>
          <h3 className="text-xl font-black text-[color:var(--text-primary)] mb-2 tracking-tight">
            AI ULTRATHINK
          </h3>
          <p className="text-sm text-[color:var(--text-secondary)] font-mono animate-pulse">
            Analyzing dimensionality & generating massive protocol...
          </p>
        </div>
      )}

      {step > 0 && (
        <div className="flex gap-2 mb-10">
          {[1, 2, 3, 4, 5].map((s) => (
            <div key={s} className={`h-1.5 flex-1 rounded-[2px] transition-colors ${s <= step ? 'bg-[color:var(--accent)]' : 'bg-[color:var(--bg-secondary)]'}`} />
          ))}
        </div>
      )}

      {step === 0 && (
        <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] text-[color:var(--accent)] mb-4">
              <span className="text-3xl">📊</span>
            </div>
            <h2 className="text-2xl font-bold text-[color:var(--text-primary)]">{t('protocol_step_data_title')}</h2>
            <p className="text-[color:var(--text-secondary)] mt-2">{t('protocol_step_data_desc')}</p>
          </div>

          <div className="grid grid-cols-1 gap-3">
            {datasets.length === 0 ? (
              <div className="p-10 border border-dashed border-[color:var(--border-color)] rounded-[2px] text-center text-[color:var(--text-secondary)]">
                {t('protocol_step_data_empty')}
              </div>
            ) : (
              datasets.map((ds) => (
                <button
                  key={ds.id}
                  onClick={() => onDatasetSelect(ds)}
                  className="flex items-center justify-between p-4 border border-[color:var(--border-color)] rounded-[2px] hover:border-[color:var(--accent)] hover:bg-[color:var(--bg-secondary)] transition-colors text-left group"
                >
                  <div className="flex items-center gap-4">
                    <div className="w-10 h-10 bg-[color:var(--bg-secondary)] rounded-[2px] border border-[color:var(--border-color)] flex items-center justify-center transition-colors">📄</div>
                    <div>
                      <div className="font-bold text-[color:var(--text-primary)]">{ds.filename}</div>
                      <div className="text-xs text-[color:var(--text-secondary)] font-mono">{ds.id.slice(0, 8)}...</div>
                    </div>
                  </div>
                  <span className="text-[color:var(--accent)] font-bold opacity-0 group-hover:opacity-100 transition-opacity">{t('protocol_step_select_action')}</span>
                </button>
              ))
            )}
          </div>
        </div>
      )}

      {step === 1 && (
        <div className="animate-in fade-in slide-in-from-right-4 duration-350">
          <h2 className="text-xl font-bold mb-6 text-[color:var(--text-primary)]">{t('protocol_step_goal_title')}</h2>
          
          <div className="mb-6 relative group">
            <div className="absolute -inset-0.5 bg-gradient-to-r from-[color:var(--accent)] to-purple-600 rounded-[4px] blur opacity-25 group-hover:opacity-75 transition duration-500"></div>
            <ProtocolWizardOptionCard
              icon="🚀"
              title={t('protocol_goal_auto_title')}
              desc={t('protocol_goal_auto_desc')}
              onClick={() => onSelect('goal', 'auto_design')}
              className="relative bg-[color:var(--bg-secondary)] border-[color:var(--accent)] hover:border-transparent"
            />
            <div className="absolute top-2 right-2">
              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-800">
                {t('ai_powered_badge')}
              </span>
            </div>
          </div>

          {!aiMode && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <ProtocolWizardOptionCard
                icon="⚔️"
                title={t('protocol_goal_compare_groups_title')}
                desc={t('protocol_goal_compare_groups_desc')}
                onClick={() => onSelect('goal', 'compare_groups')}
              />
              <ProtocolWizardOptionCard
                icon="⏱️"
                title={t('protocol_goal_compare_timepoints_title')}
                desc={t('protocol_goal_compare_timepoints_desc')}
                onClick={() => onSelect('goal', 'compare_timepoints')}
              />
              <ProtocolWizardOptionCard
                icon="🔗"
                title={t('protocol_goal_relationship_title')}
                desc={t('protocol_goal_relationship_desc')}
                onClick={() => onSelect('goal', 'relationship')}
              />
              <ProtocolWizardOptionCard
                icon="📈"
                title={t('protocol_goal_forecast_title')}
                desc={t('protocol_goal_forecast_desc')}
                disabled
              />
              <ProtocolWizardOptionCard
                icon="⏳"
                title={t('protocol_goal_survival_title')}
                desc={t('protocol_goal_survival_desc')}
                onClick={() => onSelect('goal', 'survival')}
              />
              <ProtocolWizardOptionCard
                icon="🔮"
                title={t('protocol_goal_prediction_title')}
                desc={t('protocol_goal_prediction_desc')}
                onClick={() => onSelect('goal', 'prediction')}
              />
            </div>
          )}
        </div>
      )}

      {step === 2 && (
        <div className="animate-in fade-in slide-in-from-right-4 duration-350">
          <h2 className="text-xl font-bold mb-6 text-[color:var(--text-primary)]">{t('protocol_step_structure_title')}</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <ProtocolWizardOptionCard
              icon="👥"
              title={t('protocol_structure_independent_title')}
              desc={t('protocol_structure_independent_desc')}
              onClick={() => onSelect('structure', 'independent')}
            />
            <ProtocolWizardOptionCard
              icon="🔄"
              title={t('protocol_structure_paired_title')}
              desc={t('protocol_structure_paired_desc')}
              onClick={() => onSelect('structure', 'paired')}
            />
          </div>
        </div>
      )}

      {step === 3 && (
        <div className="animate-in fade-in slide-in-from-right-4 duration-350">
          <h2 className="text-xl font-bold mb-6 text-[color:var(--text-primary)]">{t('protocol_step_data_type_title')}</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <ProtocolWizardOptionCard
              icon="📏"
              title={t('protocol_data_type_numeric_title')}
              desc={t('protocol_data_type_numeric_desc')}
              onClick={() => onSelect('data_type', 'numeric')}
            />
            <ProtocolWizardOptionCard
              icon="🏷️"
              title={t('protocol_data_type_categorical_title')}
              desc={t('protocol_data_type_categorical_desc')}
              onClick={() => onSelect('data_type', 'categorical')}
            />
          </div>
        </div>
      )}

      {step === 4 && (
        <div className="animate-in fade-in slide-in-from-right-4 duration-350">
          <h2 className="text-xl font-bold mb-6 text-[color:var(--text-primary)]">{t('protocol_step_groups_title')}</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <ProtocolWizardOptionCard
              icon="🏘️"
              title={t('protocol_groups_two_title')}
              desc={t('protocol_groups_two_desc')}
              onClick={() => onSelect('groups', '2')}
            />
            <ProtocolWizardOptionCard
              icon="🏘️🏘️"
              title={t('protocol_groups_many_title')}
              desc={t('protocol_groups_many_desc')}
              onClick={() => onSelect('groups', '>2')}
            />
          </div>
        </div>
      )}

      {step === 5 && (
        <div className="animate-in fade-in slide-in-from-right-4 duration-350">
          <h2 className="text-xl font-bold mb-6 text-[color:var(--text-primary)]">{t('protocol_step_method_title')}</h2>
          <div className="mb-4 flex items-center justify-between gap-4 flex-wrap">
            <div className="text-xs text-[color:var(--text-secondary)] max-w-xl">
              {t('protocol_step_method_desc')}
            </div>
            <Button variant="ghost" onClick={onOpenDesign} className="px-4">
              {t('protocol_step_open_builder')}
            </Button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {manualMethodOptions.map((m) => (
              <ProtocolWizardOptionCard
                key={m.method_id}
                icon={m.method_id === 'kruskal' || m.method_id === 'mann_whitney' || m.method_id === 'wilcoxon' || m.method_id === 'friedman' || m.method_id === 'spearman' || m.method_id === 'fisher' ? '⬛' : '⬜'}
                title={m.name}
                desc={m.description}
                onClick={() => onPickMethod(m)}
              />
            ))}
          </div>
        </div>
      )}

      {step > 0 && (
        <button
          onClick={onBack}
          className="mt-8 px-4 py-2 text-sm text-[color:var(--text-secondary)] hover:text-[color:var(--accent)] hover:bg-[color:var(--bg-secondary)] rounded-[2px] border border-transparent hover:border-[color:var(--border-color)] transition-colors"
        >
          {t('protocol_step_back')}
        </button>
      )}
    </div>
  );
}
