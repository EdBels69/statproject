import React, { useState, useMemo, useCallback } from 'react';
import { useTranslation } from '../../hooks/useTranslation';
import {
    CheckCircleIcon,
    ExclamationTriangleIcon,
    ChevronDownIcon,
    ChevronUpIcon,
    BeakerIcon,
    ClockIcon,
    UsersIcon,
    ChartBarIcon
} from '@heroicons/react/24/outline';

/**
 * StudyDesignConfirmation component
 * Displays auto-detected study design from StudyDetector and allows user confirmation/modification
 */
export default function StudyDesignConfirmation({
    studyDetection,
    columns = [],
    onConfirm,
    onRolesChange,
    currentRoles = { target: '', group: '', covariates: [] },
    isLoading = false,
}) {
    const { t } = useTranslation();
    const [isExpanded, setIsExpanded] = useState(true);
    const [localRoles, setLocalRoles] = useState(currentRoles);

    // Extract detection results
    const detection = useMemo(() => {
        if (!studyDetection || typeof studyDetection !== 'object') {
            return null;
        }
        return {
            groupCol: studyDetection.group_col || null,
            groupValues: Array.isArray(studyDetection.group_values) ? studyDetection.group_values : [],
            timepoints: Array.isArray(studyDetection.timepoints) ? studyDetection.timepoints : [],
            endpoints: Array.isArray(studyDetection.endpoint_groups) ? studyDetection.endpoint_groups : [],
            recommendations: Array.isArray(studyDetection.recommendations) ? studyDetection.recommendations : [],
            numericCols: Array.isArray(studyDetection.numeric_cols) ? studyDetection.numeric_cols : [],
            categoricalCols: Array.isArray(studyDetection.categorical_cols) ? studyDetection.categorical_cols : [],
        };
    }, [studyDetection]);

    // Column options with type info
    const columnOptions = useMemo(() => {
        if (!Array.isArray(columns)) return [];
        return columns.map((c) => ({
            name: typeof c === 'string' ? c : c?.name || '',
            type: typeof c === 'string' ? 'text' : c?.type || 'text',
        })).filter((c) => c.name);
    }, [columns]);

    // Group column options (categorical or low-cardinality numeric)
    const groupColOptions = useMemo(() => {
        if (detection?.groupCol) {
            const det = detection.groupCol;
            const exists = columnOptions.some((c) => c.name === det);
            if (!exists) return columnOptions.filter((c) => c.type === 'categorical' || c.type === 'numeric');
            return [{ name: det, type: 'categorical' }, ...columnOptions.filter((c) => c.name !== det && (c.type === 'categorical' || c.type === 'numeric'))];
        }
        return columnOptions.filter((c) => c.type === 'categorical' || c.type === 'numeric');
    }, [columnOptions, detection]);

    // Target column options (numeric)
    const targetColOptions = useMemo(() => {
        return columnOptions.filter((c) => c.type === 'numeric');
    }, [columnOptions]);

    // Handle role changes
    const handleGroupChange = useCallback((value) => {
        const next = { ...localRoles, group: value };
        setLocalRoles(next);
        onRolesChange?.(next);
    }, [localRoles, onRolesChange]);

    const handleTargetChange = useCallback((value) => {
        const next = { ...localRoles, target: value };
        setLocalRoles(next);
        onRolesChange?.(next);
    }, [localRoles, onRolesChange]);

    const handleConfirm = useCallback(() => {
        onConfirm?.(localRoles);
    }, [localRoles, onConfirm]);

    // Auto-apply detection to local roles
    const handleApplyDetection = useCallback(() => {
        if (!detection) return;
        const next = {
            ...localRoles,
            group: detection.groupCol || localRoles.group,
            target: detection.numericCols?.[0] || localRoles.target,
        };
        setLocalRoles(next);
        onRolesChange?.(next);
    }, [detection, localRoles, onRolesChange]);

    if (!detection) {
        return null;
    }

    const hasDetection = detection.groupCol || detection.timepoints.length > 0 || detection.endpoints.length > 0;

    if (!hasDetection) {
        return null;
    }

    return (
        <div className="rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] overflow-hidden">
            {/* Header */}
            <button
                type="button"
                onClick={() => setIsExpanded(!isExpanded)}
                className="w-full flex items-center justify-between gap-3 px-4 py-3 bg-[color:var(--bg-secondary)] hover:bg-[color:var(--bg-tertiary)] transition-colors"
            >
                <div className="flex items-center gap-3">
                    <BeakerIcon className="w-5 h-5 text-[color:var(--accent)]" />
                    <div className="text-left">
                        <div className="text-sm font-semibold text-[color:var(--text-primary)]">
                            {t('study_design_auto_detect_title')}
                        </div>
                        <div className="text-xs text-[color:var(--text-muted)]">
                            {t('study_design_auto_detect_subtitle')}
                        </div>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <CheckCircleIcon className="w-5 h-5 text-green-500" />
                    {isExpanded ? (
                        <ChevronUpIcon className="w-4 h-4 text-[color:var(--text-muted)]" />
                    ) : (
                        <ChevronDownIcon className="w-4 h-4 text-[color:var(--text-muted)]" />
                    )}
                </div>
            </button>

            {/* Expandable content */}
            {isExpanded && (
                <div className="px-4 py-4 space-y-4 border-t border-[color:var(--border-color)]">
                    {/* Detection summary */}
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                        {/* Group column */}
                        {detection.groupCol && (
                            <div className="flex items-start gap-2 p-3 rounded-[2px] bg-[color:var(--bg-secondary)]">
                                <UsersIcon className="w-4 h-4 text-[color:var(--accent)] mt-0.5 flex-shrink-0" />
                                <div className="min-w-0">
                                    <div className="text-[10px] font-semibold uppercase tracking-wider text-[color:var(--text-muted)]">
                                        {t('study_design_group_label')}
                                    </div>
                                    <div className="text-sm font-medium text-[color:var(--text-primary)] truncate">
                                        {detection.groupCol}
                                    </div>
                                    {detection.groupValues.length > 0 && (
                                        <div className="mt-1 text-xs text-[color:var(--text-secondary)]">
                                            {t('study_design_group_values', {
                                                count: detection.groupValues.length,
                                                values: detection.groupValues.slice(0, 3).join(', '),
                                                ellipsis: detection.groupValues.length > 3 ? '…' : ''
                                            })}
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}

                        {/* Timepoints */}
                        {detection.timepoints.length > 0 && (
                            <div className="flex items-start gap-2 p-3 rounded-[2px] bg-[color:var(--bg-secondary)]">
                                <ClockIcon className="w-4 h-4 text-blue-500 mt-0.5 flex-shrink-0" />
                                <div className="min-w-0">
                                    <div className="text-[10px] font-semibold uppercase tracking-wider text-[color:var(--text-muted)]">
                                        {t('study_design_timepoints_label')}
                                    </div>
                                    <div className="text-sm font-medium text-[color:var(--text-primary)]">
                                        {t('study_design_timepoints_count', { count: detection.timepoints.length })}
                                    </div>
                                    <div className="mt-1 text-xs text-[color:var(--text-secondary)] truncate">
                                        {detection.timepoints.slice(0, 4).join(', ')}{detection.timepoints.length > 4 ? '…' : ''}
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Endpoints */}
                        {detection.endpoints.length > 0 && (
                            <div className="flex items-start gap-2 p-3 rounded-[2px] bg-[color:var(--bg-secondary)]">
                                <ChartBarIcon className="w-4 h-4 text-purple-500 mt-0.5 flex-shrink-0" />
                                <div className="min-w-0">
                                    <div className="text-[10px] font-semibold uppercase tracking-wider text-[color:var(--text-muted)]">
                                        {t('study_design_endpoints_label')}
                                    </div>
                                    <div className="text-sm font-medium text-[color:var(--text-primary)]">
                                        {t('study_design_endpoints_count', { count: detection.endpoints.length })}
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Role selection */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
                        <div>
                            <label className="block text-xs font-semibold text-[color:var(--text-secondary)] mb-1">
                                {t('study_design_group_column_label')}
                            </label>
                            <select
                                value={localRoles.group || ''}
                                onChange={(e) => handleGroupChange(e.target.value)}
                                className="w-full h-10 px-3 bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] text-sm focus:outline-none focus:border-[color:var(--accent)]"
                            >
                                <option value="">{t('option_not_selected')}</option>
                                {groupColOptions.map((c) => (
                                    <option key={c.name} value={c.name}>
                                        {c.name} {c.name === detection.groupCol ? t('auto_suffix') : ''}
                                    </option>
                                ))}
                            </select>
                        </div>

                        <div>
                            <label className="block text-xs font-semibold text-[color:var(--text-secondary)] mb-1">
                                {t('study_design_target_column_label')}
                            </label>
                            <select
                                value={localRoles.target || ''}
                                onChange={(e) => handleTargetChange(e.target.value)}
                                className="w-full h-10 px-3 bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] text-sm focus:outline-none focus:border-[color:var(--accent)]"
                            >
                                <option value="">{t('option_not_selected')}</option>
                                {targetColOptions.map((c) => (
                                    <option key={c.name} value={c.name}>{c.name}</option>
                                ))}
                            </select>
                        </div>
                    </div>

                    {/* Recommendations */}
                    {detection.recommendations.length > 0 && (
                        <div className="pt-2">
                            <div className="text-[10px] font-semibold uppercase tracking-wider text-[color:var(--text-muted)] mb-2">
                                {t('study_design_recommended_tests')}
                            </div>
                            <div className="flex flex-wrap gap-2">
                                {detection.recommendations.slice(0, 5).map((rec, idx) => {
                                    const methodName = typeof rec === 'string'
                                        ? rec
                                        : rec?.method || rec?.method_id || t('test');
                                    return (
                                        <span
                                            key={idx}
                                            className="inline-flex items-center gap-1 px-2 py-1 rounded-[2px] bg-[color:var(--bg-tertiary)] text-xs text-[color:var(--text-secondary)]"
                                        >
                                            {methodName}
                                        </span>
                                    );
                                })}
                            </div>
                        </div>
                    )}

                    {/* Actions */}
                    <div className="flex items-center justify-between gap-3 pt-3 border-t border-[color:var(--border-color)]">
                        <button
                            type="button"
                            onClick={handleApplyDetection}
                            className="text-xs font-semibold text-[color:var(--accent)] hover:underline"
                        >
                            {t('study_design_apply_auto')}
                        </button>
                        <button
                            type="button"
                            onClick={handleConfirm}
                            disabled={isLoading}
                            className="h-9 px-4 rounded-[2px] bg-[color:var(--black)] text-[color:var(--white)] text-xs font-bold uppercase tracking-wider hover:opacity-90 disabled:opacity-50"
                        >
                            {isLoading ? t('study_design_confirming') : t('study_design_confirm')}
                        </button>
                    </div>

                    {/* Warning if no group selected */}
                    {!localRoles.group && detection.groupCol && (
                        <div className="flex items-start gap-2 p-3 rounded-[2px] bg-yellow-50 border border-yellow-200">
                            <ExclamationTriangleIcon className="w-4 h-4 text-yellow-600 mt-0.5 flex-shrink-0" />
                            <div className="text-xs text-yellow-800">
                                {t('study_design_group_recommendation', { name: detection.groupCol })}
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
