import streamlit as st
import pandas as pd
import datetime
import base64
import random
from copy import deepcopy

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(page_title="VPS Timetable Manager", page_icon="🏫", layout="wide")

# ============================================================
# CONSTANTS
# ============================================================

DAYS_9_10 = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
DAYS_8    = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

SLOTS = {
    "regular":  ["P1","P2","P3","P4","P5","P6","P7","P8","P9"],
    "saturday": ["P1","P2","P3","P4","P5","P6"],
    "zero":     ["P0","P1","P2","P3","P4","P5","P6","P7","P8","P9"],
}

TIMES = {
    "regular": {
        "P1":"8:30-9:10","P2":"9:10-9:50","P3":"9:50-10:30",
        "P4":"10:40-11:20","P5":"11:20-12:00","P6":"12:00-12:40",
        "P7":"1:10-1:50","P8":"1:50-2:30","P9":"2:30-3:10",
    },
    "saturday": {
        "P1":"9:10-9:50","P2":"9:50-10:30",
        "P3":"10:40-11:20","P4":"11:20-12:00",
        "P5":"12:00-12:40","P6":"12:40-1:10",
    },
    "zero": {
        "P0":"8:30-9:10","P1":"9:10-9:45","P2":"9:45-10:20",
        "P3":"10:30-11:05","P4":"11:05-11:40","P5":"11:40-12:15",
        "P6":"12:15-12:50","P7":"1:20-1:55","P8":"1:55-2:30","P9":"2:30-3:10",
    },
}

POST_LUNCH = {"P7","P8","P9"}
MORNING    = {"P1","P2","P3"}

ASSEMBLY_DAY   = {"8":"Friday",    "9":"Thursday",  "10":"Tuesday"}
CLASS_TEST_DAY = {"8":"Wednesday", "9":"Wednesday", "10":"Monday"}

NO_SUB_ROLES      = {"PRINCIPAL","VICE PRINCIPAL","LEVEL COORDINATOR"}
SUB_COORD_MAX_WK  = 3
REGULAR_MAX_LOAD  = 7

PE_BLOCKED_SUBS = {"P1","P7"}
SPECIAL_IDS = {"CLASSTCHR","SCILAB","COSCHO"}

SUBJ_COLOR = {
    "Mathematics":"#FFB3B3","English":"#B3E5FC","Kannada":"#B3F0E0",
    "Hindi":"#C8E6C9","Sanskrit":"#FFF9C4","Physics":"#E1BEE7",
    "Chemistry":"#FFF59D","Biology":"#DCEDC8","Social Science":"#FFCCBC",
    "History":"#D7CCC8","Geography":"#B3E5FC","Political Science":"#F8BBD9",
    "Economics":"#FFE0B2","Science Lab":"#CE93D8","AI":"#80DEEA",
    "Computer Science":"#90CAF9","Yoga/HeyMath":"#FFD54F","Library":"#E0E0E0",
    "Art":"#F48FB1","Art/Co-Scholastic":"#FFAB91","PE":"#A5D6A7",
    "Sports":"#A5D6A7","GK":"#F5DEB3","STEM":"#B39DDB",
    "Assembly":"#B0BEC5","Class Test":"#FFCC80","Co-Scholastic":"#FFCCBC",
    "PMS":"#E0F7FA","CT to Take":"#F1F8E9",
    "Elements of Business":"#FCE4EC","Study Skills":"#E8F5E9",
    "Music":"#FFF3E0","Dance":"#FCE4EC",
}

def subj_color(subj):
    for k, v in SUBJ_COLOR.items():
        if k.lower() in subj.lower():
            return v
    return "#F5F5F5"

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_slots(class_num, day):
    if class_num in (9, 10):
        return SLOTS["saturday"] if day == "Saturday" else SLOTS["regular"]
    else:
        return SLOTS["zero"] if day in ("Monday","Wednesday") else SLOTS["regular"]

def get_time(class_num, day, period):
    if class_num in (9,10) and day == "Saturday":
        return TIMES["saturday"].get(period,"")
    elif class_num == 8 and day in ("Monday","Wednesday"):
        return TIMES["zero"].get(period,"")
    else:
        return TIMES["regular"].get(period,"")

