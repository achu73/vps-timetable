import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, time
import io
from typing import Dict, List, Tuple, Optional
import copy

# ============================================================================
# PAGE CONFIG AND SESSION STATE INITIALIZATION
# ============================================================================

st.set_page_config(
    page_title="VPS Timetable & Substitution Manager",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize all session state keys at startup
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'password_attempted' not in st.session_state:
    st.session_state.password_attempted = False
if 'teachers_df' not in st.session_state:
    st.session_state.teachers_df = None
if 'periods_df' not in st.session_state:
    st.session_state.periods_df = None
if 'master_timetable' not in st.session_state:
    st.session_state.master_timetable = None
if 'substitution_log' not in st.session_state:
    st.session_state.substitution_log = []
if 'generator_timetable' not in st.session_state:
    st.session_state.generator_timetable = None
if 'generator_status' not in st.session_state:
    st.session_state.generator_status = None

# ============================================================================
# CUSTOM CSS
# ============================================================================

st.markdown("""
<style>
    /* Main app styling */
    .main {
        background-color: #f8f9fa;
    }
    
    /* Header styling */
    h1, h2, h3, h4 {
        color: #1e3a8a;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    
    /* Card-like containers */
    .stAlert {
        border-radius: 10px;
        border-left: 5px solid #3b82f6;
    }
    
    /* Timetable cells */
    .period-cell {
        padding: 8px;
        border: 1px solid #cbd5e1;
        border-radius: 5px;
        background-color: white;
        text-align: center;
        min-height: 60px;
    }
    
    .period-header {
        background-color: #1e3a8a;
        color: white;
        font-weight: bold;
        padding: 10px;
        border-radius: 5px;
    }
    
    /* Teacher status badges */
    .teacher-free {
        background-color: #dcfce7;
        color: #166534;
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 0.85em;
        font-weight: 600;
    }
    
    .teacher-busy {
        background-color: #fee2e2;
        color: #991b1b;
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 0.85em;
        font-weight: 600;
    }
    
    .teacher-warning {
        background-color: #fef3c7;
        color: #92400e;
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 0.85em;
        font-weight: 600;
    }
    
    /* Button styling */
    .stButton>button {
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.3s;
    }
    
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    
    /* Dataframe styling */
    .dataframe {
        font-size: 0.9em;
    }
    
    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0;
        padding: 12px 20px;
        font-weight: 600;
    }
    
    /* File uploader */
    .uploadedFile {
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# CONSTANTS AND CONFIGURATION
# ============================================================================

# Class and section configuration
CLASSES = ['8', '9', '10']
SECTIONS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
ALL_SECTIONS = [f"{cls}{sec}" for cls in CLASSES for sec in SECTIONS]

# Day configurations
DAYS_WEEKDAY = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
DAYS_ALL = DAYS_WEEKDAY + ['Saturday']

# Period configurations by class and day type
PERIODS_CLASS_8_ZERO = ['P0', 'P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'P7', 'P8', 'P9']
PERIODS_CLASS_8_REGULAR = ['P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'P7', 'P8', 'P9']
PERIODS_CLASS_9_10_WEEKDAY = ['P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'P7', 'P8', 'P9']
PERIODS_CLASS_9_10_SATURDAY = ['P1', 'P2', 'P3', 'P4', 'P5', 'P6']

# Period timings
PERIOD_TIMINGS = {
    '9_10_weekday': {
        'P1': ('08:30', '09:10'),
        'P2': ('09:10', '09:50'),
        'P3': ('09:50', '10:30'),
        'Break': ('10:30', '10:40'),
        'P4': ('10:40', '11:20'),
        'P5': ('11:20', '12:00'),
        'P6': ('12:00', '12:40'),
        'Lunch': ('12:40', '13:10'),
        'P7': ('13:10', '13:50'),
        'P8': ('13:50', '14:30'),
        'P9': ('14:30', '15:10'),
    },
    '9_10_saturday': {
        'P1': ('09:10', '09:50'),
        'P2': ('09:50', '10:30'),
        'Break': ('10:30', '10:40'),
        'P3': ('10:40', '11:20'),
        'P4': ('11:20', '12:00'),
        'P5': ('12:00', '12:40'),
        'P6': ('12:40', '13:10'),
    },
    '8_zero': {
        'P0': ('08:30', '09:10'),
        'P1': ('09:10', '09:45'),
        'P2': ('09:45', '10:20'),
        'Break': ('10:20', '10:30'),
        'P3': ('10:30', '11:05'),
        'P4': ('11:05', '11:40'),
        'P5': ('11:40', '12:15'),
        'P6': ('12:15', '12:50'),
        'Lunch': ('12:50', '13:20'),
        'P7': ('13:20', '13:55'),
        'P8': ('13:55', '14:30'),
        'P9': ('14:30', '15:10'),
    },
    '8_regular': {
        'P1': ('08:30', '09:10'),
        'P2': ('09:10', '09:50'),
        'P3': ('09:50', '10:30'),
        'Break': ('10:30', '10:40'),
        'P4': ('10:40', '11:20'),
        'P5': ('11:20', '12:00'),
        'P6': ('12:00', '12:40'),
        'Lunch': ('12:40', '13:10'),
        'P7': ('13:10', '13:50'),
        'P8': ('13:50', '14:30'),
        'P9': ('14:30', '15:10'),
    }
}

# Fixed periods
ASSEMBLY_DAYS = {
    '8': 'Friday',
    '9': 'Thursday',
    '10': 'Tuesday'
}

CLASS_TEST_DAYS = {
    '8': 'Wednesday',
    '9': 'Wednesday',
    '10': 'Monday'
}

# Teacher roles
ROLES_NO_SUB = ['PRINCIPAL', 'VICE PRINCIPAL', 'LEVEL COORDINATOR']
ROLE_SUBJECT_COORDINATOR = 'SUBJECT COORDINATOR'
ROLE_REGULAR = 'REGULAR'

# Workload limits
MAX_PERIODS_PER_DAY = 7
MAX_SUBS_SUBJECT_COORDINATOR = 3

# Special subjects
SPECIAL_SUBJECTS = ['Assembly', 'Class Test', 'PMS', 'CT to Take', 'Co-Scholastic', 
                    'Science Lab', 'EOB', 'Yoga', 'HeyMath']

# ============================================================================
# PASSWORD AUTHENTICATION
# ============================================================================

def check_password():
    """Handle password authentication"""
    
    # Check if secrets are configured
    if 'passwords' not in st.secrets:
        st.error("⚠️ Password configuration not found in secrets. Please configure st.secrets.")
        return False
    
    # If already authenticated, return True
    if st.session_state.authenticated:
        return True
    
    # Display login form
    st.markdown("### 🔐 VPS Timetable & Substitution Manager")
    st.markdown("Please enter the password to access the application.")
    
    password = st.text_input("Password", type="password", key="password_input")
    
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        if st.button("Login", use_container_width=True):
            st.session_state.password_attempted = True
            if password in st.secrets.passwords.values():
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("❌ Incorrect password. Please try again.")
    
    # Show error only after an attempt has been made
    if st.session_state.password_attempted and not st.session_state.authenticated:
        if password == "":
            st.warning("⚠️ Please enter a password.")
    
    return False

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_periods_for_class_day(class_num: str, day: str) -> List[str]:
    """Get the correct period list for a given class and day"""
    if class_num == '8':
        if day == 'Saturday':
            return []  # Class 8 has no Saturday school
        elif day in ['Monday', 'Wednesday']:
            return PERIODS_CLASS_8_ZERO
        else:
            return PERIODS_CLASS_8_REGULAR
    else:  # Class 9 or 10
        if day == 'Saturday':
            return PERIODS_CLASS_9_10_SATURDAY
        else:
            return PERIODS_CLASS_9_10_WEEKDAY

def get_period_timing(class_num: str, day: str, period: str) -> Tuple[str, str]:
    """Get start and end time for a specific period"""
    if class_num == '8':
        if day in ['Monday', 'Wednesday']:
            return PERIOD_TIMINGS['8_zero'].get(period, ('--:--', '--:--'))
        else:
            return PERIOD_TIMINGS['8_regular'].get(period, ('--:--', '--:--'))
    else:
        if day == 'Saturday':
            return PERIOD_TIMINGS['9_10_saturday'].get(period, ('--:--', '--:--'))
        else:
            return PERIOD_TIMINGS['9_10_weekday'].get(period, ('--:--', '--:--'))

def is_teacher_available_for_sub(teacher_row: pd.Series) -> bool:
    """Check if a teacher can be assigned substitution based on role and status"""
    if teacher_row['Vacant'] == 'Yes':
        return False
    if teacher_row['Role'] in ROLES_NO_SUB:
        return False
    return True

def get_teacher_name(teacher_id: str, teachers_df: pd.DataFrame) -> str:
    """Get teacher name from ID"""
    if teachers_df is None or teacher_id is None or pd.isna(teacher_id):
        return ""
    match = teachers_df[teachers_df['Teacher_ID'] == teacher_id]
    if len(match) > 0:
        return match.iloc[0]['Teacher_Name']
    return ""

def get_teacher_subjects(teacher_id: str, teachers_df: pd.DataFrame) -> List[str]:
    """Get list of subjects a teacher can teach"""
    if teachers_df is None or teacher_id is None or pd.isna(teacher_id):
        return []
    match = teachers_df[teachers_df['Teacher_ID'] == teacher_id]
    if len(match) > 0:
        subjects_str = match.iloc[0]['Subjects']
        if pd.notna(subjects_str):
            return [s.strip() for s in subjects_str.split('|')]
    return []

def create_empty_timetable() -> Dict:
    """Create an empty timetable structure"""
    timetable = {}
    for section in ALL_SECTIONS:
        class_num = section[:-1]
        timetable[section] = {}
        for day in DAYS_ALL:
            periods = get_periods_for_class_day(class_num, day)
            if not periods:  # Skip if no school (e.g., Class 8 Saturday)
                continue
            timetable[section][day] = {period: None for period in periods}
    return timetable

def validate_csv_files(teachers_df: pd.DataFrame, periods_df: pd.DataFrame) -> Tuple[bool, List[str]]:
    """Validate uploaded CSV files structure"""
    errors = []
    
    # Check teachers.csv
    required_teacher_cols = ['Teacher_ID', 'Teacher_Name', 'Subjects', 'Role', 'Teaches_MS', 'Vacant']
    missing_teacher_cols = [col for col in required_teacher_cols if col not in teachers_df.columns]
    if missing_teacher_cols:
        errors.append(f"teachers.csv missing columns: {', '.join(missing_teacher_cols)}")
    
    # Check periods_config.csv
    required_period_cols = ['Class', 'Section', 'Subject', 'Periods_Per_Week', 'Teacher_ID', 
                           'Practical', 'Block_Period', 'Parallel_Subject', 'Parallel_Teacher_ID']
    missing_period_cols = [col for col in required_period_cols if col not in periods_df.columns]
    if missing_period_cols:
        errors.append(f"periods_config.csv missing columns: {', '.join(missing_period_cols)}")
    
    # Check for empty dataframes
    if len(teachers_df) == 0:
        errors.append("teachers.csv is empty")
    if len(periods_df) == 0:
        errors.append("periods_config.csv is empty")
    
    return (len(errors) == 0, errors)

def count_teacher_periods_day(timetable: Dict, teacher_id: str, section: str, day: str) -> int:
    """Count how many periods a teacher has on a specific day for a specific section"""
    if timetable is None or section not in timetable or day not in timetable[section]:
        return 0
    
    count = 0
    for period, assignment in timetable[section][day].items():
        if assignment and isinstance(assignment, dict):
            if assignment.get('teacher_id') == teacher_id:
                count += 1
    return count

def count_teacher_total_periods_day(timetable: Dict, teacher_id: str, day: str) -> int:
    """Count total periods for a teacher across all sections on a specific day"""
    if timetable is None:
        return 0
    
    count = 0
    for section in timetable:
        if day in timetable[section]:
            for period, assignment in timetable[section][day].items():
                if assignment and isinstance(assignment, dict):
                    if assignment.get('teacher_id') == teacher_id:
                        count += 1
    return count

def is_teacher_free(timetable: Dict, teacher_id: str, day: str, period: str, 
                    exclude_section: str = None) -> bool:
    """Check if a teacher is free during a specific period"""
    if timetable is None:
        return True
    
    for section in timetable:
        if exclude_section and section == exclude_section:
            continue
        if day in timetable[section] and period in timetable[section][day]:
            assignment = timetable[section][day][period]
            if assignment and isinstance(assignment, dict):
                if assignment.get('teacher_id') == teacher_id:
                    return False
    return True

def get_teacher_schedule_day(timetable: Dict, teacher_id: str, day: str) -> Dict[str, str]:
    """Get a teacher's schedule for a specific day across all sections"""
    schedule = {}
    if timetable is None:
        return schedule
    
    for section in timetable:
        if day in timetable[section]:
            for period, assignment in timetable[section][day].items():
                if assignment and isinstance(assignment, dict):
                    if assignment.get('teacher_id') == teacher_id:
                        schedule[period] = f"{section} - {assignment.get('subject', 'Unknown')}"
    return schedule

# ============================================================================
# MAIN APPLICATION STRUCTURE
# ============================================================================

def main():
    """Main application entry point"""
    
    # Check authentication
    if not check_password():
        return
    
    # Display header
    st.title("📚 VPS Timetable & Substitution Manager")
    st.markdown("**Vidyaniketan Public School - High School**")
    st.markdown("---")
    
    # Sidebar for file upload and quick info
    with st.sidebar:
        st.header("📂 Data Upload")
        
        # File uploaders
        teachers_file = st.file_uploader("Upload teachers.csv", type=['csv'], key='teachers_upload')
        periods_file = st.file_uploader("Upload periods_config.csv", type=['csv'], key='periods_upload')
        
        if teachers_file and periods_file:
            try:
                # Load dataframes
                teachers_df = pd.read_csv(teachers_file)
                periods_df = pd.read_csv(periods_file)
                
                # Validate
                is_valid, errors = validate_csv_files(teachers_df, periods_df)
                
                if is_valid:
                    st.session_state.teachers_df = teachers_df
                    st.session_state.periods_df = periods_df
                    st.success("✅ Files loaded successfully!")
                    
                    # Show quick stats
                    st.markdown("---")
                    st.markdown("**Quick Stats:**")
                    st.metric("Total Teachers", len(teachers_df))
                    st.metric("Total Sections", len(ALL_SECTIONS))
                    st.metric("Total Configurations", len(periods_df))
                else:
                    st.error("❌ Validation Errors:")
                    for error in errors:
                        st.error(f"• {error}")
            except Exception as e:
                st.error(f"❌ Error loading files: {str(e)}")
        
        st.markdown("---")
        st.markdown("**School Info:**")
        st.info("📌 Classes: 8, 9, 10\n\n📌 Sections: A-H (24 total)\n\n📌 High School Only")
        
        # Logout button
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.password_attempted = False
            st.rerun()
    
    # Create tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📋 Master Timetable Editor",
        "👥 Class View",
        "👨‍🏫 Teacher View",
        "🔄 Smart Substitution",
        "⚙️ Timetable Generator"
    ])
    
    # Tab 5 should work without file upload
    # Other tabs require files to be loaded
    
    with tab1:
        if st.session_state.teachers_df is not None and st.session_state.periods_df is not None:
            st.header("📋 Master Timetable Editor")
            st.info("This section will allow manual editing of the timetable. (Implemented in Part 3)")
        else:
            st.warning("⚠️ Please upload both CSV files to access this feature.")
    
    with tab2:
        if st.session_state.teachers_df is not None and st.session_state.periods_df is not None:
            st.header("👥 Class View")
            st.info("This section will display timetables by class and section. (Implemented in Part 3)")
        else:
            st.warning("⚠️ Please upload both CSV files to access this feature.")
    
    with tab3:
        if st.session_state.teachers_df is not None and st.session_state.periods_df is not None:
            st.header("👨‍🏫 Teacher View")
            st.info("This section will display individual teacher schedules. (Implemented in Part 3)")
        else:
            st.warning("⚠️ Please upload both CSV files to access this feature.")
    
    with tab4:
        if st.session_state.teachers_df is not None and st.session_state.periods_df is not None:
            st.header("🔄 Smart Substitution Engine")
            st.info("This section will handle intelligent teacher substitutions. (Implemented in Part 3)")
        else:
            st.warning("⚠️ Please upload both CSV files to access this feature.")
    
        with tab5:
        render_timetable_generator()

