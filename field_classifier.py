from google import genai
from google.genai import types
from pydantic import BaseModel
import json
import re
import logging
from dataclasses import dataclass, field, fields, asdict
from typing import Optional

logger = logging.getLogger(__name__)


class GeminiLandField(BaseModel):
    value: Optional[str] = None
    confidence: str = "low"
    confidence_score: float = 0.0


class GeminiLandRecordResponse(BaseModel):
    landowner_name: GeminiLandField
    father_spouse_name: GeminiLandField
    caste_category: GeminiLandField
    survey_number: GeminiLandField
    khasra_number: GeminiLandField
    khata_number: GeminiLandField
    plot_number: GeminiLandField
    village: GeminiLandField
    tehsil: GeminiLandField
    district: GeminiLandField
    state: GeminiLandField
    pincode: GeminiLandField
    plot_area: GeminiLandField
    area_unit: GeminiLandField
    land_classification: GeminiLandField
    land_use: GeminiLandField
    boundary_north: GeminiLandField
    boundary_south: GeminiLandField
    boundary_east: GeminiLandField
    boundary_west: GeminiLandField
    ownership_type: GeminiLandField
    ownership_share: GeminiLandField
    registration_number: GeminiLandField
    registration_date: GeminiLandField
    mutation_number: GeminiLandField
    mutation_date: GeminiLandField
    document_date: GeminiLandField


@dataclass
class LandField:
    """
    Represents one extracted field from a land record.
    Every attribute in LandRecord is a LandField.
    confidence is exactly one of: "high", "medium", "low"
    needs_review is True when the field is uncertain or missing.
    """
    value: Optional[str]
    confidence: str
    confidence_score: float
    needs_review: bool


@dataclass
class LandRecord:
    """
    All 27 structured fields extracted from one land record document.
    Each field is a LandField with value, confidence, and review flag.
    Used by validation_engine.py and database.py.
    """
    landowner_name:      LandField
    father_spouse_name:  LandField
    caste_category:      LandField

    survey_number:       LandField
    khasra_number:       LandField
    khata_number:        LandField
    plot_number:         LandField

    village:             LandField
    tehsil:              LandField
    district:            LandField
    state:               LandField
    pincode:             LandField

    plot_area:           LandField
    area_unit:           LandField
    land_classification: LandField
    land_use:            LandField

    boundary_north:      LandField
    boundary_south:      LandField
    boundary_east:       LandField
    boundary_west:       LandField

    ownership_type:      LandField
    ownership_share:     LandField

    registration_number: LandField
    registration_date:   LandField
    mutation_number:     LandField
    mutation_date:       LandField
    document_date:       LandField

    extraction_method:   str = "gemini-api"
    overall_confidence:  float = 0.0
    flagged_fields:      list = field(default_factory=list)
    raw_text_used:       str = ""

    def get_flagged(self) -> list:
        """Return names of all LandField attributes where needs_review is True."""
        flagged = []
        for f in fields(self):
            val = getattr(self, f.name)
            if isinstance(val, LandField) and val.needs_review:
                flagged.append(f.name)
        return flagged

    def calculate_overall_confidence(self) -> None:
        """
        Set overall_confidence to the average confidence_score of all
        LandField attributes that have a non-None value.
        Also populates flagged_fields list.
        """
        scores = []
        for f in fields(self):
            val = getattr(self, f.name)
            if isinstance(val, LandField) and val.value is not None:
                scores.append(val.confidence_score)
        self.overall_confidence = round(
            sum(scores) / len(scores), 3
        ) if scores else 0.0
        self.flagged_fields = self.get_flagged()

    def to_dict(self) -> dict:
        """Serialize to plain dict for JSON export."""
        return asdict(self)