def get_days(class_num):
    return DAYS_8 if class_num == 8 else DAYS_9_10

def teacher_name(tid, teachers_df):
    if tid in SPECIAL_IDS or "|" in str(tid):
        return tid
    if teachers_df is None or teachers_df.empty:
        return tid
    row = teachers_df[teachers_df["Teacher_ID"] == tid]
    return row.iloc[0]["Teacher_Name"] if not row.empty else tid

def teacher_info(tid, teachers_df):
    if teachers_df is None or teachers_df.empty:
        return {"role":"REGULAR","teaches_ms":"No","vacant":"No","name":tid}
    row = teachers_df[teachers_df["Teacher_ID"] == tid]
    if row.empty:
        return {"role":"REGULAR","teaches_ms":"No","vacant":"No","name":tid}
    r = row.iloc[0]
    return {
        "name": r["Teacher_Name"],
        "role": r["Role"],
        "teaches_ms": r["Teaches_MS"],
        "vacant": r["Vacant"],
        "subjects": [s.strip() for s in str(r["Subjects"]).split("|")],
    }

def is_vacant(tid, teachers_df):
    info = teacher_info(tid, teachers_df)
    return str(info.get("vacant","No")).strip().lower() == "yes"

def export_html(df, title):
    if df.empty:
        return "<p>No data to export</p>"
    
    rows = ""
    for r in df.values:
        rows += "<tr>"
        for v in r:
            rows += f"<td>{v}</td>"
        rows += "</tr>"
    
    cols = ""
    for c in df.columns:
        cols += f"<th>{c}</th>"
    
    html = '<!DOCTYPE html><html><head><meta charset="UTF-8"><title>' + title + '</title>'
    html += '<style>'
    html += 'body{font-family:Arial,sans-serif;padding:20px}'
    html += 'h2{color:#004d4d;text-align:center}'
    html += 'table{width:100%;border-collapse:collapse;margin-top:15px}'
    html += 'th{background:#006666;color:white;padding:9px;text-align:left}'
    html += 'td{padding:7px;border-bottom:1px solid #ddd}'
    html += 'tr:nth-child(even){background:#f9f9f9}'
    html += '.footer{text-align:center;margin-top:25px;font-size:12px;color:#888}'
    html += '</style></head><body>'
    html += '<h2>' + title + '</h2>'
    html += '<table><thead><tr>' + cols + '</tr></thead><tbody>' + rows + '</tbody></table>'
    html += '<div class="footer">VPS Timetable Manager &mdash; ' + str(datetime.date.today()) + '</div>'
    html += '</body></html>'
    
    b64 = base64.b64encode(html.encode()).decode()
    return '<a href="data:text/html;base64,' + b64 + '" download="' + title.replace(" ","_") + '.html" style="display:inline-block;padding:9px 18px;background:#006666;color:white;text-decoration:none;border-radius:7px;font-weight:bold;">📥 Download (Print to PDF)</a>'

# ============================================================
# PASSWORD PROTECTION
# ============================================================
def check_password():
    if st.session_state.get("password_correct", False):
        return True

    st.markdown("""
    <style>
    .login-wrap{display:flex;justify-content:center;margin-top:80px}
    .login-box{background:linear-gradient(135deg,#004d4d,#006666);
    padding:45px 40px;border-radius:20px;text-align:center;
    color:white;width:380px;box-shadow:0 10px 30px rgba(0,0,0,.3)}
    .stTextInput>div>div>input{border-radius:25px!important;
    border:2px solid #009999!important;text-align:center}
    </style>""", unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1,1.6,1])
    with c2:
        st.markdown('<div class="login-box">', unsafe_allow_html=True)
        st.markdown("### 🔐 VPS Timetable Manager")
        st.markdown("Vidyaniketan Public School — High School")
        pwd = st.text_input("Password", type="password", placeholder="Enter password...", key="pwd_field")
        if st.button("🔓 Login", use_container_width=True):
            correct = st.secrets.get("APP_PASSWORD", "vps2024")
            if pwd == correct:
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("❌ Incorrect password")
        st.markdown("</div>", unsafe_allow_html=True)
    return False

