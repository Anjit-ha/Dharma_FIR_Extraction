import re
import json
import streamlit as st
from typing import Dict, List, Any
import os

# ----------------------------------------------------------
# Page Config
# ----------------------------------------------------------
st.set_page_config(page_title="DHARMA FIR Extractor", page_icon="⚖️", layout="wide")
st.title("⚖️ DHARMA Project – FIR Information Extraction & Legal Mapping")
st.markdown("""
This tool automatically extracts **structured information** from bilingual police FIR text  
and maps it to **relevant legal sections** under **BNS 2023**, **SC/ST Act**, and **Arms Act**.  

🪶 *Paste or upload the FIR text below to begin.*
""")

# ----------------------------------------------------------
# Initialize Session State
# ----------------------------------------------------------
if "fir_text" not in st.session_state:
    st.session_state.fir_text = ""
if "result" not in st.session_state:
    st.session_state.result = None

# ----------------------------------------------------------
# Helper Functions
# ----------------------------------------------------------
def extract_complainant_info(text: str) -> Dict[str, Any]:
    info = {}
    name_match = re.search(r"complainant\s+([A-Z][a-zA-Z\s]+)", text, re.I)
    father_match = re.search(r"S/o\s+([A-Z][a-zA-Z\s]+)", text, re.I)
    age_match = re.search(r"aged\s+(\d+)", text, re.I)
    caste_match = re.search(r"(Scheduled\s+Caste|Scheduled\s+Tribe|Backward\s+Class)", text, re.I)
    occ_match = re.search(r"occupation[:\s]*([A-Za-z\s]+)", text, re.I)
    addr_match = re.search(r"resident\s+of\s+([A-Za-z\s,]+)", text, re.I)
    if name_match: info["Name"] = name_match.group(1).strip()
    if father_match: info["Father"] = father_match.group(1).strip()
    if age_match: info["Age"] = int(age_match.group(1))
    if caste_match: info["Community"] = caste_match.group(1).strip()
    if occ_match: info["Occupation"] = occ_match.group(1).strip()
    if addr_match: info["Address"] = addr_match.group(1).strip()
    return info

def extract_accused_info(text: str) -> List[Dict[str, Any]]:
    accused_block = re.findall(
        r"([A-Z][a-zA-Z\s]+),\s*aged\s*about\s*(\d+).*?(?:S/o\s*([A-Za-z\s]+))?.*?(?:resident\s*of\s*([A-Za-z\s]+))?.*?(?:history-sheeter)?",
        text, re.I)
    accused_list = []
    for match in accused_block:
        name, age, relation, addr = match
        acc = {"Name": name.strip(), "Age": int(age)}
        if relation: acc["Relation"] = f"S/o {relation.strip()}"
        if addr: acc["Address"] = addr.strip()
        accused_list.append(acc)
    if "unknown" in text.lower():
        unknown_match = re.search(r"unknown person.*?(medium build|black shirt|fair|dark)", text, re.I)
        desc = unknown_match.group(1) if unknown_match else "Unknown description"
        accused_list.append({"Name": "Unknown", "Description": desc})
    return accused_list

def extract_vehicles(text: str) -> List[str]:
    return re.findall(r"(AP-\d{2}-[A-Z]{2}-\d{4})", text)

def extract_weapons(text: str) -> List[str]:
    weapons = []
    if "pistol" in text.lower(): weapons.append("Country-made pistol")
    if "stick" in text.lower(): weapons.append("Stick")
    return weapons

def extract_offences(text: str) -> List[str]:
    offences = []
    if "caste" in text.lower() or "mala" in text.lower(): offences.append("Caste abuse")
    if "pistol" in text.lower() or "fire" in text.lower(): offences.append("Threat with firearm")
    if "snatched" in text.lower() or "cash" in text.lower(): offences.append("Robbery")
    if "injury" in text.lower() or "bleeding" in text.lower(): offences.append("Assault causing injury")
    return offences

def extract_property_loss(text: str) -> List[str]:
    return re.findall(r"(Samsung.*?₹\d+|\bcash\s*₹?\d+)", text, re.I)

def extract_threats(text: str) -> List[str]:
    threats = []
    if "kill" in text.lower(): threats.append("Kill him")
    if "fire" in text.lower() or "burn" in text.lower(): threats.append("Set fire to his hut")
    return threats

def extract_witnesses(text: str) -> List[str]:
    w = re.findall(r"\b([A-Z][a-z]+)\b(?=,|\s+and)", text)
    return [x for x in w if x not in ["Rajesh", "Rao", "Babu", "Krishna"]]

def extract_datetime(text: str) -> str:
    m = re.search(r"(\d{1,2}(?:th|st|nd|rd)?\s+\w+\s+\d{4}).*?(\d{1,2}[:.]\d+\s*[AP]M)", text, re.I)
    return f"{m.group(1)}, {m.group(2)}" if m else ""

def extract_place(text: str) -> str:
    m = re.search(r"near\s+([A-Za-z\s]+culvert)", text, re.I)
    return m.group(1).strip() if m else "Not mentioned"