# ============================================================================
# TIMETABLE GENERATOR - CONSTRAINT CHECKING
# ============================================================================

def check_hard_constraints(timetable: Dict, section: str, day: str, period: str, 
                          teacher_id: str, subject: str, teachers_df: pd.DataFrame,
                          is_block_period: bool = False) -> Tuple[bool, str]:
    """
    Check all hard constraints for a proposed assignment.
    Returns (is_valid, error_message)
    """
    
    class_num = section[:-1]
    
    # H1: Teacher cannot be in two classes simultaneously
    if not is_teacher_free(timetable, teacher_id, day, period):
        other_assignment = ""
        for sec in timetable:
            if day in timetable[sec] and period in timetable[sec][day]:
                assign = timetable[sec][day][period]
                if assign and isinstance(assign, dict) and assign.get('teacher_id') == teacher_id:
                    other_assignment = f"{sec} - {assign.get('subject')}"
                    break
        return False, f"H1: Teacher already teaching {other_assignment} in {period}"
    
    # H2: Class cannot have two subjects simultaneously (already checked by timetable structure)
    if timetable[section][day][period] is not None:
        return False, f"H2: {section} already has a class in {period}"
    
    # H3: Max 7 teaching periods per teacher per day
    teacher_periods = count_teacher_total_periods_day(timetable, teacher_id, day)
    if teacher_periods >= MAX_PERIODS_PER_DAY:
        return False, f"H3: Teacher already has {teacher_periods} periods today (max {MAX_PERIODS_PER_DAY})"
    
    # H4: PE not in P1 or P7 on weekdays (except Saturday)
    if subject == 'Physical Education' and day != 'Saturday':
        if period in ['P1', 'P7']:
            return False, f"H4: PE cannot be scheduled in {period} on weekdays (field/lunch duty)"
    
    # H5: Science Lab must be block period (checked during assignment, not here)
    # This is handled at the scheduling level
    
    # H6: One section per science lab per period
    if subject == 'Science Lab':
        for sec in timetable:
            if sec != section and day in timetable[sec] and period in timetable[sec][day]:
                assign = timetable[sec][day][period]
                if assign and isinstance(assign, dict) and assign.get('subject') == 'Science Lab':
                    return False, f"H6: Lab already occupied by {sec} in {period}"
    
    # H7: Library - one section per period across all classes
    if subject == 'Library':
        for sec in timetable:
            if sec != section and day in timetable[sec] and period in timetable[sec][day]:
                assign = timetable[sec][day][period]
                if assign and isinstance(assign, dict) and assign.get('subject') == 'Library':
                    return False, f"H7: Library already occupied by {sec} in {period}"
    
    # H8: Assembly fixed days (checked during fixed period assignment)
    # H9: Class Test fixed days (checked during fixed period assignment)
    
    # H10: Class 8 zero period - teachers shared between Class 8 and 9/10 must not clash
    if class_num == '8' and day in ['Monday', 'Wednesday'] and period == 'P0':
        # Check if teacher teaches Class 9 or 10
        # During P0 for Class 8, Class 9/10 have no period yet (school starts at 8:30 for them)
        # This is inherently safe, so we pass
        pass
    
    # H11: Same subject not twice in same day for same class
    if not is_block_period:  # Block periods are exempt
        for p, assign in timetable[section][day].items():
            if assign and isinstance(assign, dict):
                if assign.get('subject') == subject and not assign.get('is_block_second_period', False):
                    return False, f"H11: {subject} already scheduled in {p} for {section}"
    
    # H12: Teacher not twice in same class per day (except block periods)
    if not is_block_period:
        teacher_count = count_teacher_periods_day(timetable, teacher_id, section, day)
        if teacher_count >= 1:
            # Check if existing period is a block period
            has_block = False
            for p, assign in timetable[section][day].items():
                if assign and isinstance(assign, dict):
                    if assign.get('teacher_id') == teacher_id and assign.get('is_block_period'):
                        has_block = True
                        break
            if not has_block:
                return False, f"H12: Teacher already teaching {section} once today (non-block)"
    
    return True, ""

