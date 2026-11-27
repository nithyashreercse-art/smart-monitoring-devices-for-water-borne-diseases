"""Random Forest risk classifier (Low / Medium / High) built with scikit-learn.

The labelled training set is SIMULATED: it is generated from three hidden
"outbreak states" with overlapping feature distributions plus 5 % label noise,
so that the evaluation numbers are realistic rather than a perfect 100 %.
Replace `generate_training_data()` with real labelled records when available.
"""
import json
import os
from datetime import datetime

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (accuracy_score, confusion_matrix,
                             precision_recall_fscore_support)
from sklearn.model_selection import cross_val_score, train_test_split

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "models")
MODEL_PATH = os.path.join(MODEL_DIR, "risk_rf.joblib")
METRICS_PATH = os.path.join(MODEL_DIR, "metrics.json")

FEATURES = ["cases_per_1000", "case_trend", "deaths_7d", "ecoli_max",
            "turbidity_mean", "chlorine_min", "ph_dev", "rain_7d", "rain_3d", "type_code"]
FEATURE_LABELS = {
    "cases_per_1000": "Cases per 1000 people (7 d)",
    "case_trend": "Case trend (last 3 d vs previous 4 d)",
    "deaths_7d": "Deaths (7 d)",
    "ecoli_max": "E. coli (max, CFU/100 mL)",
    "turbidity_mean": "Turbidity (mean, NTU)",
    "chlorine_min": "Residual chlorine (min, mg/L)",
    "ph_dev": "pH deviation from 6.5-8.5",
    "rain_7d": "Rainfall (7 d, mm)",
    "rain_3d": "Rainfall (3 d, mm)",
    "type_code": "Community type (rural/semi-urban/urban)",
}
LABELS = ["Low", "Medium", "High"]

_model = None


def generate_training_data(n=4000, seed=42):
    rng = np.random.default_rng(seed)
    state = rng.choice(3, size=n, p=[0.55, 0.28, 0.17])
    X = np.zeros((n, len(FEATURES)))
    for i, s in enumerate(state):
        t = rng.choice(3, p=[0.4, 0.35, 0.25])
        if s == 0:      # Low
            cases = rng.exponential(0.15)
            trend = rng.lognormal(0.0, 0.4)
            deaths = 0 if rng.random() < 0.99 else 1
            ecoli = 0 if rng.random() < 0.70 else rng.poisson(3)
            turb = max(0.2, rng.normal(2.5, 1.6))
            chl = max(0.0, rng.normal(0.45, 0.16))
            phdev = 0.0 if rng.random() < 0.9 else abs(rng.normal(0, 0.4))
            rain7 = rng.exponential(28)
        elif s == 1:    # Medium
            cases = rng.exponential(0.8) + 0.25
            trend = rng.lognormal(0.3, 0.45)
            deaths = 0 if rng.random() < 0.93 else 1
            ecoli = 0 if rng.random() < 0.25 else rng.poisson(14)
            turb = max(0.2, rng.normal(5.2, 2.2))
            chl = max(0.0, rng.normal(0.24, 0.12))
            phdev = 0.0 if rng.random() < 0.8 else abs(rng.normal(0, 0.5))
            rain7 = rng.exponential(65)
        else:           # High
            cases = rng.exponential(2.4) + 1.2
            trend = rng.lognormal(0.65, 0.5)
            deaths = rng.poisson(0.7)
            ecoli = rng.poisson(70) if rng.random() < 0.9 else 0
            turb = max(0.2, rng.normal(9.0, 3.5))
            chl = max(0.0, rng.normal(0.10, 0.08))
            phdev = 0.0 if rng.random() < 0.7 else abs(rng.normal(0, 0.7))
            rain7 = rng.exponential(110)
        rain3 = rain7 * rng.uniform(0.0, 0.85)
        X[i] = [cases, min(trend, 8.0), deaths, ecoli, turb, chl, phdev, rain7, rain3, t]
    y = state.copy()
    flip = rng.random(n) < 0.05                      # 5 % label noise
    shift = rng.choice([-1, 1], size=n)
    y[flip] = np.clip(y[flip] + shift[flip], 0, 2)
    return X, y


def train(save=True):
    global _model
    X, y = generate_training_data()
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25, stratify=y, random_state=42)
    clf = RandomForestClassifier(n_estimators=200, max_depth=10, min_samples_leaf=3,
                                 class_weight="balanced", random_state=42, n_jobs=-1)
    clf.fit(Xtr, ytr)
    pred = clf.predict(Xte)
    prec, rec, f1, sup = precision_recall_fscore_support(yte, pred, labels=[0, 1, 2], zero_division=0)
    macro = precision_recall_fscore_support(yte, pred, average="macro", zero_division=0)
    cv = cross_val_score(RandomForestClassifier(n_estimators=100, max_depth=10, min_samples_leaf=3,
                                                class_weight="balanced", random_state=1, n_jobs=-1),
                         X, y, cv=5)
    metrics = {
        "accuracy": round(float(accuracy_score(yte, pred)), 4),
        "precision_macro": round(float(macro[0]), 4),
        "recall_macro": round(float(macro[1]), 4),
        "f1_macro": round(float(macro[2]), 4),
        "cv_accuracy_mean": round(float(cv.mean()), 4),
        "cv_accuracy_std": round(float(cv.std()), 4),
        "per_class": [{"label": LABELS[i], "precision": round(float(prec[i]), 4),
                       "recall": round(float(rec[i]), 4), "f1": round(float(f1[i]), 4),
                       "support": int(sup[i])} for i in range(3)],
        "confusion_matrix": confusion_matrix(yte, pred, labels=[0, 1, 2]).tolist(),
        "feature_importance": sorted(
            [{"feature": f, "label": FEATURE_LABELS[f], "importance": round(float(v), 4)}
             for f, v in zip(FEATURES, clf.feature_importances_)],
            key=lambda d: -d["importance"]),
        "n_train": int(len(ytr)), "n_test": int(len(yte)),
        "trained_at": datetime.now().isoformat(timespec="seconds"),
        "note": "Evaluated on SIMULATED labelled data (random 75/25 split). "
                "Real-world performance must be validated with real surveillance data.",
    }
    if save:
        os.makedirs(MODEL_DIR, exist_ok=True)
        joblib.dump(clf, MODEL_PATH)
        with open(METRICS_PATH, "w") as fh:
            json.dump(metrics, fh, indent=2)
    _model = clf
    return clf, metrics


def get_model():
    global _model
    if _model is None:
        if os.path.exists(MODEL_PATH):
            try:
                _model = joblib.load(MODEL_PATH)
            except Exception:           # e.g. different scikit-learn version -> retrain
                train()
        else:
            train()
    return _model


def get_metrics():
    if not os.path.exists(METRICS_PATH):
        train()
    with open(METRICS_PATH) as fh:
        return json.load(fh)


def predict(feat):
    """feat: dict with the FEATURES keys -> (level, {'Low':p,'Medium':p,'High':p})."""
    clf = get_model()
    x = np.array([[float(feat[f]) for f in FEATURES]])
    proba = clf.predict_proba(x)[0]
    probs = {LABELS[int(c)]: float(p) for c, p in zip(clf.classes_, proba)}
    for l in LABELS:
        probs.setdefault(l, 0.0)
    level = max(probs, key=probs.get)
    return level, probs


if __name__ == "__main__":
    _, m = train()
    print(json.dumps({k: m[k] for k in ("accuracy", "precision_macro", "recall_macro", "f1_macro")}, indent=2))
