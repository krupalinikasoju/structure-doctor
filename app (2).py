import os
import json
import sqlite3
import base64
from datetime import datetime
from io import BytesIO

import streamlit as st
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Image as RLImage,
    Table,
    TableStyle
)
from reportlab.lib import colors

from risk_engine import assess_risk


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Structure Doctor AI",
    page_icon="🏗️",
    layout="wide"
)

DB_FILE = "structure_history.db"


# ============================================================
# DATABASE
# ============================================================

def init_database():
    conn = sqlite3.connect(DB_FILE)

    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            structure_type TEXT,
            material TEXT,
            crack_width REAL,
            crack_length REAL,
            risk_score REAL,
            risk_level TEXT,
            ai_analysis TEXT
        )
    """)

    conn.commit()
    conn.close()


def save_assessment(inputs, result):
    conn = sqlite3.connect(DB_FILE)

    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO assessments (
            timestamp,
            structure_type,
            material,
            crack_width,
            crack_length,
            risk_score,
            risk_level,
            ai_analysis
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            datetime.now().isoformat(),
            inputs.get("structure_type"),
            inputs.get("material"),
            inputs.get("crack_width"),
            inputs.get("crack_length"),
            result.get("risk_score"),
            result.get("risk_level"),
            json.dumps(inputs.get("ai_result", {}))
        )
    )

    conn.commit()
    conn.close()


init_database()


# ============================================================
# GET OPENAI API KEY
# ============================================================

def get_api_key():

    api_key = os.getenv("OPENAI_API_KEY")

    if api_key:
        return api_key

    try:
        api_key = st.secrets["OPENAI_API_KEY"]
        return api_key
    except Exception:
        return None


# ============================================================
# AI IMAGE ANALYSIS
# ============================================================

def analyze_image_with_ai(image, inputs):

    api_key = get_api_key()

    if not api_key:

        return {
            "available": False,
            "crack_detected": False,
            "severity": "Unknown",
            "risk_score": 0,
            "damage_type": "AI unavailable",
            "location": "Unknown",
            "description": (
                "AI vision is not configured. "
                "The uploaded image can still be included "
                "in the assessment report."
            ),
            "possible_causes": "",
            "recommendation": ""
        }

    try:

        from openai import OpenAI

        client = OpenAI(api_key=api_key)

        buffer = BytesIO()

        image.save(
            buffer,
            format="JPEG"
        )

        image_base64 = base64.b64encode(
            buffer.getvalue()
        ).decode("utf-8")

        inspection_context = json.dumps({
            "structure_type": inputs.get("structure_type"),
            "material": inputs.get("material"),
            "crack_width_mm": inputs.get("crack_width"),
            "crack_length_mm": inputs.get("crack_length"),
            "environment": inputs.get("environment"),
        }, ensure_ascii=False)

        prompt = f"""
You are an AI assistant for preliminary visual inspection
of buildings and civil structures.

Analyze the uploaded image together with these CURRENT
inspection inputs:
{inspection_context}

Use the selected structure type, material, crack width,
crack length, and environmental condition when relevant.
Base severity and possible causes on the visible evidence
and supplied context. Do not automatically label every
crack as Low severity, and do not invent unsupported findings.

IMPORTANT:
A photograph cannot reliably determine actual structural
load-bearing capacity, crack depth, remaining strength,
or structural safety certification.

Return ONLY valid JSON with exactly these fields:
{{
  "crack_detected": true,
  "damage_type": "type of visible damage",
  "location": "visible location of damage",
  "severity": "Low",
  "risk_score": 20,
  "description": "description of visible evidence",
  "possible_causes": "possible causes based on current evidence",
  "recommendation": "recommended next action"
}}

Severity must be one of: Low, Moderate, High, Critical.
Risk score must be a number from 0 to 100.

If no visible crack or structural damage is present,
set crack_detected to false.

If potentially dangerous structural damage is visible,
recommend restricting access and professional structural
inspection.