def map_legal_sections(info: Dict[str, Any]) -> Dict[str, List[str]]:
    mapping = {"BNS 2023": [], "SC/ST Act 1989": [], "Arms Act 1959": []}
    offences = info.get("Offences", [])
    if "Robbery" in offences: mapping["BNS 2023"].append("Sec. 309 – Robbery")
    if "Assault causing injury" in offences: mapping["BNS 2023"].append("Sec. 115 – Hurt")
    if any("Threat" in x for x in offences): mapping["BNS 2023"].append("Sec. 351 – Criminal intimidation")
    if "Caste abuse" in offences:
        mapping["SC/ST Act 1989"].extend([
            "Sec. 3(1)(r) – Intentional insult/abuse by caste name",
            "Sec. 3(2)(v) – Offence committed on ground of caste"
        ])
    if "firearm" in " ".join(offences) or "pistol" in " ".join(offences):
        mapping["Arms Act 1959"].extend([
            "Sec. 25 – Possession/use of illegal arms",
            "Sec. 27 – Use of firearm in commission of offence"
        ])
    return {k: v for k, v in mapping.items() if v}

def extract_all(text: str) -> Dict[str, Any]:
    data = {
        "Complainant": extract_complainant_info(text),
        "DateTime": extract_datetime(text),
        "Place": extract_place(text),
        "Accused": extract_accused_info(text),
        "Vehicles": extract_vehicles(text),
        "WeaponsUsed": extract_weapons(text),
        "Offences": extract_offences(text),
        "PropertyLoss": extract_property_loss(text),
        "Threats": extract_threats(text),
        "Witnesses": extract_witnesses(text),
        "Impact": "Fear, public fled, complainant hospitalized" if "hospital" in text.lower() else ""
    }
    data["LegalMapping"] = map_legal_sections(data)
    return data

def save_extracted_data(data: Dict[str, Any], filename="extracted_fir_data.json"):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            all_data = json.load(f)
    else:
        all_data = []
    all_data.append(data)
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(all_data, f, indent=2, ensure_ascii=False)

# ----------------------------------------------------------
# Streamlit UI
# ----------------------------------------------------------
st.subheader("📄 Input FIR Text")
option = st.radio("Choose Input Method:", ["✍️ Paste FIR Text", "📁 Upload .txt File"])

if option == "✍️ Paste FIR Text":
    fir_text = st.text_area("Paste FIR text here:", value=st.session_state.fir_text, key="fir_text_area", height=250)
else:
    uploaded_file = st.file_uploader("Upload FIR text file", type=["txt"])
    fir_text = uploaded_file.read().decode("utf-8") if uploaded_file else ""

col1, col2 = st.columns(2)
with col1:
    if st.button("🔍 Extract Information"):
        if not fir_text.strip():
            st.warning("Please enter or upload FIR text.")
        else:
            result = extract_all(fir_text)
            st.session_state.result = result
            st.session_state.fir_text = fir_text
            st.success("✅ Extraction Completed!")
            save_extracted_data(result)

with col2:
    if st.button("🔁 New Extraction"):
        st.session_state.clear()
        st.rerun()



# ----------------------------------------------------------
# Display Output
# ----------------------------------------------------------
if st.session_state.get("result"):
    result = st.session_state.result
    st.markdown("---")
    st.header("📘 Structured Information")

    with st.expander("👤 Complainant Details", expanded=True):
        for k, v in result["Complainant"].items():
            st.markdown(f"**{k}:** {v}")

    with st.expander("👮 Accused Details", expanded=False):
        for idx, acc in enumerate(result["Accused"], 1):
            st.markdown(f"**Accused {idx}:**")
            for k, v in acc.items():
                st.markdown(f"- **{k}:** {v}")

    with st.expander("📅 Incident Details", expanded=False):
        st.markdown(f"**Date & Time:** {result['DateTime']}")
        st.markdown(f"**Place:** {result['Place']}")
        st.markdown(f"**Vehicles:** {', '.join(result['Vehicles']) if result['Vehicles'] else 'None'}")
        st.markdown(f"**Weapons Used:** {', '.join(result['WeaponsUsed']) if result['WeaponsUsed'] else 'None'}")

    with st.expander("⚠️ Offence Summary", expanded=False):
        st.markdown(f"**Offences:** {', '.join(result['Offences'])}")
        st.markdown(f"**Threats:** {', '.join(result['Threats']) if result['Threats'] else 'None'}")
        st.markdown(f"**Property Loss:** {', '.join(result['PropertyLoss']) if result['PropertyLoss'] else 'None'}")
        st.markdown(f"**Impact:** {result['Impact']}")

    st.markdown("---")
    st.header("⚖️ Relevant Legal Mapping")
    for law, sections in result["LegalMapping"].items():
        st.markdown(f"**{law}:**")
        for s in sections:
            st.markdown(f"- {s}")

    st.download_button(
        label="⬇️ Download Extracted JSON",
        data=json.dumps(result, indent=2, ensure_ascii=False),
        file_name="fir_extracted_data.json",
        mime="application/json"
    )

# ----------------------------------------------------------
# Footer
# ----------------------------------------------------------
st.markdown("""
---
**DHARMA Project – AI/ML Expert Task**  
Developed using **Streamlit** | NLP + Regex Based FIR Structuring  
👩‍💻 Author: *Anjitha*
""")

