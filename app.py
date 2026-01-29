import streamlit as st
from PIL import Image
import pytesseract
import pdfplumber
from docx import Document
from deep_translator import GoogleTranslator
from groq import Groq
from dotenv import load_dotenv
import os, re, tempfile
from gtts import gTTS

# ---------------- LOAD ENV ----------------
#load_dotenv()
#groq_client = Groq(api_key="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")

# ---------------- LOAD ENV ----------------
load_dotenv()
# This pulls the key from your hidden .env file instead of showing it in the code
api_key = os.getenv("GROQ_API_KEY") 
groq_client = Groq(api_key=api_key)

# ---------------- PAGE CONFIG ----------------
st.set_page_config(page_title="BenefitBot", page_icon="🎯", layout="wide")

# ---------------- SESSION STATE FOR AUTH ----------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_db" not in st.session_state:
    st.session_state.user_db = {} 

# ---------------- CUSTOM STYLING ----------------
def apply_custom_styles(dark_mode=False):
    if dark_mode:
        bg_color = "#0f172a"
        text_css = """
            .stMarkdown p, label, .stRadio div { color: white !important; font-weight: 500; }
            .purple-heading { color: #a78bfa !important; text-align: center; font-weight: 800; font-size: 32px; margin-bottom: 25px; }
            div[data-baseweb="input"] { background-color: #1e293b !important; border: 1px solid #475569 !important; }
            input { color: white !important; }
        """
    else:
        bg_color = "#fff5f7"
        text_css = ""

    st.markdown(f"""
    <style>
        .stApp {{ background-color: {bg_color}; }}
        {text_css}
        .welcome-container {{
            background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 100%);
            padding: 40px 20px; border-radius: 20px; text-align: center; margin: 10px auto 20px auto; max-width: 900px; box-shadow: 0 10px 30px rgba(0,0,0,0.3); color: white;
        }}
        .team-container {{
            background: linear-gradient(135deg, #ffffff 0%, #e0f7fa 100%);
            padding: 30px; border-radius: 20px; border-left: 8px solid #00acc1; margin: 0 auto 30px auto; max-width: 900px; box-shadow: 0 15px 35px rgba(0, 172, 193, 0.15); 
        }}
        .team-p {{ font-size: 1.15rem; text-align: center; font-weight: 500; margin-bottom: 25px; color: #000000 !important; line-height: 1.6; }}
        .team-left b, .team-right b {{ color: #064e3b !important; font-size: 1.1rem; letter-spacing: 0.5px; }}
        .team-flex {{ display: flex; justify-content: space-between; align-items: flex-end; padding: 0 15px; }}
        .team-left {{ text-align: left; line-height: 1.8; }}
        .team-right {{ text-align: right; line-height: 1.8; }}
        .college-name {{ font-weight: bold; color: #000000; margin-top: 8px; font-size: 1rem; opacity: 0.9; }}
        .clean-point {{ font-weight: 500; color: #1e293b; margin-bottom: 10px; display: block; }}
        .welcome-title {{ color: #ffffff !important; font-size: 40px; font-weight: 800; margin-bottom: 5px; }}
        .welcome-subtitle {{ color: #bfdbfe !important; font-size: 20px; margin-bottom: 15px; }}
        .welcome-text {{ font-size: 1.05rem; max-width: 700px; margin: 0 auto !important; color: #cbd5e1 !important; line-height: 1.5; text-align: center !important; display: block; }}
        .lavender-heading {{ color: #7c3aed !important; text-align: center !important; font-weight: 700 !important; margin-top: 20px !important; margin-bottom: 20px !important; font-size: 28px !important; }}
        .chat-heading {{ color: #7c3aed !important; text-align: left !important; font-weight: 700 !important; margin-top: 30px !important; margin-bottom: 10px !important; font-size: 24px !important; }}
        
        [data-testid="stVerticalBlockBorderWrapper"] {{
            background-color: #ffffff; border: 1px solid #fbcfe8 !important; padding: 25px; border-radius: 15px;
        }}
        div.stButton > button:first-child {{ background-color: #28a745; color: white; border-radius: 8px; border: none; font-weight: bold; }}
    </style>
    """, unsafe_allow_html=True)

# ---------------- HELPER FUNCTIONS ----------------
def format_indian_currency(number_str):
    if not number_str: return ""
    number_str = re.sub(r"[^\d]", "", number_str)
    if not number_str: return ""
    if len(number_str) <= 3: return number_str
    last_three = number_str[-3:]; remaining = number_str[:-3]
    remaining_with_commas = ""
    while len(remaining) > 2:
        remaining_with_commas = "," + remaining[-2:] + remaining_with_commas
        remaining = remaining[:-2]
    return remaining + remaining_with_commas + "," + last_three

