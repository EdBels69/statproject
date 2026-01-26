import pandas as pd
from typing import List, Dict, Any, Optional
import numpy as np
import re


def _omni_norm_col(name: Any) -> str:
    s = "" if name is None else str(name)
    s = s.strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _omni_slug(value: str) -> str:
    s = _omni_norm_col(value).lower()
    s = re.sub(r"[^a-z0-9а-яё]+", "_", s, flags=re.IGNORECASE)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "x"


def _omni_extract_visit(col: str) -> Optional[Dict[str, Any]]:
    s = _omni_norm_col(col)
    if not s:
        return None

    lower = s.lower()
    baseline_patterns = [r"(?:^|[\s_\-])bl(?:$|[\s_\-])", r"(?:^|[\s_\-])baseline(?:$|[\s_\-])", r"(?:^|[\s_\-])base(?:$|[\s_\-])"]
    for pat in baseline_patterns:
        if re.search(pat, lower, flags=re.IGNORECASE):
            base = re.sub(pat, " ", s, flags=re.IGNORECASE)
            base = re.sub(r"[\s_\-]+", "_", base).strip("_ ")
            if not base:
                return None
            return {"visit_id": "BL", "label": "BL", "order": 0, "base": base}

    m = re.search(r"(?:^|[\s_\-])(?:v|visit|week|w|month|m|day|d)\s*0*(\d+)(?:$|[\s_\-])", lower, flags=re.IGNORECASE)
    if not m:
        m = re.search(r"(?:^|[\s_\-])v\s*0*(\d+)(?:$|[\s_\-])", lower, flags=re.IGNORECASE)
    if not m:
        return None

    try:
        n = int(m.group(1))
    except Exception:
        return None

    base = re.sub(m.re.pattern, " ", s, flags=re.IGNORECASE)
    base = re.sub(r"[\s_\-]+", "_", base).strip("_ ")
    if not base:
        return None
    return {"visit_id": f"V{n}", "label": f"V{n}", "order": n, "base": base}


def _omni_pick_subject_id(df: pd.DataFrame, candidate_cols: List[str]) -> Optional[str]:
    best = None
    best_score = -1.0
    n = int(len(df)) if isinstance(df, pd.DataFrame) else 0
    if n <= 1:
        return None
    for col in candidate_cols:
        if col not in df.columns:
            continue
        s = df[col]
        try:
            non_na = s.dropna()
            u = int(non_na.nunique(dropna=True))
            ratio = u / max(1, int(len(non_na)))
        except Exception:
            continue

        name_l = str(col).lower()
        name_bonus = 0.0
        if any(k in name_l for k in ["subject", "patient", "case", "participant", "id", "пациент", "субъект"]):
            name_bonus += 0.2
        if name_l.endswith("id") or name_l.endswith("_id"):
            name_bonus += 0.15

        score = ratio + name_bonus
        if score > best_score and ratio >= 0.6:
            best_score = score
            best = col
    return best


def _omni_pick_group(df: pd.DataFrame, candidate_cols: List[str], subject_col: Optional[str]) -> Optional[str]:
    best = None
    best_score = -1.0
    n = int(len(df)) if isinstance(df, pd.DataFrame) else 0
    if n <= 1:
        return None
    for col in candidate_cols:
        if col not in df.columns:
            continue
        if subject_col and col == subject_col:
            continue
        s = df[col]
        try:
            non_na = s.dropna()
            u = int(non_na.nunique(dropna=True))
        except Exception:
            continue
        if u < 2 or u > 12:
            continue

        name_l = str(col).lower()
        name_bonus = 0.0
        if any(k in name_l for k in ["group", "arm", "treat", "treatment", "cohort", "grp", "группа", "лечен", "плацебо", "рандом"]):
            name_bonus += 0.35
        if u in (2, 3, 4):
            name_bonus += 0.1

        missing_ratio = 1.0
        try:
            missing_ratio = float(non_na.isna().mean())
        except Exception:
            missing_ratio = 0.0

        score = name_bonus + (1.0 - missing_ratio) + (1.0 - abs(u - 2) * 0.05)
        if score > best_score:
            best_score = score
            best = col
    return best


def _omni_strip_token(s: Any) -> str:
    out = "" if s is None else str(s)
    out = out.strip()
    out = re.sub(r"^[\s\-\*\u2022]+", "", out)
    if (out.startswith('"') and out.endswith('"')) or (out.startswith("'") and out.endswith("'")):
        out = out[1:-1].strip()
    if out.startswith("`") and out.endswith("`"):
        out = out[1:-1].strip()
    return out


def _omni_split_list(s: Any) -> List[str]:
    raw = _omni_strip_token(s)
    if not raw:
        return []
    raw = raw.replace("\t", " ")
    parts = re.split(r"[\n,;|]+", raw)
    out: List[str] = []
    for p in parts:
        t = _omni_strip_token(p)
        if t:
            out.append(t)
    return out


def _omni_parse_bool(s: Any) -> Optional[bool]:
    v = _omni_strip_token(s).lower()
    if not v:
        return None
    if v in {"1", "true", "yes", "y", "да", "истина", "on"}:
        return True
    if v in {"0", "false", "no", "n", "нет", "ложь", "off"}:
        return False
    return None


def _omni_norm_key(s: Any) -> str:
    out = _omni_strip_token(s).lower()
    out = out.replace(" ", "_")
    out = re.sub(r"_+", "_", out).strip("_")
    return out


