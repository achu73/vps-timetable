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
# CONSTANTS — Period timings & scheduling rules
# ============================================================

DAYS_9_10 = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
DAYS_8    = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

# Ordered period labels per schedule-type
SLOTS = {
    "regular":  ["P1","P2","P3","P4","P5","P6","P7","P8","P9"],   # 9/10 weekday + 8 Tue/Thu/Fri
    "saturday": ["P1","P2","P3","P4","P5","P6"],                   # 9/10 Saturday
    "zero":     ["P0","P1","P2","P3","P4","P5","P6","P7","P8","P9"], # 8 Mon/Wed
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

# Periods that come after lunch (preferred for PE/Art/Library) — regular schedule
POST_LUNCH = {"P7","P8","P9"}
MORNING    = {"P1","P2","P3"}    # preferred for Maths/core subjects

# Fixed-day rules (H8, H9)
ASSEMBLY_DAY   = {"8":"Friday",    "9":"Thursday",  "10":"Tuesday"}
CLASS_TEST_DAY = {"8":"Wednesday", "9":"Wednesday", "10":"Monday"}

# Role-based substitution rules
NO_SUB_ROLES      = {"PRINCIPAL","VICE PRINCIPAL","LEVEL COORDINATOR"}
SUB_COORD_MAX_WK  = 3   # Subject Coordinator max subs per week
REGULAR_MAX_LOAD  = 7   # Regular teacher max periods/day

# PE cannot sub P1 or P7 on weekdays
PE_BLOCKED_SUBS = {"P1","P7"}

# Special pseudo-IDs (not real teachers)
SPECIAL_IDS = {"CLASSTCHR","SCILAB","COSCHO"}

# Subject colour palette for timetable grid
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
    for k,v in SUBJ_COLOR.items():
        if k.lower() in subj.lower():
            return v
    return "#F5F5F5"

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_slots(class_num: int, day: str) -> list:
    """Return ordered list of period labels for a class/day combination."""
    if class_num in (9, 10):
        return SLOTS["saturday"] if day == "Saturday" else SLOTS["regular"]
    else:  # Class 8
        return SLOTS["zero"] if day in ("Monday","Wednesday") else SLOTS["regular"]

def get_time(class_num: int, day: str, period: str) -> str:
    if class_num in (9,10) and day == "Saturday":
        return TIMES["saturday"].get(period,"")
    elif class_num == 8 and day in ("Monday","Wednesday"):
        return TIMES["zero"].get(period,"")
    else:
        return TIMES["regular"].get(period,"")

def get_days(class_num: int) -> list:
    return DAYS_8 if class_num == 8 else DAYS_9_10

def is_pe_teacher(tid: str, teachers_df: pd.DataFrame) -> bool:
    row = teachers_df[teachers_df["Teacher_ID"] == tid]
    if row.empty:
        return False
    subjs = str(row.iloc[0]["Subjects"])
    return any(s.strip() in {"PE","Sports"} for s in subjs.split("|"))

def can_give_sub(role: str) -> bool:
    return role.upper() not in NO_SUB_ROLES

def teacher_name(tid: str, teachers_df: pd.DataFrame) -> str:
    if tid in SPECIAL_IDS or "|" in str(tid):
        return tid
    row = teachers_df[teachers_df["Teacher_ID"] == tid]
    return row.iloc[0]["Teacher_Name"] if not row.empty else tid

def teacher_info(tid: str, teachers_df: pd.DataFrame) -> dict:
    row = teachers_df[teachers_df["Teacher_ID"] == tid]
    if row.empty:
        return {"role":"REGULAR","teaches_ms":"No","vacant":"No","name":tid}
    r = row.iloc[0]
    return {
        "name":      r["Teacher_Name"],
        "role":      r["Role"],
        "teaches_ms":r["Teaches_MS"],
        "vacant":    r["Vacant"],
        "subjects":  [s.strip() for s in str(r["Subjects"]).split("|")],
    }

def is_vacant(tid: str, teachers_df: pd.DataFrame) -> bool:
    info = teacher_info(tid, teachers_df)
    return str(info.get("vacant","No")).strip().lower() == "yes"

def export_html(df: pd.DataFrame, title: str) -> str:
    """Returns an anchor tag that downloads the dataframe as a printable HTML file."""
    rows = "".join(
        "<tr>" + "".join(f"<td>{v}</td>" for v in r) + "</tr>"
        for r in df.values
    )
    cols = "".join(f"<th>{c}</th>" for c in df.columns)
    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>{title}</title>
<style>
  body{{font-family:Arial,sans-serif;padding:20px}}
  h2{{color:#004d4d;text-align:center}}
  table{{width:100%;border-collapse:collapse;margin-top:15px}}
  th{{background:#006666;color:white;padding:9px;text-align:left}}
  td{{padding:7px;border-bottom:1px solid #ddd}}
  tr:nth-child(even){{background:#f9f9f9}}
  .footer{{text-align:center;margin-top:25px;font-size:12px;color:#888}}
</style></head><body>
<h2>{title}</h2>
<table><thead><tr>{cols}</tr></thead><tbody>{rows}</tbody></table>
<div class="footer">VPS Timetable Manager &mdash; {datetime.date.today()}</div>
</body></html>"""
    b64 = base64.b64encode(html.encode()).decode()
    return (f'<a href="data:text/html;base64,{b64}" download="{title.replace(" ","_")}.html" '
            f'style="display:inline-block;padding:9px 18px;background:#006666;color:white;'
            f'text-decoration:none;border-radius:7px;font-weight:bold;">📥 Download (Print to PDF)</a>')

# ============================================================
# PASSWORD PROTECTION  — Bug Fix: no error shown on first load
# ============================================================
def check_password() -> bool:
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

    c1,c2,c3 = st.columns([1,1.6,1])
    with c2:
        st.markdown('<div class="login-box">', unsafe_allow_html=True)
        st.markdown("### 🔐 VPS Timetable Manager")
        st.markdown("Vidyaniketan Public School — High School")
        pwd = st.text_input("Password", type="password",
                            placeholder="Enter password...", key="pwd_field")
        if st.button("🔓 Login", use_container_width=True):
            correct = st.secrets.get("APP_PASSWORD","vps2024")
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
  .tt-cell{padding:6px 10px;border-radius:8px;font-size:12px;
    font-weight:600;text-align:center;white-space:nowrap;
    overflow:hidden;text-overflow:ellipsis}
  .warn-ms{background:#FFF3CD;border-left:4px solid #FFA000;
    padding:6px 10px;border-radius:6px;margin:4px 0}
  .section-head{background:#E0F2F1;padding:10px 15px;
    border-radius:8px;border-left:5px solid #006666;margin-bottom:12px}
  .sub-chip{display:inline-block;padding:3px 10px;margin:2px;
    border-radius:12px;font-size:12px;font-weight:600;color:#333}
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
        for k in ["password_correct","teachers_df","periods_df","timetable",
                  "teacher_sched","sub_log","assigned_subs"]:
            st.session_state.pop(k, None)
        st.rerun()

# ============================================================
# SESSION STATE INITIALISATION
# ============================================================
for k, v in [("teachers_df", None), ("periods_df", None),
             ("timetable", None), ("teacher_sched", None),
             ("sub_log", []), ("assigned_subs", [])]:
    if k not in st.session_state:
        st.session_state[k] = v

# ============================================================
# DATA UPLOAD  — Bug Fix #4: no disk storage; session state only
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
periods_df  = st.session_state["periods_df"]
data_ready  = (teachers_df is not None) and (periods_df is not None)

# ============================================================
# TABS  — Bug Fix #1: Tab 5 accessible without timetable
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
    """Return empty timetable and teacher_sched dicts."""
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
    for _, row in teachers_df.iterrows():
        tid = row["Teacher_ID"]
        if str(row.get("Vacant","No")).strip().lower() == "yes":
            continue
        teacher_sched[tid] = {}
        # Use all possible days/periods (union of both class types)
        for day in DAYS_9_10:
            teacher_sched[tid][day] = {}
            # Store for all possible slot labels
            for p in ["P0","P1","P2","P3","P4","P5","P6","P7","P8","P9"]:
                teacher_sched[tid][day][p] = None

    return timetable, teacher_sched


def place_slot(timetable, teacher_sched, cs_key, day, period,
               subject, tid, tname, lab_tracker, lib_tracker):
    """
    Attempt to place one (subject, teacher) into (cs_key, day, period).
    Returns True on success, False if any hard constraint is violated.
    lab_tracker[day][period] = count of sections in sci lab
    lib_tracker[day][period] = count of sections in library
    """
    cls = int(cs_key[:-1])    # e.g. "10F" → 10
    # sec = cs_key[-1]

    # H2: class slot must be empty
    if timetable[cs_key][day].get(period) is not None:
        return False

    # H3: max 7 teaching periods per teacher per day (skip special IDs)
    if tid not in SPECIAL_IDS and "|" not in tid:
        day_load = sum(1 for p, v in teacher_sched.get(tid,{}).get(day,{}).items() if v is not None)
        if day_load >= REGULAR_MAX_LOAD:
            return False

    # H1: teacher not double-booked (skip special IDs)
    if tid not in SPECIAL_IDS and "|" not in tid:
        if teacher_sched.get(tid,{}).get(day,{}).get(period) is not None:
            return False

    # H4: PE not in P1 or P7 on weekdays
    if subject in {"PE","Sports"} and day != "Saturday" and period in PE_BLOCKED_SUBS:
        return False

    # H6: Science Lab — only one section per period
    if subject == "Science Lab":
        count = lab_tracker.get(day,{}).get(period,0)
        if count >= 1:
            return False

    # H7: Library — one section per period
    if subject == "Library":
        count = lib_tracker.get(day,{}).get(period,0)
        if count >= 1:
            return False

    # H11: same subject not twice in same day for same class
    # Exception: Mathematics allows up to 2/day (S2 explicitly permits this)
    ALLOW_TWO_PER_DAY = {"Mathematics"}
    day_subjects = [v["subject"] for v in timetable[cs_key][day].values() if v]
    if subject in day_subjects and subject not in {"Assembly","Class Test","Science Lab"}:
        if subject in ALLOW_TWO_PER_DAY:
            # Allow at most 2 per day
            if day_subjects.count(subject) >= 2:
                return False
        else:
            return False

    # H12: teacher not twice in same class per day (except block periods & high-freq subjects)
    # Mathematics needs 8 periods/6 days → must allow 2/day on some days
    if tid not in SPECIAL_IDS and "|" not in tid and subject != "Science Lab":
        teacher_in_class_today = sum(
            1 for v in timetable[cs_key][day].values()
            if v and v.get("teacher_id") == tid
        )
        limit = 2 if subject in ALLOW_TWO_PER_DAY else 1
        if teacher_in_class_today >= limit:
            return False

    # All checks passed — place it
    timetable[cs_key][day][period] = {
        "subject": subject, "teacher_id": tid, "teacher_name": tname
    }
    if tid not in SPECIAL_IDS and "|" not in tid:
        teacher_sched[tid][day][period] = cs_key

    if subject == "Science Lab":
        lab_tracker.setdefault(day,{})[period] = lab_tracker.get(day,{}).get(period,0) + 1
    if subject == "Library":
        lib_tracker.setdefault(day,{})[period] = lib_tracker.get(day,{}).get(period,0) + 1

    return True


def place_block(timetable, teacher_sched, cs_key, day, subject, tid, tname,
                lab_tracker, lib_tracker):
    """
    Try to place a 2-consecutive-period block (Science Lab) on the given day.
    Returns (p1, p2) if placed, else None.
    """
    cls = int(cs_key[:-1])
    slots = get_slots(cls, day)
    # Skip P0 for blocks; don't cross break/lunch (just check consecutive index)
    for i in range(len(slots) - 1):
        p1, p2 = slots[i], slots[i+1]
        if p1 == "P0":
            continue
        # Don't place across the break (P3→P4) or lunch gaps
        # In regular schedule: break is between P3 and P4; lunch between P6 and P7
        # We reject P3+P4 cross (index gap represents break) by checking they are numerically consecutive
        n1 = int(p1[1:])
        n2 = int(p2[1:])
        if n2 != n1 + 1:
            continue
        # Skip across break/lunch by period numbers
        if (n1 == 3 and n2 == 4) or (n1 == 6 and n2 == 7):
            # These cross break or lunch — still valid periods but teachers may object
            # Per spec the break is 10 mins and lab is 2 consecutive, allow it
            pass

        # Check H6: lab can't have another section in either slot
        lab_ok = (lab_tracker.get(day,{}).get(p1,0) < 1 and
                  lab_tracker.get(day,{}).get(p2,0) < 1)
        if not lab_ok:
            continue

        # Temporarily place
        ok1 = place_slot(timetable, teacher_sched, cs_key, day, p1,
                         subject, tid, tname, lab_tracker, lib_tracker)
        if not ok1:
            continue
        ok2 = place_slot(timetable, teacher_sched, cs_key, day, p2,
                         subject, tid, tname, lab_tracker, lib_tracker)
        if ok2:
            return (p1, p2)
        else:
            # Undo p1
            timetable[cs_key][day][p1] = None
            if tid not in SPECIAL_IDS:
                teacher_sched.get(tid,{}).get(day,{}).__setitem__(p1, None)
            lab_tracker.get(day,{}).__setitem__(p1, max(0, lab_tracker.get(day,{}).get(p1,0)-1))
    return None


def score_slot(period, subject, day, class_num):
    """
    Soft-constraint scoring — higher = better slot for this subject.
    Used to sort candidate slots before trying placement.
    """
    score = 0
    p_num = int(period[1:]) if period[1:].isdigit() else 0

    # S1: Maths in morning
    if "Math" in subject:
        if period in MORNING:
            score += 10
        elif period in POST_LUNCH:
            score -= 5

    # S3: Art/PE/Library after lunch
    if subject in {"Art","Art/Co-Scholastic","PE","Sports","Library","Co-Scholastic"}:
        if period in POST_LUNCH:
            score += 8
        elif period in MORNING:
            score -= 3

    # S5: Core subjects in morning
    if subject in {"English","Physics","Chemistry","Biology","Social Science",
                   "History","Geography","Political Science","Economics"}:
        if period in MORNING:
            score += 5

    # S6: Friday afternoon — light subjects
    if day == "Friday" and period in POST_LUNCH:
        if subject in {"Art","Sports","PE","Library","Yoga/HeyMath","GK","Co-Scholastic"}:
            score += 6

    # S4: Yoga/Art flexible
    if subject in {"Yoga/HeyMath","Art","Dance","Music"}:
        score += 2   # small bonus to be placed anywhere

    return score


def generate_timetable(periods_df, teachers_df):
    """
    Main generator. Returns (timetable, teacher_sched, unplaced_list).
    timetable[cs_key][day][period] = {subject, teacher_id, teacher_name} or None
    teacher_sched[teacher_id][day][period] = cs_key or None
    """
    timetable, teacher_sched = build_empty_grids(periods_df, teachers_df)
    lab_tracker = {}   # day -> period -> count
    lib_tracker = {}   # day -> period -> count
    unplaced    = []

    # --- Identify class teacher per section (most-periods teacher) ---
    class_teachers = {}
    for cs_key in timetable:
        cls = int(cs_key[:-1])
        sec = cs_key[-1]
        sub_rows = periods_df[(periods_df["Class"]==cls) & (periods_df["Section"]==sec)]
        # Exclude special IDs; find teacher with most periods
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

    # --- Process each class-section ---
    for cs_key in sorted(timetable.keys()):
        cls = int(cs_key[:-1])
        sec = cs_key[-1]
        days = get_days(cls)
        sub_rows = periods_df[
            (periods_df["Class"]==cls) & (periods_df["Section"]==sec)
        ]

        # Separate subject types
        fixed_subjects  = []   # Assembly, Class Test (day is fixed)
        block_subjects  = []   # Science Lab (block period)
        regular_subjects = []  # everything else

        for _, row in sub_rows.iterrows():
            subj   = str(row["Subject"]).strip()
            ppw    = int(row["Periods_Per_Week"])
            raw_tid = str(row["Teacher_ID"]).strip()
            is_block = str(row.get("Block_Period","No")).strip().lower() == "yes"

            # Resolve teacher ID / name
            if raw_tid == "CLASSTCHR":
                tid   = class_teachers.get(cs_key,"CLASSTCHR")
                tname = teacher_name(tid, teachers_df) if tid != "CLASSTCHR" else "Class Teacher"
            elif raw_tid == "SCILAB":
                tid   = "SCILAB"
                tname = "Science Lab"
            elif raw_tid == "COSCHO":
                tid   = "COSCHO"
                tname = "Co-Scholastic"
            elif "|" in raw_tid:
                # Yoga/HeyMath alternate-week teachers — pick one
                parts = [p.strip() for p in raw_tid.split("|")]
                # Deduplicate
                parts = list(dict.fromkeys(p for p in parts if p))
                tid   = parts[0]  # Week A teacher
                tname = teacher_name(tid, teachers_df)
            else:
                tid   = raw_tid
                tname = teacher_name(tid, teachers_df)

            # Skip vacant teachers — mark subject unplaceable
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

        # ---- STEP 1: Place fixed subjects (Assembly, Class Test) ----
        for entry in fixed_subjects:
            subj = entry["subject"]
            tid  = entry["tid"]
            tname= entry["tname"]
            ppw  = entry["ppw"]

            fixed_day = None
            if subj == "Assembly":
                fixed_day = ASSEMBLY_DAY.get(str(cls))
            elif subj == "Class Test":
                fixed_day = CLASS_TEST_DAY.get(str(cls))

            if fixed_day and fixed_day in days:
                slots = get_slots(cls, fixed_day)
                placed = 0
                for p in slots:
                    if placed >= ppw:
                        break
                    ok = place_slot(timetable, teacher_sched, cs_key, fixed_day, p,
                                    subj, tid, tname, lab_tracker, lib_tracker)
                    if ok:
                        placed += 1
                if placed < ppw:
                    unplaced.append({"Class":cs_key,"Subject":subj,
                                     "Reason":f"Only {placed}/{ppw} placed on {fixed_day}"})

        # ---- STEP 2: Place block subjects (Science Lab) ----
        for entry in block_subjects:
            subj = entry["subject"]
            tid  = entry["tid"]
            tname= entry["tname"]

            placed = False
            # Try each day in a shuffled order
            day_order = [d for d in days if d != "Saturday"]
            random.shuffle(day_order)
            for day in day_order:
                result = place_block(timetable, teacher_sched, cs_key, day, subj,
                                     tid, tname, lab_tracker, lib_tracker)
                if result:
                    placed = True
                    break
            if not placed:
                unplaced.append({"Class":cs_key,"Subject":subj,"Reason":"No block slot found"})

        # ---- STEP 3: Place regular subjects ----
        for entry in regular_subjects:
            subj = entry["subject"]
            tid  = entry["tid"]
            tname= entry["tname"]
            ppw  = entry["ppw"]

            # Build a pool of candidate (day, period) slots, scored by soft constraints
            candidates = []
            for day in days:
                for p in get_slots(cls, day):
                    if timetable[cs_key][day].get(p) is None:
                        score = score_slot(p, subj, day, cls)
                        candidates.append((score, day, p))

            # Sort: higher score first; within equal score, shuffle for variety
            random.shuffle(candidates)
            candidates.sort(key=lambda x: -x[0])

            placed = 0
            for _, day, p in candidates:
                if placed >= ppw:
                    break
                ok = place_slot(timetable, teacher_sched, cs_key, day, p,
                                subj, tid, tname, lab_tracker, lib_tracker)
                if ok:
                    placed += 1

            if placed < ppw:
                unplaced.append({"Class":cs_key,"Subject":subj,
                                 "Reason":f"Only {placed}/{ppw} placed"})

    return timetable, teacher_sched, unplaced


def timetable_to_df(timetable, teachers_df):
    """Flatten timetable dict into a DataFrame for display/export."""
    rows = []
    for cs_key, days_dict in timetable.items():
        cls = int(cs_key[:-1])
        sec = cs_key[-1]
        for day, periods_dict in days_dict.items():
            for period, val in periods_dict.items():
                if val:
                    rows.append({
                        "Class": cls, "Section": sec,
                        "Class_Section": cs_key,
                        "Day": day, "Period": period,
                        "Time": get_time(cls, day, period),
                        "Subject": val["subject"],
                        "Teacher_ID": val["teacher_id"],
                        "Teacher": val["teacher_name"],
                    })
    return pd.DataFrame(rows)


def render_class_grid(cs_key, timetable):
    """Render an HTML timetable grid for a class-section."""
    cls  = int(cs_key[:-1])
    days = get_days(cls)

    # Build header row
    header = "<tr><th>Period</th>" + "".join(f"<th>{d}</th>" for d in days) + "</tr>"

    # Collect all unique periods across all days for this class
    all_periods = []
    seen = set()
    for day in days:
        for p in get_slots(cls, day):
            if p not in seen:
                all_periods.append(p)
                seen.add(p)

    rows_html = ""
    for p in all_periods:
        row = f"<tr><td><b>{p}</b></td>"
        for day in days:
            val = timetable.get(cs_key,{}).get(day,{}).get(p)
            if day not in timetable.get(cs_key,{}):
                row += "<td style='background:#f0f0f0;color:#aaa'>—</td>"
            elif val is None:
                row += "<td>—</td>"
            else:
                color = subj_color(val["subject"])
                row += (f'<td><div class="tt-cell" style="background:{color}">'
                        f'{val["subject"]}<br>'
                        f'<small>{val["teacher_name"]}</small></div></td>')
        row += "</tr>"
        rows_html += row

    return f"""<table style="width:100%;border-collapse:collapse;font-size:13px">
<thead style="background:#006666;color:white">{header}</thead>
<tbody>{rows_html}</tbody></table>"""


# ============================================================
# TAB 5 — TIMETABLE GENERATOR  (available even before timetable exists)
# ============================================================
with tab5:
    st.markdown('<div class="section-head"><h3>🔄 Auto Timetable Generator</h3>'
                'Generates a clash-free weekly timetable from your CSV data using '
                'all hard and soft scheduling constraints.</div>', unsafe_allow_html=True)

    if not data_ready:
        st.warning("⚠️ Please upload both **teachers.csv** and **periods_config.csv** above to use the generator.")
    else:
        # --- Config panel ---
        with st.expander("⚙️ Generator Settings", expanded=True):
            gc1, gc2, gc3 = st.columns(3)
            with gc1:
                n_attempts = st.number_input("Attempts (more = better quality)",
                                             min_value=1, max_value=20, value=5,
                                             key="gen_attempts")
            with gc2:
                seed_val = st.number_input("Random seed (0 = random each time)",
                                           min_value=0, value=42, key="gen_seed")
            with gc3:
                st.markdown("<br>", unsafe_allow_html=True)
                gen_btn = st.button("🚀 Generate Timetable", type="primary",
                                    use_container_width=True)

        # --- Input validation (Bug Fix #5) ---
        if gen_btn:
            errors = []
            # Check all Teacher_IDs in periods_config exist in teachers_df
            known_ids = set(teachers_df["Teacher_ID"].astype(str).str.strip())
            for _, row in periods_df.iterrows():
                tid = str(row["Teacher_ID"]).strip()
                if tid in SPECIAL_IDS:
                    continue
                for part in tid.split("|"):
                    part = part.strip()
                    if part and part not in known_ids:
                        errors.append(f"Unknown Teacher_ID `{part}` in {row['Class']}{row['Section']} — {row['Subject']}")

            if errors:
                st.error("❌ Validation errors found:")
                for e in errors[:15]:
                    st.markdown(f"- {e}")
                if len(errors) > 15:
                    st.markdown(f"... and {len(errors)-15} more.")
            else:
                # Run generator
                best_tt, best_ts, best_up = None, None, None
                best_score = -9999

                with st.spinner(f"Generating ({n_attempts} attempt(s))…"):
                    for attempt in range(n_attempts):
                        rseed = seed_val if seed_val > 0 else random.randint(1, 99999)
                        random.seed(rseed + attempt)
                        tt, ts, up = generate_timetable(
                            periods_df.copy(), teachers_df.copy()
                        )
                        score = -len(up)  # fewer unplaced = better
                        if score > best_score:
                            best_score = score
                            best_tt, best_ts, best_up = tt, ts, up

                st.session_state["timetable"]    = best_tt
                st.session_state["teacher_sched"] = best_ts

                placed_count = sum(
                    1 for cs in best_tt.values()
                    for day in cs.values()
                    for v in day.values() if v
                )
                st.success(f"✅ Timetable generated! **{placed_count}** periods placed. "
                           f"**{len(best_up)}** unplaced.")

                if best_up:
                    with st.expander(f"⚠️ {len(best_up)} unplaced periods — click to review"):
                        st.dataframe(pd.DataFrame(best_up), hide_index=True,
                                     use_container_width=True)

        # --- Display generated timetable ---
        if st.session_state["timetable"]:
            tt = st.session_state["timetable"]
            st.markdown("---")
            st.markdown("### 📊 View Generated Timetable")

            view_mode = st.radio("View by:", ["Class/Section","Teacher"], horizontal=True,
                                 key="gen_view_mode")

            if view_mode == "Class/Section":
                cs_options = sorted(tt.keys())
                sel_cs = st.selectbox("Select Class–Section", cs_options, key="gen_sel_cs")
                st.markdown(render_class_grid(sel_cs, tt), unsafe_allow_html=True)

                # Export
                tt_df = timetable_to_df(tt, teachers_df)
                cs_df = tt_df[tt_df["Class_Section"]==sel_cs].drop(
                    columns=["Class_Section"]).sort_values(["Day","Period"])
                st.markdown(export_html(cs_df, f"Timetable_{sel_cs}"), unsafe_allow_html=True)

            else:  # Teacher view
                tt_df = timetable_to_df(tt, teachers_df)
                t_options = sorted(tt_df["Teacher"].dropna().unique())
                sel_t = st.selectbox("Select Teacher", t_options, key="gen_sel_t")
                t_df = tt_df[tt_df["Teacher"]==sel_t][
                    ["Day","Period","Time","Class","Section","Subject"]
                ].sort_values(["Day","Period"])
                st.dataframe(t_df, hide_index=True, use_container_width=True)
                st.markdown(export_html(t_df, f"{sel_t}_Schedule"), unsafe_allow_html=True)

            # Full export
            st.markdown("---")
            full_df = timetable_to_df(tt, teachers_df).drop(columns=["Class_Section"])
            dl1, dl2 = st.columns(2)
            with dl1:
                st.download_button(
                    "📥 Download Full Timetable (CSV)",
                    data=full_df.to_csv(index=False).encode(),
                    file_name="VPS_Generated_Timetable.csv",
                    mime="text/csv", use_container_width=True
                )
            with dl2:
                st.markdown(export_html(full_df, "VPS Complete Timetable"), unsafe_allow_html=True)

            # Teacher workload summary
            with st.expander("👨‍🏫 Teacher Workload Summary"):
                wl = (timetable_to_df(tt, teachers_df)
                      .groupby("Teacher").size().reset_index(name="Total Periods")
                      .sort_values("Total Periods", ascending=False))
                st.dataframe(wl, hide_index=True, use_container_width=True)

# ============================================================
# HELPER: require timetable for tabs 1–4
# ============================================================
def tt_required(tab_name):
    st.info(f"ℹ️ **{tab_name}** is available once a timetable has been generated. "
            "Go to the **🔄 Timetable Generator** tab and click Generate.")

timetable    = st.session_state.get("timetable")
teacher_sched = st.session_state.get("teacher_sched")
tt_df_full   = timetable_to_df(timetable, teachers_df) if (timetable and data_ready) else None

# ============================================================
# TAB 1 — MASTER EDITOR
# ============================================================
with tab1:
    if not data_ready:
        st.warning("⚠️ Upload both CSV files first.")
    elif timetable is None:
        tt_required("Master Editor")
    else:
        st.markdown('<div class="section-head"><h3>🗂️ Master Timetable Editor</h3>'
                    'Edit periods directly. Changes are reflected in Class and Teacher views.</div>',
                    unsafe_allow_html=True)

        edited = st.data_editor(
            tt_df_full.drop(columns=["Class_Section"]),
            num_rows="dynamic", use_container_width=True, height=500
        )

        ec1, ec2, ec3 = st.columns(3)
        with ec1:
            st.download_button(
                "💾 Download as CSV",
                data=edited.to_csv(index=False).encode(),
                file_name="VPS_Master_Timetable.csv",
                mime="text/csv", use_container_width=True
            )
        with ec2:
            st.markdown(export_html(edited, "VPS Master Timetable"), unsafe_allow_html=True)
        with ec3:
            if st.button("🔄 Rebuild views from edits", use_container_width=True):
                # Rebuild timetable dict from edited df
                new_tt = build_empty_grids(periods_df, teachers_df)[0]
                for _, row in edited.iterrows():
                    cs = f"{int(row['Class'])}{row['Section']}"
                    day = row["Day"]
                    per = row["Period"]
                    if cs in new_tt and day in new_tt[cs] and per in new_tt[cs][day]:
                        new_tt[cs][day][per] = {
                            "subject":     row["Subject"],
                            "teacher_id":  row["Teacher_ID"],
                            "teacher_name":row["Teacher"],
                        }
                st.session_state["timetable"] = new_tt
                st.success("✅ Timetable updated from edits.")
                st.rerun()

# ============================================================
# TAB 2 — CLASS VIEW
# ============================================================
with tab2:
    if not data_ready:
        st.warning("⚠️ Upload both CSV files first.")
    elif timetable is None:
        tt_required("Class View")
    else:
        st.markdown('<div class="section-head"><h3>📘 Class Timetable View</h3></div>',
                    unsafe_allow_html=True)

        cs_list = sorted(timetable.keys())
        cv1, cv2 = st.columns([1,3])
        with cv1:
            sel_cs2 = st.selectbox("Class–Section", cs_list, key="cv_sel")

        st.markdown(render_class_grid(sel_cs2, timetable), unsafe_allow_html=True)

        # Subject-teacher legend for this section
        cls2 = int(sel_cs2[:-1])
        sec2 = sel_cs2[-1]
        legend_rows = periods_df[
            (periods_df["Class"]==cls2) & (periods_df["Section"]==sec2)
        ][["Subject","Teacher_ID","Periods_Per_Week"]].copy()
        legend_rows["Teacher"] = legend_rows["Teacher_ID"].apply(
            lambda tid: teacher_name(str(tid).split("|")[0].strip(), teachers_df)
            if str(tid) not in SPECIAL_IDS else str(tid)
        )
        with st.expander("📋 Subject–Teacher legend for this section"):
            st.dataframe(legend_rows[["Subject","Teacher","Periods_Per_Week"]],
                         hide_index=True, use_container_width=True)

        cs_flat = tt_df_full[tt_df_full["Class_Section"]==sel_cs2].drop(
            columns=["Class_Section"]).sort_values(["Day","Period"])
        st.markdown(export_html(cs_flat, f"Timetable_{sel_cs2}"), unsafe_allow_html=True)

# ============================================================
# TAB 3 — TEACHER VIEW
# ============================================================
with tab3:
    if not data_ready:
        st.warning("⚠️ Upload both CSV files first.")
    elif timetable is None:
        tt_required("Teacher View")
    else:
        st.markdown('<div class="section-head"><h3>🧑‍🏫 Teacher Schedule View</h3></div>',
                    unsafe_allow_html=True)

        # Only real (non-special, non-vacant) teachers who appear in timetable
        t_in_tt = sorted(
            t for t in tt_df_full["Teacher"].dropna().unique()
            if t not in {"Science Lab","Co-Scholastic","Class Teacher","COSCHO","SCILAB"}
        )
        sel_t3 = st.selectbox("Select Teacher", t_in_tt, key="tv_sel")

        t3_df = tt_df_full[tt_df_full["Teacher"]==sel_t3][
            ["Day","Period","Time","Class","Section","Subject"]
        ].sort_values(["Day","Period"])

        # Info banner
        t3_row = teachers_df[teachers_df["Teacher_Name"]==sel_t3]
        if not t3_row.empty:
            ri = t3_row.iloc[0]
            ms_flag = str(ri["Teaches_MS"]).strip().lower() == "yes"
            st.markdown(
                f"**{sel_t3}** &nbsp;|&nbsp; Role: `{ri['Role']}` &nbsp;|&nbsp; "
                f"Subjects: `{ri['Subjects']}`" +
                (" &nbsp; ⚠️ *Also teaches Middle School — verify availability*"
                 if ms_flag else ""),
                unsafe_allow_html=False
            )

        tc1, tc2 = st.columns([2,1])
        with tc1:
            st.dataframe(t3_df, hide_index=True, use_container_width=True)
        with tc2:
            st.metric("Total periods/week", len(t3_df))
            daily = t3_df.groupby("Day").size()
            for day, cnt in daily.items():
                st.write(f"**{day}:** {cnt} periods")

        st.markdown(export_html(t3_df, f"{sel_t3}_Schedule"), unsafe_allow_html=True)

# ============================================================
# TAB 4 — SMART SUBSTITUTION ENGINE
# ============================================================
with tab4:
    if not data_ready:
        st.warning("⚠️ Upload both CSV files first.")
    elif timetable is None:
        tt_required("Smart Substitution")
    else:
        st.markdown('<div class="section-head"><h3>🧠 Smart Substitution Engine</h3>'
                    'Manages daily absences with priority-based, constraint-aware candidate selection.'
                    '</div>', unsafe_allow_html=True)

        # Bug Fix #4: substitution log in session state only
        if "sub_log" not in st.session_state:
            st.session_state["sub_log"] = []
        if "assigned_subs" not in st.session_state:
            st.session_state["assigned_subs"] = []

        sa1, sa2 = st.columns([1,2])
        with sa1:
            st.markdown("#### Select Absent Teacher")
            absent_day = st.selectbox(
                "Day", ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"],
                key="sub_day"
            )
            # Only real teachers in the timetable
            all_real_teachers = sorted(
                r["Teacher_Name"] for _, r in teachers_df.iterrows()
                if str(r.get("Vacant","No")).strip().lower() != "yes"
                and str(r.get("Role","")).strip().upper()
                   not in ("","VACANT")
            )
            absent_name = st.selectbox("Absent Teacher", all_real_teachers, key="sub_teacher")

            # Get Teacher_ID
            absent_row = teachers_df[teachers_df["Teacher_Name"]==absent_name]
            absent_tid = absent_row.iloc[0]["Teacher_ID"] if not absent_row.empty else None

            if st.button("🗑️ Clear today's assignments", key="sub_clear"):
                st.session_state["assigned_subs"] = [
                    s for s in st.session_state["assigned_subs"]
                    if s["day"] != absent_day
                ]
                st.rerun()

        with sa2:
            if absent_tid is None:
                st.error("Teacher not found in teachers.csv")
            else:
                # Find all periods this teacher has on absent_day
                teacher_periods_today = []
                for cs_key, days_d in timetable.items():
                    if absent_day not in days_d:
                        continue
                    for period, val in days_d[absent_day].items():
                        if val and val.get("teacher_id") == absent_tid:
                            teacher_periods_today.append({
                                "cs_key":  cs_key,
                                "period":  period,
                                "subject": val["subject"],
                            })
                teacher_periods_today.sort(key=lambda x: x["period"])

                if not teacher_periods_today:
                    st.success(f"✅ **{absent_name}** has no periods on **{absent_day}**.")
                else:
                    st.markdown(f"**{absent_name}** has **{len(teacher_periods_today)}** "
                                f"period(s) on {absent_day} to cover:")

                    # Weekly sub counts from log (Mon–Sun window)
                    today = datetime.date.today()
                    week_start = today - datetime.timedelta(days=today.weekday())
                    week_end   = week_start + datetime.timedelta(days=6)
                    weekly_sub_counts = {}
                    for entry in st.session_state["sub_log"]:
                        try:
                            d = datetime.date.fromisoformat(entry["date"])
                        except Exception:
                            continue
                        if week_start <= d <= week_end:
                            sub = entry["substitute_id"]
                            weekly_sub_counts[sub] = weekly_sub_counts.get(sub, 0) + 1

                    for slot in teacher_periods_today:
                        cs_key  = slot["cs_key"]
                        period  = slot["period"]
                        subject = slot["subject"]

                        cls_num = int(cs_key[:-1])
                        period_time = get_time(cls_num, absent_day, period)

                        st.markdown(f"---")
                        st.markdown(f"#### 🕒 {period} ({period_time}) — "
                                    f"Class **{cs_key}** — *{subject}*")

                        already = next(
                            (s for s in st.session_state["assigned_subs"]
                             if s["period"]==period and s["day"]==absent_day
                             and s["cs_key"]==cs_key),
                            None
                        )

                        if already:
                            st.success(f"✅ Assigned: **{already['substitute_name']}**")
                            col_save, col_undo = st.columns(2)
                            with col_save:
                                if st.button(f"💾 Confirm & Log (P{period}_{cs_key})",
                                             key=f"log_{period}_{cs_key}"):
                                    st.session_state["sub_log"].append({
                                        "date":           str(today),
                                        "day":            absent_day,
                                        "period":         period,
                                        "class_section":  cs_key,
                                        "subject":        subject,
                                        "absent_name":    absent_name,
                                        "absent_id":      absent_tid,
                                        "substitute_name":already["substitute_name"],
                                        "substitute_id":  already["substitute_id"],
                                    })
                                    st.success("Logged ✓")
                            with col_undo:
                                if st.button(f"↩️ Undo (P{period}_{cs_key})",
                                             key=f"undo_{period}_{cs_key}"):
                                    st.session_state["assigned_subs"] = [
                                        s for s in st.session_state["assigned_subs"]
                                        if not (s["period"]==period and s["day"]==absent_day
                                                and s["cs_key"]==cs_key)
                                    ]
                                    st.rerun()
                            continue

                        # --- Build candidate list ---
                        # Who is busy this period (teaching or already subbing)?
                        busy_teaching = {
                            val["teacher_id"]
                            for cs2, days2 in timetable.items()
                            for p2, val in days2.get(absent_day, {}).items()
                            if p2 == period and val
                        }
                        busy_subbing = {
                            s["substitute_id"]
                            for s in st.session_state["assigned_subs"]
                            if s["period"] == period and s["day"] == absent_day
                        }
                        busy = busy_teaching | busy_subbing | {absent_tid}

                        # Teachers of same class-section (Priority 1 base pool)
                        same_section_tids = {
                            val["teacher_id"]
                            for p2, val in timetable.get(cs_key, {}).get(absent_day, {}).items()
                            if val
                        }
                        # Also add teachers who teach that subject anywhere (Priority 2 base pool)
                        # Find subject-matching teachers from periods_df
                        subj_match_tids = set(
                            str(r["Teacher_ID"]).strip()
                            for _, r in periods_df[periods_df["Subject"]==subject].iterrows()
                            if str(r["Teacher_ID"]).strip() not in SPECIAL_IDS
                        )

                        candidates_p1 = []
                        candidates_p2 = []

                        for _, trow in teachers_df.iterrows():
                            tid2  = str(trow["Teacher_ID"]).strip()
                            tname2= str(trow["Teacher_Name"]).strip()
                            role2 = str(trow["Role"]).strip().upper()
                            ms2   = str(trow.get("Teaches_MS","No")).strip().lower() == "yes"
                            vac2  = str(trow.get("Vacant","No")).strip().lower() == "yes"

                            if tid2 in busy or vac2:
                                continue
                            if role2 in NO_SUB_ROLES:
                                continue
                            if not can_give_sub(role2):
                                continue

                            # Subject Coordinator weekly cap
                            if role2 == "SUBJECT COORDINATOR":
                                wk_count = weekly_sub_counts.get(tid2, 0)
                                # Also count today's assigned subs
                                wk_count += sum(
                                    1 for s in st.session_state["assigned_subs"]
                                    if s["substitute_id"] == tid2
                                )
                                if wk_count >= SUB_COORD_MAX_WK:
                                    continue

                            # PE blocked periods
                            if is_pe_teacher(tid2, teachers_df):
                                if absent_day != "Saturday" and period in PE_BLOCKED_SUBS:
                                    continue

                            # Daily load check
                            day_load = sum(
                                1 for p2, v in timetable.get(tid2, {teacher_sched.get(tid2,{}).get(absent_day,{})}).items()
                                if v
                            )
                            # Use teacher_sched for accurate load
                            ts_day = st.session_state.get("teacher_sched",{}).get(tid2,{}).get(absent_day,{})
                            day_load = sum(1 for v in ts_day.values() if v)
                            # Add already-assigned subs today
                            day_load += sum(
                                1 for s in st.session_state["assigned_subs"]
                                if s["substitute_id"] == tid2 and s["day"] == absent_day
                            )
                            if day_load >= REGULAR_MAX_LOAD:
                                continue

                            wk_subs = weekly_sub_counts.get(tid2, 0)

                            candidate = {
                                "Teacher_ID":    tid2,
                                "Name":          tname2,
                                "Role":          role2,
                                "Day Load":      day_load,
                                "Subs This Week":wk_subs,
                                "⚠️ Also MS":    "⚠️ Yes" if ms2 else "",
                            }

                            # Build visual period schedule for this teacher
                            ts_day_full = st.session_state.get("teacher_sched",{}).get(tid2,{}).get(absent_day,{})
                            schedule_vis = ""
                            all_day_slots = get_slots(cls_num, absent_day)
                            for px in all_day_slots:
                                if px == period:
                                    schedule_vis += f"🟨{px} "
                                elif ts_day_full.get(px):
                                    schedule_vis += f"🟥{px} "
                                else:
                                    schedule_vis += f"🟩{px} "
                            candidate["Schedule"] = schedule_vis.strip()

                            is_p1 = (tid2 in same_section_tids)
                            is_p2_subj = (tid2 in subj_match_tids)

                            if is_p1:
                                candidates_p1.append(candidate)
                            elif is_p2_subj:
                                candidates_p2.append(candidate)
                            # else: available but neither — still show in P2
                            else:
                                candidates_p2.append(candidate)

                        # Sort by subs this week (fewest first)
                        candidates_p1.sort(key=lambda x: x["Subs This Week"])
                        candidates_p2.sort(key=lambda x: x["Subs This Week"])

                        st.markdown("**🟩 Free &nbsp; 🟥 Busy &nbsp; 🟨 Proposed sub slot**")

                        col_p1, col_p2 = st.columns(2)

                        with col_p1:
                            st.markdown("**🥇 Priority 1** — Same class-section teachers")
                            if candidates_p1:
                                disp1 = pd.DataFrame(candidates_p1)[
                                    ["Name","Role","Day Load","Subs This Week","⚠️ Also MS","Schedule"]
                                ]
                                st.dataframe(disp1, hide_index=True, use_container_width=True)
                                sel1 = st.selectbox(
                                    "Assign →",
                                    ["— select —"] + [c["Name"] for c in candidates_p1],
                                    key=f"sel_p1_{period}_{cs_key}"
                                )
                                if sel1 != "— select —":
                                    sel1_tid = next(
                                        c["Teacher_ID"] for c in candidates_p1
                                        if c["Name"] == sel1
                                    )
                                    st.session_state["assigned_subs"].append({
                                        "day":            absent_day,
                                        "period":         period,
                                        "cs_key":         cs_key,
                                        "substitute_name":sel1,
                                        "substitute_id":  sel1_tid,
                                    })
                                    st.rerun()
                            else:
                                st.write("No candidates.")

                        with col_p2:
                            st.markdown("**🥈 Priority 2** — Subject-match / other free teachers")
                            if candidates_p2:
                                disp2 = pd.DataFrame(candidates_p2)[
                                    ["Name","Role","Day Load","Subs This Week","⚠️ Also MS","Schedule"]
                                ]
                                st.dataframe(disp2, hide_index=True, use_container_width=True)
                                sel2 = st.selectbox(
                                    "Assign →",
                                    ["— select —"] + [c["Name"] for c in candidates_p2],
                                    key=f"sel_p2_{period}_{cs_key}"
                                )
                                if sel2 != "— select —":
                                    sel2_tid = next(
                                        c["Teacher_ID"] for c in candidates_p2
                                        if c["Name"] == sel2
                                    )
                                    st.session_state["assigned_subs"].append({
                                        "day":            absent_day,
                                        "period":         period,
                                        "cs_key":         cs_key,
                                        "substitute_name":sel2,
                                        "substitute_id":  sel2_tid,
                                    })
                                    st.rerun()
                            else:
                                st.write("No candidates.")

        # --- Substitution Log ---
        st.markdown("---")
        st.markdown("### 📋 Substitution Log (this session)")
        if st.session_state["sub_log"]:
            log_df = pd.DataFrame(st.session_state["sub_log"])
            st.dataframe(log_df, hide_index=True, use_container_width=True)
            dl_c1, dl_c2 = st.columns(2)
            with dl_c1:
                st.download_button(
                    "📥 Download Log (CSV)",
                    data=log_df.to_csv(index=False).encode(),
                    file_name=f"Sub_Log_{datetime.date.today()}.csv",
                    mime="text/csv", use_container_width=True
                )
            with dl_c2:
                st.markdown(export_html(log_df, "Substitution Log"), unsafe_allow_html=True)
            if st.button("🗑️ Clear entire log", key="clear_log"):
                st.session_state["sub_log"] = []
                st.rerun()
        else:
            st.info("No substitutions logged yet this session.")
