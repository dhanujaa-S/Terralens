import streamlit as st
from pathlib import Path

from modules.ocr_pipeline import OCRPipeline
from modules.field_classifier import FieldClassifier, LandField
from modules.validation_engine import ValidationEngine
from modules.database import insert_document, insert_land_record, save_validation
from modules.doc_repository import store_document
from modules.gis_module import auto_geotag_record
from modules.auth import has_permission
from ui.components import (
    page_header, confidence_bar, confidence_badge,
    record_field_row, section_header,
    processing_step,
    empty_state,
)

ALL_FIELDS = [
    "landowner_name", "father_spouse_name", "caste_category",
    "survey_number", "khasra_number", "khata_number", "plot_number",
    "village", "tehsil", "district", "state", "pincode",
    "plot_area", "area_unit", "land_classification", "land_use",
    "boundary_north", "boundary_south", "boundary_east", "boundary_west",
    "ownership_type", "ownership_share",
    "registration_number", "registration_date",
    "mutation_number", "mutation_date", "document_date",
]

FIELD_GROUPS = {
    "👤 Owner": ["landowner_name", "father_spouse_name", "caste_category"],
    "📍 Survey": ["survey_number", "khasra_number", "khata_number", "plot_number"],
    "🗺️  Location": ["village", "tehsil", "district", "state", "pincode"],
    "🌾 Land": ["plot_area", "area_unit", "land_classification", "land_use"],
    "🧭 Boundaries": ["boundary_north", "boundary_south", "boundary_east", "boundary_west"],
    "🤝 Ownership": ["ownership_type", "ownership_share"],
    "📜 Registration": ["registration_number", "registration_date"],
    "🔄 Mutation": ["mutation_number", "mutation_date", "document_date"],
}


def _fv(record, fname: str):
    """Safely read a LandRecord field's extracted value, or None if missing."""
    f = getattr(record, fname, None)
    return getattr(f, "value", None)


def _fc(record, fname: str) -> str:
    """Safely read a LandRecord field's confidence label, defaulting to low."""
    f = getattr(record, fname, None)
    return getattr(f, "confidence", "low")


def _count(record) -> int:
    """Count how many of the 27 land record fields have a non-null value."""
    return sum(1 for fname in ALL_FIELDS if _fv(record, fname) is not None)


def _get_services():
    """Lazily construct and cache the OCR, classifier, and validator services in session state."""
    if "ocr_pipeline" not in st.session_state:
        st.session_state.ocr_pipeline = OCRPipeline()
    if "classifier" not in st.session_state:
        st.session_state.classifier = FieldClassifier()
    if "validator" not in st.session_state:
        st.session_state.validator = ValidationEngine()
    return st.session_state.ocr_pipeline, st.session_state.classifier, st.session_state.validator


