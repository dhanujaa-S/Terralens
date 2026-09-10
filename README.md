
## Intelligent Land Record Digitization and Validation System
### Ministry of Rural Development — Department of Land Resources

## Setup
1. pip install -r requirements.txt
2. sudo apt install tesseract-ocr tesseract-ocr-hin tesseract-ocr-tam tesseract-ocr-tel tesseract-ocr-kan tesseract-ocr-ben tesseract-ocr-guj
3. Add your ANTHROPIC_API_KEY in .env
4. python modules/test_data.py
5. streamlit run app.py

## Demo login
admin / admin123
verifier1 / verify123
uploader1 / upload123
viewer1 / view123
Terra Lens 

Smart India Hackathon 2026 — Land Records Verification System

Terra Lens is a Streamlit-based platform for digitizing, cross-checking, and verifying land records with a human-in-the-loop review process. It combines automated document processing with a structured review workflow so flagged or uncertain records can be manually verified before being finalized.

🚩 Problem Statement

Land record verification is often manual, slow, and error-prone, leading to disputes, delays, and fraud risks. Terra Lens aims to streamline this process by:

Digitizing land records for easier access and processing
Automatically flagging inconsistent or suspicious fields
Providing a clean interface for human reviewers to verify or reject flagged records
Maintaining an auditable trail of verification decisions
✨ Features
📄 Document Repository — centralized storage and retrieval of land record documents
🔍 Automated Field Flagging — highlights fields that may need manual review
✅ Human Review UI — reviewers can view, edit, verify, or reject flagged records through an editable form
🗃️ Database Integration — all verification actions (Verify/Reject) are recorded and persisted
🔐 Structured Workflow — ensures every record passes through a consistent review pipeline before approval
🏗️ Project Modules
Module	Description
Module 1	(Data ingestion / document upload — update with details)
Module 2	(Document processing / OCR — update with details)
Module 3	(Automated flagging logic — update with details)
Module 4	(Database & storage layer — update with details)
Module 5 — Human Review UI	Filters records, provides an editable field form with flagged-field highlighting, and wires Verify/Reject actions to the database and document repository

Update the placeholder modules above with your teammates' module descriptions.

🛠️ Tech Stack
Frontend/UI: Streamlit
Backend/Logic: Python
Database: (specify — e.g. SQLite/PostgreSQL)
(Add any ML/CV or OCR components used elsewhere in the pipeline)
📂 Project Structure
terra-lens/
├── modules/
│   ├── database.py
│   ├── doc_repository.py
│   ├── review_ui.py
│   └── ...
├── app.py
├── requirements.txt
└── README.md
 Getting Started
Prerequisites
Python 3.9+
pip
Installation
bash
git clone https://github.com/<your-username>/terra-lens.git
cd terra-lens
pip install -r requirements.txt
Run the app
bash
streamlit run app.py


Built for Smart India Hackathon (SIH) 2026. Module 5 (Human Review UI) is complete; other modules are in active development.


Content
CS5305-MACHINE LEARNING (1).pptx

PPTX
