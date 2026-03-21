# Production Smoke Report

- generated_at: 2026-03-01T09:40:30Z
- host: MacBook-Air-Eduard.local
- repo: /Users/eduardbelskih/Проекты Github/statproject
- commit: 2af2517

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
======================= 5 passed, 26 warnings in 15.89s ========================
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

============================== 4 passed in 14.32s ==============================
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

 ✓ src/app/utils/analysisSet.test.js (4 tests) 8ms
 ✓ src/lib/api.test.js (14 tests) 98ms
 ✓ src/app/components/AnalyticsChart.test.jsx (2 tests) 155ms
 ✓ src/app/pages/PromptBuilder.test.jsx (1 test) 112ms
 ✓ src/app/pages/Analyze.test.jsx (2 tests) 135ms
 ✓ src/app/pages/Settings.test.jsx (1 test) 132ms
 ✓ src/features/copilot/components/benchmarkScoring.test.js (2 tests) 4ms
 ✓ src/app/pages/pageSizeGuard.test.js (4 tests) 2ms
 ✓ src/app/components/visualizations/utils.test.js (3 tests) 2ms
 ✓ src/features/copilot/CopilotPage.test.jsx (4 tests) 1309ms
   ✓ CopilotPage publication flow > auto-freezes cohort in publication mode and forwards analysis_set_id to execute  622ms

 Test Files  10 passed (10)
      Tests  37 passed (37)
   Start at  12:41:21
   Duration  3.64s (transform 1.54s, setup 0ms, collect 5.05s, tests 1.96s, environment 7.03s, prepare 1.01s)

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
dist/assets/index-DT-zOpNp.js                                 0.09 kB │ gzip:   0.10 kB
dist/assets/ArrowDownTrayIcon-2zAkpK6r.js                     0.56 kB │ gzip:   0.39 kB
dist/assets/PlayIcon-ccslBvpY.js                              0.58 kB │ gzip:   0.40 kB
dist/assets/InformationCircleIcon-BlNwyY08.js                 0.61 kB │ gzip:   0.43 kB
dist/assets/Badge-Bxi1H8E5.js                                 0.73 kB │ gzip:   0.36 kB
dist/assets/Button-zzyjNtoS.js                                1.15 kB │ gzip:   0.52 kB
dist/assets/analysisSet-DdW4roBG.js                           1.23 kB │ gzip:   0.59 kB
dist/assets/TrashIcon-ewAVGpCc.js                             1.30 kB │ gzip:   0.59 kB
dist/assets/AnalysisDesign-D_d8Esmd.js                        1.30 kB │ gzip:   0.74 kB
dist/assets/Tabs-DSKaTnVd.js                                  1.82 kB │ gzip:   0.82 kB
dist/assets/SparklesIcon-8PGqje3G.js                          1.94 kB │ gzip:   0.64 kB
dist/assets/Settings-CmgvDmJt.js                              4.49 kB │ gzip:   1.16 kB
dist/assets/diverging-DU-ivXed.js                             5.52 kB │ gzip:   2.00 kB
dist/assets/Upload-iUyPiqf5.js                                6.64 kB │ gzip:   2.64 kB
dist/assets/EditableDataGrid-CMghZ2Oe.js                      6.87 kB │ gzip:   2.74 kB
dist/assets/StudySetup-CTlvM-Js.js                            7.41 kB │ gzip:   2.48 kB
dist/assets/InteractionPlot-UxQDtfrj.js                       7.42 kB │ gzip:   2.57 kB
dist/assets/react-virtualized-auto-sizer.esm-DBFq3pGV.js      7.61 kB │ gzip:   2.69 kB
dist/assets/ClusteredHeatmap-CgUJ-ft-.js                      8.42 kB │ gzip:   2.88 kB
dist/assets/ordinal-BNfmJLi_.js                               8.50 kB │ gzip:   2.91 kB
dist/assets/DatasetList-DnWlyfc1.js                           8.97 kB │ gzip:   2.92 kB
dist/assets/StatTooltip-5tEM0heW.js                          10.16 kB │ gzip:   4.00 kB
dist/assets/SearchableSelect-B7MtDs39.js                     20.48 kB │ gzip:   6.65 kB
dist/assets/PromptBuilder-DEq30Nt7.js                        20.73 kB │ gzip:   5.99 kB
dist/assets/StatWiki-CikiiWSS.js                             22.69 kB │ gzip:   5.49 kB
dist/assets/SampleSizeCalculator-B0FKTeF7.js                 23.78 kB │ gzip:   5.81 kB
dist/assets/api-DVs1BpUf.js                                  24.03 kB │ gzip:   5.63 kB
dist/assets/transform-DcJHdgUV.js                            31.34 kB │ gzip:   9.93 kB
dist/assets/ExportSettingsModal-28wzQ7By.js                  32.46 kB │ gzip:  12.10 kB
dist/assets/Analyze-VJiVPDpQ.js                              37.21 kB │ gzip:  10.23 kB
dist/assets/AnalysisAIDesign-tLbeuFES.js                     39.55 kB │ gzip:   9.20 kB
dist/assets/index.esm-WEoFk7RH.js                            48.09 kB │ gzip:  14.50 kB
dist/assets/Profile-CpSEaI5m.js                              59.62 kB │ gzip:  12.85 kB
dist/assets/CopilotPage-DoILrFX5.js                          77.21 kB │ gzip:  17.41 kB
dist/assets/VariablePreview-CWfcESES.js                      79.58 kB │ gzip:  18.70 kB
dist/assets/ProtocolSorcerer-BN2fqKMY.js                     86.13 kB │ gzip:  20.66 kB
dist/assets/AnalysisDesignLegacy-YmDVY6Jh.js                165.29 kB │ gzip:  39.06 kB
dist/assets/index-CI4KF4rp.js                               313.26 kB │ gzip: 100.17 kB
dist/assets/VisualizePlot-CpctI6tM.js                       347.73 kB │ gzip: 101.60 kB
dist/assets/main.esm-BksBaOQd.js                          1,020.85 kB │ gzip: 274.49 kB
✓ built in 4.41s
```

## Summary

- overall_status: PASS