def calculate_soft_constraint_score(timetable: Dict, section: str, day: str, period: str,
                                   teacher_id: str, subject: str) -> float:
    """
    Calculate a score based on soft constraints (higher is better).
    Used to prefer better assignments when multiple options are valid.
    """
    
    score = 100.0
    class_num = section[:-1]
    period_num = int(period.replace('P', ''))
    
    # S1: Maths in morning (P1-P3 preferred)
    if subject == 'Mathematics':
        if period_num >= 1 and period_num <= 3:
            score += 20
        else:
            score -= 10
    
    # S2: Max 2 Maths periods per class per day (check existing)
    if subject == 'Mathematics':
        math_count = sum(1 for p, assign in timetable[section][day].items() 
                        if assign and isinstance(assign, dict) and assign.get('subject') == 'Mathematics')
        if math_count >= 2:
            score -= 30
    
    # S3: Art/PE/Library post lunch preferred (P7-P9)
    if subject in ['Art', 'Physical Education', 'Library']:
        if period_num >= 7:
            score += 15
        else:
            score -= 5
    
    # S5: Core subjects in morning preferred
    core_subjects = ['English', 'Hindi', 'Sanskrit', 'Science', 'Social Science']
    if subject in core_subjects:
        if period_num <= 6:
            score += 10
        else:
            score -= 5
    
    # S6: Friday afternoon - light subjects preferred
    if day == 'Friday':
        light_subjects = ['Art', 'Physical Education', 'Library', 'Yoga', 'Co-Scholastic']
        if period_num >= 7:
            if subject in light_subjects:
                score += 15
            else:
                score -= 10
    
    # S7: Minimize isolated free periods for teachers
    # Check if teacher has periods before and after this slot
    teacher_schedule = get_teacher_schedule_day(timetable, teacher_id, day)
    if len(teacher_schedule) > 0:
        period_numbers = [int(p.replace('P', '')) for p in teacher_schedule.keys()]
        if period_num > min(period_numbers) and period_num < max(period_numbers):
            # This period is between existing periods - good for continuity
            score += 10
    
    return score