class FieldClassifier:
    """
    Extracts structured land record fields from raw OCR text using Google Gemini.
    Sends cleaned OCR text to gemini-2.5-flash with a detailed prompt
    that includes Hindi and Tamil terminology hints.
    Parses the JSON response into a LandRecord dataclass.
    Never crashes — returns empty LandRecord on any API failure.
    """
    MODEL = "gemini-3.6-flash"
    MAX_TOKENS = 3000
    SYSTEM_PROMPT = (
        "You are an expert in Indian land records and revenue administration. "
        "You have deep knowledge of land record terminology in Hindi, Tamil, "
        "Telugu, Kannada, Bengali, Gujarati, Marathi, and English. "
        "You understand documents like RoR (Record of Rights), Khasra, "
        "Khatauni, Patta, and Jamabandi. "
        "Extract information precisely. Set confidence to low if any field "
        "is unclear or ambiguous. Never guess or hallucinate values. "
        "Return only valid JSON — no markdown, no explanation, no preamble."
    )

    def __init__(self):
        """Initialize the Gemini client. Reads GEMINI_API_KEY from environment."""
        self.client = genai.Client()

    def _build_prompt(self, ocr_text: str) -> str:
        """
        Build the extraction prompt with all 27 field names,
        multilingual hints, and the exact JSON structure Gemini must return.
        """
        return f"""Extract all land record information from the OCR text below.
Return ONLY a valid JSON object with EXACTLY this structure.
No markdown. No extra keys. No explanation before or after.

{{
  "landowner_name":       {{"value": null, "confidence": "low", "confidence_score": 0.0}},
  "father_spouse_name":   {{"value": null, "confidence": "low", "confidence_score": 0.0}},
  "caste_category":       {{"value": null, "confidence": "low", "confidence_score": 0.0}},
  "survey_number":        {{"value": null, "confidence": "low", "confidence_score": 0.0}},
  "khasra_number":        {{"value": null, "confidence": "low", "confidence_score": 0.0}},
  "khata_number":         {{"value": null, "confidence": "low", "confidence_score": 0.0}},
  "plot_number":          {{"value": null, "confidence": "low", "confidence_score": 0.0}},
  "village":              {{"value": null, "confidence": "low", "confidence_score": 0.0}},
  "tehsil":               {{"value": null, "confidence": "low", "confidence_score": 0.0}},
  "district":             {{"value": null, "confidence": "low", "confidence_score": 0.0}},
  "state":                {{"value": null, "confidence": "low", "confidence_score": 0.0}},
  "pincode":              {{"value": null, "confidence": "low", "confidence_score": 0.0}},
  "plot_area":            {{"value": null, "confidence": "low", "confidence_score": 0.0}},
  "area_unit":            {{"value": null, "confidence": "low", "confidence_score": 0.0}},
  "land_classification":  {{"value": null, "confidence": "low", "confidence_score": 0.0}},
  "land_use":             {{"value": null, "confidence": "low", "confidence_score": 0.0}},
  "boundary_north":       {{"value": null, "confidence": "low", "confidence_score": 0.0}},
  "boundary_south":       {{"value": null, "confidence": "low", "confidence_score": 0.0}},
  "boundary_east":        {{"value": null, "confidence": "low", "confidence_score": 0.0}},
  "boundary_west":        {{"value": null, "confidence": "low", "confidence_score": 0.0}},
  "ownership_type":       {{"value": null, "confidence": "low", "confidence_score": 0.0}},
  "ownership_share":      {{"value": null, "confidence": "low", "confidence_score": 0.0}},
  "registration_number":  {{"value": null, "confidence": "low", "confidence_score": 0.0}},
  "registration_date":    {{"value": null, "confidence": "low", "confidence_score": 0.0}},
  "mutation_number":      {{"value": null, "confidence": "low", "confidence_score": 0.0}},
  "mutation_date":        {{"value": null, "confidence": "low", "confidence_score": 0.0}},
  "document_date":        {{"value": null, "confidence": "low", "confidence_score": 0.0}}
}}

RULES:
- confidence must be exactly "high" (score 0.8-1.0), "medium" (0.5-0.79), or "low" (0.0-0.49)
- confidence_score must be a float that matches the confidence label range
- If a field is not present in the text, set value to null and confidence to "low"
- Dates: standardize to DD-MM-YYYY format
- plot_area: numeric value only — "2.5" not "2.5 acres"
- ownership_type: standardize to one of: Single / Joint / Government / Trust / Disputed

HINDI TERMS TO RECOGNIZE:
खातेदार = landowner_name
खसरा = khasra_number
खाता = khata_number
ग्राम = village
तहसील = tehsil
जिला = district
क्षेत्रफल = plot_area

TAMIL TERMS TO RECOGNIZE:
சர்வே எண் = survey_number
கிராமம் = village
மாவேட்டம் = district
பட்டா = registration_number
உரிமையாளர் = landowner_name

OCR TEXT:
{ocr_text}
"""

    def _parse_response(self, response_text: str) -> dict:
        """
        Robustly parse JSON from Gemini response.
        Strips markdown fences if present.
        Finds first { and last } to extract JSON object.
        Returns empty dict on any parse failure.
        """
        try:
            text = re.sub(r"```(?:json)?", "", response_text).strip()
            text = text.replace("```", "").strip()
            start = text.find("{")
            end = text.rfind("}") + 1
            if start == -1 or end == 0:
                logger.error("No JSON object found in Gemini response")
                return {}
            return json.loads(text[start:end])
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            logger.debug(f"Response was: {response_text[:500]}")
            return {}
        except Exception as e:
            logger.error(f"Response parse error: {e}")
            return {}

    def _dict_to_land_field(self, d: dict) -> LandField:
        """
        Convert a raw dict from Gemini JSON response into a LandField.
        Enforces that confidence_score matches the confidence label range.
        Sets needs_review=True if score < 0.6 or value is None.
        """
        value = d.get("value")
        confidence = str(d.get("confidence", "low")).lower().strip()
        score = float(d.get("confidence_score", 0.0))

        if confidence == "high":
            score = max(score, 0.80)
            score = min(score, 1.00)
        elif confidence == "medium":
            score = max(score, 0.50)
            score = min(score, 0.79)
        else:
            confidence = "low"
            score = min(score, 0.49)

        clean_value = str(value).strip() if value is not None and str(value).strip() else None
        needs_review = clean_value is None or score < 0.60

        return LandField(
            value=clean_value,
            confidence=confidence,
            confidence_score=round(score, 3),
            needs_review=needs_review,
        )

    def _empty_land_field(self) -> LandField:
        """Return a blank low-confidence LandField used when API fails."""
        return LandField(
            value=None,
            confidence="low",
            confidence_score=0.0,
            needs_review=True,
        )

    def classify(self, ocr_text: str, truncate_chars: int = 8000) -> LandRecord:
        """
        Main entry point.
        Takes raw OCR text, calls the Gemini API, returns structured LandRecord.
        On any failure returns a LandRecord with all fields as empty low-confidence.
        Never raises an exception.
        """
        text_to_send = ocr_text[:truncate_chars]
        logger.info(f"Sending {len(text_to_send)} chars to Gemini API...")

        raw_dict = {}
        try:
            response = self.client.models.generate_content(
                model=self.MODEL,
                contents=self._build_prompt(text_to_send),
                config=types.GenerateContentConfig(
                    system_instruction=self.SYSTEM_PROMPT,
                    temperature=0.1,
                    max_output_tokens=self.MAX_TOKENS,
                    response_mime_type="application/json",
                    response_schema=GeminiLandRecordResponse,
                ),
            )
            logger.info("Gemini API response received.")

            if response.parsed:
                if hasattr(response.parsed, "model_dump"):
                    raw_dict = response.parsed.model_dump()
                elif isinstance(response.parsed, dict):
                    raw_dict = response.parsed
                else:
                    raw_dict = {}
            else:
                response_text = response.text or ""
                raw_dict = self._parse_response(response_text)
        except Exception as e:
            logger.error(f"Gemini API call failed: {e}")
            raw_dict = {}

        def get_field(key: str) -> LandField:
            raw = raw_dict.get(key)
            if raw and isinstance(raw, dict):
                return self._dict_to_land_field(raw)
            return self._empty_land_field()

        record = LandRecord(
            landowner_name=      get_field("landowner_name"),
            father_spouse_name=  get_field("father_spouse_name"),
            caste_category=      get_field("caste_category"),
            survey_number=       get_field("survey_number"),
            khasra_number=       get_field("khasra_number"),
            khata_number=        get_field("khata_number"),
            plot_number=         get_field("plot_number"),
            village=             get_field("village"),
            tehsil=              get_field("tehsil"),
            district=            get_field("district"),
            state=               get_field("state"),
            pincode=             get_field("pincode"),
            plot_area=           get_field("plot_area"),
            area_unit=           get_field("area_unit"),
            land_classification= get_field("land_classification"),
            land_use=            get_field("land_use"),
            boundary_north=      get_field("boundary_north"),
            boundary_south=      get_field("boundary_south"),
            boundary_east=       get_field("boundary_east"),
            boundary_west=       get_field("boundary_west"),
            ownership_type=      get_field("ownership_type"),
            ownership_share=     get_field("ownership_share"),
            registration_number= get_field("registration_number"),
            registration_date=   get_field("registration_date"),
            mutation_number=     get_field("mutation_number"),
            mutation_date=       get_field("mutation_date"),
            document_date=       get_field("document_date"),
            raw_text_used=       text_to_send[:300] + "...",
        )
        record.calculate_overall_confidence()
        logger.info(
            f"Extraction complete. "
            f"Confidence: {record.overall_confidence:.1%}  "
            f"Flagged fields: {len(record.flagged_fields)}"
        )
        return record