def clean_text(text):
    text = re.sub(r"\(cid:\d+\)", "", text); text = re.sub(r"\s{2,}", " ", text)
    return text.strip()

def extract_heading(text):
    lines = [l.strip() for l in text.split("\n") if len(l.strip()) > 5]
    return lines[0] if lines else "Scheme / Scholarship Document"

def summarize_points(text):
    important = ["eligibility", "benefit", "amount", "age", "income", "caste", "apply", "scheme", "scholarship"]
    sentences = re.split(r"\.\s+|\n", text)
    bullets = []
    for s in sentences:
        s_clean = s.strip().replace("..", "").replace("•", "").strip()
        if 15 < len(s_clean) < 300 and any(k in s_clean.lower() for k in important):
            bullets.append(s_clean)
    return bullets[:10]

def recommend_schemes(p):
    r = []
    occ, edu, age, gen, hos, inc = p.get("occupation",""), p.get("education",""), p.get("age",0), p.get("gender","male"), p.get("hostel",False), p.get("income",0)
    caste = p.get("caste", "")

    # Welfare Logic
    if occ == "student" and edu in ["school", "intermediate", "diploma"] and 6 <= age <= 18 and inc <= 144000:
        r.append(("Talliki Vandanam", "https://pmschemehub.in/thalliki-vandanam-scheme/", "Student aged 6–18"))
    if occ == "farmer" and age >= 18 and inc <= 200000:
        r.append(("Annadata Sukhibhava Scheme", "https://annadathasukhibhava.ap.gov.in", "Farmer aged 18+"))
    if occ == "senior" and age >= 60 and inc <= 500000:
        r.append(("Dr NTR Vaidya Seva", "https://navasakam.ap.gov.in", "Senior citizen aged 60+"))
    if occ == "single women (married)" and age >= 18 and gen == "female" and inc <= 300000:
        r.append(("NTR Bharosa Pension Scheme (Single Women Pension)", "https://navasakam.ap.gov.in", "Married single woman aged 18+"))
    if occ == "worker" and age >= 18 and inc <= 300000:
        r.append(("Mana Illu Mana Gouravam", "https://manaillumanagouravam.ap.gov.in", "Worker aged 18+")) 
    if occ == "disable" and age >= 18 and inc <= 100000:
        r.append(("NTR Bharosa", "https://navasakam.ap.gov.in", "Person with disability aged 18+"))
    if occ == "widow" and age >= 18 and gen == "female" and inc <= 100000:
        r.append(("NTR Bharosa", "https://navasakam.ap.gov.in", "Widow aged 18+"))   
    if occ == "single women (unmarried)" and age >= 18 and gen == "female" and inc <= 300000:
        r.append(("NTR Bharosa Pension Scheme (Single Women Pension)", "https://navasakam.ap.gov.in", "Unmarried single woman aged 18+"))

    # Scholarship Logic
    if occ == "student":
        if edu in ["btech", "degree"] and 18 <= age <= 22 and inc <= 120000:
            r.append(("Post Matric Scholarship – Tuition Fee (Jnanabhumi)", "https://jnanabhumi.ap.gov.in", "Degree/BTech Student RTF"))
        
        # RESTORED POST MATRIC MTF LOGIC
        if edu in ["degree", "intermediate"] and 18 <= age <= 22 and inc < 100000 and hos:
            r.append(("Post Matric Scholarship – Maintenance Fee (Jnanabhumi)", "https://jnanabhumi.ap.gov.in", "Hostel student (Degree/Inter) aged 18-22"))

        if edu == "school" and 6 <= age <= 16 and caste in ["BC", "SC", "ST", "Minority"] and inc <= 200000:
            r.append(("Pre Matric Scholarship", "https://jnanabhumi.ap.gov.in", "School student (BC/SC/ST/Minority)"))
        if edu == "degree" and caste == "Minority" and inc <= 250000:
            r.append(("Minority Scholarship", "https://scholarships.gov.in", "Minority degree students"))
        if edu in ["btech", "b.e", "diploma"] and gen == "female" and 18 <= age <= 22 and caste in ["BC", "SC", "ST"] and inc <= 800000:
            r.append(("AICTE Pragati Scholarship", "https://www.aicte-india.org/schemes/students-development-schemes", "Female Technical Students"))
        if edu in ["degree", "diploma"] and 15 <= age <= 22 and caste in ["BC", "SC", "ST"] and inc <= 800000:
            r.append(("AICTE Saksham Scholarship", "https://www.aicte-india.org/schemes/students-development-schemes", "Differently-abled technical students"))
        if edu in ["pg"] and gen == "female" and 26 <= age <= 35 and caste in ["OC", "BC", "SC", "ST"] and inc <= 600000:
            r.append(("NTR Videshi Vidyadharana", "https://scholarshipbuddyhub.com", "Female Overseas PG Students"))

    return r

