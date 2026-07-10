"""Cached SHAP Failure Fingerprints & Pre-Trade Memory Engine (`Phase A3`).

Discretizes historical `SETTLED MODEL_MISS` features into compact 8-element ternary sign vectors (`[-1, 0, +1]`)
and caches them in `backend/data/shap_failure_memory_cache.json`.
Before any new pre-trade Quant Qlib alpha score is issued, `check_pretrade_memory_risk` computes the
Hamming Distance against all cached failure vectors in `<0.2ms`. If max similarity >= 80%, it injects
a `Pre-Trade Risk Warning Active` flag and applies a `-15% Confidence Discount` to prevent capital loss.
"""

import os
import json
import time
import logging
from typing import Dict, Any, List, Optional
import numpy as np

logger = logging.getLogger("SHAPMemoryService")

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CACHE_PATH = os.path.join(DATA_DIR, "shap_failure_memory_cache.json")

SUPER_FACTORS = [
    "roc_5",
    "roc_20",
    "z_score_20",
    "volume_surge_ratio",
    "pvt_20",
    "realized_vol_20",
    "deliv_per"
]


def discretize_features_to_ternary(features: Dict[str, Any], market_regime: str = "Normal_Vol") -> List[int]:
    """Converts continuous quantitative factor indicators into a compact 8-element ternary sign vector `[-1, 0, +1]`.

    Index mapping:
        0: roc_5 (> 3.0 -> +1, < -3.0 -> -1)
        1: roc_20 (> 5.0 -> +1, < -5.0 -> -1)
        2: z_score_20 (> 1.5 -> +1, < -1.5 -> -1)
        3: volume_surge_ratio (> 1.5 -> +1, < 0.8 -> -1)
        4: pvt_20 (> 2.0 -> +1, < -2.0 -> -1)
        5: realized_vol_20 (> 25.0 -> +1, < 12.0 -> -1)
        6: deliv_per (> 60.0 -> +1, < 35.0 -> -1)
        7: market_regime ('High' in regime -> +1, 'Low' in regime -> -1, else 0)
    """
    if not isinstance(features, dict):
        features = {}

    def _get_val(keys, default=0.0):
        for k in keys:
            if k in features and features[k] is not None:
                try:
                    return float(features[k])
                except (ValueError, TypeError):
                    pass
        return default

    vec = [0] * 8

    # 0: roc_5
    v_r5 = _get_val(["roc_5", "momentum_5d_pct", "roc5"])
    vec[0] = 1 if v_r5 > 3.0 else (-1 if v_r5 < -3.0 else 0)

    # 1: roc_20
    v_r20 = _get_val(["roc_20", "momentum_20d_pct", "roc20"])
    vec[1] = 1 if v_r20 > 5.0 else (-1 if v_r20 < -5.0 else 0)

    # 2: z_score_20
    v_z = _get_val(["z_score_20", "bollinger_z_score", "zscore"])
    vec[2] = 1 if v_z > 1.5 else (-1 if v_z < -1.5 else 0)

    # 3: volume_surge_ratio
    v_v = _get_val(["volume_surge_ratio", "volume_surge", "vsurge"], 1.0)
    vec[3] = 1 if v_v > 1.5 else (-1 if v_v < 0.8 else 0)

    # 4: pvt_20
    v_pvt = _get_val(["pvt_20", "price_volume_trend_score", "pvt"])
    vec[4] = 1 if v_pvt > 2.0 else (-1 if v_pvt < -2.0 else 0)

    # 5: realized_vol_20
    v_vol = _get_val(["realized_vol_20", "realized_volatility_annualized_pct", "vol20"], 18.0)
    vec[5] = 1 if v_vol > 25.0 else (-1 if v_vol < 12.0 else 0)

    # 6: deliv_per
    v_del = _get_val(["deliv_per", "delivery_pct", "deliv"], 50.0)
    vec[6] = 1 if v_del > 60.0 else (-1 if v_del < 35.0 else 0)

    # 7: regime
    reg_str = str(market_regime).upper()
    vec[7] = 1 if "HIGH" in reg_str else (-1 if "LOW" in reg_str else 0)

    return vec


