"""Modular gait-analysis pipeline.

Stage order (see docs/architecture.md):
    video -> quality -> detection/tracking -> pose -> smoothing ->
    gait events -> metrics -> clinical flags -> report
"""
