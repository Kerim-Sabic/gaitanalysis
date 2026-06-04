"""Clinician-readable PDF report (ReportLab Platypus).

Clean clinical typography, structured tables, model transparency and a mandatory
non-diagnostic disclaimer. Premium look without external assets.
"""
from __future__ import annotations

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.pipeline.narrative import DISCLAIMER
from app.schemas import AnalysisMode, GaitAnalysisResult, PatientCase

NAVY = colors.HexColor("#0B1F3A")
BLUE = colors.HexColor("#2D6CDF")
SLATE = colors.HexColor("#475569")
LIGHT = colors.HexColor("#EEF2F7")
LINE = colors.HexColor("#D5DEEA")


def _styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle("H1", parent=ss["Title"], textColor=NAVY, fontSize=20,
                          spaceAfter=2, alignment=TA_LEFT))
    ss.add(ParagraphStyle("Sub", parent=ss["Normal"], textColor=SLATE, fontSize=10,
                          spaceAfter=10))
    ss.add(ParagraphStyle("H2", parent=ss["Heading2"], textColor=NAVY, fontSize=12,
                          spaceBefore=12, spaceAfter=4))
    ss.add(ParagraphStyle("Body", parent=ss["Normal"], fontSize=9.5, leading=14,
                          textColor=colors.HexColor("#1E293B")))
    ss.add(ParagraphStyle("Small", parent=ss["Normal"], fontSize=8, textColor=SLATE,
                          leading=11))
    ss.add(ParagraphStyle("Disc", parent=ss["Normal"], fontSize=8.5, leading=12,
                          textColor=NAVY))
    return ss


def _kv_table(rows, col_widths):
    t = Table(rows, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), SLATE),
        ("TEXTCOLOR", (1, 0), (-1, -1), colors.HexColor("#0F172A")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, LINE),
    ]))
    return t


def _metric_table(headers, data):
    rows = [headers] + data
    t = Table(rows, colWidths=[58 * mm, 26 * mm, 22 * mm, 64 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, LINE),
    ]))
    return t