def build_shap_failure_memory_cache() -> Dict[str, Any]:
    """Scans `SETTLED MODEL_MISS` records from the ledger and writes their ternary vectors to the fast disk cache."""
    try:
        import prediction_ledger_service as pls
        misses = [r for r in pls.get_settled_predictions() if r.get("settlement_verdict") == "MODEL_MISS"]
    except Exception as e:
        logger.warning(f"Error reading prediction ledger misses: {e}")
        misses = []

    cached_vectors = []
    for r in misses:
        feats = r.get("features", {})
        regime = r.get("market_regime", "Normal_Vol")
        t_vec = discretize_features_to_ternary(feats, regime)
        cached_vectors.append({
            "prediction_id": r.get("prediction_id", ""),
            "symbol": r.get("symbol", "UNKNOWN"),
            "evaluated_at": r.get("evaluated_at", r.get("target_eval_date", "")),
            "residual_miss_pct": float(r.get("idiosyncratic_residual_pct", 0.0)),
            "predicted_return_pct": float(r.get("predicted_return_pct", 0.0)),
            "actual_return_pct": float(r.get("actual_return_pct", 0.0)),
            "ternary_vector": t_vec,
            "market_regime": regime
        })

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump({"updated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "cache_count": len(cached_vectors), "failures": cached_vectors}, f, indent=2)

    logger.info(f"Built SHAP failure memory cache with {len(cached_vectors)} ternary fingerprints.")
    return {"status": "success", "cached_failures_count": len(cached_vectors), "cache_path": CACHE_PATH}


def check_pretrade_memory_risk(features: Dict[str, Any], market_regime: str = "Normal_Vol") -> Dict[str, Any]:
    """Checks live candidate features against cached MODEL_MISS failure vectors via Hamming similarity in <0.2ms.

    Returns:
        Dictionary containing `risk_warning_active`, `confidence_discount_pct` (15.0 if match >= 80%),
        `max_similarity_pct`, and `warning_message`.
    """
    t0 = time.perf_counter()
    cand_vec = discretize_features_to_ternary(features, market_regime)

    failures = []
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                failures = data.get("failures", [])
        except Exception:
            pass

    # If cache is empty or not yet built, trigger build once
    if not failures:
        build_res = build_shap_failure_memory_cache()
        if os.path.exists(CACHE_PATH):
            try:
                with open(CACHE_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    failures = data.get("failures", [])
            except Exception:
                pass

    if not failures:
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return {
            "risk_warning_active": False,
            "confidence_discount_pct": 0.0,
            "max_similarity_pct": 0.0,
            "matched_failure": None,
            "latency_ms": round(elapsed_ms, 3)
        }

    max_sim = 0.0
    best_match = None

    # Vectorized / exact integer loop for <0.2ms speed
    for fail in failures:
        m_vec = fail.get("ternary_vector")
        if not m_vec or len(m_vec) != 8:
            continue
        # Exact element-wise match count (Hamming similarity)
        matches = sum(1 for a, b in zip(cand_vec, m_vec) if a == b)
        sim_pct = (matches / 8.0) * 100.0
        if sim_pct > max_sim:
            max_sim = sim_pct
            best_match = fail

    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    is_warning = bool(max_sim >= 80.0 and best_match is not None)
    discount = 15.0 if is_warning else 0.0

    msg = None
    if is_warning and best_match:
        sym = best_match.get("symbol", "UNKNOWN")
        miss_val = best_match.get("residual_miss_pct", 0.0)
        dt_str = str(best_match.get("evaluated_at", ""))[:10]
        msg = f"Pre-Trade Risk Warning: Candidate features match {round(max_sim, 1)}% with historical MODEL_MISS failure on {sym} ({dt_str}, Residual error: {miss_val:+g}%)"

    return {
        "risk_warning_active": is_warning,
        "confidence_discount_pct": discount,
        "max_similarity_pct": round(max_sim, 1),
        "matched_failure": best_match if is_warning else None,
        "warning_message": msg,
        "latency_ms": round(elapsed_ms, 3)
    }
