import json
from datetime import datetime, date
from pathlib import Path
import pandas as pd
import streamlit as st
from db import init_db, get_connection

st.set_page_config(page_title="PILLPAL – Your Everyday Health Companion", page_icon="💊", layout="wide")
init_db()

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


@st.cache_data
def load_guides():
    with open("data/guides.json", "r", encoding="utf-8") as f:
        return json.load(f)


guides = load_guides()

# Sidebar Navigation & Emergency Quick Access
st.sidebar.title("💊 PILLPAL")
st.sidebar.caption("Your Everyday Health Companion")

page = st.sidebar.radio(
    "Navigate",
    [
        "Dashboard",
        "Medication Reminders",
        "Doctor Appointments",
        "Health Records & Reports",
        "Checkups & Wellness",
        "First-Aid Guidance",
        "Emergency Quick Actions",
        "Health Tracking",
    ],
)

st.sidebar.divider()
st.sidebar.subheader("🚨 Quick Emergency Info")
st.sidebar.info("India Emergency: **112** | Ambulance: **108**")
st.sidebar.caption("Supports organization & awareness; does not replace doctors or emergency services.")


def fetch_df(query, params=()):
    with get_connection() as conn:
        return pd.read_sql_query(query, conn, params=params)


def execute_sql(query, params=()):
    with get_connection() as conn:
        conn.execute(query, params)
        conn.commit()


# 1. Personalised Health Dashboard
if page == "Dashboard":
    st.title("Personalised Health Dashboard")
    st.write("A unified view of your daily medications, upcoming appointments, health logs, and records.")

    meds_df = fetch_df("SELECT * FROM medications WHERE active = 1")
    appts_df = fetch_df("SELECT * FROM appointments ORDER BY appt_date, appt_time")
    logs_df = fetch_df("SELECT * FROM health_logs ORDER BY log_date DESC")
    recs_df = fetch_df("SELECT * FROM records ORDER BY record_date DESC")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Active Medications", len(meds_df))
    c2.metric("Scheduled Appointments", len(appts_df))
    c3.metric("Health Logs", len(logs_df))
    c4.metric("Saved Records", len(recs_df))

    col_left, col_right = st.columns(2)
    with col_left:
        st.subheader("Today's Medication Schedule")
        if meds_df.empty:
            st.write("No active medications added yet.")
        else:
            st.dataframe(meds_df[["name", "dosage", "schedule_times"]], use_container_width=True, hide_index=True)

    with col_right:
        st.subheader("Upcoming Appointments")
        if appts_df.empty:
            st.write("No appointments scheduled yet.")
        else:
            st.dataframe(appts_df[["doctor_name", "specialty", "appt_date", "appt_time"]], use_container_width=True, hide_index=True)


# 2. Medication Reminders
elif page == "Medication Reminders":
    st.title("Medication Reminders")
    st.caption("Note: Browser/push alerts require background workers or desktop notifications; in-app alerts highlight scheduled times here.")

    now_hm = datetime.now().strftime("%H:%M")
    active_meds = fetch_df("SELECT * FROM medications WHERE active = 1")
    if not active_meds.empty:
        due_now = []
        for _, row in active_meds.iterrows():
            times = [t.strip() for t in str(row["schedule_times"]).split(",")]
            if any(now_hm >= t for t in times):
                due_now.append(f"**{row['name']}** ({row['dosage']}) — scheduled at `{row['schedule_times']}`")
        if due_now:
            st.warning("Scheduled / Due Today:\n\n" + "\n\n".join(f"- {item}" for item in due_now))

    with st.form("add_med_form", clear_on_submit=True):
        st.subheader("Add Medication")
        c1, c2 = st.columns(2)
        name = c1.text_input("Medicine Name", placeholder="e.g., Vitamin D3")
        dosage = c2.text_input("Dosage Instructions", placeholder="e.g., 1 tablet after meal")
        c3, c4 = st.columns(2)
        freq = c3.selectbox("Frequency", ["Once daily", "Twice daily", "Thrice daily", "Custom"])
        schedule_times = c4.text_input("Reminder Times (24h, comma-separated)", value="08:00, 20:00")
        submitted = st.form_submit_button("Save Medication")
        if submitted and name and dosage:
            execute_sql(
                "INSERT INTO medications (name, dosage, times_per_day, schedule_times, active) VALUES (?, ?, ?, ?, 1)",
                (name.strip(), dosage.strip(), freq, schedule_times.strip()),
            )
            st.success("Medication saved.")
            st.rerun()

    st.subheader("Saved Medications")
    all_meds = fetch_df("SELECT * FROM medications ORDER BY id DESC")
    if not all_meds.empty:
        st.dataframe(all_meds, use_container_width=True, hide_index=True)