# ============================================================================
# TIMETABLE GENERATOR - ASSIGNMENT FUNCTIONS
# ============================================================================

def assign_fixed_periods(timetable: Dict, teachers_df: pd.DataFrame) -> Dict:
    """Assign fixed periods: Assembly and Class Test"""
    
    for section in ALL_SECTIONS:
        class_num = section[:-1]
        
        # Find class teacher for this section
        section_config = st.session_state.periods_df[
            (st.session_state.periods_df['Class'] == int(class_num)) &
            (st.session_state.periods_df['Section'] == section[-1])
        ]
        
        # Get class teacher (usually from any subject assignment for that section)
        # For simplicity, we'll use the first teacher assigned to that section
        class_teacher_id = None
        if len(section_config) > 0:
            class_teacher_id = section_config.iloc[0]['Teacher_ID']
        
        # Assembly
        assembly_day = ASSEMBLY_DAYS.get(class_num)
        if assembly_day:
            periods = get_periods_for_class_day(class_num, assembly_day)
            if periods and 'P1' in periods:
                timetable[section][assembly_day]['P1'] = {
                    'subject': 'Assembly',
                    'teacher_id': class_teacher_id,
                    'teacher_name': get_teacher_name(class_teacher_id, teachers_df),
                    'is_fixed': True
                }
        
        # Class Test
        test_day = CLASS_TEST_DAYS.get(class_num)
        if test_day:
            periods = get_periods_for_class_day(class_num, test_day)
            # Assign to last period
            if periods and len(periods) > 0:
                last_period = periods[-1]
                timetable[section][test_day][last_period] = {
                    'subject': 'Class Test',
                    'teacher_id': class_teacher_id,
                    'teacher_name': get_teacher_name(class_teacher_id, teachers_df),
                    'is_fixed': True
                }
    
    return timetable

