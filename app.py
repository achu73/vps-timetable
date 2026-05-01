import streamlit as st
import pandas as pd
import datetime
import os

st.set_page_config(page_title="VPS Timetable Manager", layout="wide")

# --- INTEGRATED CSS STYLING ---
st.markdown("""
    <style>
        .main-header {
            background: linear-gradient(135deg, #004d4d, #006666, #009999);
            color: white; padding: 15px; border-radius: 15px;
            text-align: center; margin-bottom: 20px;
        }
        .stButton>button {
            background-color: #006666; color: white; border-radius: 8px;
        }
        .stButton>button:hover {
            background-color: #009999; color: white;
        }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header"><h2>🏫 VPS Timetable & Substitution Manager</h2></div>', unsafe_allow_html=True)

# --- FILE HANDLING ---
uploaded_file = st.file_uploader("Upload Master Timetable (Excel/CSV)", type=["xlsx", "csv"])

# Initialize the persistent substitution log if it doesn't exist
log_file = "Substitution_Log.csv"
if not os.path.exists(log_file):
    pd.DataFrame(columns=['Date', 'Day', 'Period', 'Absent_Teacher', 'Substitute']).to_csv(log_file, index=False)

if uploaded_file:
    # Load Master Data
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)
        
    df['Class'] = df['Class'].astype(str)
    
    # Ensure Role column exists
    if 'Role' not in df.columns:
        df['Role'] = 'Regular'
        
    all_teachers = set(df['Teacher'].dropna().unique())
    history_df = pd.read_csv(log_file)

    # --- APP NAVIGATION ---
    tab1, tab2, tab3, tab4 = st.tabs(["🗂️ Master Editor", "📘 Class View", "🧑‍🏫 Teacher View", "🧠 Smart Substitution"])

    # TAB 1: MASTER EDITOR
    with tab1:
        st.info("Edit cells directly. Any new vocational subjects added here will automatically update the whole app!")
        edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True, height=400)
        
        st.download_button(
            "💾 Download Master Timetable",
            data=edited_df.to_csv(index=False).encode('utf-8'),
            file_name="VPS_Master_Timetable.csv",
            mime="text/csv"
        )

    # TAB 2: CLASS VIEW
    with tab2:
        col1, col2 = st.columns(2)
        with col1:
            sel_class = st.selectbox("Select Class", sorted(edited_df['Class'].unique()))
        with col2:
            sections = sorted(edited_df[edited_df['Class'] == sel_class]['Section'].unique())
            sel_section = st.selectbox("Select Section", sections)
            
        st.dataframe(edited_df[(edited_df['Class'] == sel_class) & (edited_df['Section'] == sel_section)].sort_values('Period'), use_container_width=True, hide_index=True)

    # TAB 3: TEACHER VIEW
    with tab3:
        sel_teacher = st.selectbox("Select Teacher", sorted(list(all_teachers)))
        st.dataframe(edited_df[edited_df['Teacher'] == sel_teacher].sort_values(['Day', 'Period']), use_container_width=True, hide_index=True)

    # TAB 4: SUBSTITUTION ENGINE
    with tab4:
        if 'assigned_subs' not in st.session_state:
            st.session_state.assigned_subs = []

        col1, col2 = st.columns([1, 2])
        
        with col1:
            absent_day = st.selectbox("Day of Absence", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"])
            absent_teacher = st.selectbox("Select Absent Teacher", sorted(list(all_teachers)))
            todays_classes = edited_df[(edited_df['Teacher'] == absent_teacher) & (edited_df['Day'] == absent_day)]
            
        with col2:
            if todays_classes.empty:
                st.success(f"✅ {absent_teacher} has no classes scheduled on {absent_day}.")
            else:
                base_workload = edited_df[edited_df['Day'] == absent_day].groupby('Teacher')['Period'].count().to_dict()
                max_period_of_day = int(edited_df['Period'].max()) if not edited_df.empty else 9
                two_weeks_ago = str(datetime.date.today() - datetime.timedelta(days=14))
                
                for period_to_cover in sorted(todays_classes['Period'].unique()):
                    class_info = todays_classes[todays_classes['Period'] == period_to_cover].iloc[0]
                    t_class, t_sec, t_sub = class_info['Class'], class_info['Section'], class_info['Subject']
                    
                    st.markdown(f"#### 🕒 Period {period_to_cover}: Class {t_class}{t_sec} ({t_sub})")
                    
                    already_assigned = next((s['Substitute'] for s in st.session_state.assigned_subs if s['Period'] == period_to_cover), None)
                    
                    if already_assigned:
                        st.success(f"🎉 Assigned to: **{already_assigned}**")
                        # Save to log button
                        if st.button(f"Confirm & Save to Log (P{period_to_cover})", key=f"save_{period_to_cover}"):
                            new_log = pd.DataFrame([{'Date': str(datetime.date.today()), 'Day': absent_day, 'Period': period_to_cover, 'Absent_Teacher': absent_teacher, 'Substitute': already_assigned}])
                            new_log.to_csv(log_file, mode='a', header=False, index=False)
                            st.success("Saved to persistent log!")
                            
                        if st.button(f"Undo (P{period_to_cover})", key=f"undo_{period_to_cover}"):
                            st.session_state.assigned_subs = [s for s in st.session_state.assigned_subs if s['Period'] != period_to_cover]
                            st.rerun()
                    else:
                        # Find who is busy
                        busy_teaching = set(edited_df[(edited_df['Day'] == absent_day) & (edited_df['Period'] == period_to_cover)]['Teacher'].unique())
                        busy_subbing = set([s['Substitute'] for s in st.session_state.assigned_subs if s['Period'] == period_to_cover])
                        busy_teachers = busy_teaching.union(busy_subbing)
                        
                        familiar_teachers = set(edited_df[(edited_df['Class'] == t_class) & (edited_df['Section'] == t_sec)]['Teacher'].unique())
                        
                        available_candidates = []
                        
                        for teacher in all_teachers:
                            if pd.isna(teacher) or teacher == absent_teacher or teacher in busy_teachers:
                                continue
                                
                            teacher_role = edited_df[edited_df['Teacher'] == teacher]['Role'].iloc[0]
                            if teacher_role == "Level Coordinator": continue
                            
                            t_schedule = edited_df[(edited_df['Teacher'] == teacher) & (edited_df['Day'] == absent_day)]
                            t_periods = t_schedule['Period'].tolist()
                            t_periods.extend([s['Period'] for s in st.session_state.assigned_subs if s['Substitute'] == teacher])
                            
                            effective_workload = len(t_periods)
                            if effective_workload >= 7: continue
                            
                            # Historical Fairness
                            past_14_days = len(history_df[(history_df['Substitute'] == teacher) & (history_df['Date'] >= two_weeks_ago)])
                            if teacher_role == "Subject Coordinator" and past_14_days >= 4: continue
                            
                            # Visual Day Map
                            visual_schedule = {}
                            for p in range(1, max_period_of_day + 1):
                                if p == period_to_cover:
                                    visual_schedule[f"P{p}"] = "🟨 Sub"
                                else:
                                    teaching_now = t_schedule[t_schedule['Period'] == p]
                                    if not teaching_now.empty:
                                        visual_schedule[f"P{p}"] = f"🟥 {teaching_now.iloc[0]['Class']}{teaching_now.iloc[0]['Section']}"
                                    else:
                                        visual_schedule[f"P{p}"] = "🟩 Free"
                            
                            available_candidates.append({
                                "Name": teacher, "Load": effective_workload, "14-Day Subs": past_14_days,
                                "Familiar": teacher in familiar_teachers, **visual_schedule
                            })
                            
                        # Sort by fairness (fewest subs first)
                        available_candidates = sorted(available_candidates, key=lambda x: x["14-Day Subs"])
                        
                        p1 = [c for c in available_candidates if c["Familiar"] and c["Load"] <= 5]
                        p2 = [c for c in available_candidates if not c["Familiar"] and c["Load"] <= 6]
                        
                        st.markdown("**Visual Guide:** 🟩 Free | 🟥 Busy | 🟨 Proposed Sub")
                        
                        col_a, col_b = st.columns(2)
                        with col_a:
                            st.markdown("**🥇 Priority 1 (Familiar, Load ≤ 5)**")
                            if p1:
                                st.dataframe(pd.DataFrame(p1).drop(columns=['Familiar']), hide_index=True)
                                sel_p1 = st.selectbox("Assign P1", ["-- Select --"] + [c["Name"] for c in p1], key=f"p1_{period_to_cover}")
                                if sel_p1 != "-- Select --":
                                    st.session_state.assigned_subs.append({'Day': absent_day, 'Period': period_to_cover, 'Substitute': sel_p1})
                                    st.rerun()
                            else: st.write("No candidates.")
                                
                        with col_b:
                            st.markdown("**🥈 Priority 2 (Available, Load ≤ 6)**")
                            if p2:
                                st.dataframe(pd.DataFrame(p2).drop(columns=['Familiar']), hide_index=True)
                                sel_p2 = st.selectbox("Assign P2", ["-- Select --"] + [c["Name"] for c in p2], key=f"p2_{period_to_cover}")
                                if sel_p2 != "-- Select --":
                                    st.session_state.assigned_subs.append({'Day': absent_day, 'Period': period_to_cover, 'Substitute': sel_p2})
                                    st.rerun()
                            else: st.write("No candidates.")
                    st.divider()
else:
    st.info("👆 Please upload your Master Timetable to begin.")
