# Production Smoke Report

- generated_at: 2026-03-01T15:59:54Z
- host: MacBook-Air-Eduard.local
- repo: /Users/eduardbelskih/Проекты Github/statproject
- commit: aed7561
- benchmark_min_runs: 0
- benchmark_strict: 0

## Backend runtime warning gate

```bash
cd '/Users/eduardbelskih/Проекты Github/statproject/backend' && ./scripts/run_runtime_warning_gate.sh
```

- status: PASS

```text
============================= test session starts ==============================
platform darwin -- Python 3.9.6, pytest-8.0.0, pluggy-1.6.0
rootdir: /Users/eduardbelskih/Проекты Github/statproject/backend
configfile: pytest.ini
plugins: anyio-4.12.0
collected 5 items

tests/test_covid_smoke_v2_flow.py .                                      [ 20%]
tests/test_engine_parity_advanced_batch_modes.py .                       [ 40%]
tests/test_execute_v2_advanced_coverage.py .                             [ 60%]
tests/test_engine_kendall_and_assumptions.py .                           [ 80%]
tests/test_descriptives.py .                                             [100%]

=============================== warnings summary ===============================
../../../Library/Python/3.9/lib/python/site-packages/matplotlib/_fontconfig_pattern.py:88
../../../Library/Python/3.9/lib/python/site-packages/matplotlib/_fontconfig_pattern.py:88
../../../Library/Python/3.9/lib/python/site-packages/matplotlib/_fontconfig_pattern.py:88
../../../Library/Python/3.9/lib/python/site-packages/matplotlib/_fontconfig_pattern.py:88
../../../Library/Python/3.9/lib/python/site-packages/matplotlib/_fontconfig_pattern.py:88
../../../Library/Python/3.9/lib/python/site-packages/matplotlib/_fontconfig_pattern.py:88
  /Users/eduardbelskih/Library/Python/3.9/lib/python/site-packages/matplotlib/_fontconfig_pattern.py:88: DeprecationWarning: 'parseString' deprecated - use 'parse_string'
    parse = parser.parseString(pattern)

../../../Library/Python/3.9/lib/python/site-packages/matplotlib/_fontconfig_pattern.py:92
../../../Library/Python/3.9/lib/python/site-packages/matplotlib/_fontconfig_pattern.py:92
../../../Library/Python/3.9/lib/python/site-packages/matplotlib/_fontconfig_pattern.py:92
../../../Library/Python/3.9/lib/python/site-packages/matplotlib/_fontconfig_pattern.py:92
../../../Library/Python/3.9/lib/python/site-packages/matplotlib/_fontconfig_pattern.py:92
../../../Library/Python/3.9/lib/python/site-packages/matplotlib/_fontconfig_pattern.py:92
  /Users/eduardbelskih/Library/Python/3.9/lib/python/site-packages/matplotlib/_fontconfig_pattern.py:92: DeprecationWarning: 'resetCache' deprecated - use 'reset_cache'
    parser.resetCache()

../../../Library/Python/3.9/lib/python/site-packages/matplotlib/_mathtext.py:45
  /Users/eduardbelskih/Library/Python/3.9/lib/python/site-packages/matplotlib/_mathtext.py:45: DeprecationWarning: 'enablePackrat' deprecated - use 'enable_packrat'
    ParserElement.enablePackrat()

../../../Library/Python/3.9/lib/python/site-packages/_pytest/config/__init__.py:1394
  /Users/eduardbelskih/Library/Python/3.9/lib/python/site-packages/_pytest/config/__init__.py:1394: PytestConfigWarning: Unknown config option: timeout
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

tests/test_covid_smoke_v2_flow.py::test_covid_smoke_v2_python_plan_execute_report
tests/test_covid_smoke_v2_flow.py::test_covid_smoke_v2_python_plan_execute_report
tests/test_covid_smoke_v2_flow.py::test_covid_smoke_v2_python_plan_execute_report
tests/test_covid_smoke_v2_flow.py::test_covid_smoke_v2_python_plan_execute_report
tests/test_covid_smoke_v2_flow.py::test_covid_smoke_v2_python_plan_execute_report
tests/test_covid_smoke_v2_flow.py::test_covid_smoke_v2_python_plan_execute_report
  /Users/eduardbelskih/Library/Python/3.9/lib/python/site-packages/seaborn/categorical.py:640: FutureWarning: SeriesGroupBy.grouper is deprecated and will be removed in a future version of pandas.
    positions = grouped.grouper.result_index.to_numpy(dtype=float)

tests/test_covid_smoke_v2_flow.py::test_covid_smoke_v2_python_plan_execute_report
tests/test_covid_smoke_v2_flow.py::test_covid_smoke_v2_python_plan_execute_report
tests/test_covid_smoke_v2_flow.py::test_covid_smoke_v2_python_plan_execute_report
tests/test_covid_smoke_v2_flow.py::test_covid_smoke_v2_python_plan_execute_report
tests/test_covid_smoke_v2_flow.py::test_covid_smoke_v2_python_plan_execute_report
tests/test_covid_smoke_v2_flow.py::test_covid_smoke_v2_python_plan_execute_report
  /Users/eduardbelskih/Library/Python/3.9/lib/python/site-packages/seaborn/_base.py:949: FutureWarning: When grouping with a length-1 list-like, you will need to pass a length-1 tuple to get_group in a future version of pandas. Pass `(name,)` instead of `name` to silence this warning.
    data_subset = grouped_data.get_group(pd_key)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================= 5 passed, 26 warnings in 14.83s ========================
```

