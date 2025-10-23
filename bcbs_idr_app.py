import streamlit as st
import pdfplumber
import re
import google.generativeai as genai
from docx import Document
from io import BytesIO
import os

# -----------------------------
# CONFIGURATION
# -----------------------------
# Direct Gemini API key (local use only)
GEMINI_API_KEY = "AIzaSyAKbtJyypvjhUii916BcqpAHeprwZWW3Dc"

# -----------------------------
# STREAMLIT FRONT END SETUP
# -----------------------------
st.set_page_config(page_title="BCBS Justification for IDR", layout="centered")
st.title("🏥 BCBS Justification for IDR Generator")
st.write("Upload EOB PDF, MRN PDF, and Prompt TXT file to generate the formatted BCBS justification document.")

# -----------------------------
# FILE UPLOADS
# -----------------------------
eob_file = st.file_uploader("📄 Upload EOB PDF", type=["pdf"])
mrn_file = st.file_uploader("🧾 Upload MRN PDF", type=["pdf"])
prompt_file = st.file_uploader("📝 Upload MRN Summary Prompt (TXT)", type=["txt"])

# -----------------------------
# HELPER FUNCTIONS
# -----------------------------
def extract_text_from_pdf(uploaded_file):
    """Extract full text from a PDF using pdfplumber"""
    text = ""
    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text

def find_field(pattern, text, label):
    """Find a single regex match or return placeholder"""
    match = re.search(pattern, text)
    return match.group(1).strip() if match else f"{label} not found"

def extract_ranked_hcpcs(eob_text):
    """Extract HCPCS codes in the order they appear in the EOB"""
    codes = re.findall(r"\b(\d{4,5})\b", eob_text)
    ranked_codes = []
    for code in codes:
        if re.match(r"^[789]\d{3,4}$", code) and code not in ranked_codes:
            ranked_codes.append(code)
    return ranked_codes

def generate_mrn_summary(prompt_text, mrn_text):
    """Generate structured MRN summary using Gemini 2.5 Flash"""
    genai.configure(api_key=GEMINI_API_KEY.strip())
    model = genai.GenerativeModel("gemini-2.5-flash")
    combined_prompt = (
        f"{prompt_text}\n\n---\n\n{mrn_text}\n\n"
        "Format output with clear Markdown rich text formatting: "
        "use **bold** for section headings, line breaks for clarity, "
        "and structure it like this:\n\n"
        "**Age:** 32 years\n"
        "**Date(s) of Service or Visit Timeline:**\nArrival Time: ...\nTriage Time: ...\n\n"
        "**Presenting Symptoms:**\n...\n\n"
        "**Notable clinical findings or diagnosis:**\n...\n\n"
        "**Clinical complexity level:** ...\n"
        "**Acuity level:** ...\n"
        "**Any relevant follow-up plans or referrals:** ..."
    )
    response = model.generate_content(combined_prompt)
    return response.text.strip()

def add_markdown_to_docx(doc, markdown_text):
    """Render Markdown-style bold (**text**) inside Word document"""
    for line in markdown_text.split("\n"):
        if not line.strip():
            doc.add_paragraph("")
            continue

        # Split the line by markdown bold markers (**bold**)
        parts = re.split(r"(\*\*.*?\*\*)", line)
        para = doc.add_paragraph()
        for part in parts:
            if part.startswith("**") and part.endswith("**"):
                run = para.add_run(part.strip("**"))
                run.bold = True
            else:
                para.add_run(part)

def create_docx(date, hcpcs, drg, mrn_summary):
    """Create Word document output with bold formatting"""
    doc = Document()
    doc.add_heading("BCBS Justification for IDR", level=1)

    doc.add_heading("Claim Information", level=2)
    doc.add_paragraph(f"Date of Service: {date}")
    doc.add_paragraph(
        f"HCPCS Codes (7/8/9 only, ranked as per EOB): {', '.join(hcpcs) if hcpcs else 'None found'}"
    )
    doc.add_paragraph(f"DRG Code: {drg}")

    doc.add_heading("Patient Acuity & Complexity of Care", level=2)
    add_markdown_to_docx(doc, mrn_summary)

    output = BytesIO()
    doc.save(output)
    output.seek(0)
    return output

def create_text_output(date, hcpcs, drg, mrn_summary):
    """Return rich text formatted justification for display"""
    text = (
        f"**BCBS Justification for IDR**\n\n"
        f"**Claim Information**\n"
        f"**Date of Service:** {date}\n"
        f"**HCPCS Codes (7/8/9 only, ranked as per EOB):** {', '.join(hcpcs) if hcpcs else 'None found'}\n"
        f"**DRG Code:** {drg}\n\n"
        f"**Patient Acuity & Complexity of Care**\n{mrn_summary}\n"
    )
    return text

# -----------------------------
# MAIN WORKFLOW
# -----------------------------
if st.button("🚀 Run Automation"):
    if not (eob_file and mrn_file and prompt_file):
        st.error("Please upload all required files.")
    else:
        with st.spinner("Processing... Please wait..."):
            try:
                # Extract text
                eob_text = extract_text_from_pdf(eob_file)
                mrn_text = extract_text_from_pdf(mrn_file)
                prompt_text = prompt_file.read().decode("utf-8")

                # Parse fields
                date_of_service = find_field(
                    r"Service Dates\s+(\d{2}/\d{2}/\d{4})", eob_text, "Date"
                )
                hcpcs_codes = extract_ranked_hcpcs(eob_text)
                drg_code = find_field(r"DRG Code\s+(\d+)", eob_text, "DRG Code")

                # Generate formatted MRN summary
                mrn_summary = generate_mrn_summary(prompt_text, mrn_text)

                # Create outputs
                output_doc = create_docx(
                    date_of_service, hcpcs_codes, drg_code, mrn_summary
                )
                text_output = create_text_output(
                    date_of_service, hcpcs_codes, drg_code, mrn_summary
                )

                st.success("✅ Automation complete!")

                # Render rich formatted Markdown text
                st.subheader("📜 Generated BCBS Justification Letter")
                st.markdown(
                    f"<div style='white-space: pre-wrap; font-size:16px;'>{text_output}</div>",
                    unsafe_allow_html=True,
                )

                # Provide download option
                st.download_button(
                    label="📥 Download as Word Document (.docx)",
                    data=output_doc,
                    file_name="BCBS_Justification_for_IDR.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )

            except Exception as e:
                st.error(f"❌ Error occurred: {str(e)}")