# 3. Doctor Appointment Management
elif page == "Doctor Appointments":
    st.title("Doctor Appointment Management")

    with st.form("appt_form", clear_on_submit=True):
        st.subheader("Schedule New Appointment")
        c1, c2 = st.columns(2)
        doc_name = c1.text_input("Doctor Name", placeholder="Dr. A. Sharma")
        specialty = c2.text_input("Specialty / Clinic", placeholder="General Physician")
        c3, c4 = st.columns(2)
        appt_date = c3.date_input("Date", min_value=date.today())
        appt_time = c4.time_input("Time")
        notes = st.text_area("Notes / Preparation")
        if st.form_submit_button("Save Appointment") and doc_name and specialty:
            execute_sql(
                "INSERT INTO appointments (doctor_name, specialty, appt_date, appt_time, notes) VALUES (?, ?, ?, ?, ?)",
                (doc_name.strip(), specialty.strip(), str(appt_date), appt_time.strftime("%H:%M"), notes.strip()),
            )
            st.success("Appointment saved.")
            st.rerun()

    appts = fetch_df("SELECT * FROM appointments ORDER BY appt_date, appt_time")
    today_str = str(date.today())
    if not appts.empty:
        upcoming = appts[appts["appt_date"] >= today_str]
        if not upcoming.empty:
            st.info(f"Upcoming reminder: Next visit is with **{upcoming.iloc[0]['doctor_name']}** on **{upcoming.iloc[0]['appt_date']}** at **{upcoming.iloc[0]['appt_time']}**.")
        st.dataframe(appts, use_container_width=True, hide_index=True)


# 4. Health Records and Reports
elif page == "Health Records & Reports":
    st.title("Health Records and Reports")
    st.write("Store prescriptions, lab reports, and medical summaries in one organized place.")

    with st.form("record_form", clear_on_submit=True):
        title = st.text_input("Document Title", placeholder="Blood Panel - Nov 2026")
        category = st.selectbox("Category", ["Prescription", "Lab Report", "Discharge / Visit Summary", "Other"])
        rec_date = st.date_input("Document Date", value=date.today())
        uploaded_file = st.file_uploader("Upload File (PDF, PNG, JPG)", type=["pdf", "png", "jpg", "jpeg"])
        if st.form_submit_button("Save Record") and title and uploaded_file is not None:
            safe_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{uploaded_file.name}"
            dest = UPLOAD_DIR / safe_name
            dest.write_bytes(uploaded_file.getbuffer())
            execute_sql(
                "INSERT INTO records (title, category, record_date, file_path) VALUES (?, ?, ?, ?)",
                (title.strip(), category, str(rec_date), str(dest)),
            )
            st.success("Record uploaded and indexed.")
            st.rerun()

    recs = fetch_df("SELECT * FROM records ORDER BY record_date DESC")
    if not recs.empty:
        for _, row in recs.iterrows():
            col1, col2 = st.columns([4, 1])
            col1.write(f"**{row['title']}** — {row['category']} ({row['record_date']})")
            p = Path(row["file_path"])
            if p.exists():
                col2.download_button("Download", data=p.read_bytes(), file_name=p.name, key=f"dl_{row['id']}")