## Backend release smoke tests

```bash
cd '/Users/eduardbelskih/Проекты Github/statproject/backend' && python3 -m pytest -q tests/test_covid_smoke_v2_flow.py::test_covid_smoke_v2_python_plan_execute_report tests/test_covid_smoke_v2_flow.py::test_covid_smoke_v2_release_bundle_strict_compare tests/test_report_quality_checklist.py::test_report_quality_endpoint_passes_with_full_artifacts tests/test_release_bundle.py::test_release_bundle_generated_script_verifies_manifest
```

- status: PASS

```text
============================= test session starts ==============================
platform darwin -- Python 3.9.6, pytest-8.0.0, pluggy-1.6.0
rootdir: /Users/eduardbelskih/Проекты Github/statproject/backend
configfile: pytest.ini
plugins: anyio-4.12.0
collected 4 items

tests/test_covid_smoke_v2_flow.py ..                                     [ 50%]
tests/test_report_quality_checklist.py .                                 [ 75%]
tests/test_release_bundle.py .                                           [100%]

============================== 4 passed in 13.97s ==============================
```

## Model-router benchmark snapshot build

```bash
cd '/Users/eduardbelskih/Проекты Github/statproject' && python3 backend/scripts/benchmark_model_router.py --workspace-dir workspace --output release/model_router_benchmark_report.json --markdown-out release/model_router_benchmark_report.md --min-runs 0  --pretty
```

- status: PASS

```text
Saved: /Users/eduardbelskih/Проекты Github/statproject/release/model_router_benchmark_report.json
Saved: /Users/eduardbelskih/Проекты Github/statproject/release/model_router_benchmark_report.md
runs_total=0 variants_total=0
coverage_gate=PASS (runs_total=0 min_runs=0)
publication: winner=- share=0.0 n=0
focused: winner=- share=0.0 n=0
exploratory: winner=- share=0.0 n=0
```

## Backend benchmark contract tests

```bash
cd '/Users/eduardbelskih/Проекты Github/statproject/backend' && python3 -m pytest -q tests/test_api_v2.py::test_model_router_benchmark_snapshot_endpoint tests/test_model_router_benchmark.py::test_benchmark_cli_generates_json_and_markdown tests/test_model_router_benchmark.py::test_benchmark_cli_strict_min_runs_fails_when_insufficient
```

- status: PASS

```text
============================= test session starts ==============================
platform darwin -- Python 3.9.6, pytest-8.0.0, pluggy-1.6.0
rootdir: /Users/eduardbelskih/Проекты Github/statproject/backend
configfile: pytest.ini
plugins: anyio-4.12.0
collected 3 items

tests/test_api_v2.py .                                                   [ 33%]
tests/test_model_router_benchmark.py ..                                  [100%]

============================== 3 passed in 0.75s ===============================
```

## Frontend lint

```bash
cd '/Users/eduardbelskih/Проекты Github/statproject/frontend' && npm run lint
```

- status: PASS

```text

> frontend@0.0.0 lint
> eslint .

```

## Frontend unit tests

```bash
cd '/Users/eduardbelskih/Проекты Github/statproject/frontend' && npm run test:run
```

- status: PASS

```text

> frontend@0.0.0 test:run
> vitest run


 RUN  v3.2.4 /Users/eduardbelskih/Проекты Github/statproject/frontend

 ✓ src/features/copilot/components/benchmarkScoring.test.js (4 tests) 20ms
 ✓ src/lib/api.test.js (16 tests) 84ms
 ✓ src/app/components/AnalyticsChart.test.jsx (2 tests) 199ms
 ✓ src/app/pages/PromptBuilder.test.jsx (1 test) 85ms
 ✓ src/app/pages/Analyze.test.jsx (2 tests) 156ms
 ✓ src/app/pages/Settings.test.jsx (1 test) 146ms
 ✓ src/app/utils/analysisSet.test.js (4 tests) 4ms
 ✓ src/app/components/visualizations/utils.test.js (3 tests) 3ms
 ✓ src/app/pages/pageSizeGuard.test.js (4 tests) 1ms
 ✓ src/features/copilot/CopilotPage.test.jsx (5 tests) 1339ms
   ✓ CopilotPage publication flow > auto-freezes cohort in publication mode and forwards analysis_set_id to execute  591ms

 Test Files  10 passed (10)
      Tests  42 passed (42)
   Start at  19:00:48
   Duration  3.56s (transform 1.58s, setup 0ms, collect 4.19s, tests 2.04s, environment 7.27s, prepare 1.22s)

```

## Frontend build

```bash
cd '/Users/eduardbelskih/Проекты Github/statproject/frontend' && npm run build
```

- status: PASS