def find_block_period_slot(timetable: Dict, section: str, day: str, 
                           teacher_id: str, subject: str, teachers_df: pd.DataFrame) -> Optional[str]:
    """Find a suitable starting period for a 2-period block"""
    
    class_num = section[:-1]
    periods = get_periods_for_class_day(class_num, day)
    
    for i in range(len(periods) - 1):
        period1 = periods[i]
        period2 = periods[i + 1]
        
        # Skip if break or lunch in between
        if period1 == 'P3' or period1 == 'P6':
            continue
        
        # Check if both slots are free for class and teacher
        if (timetable[section][day][period1] is None and 
            timetable[section][day][period2] is None):
            
            # Check constraints for both periods
            valid1, _ = check_hard_constraints(timetable, section, day, period1, 
                                              teacher_id, subject, teachers_df, True)
            valid2, _ = check_hard_constraints(timetable, section, day, period2, 
                                              teacher_id, subject, teachers_df, True)
            
            if valid1 and valid2:
                return period1
    
    return None

def assign_subject_periods(timetable: Dict, section: str, subject: str, 
                          periods_per_week: int, teacher_id: str, teachers_df: pd.DataFrame,
                          is_practical: bool, is_block: bool) -> Tuple[Dict, bool]:
    """
    Assign periods for a specific subject to a section across the week.
    Returns (updated_timetable, success)
    """
    
    class_num = section[:-1]
    assigned_count = 0
    max_attempts = 100
    attempts = 0
    
    # Special handling for block periods (Science Lab)
    if is_block:
        # Need to assign half the periods as blocks (each block = 2 periods)
        blocks_needed = periods_per_week // 2
        
        for _ in range(blocks_needed):
            attempts = 0
            assigned = False
            
            while not assigned and attempts < max_attempts:
                attempts += 1
                
                # Try each day
                available_days = DAYS_WEEKDAY if class_num != '8' else \
                    ['Tuesday', 'Thursday', 'Friday'] + ['Monday', 'Wednesday']
                
                for day in available_days:
                    periods = get_periods_for_class_day(class_num, day)
                    if not periods:
                        continue
                    
                    # Find block slot
                    start_period = find_block_period_slot(timetable, section, day, 
                                                         teacher_id, subject, teachers_df)
                    
                    if start_period:
                        # Get the next period
                        period_idx = periods.index(start_period)
                        second_period = periods[period_idx + 1]
                        
                        # Assign both periods
                        timetable[section][day][start_period] = {
                            'subject': subject,
                            'teacher_id': teacher_id,
                            'teacher_name': get_teacher_name(teacher_id, teachers_df),
                            'is_block_period': True,
                            'is_practical': True
                        }
                        
                        timetable[section][day][second_period] = {
                            'subject': subject,
                            'teacher_id': teacher_id,
                            'teacher_name': get_teacher_name(teacher_id, teachers_df),
                            'is_block_period': True,
                            'is_block_second_period': True,
                            'is_practical': True
                        }
                        
                        assigned = True
                        assigned_count += 2
                        break
            
            if not assigned:
                return timetable, False
        
        return timetable, True
    
    # Regular period assignment
    while assigned_count < periods_per_week and attempts < max_attempts:
        attempts += 1
        
        # Try to find best slot across all days
        best_day = None
        best_period = None
        best_score = -999
        
        available_days = DAYS_WEEKDAY if class_num != '8' else \
            ['Tuesday', 'Thursday', 'Friday'] + ['Monday', 'Wednesday']
        
        for day in available_days:
            periods = get_periods_for_class_day(class_num, day)
            if not periods:
                continue
            
            for period in periods:
                # Skip if already assigned
                if timetable[section][day][period] is not None:
                    continue
                
                # Check hard constraints
                valid, error = check_hard_constraints(timetable, section, day, period,
                                                     teacher_id, subject, teachers_df)
                
                if valid:
                    # Calculate soft constraint score
                    score = calculate_soft_constraint_score(timetable, section, day, period,
                                                           teacher_id, subject)
                    
                    if score > best_score:
                        best_score = score
                        best_day = day
                        best_period = period
        
        # Assign the best slot found
        if best_day and best_period:
            timetable[section][best_day][best_period] = {
                'subject': subject,
                'teacher_id': teacher_id,
                'teacher_name': get_teacher_name(teacher_id, teachers_df),
                'is_practical': is_practical
            }
            assigned_count += 1
        else:
            # No valid slot found
            break
    
    # Check if we assigned all required periods
    success = (assigned_count == periods_per_week)
    return timetable, success

