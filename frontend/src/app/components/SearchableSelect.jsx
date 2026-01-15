import React, { useState, useRef, useEffect, useMemo } from 'react';
import { MagnifyingGlassIcon, ChevronDownIcon, XMarkIcon } from '@heroicons/react/24/outline';

/**
 * SearchableSelect - A dropdown with search functionality for large option lists.
 * Replaces standard <select> when dealing with 50+ options.
 */
export default function SearchableSelect({
    value,
    onChange,
    options,
    placeholder = 'Select...',
    disabled = false,
    className = '',
    pinnedOptions = [],
    highlightedOptions = [],
    searchPlaceholder = 'Поиск…',
    emptyText = 'Ничего не найдено',
    countLabel = 'переменных'
}) {
    const [isOpen, setIsOpen] = useState(false);
    const [search, setSearch] = useState('');
    const containerRef = useRef(null);
    const inputRef = useRef(null);

    const pinnedSet = useMemo(() => new Set(Array.isArray(pinnedOptions) ? pinnedOptions : []), [pinnedOptions]);
    const highlightedSet = useMemo(() => new Set(Array.isArray(highlightedOptions) ? highlightedOptions : []), [highlightedOptions]);

    const normalizedOptions = useMemo(() => {
        const raw = Array.isArray(options) ? options : [];
        const pinned = (Array.isArray(pinnedOptions) ? pinnedOptions : []).filter((x) => raw.includes(x));
        const rest = raw.filter((x) => !pinnedSet.has(x));
        return [...pinned, ...rest];
    }, [options, pinnedOptions, pinnedSet]);

    const filteredOptions = useMemo(() => {
        if (!search.trim()) return normalizedOptions;
        const query = search.toLowerCase();
        return normalizedOptions.filter(opt =>
            String(opt).toLowerCase().includes(query)
        );
    }, [normalizedOptions, search]);

    // Close dropdown when clicking outside
    useEffect(() => {
        const handleClickOutside = (event) => {
            if (containerRef.current && !containerRef.current.contains(event.target)) {
                setIsOpen(false);
                setSearch('');
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    // Focus search input when dropdown opens
    useEffect(() => {
        if (isOpen && inputRef.current) {
            inputRef.current.focus();
        }
    }, [isOpen]);

    const handleSelect = (opt) => {
        onChange?.(opt);
        setIsOpen(false);
        setSearch('');
    };

    const handleClear = (e) => {
        e.stopPropagation();
        onChange?.('');
    };

    return (
        <div ref={containerRef} className={`relative ${className}`}>
            {/* Selected value display / trigger */}
            <button
                type="button"
                onClick={() => !disabled && setIsOpen(!isOpen)}
                disabled={disabled}
                className={`
          w-full px-3 py-2 bg-[color:var(--white)] border rounded-[2px] text-sm text-left
          flex items-center justify-between gap-2
          focus:outline-none focus:border-[color:var(--accent)]
          ${disabled ? 'opacity-50 cursor-not-allowed border-[color:var(--border-color)] bg-[color:var(--bg-secondary)]' : 'border-[color:var(--border-color)] hover:border-[color:var(--text-primary)]'}
        `}
            >
                <span className={value ? 'text-[color:var(--text-primary)]' : 'text-[color:var(--text-secondary)]'}>
                    {value || placeholder}
                </span>
                <div className="flex items-center gap-1">
                    {value && !disabled && (
                        <XMarkIcon
                            className="w-4 h-4 text-[color:var(--text-muted)] hover:text-[color:var(--text-primary)]"
                            onClick={handleClear}
                        />
                    )}
                    <ChevronDownIcon className={`w-4 h-4 text-[color:var(--text-muted)] transition-transform ${isOpen ? 'rotate-180' : ''}`} />
                </div>
            </button>

            {/* Dropdown panel */}
            {isOpen && (
                <div className="absolute z-50 mt-1 w-full bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] overflow-hidden">
                    {/* Search input */}
                    <div className="p-2 border-b border-[color:var(--border-color)]">
                        <div className="relative">
                            <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[color:var(--text-muted)]" />
                            <input
                                ref={inputRef}
                                type="text"
                                value={search}
                                onChange={(e) => setSearch(e.target.value)}
                                placeholder={searchPlaceholder}
                                className="w-full pl-9 pr-3 py-2 text-sm border border-[color:var(--border-color)] rounded-[2px] bg-[color:var(--white)] focus:outline-none focus:border-[color:var(--accent)]"
                            />
                        </div>
                    </div>

                    {/* Options list */}
                    <div className="max-h-60 overflow-y-auto">
                        {filteredOptions.length === 0 ? (
                            <div className="p-3 text-sm text-[color:var(--text-secondary)] text-center">
                                {emptyText}
                            </div>
                        ) : (
                            filteredOptions.map((opt) => (
                                <button
                                    key={opt}
                                    type="button"
                                    onClick={() => handleSelect(opt)}
                                    className={`
                    w-full px-3 py-2 text-sm text-left hover:bg-[color:var(--bg-secondary)]
                    ${opt === value ? 'bg-[color:var(--bg-secondary)] text-[color:var(--accent)] font-semibold' : highlightedSet.has(opt) ? 'bg-[color:var(--bg-secondary)] text-[color:var(--text-primary)]' : 'text-[color:var(--text-primary)]'}
                  `}
                                >
                                    <div className="flex items-center justify-between gap-2">
                                        <span className="truncate">{opt}</span>
                                        {highlightedSet.has(opt) && opt !== value && (
                                            <span className="flex-shrink-0 text-[10px] font-semibold tracking-[0.18em] uppercase text-[color:var(--accent)]">
                                                Подсказка
                                            </span>
                                        )}
                                    </div>
                                </button>
                            ))
                        )}
                    </div>

                    {/* Count indicator */}
                    <div className="px-3 py-2 border-t border-[color:var(--border-color)] text-xs text-[color:var(--text-secondary)] bg-[color:var(--bg-secondary)]">
                        {filteredOptions.length} / {normalizedOptions.length} {countLabel}
                    </div>
                </div>
            )}
        </div>
    );
}