if not check_password():
    st.stop()

# ============================================================
# CSS
# ============================================================
st.markdown("""
<style>
.main-header{background:linear-gradient(135deg,#004d4d,#006666,#009999);
color:white;padding:14px 20px;border-radius:14px;
text-align:center;margin-bottom:18px}
.stButton>button{background:#006666;color:white;border-radius:8px;
border:none;font-weight:600}
.stButton>button:hover{background:#009999;color:white}
.tt-cell{padding:8px 12px;border-radius:8px;font-size:13px;
font-weight:600;text-align:center;color:#000000}
.tt-cell small{color:#333333;font-weight:normal}
.section-head{background:#E0F2F1;padding:10px 15px;
border-radius:8px;border-left:5px solid #006666;margin-bottom:12px}
</style>""", unsafe_allow_html=True)

# ============================================================
# HEADER + LOGOUT
# ============================================================
hcol, lcol = st.columns([7,1])
with hcol:
    st.markdown('<div class="main-header"><h2>🏫 VPS Timetable &amp; Substitution Manager</h2>'
                '<p style="margin:0;opacity:.85">Vidyaniketan Public School — High School (Classes 8–10)</p>'
                '</div>', unsafe_allow_html=True)
with lcol:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🚪 Logout"):
        for k in ["password_correct","teachers_df","periods_df","timetable","teacher_sched","sub_log","assigned_subs"]:
            st.session_state.pop(k, None)
        st.rerun()

# ============================================================
# SESSION STATE INITIALISATION
# ============================================================
if "teachers_df" not in st.session_state:
    st.session_state["teachers_df"] = None
if "periods_df" not in st.session_state:
    st.session_state["periods_df"] = None
if "timetable" not in st.session_state:
    st.session_state["timetable"] = None
if "teacher_sched" not in st.session_state:
    st.session_state["teacher_sched"] = None
if "sub_log" not in st.session_state:
    st.session_state["sub_log"] = []
if "assigned_subs" not in st.session_state:
    st.session_state["assigned_subs"] = []

# ============================================================
# DATA UPLOAD
# ============================================================
with st.expander("📂 Load Data Files", expanded=(st.session_state["teachers_df"] is None)):
    uc1, uc2 = st.columns(2)
    with uc1:
        tf = st.file_uploader("Upload **teachers.csv**", type="csv", key="up_teachers")
        if tf:
            try:
                tdf = pd.read_csv(tf)
                tdf.columns = [c.strip() for c in tdf.columns]
                st.session_state["teachers_df"] = tdf
                st.success(f"✅ {len(tdf)} teachers loaded")
            except Exception as e:
                st.error(f"Error reading teachers.csv: {e}")
    with uc2:
        pf = st.file_uploader("Upload **periods_config.csv**", type="csv", key="up_periods")
        if pf:
            try:
                pdf = pd.read_csv(pf)
                pdf.columns = [c.strip() for c in pdf.columns]
                pdf["Class"] = pdf["Class"].astype(int)
                st.session_state["periods_df"] = pdf
                st.success(f"✅ {len(pdf)} subject-section rows loaded")
            except Exception as e:
                st.error(f"Error reading periods_config.csv: {e}")

teachers_df = st.session_state["teachers_df"]
periods_df = st.session_state["periods_df"]
data_ready = (teachers_df is not None) and (periods_df is not None)

# ============================================================
# TABS
# ============================================================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🗂️ Master Editor",
    "📘 Class View",
    "🧑‍🏫 Teacher View",
    "🧠 Smart Substitution",
    "🔄 Timetable Generator",
])

# ============================================================
# TIMETABLE GENERATOR ENGINE
# ============================================================