# 5. Health Checkups and Wellness Tips
elif page == "Checkups & Wellness":
    st.title("Health Checkups and Wellness Tips")
    st.write("General wellness guidance to support proactive daily habits.")

    for tip in guides["wellness_tips"]:
        st.markdown(f"- {tip}")

    st.subheader("Routine Checkup Ideas to Discuss with Your Doctor")
    st.markdown("- Annual general physical and vital signs review\n- Routine blood work tailored to age and risk factors\n- Dental, vision, and vaccination status checks")


# 6. First-Aid Guidance
elif page == "First-Aid Guidance":
    st.title("First-Aid Guidance")
    st.warning("For informational guidance only. Always seek professional medical help for serious injuries or symptoms.")

    scenario = st.selectbox("Select a Situation", list(guides["first_aid"].keys()))
    st.subheader(f"Initial Steps: {scenario}")
    for idx, step in enumerate(guides["first_aid"][scenario], start=1):
        st.markdown(f"**{idx}.** {step}")


# 7. Emergency Quick Actions
elif page == "Emergency Quick Actions":
    st.title("Emergency Quick Actions")
    st.error("In a life-threatening emergency, contact local emergency services immediately.")

    if "emergency_contacts" not in st.session_state:
        st.session_state.emergency_contacts = [
            {"Name": "National Emergency Number (India)", "Relation": "Emergency Services", "Phone": "112"},
            {"Name": "Ambulance", "Relation": "Medical Dispatch", "Phone": "108"},
        ]

    st.table(pd.DataFrame(st.session_state.emergency_contacts))

    with st.form("ec_form", clear_on_submit=True):
        st.subheader("Add Personal Emergency Contact")
        c1, c2, c3 = st.columns(3)
        cname = c1.text_input("Contact Name")
        crel = c2.text_input("Relationship")
        cphone = c3.text_input("Phone Number")
        if st.form_submit_button("Add Contact") and cname and cphone:
            st.session_state.emergency_contacts.append(
                {"Name": cname.strip(), "Relation": crel.strip() or "Contact", "Phone": cphone.strip()}
            )
            st.rerun()


# 8. Health Tracking
elif page == "Health Tracking":
    st.title("Health Tracking")
    st.write("Log measurements over time to spot trends and share organized summaries with your doctor.")

    with st.form("health_log_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        log_date = c1.date_input("Date", value=date.today())
        metric_type = c2.selectbox("Measurement", ["Blood Pressure (mmHg)", "Blood Glucose (mg/dL)", "Resting Heart Rate (bpm)", "Weight (kg)"])
        val1 = c3.number_input("Primary Value (e.g., Systolic / Reading / Weight)", min_value=0.0, step=0.1)

        val2 = None
        unit = metric_type.split("(")[-1].rstrip(")")
        if metric_type.startswith("Blood Pressure"):
            val2 = st.number_input("Diastolic Value (mmHg)", min_value=0.0, step=1.0, value=80.0)

        if st.form_submit_button("Log Measurement") and val1 > 0:
            execute_sql(
                "INSERT INTO health_logs (log_date, metric_type, value_primary, value_secondary, unit) VALUES (?, ?, ?, ?, ?)",
                (str(log_date), metric_type, float(val1), float(val2) if val2 is not None else None, unit),
            )
            st.success("Measurement logged.")
            st.rerun()

    logs = fetch_df("SELECT * FROM health_logs ORDER BY log_date ASC, id ASC")
    if not logs.empty:
        selected_metric = st.selectbox("View Trend For", logs["metric_type"].unique())
        filtered = logs[logs["metric_type"] == selected_metric].copy()
        filtered["log_date"] = pd.to_datetime(filtered["log_date"])
        filtered = filtered.set_index("log_date")
        cols = ["value_primary"] + (["value_secondary"] if filtered["value_secondary"].notna().any() else [])
        st.line_chart(filtered[cols])
        st.dataframe(logs.sort_values("log_date", ascending=False), use_container_width=True, hide_index=True)