# ---------------- LOGIN / SIGNUP PAGE ----------------
if not st.session_state.logged_in:
    apply_custom_styles(dark_mode=True)
    _, center_col, _ = st.columns([1.5, 1, 1.5])
    with center_col:
        st.markdown('<div style="height: 100px;"></div>', unsafe_allow_html=True)
        st.markdown('<div class="purple-heading">Access to the BenefitBot</div>', unsafe_allow_html=True)
        auth_mode = st.radio("Choose Action", ["Login", "Sign Up"], horizontal=True)
        email = st.text_input("Email Address")
        password = st.text_input("Password", type="password")
        if auth_mode == "Sign Up":
            if st.button("Create Account", use_container_width=True):
                if email and password:
                    st.session_state.user_db[email] = password
                    st.success("Account created! You can now Login.")
        else:
            if st.button("Login", use_container_width=True):
                if email in st.session_state.user_db and st.session_state.user_db[email] == password:
                    st.session_state.logged_in = True
                    st.rerun()
                else: st.error("Invalid credentials.")
    st.stop()

# ---------------- MAIN APP (POST-LOGIN) ----------------
apply_custom_styles(dark_mode=False)

# --- Logout Button in Top Right Corner ---
col_main, col_logout = st.columns([9, 1])
with col_logout:
    if st.button("🔓 Logout"):
        st.session_state.logged_in = False
        st.rerun()

tab_home, tab1, tab2 = st.tabs(["🏠 Home", "🧑 Applicant Details", "📄 AI Document Assistant"])