def build_empty_grids(periods_df, teachers_df):
    sections = []
    for _, row in periods_df[["Class","Section"]].drop_duplicates().iterrows():
        sections.append((int(row["Class"]), str(row["Section"])))

    timetable = {}
    for cls, sec in sections:
        key = f"{cls}{sec}"
        timetable[key] = {}
        for day in get_days(cls):
            timetable[key][day] = {p: None for p in get_slots(cls, day)}

    teacher_sched = {}
    if teachers_df is not None:
        for _, row in teachers_df.iterrows():
            tid = row["Teacher_ID"]
            if str(row.get("Vacant","No")).strip().lower() == "yes":
                continue
            teacher_sched[tid] = {}
            for day in DAYS_9_10:
                teacher_sched[tid][day] = {}
                for p in ["P0","P1","P2","P3","P4","P5","P6","P7","P8","P9"]:
                    teacher_sched[tid][day][p] = None

    return timetable, teacher_sched

def place_slot(timetable, teacher_sched, cs_key, day, period, subject, tid, tname, lab_tracker, lib_tracker):
    cls = int(cs_key[:-1])

    if timetable[cs_key][day].get(period) is not None:
        return False

    if tid not in SPECIAL_IDS and "|" not in tid and teacher_sched:
        if teacher_sched.get(tid, {}).get(day, {}):
            day_load = sum(1 for v in teacher_sched[tid][day].values() if v is not None)
            if day_load >= REGULAR_MAX_LOAD:
                return False

    if tid not in SPECIAL_IDS and "|" not in tid and teacher_sched:
        if teacher_sched.get(tid, {}).get(day, {}).get(period) is not None:
            return False

    if subject in {"PE","Sports"} and day != "Saturday" and period in PE_BLOCKED_SUBS:
        return False

    if subject == "Science Lab":
        count = lab_tracker.get(day,{}).get(period,0)
        if count >= 1:
            return False

    if subject == "Library":
        count = lib_tracker.get(day,{}).get(period,0)
        if count >= 1:
            return False

    ALLOW_TWO_PER_DAY = {"Mathematics"}
    day_subjects = [v["subject"] for v in timetable[cs_key][day].values() if v]
    if subject in day_subjects and subject not in {"Assembly","Class Test","Science Lab"}:
        if subject in ALLOW_TWO_PER_DAY:
            if day_subjects.count(subject) >= 2:
                return False
        else:
            return False

    if tid not in SPECIAL_IDS and "|" not in tid and subject != "Science Lab":
        teacher_in_class_today = sum(1 for v in timetable[cs_key][day].values() if v and v.get("teacher_id") == tid)
        limit = 2 if subject in ALLOW_TWO_PER_DAY else 1
        if teacher_in_class_today >= limit:
            return False

    timetable[cs_key][day][period] = {"subject": subject, "teacher_id": tid, "teacher_name": tname}
    if tid not in SPECIAL_IDS and "|" not in tid and teacher_sched:
        teacher_sched[tid][day][period] = cs_key

    if subject == "Science Lab":
        lab_tracker.setdefault(day,{})[period] = lab_tracker.get(day,{}).get(period,0) + 1
    if subject == "Library":
        lib_tracker.setdefault(day,{})[period] = lib_tracker.get(day,{}).get(period,0) + 1

    return True