def _omni_canon_visit_id(v: Any) -> Optional[str]:
    raw = _omni_strip_token(v)
    if not raw:
        return None
    s = raw.strip().upper().replace(" ", "")
    if not s:
        return None
    if s in {"BL", "BASELINE", "BASE"}:
        return "BL"
    m = re.match(r"^V0*(\d+)$", s)
    if m:
        return f"V{int(m.group(1))}"
    return s


def _omni_column_lookup(columns: List[str]) -> Dict[str, str]:
    m: Dict[str, str] = {}
    for c in columns or []:
        if c is None:
            continue
        sc = _omni_norm_col(c)
        if not sc:
            continue
        m[sc.lower()] = sc
    return m


def _omni_resolve_column(token: Any, colmap: Dict[str, str]) -> Optional[str]:
    t = _omni_strip_token(token)
    if not t:
        return None
    key = _omni_norm_col(t).lower()
    if key in colmap:
        return colmap[key]
    key2 = re.sub(r"\s+", " ", key).strip()
    if key2 in colmap:
        return colmap[key2]
    return None


def _omni_parse_kv_blob(blob: str) -> Dict[str, str]:
    raw = _omni_strip_token(blob)
    if not raw:
        return {}
    out: Dict[str, str] = {}
    parts = re.split(r"[,;\n]+", raw)
    for p in parts:
        seg = _omni_strip_token(p)
        if not seg:
            continue
        if "=" not in seg and ":" not in seg:
            continue
        if "=" in seg:
            k, v = seg.split("=", 1)
        else:
            k, v = seg.split(":", 1)
        kk = _omni_norm_key(k)
        vv = _omni_strip_token(v)
        if kk and vv:
            out[kk] = vv
    return out


