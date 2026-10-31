"""Reproducible synthetic placement estimator.

This is NOT a validated real-world placement probability. It is a logistic
regression trained on synthetic campus-style records generated from a known
scoring process so estimates are inspectable and reproducible.

Implemented in NumPy so the demo runs on Python 3.14 without scikit-learn wheels.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

FEATURE_ORDER = [
    "aptitude_score",
    "english_score",
    "technical_score",
    "mock_interviews",
    "mock_interview_avg",
    "attendance_pct",
    "applications_count",
    "internships",
    "cgpa",
    "projects_count",
    "certifications_count",
]

FEATURE_LABELS = {
    "aptitude_score": "Aptitude score",
    "english_score": "English score",
    "technical_score": "Technical score",
    "mock_interviews": "Mock interviews completed",
    "mock_interview_avg": "Mock interview average",
    "attendance_pct": "Class attendance",
    "applications_count": "Job applications",
    "internships": "Internships",
    "cgpa": "CGPA",
    "projects_count": "Projects",
    "certifications_count": "Certifications",
}

LIMITATIONS = (
    "Estimate only. This model is trained on reproducible synthetic campus records, "
    "not on verified placement outcomes from a real college. It cannot account for "
    "company-specific hiring bars, market cycles, referral networks, or identity. "
    "Treat the number as a coaching signal, not a guaranteed offer probability."
)

MODEL_PATH = Path(__file__).resolve().parent.parent / "artifacts" / "placement_model.npz"
RNG_SEED = 42

TRUE_WEIGHTS = np.array(
    [0.028, 0.016, 0.034, 0.18, 0.022, 0.014, 0.045, 0.42, 0.55, 0.11, 0.08],
    dtype=float,
)
# Calibrated so mean synthetic students sit near 50% placed (not ~97%).
TRUE_INTERCEPT = -12.45


@dataclass
class PredictionResult:
    probability: float
    band: str
    factors: list[dict]
    limitations: str
    model_version: str
    is_estimate: bool = True


def _clip_features(values: dict) -> dict:
    return {
        "aptitude_score": float(np.clip(values.get("aptitude_score", 0), 0, 100)),
        "english_score": float(np.clip(values.get("english_score", 0), 0, 100)),
        "technical_score": float(np.clip(values.get("technical_score", 0), 0, 100)),
        "mock_interviews": int(np.clip(values.get("mock_interviews", 0), 0, 30)),
        "mock_interview_avg": float(np.clip(values.get("mock_interview_avg", 0), 0, 100)),
        "attendance_pct": float(np.clip(values.get("attendance_pct", 0), 0, 100)),
        "applications_count": int(np.clip(values.get("applications_count", 0), 0, 80)),
        "internships": int(np.clip(values.get("internships", 0), 0, 6)),
        "cgpa": float(np.clip(values.get("cgpa", 0), 0, 10)),
        "projects_count": int(np.clip(values.get("projects_count", 0), 0, 20)),
        "certifications_count": int(np.clip(values.get("certifications_count", 0), 0, 20)),
    }


def vectorize(values: dict) -> np.ndarray:
    clipped = _clip_features(values)
    return np.array([[clipped[name] for name in FEATURE_ORDER]], dtype=float)


def generative_logit(X: np.ndarray) -> np.ndarray:
    return TRUE_INTERCEPT + X @ TRUE_WEIGHTS


def generate_synthetic_dataset(n: int = 2400, seed: int = RNG_SEED) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    aptitude = rng.normal(62, 16, n).clip(18, 98)
    english = rng.normal(64, 14, n).clip(20, 98)
    technical = rng.normal(58, 18, n).clip(12, 98)
    mocks = rng.poisson(2.2, n).clip(0, 18)
    mock_avg = rng.normal(55, 15, n).clip(20, 95)
    attendance = rng.normal(78, 12, n).clip(35, 100)
    applications = rng.poisson(6, n).clip(0, 40)
    internships = rng.poisson(0.7, n).clip(0, 4)
    cgpa = rng.normal(7.4, 0.9, n).clip(5.0, 9.8)
    projects = rng.poisson(2.4, n).clip(0, 10)
    certs = rng.poisson(1.5, n).clip(0, 8)

    X = np.column_stack(
        [
            aptitude,
            english,
            technical,
            mocks,
            mock_avg,
            attendance,
            applications,
            internships,
            cgpa,
            projects,
            certs,
        ]
    )
    logits = generative_logit(X)
    probs = 1 / (1 + np.exp(-logits))
    y = rng.binomial(1, probs)
    return X, y.astype(int)


def _sigmoid(z: np.ndarray) -> np.ndarray:
    z = np.clip(z, -30, 30)
    return 1 / (1 + np.exp(-z))


def _standardize(X: np.ndarray, mean: np.ndarray | None = None, std: np.ndarray | None = None):
    if mean is None:
        mean = X.mean(axis=0)
        std = X.std(axis=0)
        std = np.where(std < 1e-8, 1.0, std)
    return (X - mean) / std, mean, std


def _fit_logreg(X: np.ndarray, y: np.ndarray, steps: int = 20):
    """IRLS logistic regression with intercept."""
    n, d = X.shape
    y = y.astype(float)
    Xb = np.column_stack([np.ones(n), X])
    beta = np.zeros(d + 1)
    for _ in range(steps):
        z = Xb @ beta
        p = _sigmoid(z)
        p = np.clip(p, 1e-6, 1 - 1e-6)
        w = p * (1 - p)
        z_adj = z + (y - p) / w
        xtw = Xb.T * w
        hess = xtw @ Xb + 1e-5 * np.eye(d + 1)
        beta = np.linalg.solve(hess, xtw @ z_adj)
    return beta[1:], float(beta[0])


def _split(X, y, test_size=0.25, seed=RNG_SEED):
    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(y))
    n_test = int(len(y) * test_size)
    test_idx, train_idx = idx[:n_test], idx[n_test:]
    return X[train_idx], X[test_idx], y[train_idx], y[test_idx]


def _metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    y_true = y_true.astype(int)
    y_pred = y_pred.astype(int)
    tp = int(np.sum((y_true == 1) & (y_pred == 1)))
    fp = int(np.sum((y_true == 0) & (y_pred == 1)))
    fn = int(np.sum((y_true == 1) & (y_pred == 0)))
    tn = int(np.sum((y_true == 0) & (y_pred == 0)))
    acc = (tp + tn) / max(len(y_true), 1)
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-9)
    return {
        "accuracy": float(acc),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
    }


def train_and_persist() -> dict:
    X, y = generate_synthetic_dataset()
    X_train, X_test, y_train, y_test = _split(X, y)
    Xs_train, mean, std = _standardize(X_train)
    Xs_test, _, _ = _standardize(X_test, mean, std)
    w, b = _fit_logreg(Xs_train, y_train)
    proba = _sigmoid(Xs_test @ w + b)
    y_pred = (proba >= 0.5).astype(int)
    metrics = _metrics(y_test, y_pred)
    metrics.update(
        {
            "n_train": int(len(X_train)),
            "n_test": int(len(X_test)),
            "positive_rate_test": float(y_test.mean()),
            "seed": RNG_SEED,
            "note": "Held-out metrics on synthetic labels only. Not real placement accuracy.",
        }
    )
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        MODEL_PATH,
        weights=w,
        intercept=np.array([b]),
        mean=mean,
        std=std,
        metrics_json=np.array([str(metrics)]),
    )
    # store metrics alongside for easy load
    (MODEL_PATH.parent / "metrics.json").write_text(__import__("json").dumps(metrics, indent=2), encoding="utf-8")
    return metrics


def load_bundle() -> dict:
    import json

    if not MODEL_PATH.exists():
        train_and_persist()
    data = np.load(MODEL_PATH, allow_pickle=False)
    metrics_path = MODEL_PATH.parent / "metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.exists() else {}
    return {
        "weights": data["weights"],
        "intercept": float(data["intercept"][0]),
        "mean": data["mean"],
        "std": data["std"],
        "metrics": metrics,
    }


def probability_band(p: float) -> str:
    if p < 0.35:
        return "Needs focused prep"
    if p < 0.55:
        return "Developing"
    if p < 0.75:
        return "Competitive"
    return "Offer-ready trajectory"


def _proba(bundle: dict, X: np.ndarray) -> np.ndarray:
    Xs = (X - bundle["mean"]) / bundle["std"]
    return _sigmoid(Xs @ bundle["weights"] + bundle["intercept"])


def predict_classes(bundle: dict, X: np.ndarray) -> np.ndarray:
    return (_proba(bundle, X) >= 0.5).astype(int)


def explain(values: dict, bundle: dict) -> list[dict]:
    x = vectorize(values)[0]
    x_std = (x - bundle["mean"]) / bundle["std"]
    contrib = bundle["weights"] * x_std
    ranked = sorted(zip(FEATURE_ORDER, contrib, x), key=lambda t: abs(t[1]), reverse=True)
    factors = []
    for name, c, raw in ranked:
        direction = "helps" if c > 0 else "holds back"
        factors.append(
            {
                "feature": name,
                "label": FEATURE_LABELS[name],
                "value": round(float(raw), 2),
                "contribution": round(float(c), 3),
                "direction": direction,
                "why": (
                    f"{FEATURE_LABELS[name]} of {raw:.1f} {direction} the estimate "
                    f"(log-odds contribution {c:+.3f})."
                ),
            }
        )
    return factors


def predict_from_features(values: dict) -> PredictionResult:
    bundle = load_bundle()
    x = vectorize(values)
    proba = float(_proba(bundle, x)[0])
    return PredictionResult(
        probability=round(proba, 4),
        band=probability_band(proba),
        factors=explain(values, bundle),
        limitations=LIMITATIONS,
        model_version="synthetic-logit-v1",
        is_estimate=True,
    )


def student_to_features(student) -> dict:
    return {name: getattr(student, name) for name in FEATURE_ORDER}
