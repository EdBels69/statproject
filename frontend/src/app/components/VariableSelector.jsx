import { useMemo, useState } from 'react';

const TypeIcon = ({ type }) => {
    const getLabel = () => {
        switch (type) {
            case 'numeric': return 'NUM';
            case 'categorical': return 'CAT';
            case 'datetime': return 'DAT';
            default: return 'TXT';
        }
    };
    return (
        <span style={{
            fontFamily: 'monospace',
            fontSize: '9px',
            fontWeight: 'bold',
            color: 'var(--accent)',
            background: 'rgba(249, 115, 22, 0.15)',
            padding: '2px 6px',
            borderRadius: '3px'
        }}>
            {getLabel()}
        </span>
    );
};

export default function VariableSelector({ allColumns, onRun, loading }) {
    const [targetCols, setTargetCols] = useState([]);
    const [groupCol, setGroupCol] = useState(null);
    const [selectedAvailableNames, setSelectedAvailableNames] = useState([]);
    const [selectedTargetNames, setSelectedTargetNames] = useState([]);

    const available = useMemo(() => {
        const taken = new Set([
            ...targetCols.map(c => c?.name).filter(Boolean),
            groupCol?.name
        ].filter(Boolean));
        return (Array.isArray(allColumns) ? allColumns : []).filter(c => c && !taken.has(c.name));
    }, [allColumns, targetCols, groupCol]);

    const moveRightTarget = () => {
        const toMove = available.filter(c => selectedAvailableNames.includes(c.name));
        setTargetCols([...targetCols, ...toMove]);
        setSelectedAvailableNames([]);
    };

    const moveRightGroup = () => {
        if (selectedAvailableNames.length !== 1) return;
        const next = available.find(c => c.name === selectedAvailableNames[0]);
        if (!next) return;
        setGroupCol(next);
        setSelectedAvailableNames([]);
    };

    const moveLeftTarget = () => {
        setTargetCols(targetCols.filter(c => !selectedTargetNames.includes(c.name)));
        setSelectedTargetNames([]);
    };

    const removeGroup = () => {
        if (groupCol) setGroupCol(null);
    };

    const renderItem = (col, isSelected, onClick) => (
        <div
            key={col.name}
            onClick={onClick}
            style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                padding: '8px 12px',
                cursor: 'pointer',
                background: isSelected ? 'rgba(249, 115, 22, 0.1)' : 'transparent',
                borderBottom: '1px solid var(--border-color)',
                transition: 'background 0.15s'
            }}
        >
            <TypeIcon type={col.type} />
            <span style={{
                fontSize: '12px',
                fontFamily: 'monospace',
                color: isSelected ? 'var(--accent)' : 'var(--text-secondary)',
                fontWeight: isSelected ? '600' : '400',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap'
            }} title={col.name}>
                {col.name}
            </span>
        </div>
    );

    const sectionStyle = {
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        border: '1px solid var(--border-color)',
        borderRadius: '6px',
        overflow: 'hidden',
        minHeight: 0
    };

    const headerStyle = {
        background: 'var(--bg-tertiary)',
        padding: '8px 12px',
        borderBottom: '1px solid var(--border-color)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
    };

    const labelStyle = {
        fontSize: '10px',
        fontWeight: '600',
        textTransform: 'uppercase',
        letterSpacing: '0.05em',
        color: 'var(--text-muted)'
    };

    const countStyle = {
        fontSize: '10px',
        fontFamily: 'monospace',
        color: 'var(--text-muted)'
    };

    return (
        <div style={{
            display: 'flex',
            flexDirection: 'column',
            height: '100%',
            background: 'var(--bg-secondary)'
        }}>
            <div style={{
                padding: '16px',
                borderBottom: '1px solid var(--border-color)'
            }}>
                <h2 style={{
                    fontSize: '11px',
                    fontWeight: '600',
                    textTransform: 'uppercase',
                    letterSpacing: '0.1em',
                    color: 'var(--text-primary)'
                }}>
                    Configuration
                </h2>
            </div>

            <div style={{
                display: 'flex',
                flexDirection: 'column',
                flex: 1,
                padding: '16px',
                gap: '12px',
                minHeight: 0,
                overflow: 'hidden'
            }}>
                {/* Available */}
                <div style={sectionStyle}>
                    <div style={headerStyle}>
                        <span style={labelStyle}>Available</span>
                        <span style={countStyle}>{available.length}</span>
                    </div>
                <div style={{ flex: 1, overflowY: 'auto' }}>
                    {available.map(col => renderItem(
                        col,
                        selectedAvailableNames.includes(col.name),
                        () => {
                                if (selectedAvailableNames.includes(col.name)) {
                                    setSelectedAvailableNames(selectedAvailableNames.filter(n => n !== col.name));
                                } else {
                                    setSelectedAvailableNames([...selectedAvailableNames, col.name]);
                                }
                        }
                    ))}
                </div>
                </div>

                {/* Actions */}
                <div style={{ display: 'flex', justifyContent: 'center', gap: '8px' }}>
                    <button
                        onClick={moveRightTarget}
                        disabled={selectedAvailableNames.length === 0}
                        className="btn-secondary"
                        style={{ fontSize: '10px', padding: '6px 12px' }}
                    >
                        Add Y ↓
                    </button>
                    <button
                        onClick={moveLeftTarget}
                        disabled={selectedTargetNames.length === 0}
                        className="btn-secondary"
                        style={{ fontSize: '10px', padding: '6px 12px' }}
                    >
                        Remove ↑
                    </button>
                </div>

                {/* Target Variables (Y) */}
                <div style={sectionStyle}>
                    <div style={headerStyle}>
                        <span style={labelStyle}>Dependent (Y)</span>
                        <span style={countStyle}>{targetCols.length}</span>
                    </div>
                    <div style={{ flex: 1, overflowY: 'auto', position: 'relative' }}>
                        {targetCols.length === 0 && (
                            <div style={{
                                position: 'absolute',
                                inset: 0,
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                fontSize: '10px',
                                color: 'var(--text-muted)'
                            }}>
                                Empty
                            </div>
                        )}
                        {targetCols.map(col => renderItem(
                            col,
                            selectedTargetNames.includes(col.name),
                            () => {
                                if (selectedTargetNames.includes(col.name)) {
                                    setSelectedTargetNames(selectedTargetNames.filter(n => n !== col.name));
                                } else {
                                    setSelectedTargetNames([...selectedTargetNames, col.name]);
                                }
                            }
                        ))}
                    </div>
                </div>

                {/* Grouping Variable (X) */}
                <div style={{
                    ...sectionStyle,
                    flex: 'none',
                    height: '80px'
                }}>
                    <div style={headerStyle}>
                        <span style={labelStyle}>Grouping (X)</span>
                        <button
                            onClick={moveRightGroup}
                            disabled={selectedAvailableNames.length !== 1 || !!groupCol}
                            style={{
                                fontSize: '9px',
                                color: 'var(--accent)',
                                background: 'none',
                                border: 'none',
                                cursor: 'pointer',
                                opacity: selectedAvailableNames.length !== 1 || !!groupCol ? 0 : 1
                            }}
                        >
                            Assign
                        </button>
                    </div>
                    <div style={{
                        flex: 1,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        padding: '0 12px'
                    }}>
                        {groupCol ? (
                            <div style={{
                                width: '100%',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between'
                            }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                    <TypeIcon type={groupCol.type} />
                                    <span style={{
                                        fontSize: '12px',
                                        fontFamily: 'monospace',
                                        color: 'var(--text-primary)',
                                        fontWeight: '600'
                                    }}>
                                        {groupCol.name}
                                    </span>
                                </div>
                                <button
                                    onClick={removeGroup}
                                    style={{
                                        background: 'none',
                                        border: 'none',
                                        color: 'var(--text-muted)',
                                        fontSize: '16px',
                                        cursor: 'pointer'
                                    }}
                                >
                                    ×
                                </button>
                            </div>
                        ) : (
                            <div style={{
                                fontSize: '10px',
                                color: 'var(--text-muted)'
                            }}>
                                Not selected
                            </div>
                        )}
                    </div>
                </div>

                {/* Run Button */}
                <button
                    onClick={() => onRun(targetCols.map(c => c.name), groupCol ? groupCol.name : null)}
                    disabled={!targetCols.length || !groupCol || loading}
                    className="btn-primary"
                    style={{
                        width: '100%',
                        padding: '12px',
                        fontSize: '11px',
                        fontWeight: '600',
                        textTransform: 'uppercase',
                        letterSpacing: '0.1em'
                    }}
                >
                    {loading ? 'Processing...' : 'Run Analysis'}
                </button>
            </div>
        </div>
    );
}
