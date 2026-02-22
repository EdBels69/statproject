# Method Coverage Matrix (Python vs R)

Источник истины: `backend/app/stats/method_coverage.py`.

| method_id | Python | R |
|---|---:|---:|
| `t_test_ind` | yes | yes |
| `t_test_welch` | yes | yes |
| `mann_whitney` | yes | yes |
| `t_test_rel` | yes | yes |
| `wilcoxon` | yes | yes |
| `anova` | yes | yes |
| `anova_welch` | yes | yes |
| `kruskal` | yes | yes |
| `chi_square` | yes | yes |
| `fisher_exact` | yes | yes |
| `pearson` | yes | yes |
| `spearman` | yes | yes |
| `linear_regression` | yes | yes |
| `logistic_regression` | yes | yes |
| `roc_analysis` | yes | yes |
| `survival_km` | yes | yes |
| `rm_anova` | yes | yes |
| `friedman` | yes | yes |
| `batch_analysis` | yes | yes |
| `timepoint_batch_analysis` | yes | yes |
| `delta_batch_analysis` | yes | yes |
| `paired_wide` | yes | yes |
| `mixed_effects` | yes | yes |
| `clustered_correlation` | yes | yes |
| `bootstrap_pipeline` | yes | no |
| `cluster_profiles` | yes | no |
| `external_validation` | yes | no |
| `responders` | yes | yes |
| `anova_twoway` | yes | yes |

## Runtime validation

На endpoint `POST /api/v1/v2/analysis/execute` добавлена проверка:

1. Нормализация engine (`python`, `r`).
2. Проверка поддержки `method_id` в выбранном engine.
3. Явная ошибка до запуска шага, если комбинация несовместима.