class OmniReportDesignEngine:
    def suggest_design_spec(self, dataset_id: str, df: pd.DataFrame, columns: List[str]) -> Dict[str, Any]:
        cols = [_omni_norm_col(c) for c in (columns or []) if c is not None]

        endpoint_map: Dict[str, Dict[str, str]] = {}
        visits_map: Dict[str, Dict[str, Any]] = {}
        for c in cols:
            hit = _omni_extract_visit(c)
            if not hit:
                continue
            base = hit["base"]
            visit_id = hit["visit_id"]
            endpoint_map.setdefault(base, {})[visit_id] = c
            if visit_id not in visits_map:
                visits_map[visit_id] = {"id": visit_id, "label": hit["label"], "order": int(hit["order"])}

        issues: List[str] = []

        sample_df = df
        if not isinstance(sample_df, pd.DataFrame):
            sample_df = pd.DataFrame()
        if len(sample_df) > 5000:
            sample_df = sample_df.iloc[:5000]

        subject_candidates = [c for c in cols if any(k in str(c).lower() for k in ["subject", "patient", "participant", "case", "id", "пациент", "субъект"])]
        group_candidates = [c for c in cols if any(k in str(c).lower() for k in ["group", "arm", "treat", "treatment", "cohort", "grp", "группа", "лечен", "плацебо"])]

        fallback_candidates = [c for c in cols if c]
        subject_col = _omni_pick_subject_id(sample_df, subject_candidates + fallback_candidates)
        group_col = _omni_pick_group(sample_df, group_candidates + fallback_candidates, subject_col)

        if not subject_col:
            issues.append("Не удалось уверенно распознать колонку идентификатора субъекта")
        if not group_col:
            issues.append("Не удалось уверенно распознать колонку группы/лечения")

        visits = sorted(visits_map.values(), key=lambda x: (int(x.get("order") or 0), str(x.get("id") or "")))
        baseline_visit_id = None
        if "BL" in visits_map:
            baseline_visit_id = "BL"
        else:
            numbered = [v for v in visits if v.get("id") and str(v.get("id")).upper().startswith("V")]
            if numbered:
                baseline_visit_id = str(numbered[0]["id"])

        endpoints: List[Dict[str, Any]] = []
        for base, by_visit in sorted(endpoint_map.items(), key=lambda kv: kv[0].lower()):
            if not isinstance(by_visit, dict) or not by_visit:
                continue
            ep_id = _omni_slug(base)
            endpoints.append(
                {
                    "id": ep_id,
                    "name": base,
                    "primary": False,
                    "direction": None,
                    "baseline_visit_id": baseline_visit_id,
                    "columns_by_visit": {str(k): str(v) for k, v in by_visit.items()},
                }
            )

        if not endpoints:
            issues.append("Не удалось распознать эндпоинты/визиты по именам колонок")

        confidence = 0.2
        if subject_col:
            confidence += 0.3
        if group_col:
            confidence += 0.2
        any_repeated = any(len(ep.get("columns_by_visit") or {}) >= 2 for ep in endpoints)
        if any_repeated:
            confidence += 0.3
        if baseline_visit_id:
            confidence += 0.1
        confidence = max(0.0, min(1.0, float(confidence)))

        survival: Optional[Dict[str, str]] = None
        try:
            if isinstance(sample_df, pd.DataFrame) and not sample_df.empty:
                time_candidates = [c for c in cols if any(k in str(c).lower() for k in ["time_to", "time", "days", "duration", "follow", "os", "pfs"])]
                event_candidates = [c for c in cols if any(k in str(c).lower() for k in ["event", "status", "death", "progress", "censor"])]

                time_col = None
                for c in time_candidates:
                    if c not in sample_df.columns:
                        continue
                    s = pd.to_numeric(sample_df[c], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
                    if len(s) >= 10 and float(s.min()) >= 0.0:
                        time_col = c
                        break

                event_col = None
                for c in event_candidates:
                    if c not in sample_df.columns:
                        continue
                    s = sample_df[c].dropna()
                    if s.empty:
                        continue
                    uniq = list(pd.unique(s))
                    if len(uniq) == 2:
                        event_col = c
                        break
                    if len(uniq) == 1:
                        continue
                    s_num = pd.to_numeric(s, errors="coerce").dropna()
                    uniq_num = sorted(set(float(v) for v in pd.unique(s_num)))
                    if set(uniq_num) <= {0.0, 1.0} and len(uniq_num) >= 1:
                        event_col = c
                        break

                if time_col and event_col:
                    survival = {"time_column": str(time_col), "event_column": str(event_col)}
        except Exception:
            survival = None

        return {
            "design_spec": {
                "dataset_id": dataset_id,
                "subject_id_column": subject_col,
                "group_column": group_col,
                "time": {"format": "wide", "baseline_visit_id": baseline_visit_id, "visits": visits},
                "endpoints": endpoints,
                "covariates": [],
                "survival": survival,
            },
            "confidence": confidence,
            "issues": issues,
        }

    def parse_design_spec(self, dataset_id: str, df: pd.DataFrame, columns: List[str], text: str) -> Dict[str, Any]:
        base = self.suggest_design_spec(dataset_id, df, columns)
        ds = base.get("design_spec") if isinstance(base.get("design_spec"), dict) else {"dataset_id": dataset_id}
        issues: List[str] = list(base.get("issues") or []) if isinstance(base.get("issues"), list) else []
        confidence = float(base.get("confidence") or 0.0)

        colmap = _omni_column_lookup([_omni_norm_col(c) for c in (columns or []) if c is not None])
        raw = _omni_strip_token(text)
        if not raw:
            issues.append("Пустое текстовое описание дизайна")
            return {"design_spec": ds, "confidence": confidence, "issues": issues}

        time = ds.get("time") if isinstance(ds.get("time"), dict) else {}
        ds["time"] = time
        endpoints = ds.get("endpoints") if isinstance(ds.get("endpoints"), list) else []
        ds["endpoints"] = endpoints
        opts = ds.get("options") if isinstance(ds.get("options"), dict) else {}
        ds["options"] = opts

        ep_index: Dict[str, Dict[str, Any]] = {}
        for ep in endpoints:
            if not isinstance(ep, dict):
                continue
            ep_id = _omni_norm_key(ep.get("id")) if isinstance(ep.get("id"), str) else ""
            ep_name = _omni_norm_key(ep.get("name")) if isinstance(ep.get("name"), str) else ""
            if ep_id:
                ep_index[ep_id] = ep
            if ep_name:
                ep_index[ep_name] = ep

        def _bump(ok: bool, delta: float = 0.05) -> None:
            nonlocal confidence
            if ok:
                confidence = max(0.0, min(1.0, float(confidence + delta)))

        lines = [ln for ln in re.split(r"\r?\n+", raw) if _omni_strip_token(ln)]
        for ln in lines:
            line = _omni_strip_token(ln)
            lower = line.lower()

            if re.match(r"^(dataset|dataset_id|датасет|набор_данных)\b", lower):
                continue

            if re.match(r"^(subject|subject_id|patient|id_?column|субъект|пациент|идентификатор)\b", lower) and (":" in line or "=" in line):
                sep = ":" if ":" in line else "="
                _, v = line.split(sep, 1)
                col = _omni_resolve_column(v, colmap)
                if col:
                    ds["subject_id_column"] = col
                    _bump(True)
                else:
                    issues.append(f"Колонка subject_id не найдена: {v}")
                continue

            if re.match(r"^(group|arm|treat|treatment|cohort|группа|лечени)\b", lower) and (":" in line or "=" in line):
                sep = ":" if ":" in line else "="
                _, v = line.split(sep, 1)
                col = _omni_resolve_column(v, colmap)
                if col:
                    ds["group_column"] = col
                    _bump(True)
                else:
                    issues.append(f"Колонка group не найдена: {v}")
                continue

            if re.match(r"^(format|time_format|wide|long|формат)\b", lower) and (":" in line or "=" in line):
                sep = ":" if ":" in line else "="
                _, v = line.split(sep, 1)
                fmt = _omni_norm_key(v)
                if fmt in {"wide", "широкий", "широк"}:
                    time["format"] = "wide"
                    _bump(True)
                elif fmt in {"long", "длинный", "длин"}:
                    time["format"] = "long"
                    _bump(True)
                else:
                    issues.append(f"Неизвестный формат времени: {v}")
                continue

            if re.match(r"^(baseline|baseline_visit|base|bl|исход|базов)\b", lower) and (":" in line or "=" in line):
                sep = ":" if ":" in line else "="
                _, v = line.split(sep, 1)
                base_vid = _omni_strip_token(v)
                if base_vid:
                    time["baseline_visit_id"] = base_vid
                    for ep in endpoints:
                        if isinstance(ep, dict):
                            ep["baseline_visit_id"] = base_vid
                    _bump(True)
                continue

            if re.match(r"^(include_visits|exclude_visits)\b", lower) and (":" in line or "=" in line):
                sep = ":" if ":" in line else "="
                k_raw, v_raw = line.split(sep, 1)
                key = _omni_norm_key(k_raw)
                visit_ids = [_omni_canon_visit_id(x) for x in _omni_split_list(v_raw)]
                visit_ids = [x for x in visit_ids if isinstance(x, str) and x]
                if key == "include_visits":
                    ds["include_visits"] = visit_ids
                    _bump(bool(visit_ids))
                elif key == "exclude_visits":
                    ds["exclude_visits"] = visit_ids
                    _bump(bool(visit_ids))
                continue

            if re.match(r"^(visits|visit_ids|visit|визиты|посещения)\b", lower) and (":" in line or "=" in line):
                sep = ":" if ":" in line else "="
                _, v = line.split(sep, 1)
                visit_ids = _omni_split_list(v)
                if visit_ids:
                    visits_out: List[Dict[str, Any]] = []
                    for vid in visit_ids:
                        vid_s = _omni_strip_token(vid)
                        if not vid_s:
                            continue
                        if _omni_norm_key(vid_s) in {"bl", "baseline"}:
                            vid_s = "BL"
                        order = 0
                        m = re.match(r"^v\s*0*(\d+)$", vid_s.strip(), flags=re.IGNORECASE)
                        if m:
                            try:
                                order = int(m.group(1))
                            except Exception:
                                order = len(visits_out)
                        elif vid_s.upper() == "BL":
                            order = 0
                        else:
                            order = len(visits_out)
                        visits_out.append({"id": vid_s, "label": vid_s, "order": order})
                    time["visits"] = visits_out
                    _bump(True)
                continue

            if re.match(r"^(covariates|covars|adjust|ковариаты|ковариат|сопутств)\b", lower) and (":" in line or "=" in line):
                sep = ":" if ":" in line else "="
                _, v = line.split(sep, 1)
                covs_raw = _omni_split_list(v)
                covs: List[str] = []
                for c in covs_raw:
                    col = _omni_resolve_column(c, colmap)
                    if col:
                        covs.append(col)
                    else:
                        issues.append(f"Ковариата не найдена: {c}")
                ds["covariates"] = list(dict.fromkeys(covs))
                _bump(bool(covs))
                continue

            if re.match(r"^(options|опции|settings|настройки)\b", lower) and (":" in line or "=" in line):
                sep = ":" if ":" in line else "="
                _, v = line.split(sep, 1)
                kv = _omni_parse_kv_blob(v)
                any_ok = False
                for k, vv in kv.items():
                    b = _omni_parse_bool(vv)
                    if b is not None:
                        opts[k] = bool(b)
                        any_ok = True
                        continue
                    raw_v = _omni_strip_token(vv)
                    if raw_v:
                        opts[k] = raw_v
                        any_ok = True
                _bump(any_ok)
                continue

            if re.match(r"^(survival|time_to_event|выживаем|смертн)\b", lower) and (":" in line or "=" in line):
                sep = ":" if ":" in line else "="
                _, v = line.split(sep, 1)
                kv = _omni_parse_kv_blob(v)
                tcol = kv.get("time") or kv.get("time_column") or kv.get("duration") or kv.get("days")
                ecol = kv.get("event") or kv.get("event_column") or kv.get("status")
                t_res = _omni_resolve_column(tcol, colmap) if tcol else None
                e_res = _omni_resolve_column(ecol, colmap) if ecol else None
                if t_res and e_res:
                    ds["survival"] = {"time_column": t_res, "event_column": e_res}
                    _bump(True)
                else:
                    if tcol and not t_res:
                        issues.append(f"Колонка времени выживаемости не найдена: {tcol}")
                    if ecol and not e_res:
                        issues.append(f"Колонка события выживаемости не найдена: {ecol}")
                continue

            m_primary = re.match(r"^(primary_endpoint|primary|первичн(?:ый|ая)?)\b", lower)
            if m_primary and (":" in line or "=" in line):
                sep = ":" if ":" in line else "="
                _, v = line.split(sep, 1)
                ep_key = _omni_norm_key(v)
                ep = ep_index.get(ep_key)
                if isinstance(ep, dict):
                    for epp in endpoints:
                        if isinstance(epp, dict):
                            epp["primary"] = False
                    ep["primary"] = True
                    _bump(True)
                else:
                    issues.append(f"Эндпоинт не найден для primary: {v}")
                continue

            if re.match(r"^(endpoint|эндпоинт|показатель|endpoint\s+|показатель\s+)", lower):
                rest = re.sub(r"^(endpoint|эндпоинт|показатель)\s*", "", line, flags=re.IGNORECASE).strip()
                if not rest:
                    continue

                name_part = rest
                attr_part = ""
                if ":" in rest:
                    name_part, attr_part = rest.split(":", 1)
                name = _omni_strip_token(name_part)
                if not name:
                    continue
                ep = ep_index.get(_omni_norm_key(name))
                if not isinstance(ep, dict):
                    issues.append(f"Эндпоинт не найден: {name}")
                    continue

                tokens = _omni_split_list(attr_part) if attr_part else []
                blob = " ".join(tokens) if tokens else rest
                kv = _omni_parse_kv_blob(attr_part) if attr_part else _omni_parse_kv_blob(rest)

                if "primary" in blob.lower() or kv.get("primary"):
                    for epp in endpoints:
                        if isinstance(epp, dict):
                            epp["primary"] = False
                    ep["primary"] = True
                    _bump(True)

                dir_raw = kv.get("direction")
                if not dir_raw:
                    if re.search(r"\bdecrease\b|\bснижен\b|\bуменьш\b", blob, flags=re.IGNORECASE):
                        dir_raw = "decrease"
                    elif re.search(r"\bincrease\b|\bрост\b|\bувелич\b", blob, flags=re.IGNORECASE):
                        dir_raw = "increase"
                if dir_raw:
                    d = _omni_norm_key(dir_raw)
                    if d in {"decrease", "increase"}:
                        ep["direction"] = d
                        _bump(True)

                base_raw = kv.get("baseline") or kv.get("baseline_visit") or kv.get("baseline_visit_id")
                if base_raw:
                    ep["baseline_visit_id"] = _omni_strip_token(base_raw)
                    _bump(True)

                include_visits_raw = kv.get("include_visits") or kv.get("visits")
                if include_visits_raw:
                    ep["include_visits"] = [str(x) for x in _omni_split_list(include_visits_raw) if x]
                    _bump(bool(ep.get("include_visits")))

                exclude_visits_raw = kv.get("exclude_visits") or kv.get("exclude")
                if exclude_visits_raw:
                    ep["exclude_visits"] = [str(x) for x in _omni_split_list(exclude_visits_raw) if x]
                    _bump(bool(ep.get("exclude_visits")))

                method_raw = kv.get("method") or kv.get("test")
                if method_raw:
                    ep["method"] = _omni_norm_key(method_raw) or _omni_strip_token(method_raw)
                    _bump(True)

                alt_raw = kv.get("alternative")
                if alt_raw:
                    alt = _omni_norm_key(alt_raw)
                    if alt in {"two_sided", "two-sided", "two"}:
                        ep["alternative"] = "two-sided"
                        _bump(True)
                    elif alt in {"less", "left"}:
                        ep["alternative"] = "less"
                        _bump(True)
                    elif alt in {"greater", "right"}:
                        ep["alternative"] = "greater"
                        _bump(True)

                post_raw = kv.get("post_hoc")
                if post_raw:
                    post = _omni_norm_key(post_raw)
                    if post in {"none", "off", "false", "0"}:
                        ep["post_hoc"] = "none"
                        _bump(True)
                    elif post in {"auto", "tukey", "games_howell", "gameshowell", "dunn"}:
                        ep["post_hoc"] = "games_howell" if post == "gameshowell" else post
                        _bump(True)

                phc_raw = kv.get("post_hoc_correction")
                if phc_raw:
                    phc = _omni_norm_key(phc_raw)
                    if phc in {"none", "off", "false", "0"}:
                        ep["post_hoc_correction"] = "none"
                        _bump(True)
                    else:
                        ep["post_hoc_correction"] = phc
                        _bump(True)

                thr_raw = kv.get("responder_threshold") or kv.get("threshold")
                if thr_raw is not None:
                    try:
                        ep["responder_threshold"] = float(thr_raw)
                        _bump(True)
                    except Exception:
                        issues.append(f"Некорректный responder_threshold для {name}: {thr_raw}")

                cols_by_visit = ep.get("columns_by_visit") if isinstance(ep.get("columns_by_visit"), dict) else {}
                visit_map = {k: v for k, v in kv.items() if k and (k.upper().startswith("V") or k.upper() == "BL")}
                if visit_map:
                    any_map_ok = False
                    for vid, col_token in visit_map.items():
                        col = _omni_resolve_column(col_token, colmap)
                        if col:
                            cols_by_visit[str(vid).upper()] = col
                            any_map_ok = True
                        else:
                            issues.append(f"Колонка для {name} {vid} не найдена: {col_token}")
                    ep["columns_by_visit"] = cols_by_visit
                    _bump(any_map_ok)

                continue

        ds["options"] = opts
        ds["time"] = time
        ds["endpoints"] = endpoints
        return {"design_spec": ds, "confidence": confidence, "issues": issues}


class OmniReportPlanner:
    def build_protocol(self, dataset_id: str, design_spec: Dict[str, Any], alpha: float = 0.05) -> Dict[str, Any]:
        ds = design_spec if isinstance(design_spec, dict) else {}
        time = ds.get("time") if isinstance(ds.get("time"), dict) else {}
        visits = time.get("visits") if isinstance(time.get("visits"), list) else []
        baseline_visit_id = time.get("baseline_visit_id") if isinstance(time.get("baseline_visit_id"), str) else None
        subject_col = ds.get("subject_id_column") if isinstance(ds.get("subject_id_column"), str) else None
        group_col = ds.get("group_column") if isinstance(ds.get("group_column"), str) else None

        global_include_visits_raw = ds.get("include_visits") if isinstance(ds.get("include_visits"), list) else []
        global_exclude_visits_raw = ds.get("exclude_visits") if isinstance(ds.get("exclude_visits"), list) else []
        global_include_visits = [_omni_canon_visit_id(x) for x in global_include_visits_raw]
        global_include_visits = [x for x in global_include_visits if isinstance(x, str) and x]
        global_exclude_visits = [_omni_canon_visit_id(x) for x in global_exclude_visits_raw]
        global_exclude_visits = {x for x in global_exclude_visits if isinstance(x, str) and x}
        global_allowed_visits: Optional[set] = set(global_include_visits) if global_include_visits else None

        def _visit_ok(visit_id: Optional[str]) -> bool:
            vid = _omni_canon_visit_id(visit_id)
            if not vid:
                return False
            if global_allowed_visits is not None and vid not in global_allowed_visits:
                return False
            if vid in global_exclude_visits:
                return False
            return True

        opts = ds.get("options") if isinstance(ds.get("options"), dict) else {}

        post_hoc_correction = opts.get("post_hoc_correction")
        if isinstance(post_hoc_correction, str):
            post_hoc_correction = post_hoc_correction.strip() or None
        else:
            post_hoc_correction = None

        def _enabled(name: str, default: bool = True) -> bool:
            v = opts.get(name)
            if v is None:
                return bool(default)
            return bool(v)

        visit_order: Dict[str, int] = {}
        for v in visits:
            if not isinstance(v, dict):
                continue
            vid = v.get("id")
            if not isinstance(vid, str) or not vid:
                continue
            try:
                visit_order[vid] = int(v.get("order") or 0)
            except Exception:
                visit_order[vid] = 0

        steps: List[Dict[str, Any]] = []
        endpoints = ds.get("endpoints") if isinstance(ds.get("endpoints"), list) else []

        primary_endpoint_id: Optional[str] = None
        for ep in endpoints:
            if isinstance(ep, dict) and ep.get("primary") is True and isinstance(ep.get("id"), str) and ep.get("id"):
                primary_endpoint_id = str(ep.get("id"))
                break
        if not primary_endpoint_id:
            for ep in endpoints:
                if isinstance(ep, dict) and isinstance(ep.get("id"), str) and ep.get("id"):
                    primary_endpoint_id = str(ep.get("id"))
                    break

        if _enabled("include_survival", True) and group_col and isinstance(ds.get("survival"), dict):
            survival = ds.get("survival")
            time_col = survival.get("time_column")
            event_col = survival.get("event_column")
            if isinstance(time_col, str) and isinstance(event_col, str) and time_col and event_col:
                steps.append(
                    {
                        "id": "survival__overall",
                        "type": "survival",
                        "time": time_col,
                        "event": event_col,
                        "group": group_col,
                        "task": "survival",
                        "alpha": alpha,
                    }
                )

        if _enabled("include_correlations", True):
            baseline_cols: List[str] = []
            for ep in endpoints:
                if not isinstance(ep, dict):
                    continue
                cols_by_visit = ep.get("columns_by_visit") if isinstance(ep.get("columns_by_visit"), dict) else {}
                base_visit = ep.get("baseline_visit_id") if isinstance(ep.get("baseline_visit_id"), str) else baseline_visit_id
                if base_visit and _visit_ok(base_visit) and base_visit in cols_by_visit:
                    col = cols_by_visit.get(base_visit)
                    if isinstance(col, str) and col:
                        baseline_cols.append(col)
            baseline_cols = list(dict.fromkeys([c for c in baseline_cols if isinstance(c, str) and c]))
            if len(baseline_cols) >= 2:
                steps.append(
                    {
                        "id": "clustered_correlation__baseline",
                        "type": "clustered_correlation",
                        "variables": baseline_cols,
                        "method": "spearman",
                        "show_p_values": True,
                        "alpha": alpha,
                        "task": "correlation",
                        "visit": baseline_visit_id,
                    }
                )

        for ep in endpoints:
            if not isinstance(ep, dict):
                continue
            ep_name = ep.get("name") if isinstance(ep.get("name"), str) else ep.get("id")
            cols_by_visit = ep.get("columns_by_visit") if isinstance(ep.get("columns_by_visit"), dict) else {}
            if not cols_by_visit or not group_col:
                continue

            allowed_visits: Optional[set] = None
            include_visits = ep.get("include_visits") if isinstance(ep.get("include_visits"), list) else []
            include_visits = [_omni_canon_visit_id(v) for v in include_visits]
            include_visits = [v for v in include_visits if isinstance(v, str) and v]
            if include_visits:
                allowed_visits = set(include_visits)
            exclude_visits = ep.get("exclude_visits") if isinstance(ep.get("exclude_visits"), list) else []
            exclude_visits = {_omni_canon_visit_id(v) for v in exclude_visits}
            exclude_visits = {v for v in exclude_visits if isinstance(v, str) and v}

            if global_allowed_visits is not None:
                if allowed_visits is None:
                    allowed_visits = set(global_allowed_visits)
                else:
                    allowed_visits = set(allowed_visits).intersection(global_allowed_visits)
            exclude_visits = set(exclude_visits).union(global_exclude_visits)

            method_override = ep.get("method") if isinstance(ep.get("method"), str) and ep.get("method") else None
            alternative = ep.get("alternative") if isinstance(ep.get("alternative"), str) and ep.get("alternative") else None
            post_hoc = ep.get("post_hoc") if isinstance(ep.get("post_hoc"), str) and ep.get("post_hoc") else None
            ep_post_hoc_correction = ep.get("post_hoc_correction") if isinstance(ep.get("post_hoc_correction"), str) and ep.get("post_hoc_correction") else None
            effective_post_hoc_correction = ep_post_hoc_correction or post_hoc_correction

            if post_hoc is None:
                post_hoc = "auto"
            base_visit = ep.get("baseline_visit_id") if isinstance(ep.get("baseline_visit_id"), str) else baseline_visit_id
            if _enabled("include_baseline_descriptives", True) and base_visit and _visit_ok(base_visit) and base_visit in cols_by_visit:
                steps.append(
                    {
                        "id": f"baseline_desc__{ep.get('id')}",
                        "type": "descriptive_compare",
                        "target": cols_by_visit.get(base_visit),
                        "target_label": f"{ep_name} ({base_visit})",
                        "group": group_col,
                        "task": "baseline",
                        "endpoint": ep.get("id"),
                        "visit": base_visit,
                    }
                )

            for v in visits:
                if not isinstance(v, dict):
                    continue
                vid = v.get("id")
                if not isinstance(vid, str) or vid not in cols_by_visit:
                    continue
                if allowed_visits is not None and vid not in allowed_visits:
                    continue
                if vid in exclude_visits:
                    continue
                if not _visit_ok(vid):
                    continue
                if _enabled("include_between_groups", True):
                    steps.append(
                        {
                            "id": f"between_groups__{ep.get('id')}__{vid}",
                            "type": "compare",
                            "target": cols_by_visit.get(vid),
                            "target_label": f"{ep_name} ({vid})",
                            "group": group_col,
                            "task": "between_groups",
                            "endpoint": ep.get("id"),
                            "visit": vid,
                            "alpha": alpha,
                            "post_hoc": post_hoc,
                            "post_hoc_correction": effective_post_hoc_correction,
                            "alternative": alternative,
                            "method": method_override,
                        }
                    )

                if _enabled("include_change_from_baseline", True) and base_visit and _visit_ok(base_visit) and base_visit in cols_by_visit and vid != base_visit:
                    base_col = cols_by_visit.get(base_visit)
                    follow_col = cols_by_visit.get(vid)
                    direction = ep.get("direction") if isinstance(ep.get("direction"), str) else None
                    if direction not in {"decrease", "increase"}:
                        direction = None
                    if isinstance(base_col, str) and isinstance(follow_col, str) and base_col and follow_col:
                        steps.append(
                            {
                                "id": f"change_from_baseline__{ep.get('id')}__{vid}",
                                "type": "compare",
                                "baseline_column": base_col,
                                "followup_column": follow_col,
                                "target_label": f"{ep_name} Δ({base_visit}→{vid})",
                                "group": group_col,
                                "task": "change_from_baseline_between_groups",
                                "endpoint": ep.get("id"),
                                "visit": vid,
                                "baseline_visit": base_visit,
                                "direction": direction,
                                "alpha": alpha,
                                "post_hoc": post_hoc,
                                "post_hoc_correction": effective_post_hoc_correction,
                                "alternative": alternative,
                                "method": method_override,
                            }
                        )

            if subject_col and group_col:
                ordered_visits = [v.get("id") for v in visits if isinstance(v, dict) and isinstance(v.get("id"), str) and v.get("id") in cols_by_visit]
                if allowed_visits is not None:
                    ordered_visits = [vid for vid in ordered_visits if vid in allowed_visits]
                if exclude_visits:
                    ordered_visits = [vid for vid in ordered_visits if vid not in exclude_visits]
                ordered_visits = [vid for vid in ordered_visits if _visit_ok(vid)]
                outcome_columns = [cols_by_visit[v] for v in ordered_visits]
                time_labels = ordered_visits
                if _enabled("include_longitudinal_model", True) and len(outcome_columns) >= 3:
                    steps.append(
                        {
                            "id": f"mixed_effects__{ep.get('id')}",
                            "type": "mixed_effects",
                            "outcome": ep_name,
                            "outcome_label": ep_name,
                            "time_column": "Visit",
                            "group_column": group_col,
                            "subject_column": subject_col,
                            "outcome_columns": outcome_columns,
                            "time_labels": time_labels,
                            "random_slopes": False,
                            "alpha": alpha,
                            "task": "longitudinal",
                            "endpoint": ep.get("id"),
                        }
                    )

                if _enabled("include_responders", True) and len(outcome_columns) >= 2:
                    direction = ep.get("direction") if isinstance(ep.get("direction"), str) else None
                    if direction not in {"decrease", "increase"}:
                        direction = "decrease"
                    thr_raw = ep.get("responder_threshold")
                    try:
                        threshold = float(thr_raw) if thr_raw is not None else 0.0
                    except Exception:
                        threshold = 0.0
                    steps.append(
                        {
                            "id": f"responders__{ep.get('id')}",
                            "type": "responders",
                            "outcome_label": ep_name,
                            "group_column": group_col,
                            "subject_column": subject_col,
                            "outcome_columns": outcome_columns,
                            "time_labels": time_labels,
                            "baseline_label": base_visit or (time_labels[0] if time_labels else None),
                            "threshold": threshold,
                            "direction": direction,
                            "alpha": alpha,
                            "task": "responders",
                            "endpoint": ep.get("id"),
                        }
                    )

                if (
                    _enabled("include_regression", True)
                    and primary_endpoint_id
                    and str(ep.get("id")) == primary_endpoint_id
                    and base_visit
                    and _visit_ok(base_visit)
                    and base_visit in cols_by_visit
                    and len(outcome_columns) >= 2
                ):
                    base_col = cols_by_visit.get(base_visit)
                    candidates = [v for v in ordered_visits if isinstance(v, str) and v in cols_by_visit]
                    candidates = sorted(candidates, key=lambda x: (visit_order.get(str(x), 0), str(x)))
                    last_visit = candidates[-1] if candidates else None
                    last_col = cols_by_visit.get(last_visit) if last_visit else None
                    covariates = ds.get("covariates") if isinstance(ds.get("covariates"), list) else []
                    covariates = [str(c) for c in covariates if isinstance(c, str) and c]
                    predictors = [group_col]
                    if isinstance(base_col, str) and base_col:
                        predictors.append(base_col)
                    predictors.extend(covariates)

                    if isinstance(last_col, str) and last_col and isinstance(predictors, list) and predictors:
                        steps.append(
                            {
                                "id": f"regression__{ep.get('id')}__{last_visit}",
                                "type": "regression",
                                "kind": "linear",
                                "target": last_col,
                                "predictors": predictors,
                                "task": "regression_adjusted",
                                "endpoint": ep.get("id"),
                                "visit": last_visit,
                                "baseline_visit": base_visit,
                                "alpha": alpha,
                            }
                        )

        protocol: Dict[str, Any] = {
            "name": "OmniReport",
            "goal": "omnireport",
            "dataset_id": dataset_id,
            "alpha": alpha,
            "design_spec": ds,
            "steps": steps,
        }
        return protocol

class StudyDesignEngine:
    """
    Expert System that translates high-level 'Study Goals' into executable 'Analysis Protocols'.
    Acts as the 'Methodologist' role.
    """

    def suggest_protocol(self, goal: str, variables: Dict[str, Any], metadata: Dict[str, Any], template_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Main entry point.
        goal: 'compare_groups', 'relationship', 'survival', 'prediction'
        variables: { 'target': 'Hb', 'group': 'Treatment', 'time': 'Month' }
        metadata: { 'Hb': { 'is_normal': False, 'type': 'numeric' } }
        
        Returns: A fully-formed Protocol JSON ready for the Engine.
        """
        steps = []
        name = "Generated Study"
        
        if goal == "compare_groups":
            target = variables.get("target")
            group = variables.get("group")
            time_col = variables.get("time") # Optional for dynamic
            
            if time_col:
                # DYNAMIC (Repeated Measures)
                name = f"Dynamic Analysis of {target} by {group}"
                steps = self._design_dynamic_comparison(target, group, time_col, metadata)
            else:
                # STATIC (Cross-sectional)
                name = f"Comparison of {target} by {group}"
                steps = self._design_static_comparison(target, group, metadata)

            if template_id == "compare_quick":
                steps = [s for s in steps if s.get("id") != "desc_stats"]

        elif goal == "relationship":
            target = variables.get("target")
            predictor = variables.get("predictor")
            name = f"Correlation: {target} vs {predictor}"
            steps = self._design_correlation(target, predictor, metadata)

        return {
            "name": name,
            "goal": goal,
            "steps": steps,
            "required_visualization": "dashboard_v1"
        }

    def _design_static_comparison(self, target: str, group: str, meta: Dict) -> List[Dict]:
        """
        Logic for T-Test / ANOVA / Non-parametric equivalents.
        """
        steps = []
        
        # 1. Descriptive Stats (Table 1 equivalent)
        steps.append({
            "id": "desc_stats",
            "type": "descriptive_compare",
            "target": target,
            "group": group
        })
        
        # 2. Hypothesis Testing
        # Check normalization from metadata to suggest method
        target_meta = meta.get(target, {})
        is_normal = target_meta.get("normality", {}).get("is_normal", True) # Default to True if unknown
        
        # Note: We can force a method, or let engine.select_test decide dynamically.
        # "Methodological Brain" prefers to be explicit here if possible, but engine.py has good runtime logic.
        # Let's rely on engine.py's robust 'compare' dispatch for now, but generic 'compare' is enough.
        
        method_category = "parametric" if is_normal else "non_parametric"
        
        steps.append({
            "id": "hypothesis_test",
            "type": "compare",
            "target": target,
            "group": group,
            "assumptions_checked": ["normality", "homogeneity"],
            "method": {
                "id": "auto",
                "name": "Auto-Detect Test",
                "category": method_category,
                "params": {"target": target, "group": group}
            }
        })
        
        return steps

    def _design_dynamic_comparison(self, target: str, group: str, time_col: str, meta: Dict) -> List[Dict]:
        """
        Logic for Longitudinal Analysis (Repeated Measures).
        """
        steps = []
        
        # 1. Overall Trend (All Groups) - e.g. RM ANOVA or Friedmann
        steps.append({
            "id": "time_trend_overall",
            "type": "compare_dynamic", # New capability needed in Engine
            "target": target,
            "time": time_col,
            "group": group
        })
        
        # 2. Post-hoc: Compare groups at EACH timepoint
        # We generate a sub-step for the Engine to expand, or hardcode generic instruction
        steps.append({
             "id": "timepoint_comparison",
             "type": "batch_compare_by_factor", # "Loop over Time"
             "target": target,
             "group": group,
             "split_by": time_col
        })
        
        return steps

    def _design_correlation(self, target: str, predictor: str, meta: Dict) -> List[Dict]:
        return [{
            "id": "corr_analysis",
            "type": "correlation",
            "target": target,
            "group": predictor
        }]

    def list_templates(self, goal: Optional[str] = None) -> List[Dict[str, str]]:
        templates = [
            {
                "id": "compare_full",
                "goal": "compare_groups",
                "name": "Full comparison",
                "description": "Descriptives + hypothesis test (auto)",
            },
            {
                "id": "compare_quick",
                "goal": "compare_groups",
                "name": "Quick comparison",
                "description": "Only hypothesis test (auto)",
            },
            {
                "id": "correlation_auto",
                "goal": "relationship",
                "name": "Correlation (auto)",
                "description": "Auto-select Pearson/Spearman",
            },
        ]

        if goal:
            return [t for t in templates if t.get("goal") == goal]
        return templates
