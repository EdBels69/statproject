import { useState, useEffect, lazy, Suspense, useMemo } from 'react';
import { getWizardRecommendation, applyStrategy, listDatasets, getDataset, exportReport, exportDocx } from '../../lib/api';
import Badge from '../components/ui/Badge';
import Button from '../components/ui/Button';

const AnalyticsChart = lazy(() => import('../components/AnalyticsChart'));

export default function ProtocolWizard() {
  const [step, setStep] = useState(0); // Step 0: Dataset Selection
  const [datasets, setDatasets] = useState([]);
  const [selectedDataset, setSelectedDataset] = useState(null);
  const [columns, setColumns] = useState([]);

  const [selections, setSelections] = useState({
    goal: '',
    structure: '',
    data_type: '',
    groups: '',
    normal_distribution: true
  });

  const [recommendation, setRecommendation] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showApplyForm, setShowApplyForm] = useState(false);
  const [variables, setVariables] = useState({ target: '', group: '', event: '' });
  const [analysisResult, setAnalysisResult] = useState(null);

  const chartFallback = useMemo(() => (
    <div className="animate-pulse" style={{
      height: 400,
      borderRadius: '2px',
      border: '1px solid var(--border-color)',
      background: 'var(--white)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      color: 'var(--text-secondary)',
      fontSize: '12px',
      fontWeight: 800,
      letterSpacing: '0.18em',
      textTransform: 'uppercase'
    }}>
      Loading chart
    </div>
  ), []);

  useEffect(() => {
    loadDatasets();
  }, []);

  const loadDatasets = async () => {
    try {
      const list = await listDatasets();
      setDatasets(list);
    } catch (e) {
      console.error(e);
    }
  };

  const handleDatasetSelect = async (ds) => {
    setSelectedDataset(ds);
    setLoading(true);
    try {
      const data = await getDataset(ds.id);
      setColumns(data.columns || []);
      setStep(1);
    } catch (e) {
      alert("Failed to load columns: " + e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSelect = (key, value) => {
    const newSelections = { ...selections, [key]: value };
    setSelections(newSelections);

    // Logic for steps
    if (key === 'goal') {
      if (value === 'compare_groups') setStep(2);
      else if (value === 'relationship') setStep(3);
      else setStep(5); // consult
    }
    else if (step === 2) setStep(3); // structure -> data_type
    else if (step === 3) {
      if (newSelections.goal === 'compare_groups') setStep(4); // data_type -> groups
      else handleSubmit(newSelections); // relationship -> finish
    }
    else if (step === 4) handleSubmit(newSelections);
  };

  const handleSubmit = async (finalSelections) => {
    setLoading(true);
    try {
      const res = await getWizardRecommendation(finalSelections);
      setRecommendation(res);
    } catch (e) {
      console.error(e);
      alert("Recommendation failed: " + e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleApply = async () => {
    if (!variables.target || (!variables.group && !variables.predictors)) {
      alert("Please select required variables");
      return;
    }
    setLoading(true);
    try {
      const res = await applyStrategy({
        recommendation: recommendation,
        variables: variables,
        dataset_id: selectedDataset.id
      });
      setAnalysisResult(res.results);
    } catch (e) {
      console.error(e);
      alert("Analysis failed: " + e.message);
    } finally {
      setLoading(false);
    }
  };

  const handlePredictorToggle = (colName) => {
    setVariables(prev => {
      const current = prev.predictors ? prev.predictors.split(',').filter(x => x) : [];
      const next = current.includes(colName)
        ? current.filter(c => c !== colName)
        : [...current, colName];
      return { ...prev, predictors: next.join(',') };
    });
  };

  const handleDownloadReport = async () => {
    if (!analysisResult || !selectedDataset) return;
    try {
      const blob = await exportReport({
        results: analysisResult,
        variables,
        dataset_id: selectedDataset.id
      });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `Clinical_Report_${selectedDataset.id}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
    } catch {
      alert('Failed to download report');
    }
  };

  const handleDownloadReportDocx = async () => {
    if (!analysisResult || !selectedDataset) return;
    try {
      const blob = await exportDocx({
        dataset_name: selectedDataset.filename || selectedDataset.id,
        filename: `Clinical_Report_${selectedDataset.id}.docx`,
        results: {
          protocol_name: 'Clinical Report',
          results: {
            analysis: analysisResult
          }
        }
      });

      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `Clinical_Report_${selectedDataset.id}.docx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      alert('Failed to download DOCX report');
    }
  };

  const reset = () => {
    setStep(0);
    setSelections({
      goal: '', structure: '', data_type: '', groups: '', normal_distribution: true
    });
    setRecommendation(null);
    setShowApplyForm(false);
    setAnalysisResult(null);
    setVariables({ target: '', group: '', event: '' });
    setSelectedDataset(null);
  };

  return (
    <div className="max-w-4xl mx-auto px-4 pb-20">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-bold text-[color:var(--text-primary)] flex items-center gap-2">
          🧙‍♂️ Clinical Protocol Wizard
        </h1>
        {selectedDataset && (
          <Badge variant="accent">
            Dataset: <span className="font-bold">{selectedDataset.filename}</span>
          </Badge>
        )}
      </div>

      {!recommendation ? (
        <div className="bg-[color:var(--white)] p-8 border border-[color:var(--border-color)] rounded-[2px] relative overflow-hidden">
          {/* Progress Bar (if step > 0) */}
          {step > 0 && (
            <div className="flex gap-2 mb-10">
              {[1, 2, 3, 4].map(s => (
                <div key={s} className={`h-1.5 flex-1 rounded-[2px] transition-colors ${s <= step ? 'bg-[color:var(--accent)]' : 'bg-[color:var(--bg-secondary)]'}`} />
              ))}
            </div>
          )}

          {/* STEP 0: DATASET SELECTION */}
          {step === 0 && (
            <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
              <div className="text-center mb-8">
                <div className="inline-flex items-center justify-center w-16 h-16 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] text-[color:var(--accent)] mb-4">
                  <span className="text-3xl">📊</span>
                </div>
                <h2 className="text-2xl font-bold text-[color:var(--text-primary)]">Choose your data source</h2>
                <p className="text-[color:var(--text-secondary)] mt-2">Select a dataset to begin the guided protocol design</p>
              </div>

              <div className="grid grid-cols-1 gap-3">
                {datasets.length === 0 ? (
                  <div className="p-10 border border-dashed border-[color:var(--border-color)] rounded-[2px] text-center text-[color:var(--text-secondary)]">
                    No datasets found. Please upload one in the Datasets tab first.
                  </div>
                ) : (
                  datasets.map(ds => (
                    <button
                      key={ds.id}
                      onClick={() => handleDatasetSelect(ds)}
                      className="flex items-center justify-between p-4 border border-[color:var(--border-color)] rounded-[2px] hover:border-[color:var(--accent)] hover:bg-[color:var(--bg-secondary)] transition-colors text-left group"
                    >
                      <div className="flex items-center gap-4">
                        <div className="w-10 h-10 bg-[color:var(--bg-secondary)] rounded-[2px] border border-[color:var(--border-color)] flex items-center justify-center transition-colors">📄</div>
                        <div>
                          <div className="font-bold text-[color:var(--text-primary)]">{ds.filename}</div>
                          <div className="text-xs text-[color:var(--text-secondary)] font-mono">{ds.id.slice(0, 8)}...</div>
                        </div>
                      </div>
                      <span className="text-[color:var(--accent)] font-bold opacity-0 group-hover:opacity-100 transition-opacity">Select →</span>
                    </button>
                  ))
                )}
              </div>
            </div>
          )}

          {step === 1 && (
            <div className="animate-in fade-in slide-in-from-right-4 duration-350">
              <h2 className="text-xl font-bold mb-6 text-[color:var(--text-primary)]">What is your primary study objective?</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <OptionCard
                  icon="⚔️"
                  title="Compare Groups"
                  desc="Difference between treatment arms or populations"
                  onClick={() => handleSelect('goal', 'compare_groups')}
                />
                <OptionCard
                  icon="🔗"
                  title="Find Relationships"
                  desc="Correlation or association between variables"
                  onClick={() => handleSelect('goal', 'relationship')}
                />
                <OptionCard
                  icon="📈"
                  title="Prediction"
                  desc="Focus on outcome prediction (Regression)"
                  disabled
                />
                <OptionCard
                  icon="⏳"
                  title="Survival Analysis"
                  desc="Time-to-event analysis (Clinical Survival)"
                  onClick={() => handleSelect('goal', 'survival')}
                />
                <OptionCard
                  icon="🔮"
                  title="Predict Outcome"
                  desc="Multi-factor predictive modeling (Regression)"
                  onClick={() => handleSelect('goal', 'prediction')}
                />
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="animate-in fade-in slide-in-from-right-4 duration-350">
              <h2 className="text-xl font-bold mb-6 text-[color:var(--text-primary)]">How are the groups structured?</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <OptionCard
                  icon="👥"
                  title="Independent"
                  desc="Two or more different populations (Placebo vs Drug)"
                  onClick={() => handleSelect('structure', 'independent')}
                />
                <OptionCard
                  icon="🔄"
                  title="Paired / Matched"
                  desc="Same subjects measured twice or matched sets"
                  onClick={() => handleSelect('structure', 'paired')}
                />
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="animate-in fade-in slide-in-from-right-4 duration-350">
              <h2 className="text-xl font-bold mb-6 text-[color:var(--text-primary)]">What type of data is the outcome?</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <OptionCard
                  icon="📏"
                  title="Numeric (Continuous)"
                  desc="e.g., Weight, Blood Pressure, Viral Load"
                  onClick={() => handleSelect('data_type', 'numeric')}
                />
                <OptionCard
                  icon="🏷️"
                  title="Categorical (Nominal)"
                  desc="e.g., Recovered/Not, Genotype, Adverse Event"
                  onClick={() => handleSelect('data_type', 'categorical')}
                />
              </div>
              {selections.data_type === 'numeric' && (
                <div className="mt-8 p-4 bg-[color:var(--bg-secondary)] border border-[color:var(--border-color)] rounded-[2px] flex items-center gap-3">
                  <div className="text-xl">📊</div>
                  <div className="flex-1">
                    <label className="flex items-center gap-2 cursor-pointer select-none">
                      <input
                        type="checkbox"
                        className="w-4 h-4 rounded-[2px]"
                        style={{ accentColor: 'var(--accent)' }}
                        checked={selections.normal_distribution}
                        onChange={(e) => setSelections({ ...selections, normal_distribution: e.target.checked })}
                      />
                      <span className="text-sm font-medium text-[color:var(--text-primary)]">Assume Normal Distribution (Parametric)</span>
                    </label>
                    <p className="text-xs text-[color:var(--text-secondary)] ml-6">Use this if you expect a bell-shaped curve. Otherwise, we'll suggest robust non-parametric tests.</p>
                  </div>
                </div>
              )}
            </div>
          )}

          {step === 4 && (
            <div className="animate-in fade-in slide-in-from-right-4 duration-350">
              <h2 className="text-xl font-bold mb-6 text-[color:var(--text-primary)]">How many groups are there?</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <OptionCard
                  icon="🏘️"
                  title="Two Groups"
                  desc="e.g., Control vs Treatment"
                  onClick={() => handleSelect('groups', '2')}
                />
                <OptionCard
                  icon="🏘️🏘️"
                  title="More than Two (> 2)"
                  desc="e.g., Dose-ranging study (Low vs Mid vs High)"
                  onClick={() => handleSelect('groups', '>2')}
                />
              </div>
            </div>
          )}

          {step > 0 && (
            <button
              onClick={() => step > 1 ? setStep(step - 1) : setStep(0)}
              className="mt-8 px-4 py-2 text-sm text-[color:var(--text-secondary)] hover:text-[color:var(--accent)] hover:bg-[color:var(--bg-secondary)] rounded-[2px] border border-transparent hover:border-[color:var(--border-color)] transition-colors"
            >
              ← Back to previous question
            </button>
          )}
        </div>
      ) : (
        <div className="animate-in zoom-in-95 duration-500 space-y-8">
          {/* Recommendation Card */}
          <div className="bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] p-10 text-center relative overflow-hidden">
            <div className="inline-flex items-center justify-center w-20 h-20 rounded-[2px] bg-[color:var(--bg-secondary)] text-[color:var(--accent)] mb-8 border border-[color:var(--border-color)]">
              <span className="text-4xl">💡</span>
            </div>
            <div className="text-[color:var(--text-secondary)] text-sm font-bold uppercase tracking-widest mb-2">Protocol Solution</div>
            <h2 className="text-4xl font-black text-[color:var(--text-primary)] mb-6">{recommendation.name}</h2>
            <p className="text-xl text-[color:var(--text-secondary)] mb-10 max-w-2xl mx-auto leading-relaxed">{recommendation.description}</p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-10 max-w-xl mx-auto text-left">
              {recommendation.assumptions?.map((ass, i) => (
                <div key={i} className="flex items-center gap-2 text-sm text-[color:var(--text-secondary)] bg-[color:var(--bg-secondary)] px-4 py-2 rounded-[2px] border border-[color:var(--border-color)]">
                  <span className="text-[color:var(--accent)]">✓</span> {ass}
                </div>
              ))}
            </div>

            {!showApplyForm ? (
              <div className="flex justify-center flex-wrap gap-4">
                <Button variant="ghost" onClick={reset} className="px-8">
                  Start Over
                </Button>
                {recommendation.method_id !== "consult_statistician" && (
                  <Button variant="primary" onClick={() => setShowApplyForm(true)} className="px-8">
                    Apply to Dataset →
                  </Button>
                )}
              </div>
            ) : null}
          </div>

          {/* Apply Form - Appears below recommendation */}
          {showApplyForm && (
            <div className="bg-[color:var(--white)] p-8 border border-[color:var(--border-color)] rounded-[2px] animate-in slide-in-from-bottom-8 duration-500">
              <div className="flex items-center gap-3 mb-8">
                <div className="w-10 h-10 bg-[color:var(--accent)] text-[color:var(--white)] rounded-[2px] flex items-center justify-center font-bold">🛠️</div>
                <div>
                  <h3 className="font-bold text-xl text-[color:var(--text-primary)]">Analysis Configuration</h3>
                  <p className="text-sm text-[color:var(--text-secondary)]">Mapping variables for {recommendation.name}</p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-10">
                <div className="space-y-2">
                  <label className="block text-sm font-black text-[color:var(--text-primary)] uppercase tracking-wide">
                    {recommendation?.method_id === 'survival_km' ? 'Duration Column (Time)' : 'Target Outcome'}
                  </label>
                  <p className="text-xs text-[color:var(--text-secondary)] mb-2">
                    {recommendation?.method_id === 'survival_km' ? 'e.g., Days until recovery' : 'Select the column you want to measure'}
                  </p>
                  <select
                    className="w-full border border-[color:var(--border-color)] rounded-[2px] px-3 py-2 bg-[color:var(--bg-secondary)] focus:border-[color:var(--accent)] focus:outline-none transition-colors"
                    value={variables.target}
                    onChange={e => setVariables({ ...variables, target: e.target.value })}
                  >
                    <option value="">-- Choose Column --</option>
                    {columns.map(c => (
                      <option key={c.name} value={c.name}>{c.name} ({c.type})</option>
                    ))}
                  </select>
                </div>

                {recommendation?.method_id === 'survival_km' && (
                  <div className="space-y-2">
                    <label className="block text-sm font-black text-[color:var(--text-primary)] uppercase tracking-wide">Event Status (Censoring)</label>
                    <p className="text-xs text-[color:var(--text-secondary)] mb-2">Column with 1 for event, 0 for censored</p>
                    <select
                      className="w-full border border-[color:var(--border-color)] rounded-[2px] px-3 py-2 bg-[color:var(--bg-secondary)] focus:border-[color:var(--accent)] focus:outline-none transition-colors"
                      value={variables.event}
                      onChange={e => setVariables({ ...variables, event: e.target.value })}
                    >
                      <option value="">-- Choose Column --</option>
                      {columns.map(c => (
                        <option key={c.name} value={c.name}>{c.name} ({c.type})</option>
                      ))}
                    </select>
                  </div>
                )}

                {(recommendation?.method_id === 'linear_regression' || recommendation?.method_id === 'logistic_regression') ? (
                  <div className="space-y-4 col-span-full">
                    <label className="block text-sm font-black text-[color:var(--text-primary)] uppercase tracking-wide">Predictors (Input Factors)</label>
                    <p className="text-xs text-[color:var(--text-secondary)] mb-2">Select one or more columns that might predict the outcome</p>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                      {columns.map(c => (
                        <button
                          key={c.name}
                          onClick={() => handlePredictorToggle(c.name)}
                          className={`p-3 rounded-[2px] border text-xs font-bold transition-colors ${variables.predictors?.split(',').includes(c.name)
                            ? 'border-[color:var(--accent)] bg-[color:var(--bg-secondary)] text-[color:var(--text-primary)]'
                            : 'border-[color:var(--border-color)] bg-[color:var(--white)] text-[color:var(--text-secondary)] hover:border-[color:var(--text-primary)]'
                            }`}
                        >
                          {c.name}
                        </button>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="space-y-2">
                    <label className="block text-sm font-black text-[color:var(--text-primary)] uppercase tracking-wide">Grouping Factor</label>
                    <p className="text-xs text-[color:var(--text-secondary)] mb-2">Select the column that defines your groups (Optional for survival)</p>
                    <select
                      className="w-full border border-[color:var(--border-color)] rounded-[2px] px-3 py-2 bg-[color:var(--bg-secondary)] focus:border-[color:var(--accent)] focus:outline-none transition-colors"
                      value={variables.group}
                      onChange={e => setVariables({ ...variables, group: e.target.value })}
                    >
                      <option value="">-- Choose Column --</option>
                      {columns.map(c => (
                        <option key={c.name} value={c.name}>{c.name} ({c.type})</option>
                      ))}
                    </select>
                  </div>
                )}
              </div>

              <div className="flex items-center justify-between pt-6 border-t border-[color:var(--border-color)]">
                <button onClick={() => setShowApplyForm(false)} className="text-[color:var(--text-secondary)] font-bold hover:text-[color:var(--text-primary)] transition-colors">Discard</button>
                <div className="flex gap-4">
                  <button
                    onClick={handleApply}
                    disabled={loading || !variables.target || (
                      recommendation?.method_id === 'survival_km' ? !variables.event :
                        (recommendation?.method_id?.includes('regression') ? !variables.predictors : !variables.group)
                    )}
                    className="bg-[color:var(--accent)] text-[color:var(--white)] px-10 py-4 rounded-[2px] font-black text-lg hover:bg-[color:var(--accent-hover)] disabled:opacity-30 transition-colors"
                  >
                    {loading ? 'Analyzing...' : 'Execute Protocol ⚡'}
                  </button>
                </div>
              </div>

              {/* Results Display */}
              {analysisResult && (
                <div className="mt-12 space-y-8 animate-in fade-in duration-700">
                  <div className="flex items-center gap-4">
                    <div className="h-px flex-1 bg-[color:var(--border-color)]"></div>
                    <div className="text-xs font-black text-[color:var(--text-secondary)] uppercase tracking-widest">Experimental Results</div>
                    <div className="h-px flex-1 bg-[color:var(--border-color)]"></div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <div className="bg-[color:var(--white)] p-6 rounded-[2px] border border-[color:var(--border-color)] text-center">
                      <span className="block text-[color:var(--text-secondary)] text-xs font-black mb-1 uppercase tracking-tighter">P-Value</span>
                      <span className={`text-4xl font-mono font-black ${analysisResult.significant ? 'text-[color:var(--success)]' : 'text-[color:var(--text-primary)]'}`}>
                        {analysisResult.p_value < 0.001 ? '< 0.001' : analysisResult.p_value.toFixed(4)}
                      </span>
                    </div>
                    <div className="bg-[color:var(--white)] p-6 rounded-[2px] border border-[color:var(--border-color)] text-center">
                      <span className="block text-[color:var(--text-secondary)] text-xs font-black mb-1 uppercase tracking-tighter">Statistic</span>
                      <span className="text-4xl font-mono font-black text-[color:var(--text-primary)]">
                        {analysisResult.stat_value.toFixed(2)}
                      </span>
                    </div>
                    <div className="bg-[color:var(--white)] p-6 rounded-[2px] border border-[color:var(--border-color)] text-center">
                      <span className="block text-[color:var(--text-secondary)] text-xs font-black mb-1 uppercase tracking-tighter">Significance</span>
                      <span className={`text-xl font-bold ${analysisResult.significant ? 'text-[color:var(--success)]' : 'text-[color:var(--text-muted)]'}`}>
                        {analysisResult.significant ? '✓ SIGNIF.' : '✖ NOT SIGNIF.'}
                      </span>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <div className="bg-[color:var(--white)] p-6 rounded-[2px] border border-[color:var(--border-color)] text-center">
                      <span className="block text-[color:var(--text-secondary)] text-xs font-black mb-1 uppercase tracking-tighter">Effect size</span>
                      <span className="text-2xl font-mono font-black text-[color:var(--text-primary)]">
                        {typeof analysisResult.effect_size === 'number'
                          ? `${analysisResult.effect_size_name || 'effect'} ${analysisResult.effect_size.toFixed(2)}`
                          : '—'
                        }
                      </span>
                      <div className="mt-2 text-xs text-[color:var(--text-secondary)] font-mono">
                        {typeof analysisResult.effect_size_ci_lower === 'number' && typeof analysisResult.effect_size_ci_upper === 'number'
                          ? `CI: [${analysisResult.effect_size_ci_lower.toFixed(2)}, ${analysisResult.effect_size_ci_upper.toFixed(2)}]`
                          : 'CI: —'
                        }
                      </div>
                    </div>
                    <div className="bg-[color:var(--white)] p-6 rounded-[2px] border border-[color:var(--border-color)] text-center">
                      <span className="block text-[color:var(--text-secondary)] text-xs font-black mb-1 uppercase tracking-tighter">Power</span>
                      <span className="text-2xl font-mono font-black text-[color:var(--text-primary)]">
                        {typeof analysisResult.power === 'number' ? analysisResult.power.toFixed(2) : '—'}
                      </span>
                    </div>
                    <div className="bg-[color:var(--white)] p-6 rounded-[2px] border border-[color:var(--border-color)] text-center">
                      <span className="block text-[color:var(--text-secondary)] text-xs font-black mb-1 uppercase tracking-tighter">BF10</span>
                      <span className="text-2xl font-mono font-black text-[color:var(--text-primary)]">
                        {typeof analysisResult.bf10 === 'number' ? analysisResult.bf10.toPrecision(3) : '—'}
                      </span>
                    </div>
                  </div>

                  {/* Visualization Block */}
                  <div className="bg-[color:var(--white)] p-8 rounded-[2px] border border-[color:var(--border-color)]">
                    <Suspense fallback={chartFallback}>
                      <AnalyticsChart result={analysisResult} />
                    </Suspense>
                  </div>

                  <div className="flex justify-center mt-4 gap-3 flex-wrap">
                    <Button variant="secondary" onClick={handleDownloadReport} className="px-8">
                      <span>📥</span> Download Official Report (PDF)
                    </Button>
                    <Button variant="ghost" onClick={handleDownloadReportDocx} className="px-8">
                      <span>⌁</span> Download Word Report (DOCX)
                    </Button>
                  </div>

                  {analysisResult.conclusion && (
                    <div className="bg-[color:var(--white)] text-[color:var(--text-primary)] p-10 rounded-[2px] relative border border-[color:var(--accent)] overflow-hidden">
                      <h4 className="font-black text-lg mb-4 flex items-center gap-2">
                        <span className="w-2 h-2 bg-[color:var(--accent)] rounded-[2px]"></span>
                        Clinical Interpretation (AI Generated)
                      </h4>
                      <p className="text-xl leading-relaxed italic">"{analysisResult.conclusion}"</p>
                    </div>
                  )}

                  <button onClick={reset} className="w-full py-4 text-[color:var(--text-secondary)] hover:text-[color:var(--accent)] font-bold text-sm transition-colors mt-8">
                    Clear Results & Start New Design
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function OptionCard({ icon, title, desc, onClick, disabled }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`text-left p-6 border rounded-[2px] transition-colors relative overflow-hidden group ${disabled
        ? 'opacity-40 border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] cursor-not-allowed'
        : 'border-[color:var(--border-color)] hover:border-[color:var(--accent)] hover:bg-[color:var(--bg-secondary)]'
        }`}
    >
      <div className="flex items-start gap-4">
        <div className={`w-12 h-12 rounded-[2px] border border-[color:var(--border-color)] flex items-center justify-center text-2xl transition-colors ${disabled ? 'bg-[color:var(--bg-secondary)]' : 'bg-[color:var(--bg-secondary)] group-hover:border-[color:var(--accent)]'}`}>
          {icon}
        </div>
        <div className="flex-1">
          <h3 className={`font-black text-lg ${disabled ? 'text-[color:var(--text-secondary)]' : 'text-[color:var(--text-primary)]'}`}>
            {title}
          </h3>
          <p className="text-sm text-[color:var(--text-secondary)] leading-tight mt-1">
            {desc}
          </p>
        </div>
      </div>
    </button>
  );
}