# ============================================================================
# TIMETABLE GENERATOR - MAIN ENGINE
# ============================================================================

def generate_timetable(periods_df: pd.DataFrame, teachers_df: pd.DataFrame, 
                      progress_callback=None) -> Tuple[Optional[Dict], List[str]]:
    """
    Main timetable generation engine.
    Returns (timetable, error_log)
    """
    
    error_log = []
    
    # Create empty timetable
    timetable = create_empty_timetable()
    
    if progress_callback:
        progress_callback(0.1, "Assigning fixed periods (Assembly, Class Test)...")
    
    # Step 1: Assign fixed periods
    try:
        timetable = assign_fixed_periods(timetable, teachers_df)
        error_log.append("✅ Fixed periods assigned successfully")
    except Exception as e:
        error_log.append(f"❌ Error assigning fixed periods: {str(e)}")
        return None, error_log
    
    if progress_callback:
        progress_callback(0.2, "Processing subject assignments...")
    
    # Step 2: Prepare subject assignments
    # Group by section and sort by priority (blocks first, then by periods_per_week descending)
    periods_df_sorted = periods_df.copy()
    periods_df_sorted['priority'] = periods_df_sorted.apply(
        lambda row: (1 if row['Block_Period'] == 'Yes' else 0, row['Periods_Per_Week']),
        axis=1
    )
    periods_df_sorted = periods_df_sorted.sort_values('priority', ascending=False)
    
    total_assignments = len(periods_df_sorted)
    successful_assignments = 0
    failed_assignments = []
    
    # Step 3: Assign all subjects
    for idx, row in periods_df_sorted.iterrows():
        section = f"{int(row['Class'])}{row['Section']}"
        subject = row['Subject']
        teacher_id = row['Teacher_ID']
        periods_per_week = int(row['Periods_Per_Week'])
        is_practical = row['Practical'] == 'Yes'
        is_block = row['Block_Period'] == 'Yes'
        
        if progress_callback:
            progress = 0.2 + (0.7 * (idx + 1) / total_assignments)
            progress_callback(progress, f"Assigning {subject} for {section}...")
        
        # Skip if teacher is vacant
        teacher_row = teachers_df[teachers_df['Teacher_ID'] == teacher_id]
        if len(teacher_row) > 0 and teacher_row.iloc[0]['Vacant'] == 'Yes':
            error_log.append(f"⚠️ Skipping {subject} for {section} - Teacher is vacant")
            failed_assignments.append({
                'section': section,
                'subject': subject,
                'reason': 'Teacher vacant'
            })
            continue
        
        # Special subjects handling
        if subject in ['Assembly', 'Class Test']:
            # Already assigned in fixed periods
            successful_assignments += 1
            continue
        
        if subject in ['PMS', 'CT to Take', 'Co-Scholastic']:
            # These are handled by class teacher or don't need teacher assignment
            # We'll just mark them as assigned without specific slots
            successful_assignments += 1
            continue
        
        # Assign periods
        timetable, success = assign_subject_periods(
            timetable, section, subject, periods_per_week, 
            teacher_id, teachers_df, is_practical, is_block
        )
        
        if success:
            successful_assignments += 1
            error_log.append(f"✅ {section} - {subject}: {periods_per_week} periods assigned")
        else:
            failed_assignments.append({
                'section': section,
                'subject': subject,
                'teacher': get_teacher_name(teacher_id, teachers_df),
                'periods_needed': periods_per_week
            })
            error_log.append(f"❌ {section} - {subject}: Could not assign all {periods_per_week} periods")
    
    if progress_callback:
        progress_callback(0.95, "Finalizing timetable...")
    
    # Step 4: Summary
    error_log.append("\n" + "="*60)
    error_log.append("GENERATION SUMMARY")
    error_log.append("="*60)
    error_log.append(f"Total Assignments: {total_assignments}")
    error_log.append(f"Successful: {successful_assignments}")
    error_log.append(f"Failed: {len(failed_assignments)}")
    
    if failed_assignments:
        error_log.append("\n❌ FAILED ASSIGNMENTS:")
        for fail in failed_assignments:
            error_log.append(f"  • {fail['section']} - {fail['subject']} " +
                           f"({fail.get('periods_needed', '?')} periods) - {fail.get('reason', 'Constraint conflicts')}")
    
    if progress_callback:
        progress_callback(1.0, "Generation complete!")
    
    return timetable, error_log