if __name__ == "__main__":
    import os

    logging.basicConfig(level=logging.INFO)

    sample_ocr = """
    RECORD OF RIGHTS (ROR)
    District: Pune   Tehsil: Haveli   Village: Khed
    Khata No: 125    Survey No: 47/2   Khasra No: 89
    Landowner: Ramesh Kumar Sharma
    Father Name: Late Suresh Sharma
    Caste: General
    Land Area: 2.50 Acres
    Land Classification: Agricultural
    Registration Number: REG/2019/45678
    Date of Registration: 15-08-2019
    Mutation No: MUT/2020/1234
    Mutation Date: 22-01-2020
    North: Road   South: Plot 46   East: River   West: Plot 48
    Ownership: Single
    State: Maharashtra   Pincode: 411001
    """

    if not os.getenv("GEMINI_API_KEY"):
        print("ERROR: GEMINI_API_KEY not set in environment.")
    else:
        clf = FieldClassifier()
        rec = clf.classify(sample_ocr)
        print("\n" + "=" * 60)
        print(f"Overall Confidence: {rec.overall_confidence:.1%}")
        print(f"Flagged fields:     {rec.flagged_fields}")
        print("\nExtracted fields:")
        extracted_count = 0
        for f in fields(rec):
            val = getattr(rec, f.name)
            if isinstance(val, LandField) and val.value:
                extracted_count += 1
                icon = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(val.confidence, "")
                print(f"  {icon} {f.name}: {val.value} ({val.confidence})")
        print()
        if extracted_count > 0:
            print("Module 2 — field_classifier.py OK")
        else:
            print("Module 2 — field_classifier.py FAILED")