Do not claim that crack depth or actual structural capacity
can be determined from this photograph.
"""

        response = client.responses.create(
            model="gpt-4.1-mini",
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": prompt
                        },
                        {
                            "type": "input_image",
                            "image_url": (
                                "data:image/jpeg;base64,"
                                + image_base64
                            )
                        }
                    ]
                }
            ]
        )

        text = response.output_text

        result = json.loads(text)

        result["available"] = True

        return result

    except Exception as e:

        return {
            "available": False,
            "crack_detected": False,
            "severity": "Unknown",
            "risk_score": 0,
            "damage_type": "AI analysis failed",
            "location": "Unknown",
            "description": (
                "AI analysis could not be completed: "
                + str(e)
            ),
            "possible_causes": "",
            "recommendation": (
                "Perform a professional inspection."
            )
        }


# ============================================================
# PDF REPORT
# ============================================================

def create_pdf(
    inputs,
    result,
    ai_result,
    image
):

    pdf_buffer = BytesIO()

    document = SimpleDocTemplate(
        pdf_buffer,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm
    )

    styles = getSampleStyleSheet()

    story = []

    story.append(
        Paragraph(
            "STRUCTURE DOCTOR AI",
            styles["Title"]
        )
    )

    story.append(
        Paragraph(
            "Preliminary Structural Damage Screening Report",
            styles["Heading2"]
        )
    )

    story.append(
        Paragraph(
            datetime.now().strftime(
                "Assessment date: %d-%m-%Y %H:%M"
            ),
            styles["Normal"]
        )
    )

    story.append(Spacer(1, 10))

    # --------------------------------------------------------
    # IMAGE
    # --------------------------------------------------------

    image_buffer = BytesIO()

    image.save(
        image_buffer,
        format="JPEG"
    )

    image_buffer.seek(0)

    story.append(
        RLImage(
            image_buffer,
            width=160 * mm,
            height=100 * mm
        )
    )

    story.append(Spacer(1, 10))

    # --------------------------------------------------------
    # STRUCTURE INFORMATION
    # --------------------------------------------------------

    story.append(
        Paragraph(
            "Structure Information",
            styles["Heading2"]
        )
    )

    structure_data = [
        ["Parameter", "Value"],
        [
            "Structure type",
            inputs.get(
                "structure_type",
                "Unknown"
            )
        ],
        [
            "Material",
            inputs.get(
                "material",
                "Unknown"
            )
        ],
        [
            "Crack width",
            f"{inputs.get('crack_width', 0)} mm"
        ],
        [
            "Crack length",
            f"{inputs.get('crack_length', 0)} mm"
        ],
        [
            "Environment",
            inputs.get(
                "environment",
                "Unknown"
            )
        ]
    ]

    table = Table(
        structure_data,
        colWidths=[
            60 * mm,
            110 * mm
        ]
    )

    table.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.lightgrey
            ),
            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.5,
                colors.grey
            ),
            (
                "PADDING",
                (0, 0),
                (-1, -1),
                6
            )
        ])
    )

    story.append(table)

    story.append(Spacer(1, 10))

    # --------------------------------------------------------
    # AI ANALYSIS
    # --------------------------------------------------------

    story.append(
        Paragraph(
            "AI Visual Analysis",
            styles["Heading2"]
        )
    )

    story.append(
        Paragraph(
            "<b>Crack detected:</b> "
            + str(
                ai_result.get(
                    "crack_detected",
                    "Unknown"
                )
            ),
            styles["Normal"]
        )
    )

    story.append(
        Paragraph(
            "<b>Damage type:</b> "
            + str(
                ai_result.get(
                    "damage_type",
                    "Unknown"
                )
            ),
            styles["Normal"]
        )
    )

    story.append(
        Paragraph(
            "<b>Location:</b> "
            + str(
                ai_result.get(
                    "location",
                    "Unknown"
                )
            ),
            styles["Normal"]
        )
    )

    story.append(
        Paragraph(
            "<b>Visual severity:</b> "
            + str(
                ai_result.get(
                    "severity",
                    "Unknown"
                )
            ),
            styles["Normal"]
        )
    )

    story.append(
        Paragraph(
            "<b>Description:</b> "
            + str(
                ai_result.get(
                    "description",
                    ""
                )
            ),
            styles["Normal"]
        )
    )

    story.append(
        Paragraph(
            "<b>Possible causes:</b> "
            + str(
                ai_result.get(
                    "possible_causes",
                    ""
                )
            ),
            styles["Normal"]
        )
    )

    story.append(Spacer(1, 10))

    # --------------------------------------------------------
    # RISK ASSESSMENT
    # --------------------------------------------------------

    story.append(
        Paragraph(
            "Risk Assessment",
            styles["Heading2"]
        )
    )

    story.append(
        Paragraph(
            "<b>Risk score:</b> "
            + str(result["risk_score"])
            + "/100",
            styles["Normal"]
        )
    )

    story.append(
        Paragraph(
            "<b>Risk level:</b> "
            + str(result["risk_level"]),
            styles["Normal"]
        )
    )

    story.append(
        Paragraph(
            result["explanation"],
            styles["Normal"]
        )
    )

    story.append(Spacer(1, 10))

    # --------------------------------------------------------
    # RECOMMENDATIONS
    # --------------------------------------------------------

    story.append(
        Paragraph(
            "Recommended Actions",
            styles["Heading2"]
        )
    )

    for recommendation in result["recommendations"]:

        story.append(
            Paragraph(
                "• " + str(recommendation),
                styles["Normal"]
            )
        )

    story.append(Spacer(1, 12))

    # --------------------------------------------------------
    # SAFETY NOTICE
    # --------------------------------------------------------

    story.append(
        Paragraph(
            "IMPORTANT SAFETY NOTICE",
            styles["Heading2"]
        )
    )

    story.append(
        Paragraph(
            "This report is an experimental AI-assisted "
            "visual screening tool. A photograph cannot "
            "reliably determine actual structural "
            "load-bearing capacity, remaining strength, "
            "crack depth, or structural safety. This "
            "assessment must not replace inspection, "
            "testing, or certification by a qualified "
            "structural engineer.",
            styles["Normal"]
        )
    )

    document.build(story)

    pdf_buffer.seek(0)

    return pdf_buffer


# ============================================================
# APPLICATION UI
# ============================================================

st.title("🏗️ Structure Doctor AI")

st.write(
    "AI-assisted preliminary screening of visible "
    "structural damage."
)

st.warning(
    "⚠️ This tool provides preliminary visual screening "
    "only. It cannot determine actual structural load "
    "capacity or certify a structure as safe."
)


# ============================================================
# IMAGE UPLOAD
# ============================================================

st.header("📷 Upload Building Image")

uploaded_file = st.file_uploader(
    "Upload a photo showing the building, crack, "
    "or damaged area.",
    type=[
        "jpg",
        "jpeg",
        "png"
    ]
)

image = None

if uploaded_file:

    image = Image.open(
        uploaded_file
    ).convert("RGB")

    st.image(
        image,
        caption="Uploaded structural image",
        use_container_width=True
    )


# ============================================================
# STRUCTURE INFORMATION
# ============================================================

st.header("🏗️ Structure Information")

col1, col2 = st.columns(2)

with col1:

    structure_type = st.selectbox(
        "Structure type",
        [
            "Residential building",
            "Commercial building",
            "Bridge",
            "Industrial building",
            "Retaining wall",
            "Other"
        ]
    )

    material = st.selectbox(
        "Material",
        [
            "Reinforced Concrete",
            "Concrete",
            "Brick Masonry",
            "Steel",
            "Unknown"
        ]
    )


with col2:

    crack_width = st.number_input(
        "Approximate crack width (mm)",
        min_value=0.0,
        max_value=100.0,
        value=0.0,
        step=0.1
    )

    crack_length = st.number_input(
        "Approximate crack length (mm)",
        min_value=0.0,
        max_value=10000.0,
        value=0.0,
        step=10.0
    )


environment = st.selectbox(
    "Environmental condition",
    [
        "Normal",
        "Heavy rain / water leakage",
        "Damp / corrosion",
        "Earthquake exposure",
        "Flood exposure",
        "Fire exposure",
        "Landslide exposure"
    ]
)


# ============================================================
# ANALYZE BUTTON
# ============================================================

if st.button(
    "🔍 Analyze Structure",
    type="primary",
    use_container_width=True
):

    if image is None:

        st.error(
            "Please upload a building or crack image first."
        )

    else:

        inputs = {
            "structure_type": structure_type,
            "material": material,
            "crack_width": crack_width,
            "crack_length": crack_length,
            "environment": environment,
        }

        with st.spinner(
            "AI is analyzing the visible structural damage..."
        ):

            ai_result = analyze_image_with_ai(
                image,
                inputs
            )

        inputs["ai_result"] = ai_result

        result = assess_risk(
            inputs
        )

        save_assessment(
            inputs,
            result
        )

        st.session_state[
            "last_inputs"
        ] = inputs

        st.session_state[
            "last_result"
        ] = result

        st.session_state[
            "last_ai"
        ] = ai_result

        st.session_state[
            "last_image"
        ] = image


# ============================================================
# DISPLAY RESULT
# ============================================================

if "last_result" in st.session_state:

    result = st.session_state[
        "last_result"
    ]

    ai_result = st.session_state[
        "last_ai"
    ]

    st.divider()

    st.header(
        "📊 Assessment Result"
    )

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "Visual Risk Score",
            f"{result['risk_score']}/100"
        )

    with col2:

        st.metric(
            "Risk Level",
            result["risk_level"]
        )

    with col3:

        st.metric(
            "Severity",
            result["severity"]
        )


    # --------------------------------------------------------
    # AI FINDINGS
    # --------------------------------------------------------

    st.subheader(
        "🤖 AI Visual Findings"
    )

    st.write(
        "**Crack detected:** "
        + str(
            ai_result.get(
                "crack_detected",
                "Unknown"
            )
        )
    )

    st.write(
        "**Damage type:** "
        + str(
            ai_result.get(
                "damage_type",
                "Unknown"
            )
        )
    )

    st.write(
        "**Location:** "
        + str(
            ai_result.get(
                "location",
                "Unknown"
            )
        )
    )

    st.write(
        "**Severity:** "
        + str(
            ai_result.get(
                "severity",
                "Unknown"
            )
        )
    )

    st.write(
        "**Description:** "
        + str(
            ai_result.get(
                "description",
                ""
            )
        )
    )

    st.write(
        "**Possible causes:** "
        + str(
            ai_result.get(
                "possible_causes",
                ""
            )
        )
    )


    # --------------------------------------------------------
    # RECOMMENDATIONS
    # --------------------------------------------------------

    st.subheader(
        "🛠️ Recommended Actions"
    )

    for recommendation in result[
        "recommendations"
    ]:

        st.write(
            "• " + str(recommendation)
        )


    # --------------------------------------------------------
    # SAFETY OVERRIDE
    # --------------------------------------------------------

    if result[
        "safety_override"
    ]:

        st.error(
            "🚨 SAFETY OVERRIDE: Potentially dangerous "
            "structural damage was identified. Restrict "
            "access where appropriate and obtain an urgent "
            "professional structural inspection."
        )


    # --------------------------------------------------------
    # PDF REPORT
    # --------------------------------------------------------

    pdf = create_pdf(
        st.session_state["last_inputs"],
        result,
        ai_result,
        st.session_state["last_image"]
    )

    st.download_button(
        label="📄 Download Complete PDF Report",
        data=pdf,
        file_name="structure_doctor_report.pdf",
        mime="application/pdf",
        use_container_width=True
    )


# ============================================================
# ASSESSMENT HISTORY
# ============================================================

st.divider()

st.header(
    "🗃️ Assessment History"
)

conn = sqlite3.connect(
    DB_FILE
)

history = conn.execute(
    "SELECT timestamp, structure_type, material, "
    "risk_score, risk_level "
    "FROM assessments "
    "ORDER BY id DESC LIMIT 10"
).fetchall()

conn.close()


if history:

    for row in history:

        st.write(
            f"**{row[0]}** | "
            f"{row[1]} | "
            f"{row[2]} | "
            f"Score: {row[3]} | "
            f"Risk: {row[4]}"
        )

else:

    st.info(
        "No assessments yet."
    )