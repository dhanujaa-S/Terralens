import streamlit as st


def inject_styles() -> None:
    """Inject the Terra Lens enterprise-grade CSS theme into the current Streamlit page."""
    st.markdown(
        """
        <style>
        :root {
            --primary: #1B2A4A;
            --primary-light: #2D4373;
            --secondary: #0D7E6A;
            --accent: #E8A020;
            --danger: #C0392B;
            --bg-main: #F4F6FA;
            --bg-card: #FFFFFF;
            --text-primary: #1A202C;
            --text-secondary: #4A5568;
            --text-muted: #718096;
            --border: #E2E8F0;
            --shadow: 0 2px 10px rgba(0,0,0,0.08);
            --shadow-lg: 0 6px 20px rgba(0,0,0,0.10);
        }

        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}

        html, body, .stApp {
            font-size: 16px;
            background: var(--bg-main);
        }

        /* ---------- Main content width & spacing ---------- */
        div[data-testid="stAppViewContainer"] .main .block-container,
        .block-container {
            max-width: 1500px;
            padding-top: 1.5rem;
            padding-bottom: 2rem;
            padding-left: 2.5rem;
            padding-right: 2.5rem;
        }

        div[data-testid="stVerticalBlock"] {
            gap: 0.9rem;
        }

        /* ---------- Sidebar ---------- */
        section[data-testid="stSidebar"] {
            background: #FFFFFF;
            border-right: 1px solid var(--border);
            min-width: 290px !important;
            max-width: 300px !important;
            width: 290px !important;
        }
        section[data-testid="stSidebar"] > div {
            width: 290px !important;
            padding: 1.5rem 1.25rem;
        }
        section[data-testid="stSidebar"] div[data-testid="stRadio"] label {
            padding: 0.55rem 0.6rem;
            border-radius: 8px;
        }
        section[data-testid="stSidebar"] div[data-testid="stRadio"] label:hover {
            background: var(--bg-main);
        }
        section[data-testid="stSidebar"] div[data-testid="stRadio"] p,
        section[data-testid="stSidebar"] div[data-testid="stRadio"] label span {
            font-size: 16px;
            font-weight: 500;
        }
        section[data-testid="stSidebar"] p, section[data-testid="stSidebar"] span {
            font-size: 15px;
        }

        /* ---------- Metrics ---------- */
        div[data-testid="stMetric"] {
            background: var(--bg-card);
            border-radius: 12px;
            box-shadow: var(--shadow);
            border-left: 5px solid var(--primary);
            padding: 1.35rem 1.5rem;
        }
        div[data-testid="stMetric"]:hover {
            box-shadow: var(--shadow-lg);
        }
        div[data-testid="stMetricValue"] {
            font-size: 2.1rem;
            font-weight: 700;
        }
        div[data-testid="stMetricLabel"] {
            font-size: 1rem;
            color: var(--text-secondary);
        }

        /* ---------- Buttons & form controls ---------- */
        .stButton > button {
            background: var(--primary);
            color: #FFFFFF;
            border-radius: 8px;
            border: none;
            cursor: pointer;
            font-size: 15px;
            font-weight: 600;
            padding: 0.65rem 1.5rem;
        }
        .stButton > button:hover {
            background: var(--primary-light);
            color: #FFFFFF;
        }
        .stDownloadButton > button {
            border-radius: 8px;
            font-size: 15px;
            font-weight: 600;
            padding: 0.65rem 1.5rem;
        }

        div[data-testid="stTextInput"] input,
        div[data-testid="stTextArea"] textarea,
        div[data-baseweb="select"] > div,
        div[data-testid="stNumberInput"] input {
            font-size: 15px !important;
            border-radius: 8px !important;
            min-height: 2.75rem;
        }
        div[data-testid="stTextInput"] label,
        div[data-testid="stTextArea"] label,
        div[data-testid="stSelectbox"] label,
        div[data-testid="stNumberInput"] label,
        div[data-testid="stSlider"] label,
        div[data-testid="stCheckbox"] label p {
            font-size: 15px !important;
            font-weight: 600;
            color: var(--text-secondary);
        }

        div[data-testid="stExpander"] {
            background: var(--bg-card);
            border-radius: 10px;
            box-shadow: var(--shadow);
            border: 1px solid var(--border);
        }
        div[data-testid="stExpander"] summary {
            font-size: 16px;
            font-weight: 600;
            padding: 0.9rem 1.1rem;
        }

        /* ---------- Typography ---------- */
        h1 {
            color: var(--text-primary);
            font-size: 2.2rem;
            font-weight: 800;
            margin-bottom: 0.3rem;
            letter-spacing: -0.01em;
        }
        h2 {
            color: var(--text-primary);
            font-size: 1.5rem;
            font-weight: 700;
        }
        h3 {
            color: var(--text-primary);
            font-size: 1.3rem;
            font-weight: 600;
        }
        h4 {
            font-size: 1.3rem;
            font-weight: 700;
            color: var(--text-primary);
        }
        div[data-testid="stMarkdownContainer"] p,
        div[data-testid="stCaptionContainer"] {
            font-size: 15.5px;
            line-height: 1.55;
        }

        .terra-card {
            background: var(--bg-card);
            border-radius: 14px;
            box-shadow: var(--shadow);
            padding: 1.75rem;
            border: 1px solid var(--border);
            margin-bottom: 1.1rem;
        }

        .status-badge {
            display: inline-block;
            border-radius: 20px;
            padding: 5px 16px;
            font-size: 13.5px;
            font-weight: 700;
            letter-spacing: 0.03em;
        }

        .badge-verified { background: #D4EDDA; color: #155724; }
        .badge-pending  { background: #FFF3CD; color: #856404; }
        .badge-rejected { background: #F8D7DA; color: #721C24; }
        .badge-high     { background: #D4EDDA; color: #155724; }
        .badge-medium   { background: #FFF3CD; color: #856404; }
        .badge-low      { background: #F8D7DA; color: #721C24; }
        .badge-admin    { background: #1B2A4A; color: #FFFFFF; }
        .badge-verifier { background: #0D7E6A; color: #FFFFFF; }
        .badge-uploader { background: #2471A3; color: #FFFFFF; }
        .badge-viewer   { background: #566573; color: #FFFFFF; }

        .page-header {
            padding-bottom: 1.1rem;
            border-bottom: 3px solid var(--primary);
            margin-bottom: 1.75rem;
        }
        .page-header h1 {
            font-size: 34px;
        }

        .field-row {
            display: flex;
            align-items: center;
            padding: 0.6rem 0;
            border-bottom: 1px solid var(--border);
            gap: 0.5rem;
            font-size: 15.5px;
        }

        div[data-testid="stDataFrame"] {
            border-radius: 10px;
            overflow: hidden;
            box-shadow: var(--shadow);
        }
        div[data-testid="stDataFrame"] thead tr th {
            background: var(--primary);
            color: #FFFFFF;
            font-size: 14.5px;
        }
        div[data-testid="stDataFrame"] td {
            font-size: 14.5px;
        }

        div[data-testid="stAlert"] {
            border-radius: 10px;
            font-size: 15.5px;
            padding: 0.9rem 1.1rem;
        }

        .section-header {
            color: var(--primary);
            font-weight: 700;
            font-size: 21px;
            padding: 0.6rem 0 0.35rem 0;
            border-bottom: 2px solid var(--border);
            margin-bottom: 0.75rem;
        }

        /* File uploader */
        div[data-testid="stFileUploaderDropzone"] {
            border-radius: 12px;
            padding: 1rem;
        }

        /* Enlarge the Leaflet GIS map iframe without touching backend/gis_module.py */
        iframe {
            min-height: 650px;
        }
        div[data-testid="stCustomComponentV1"] {
            min-height: 650px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