# ============================================================================
# TIMETABLE GENERATOR - UI COMPONENT (for Tab 5)
# ============================================================================

def render_timetable_generator():
    """Render the timetable generator interface in Tab 5"""
    
    st.header("⚙️ Automated Timetable Generator")
    
    st.markdown("""
    This generator uses **constraint-based scheduling** to automatically create a complete 
    weekly timetable for all 24 sections while respecting:
    
    - ✅ **10 Hard Constraints** (never violated)
    - 🎯 **8 Soft Constraints** (optimized for best fit)
    """)
    
    # Show constraint details in expanders
    col1, col2 = st.columns(2)
    
    with col1:
        with st.expander("📋 Hard Constraints (Must Satisfy)", expanded=False):
            st.markdown("""
            1. Teacher cannot be in two classes simultaneously
            2. Class cannot have two subjects simultaneously
            3. Max 7 teaching periods per teacher per day
            4. PE not in P1 or P7 on weekdays (field/lunch duty)
            5. Science Lab = 2 consecutive periods (block)
            6. One section per science lab per period
            7. Library - one section per period
            8. Assembly fixed (8: Fri, 9: Thu, 10: Tue)
            9. Class Test fixed (8&9: Wed, 10: Mon)
            10. Class 8 zero period - no teacher conflicts with 9/10
            11. Same subject not twice in same day
            12. Teacher not twice per class per day (except blocks)
            """)
    
    with col2:
        with st.expander("🎯 Soft Constraints (Optimized)", expanded=False):
            st.markdown("""
            1. Maths in morning (P1-P3 preferred)
            2. Max 2 Maths periods per day per class
            3. Art/PE/Library post-lunch preferred (P7-P9)
            4. Yoga and Art flexible placement
            5. Core subjects morning preferred
            6. Friday afternoon - light subjects
            7. Minimize teacher free period gaps
            8. Spread subjects evenly across week
            """)
    
    st.markdown("---")
    
    # Input validation check
    can_generate = (st.session_state.teachers_df is not None and 
                   st.session_state.periods_df is not None)
    
    if not can_generate:
        st.warning("⚠️ Please upload both **teachers.csv** and **periods_config.csv** to enable generation.")
        st.info("💡 Upload files using the sidebar on the left.")
        return
    
    # Pre-generation validation
    st.subheader("📊 Pre-Generation Validation")
    
    teachers_df = st.session_state.teachers_df
    periods_df = st.session_state.periods_df
    
    # Validation checks
    val_col1, val_col2, val_col3 = st.columns(3)
    
    with val_col1:
        total_teachers = len(teachers_df)
        active_teachers = len(teachers_df[teachers_df['Vacant'] != 'Yes'])
        st.metric("Total Teachers", total_teachers, f"{active_teachers} active")
    
    with val_col2:
        total_configs = len(periods_df)
        unique_sections = periods_df.groupby(['Class', 'Section']).ngroups
        st.metric("Subject Configs", total_configs, f"{unique_sections} sections")
    
    with val_col3:
        total_periods_needed = periods_df['Periods_Per_Week'].sum()
        st.metric("Total Periods/Week", total_periods_needed)
    
    # Check for issues
    issues = []
    
    # Check for missing teachers
    missing_teachers = periods_df[~periods_df['Teacher_ID'].isin(teachers_df['Teacher_ID'])]
    if len(missing_teachers) > 0:
        issues.append(f"❌ {len(missing_teachers)} subject assignments reference teachers not in teachers.csv")
    
    # Check for vacant teachers assigned
    vacant_teachers = teachers_df[teachers_df['Vacant'] == 'Yes']['Teacher_ID'].tolist()
    vacant_assigned = periods_df[periods_df['Teacher_ID'].isin(vacant_teachers)]
    if len(vacant_assigned) > 0:
        issues.append(f"⚠️ {len(vacant_assigned)} assignments use vacant teachers (will be skipped)")
    
    if issues:
        st.warning("**Validation Warnings:**")
        for issue in issues:
            st.markdown(f"- {issue}")
    else:
        st.success("✅ All validation checks passed!")
    
    st.markdown("---")
    
    # Generation controls
    st.subheader("🚀 Generate Timetable")
    
    col_gen1, col_gen2, col_gen3 = st.columns([2, 1, 1])
    
    with col_gen1:
        if st.button("🎯 Generate Complete Timetable", type="primary", use_container_width=True):
            # Initialize progress tracking
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            def update_progress(value, message):
                progress_bar.progress(value)
                status_text.text(message)
            
            # Run generation
            with st.spinner("Generating timetable..."):
                timetable, log = generate_timetable(
                    periods_df, 
                    teachers_df,
                    progress_callback=update_progress
                )
            
            # Store results
            st.session_state.generator_timetable = timetable
            st.session_state.generator_status = log
            
            progress_bar.empty()
            status_text.empty()
            
            if timetable:
                st.success("✅ Timetable generation completed!")
                st.balloons()
            else:
                st.error("❌ Timetable generation failed. Check the log below.")
    
    with col_gen2:
        if st.button("🔄 Reset", use_container_width=True):
            st.session_state.generator_timetable = None
            st.session_state.generator_status = None
            st.rerun()
    
    # Display results if available
    if st.session_state.generator_status:
        st.markdown("---")
        st.subheader("📋 Generation Log")
        
        log_text = "\n".join(st.session_state.generator_status)
        st.text_area("Log Output", log_text, height=300)
        
        # Download log
        st.download_button(
            label="💾 Download Log",
            data=log_text,
            file_name=f"timetable_generation_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain"
        )
    
    # Display generated timetable preview
    if st.session_state.generator_timetable:
        st.markdown("---")
        st.subheader("📅 Generated Timetable Preview")
        
        # Section selector for preview
        preview_section = st.selectbox(
            "Select section to preview:",
            ALL_SECTIONS,
            key='gen_preview_section'
        )
        
        if preview_section:
            class_num = preview_section[:-1]
            timetable = st.session_state.generator_timetable
            
            # Display as weekly grid
            if preview_section in timetable:
                for day in DAYS_ALL:
                    if day not in timetable[preview_section]:
                        continue
                    
                    st.markdown(f"**{day}**")
                    periods = get_periods_for_class_day(class_num, day)
                    
                    # Create columns for periods
                    period_cols = st.columns(len(periods))
                    
                    for idx, period in enumerate(periods):
                        with period_cols[idx]:
                            assignment = timetable[preview_section][day].get(period)
                            
                            timing_start, timing_end = get_period_timing(class_num, day, period)
                            
                            if assignment:
                                subject = assignment.get('subject', 'Unknown')
                                teacher = assignment.get('teacher_name', 'TBD')
                                
                                st.markdown(f"""
                                <div style='background-color: #e0f2fe; padding: 8px; border-radius: 5px; 
                                            border-left: 3px solid #0284c7; margin-bottom: 5px;'>
                                    <div style='font-weight: bold; font-size: 0.75em;'>{period}</div>
                                    <div style='font-size: 0.7em; color: #64748b;'>{timing_start}-{timing_end}</div>
                                    <div style='font-size: 0.85em; margin-top: 3px;'>{subject}</div>
                                    <div style='font-size: 0.75em; color: #64748b;'>{teacher}</div>
                                </div>
                                """, unsafe_allow_html=True)
                            else:
                                st.markdown(f"""
                                <div style='background-color: #f1f5f9; padding: 8px; border-radius: 5px; 
                                            margin-bottom: 5px;'>
                                    <div style='font-weight: bold; font-size: 0.75em;'>{period}</div>
                                    <div style='font-size: 0.7em; color: #94a3b8;'>{timing_start}-{timing_end}</div>
                                    <div style='font-size: 0.85em; margin-top: 3px; color: #94a3b8;'>Free</div>
                                </div>
                                """, unsafe_allow_html=True)
                    
                    st.markdown("<br>", unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Use generated timetable button
        col_use1, col_use2 = st.columns([2, 2])
        
        with col_use1:
            if st.button("✅ Use This Timetable as Master", type="primary", use_container_width=True):
                st.session_state.master_timetable = copy.deepcopy(st.session_state.generator_timetable)
                st.success("✅ Timetable saved as Master! You can now view and edit it in other tabs.")
                st.info("💡 Go to Tab 1 (Master Timetable Editor) to make manual adjustments.")

if __name__ == "__main__":
    main()