def build_pdf_report(result: GaitAnalysisResult, case: PatientCase) -> bytes:
    ss = _styles()
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm,
        title="Horalix Gait AI Report",
    )
    el = []

    # Header
    el.append(Paragraph("HORALIX GAIT AI", ss["H1"]))
    el.append(Paragraph("AI-assisted gait quantification report &nbsp;·&nbsp; For clinician review",
                        ss["Sub"]))
    if result.analysis_mode == AnalysisMode.demo:
        el.append(Paragraph(
            "<b>DEMO MODE</b> — simulated / fallback analysis. Not clinical-grade.",
            ParagraphStyle("warn", parent=ss["Small"], textColor=colors.HexColor("#B45309"))))
    el.append(HRFlowable(width="100%", color=BLUE, thickness=1.4, spaceAfter=8))

    # 1. Patient / case
    el.append(Paragraph("1 · Patient / case information", ss["H2"]))
    el.append(_kv_table([
        ["Patient code", case.patient_code or "—", "Indication", case.indication or "—"],
        ["Age", str(case.age or "—"), "Sex", case.sex.value],
        ["Height (cm)", str(case.height_cm or "—"), "Clinician", case.clinician or "—"],
    ], [30 * mm, 55 * mm, 30 * mm, 55 * mm]))

    # 2. Protocol + 3. Quality
    el.append(Paragraph("2 · Test protocol &amp; video quality", ss["H2"]))
    q = result.quality
    el.append(_kv_table([
        ["Test type", result.test_type.value.replace("_", " "),
         "Analysis mode", result.analysis_mode.value],
        ["Overall quality", f"{q.overall_score:.0f}/100", "Detected view", q.detected_view.value],
        ["Feet visibility", f"{q.feet_visibility:.0f}/100",
         "Camera stability", f"{q.camera_stability:.0f}/100"],
    ], [30 * mm, 55 * mm, 30 * mm, 55 * mm]))
    if q.warnings:
        el.append(Paragraph("Quality notes: " + "; ".join(q.warnings), ss["Small"]))

    # 4. Key metrics
    el.append(Paragraph("3 · Key gait metrics", ss["H2"]))
    data = []
    for m in result.metrics:
        val = "—" if m.value is None else f"{m.value:g} {m.unit}".strip()
        data.append([
            Paragraph(m.label, ss["Small"]), val, f"{m.confidence:.0%}",
            Paragraph(m.interpretation or (m.normal_reference or ""), ss["Small"]),
        ])
    el.append(_metric_table(
        ["Metric", "Value", "Conf.", "Interpretation"], data))

    # 5. Asymmetry
    el.append(Paragraph("4 · Left–right comparison", ss["H2"]))
    arows = []
    for a in result.asymmetry:
        arows.append([
            Paragraph(a.label, ss["Small"]),
            f"{a.left:g}" if a.left is not None else "—",
            f"{a.right:g}" if a.right is not None else "—",
            Paragraph(
                (f"{a.asymmetry_percent:.1f}% — " if a.asymmetry_percent is not None else "")
                + (a.interpretation or ""), ss["Small"]),
        ])
    at = Table([["Parameter", "Left", "Right", "Asymmetry"]] + arows,
               colWidths=[45 * mm, 22 * mm, 22 * mm, 81 * mm])
    at.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), SLATE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    el.append(at)

    # 6. Joint motion summary
    el.append(Paragraph("5 · Joint motion summary", ss["H2"]))
    jrows = [["Joint", "Min (°)", "Max (°)", "ROM (°)"]]
    for c in result.joint_curves:
        jrows.append([c.label, f"{c.min:g}" if c.min is not None else "—",
                      f"{c.max:g}" if c.max is not None else "—",
                      f"{c.rom:g}" if c.rom is not None else "—"])
    jt = Table(jrows, colWidths=[58 * mm, 28 * mm, 28 * mm, 56 * mm])
    jt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), SLATE), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    el.append(jt)

    # 7. Mobility risk + flags
    el.append(Paragraph("6 · Mobility Risk Support Score &amp; flags for review", ss["H2"]))
    el.append(Paragraph(
        f"<b>Mobility Risk Support Score: {result.mobility_risk_support_score:.0f}/100</b> "
        f"({result.mobility_risk_band.replace('_', ' ')}). Screening aid only — not a "
        "fall-risk diagnosis.", ss["Body"]))
    el.append(Spacer(1, 4))
    for f in result.clinical_flags:
        el.append(Paragraph(
            f"<b>[{f.severity.value.upper()}]</b> {f.name} "
            f"<font color='#64748B'>({f.confidence:.0%} conf.)</font> — {f.explanation}",
            ss["Small"]))
        el.append(Spacer(1, 2))

    # 8. Interpretation
    el.append(Paragraph("7 · Interpretation", ss["H2"]))
    el.append(Paragraph(result.report_summary, ss["Body"]))

    # 9. Limitations
    el.append(Paragraph("8 · Limitations", ss["H2"]))
    for lim in result.limitations:
        el.append(Paragraph(f"• {lim}", ss["Small"]))

    # 10. Recommendations
    el.append(Paragraph("9 · Suggested clinician review points", ss["H2"]))
    for r in result.recommendations:
        el.append(Paragraph(f"• {r}", ss["Small"]))

    # 10. Model transparency
    el.append(Paragraph("10 · Model transparency", ss["H2"]))
    mi = result.model_info
    is_demo = result.analysis_mode == AnalysisMode.demo_simulated
    el.append(_kv_table([
        ["Pose model", f"{mi.pose_model} {mi.pose_model_version}", "Backend", mi.pose_backend],
        ["Selected backend", mi.selected_backend or mi.pose_backend,
         "Foot landmarks", "Available" if mi.foot_landmarks_available else "Unavailable"],
        ["Analysis mode", mi.analysis_mode.value, "Keypoint source", mi.keypoint_source],
        ["Real model loaded", "Yes" if mi.model_loaded else "No",
         "Model verified", "Yes" if mi.model_verified else "No"],
        ["Device", mi.device, "Simulated data used", "Yes" if mi.simulated_data_used else "No"],
        ["Frames processed", str(mi.frame_count),
         "Valid pose frames", str(mi.valid_pose_frames)],
        ["Mean keypoint confidence", f"{mi.mean_keypoint_confidence:.0%}",
         "Calibration", mi.calibration_status],
        ["SAM2 segmentation", mi.sam2_status, "Depth helper", mi.depth_status],
        ["MMPose RTMW", mi.mmpose_status, "WHAM 3D", mi.wham_status],
        ["Lowest-confidence keypoints", ", ".join(mi.lowest_confidence_keypoints) or "—",
         "Interpolation used", "Yes" if mi.interpolation_used else "No"],
        ["Clinical validation", mi.clinical_validation_status, "Pipeline", f"v{mi.pipeline_version}"],
    ], [38 * mm, 52 * mm, 34 * mm, 46 * mm]))
    if mi.selection_reason:
        el.append(Paragraph(f"<b>Selection reason:</b> {mi.selection_reason}", ss["Small"]))
    if mi.backend_scores:
        score_text = "; ".join(
            f"{name}: {details.get('final_score', 0):.1f}/100"
            for name, details in mi.backend_scores.items()
        )
        el.append(Paragraph(f"<b>Compared backend scores:</b> {score_text}", ss["Small"]))
    if mi.backend_failures:
        el.append(Paragraph(
            "<b>Unavailable/failed backends:</b> "
            + "; ".join(f"{name}: {reason}" for name, reason in mi.backend_failures.items()),
            ss["Small"],
        ))
    if mi.helper_models:
        for name, details in mi.helper_models.items():
            status = details.get("status", "NOT_RUN")
            used = "used" if details.get("used_in_analysis") else "not used"
            error = details.get("error", "")
            text = f"<b>{name.upper()}:</b> {status}; {used} in this analysis."
            if error:
                text += f" Reason: {error}"
            el.append(Paragraph(text, ss["Small"]))

    # Provenance statement (real vs demo).
    if is_demo:
        el.append(Paragraph(
            "<b>Demo Mode — simulated keypoints, not real patient analysis.</b>",
            ParagraphStyle("prov", parent=ss["Small"], textColor=colors.HexColor("#B45309"))))
    else:
        el.append(Paragraph(
            "Real AI keypoint analysis from uploaded video. This analysis is intended "
            "to support clinical review and should not be used as a standalone "
            "diagnostic decision.", ss["Small"]))

    # 11. Disclaimer
    el.append(Spacer(1, 8))
    el.append(HRFlowable(width="100%", color=LINE, thickness=0.8, spaceAfter=6))
    el.append(Paragraph("Disclaimer", ss["H2"]))
    el.append(Paragraph(DISCLAIMER, ss["Disc"]))
    el.append(Paragraph(
        f"Generated {result.created_at.strftime('%Y-%m-%d %H:%M UTC')} · "
        f"Analysis ID {result.analysis_id}", ss["Small"]))

    doc.build(el)
    return buf.getvalue()