```text

> frontend@0.0.0 build
> vite build

vite v7.3.0 building client environment for production...
transforming...
✓ 1475 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                                               0.46 kB │ gzip:   0.29 kB
dist/assets/index-CZIdd4na.css                               59.02 kB │ gzip:  11.14 kB
dist/assets/ag-theme-quartz-DeLi5V1V.css                     71.70 kB │ gzip:  14.88 kB
dist/assets/ag-grid-DovOAdF2.css                            162.67 kB │ gzip:  24.61 kB
dist/assets/index-IaTSH15x.js                                 0.09 kB │ gzip:   0.10 kB
dist/assets/ArrowDownTrayIcon-D4ws4kDP.js                     0.56 kB │ gzip:   0.39 kB
dist/assets/PlayIcon-Ccxjtkmt.js                              0.58 kB │ gzip:   0.40 kB
dist/assets/InformationCircleIcon-7tiOBgvg.js                 0.61 kB │ gzip:   0.43 kB
dist/assets/Badge-CeNtjDBX.js                                 0.73 kB │ gzip:   0.36 kB
dist/assets/Button-BvxqUMV8.js                                1.15 kB │ gzip:   0.52 kB
dist/assets/analysisSet-DdW4roBG.js                           1.23 kB │ gzip:   0.59 kB
dist/assets/TrashIcon-DnjEyJAQ.js                             1.30 kB │ gzip:   0.59 kB
dist/assets/AnalysisDesign-BeuBrl2d.js                        1.30 kB │ gzip:   0.75 kB
dist/assets/Tabs-DH0pZApy.js                                  1.82 kB │ gzip:   0.82 kB
dist/assets/SparklesIcon-BiPyPs8N.js                          1.94 kB │ gzip:   0.64 kB
dist/assets/Settings-BwYoZnjS.js                              4.49 kB │ gzip:   1.16 kB
dist/assets/diverging-CX-4w9wN.js                             5.52 kB │ gzip:   1.99 kB
dist/assets/Upload-DCE_Dy-_.js                                6.64 kB │ gzip:   2.64 kB
dist/assets/EditableDataGrid-DCAR6OMZ.js                      6.87 kB │ gzip:   2.74 kB
dist/assets/StudySetup-CdPUflDp.js                            7.41 kB │ gzip:   2.49 kB
dist/assets/InteractionPlot-Pl8CtXti.js                       7.42 kB │ gzip:   2.57 kB
dist/assets/react-virtualized-auto-sizer.esm-BU5GeTvf.js      7.61 kB │ gzip:   2.69 kB
dist/assets/ClusteredHeatmap-CQEZXvBm.js                      8.42 kB │ gzip:   2.88 kB
dist/assets/ordinal-B-c1MlK_.js                               8.50 kB │ gzip:   2.91 kB
dist/assets/DatasetList-YOY9rFmp.js                           8.97 kB │ gzip:   2.92 kB
dist/assets/StatTooltip-CLqLpTC6.js                          10.16 kB │ gzip:   4.00 kB
dist/assets/SearchableSelect-B9HMNIxr.js                     20.48 kB │ gzip:   6.65 kB
dist/assets/PromptBuilder-CsaPtnOO.js                        20.73 kB │ gzip:   5.99 kB
dist/assets/StatWiki-DCYanlZe.js                             22.69 kB │ gzip:   5.50 kB
dist/assets/SampleSizeCalculator-KiF7jAA5.js                 23.78 kB │ gzip:   5.81 kB
dist/assets/api-Dd4tLLTg.js                                  24.72 kB │ gzip:   5.82 kB
dist/assets/transform-ViMf9YAE.js                            31.34 kB │ gzip:   9.93 kB
dist/assets/ExportSettingsModal-Dyp_0Px_.js                  32.46 kB │ gzip:  12.10 kB
dist/assets/Analyze-Dho4Z208.js                              37.21 kB │ gzip:  10.24 kB
dist/assets/AnalysisAIDesign-BV8uOKFH.js                     39.55 kB │ gzip:   9.20 kB
dist/assets/index.esm-DGqdgzde.js                            48.09 kB │ gzip:  14.50 kB
dist/assets/Profile-B1Z-kaHO.js                              59.62 kB │ gzip:  12.85 kB
dist/assets/VariablePreview-DLN-bOmX.js                      79.58 kB │ gzip:  18.69 kB
dist/assets/ProtocolSorcerer-D3sS-w0S.js                     86.13 kB │ gzip:  20.66 kB
dist/assets/CopilotPage-lkyqt_tH.js                          86.54 kB │ gzip:  19.49 kB
dist/assets/AnalysisDesignLegacy-BDdIJwVB.js                165.29 kB │ gzip:  39.07 kB
dist/assets/index-LN7JTsCn.js                               313.26 kB │ gzip: 100.18 kB
dist/assets/VisualizePlot-C3BmbzHD.js                       347.73 kB │ gzip: 101.60 kB
dist/assets/main.esm-BksBaOQd.js                          1,020.85 kB │ gzip: 274.49 kB
✓ built in 4.88s
```

## Summary

- overall_status: PASS
