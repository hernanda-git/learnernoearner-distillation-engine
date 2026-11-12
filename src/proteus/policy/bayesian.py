"""Phase 3: Fitted Bayesian Log-Odds Cognitive Policy (`proteus.policy.bayesian`).

Trains an inverse-decision log-odds classifier across the 97 canonical setups and
5,000 negative-space abstention bars (N = 5,097), learning empirical feature weights
for P(ABSTAIN | x), P(ENTER_LONG | x), and P(ENTER_SHORT | x).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from proteus.market.lakehouse import FeatureVector

CLASSES: tuple[str, ...] = ("ABSTAIN", "ENTER_LONG", "ENTER_SHORT")


@dataclass(frozen=True)
class PolicyEvaluationMetrics:
    total_bars: int
    positive_signals: int
    negative_bars: int
    abstention_accuracy: float
    setup_recall: float
    directional_concordance: float
    learned_class_priors: dict[str, float]


@dataclass(frozen=True)
class TimeSplitEvaluation:
    cutoff_utc: str
    train_bars: int
    test_bars: int
    test_positives: int
    test_negatives: int
    abstention_accuracy: float
    setup_recall: float
    directional_concordance: float
    predicted_entries: int
    false_entries: int
    status: str = "MEASURED"


class BayesianCognitivePolicy:
    """Gaussian Naive Bayes / Log-Odds policy classifier fitted on the 5,097-bar lakehouse."""

    def __init__(self, variance_floor: float = 0.04) -> None:
        self.variance_floor = variance_floor
        self._priors: dict[str, float] = {}
        self._means: dict[str, list[float]] = {}
        self._vars: dict[str, list[float]] = {}
        self._fitted = False

    def fit(self, dataset: Sequence[FeatureVector]) -> BayesianCognitivePolicy:
        if not dataset:
            raise ValueError("dataset must not be empty")

        by_class: dict[str, list[tuple[float, ...]]] = {c: [] for c in CLASSES}
        for row in dataset:
            by_class[row.label].append(row.to_numeric_tuple())

        total = float(len(dataset))
        dim = len(dataset[0].to_numeric_tuple())

        for cls_name in CLASSES:
            rows = by_class[cls_name]
            n_cls = len(rows)
            if n_cls == 0:
                self._priors[cls_name] = 1e-6
                self._means[cls_name] = [0.0] * dim
                self._vars[cls_name] = [1.0] * dim
                continue

            self._priors[cls_name] = round(n_cls / total, 6)
            means = [sum(r[d] for r in rows) / n_cls for d in range(dim)]
            variances = [
                max(
                    self.variance_floor,
                    sum((r[d] - means[d]) ** 2 for r in rows) / max(1, n_cls - 1),
                )
                for d in range(dim)
            ]
            self._means[cls_name] = means
            self._vars[cls_name] = variances

        self._fitted = True
        return self

    def predict_proba(self, vec: FeatureVector) -> dict[str, float]:
        if not self._fitted:
            raise RuntimeError("BayesianCognitivePolicy must be fitted before calling predict_proba")

        x = vec.to_numeric_tuple()
        log_scores: dict[str, float] = {}

        for cls_name in CLASSES:
            log_p = math.log(max(1e-9, self._priors[cls_name]))
            means = self._means[cls_name]
            variances = self._vars[cls_name]
            for xi, mu, var in zip(x, means, variances):
                log_p += -0.5 * math.log(2.0 * math.pi * var) - ((xi - mu) ** 2) / (2.0 * var)
            log_scores[cls_name] = log_p

        max_log = max(log_scores.values())
        exp_scores = {c: math.exp(max(-60.0, s - max_log)) for c, s in log_scores.items()}
        norm = sum(exp_scores.values())
        return {c: round(v / norm, 6) for c, v in exp_scores.items()}

    def predict(self, vec: FeatureVector) -> str:
        probs = self.predict_proba(vec)
        # Apply empirical conviction thresholds: Short >= 0.85, Long >= 0.65, else ABSTAIN
        if probs["ENTER_SHORT"] >= 0.85:
            return "ENTER_SHORT"
        if probs["ENTER_LONG"] >= 0.65:
            return "ENTER_LONG"
        return "ABSTAIN"

    def evaluate_dataset(self, dataset: Sequence[FeatureVector]) -> PolicyEvaluationMetrics:
        neg_total = 0
        neg_correct = 0
        pos_total = 0
        pos_recalled = 0
        dir_correct = 0

        for vec in dataset:
            pred = self.predict(vec)
            if vec.label == "ABSTAIN":
                neg_total += 1
                if pred == "ABSTAIN":
                    neg_correct += 1
            else:
                pos_total += 1
                if pred in ("ENTER_LONG", "ENTER_SHORT"):
                    pos_recalled += 1
                    if pred == vec.label:
                        dir_correct += 1

        return PolicyEvaluationMetrics(
            total_bars=len(dataset),
            positive_signals=pos_total,
            negative_bars=neg_total,
            abstention_accuracy=round(neg_correct / max(1, neg_total), 4),
            setup_recall=round(pos_recalled / max(1, pos_total), 4),
            directional_concordance=round(dir_correct / max(1, pos_recalled), 4),
            learned_class_priors=dict(self._priors),
        )


def evaluate_time_split(
    dataset: Sequence[FeatureVector],
    cutoff_utc: str | None = None,
    train_fraction: float = 0.8,
) -> TimeSplitEvaluation | None:
    """Train on bars strictly before ``cutoff_utc`` and evaluate after it.

    The split is chronological; no row is shuffled. When ``cutoff_utc`` is
    omitted the 80th percentile timestamp is used. Returns ``None`` when either
    side is empty.
    """
    ordered = sorted(dataset, key=lambda row: row.timestamp_utc)
    if not ordered:
        return None
    if cutoff_utc is None:
        index = min(len(ordered) - 1, max(0, int(len(ordered) * train_fraction)))
        cutoff_utc = ordered[index].timestamp_utc

    train = [row for row in ordered if row.timestamp_utc < cutoff_utc]
    test = [row for row in ordered if row.timestamp_utc >= cutoff_utc]
    if not train or not test:
        return None

    model = BayesianCognitivePolicy().fit(train)
    metrics = model.evaluate_dataset(test)
    predictions = [model.predict(row) for row in test]
    false_entries = sum(
        1
        for row, prediction in zip(test, predictions)
        if row.label == "ABSTAIN" and prediction != "ABSTAIN"
    )
    return TimeSplitEvaluation(
        cutoff_utc=cutoff_utc,
        train_bars=len(train),
        test_bars=len(test),
        test_positives=metrics.positive_signals,
        test_negatives=metrics.negative_bars,
        abstention_accuracy=metrics.abstention_accuracy,
        setup_recall=metrics.setup_recall,
        directional_concordance=metrics.directional_concordance,
        predicted_entries=sum(1 for prediction in predictions if prediction != "ABSTAIN"),
        false_entries=false_entries,
    )