with tab_home:
    st.markdown("""<div class="welcome-container"><div class="welcome-title">🎯 BenefitBot</div><div class="welcome-subtitle">AI-Powered Eligibility Portal for Andhra Pradesh Welfare</div><div class="welcome-text">Your one-stop destination to discover government welfare schemes. </div></div>""", unsafe_allow_html=True)
    
    # RESTORED ORIGINAL TEAM BOX CODE
    st.markdown("""
        <div class="team-container">
            <p class="team-p">We are 3rd-year BTech students at KIETW. We are part of the Artificial Intelligence Career for Women program, a CSR by Microsoft and SAP, implemented by the Edunet Foundation.</p>
            <div class="team-flex">
                <div class="team-left">
                    <b>Pravallika Somisetti</b><br>
                    <b>Jyothi Chikkala</b><br>
                    <b>Mythili Nukala</b><br>
                    <b>Visalya Sabbisetti</b><br>
                    <div class="college-name">Kakinada Institute of Engineering and Technology for Women</div>
                </div>
                <div class="team-right">
                    <b>Abdul Aziz Md</b><br>
                    <b>Master Trainer</b><br>
                    <div class="college-name">Microsoft and SAP, Edunet Foundation</div>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)

# ================= TAB 1 =================
with tab1:
    st.markdown('<div class="lavender-heading">🧑 Personal Profile</div>', unsafe_allow_html=True)
    col_l, col_c, col_r = st.columns([1, 4, 1])
    with col_c:
        with st.container(border=True):
            occupation = st.selectbox("Occupation", ["student", "farmer", "worker", "widow", "senior", "disable", "single women (married)", "single women (unmarried)"])
            education = "none"
            if occupation == "student":
                education = st.selectbox("Education", ["school", "intermediate", "diploma", "btech", "degree", "pg", "b.e"])
            
            # Dynamic Age Logic
            age_min, age_max, age_val = 0, 100, 18
            if occupation == "student":
                if education == "school": age_min, age_max, age_val = 6, 16, 10
                elif education == "intermediate": age_min, age_max, age_val = 16, 18, 17
                elif education == "diploma": age_min, age_max, age_val = 16, 19, 17
                elif education in ["btech", "degree"]: age_min, age_max, age_val = 18, 22, 20
                elif education in ["pg", "b.e"]: age_min, age_max, age_val = 22, 24, 23
            elif occupation in ["farmer", "worker", "widow"]: age_min, age_max, age_val = 18, 100, 30
            elif occupation == "senior": age_min, age_max, age_val = 60, 100, 65
            elif occupation in ["single women (married)", "single women (unmarried)"]: age_min, age_max, age_val = 18, 100, 35

            age = st.slider("Select Age", min_value=age_min, max_value=age_max, value=age_val)
            gender = "female" if occupation in ["widow", "single women (married)", "single women (unmarried)"] else st.selectbox("Gender", ["male", "female"])
            caste = st.selectbox("Caste", ["OC", "BC", "SC", "ST", "Minority"])
            hostel = st.checkbox("Staying in Hostel?") if occupation == "student" else False

            if 'income_display' not in st.session_state: st.session_state.income_display = ""
            inc_label = "Guardian's Annual Income (₹)" if occupation == "student" else "Annual Income (₹)"
            income_raw = st.text_input(inc_label, value=st.session_state.income_display)
            fmt = format_indian_currency(income_raw)
            if fmt != income_raw: st.session_state.income_display = fmt; st.rerun()

            if st.button("🔍 Check Eligibility", use_container_width=True):
                clean_inc = int(re.sub(r"[^\d]", "", st.session_state.income_display)) if st.session_state.income_display else 0
                res = recommend_schemes({"occupation": occupation, "education": education, "age": age, "gender": gender, "hostel": hostel, "income": clean_inc, "caste": caste})
                if res:
                    st.success("Eligible Schemes Found 🎉")
                    for s in res: st.markdown(f"**{s[0]}** \n{s[2]}  \n[Apply here]({s[1]})")
                else: st.warning("No eligible schemes found.")

# ================= TAB 2 =================
with tab2:
    st.markdown('<div class="lavender-heading">📄 AI Document Intelligence</div>', unsafe_allow_html=True)
    uploaded_file = st.file_uploader("Upload Scheme Document", type=["pdf", "docx", "png", "jpg", "jpeg"])
    valid_schemes = ["talliki vandanam", "amma vodi", "dr ntr vaidya seva", "annadata sukhibhava", "mana illu", "ntr bharosa", "tuition fee", "maintenance fee", "jnanabhumi", "pre matric", "minority scholarship", "pragati scholarship", "saksham scholarship", "videshi vidyadharana"]

    if uploaded_file:
        with st.spinner("Analyzing..."):
            text = ""
            if uploaded_file.type == "application/pdf":
                with pdfplumber.open(uploaded_file) as pdf:
                    for page in pdf.pages: text += page.extract_text() or ""
            elif uploaded_file.type.endswith("document"):
                doc = Document(uploaded_file)
                for p in doc.paragraphs: text += p.text + "\n"
            else: text = pytesseract.image_to_string(Image.open(uploaded_file))
            text = clean_text(text)

        if not any(s in text.lower() for s in valid_schemes):
            st.error("⚠️ Please upload the current ap govt schemes/scholarships documents.")
            st.session_state.doc_text = None
        else:
            st.session_state.doc_text = text
            st.markdown(f"### 📌 {extract_heading(text)}")
            bullets = summarize_points(text)
            for b in bullets: st.markdown(f'<span class="clean-point">➡ {b}</span>', unsafe_allow_html=True)
            tts_en = gTTS(text=" ".join(bullets), lang='en')
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f: tts_en.save(f.name); st.audio(f.name)
            st.divider(); st.markdown("### 🌐 ముఖ్యమైన అంశాలు (Telugu)")
            try:
                trans = GoogleTranslator(source='auto', target='te')
                bullets_te = [trans.translate(b) for b in bullets]
                for b in bullets_te: st.markdown(f'<span class="clean-point">➡ {b}</span>', unsafe_allow_html=True)
                tts_te = gTTS(text=" ".join(bullets_te), lang='te')
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f_te:
                    tts_te.save(f_te.name); st.audio(f_te.name)
            except: st.warning("⚠️ Translation connection timed out.")

    st.divider(); st.markdown('<div class="chat-heading">🤖 BenefitBot Chat</div>', unsafe_allow_html=True)
    if "chat_history" not in st.session_state: st.session_state.chat_history = []
    chat_container = st.container()
    with chat_container:
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]): st.markdown(msg["content"])
    user_q = st.chat_input("Ask about the document...")
    if user_q:
        st.session_state.chat_history.append({"role": "user", "content": user_q})
        if st.session_state.get("doc_text"):
            res = groq_client.chat.completions.create(model="llama-3.1-8b-instant", messages=[{"role": "system", "content": "Answer ONLY based on text."}, {"role": "user", "content": f"Text: {st.session_state.doc_text}\nQ: {user_q}"}])
            answer = res.choices[0].message.content
        else: answer = "Please upload a valid document first!"
        st.session_state.chat_history.append({"role": "assistant", "content": answer}); st.rerun()

st.divider(); st.markdown("<p style='text-align: center; color: #64748b;'>© 2026 BenefitBot | AP Government AI Assistant Portal</p>", unsafe_allow_html=True)