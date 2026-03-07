# Production Smoke Report

- generated_at: 2026-03-01T20:13:52Z
- host: MacBook-Air-Eduard.local
- repo: /Users/eduardbelskih/Проекты Github/statproject
- commit: aed7561
- benchmark_min_runs: 0
- benchmark_strict: 0
- benchmark_capture_run: 1

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
======================= 5 passed, 26 warnings in 14.99s ========================
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

============================== 4 passed in 16.53s ==============================
```

## Model-router benchmark capture run

```bash
cd '/Users/eduardbelskih/Проекты Github/statproject' && python3 backend/scripts/run_model_router_benchmark_capture.py --workspace-dir workspace --analysis-mode focused --max-protocol-steps 1 --min-runs 0 --snapshot-output release/model_router_benchmark_report.json --snapshot-markdown release/model_router_benchmark_report.md --capture-output release/model_router_benchmark_capture_last.json --pretty
```

- status: PASS

```text
2026-03-01 23:14:44,541 - httpx - INFO - HTTP Request: POST https://routerai.ru/api/v1/chat/completions "HTTP/1.1 200 OK"
2026-03-01 23:14:44,542 - stat_analyzer - ERROR - LLM Research Design Error: Expecting ',' delimiter: line 139 column 6 (char 3392)
Traceback (most recent call last):
  File "/Users/eduardbelskih/Проекты Github/statproject/backend/app/llm/__init__.py", line 1151, in _analyze_research_design_single
    parsed = json.loads(payload)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/json/__init__.py", line 346, in loads
    return _default_decoder.decode(s)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/json/decoder.py", line 337, in decode
    obj, end = self.raw_decode(s, idx=_w(s, 0).end())
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/json/decoder.py", line 353, in raw_decode
    obj, end = self.scan_once(s, idx)
json.decoder.JSONDecodeError: Expecting ',' delimiter: line 139 column 6 (char 3392)
2026-03-01 23:14:49,962 - httpx - INFO - HTTP Request: POST https://routerai.ru/api/v1/chat/completions "HTTP/1.1 200 OK"
2026-03-01 23:14:54,164 - httpx - INFO - HTTP Request: POST https://routerai.ru/api/v1/chat/completions "HTTP/1.1 200 OK"
2026-03-01 23:14:54,171 - httpx - INFO - HTTP Request: POST http://testserver/api/v1/v2/analysis/plan "HTTP/1.1 200 OK"
gemini_single: status=ok quality=60.75 steps=12 elapsed_ms=15829 model_used=google/gemini-2.5-flash fallback=False
2026-03-01 23:15:20,174 - httpx - INFO - HTTP Request: POST https://routerai.ru/api/v1/chat/completions "HTTP/1.1 200 OK"
2026-03-01 23:15:20,179 - stat_analyzer - ERROR - LLM Research Design Error: Expecting ',' delimiter: line 1 column 1580 (char 1579)
Traceback (most recent call last):
  File "/Users/eduardbelskih/Проекты Github/statproject/backend/app/llm/__init__.py", line 1151, in _analyze_research_design_single
    parsed = json.loads(payload)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/json/__init__.py", line 346, in loads
    return _default_decoder.decode(s)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/json/decoder.py", line 337, in decode
    obj, end = self.raw_decode(s, idx=_w(s, 0).end())
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/json/decoder.py", line 353, in raw_decode
    obj, end = self.scan_once(s, idx)