def render_upload_page(user: dict) -> None:
    """Render the document upload page and run the full OCR -> AI -> validation -> save pipeline."""
    if not has_permission(user, "upload"):
        st.error("🔒 Access denied. You need uploader or higher role to access this page.")
        return

    page_header("Upload & Process", "AI-powered land record digitization pipeline", "📤")

    col_upload, col_settings = st.columns([2, 1])

    with col_upload:
        uploaded_files = st.file_uploader(
            "Upload land record documents (PDF or image)",
            type=["pdf", "jpg", "jpeg", "png", "tiff", "tif", "bmp"],
            accept_multiple_files=True,
            label_visibility="collapsed",
        )

    with col_settings:
        with st.expander("⚙️  Settings", expanded=False):
            language = st.selectbox(
                "Language",
                ["auto", "hindi", "english", "tamil", "telugu", "kannada", "marathi", "gujarati", "bengali"],
            )
            auto_geotag = st.checkbox("Auto Geo-tag", value=True)
            show_ocr = st.checkbox("Show Raw OCR", value=False)

    if not uploaded_files:
        empty_state("Drop land record documents above to begin", "📄", "Supports PDF, JPG, PNG, TIFF files")
        return

    ocr_pipeline, classifier, validator = _get_services()

    for uploaded_file in uploaded_files:
        filename = uploaded_file.name
        file_bytes = uploaded_file.getvalue()

        with st.expander(f"📄 {filename}  ({len(file_bytes)//1024} KB)", expanded=True):
            try:
                progress = st.progress(0, text="Initializing...")

                processing_step(1, 7, "Creating document record...", progress)
                file_ext = Path(filename).suffix.lower()
                doc_id = insert_document(
                    filename=filename,
                    file_type=file_ext,
                    file_size=len(file_bytes),
                    storage_path="",
                    uploaded_by=user["id"],
                    page_count=1,
                    ocr_method="",
                    ocr_confidence=0.0,
                    image_quality=0.0,
                    raw_ocr_text="",
                )

                processing_step(2, 7, "Storing document...", progress)
                stored = store_document(file_bytes, filename, doc_id)

                processing_step(3, 7, "Running OCR extraction...", progress)
                ocr_result = ocr_pipeline.process_file(file_bytes, filename, language)

                if not ocr_result.raw_text.strip():
                    st.warning("⚠️  OCR returned no text. Document may be unreadable. Try a higher quality scan.")
                    progress.progress(100, text="Stopped — no text found.")
                    continue

                processing_step(4, 7, "Extracting fields with Gemini AI...", progress)
                record = classifier.classify(ocr_result.raw_text)

                processing_step(5, 7, "Validating against business rules...", progress)
                val_result = validator.validate(record)

                processing_step(6, 7, "Saving to database...", progress)
                record_id = insert_land_record(doc_id, record, user["id"])
                save_validation(record_id, val_result)

                processing_step(7, 7, "Geo-tagging location...", progress)
                if auto_geotag and _fv(record, "village"):
                    auto_geotag_record(
                        record_id,
                        _fv(record, "village") or "",
                        _fv(record, "tehsil") or "",
                        _fv(record, "district") or "",
                        _fv(record, "state") or "",
                    )

                progress.progress(100, text="✅ Complete!")
                st.success(f"✅ Successfully processed: **{filename}**")

                m1, m2, m3, m4 = st.columns(4)
                m1.metric("🔍 OCR Confidence", f"{ocr_result.confidence:.0%}")
                m2.metric("🤖 Field Confidence", f"{record.overall_confidence:.0%}")
                m3.metric("✅ Validation Score", f"{val_result.validation_score:.0%}")
                m4.metric("📋 Fields Extracted", f"{_count(record)}/27")

                st.divider()

                col_scan, col_fields = st.columns(2)

                with col_scan:
                    st.markdown("#### 🖼️  Document Preview")
                    if ocr_result.preprocessed_image is not None:
                        st.image(
                            ocr_result.preprocessed_image,
                            caption=f"Method: {ocr_result.method_used} | Quality: {ocr_result.image_quality_score:.0%}",
                            use_column_width=True,
                        )
                    else:
                        st.info("Image preview not available for this file type.")

                    confidence_bar(ocr_result.confidence, f"OCR Confidence: {ocr_result.confidence:.0%}")

                    if show_ocr:
                        st.markdown("#### 📝 Raw OCR Text")
                        st.code(ocr_result.raw_text[:3000], language=None)

                with col_fields:
                    st.markdown("#### 📋 Extracted Fields")
                    for group_name, field_names in FIELD_GROUPS.items():
                        section_header(group_name)
                        for fname in field_names:
                            record_field_row(
                                label=fname.replace("_", " ").title(),
                                value=_fv(record, fname),
                                confidence=_fc(record, fname),
                                flagged=fname in record.flagged_fields,
                            )

                st.divider()
                if val_result.errors or val_result.warnings or val_result.anomalies or val_result.has_duplicates:
                    st.markdown("#### ⚠️  Validation Results")

                    if val_result.errors:
                        st.markdown(f"**❌ Validation Errors ({len(val_result.errors)})**")
                        for e in val_result.errors:
                            st.error(f"[{e.rule}] {e.field_name}: {e.message}")

                    if val_result.warnings:
                        st.markdown(f"**⚠️ Warnings ({len(val_result.warnings)})**")
                        for w in val_result.warnings:
                            st.warning(f"[{w.rule}] {w.field_name}: {w.message}")

                    if val_result.anomalies:
                        st.markdown(f"**🔍 Anomalies Detected ({len(val_result.anomalies)})**")
                        for a in val_result.anomalies:
                            st.info(a)

                    if val_result.has_duplicates:
                        st.warning("🔴 Possible duplicate detected. Please verify in Human Review.")
                else:
                    st.success("✅ Validation passed — no errors or duplicates detected.")

                st.info(f"📌 Record saved with ID **#{record_id}**. Go to Human Review to verify.")

            except Exception as e:
                st.error(f"❌ Failed to process {filename}: {str(e)}")
                st.exception(e)
