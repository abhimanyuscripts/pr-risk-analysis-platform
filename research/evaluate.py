"""Phase 9: one scoring function used by every method, so comparisons are fair."""
from sklearn.metrics import (confusion_matrix, f1_score, precision_score,
                             recall_score, roc_auc_score)


def evaluate(y_true, y_pred, y_score) -> dict:
    y_true = y_true.astype(int)
    y_pred = y_pred.astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    has_both = y_true.nunique() == 2   # recall/F1/AUC need risky AND safe PRs in the test set
    return {
        "base_rate_%": round(y_true.mean() * 100, 1),
        "precision": round(precision_score(y_true, y_pred, zero_division=0), 3),
        "recall": round(recall_score(y_true, y_pred), 3) if has_both else None,
        "f1": round(f1_score(y_true, y_pred), 3) if has_both else None,
        "roc_auc": round(roc_auc_score(y_true, y_score), 3) if has_both else None,
        "tp": int(tp), "fp": int(fp), "fn": int(fn), "tn": int(tn),
    }