def generate_timetable(periods_df, teachers_df):
    try:
        timetable, teacher_sched = build_empty_grids(periods_df, teachers_df)
    except Exception as e:
        st.error(f"Error building empty grids: {e}")
        return {}, {}, []
    
    lab_tracker = {}
    lib_tracker = {}
    unplaced = []

    class_teachers = {}
    for cs_key in timetable:
        cls = int(cs_key[:-1])
        sec = cs_key[-1]
        sub_rows = periods_df[(periods_df["Class"]==cls) & (periods_df["Section"]==sec)]
        tc_counts = {}
        for _, row in sub_rows.iterrows():
            tid = str(row["Teacher_ID"]).strip()
            if tid in SPECIAL_IDS or "|" in tid:
                continue
            tc_counts[tid] = tc_counts.get(tid,0) + int(row["Periods_Per_Week"])
        if tc_counts:
            class_teachers[cs_key] = max(tc_counts, key=tc_counts.get)
        else:
            class_teachers[cs_key] = "CLASSTCHR"

    for cs_key in sorted(timetable.keys()):
        cls = int(cs_key[:-1])
        days = get_days(cls)
        sub_rows = periods_df[(periods_df["Class"]==cls) & (periods_df["Section"]==cs_key[-1])]

        fixed_subjects = []
        block_subjects = []
        regular_subjects = []

        for _, row in sub_rows.iterrows():
            subj = str(row["Subject"]).strip()
            ppw = int(row["Periods_Per_Week"])
            raw_tid = str(row["Teacher_ID"]).strip()
            is_block = str(row.get("Block_Period","No")).strip().lower() == "yes"

            if raw_tid == "CLASSTCHR":
                tid = class_teachers.get(cs_key,"CLASSTCHR")
                tname = teacher_name(tid, teachers_df) if tid != "CLASSTCHR" else "Class Teacher"
            elif raw_tid == "SCILAB":
                tid = "SCILAB"
                tname = "Science Lab"
            elif raw_tid == "COSCHO":
                tid = "COSCHO"
                tname = "Co-Scholastic"
            elif "|" in raw_tid:
                parts = [p.strip() for p in raw_tid.split("|")]
                parts = list(dict.fromkeys(p for p in parts if p))
                tid = parts[0]
                tname = teacher_name(tid, teachers_df)
            else:
                tid = raw_tid
                tname = teacher_name(tid, teachers_df)

            if tid not in SPECIAL_IDS and "|" not in tid:
                if is_vacant(tid, teachers_df):
                    unplaced.append({"Class":cs_key,"Subject":subj,"Reason":"Teacher vacant"})
                    continue

            entry = {"subject":subj,"tid":tid,"tname":tname,"ppw":ppw,"block":is_block}

            if subj == "Assembly":
                fixed_subjects.append(entry)
            elif subj == "Class Test":
                fixed_subjects.append(entry)
            elif is_block or subj == "Science Lab":
                block_subjects.append(entry)
            else:
                regular_subjects.append(entry)

        for entry in fixed_subjects:
            subj = entry["subject"]
            tid = entry["tid"]
            tname = entry["tname"]
            ppw = entry["ppw"]

            fixed_day = ASSEMBLY_DAY.get(str(cls)) if subj == "Assembly" else CLASS_TEST_DAY.get(str(cls))

            if fixed_day and fixed_day in days:
                slots = get_slots(cls, fixed_day)
                placed = 0
                for p in slots:
                    if placed >= ppw:
                        break
                    ok = place_slot(timetable, teacher_sched, cs_key, fixed_day, p, subj, tid, tname, lab_tracker, lib_tracker)
                    if ok:
                        placed += 1
                if placed < ppw:
                    unplaced.append({"Class":cs_key,"Subject":subj, "Reason":f"Only {placed}/{ppw} placed on {fixed_day}"})

        for entry in block_subjects:
            subj = entry["subject"]
            tid = entry["tid"]
            tname = entry["tname"]
            placed = False
            day_order = [d for d in days if d != "Saturday"]
            random.shuffle(day_order)
            for day in day_order:
                for i in range(len(get_slots(cls, day)) - 1):
                    p1, p2 = get_slots(cls, day)[i], get_slots(cls, day)[i+1]
                    if p1 == "P0":
                        continue
                    ok1 = place_slot(timetable, teacher_sched, cs_key, day, p1, subj, tid, tname, lab_tracker, lib_tracker)
                    if ok1:
                        ok2 = place_slot(timetable, teacher_sched, cs_key, day, p2, subj, tid, tname, lab_tracker, lib_tracker)
                        if ok2:
                            placed = True
                            break
                        else:
                            timetable[cs_key][day][p1] = None
                            if tid not in SPECIAL_IDS and teacher_sched:
                                teacher_sched[tid][day][p1] = None
                if placed:
                    break
            if not placed:
                unplaced.append({"Class":cs_key,"Subject":subj,"Reason":"No block slot found"})

        for entry in regular_subjects:
            subj = entry["subject"]
            tid = entry["tid"]
            tname = entry["tname"]
            ppw = entry["ppw"]

            candidates = []
            for day in days:
                for p in get_slots(cls, day):
                    if timetable[cs_key][day].get(p) is None:
                        candidates.append((0, day, p))

            random.shuffle(candidates)

            placed = 0
            for _, day, p in candidates:
                if placed >= ppw:
                    break
                ok = place_slot(timetable, teacher_sched, cs_key, day, p, subj, tid, tname, lab_tracker, lib_tracker)
                if ok:
                    placed += 1

            if placed < ppw:
                unplaced.append({"Class":cs_key,"Subject":subj, "Reason":f"Only {placed}/{ppw} placed"})

    return timetable, teacher_sched, unplaced