json.decoder.JSONDecodeError: Expecting ',' delimiter: line 1 column 1580 (char 1579)
2026-03-01 23:15:23,960 - httpx - INFO - HTTP Request: POST https://routerai.ru/api/v1/chat/completions "HTTP/1.1 200 OK"
2026-03-01 23:15:23,966 - httpx - INFO - HTTP Request: POST http://testserver/api/v1/v2/analysis/plan "HTTP/1.1 200 OK"
minimax_single: status=ok quality=57.37 steps=4 elapsed_ms=29796 model_used=minimax/minimax-m2.5 fallback=False
2026-03-01 23:15:52,643 - httpx - INFO - HTTP Request: POST https://routerai.ru/api/v1/chat/completions "HTTP/1.1 200 OK"
2026-03-01 23:16:53,836 - stat_analyzer - ERROR - LLM Error: 
Traceback (most recent call last):
  File "/Users/eduardbelskih/Library/Python/3.9/lib/python/site-packages/httpx/_transports/default.py", line 67, in map_httpcore_exceptions
    yield
  File "/Users/eduardbelskih/Library/Python/3.9/lib/python/site-packages/httpx/_transports/default.py", line 371, in handle_async_request
    resp = await self._pool.handle_async_request(req)
  File "/Users/eduardbelskih/Library/Python/3.9/lib/python/site-packages/httpcore/_async/connection_pool.py", line 256, in handle_async_request
    raise exc from None
  File "/Users/eduardbelskih/Library/Python/3.9/lib/python/site-packages/httpcore/_async/connection_pool.py", line 236, in handle_async_request
    response = await connection.handle_async_request(
  File "/Users/eduardbelskih/Library/Python/3.9/lib/python/site-packages/httpcore/_async/connection.py", line 103, in handle_async_request
    return await self._connection.handle_async_request(request)
  File "/Users/eduardbelskih/Library/Python/3.9/lib/python/site-packages/httpcore/_async/http11.py", line 136, in handle_async_request
    raise exc
  File "/Users/eduardbelskih/Library/Python/3.9/lib/python/site-packages/httpcore/_async/http11.py", line 106, in handle_async_request
    ) = await self._receive_response_headers(**kwargs)
  File "/Users/eduardbelskih/Library/Python/3.9/lib/python/site-packages/httpcore/_async/http11.py", line 177, in _receive_response_headers
    event = await self._receive_event(timeout=timeout)
  File "/Users/eduardbelskih/Library/Python/3.9/lib/python/site-packages/httpcore/_async/http11.py", line 217, in _receive_event
    data = await self._network_stream.read(
  File "/Users/eduardbelskih/Library/Python/3.9/lib/python/site-packages/httpcore/_backends/anyio.py", line 37, in read
    return b""
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/contextlib.py", line 135, in __exit__
    self.gen.throw(type, value, traceback)
  File "/Users/eduardbelskih/Library/Python/3.9/lib/python/site-packages/httpcore/_exceptions.py", line 14, in map_exceptions
    raise to_exc(exc) from exc
httpcore.ReadTimeout

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "/Users/eduardbelskih/Проекты Github/statproject/backend/app/llm/__init__.py", line 352, in _run_model
    resp = await client.post(url, json=payload, headers=headers)
  File "/Users/eduardbelskih/Library/Python/3.9/lib/python/site-packages/httpx/_client.py", line 1877, in post
    return await self.request(
  File "/Users/eduardbelskih/Library/Python/3.9/lib/python/site-packages/httpx/_client.py", line 1559, in request
    return await self.send(request, auth=auth, follow_redirects=follow_redirects)
  File "/Users/eduardbelskih/Library/Python/3.9/lib/python/site-packages/httpx/_client.py", line 1646, in send
    response = await self._send_handling_auth(
  File "/Users/eduardbelskih/Library/Python/3.9/lib/python/site-packages/httpx/_client.py", line 1674, in _send_handling_auth
    response = await self._send_handling_redirects(
  File "/Users/eduardbelskih/Library/Python/3.9/lib/python/site-packages/httpx/_client.py", line 1711, in _send_handling_redirects
    response = await self._send_single_request(request)
  File "/Users/eduardbelskih/Library/Python/3.9/lib/python/site-packages/httpx/_client.py", line 1748, in _send_single_request
    response = await transport.handle_async_request(request)
  File "/Users/eduardbelskih/Library/Python/3.9/lib/python/site-packages/httpx/_transports/default.py", line 371, in handle_async_request
    resp = await self._pool.handle_async_request(req)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/contextlib.py", line 135, in __exit__
    self.gen.throw(type, value, traceback)
  File "/Users/eduardbelskih/Library/Python/3.9/lib/python/site-packages/httpx/_transports/default.py", line 84, in map_httpcore_exceptions
    raise mapped_exc(message) from exc
httpx.ReadTimeout
2026-03-01 23:16:59,048 - httpx - INFO - HTTP Request: POST https://routerai.ru/api/v1/chat/completions "HTTP/1.1 200 OK"
2026-03-01 23:16:59,049 - stat_analyzer - ERROR - LLM Research Design Error: Expecting ',' delimiter: line 123 column 6 (char 3057)
Traceback (most recent call last):
  File "/Users/eduardbelskih/Проекты Github/statproject/backend/app/llm/__init__.py", line 1151, in _analyze_research_design_single
    parsed = json.loads(payload)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/json/__init__.py", line 346, in loads
    return _default_decoder.decode(s)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/json/decoder.py", line 337, in decode
    obj, end = self.raw_decode(s, idx=_w(s, 0).end())
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/json/decoder.py", line 353, in raw_decode
    obj, end = self.scan_once(s, idx)
json.decoder.JSONDecodeError: Expecting ',' delimiter: line 123 column 6 (char 3057)
2026-03-01 23:17:03,589 - httpx - INFO - HTTP Request: POST https://routerai.ru/api/v1/chat/completions "HTTP/1.1 200 OK"
2026-03-01 23:17:07,586 - httpx - INFO - HTTP Request: POST https://routerai.ru/api/v1/chat/completions "HTTP/1.1 200 OK"
2026-03-01 23:17:07,593 - httpx - INFO - HTTP Request: POST http://testserver/api/v1/v2/analysis/plan "HTTP/1.1 200 OK"
glm5_single: status=ok quality=59.28 steps=6 elapsed_ms=103630 model_used=google/gemini-2.5-flash fallback=True
2026-03-01 23:17:26,126 - httpx - INFO - HTTP Request: POST https://routerai.ru/api/v1/chat/completions "HTTP/1.1 200 OK"
2026-03-01 23:17:26,129 - stat_analyzer - ERROR - LLM Research Design Error: Expecting ',' delimiter: line 146 column 6 (char 3233)
Traceback (most recent call last):
  File "/Users/eduardbelskih/Проекты Github/statproject/backend/app/llm/__init__.py", line 1151, in _analyze_research_design_single
    parsed = json.loads(payload)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/json/__init__.py", line 346, in loads
    return _default_decoder.decode(s)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/json/decoder.py", line 337, in decode
    obj, end = self.raw_decode(s, idx=_w(s, 0).end())
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/json/decoder.py", line 353, in raw_decode
    obj, end = self.scan_once(s, idx)
json.decoder.JSONDecodeError: Expecting ',' delimiter: line 146 column 6 (char 3233)
2026-03-01 23:17:31,852 - httpx - INFO - HTTP Request: POST https://routerai.ru/api/v1/chat/completions "HTTP/1.1 200 OK"
2026-03-01 23:17:36,358 - httpx - INFO - HTTP Request: POST https://routerai.ru/api/v1/chat/completions "HTTP/1.1 200 OK"
2026-03-01 23:17:36,364 - httpx - INFO - HTTP Request: POST http://testserver/api/v1/v2/analysis/plan "HTTP/1.1 200 OK"
qwen_single: status=ok quality=61.44 steps=15 elapsed_ms=28771 model_used=qwen/qwen3.5-397b-a17b fallback=False
2026-03-01 23:18:03,089 - httpx - INFO - HTTP Request: POST https://routerai.ru/api/v1/chat/completions "HTTP/1.1 200 OK"
2026-03-01 23:18:03,092 - stat_analyzer - ERROR - LLM Research Design Error: Expecting ',' delimiter: line 1 column 2034 (char 2033)
Traceback (most recent call last):
  File "/Users/eduardbelskih/Проекты Github/statproject/backend/app/llm/__init__.py", line 1151, in _analyze_research_design_single
    parsed = json.loads(payload)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/json/__init__.py", line 346, in loads
    return _default_decoder.decode(s)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/json/decoder.py", line 337, in decode
    obj, end = self.raw_decode(s, idx=_w(s, 0).end())
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/json/decoder.py", line 353, in raw_decode
    obj, end = self.scan_once(s, idx)
json.decoder.JSONDecodeError: Expecting ',' delimiter: line 1 column 2034 (char 2033)
2026-03-01 23:18:06,975 - httpx - INFO - HTTP Request: POST https://routerai.ru/api/v1/chat/completions "HTTP/1.1 200 OK"
2026-03-01 23:18:06,981 - httpx - INFO - HTTP Request: POST http://testserver/api/v1/v2/analysis/plan "HTTP/1.1 200 OK"
routerai_combo: status=ok quality=66.49 steps=8 elapsed_ms=30618 model_used=minimax/minimax-m2.5 fallback=False
/Users/eduardbelskih/Library/Python/3.9/lib/python/site-packages/scipy/stats/_stats_py.py:1971: UserWarning: kurtosistest only valid for n>=20 ... continuing anyway, n=13
  k, _ = kurtosistest(a, axis)
/Users/eduardbelskih/Library/Python/3.9/lib/python/site-packages/scipy/stats/_stats_py.py:1971: UserWarning: kurtosistest only valid for n>=20 ... continuing anyway, n=13
  k, _ = kurtosistest(a, axis)
/Users/eduardbelskih/Library/Python/3.9/lib/python/site-packages/seaborn/categorical.py:640: FutureWarning: SeriesGroupBy.grouper is deprecated and will be removed in a future version of pandas.
  positions = grouped.grouper.result_index.to_numpy(dtype=float)
/Users/eduardbelskih/Library/Python/3.9/lib/python/site-packages/seaborn/_base.py:949: FutureWarning: When grouping with a length-1 list-like, you will need to pass a length-1 tuple to get_group in a future version of pandas. Pass `(name,)` instead of `name` to silence this warning.
  data_subset = grouped_data.get_group(pd_key)
2026-03-01 23:18:12,543 - httpx - INFO - HTTP Request: POST http://testserver/api/v1/v2/analysis/execute "HTTP/1.1 200 OK"
dataset_id=26c1930f-62c9-4d2e-bb72-fe7a5f67d19c
recommended_id=routerai_combo
run_id=run_20260301_201810_814249_4e35eb69
snapshot: runs_total=3 variants_total=15 coverage=PASS
capture_summary=/Users/eduardbelskih/Проекты Github/statproject/release/model_router_benchmark_capture_last.json
/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/multiprocessing/resource_tracker.py:216: UserWarning: resource_tracker: There appear to be 5 leaked semaphore objects to clean up at shutdown
  warnings.warn('resource_tracker: There appear to be %d '
```

## Model-router benchmark snapshot build

```bash
cd '/Users/eduardbelskih/Проекты Github/statproject' && python3 backend/scripts/benchmark_model_router.py --workspace-dir workspace --output release/model_router_benchmark_report.json --markdown-out release/model_router_benchmark_report.md --min-runs 0  --pretty
```

- status: PASS

```text
Saved: /Users/eduardbelskih/Проекты Github/statproject/release/model_router_benchmark_report.json
Saved: /Users/eduardbelskih/Проекты Github/statproject/release/model_router_benchmark_report.md
runs_total=3 variants_total=15
coverage_gate=PASS (runs_total=3 min_runs=0)
publication: winner=- share=0.0 n=0
focused: winner=routerai_combo share=0.3333 n=3
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

============================== 3 passed in 0.80s ===============================
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

 ✓ src/app/utils/analysisSet.test.js (4 tests) 12ms
 ✓ src/lib/api.test.js (16 tests) 117ms
 ✓ src/app/components/AnalyticsChart.test.jsx (2 tests) 136ms
 ✓ src/app/pages/PromptBuilder.test.jsx (1 test) 131ms
 ✓ src/app/pages/Settings.test.jsx (1 test) 160ms
 ✓ src/app/pages/Analyze.test.jsx (2 tests) 162ms
 ✓ src/features/copilot/components/benchmarkScoring.test.js (4 tests) 3ms
 ✓ src/app/components/visualizations/utils.test.js (3 tests) 2ms
 ✓ src/app/pages/pageSizeGuard.test.js (4 tests) 2ms
 ✓ src/features/copilot/CopilotPage.test.jsx (5 tests) 1338ms
   ✓ CopilotPage publication flow > auto-freezes cohort in publication mode and forwards analysis_set_id to execute  584ms

 Test Files  10 passed (10)
      Tests  42 passed (42)
   Start at  23:18:29
   Duration  5.06s (transform 1.81s, setup 0ms, collect 5.87s, tests 2.06s, environment 13.89s, prepare 1.84s)

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
✓ built in 4.37s
```

## Summary

- overall_status: PASS
