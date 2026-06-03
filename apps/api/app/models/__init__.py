"""Model loading, registry and status — the real-model control plane.

These modules own the decision of which pose backend is active, whether a *real*
model is actually loaded and verified, and the hard rule that real analysis must
never silently fall back to simulated/demo keypoints.
"""
from .model_loader import ModelLoader, ModelUnavailableError, get_model_loader
from .model_status import ModelStatus, ModelVerifyResult

__all__ = [
    "ModelLoader",
    "ModelUnavailableError",
    "get_model_loader",
    "ModelStatus",
    "ModelVerifyResult",
]