def timetable_to_df(timetable, teachers_df):
    if not timetable:
        return pd.DataFrame()
    
    rows = []
    for cs_key, days_dict in timetable.items():
        cls = int(cs_key[:-1])
        sec = cs_key[-1]
        for day, periods_dict in days_dict.items():
            for period, val in periods_dict.items():
                if val:
                    rows.append({
                        "Class": cls,
                        "Section": sec,
                        "Class_Section": cs_key,
                        "Day": day,
                        "Period": period,
                        "Time": get_time(cls, day, period),
                        "Subject": val["subject"],
                        "Teacher_ID": val["teacher_id"],
                        "Teacher": val["teacher_name"],
                    })
    return pd.DataFrame(rows)

def render_class_grid(cs_key, timetable):
    if not timetable or cs_key not in timetable:
        return "<p>No timetable data available</p>"
    
    cls = int(cs_key[:-1])
    days = get_days(cls)

    html = '<table style="width:100%;border-collapse:collapse;font-size:13px">'
    html += '<thead style="background:#006666;color:white"><tr><th>Period</th>'
    for day in days:
        html += f'<th>{day}</th>'
    html += '</tr></thead><tbody>'

    all_periods = []
    seen = set()
    for day in days:
        for p in get_slots(cls, day):
            if p not in seen:
                all_periods.append(p)
                seen.add(p)

    for p in all_periods:
        html += f'<tr><td><b>{p}</b></td>'
        for day in days:
            val = timetable.get(cs_key,{}).get(day,{}).get(p)
            if val is None:
                html += '<td style="text-align:center">—</td>'
            else:
                color = subj_color(val["subject"])
                html += f'<td style="background:{color};text-align:center;padding:8px">'
                html += f'<div class="tt-cell"><strong>{val["subject"]}</strong><br>'
                html += f'<small>{val["teacher_name"]}</small></div></td>'
        html += '</tr>'
    
    html += '</tbody></table>'
    return html

