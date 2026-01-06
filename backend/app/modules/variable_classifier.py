"""
Variable Auto-Classification Module
Analyzes column names to automatically suggest roles and timepoints.
"""
import re
from typing import Dict, List, Any

# Patterns for timepoint detection
TIMEPOINT_PATTERNS = [
    (r'[_\s]?V(\d+)$', lambda m: f'V{m.group(1)}'),           # _V0, _V1, V0, V1
    (r'[_\s]?(\d+)$', lambda m: f'V{m.group(1)}'),             # _0, _1, variable_2
    (r'baseline', lambda m: 'V0'),                              # baseline
    (r'скрининг', lambda m: 'V0'),                             # скрининг (Russian)
    (r'визит[_\s]?(\d+)', lambda m: f'V{m.group(1)}'),         # визит1, визит_2
    (r'visit[_\s]?(\d+)', lambda m: f'V{m.group(1)}'),         # visit1, visit_2
]

# Keywords for group detection
GROUP_KEYWORDS = [
    'group', 'группа', 'group_id', 'arm', 'treatment', 'лечение',
    'cohort', 'когорта', 'condition', 'состояние'
]

# Keywords for subgroup detection
SUBGROUP_KEYWORDS = [
    'subgroup', 'подгруппа', 'stratum', 'страта', 'center', 'центр',
    'site', 'сайт', 'site_id'
]

# Keywords for exclusion (IDs, metadata)
EXCLUDE_KEYWORDS = [
    'id', 'uuid', 'patient_id', 'subject_id', 'record_id',
    'номер', 'участник', 'исследования', 'дата', 'date', 'created',
    'updated', 'timestamp', 'критерии', 'criteria', 'inclusion', 'exclusion',
    'включения', 'невключения', 'исключения', 'комментарий', 'comment', 'note',
    'аппарат', 'device', 'equipment', 'база'
]

# Gender/sex columns (often good group candidates)
SEX_KEYWORDS = ['sex', 'пол', 'gender', 'male', 'female']


def classify_variables(columns: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Automatically classify variables based on column names and types.
    
    Args:
        columns: List of column info dicts with 'name' and 'type' keys
        
    Returns:
        Dict mapping column names to suggested {type, role, timepoint, reason}
    """
    result = {}
    group_candidates = []
    
    for col in columns:
        name = col.get('name', '')
        col_type = col.get('type', 'text')
        name_lower = name.lower()
        
        # Default values
        role = 'parameter'
        timepoint = None
        reason = None
        
        # 1. Check for exclusion keywords
        if any(kw in name_lower for kw in EXCLUDE_KEYWORDS):
            role = 'exclude'
            matched = [kw for kw in EXCLUDE_KEYWORDS if kw in name_lower]
            reason = f"Служебное поле ({matched[0]})"
        
        # 2. Check for group keywords
        elif any(kw in name_lower for kw in GROUP_KEYWORDS):
            group_candidates.append((name, 1))
            role = 'group'
            matched = [kw for kw in GROUP_KEYWORDS if kw in name_lower]
            reason = f"Группирующая переменная ({matched[0]})"
        
        # 3. Check for sex/gender (good group candidate)
        elif any(kw in name_lower for kw in SEX_KEYWORDS):
            group_candidates.append((name, 2))
            role = 'group'
            reason = "Демографический признак (пол)"
        
        # 4. Check for subgroup keywords
        elif any(kw in name_lower for kw in SUBGROUP_KEYWORDS):
            role = 'subgroup'
            matched = [kw for kw in SUBGROUP_KEYWORDS if kw in name_lower]
            reason = f"Подгруппа ({matched[0]})"
        
        # 5. Check for timepoint patterns (only for parameters)
        if role == 'parameter':
            for pattern, extractor in TIMEPOINT_PATTERNS:
                match = re.search(pattern, name_lower, re.IGNORECASE)
                if match:
                    try:
                        timepoint = extractor(match)
                        tp_num = int(timepoint[1:])
                        if tp_num > 9:
                            timepoint = None
                        else:
                            reason = f"Timepoint определён по названию"
                        break
                    except:
                        pass
        
        # 6. Mark non-numeric parameters
        if col_type in ['categorical', 'text'] and role == 'parameter':
            role = 'exclude'
            reason = f"Не числовой тип ({col_type})"
        
        result[name] = {
            'type': col_type,
            'role': role,
            'timepoint': timepoint,
            'reason': reason
        }
    
    # Ensure only one primary group
    if group_candidates:
        group_candidates.sort(key=lambda x: x[1])
        primary_group = group_candidates[0][0]
        
        for name in result:
            if result[name]['role'] == 'group' and name != primary_group:
                result[name]['role'] = 'subgroup'
                result[name]['reason'] = "Доп. группирующая переменная"
    
    return result



def get_classification_summary(classification: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Get summary statistics of the classification."""
    roles = {'parameter': 0, 'group': 0, 'subgroup': 0, 'exclude': 0}
    timepoints = set()
    
    for name, cfg in classification.items():
        roles[cfg.get('role', 'parameter')] += 1
        if cfg.get('timepoint'):
            timepoints.add(cfg['timepoint'])
    
    return {
        'total': len(classification),
        'roles': roles,
        'timepoints': sorted(timepoints),
        'has_group': roles['group'] > 0
    }
