import streamlit as st
from typing import Optional, Any


def page_header(title: str, subtitle: str = "", icon: str = "") -> None:
    """Render a styled page header with an optional icon and muted subtitle."""
    heading = f"{icon} {title}".strip()
    html = f"<div class='page-header'><h1>{heading}</h1>"
    if subtitle:
        html += f"<p style='color:var(--text-muted);margin:0;font-size:17px;'>{subtitle}</p>"
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def status_badge(status: str) -> str:
    """Return an HTML span string for a colored record status badge."""
    mapping = {
        "verified": "badge-verified",
        "pending": "badge-pending",
        "rejected": "badge-rejected",
    }
    css_class = mapping.get(status, "badge-pending")
    return f"<span class='status-badge {css_class}'>{status.upper()}</span>"


def confidence_badge(confidence: str) -> str:
    """Return an HTML span string for a colored confidence-level badge."""
    mapping = {
        "high": "badge-high",
        "medium": "badge-medium",
        "low": "badge-low",
    }
    css_class = mapping.get(confidence, "badge-low")
    return f"<span class='status-badge {css_class}'>{confidence.upper()}</span>"


def role_badge(role: str) -> str:
    """Return an HTML span string for a colored user-role badge."""
    mapping = {
        "admin": "badge-admin",
        "verifier": "badge-verifier",
        "uploader": "badge-uploader",
        "viewer": "badge-viewer",
    }
    css_class = mapping.get(role, "badge-viewer")
    return f"<span class='status-badge {css_class}'>{role.upper()}</span>"


def confidence_bar(score: float, label: str = "") -> None:
    """Render a color-coded confidence label followed by a progress bar."""
    if score >= 0.8:
        st.success(label or f"High confidence: {score:.0%}")
    elif score >= 0.5:
        st.warning(label or f"Medium confidence: {score:.0%}")
    else:
        st.error(label or f"Low confidence: {score:.0%}")
    st.progress(min(1.0, max(0.0, score)))


def record_field_row(label: str, value: Optional[str], confidence: str = "", flagged: bool = False) -> None:
    """Render one land record field as a labeled, valued, badge-annotated row."""
    col_label, col_value, col_badge = st.columns([2, 3, 1])
    display_label = f"⚠️  {label}" if flagged else label
    with col_label:
        st.markdown(f"**{display_label}**")
    with col_value:
        if value:
            st.markdown(value)
        else:
            st.markdown("<span style='color:var(--text-muted);'>—</span>", unsafe_allow_html=True)
    with col_badge:
        if confidence:
            st.markdown(confidence_badge(confidence), unsafe_allow_html=True)


def section_header(title: str) -> None:
    """Render a small styled subheader for grouping related fields."""
    st.markdown(f"<div class='section-header'>{title}</div>", unsafe_allow_html=True)


def empty_state(message: str, icon: str = "📭", hint: str = "") -> None:
    """Render a centered empty state placeholder for pages/sections with no data."""
    html = (
        "<div style='text-align:center;padding:3rem 1rem;'>"
        f"<div style='font-size:3.2rem;'>{icon}</div>"
        f"<div style='font-weight:700;font-size:1.3rem;margin-top:0.6rem;'>{message}</div>"
    )
    if hint:
        html += f"<div style='color:var(--text-muted);font-size:1rem;margin-top:0.35rem;'>{hint}</div>"
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def error_panel(errors: list, title: str = "Validation Errors") -> None:
    """Render a collapsible panel listing validation errors, if any exist."""
    if not errors:
        return
    with st.expander(f"❌ {title} ({len(errors)})", expanded=True):
        for e in errors:
            st.error(e)


def warning_panel(warnings: list, title: str = "Warnings") -> None:
    """Render a collapsible panel listing warnings, if any exist."""
    if not warnings:
        return
    with st.expander(f"⚠️  {title} ({len(warnings)})", expanded=False):
        for w in warnings:
            st.warning(w)


def anomaly_panel(anomalies: list) -> None:
    """Render a collapsible panel listing detected anomalies, if any exist."""
    if not anomalies:
        return
    with st.expander(f"🔍 Anomalies Detected ({len(anomalies)})", expanded=False):
        for a in anomalies:
            st.info(a)


def processing_step(step_num: int, total_steps: int, message: str, progress_bar) -> None:
    """Advance a Streamlit progress bar to reflect the current pipeline step."""
    pct = int((step_num / total_steps) * 100)
    progress_bar.progress(pct, text=f"Step {step_num}/{total_steps}: {message}")


def info_card(title: str, content: str, icon: str = "ℹ️ ") -> None:
    """Render a styled card with an icon, bold title, and body content."""
    html = (
        "<div class='terra-card'>"
        f"<div style='font-weight:700;font-size:1.2rem;'>{icon} {title}</div>"
        f"<div style='margin-top:0.6rem;color:var(--text-secondary);font-size:15.5px;'>{content}</div>"
        "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def metric_row(metrics: list) -> None:
    """Render a row of st.metric cards from a list of {label, value, delta} dicts."""
    columns = st.columns(len(metrics))
    for col, metric in zip(columns, metrics):
        with col:
            st.metric(
                label=metric.get("label", ""),
                value=metric.get("value", ""),
                delta=metric.get("delta"),
            )