# ============================================================
# TAB 5 — TIMETABLE GENERATOR
# ============================================================
with tab5:
    st.markdown('<div class="section-head"><h3>🔄 Auto Timetable Generator</h3>'
                'Generates a clash-free weekly timetable from your CSV data.</div>', unsafe_allow_html=True)

    if not data_ready:
        st.warning("⚠️ Please upload both teachers.csv and periods_config.csv above.")
    else:
        with st.expander("⚙️ Generator Settings", expanded=True):
            n_attempts = st.number_input("Attempts (more = better quality)", min_value=1, max_value=20, value=5, key="gen_attempts")
            seed_val = st.number_input("Random seed (0 = random each time)", min_value=0, value=42, key="gen_seed")
            gen_btn = st.button("🚀 Generate Timetable", type="primary", use_container_width=True)

        if gen_btn:
            errors = []
            known_ids = set(teachers_df["Teacher_ID"].astype(str).str.strip())
            for _, row in periods_df.iterrows():
                tid = str(row["Teacher_ID"]).strip()
                if tid in SPECIAL_IDS:
                    continue
                for part in tid.split("|"):
                    part = part.strip()
                    if part and part not in known_ids:
                        errors.append(f"Unknown Teacher_ID '{part}' in {row['Class']}{row['Section']} — {row['Subject']}")

            if errors:
                st.error("❌ Validation errors found:")
                for e in errors[:10]:
                    st.markdown(f"- {e}")
            else:
                best_tt, best_ts, best_up = None, None, None
                best_score = -9999

                with st.spinner(f"Generating ({n_attempts} attempt(s))..."):
                    for attempt in range(n_attempts):
                        rseed = seed_val if seed_val > 0 else random.randint(1, 99999)
                        random.seed(rseed + attempt)
                        tt, ts, up = generate_timetable(periods_df.copy(), teachers_df.copy())
                        score = -len(up)
                        if score > best_score:
                            best_score = score
                            best_tt, best_ts, best_up = tt, ts, up

                st.session_state["timetable"] = best_tt
                st.session_state["teacher_sched"] = best_ts

                placed_count = sum(1 for cs in best_tt.values() for day in cs.values() for v in day.values() if v)
                st.success(f"✅ Timetable generated! {placed_count} periods placed. {len(best_up)} unplaced.")

                if best_up:
                    with st.expander(f"⚠️ {len(best_up)} unplaced periods"):
                        st.dataframe(pd.DataFrame(best_up), hide_index=True)

        if st.session_state["timetable"]:
            tt = st.session_state["timetable"]
            tt_df = timetable_to_df(tt, teachers_df)
            
            st.markdown("---")
            st.markdown("### 📊 View Generated Timetable")

            view_mode = st.radio("View by:", ["Class/Section", "Teacher"], horizontal=True)

            if view_mode == "Class/Section":
                cs_options = sorted(tt.keys())
                sel_cs = st.selectbox("Select Class–Section", cs_options)
                st.markdown(render_class_grid(sel_cs, tt), unsafe_allow_html=True)

                if not tt_df.empty:
                    cs_df = tt_df[tt_df["Class_Section"] == sel_cs].drop(columns=["Class_Section"]).sort_values(["Day", "Period"])
                    st.markdown(export_html(cs_df, f"Timetable_{sel_cs}"), unsafe_allow_html=True)

            else:
                if not tt_df.empty:
                    t_options = sorted(tt_df["Teacher"].dropna().unique())
                    sel_t = st.selectbox("Select Teacher", t_options)
                    t_df = tt_df[tt_df["Teacher"] == sel_t][["Day", "Period", "Time", "Class", "Section", "Subject"]].sort_values(["Day", "Period"])
                    st.dataframe(t_df, hide_index=True, use_container_width=True)
                    st.markdown(export_html(t_df, f"{sel_t}_Schedule"), unsafe_allow_html=True)

            if not tt_df.empty:
                st.markdown("---")
                full_df = tt_df.drop(columns=["Class_Section"])
                st.download_button("📥 Download Full Timetable (CSV)", data=full_df.to_csv(index=False).encode(), file_name="VPS_Generated_Timetable.csv", mime="text/csv")

# ============================================================
# SIMPLIFIED TABS 1-4 (Placeholder)
# ============================================================

with tab1:
    if not data_ready:
        st.warning("⚠️ Upload both CSV files first.")
    elif st.session_state["timetable"] is None:
        st.info("ℹ️ Master Editor is available once a timetable has been generated. Go to the Timetable Generator tab.")
    else:
        st.success("✅ Master Editor - Timetable loaded successfully!")
        st.dataframe(timetable_to_df(st.session_state["timetable"], teachers_df), use_container_width=True)

with tab2:
    if not data_ready:
        st.warning("⚠️ Upload both CSV files first.")
    elif st.session_state["timetable"] is None:
        st.info("ℹ️ Class View is available once a timetable has been generated. Go to the Timetable Generator tab.")
    else:
        st.success("✅ Class View - Select a class from the Timetable Generator tab")

with tab3:
    if not data_ready:
        st.warning("⚠️ Upload both CSV files first.")
    elif st.session_state["timetable"] is None:
        st.info("ℹ️ Teacher View is available once a timetable has been generated. Go to the Timetable Generator tab.")
    else:
        st.success("✅ Teacher View - Select a teacher from the Timetable Generator tab")

with tab4:
    st.markdown('<div class="section-head"><h3>🧠 Smart Substitution Engine</h3></div>', unsafe_allow_html=True)
    st.info("ℹ️ The Smart Substitution feature will be available in the next update. Please generate a timetable first using the Timetable Generator tab.")
