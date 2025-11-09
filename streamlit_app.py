import warnings
warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL 1.1.1+")

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import gspread
from google.oauth2.service_account import Credentials
import json
import io
from datetime import datetime
import time

class DetapeTracker:
    """Handles detape monitoring before accessing dashboard"""

    DETAPE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1J3z7ISG1Vbv4uZk0mH97szJXJY6T4sO7J9lhKXQ6pEU/edit?usp=sharing"

    def __init__(self):
        self.gc = None
        self.connect_to_sheets()

    def connect_to_sheets(self):
        """Connect to Google Sheets using service account credentials"""
        try:
            credentials_dict = dict(st.secrets["google_service_account"])
            credentials = Credentials.from_service_account_info(
                credentials_dict,
                scopes=[
                    'https://www.googleapis.com/auth/spreadsheets',
                    'https://www.googleapis.com/auth/drive'
                ]
            )
            self.gc = gspread.authorize(credentials)
            return True
        except Exception as e:
            st.error(f"Error connecting to Google Sheets: {str(e)}")
            return False

    def record_detape(self, date, package_codes):
        """Record detape entries to Detape Monitoring sheet"""
        try:
            spreadsheet = self.gc.open_by_url(self.DETAPE_SHEET_URL)

            # Try to find the correct worksheet
            try:
                detape_sheet = spreadsheet.worksheet("Detape Monitoring")
            except:
                worksheets = spreadsheet.worksheets()
                for name in ["Detape Monitoring", "DetapeMonitoring", "Detape", "Sheet1"]:
                    try:
                        detape_sheet = spreadsheet.worksheet(name)
                        break
                    except:
                        continue
                else:
                    detape_sheet = worksheets[0]

            # Prepare records - one row per detape with its package code
            records = []
            for package_code in package_codes:
                records.append([date, 1, package_code])  # Each row is 1 detape with its package code

            # Append all records to sheet
            if records:
                detape_sheet.append_rows(records)
            return True
        except Exception as e:
            st.error(f"Error recording detape count: {str(e)}")
            return False

    def show_detape_form(self):
        """Display detape tracking form"""
        st.title("📊 Detape Monitoring")
        st.markdown("---")

        # Check if already completed today
        today = datetime.now().strftime("%Y-%m-%d")
        if st.session_state.get('detape_completed_date') == today:
            st.success(f"Detape count already recorded for today: {st.session_state.get('detape_count', 0)}")
            if st.button("Re-enter Detape Count"):
                del st.session_state['detape_completed_date']
                st.rerun()
            return True

        # Initialize session state for detape quantity if not exists
        if 'temp_detape_qty' not in st.session_state:
            st.session_state.temp_detape_qty = 0

        st.subheader("Daily Detape Count")

        # Detape quantity input OUTSIDE the form so it updates dynamically
        num_detape = st.number_input(
            "How many detapes were done?",
            min_value=0,
            value=st.session_state.temp_detape_qty,
            step=1,
            help="Enter the total number of detapes completed",
            key="detape_quantity_input"
        )

        # Update session state
        st.session_state.temp_detape_qty = num_detape

        # Now create the form with package codes
        with st.form("detape_form"):
            # If detapes were done, ask for package codes
            package_codes = []
            if num_detape > 0:
                st.markdown("---")
                st.subheader(f"Package Codes ({num_detape} required)")
                st.info(f"📦 Please enter the package code for each detape")

                # Create input fields for each detape
                for i in range(num_detape):
                    package_code = st.text_input(
                        f"Package Code {i+1}",
                        key=f"package_code_{i}",
                        placeholder=f"Enter package code for detape {i+1}",
                        help=f"Package code for detape #{i+1}"
                    )
                    package_codes.append(package_code)

            # Friendly reminder
            st.markdown("---")
            st.markdown("### 👇 Remember to click the button below to save")

            submitted = st.form_submit_button("✅ Submit Detape Count", type="primary", use_container_width=True)

            if submitted:
                # Validation
                if num_detape == 0:
                    st.warning("No detapes recorded (quantity is 0)")
                    st.session_state['detape_completed'] = True
                    st.session_state['detape_completed_date'] = today
                    st.session_state['detape_count'] = 0
                    # Clean up temp session state
                    if 'temp_detape_qty' in st.session_state:
                        del st.session_state.temp_detape_qty
                    time.sleep(1)
                    st.rerun()
                    return True

                # Check if all package codes are filled
                empty_codes = [i+1 for i, code in enumerate(package_codes) if not code.strip()]
                if empty_codes:
                    st.error(f"❌ Please fill in package code(s) for detape: {', '.join(map(str, empty_codes))}")
                    return False

                # Record to Google Sheets
                with st.spinner("Recording detape data..."):
                    success = self.record_detape(date=today, package_codes=package_codes)

                    if success:
                        st.session_state['detape_completed'] = True
                        st.session_state['detape_completed_date'] = today
                        st.session_state['detape_count'] = num_detape
                        st.session_state['detape_package_codes'] = package_codes  # Save package codes
                        # Clean up temp session state
                        if 'temp_detape_qty' in st.session_state:
                            del st.session_state.temp_detape_qty
                        st.success(f"✅ Recorded {num_detape} detape(s) with package codes successfully!")
                        st.balloons()
                        time.sleep(1)
                        st.rerun()
                        return True
                    else:
                        st.error("Failed to record detape data. Please try again.")
                        return False

        return False


class AttendanceTracker:
    """Handles team attendance tracking before shift starts"""

    MEMBERS_SHEET_URL = "https://docs.google.com/spreadsheets/d/1mTmcjz93wwF_YJUVoKmGPYsFR73KHiyR8l4uUnSyPYk/edit?usp=sharing"
    ATTENDANCE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1G8_xpSug-dOEODdwLI6wgGphbSNc3Y924IyXoIsyZqs/edit?usp=sharing"
    FULL_TEAM_SIZE = 3
    SHIFTS = ["Shift A", "Shift B", "Shift C"]

    def __init__(self):
        self.gc = None
        self.members_data = None
        self.connect_to_sheets()

    def connect_to_sheets(self):
        """Connect to Google Sheets using service account credentials"""
        try:
            credentials_dict = dict(st.secrets["google_service_account"])
            credentials = Credentials.from_service_account_info(
                credentials_dict,
                scopes=[
                    'https://www.googleapis.com/auth/spreadsheets',
                    'https://www.googleapis.com/auth/drive'
                ]
            )
            self.gc = gspread.authorize(credentials)
            return True
        except Exception as e:
            st.error(f"Error connecting to Google Sheets: {str(e)}")
            return False

    def load_team_members(self):
        """Load team members from PTEO Members sheet"""
        try:
            spreadsheet = self.gc.open_by_url(self.MEMBERS_SHEET_URL)

            # Try to find the correct worksheet
            try:
                # Try exact match first
                members_sheet = spreadsheet.worksheet("PTEO Members")
            except:
                # If that fails, try to find it by listing all sheets
                worksheets = spreadsheet.worksheets()

                # Try common variations
                for name in ["PTEO Members", "PTEOMembers", "PTEO_Members", "Members", "Sheet1"]:
                    try:
                        members_sheet = spreadsheet.worksheet(name)
                        break
                    except:
                        continue
                else:
                    # Use the first sheet if nothing matches
                    members_sheet = worksheets[0]

            self.members_data = members_sheet.get_all_records()
            return True
        except Exception as e:
            st.error(f"Error loading team members: {str(e)}")
            return False

    def get_team_members_for_shift(self, shift):
        """Get list of team members for a specific shift"""
        if not self.members_data:
            return []

        members = []

        # Normalize the selected shift (extract just the letter: "Shift A" -> "A")
        selected_shift_normalized = shift.replace("Shift ", "").strip()

        for member in self.members_data:
            # Get member name from various possible column names
            name = member.get('Name') or member.get('name') or member.get('Member Name') or member.get('member_name')

            # Get shift from various possible column names
            member_shift = member.get('Shift') or member.get('shift') or member.get('SHIFT')

            if name:
                # If shift column exists and has a value, filter by it
                if member_shift and member_shift.strip():
                    # Normalize member shift (could be "A", "B", "C" or "Shift A", "Shift B", "Shift C")
                    member_shift_normalized = member_shift.replace("Shift ", "").strip()

                    # Check if this member is assigned to the selected shift
                    if (member_shift_normalized == selected_shift_normalized or
                        member_shift_normalized.upper() == "ALL"):
                        members.append(name)
                else:
                    # No shift value, include all members
                    members.append(name)

        return members

    def record_attendance(self, shift, present_members, absent_members, date):
        """Record attendance to Attendance Record sheet"""
        try:
            spreadsheet = self.gc.open_by_url(self.ATTENDANCE_SHEET_URL)

            # Try to find the correct worksheet
            try:
                attendance_sheet = spreadsheet.worksheet("Attendance Record")
            except:
                # If that fails, try to find it by listing all sheets
                worksheets = spreadsheet.worksheets()

                # Try common variations
                for name in ["Attendance Record", "AttendanceRecord", "Attendance", "Sheet1"]:
                    try:
                        attendance_sheet = spreadsheet.worksheet(name)
                        break
                    except:
                        continue
                else:
                    # Use the first sheet if nothing matches
                    attendance_sheet = worksheets[0]

            # Prepare records for all team members
            records = []
            all_members = list(set(present_members + absent_members))

            for member in all_members:
                status = "Present" if member in present_members else "Absent"
                records.append([date, member, shift, status])

            # Append records to sheet
            if records:
                attendance_sheet.append_rows(records)
                return True

            return False
        except Exception as e:
            st.error(f"Error recording attendance: {str(e)}")
            return False

    def show_attendance_form(self):
        """Display attendance form and handle submission"""
        st.title("Team Attendance Check-in")
        st.markdown("---")

        # Check if already completed today
        today = datetime.now().strftime("%Y-%m-%d")
        if st.session_state.get('attendance_completed_date') == today:
            st.success("Attendance already recorded for today!")
            if st.button("Re-enter Attendance"):
                del st.session_state['attendance_completed_date']
                st.rerun()
            return True

        with st.form("attendance_form"):
            st.subheader("Shift Information")

            # Shift selection
            shift = st.selectbox("Which shift is working?", self.SHIFTS)

            # Load team members
            if not self.members_data:
                self.load_team_members()

            team_members = self.get_team_members_for_shift(shift)

            if not team_members:
                st.warning("Could not load team members. Please check the PTEO Members sheet.")
                team_members = []

            st.subheader("Team Attendance")

            # Number of present members
            num_present = st.number_input(
                f"How many team members are present today? (Full quantity = {self.FULL_TEAM_SIZE})",
                min_value=0,
                max_value=self.FULL_TEAM_SIZE,
                value=self.FULL_TEAM_SIZE,
                step=1
            )

            # If less than full team, ask who is absent
            absent_members = []
            expected_absent = self.FULL_TEAM_SIZE - num_present

            if num_present < self.FULL_TEAM_SIZE:
                st.warning(f"⚠️ Team is not at full capacity ({num_present}/{self.FULL_TEAM_SIZE})")
                st.info(f"📋 You must select exactly **{expected_absent}** absent member(s)")

                if team_members:
                    absent_members = st.multiselect(
                        f"Who is absent in this shift? (Select exactly {expected_absent})",
                        options=team_members,
                        help=f"You must select exactly {expected_absent} team member(s)",
                        max_selections=expected_absent  # Enforce limit
                    )

                    # Real-time validation feedback
                    if len(absent_members) < expected_absent:
                        st.error(f"❌ Please select {expected_absent - len(absent_members)} more member(s)")
                    elif len(absent_members) == expected_absent:
                        st.success(f"✅ Correct number of absent members selected")
                else:
                    # Manual input if team members couldn't be loaded
                    st.warning("⚠️ Could not load team member list. Please enter names manually.")
                    absent_input = st.text_area(
                        f"Enter exactly {expected_absent} absent member name(s) (one per line):",
                        help="Type each absent member's name on a new line"
                    )
                    if absent_input:
                        absent_members = [name.strip() for name in absent_input.split('\n') if name.strip()]

                        # Real-time validation feedback for manual input
                        if len(absent_members) < expected_absent:
                            st.error(f"❌ Please add {expected_absent - len(absent_members)} more name(s)")
                        elif len(absent_members) > expected_absent:
                            st.error(f"❌ Too many names! Remove {len(absent_members) - expected_absent} name(s)")
                        elif len(absent_members) == expected_absent:
                            st.success(f"✅ Correct number of absent members entered")

            # Friendly reminder for users
            st.markdown("---")
            st.markdown("### 👇 Remember to click the button below to save your attendance")

            submitted = st.form_submit_button("✅ Submit Attendance", type="primary", use_container_width=True)

            if submitted:
                # Validate absence count
                if num_present < self.FULL_TEAM_SIZE and len(absent_members) != expected_absent:
                    st.error(f"❌ Please select exactly {expected_absent} absent member(s). You selected {len(absent_members)}.")
                    return False

                # Determine present members
                if team_members:
                    present_members = [m for m in team_members if m not in absent_members]
                else:
                    # If we couldn't load team members, just record the count
                    present_members = [f"Team Member {i+1}" for i in range(num_present)]

                # Record attendance
                with st.spinner("Recording attendance..."):
                    success = self.record_attendance(
                        shift=shift,
                        present_members=present_members,
                        absent_members=absent_members,
                        date=today
                    )

                    if success:
                        st.session_state['attendance_completed'] = True
                        st.session_state['attendance_completed_date'] = today
                        st.session_state['current_shift'] = shift
                        st.success(f"Attendance recorded successfully for {shift}!")
                        st.balloons()
                        time.sleep(1)
                        st.rerun()
                        return True
                    else:
                        st.error("Failed to record attendance. Please try again.")
                        return False

        return False

class LotTrackingDashboard:
    # Columns to display in detailed data tables
    DISPLAY_COLUMNS = [
        'OPERATION', 'STEP NAME', 'PKG_CODE', 'PCKG DESC',
        'DEVC NAME', 'DEVC NUMBER', 'LOT NUMBER', 'OWNER',
        'PQQTY', 'QTY', 'OTD STATUS', 'COMMENTS'
    ]

    def __init__(self, spreadsheet_url):
        self.spreadsheet_url = spreadsheet_url
        self.before_shift_data = None
        self.after_shift_data = None
        self.processed_lots = []
        self.in_progress_lots = []
        self.split_low_yield_lots = []
        self.gc = None
        self.sheet = None
        self.restore_from_session_state()
    
    def restore_from_session_state(self):
        if 'before_shift_data' in st.session_state:
            self.before_shift_data = st.session_state.before_shift_data
        if 'after_shift_data' in st.session_state:
            self.after_shift_data = st.session_state.after_shift_data
    
    def safe_qty_sum(self, df):
        """Safely calculate sum of QTY column, handling mixed data types"""
        if 'QTY' not in df.columns or len(df) == 0:
            return 0
        try:
            # Convert to numeric, treating errors as NaN, then sum
            numeric_qty = pd.to_numeric(df['QTY'], errors='coerce')
            return numeric_qty.sum()
        except:
            return 0

    def filter_display_columns(self, df):
        """Filter dataframe to only show specified display columns"""
        if df is None or len(df) == 0:
            return df

        # Get columns that exist in both the dataframe and DISPLAY_COLUMNS
        available_columns = [col for col in self.DISPLAY_COLUMNS if col in df.columns]

        if available_columns:
            return df[available_columns].copy()
        return df
        
    def connect_to_sheet(self):
        try:
            credentials_dict = dict(st.secrets["google_service_account"])
            
            credentials = Credentials.from_service_account_info(
                credentials_dict,
                scopes=[
                    'https://www.googleapis.com/auth/spreadsheets',
                    'https://www.googleapis.com/auth/drive'
                ]
            )
            self.gc = gspread.authorize(credentials)
            self.sheet = self.gc.open_by_url(self.spreadsheet_url).sheet1
            return True
        except Exception as e:
            st.error(f"Error connecting to Google Sheets: {str(e)}")
            return False
    
    def read_sheet_data(self):
        try:
            if not self.sheet:
                if not self.connect_to_sheet():
                    return None
            
            if self.sheet is None:
                return None
                
            data = self.sheet.get_all_records()
            df = pd.DataFrame(data)
            
            return df
        except Exception as e:
            st.error(f"Error reading sheet data: {str(e)}")
            return None
    
    def filter_critical_lots(self, df):
        """Filter dataframe to only include critical OTD status or Split Low Yield lots"""
        if df is None or len(df) == 0:
            return df

        # First, exclude summary/header rows (Total, No filters applied, etc.)
        if 'Operation' in df.columns:
            # Exclude rows where Operation contains "Total" or "No filters applied"
            exclude_filter = df['Operation'].astype(str).str.contains(
                'Total|No filters applied',
                case=False,
                na=False,
                regex=True
            )
            df = df[~exclude_filter].copy()

        # Create filters for critical lots
        filters = []

        # Filter 1: Critical OTD Status (NEAR DUE, EXPEDITE OVERDUE, OVERDUE)
        if 'OTD STATUS' in df.columns:
            otd_filter = df['OTD STATUS'].str.contains(
                'NEAR DUE|EXPEDITE OVERDUE|OVERDUE',
                case=False,
                na=False,
                regex=True
            )
            filters.append(otd_filter)

        # Filter 2: Split Low Yield lots
        if 'CATEGORY' in df.columns:
            split_filter = df['CATEGORY'].str.contains(
                'ENGR-SPLIT LOW YIELD',
                case=False,
                na=False
            )
            filters.append(split_filter)

        # Combine filters with OR logic (include if ANY condition is true)
        if filters:
            combined_filter = filters[0]
            for f in filters[1:]:
                combined_filter = combined_filter | f

            filtered_df = df[combined_filter].copy()
            return filtered_df

        return df

    def capture_before_shift(self):
        data = self.read_sheet_data()
        if data is not None:
            # Filter to only include critical lots
            filtered_data = self.filter_critical_lots(data)

            self.before_shift_data = filtered_data.copy()
            st.session_state.before_shift_data = filtered_data.copy()
            st.session_state.before_shift_captured = True

            total_lots = data['LOT NUMBER'].nunique() if 'LOT NUMBER' in data.columns else len(data)
            filtered_lots = filtered_data['LOT NUMBER'].nunique() if 'LOT NUMBER' in filtered_data.columns else len(filtered_data)

            st.success(f"Before shift data captured: {filtered_lots} critical lots (out of {total_lots} total)")
            return True
        return False
    
    def capture_after_shift(self):
        data = self.read_sheet_data()
        if data is not None:
            # Filter to only include critical lots
            filtered_data = self.filter_critical_lots(data)

            self.after_shift_data = filtered_data.copy()
            st.session_state.after_shift_data = filtered_data.copy()
            st.session_state.after_shift_captured = True

            total_lots = data['LOT NUMBER'].nunique() if 'LOT NUMBER' in data.columns else len(data)
            filtered_lots = filtered_data['LOT NUMBER'].nunique() if 'LOT NUMBER' in filtered_data.columns else len(filtered_data)

            st.success(f"After shift data captured: {filtered_lots} critical lots (out of {total_lots} total)")
            self.analyze_processed_lots()
            return True
        return False
    
    def analyze_processed_lots(self):
        # Load data from session state if available
        if 'before_shift_data' in st.session_state:
            self.before_shift_data = st.session_state.before_shift_data
        if 'after_shift_data' in st.session_state:
            self.after_shift_data = st.session_state.after_shift_data
            
        if self.before_shift_data is None or self.after_shift_data is None:
            st.warning("Both before and after shift data needed for analysis")
            return
        
        # Identify processed lots (lots that disappeared)
        if 'LOT NUMBER' not in self.before_shift_data.columns or 'LOT NUMBER' not in self.after_shift_data.columns:
            st.error("LOT NUMBER column not found in data")
            return
            
        before_lot_numbers = set(self.before_shift_data['LOT NUMBER'].dropna())
        after_lot_numbers = set(self.after_shift_data['LOT NUMBER'].dropna())
        
        processed_lot_numbers = before_lot_numbers - after_lot_numbers
        in_progress_lot_numbers = before_lot_numbers.intersection(after_lot_numbers)
        
        self.processed_lots = self.before_shift_data[self.before_shift_data['LOT NUMBER'].isin(processed_lot_numbers)]
        self.in_progress_lots = self.before_shift_data[self.before_shift_data['LOT NUMBER'].isin(in_progress_lot_numbers)]
        
        # Separate processed lots into regular and split low yield
        # Note: Data is already filtered for critical OTD status and split low yield at capture time
        if len(self.processed_lots) > 0 and 'CATEGORY' in self.processed_lots.columns:
            processed_split_mask = self.processed_lots['CATEGORY'].str.contains(
                'ENGR-SPLIT LOW YIELD',
                case=False,
                na=False
            )
            self.processed_split_low_yield_lots = self.processed_lots[processed_split_mask]
            self.processed_regular_lots = self.processed_lots[~processed_split_mask]
        else:
            self.processed_split_low_yield_lots = pd.DataFrame()
            self.processed_regular_lots = self.processed_lots.copy() if len(self.processed_lots) > 0 else pd.DataFrame()

        # Separate in-progress lots into regular and split low yield
        # Note: Data is already filtered for critical OTD status and split low yield at capture time
        if len(self.in_progress_lots) > 0 and 'CATEGORY' in self.in_progress_lots.columns:
            in_progress_split_mask = self.in_progress_lots['CATEGORY'].str.contains(
                'ENGR-SPLIT LOW YIELD',
                case=False,
                na=False
            )
            self.in_progress_split_low_yield_lots = self.in_progress_lots[in_progress_split_mask]
            self.in_progress_regular_lots = self.in_progress_lots[~in_progress_split_mask]
        else:
            self.in_progress_split_low_yield_lots = pd.DataFrame()
            self.in_progress_regular_lots = self.in_progress_lots.copy() if len(self.in_progress_lots) > 0 else pd.DataFrame()
        
        # Keep backward compatibility
        self.split_low_yield_lots = self.processed_split_low_yield_lots
        
        st.session_state.analysis_complete = True
    
    def create_pie_chart(self):
        if not hasattr(self, 'processed_lots') or not hasattr(self, 'in_progress_lots'):
            return None
        
        labels = ['Processed', 'In Progress']
        values = [len(self.processed_lots), len(self.in_progress_lots)]
        colors = ['#2E8B57', '#FF6B6B']
        
        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            marker_colors=colors,
            textinfo='label+percent+value',
            hovertemplate='<b>%{label}</b><br>Count: %{value}<br>Percentage: %{percent}<extra></extra>'
        )])
        
        fig.update_layout(
            title="Lot Processing Status",
            showlegend=True,
            height=400
        )
        
        return fig
    
    def create_processed_categories_chart(self):
        if not hasattr(self, 'processed_lots') or len(self.processed_lots) == 0:
            return None
        
        regular_processed = len(self.processed_lots) - len(self.split_low_yield_lots)
        split_low_yield = len(self.split_low_yield_lots)
        
        labels = ['Regular Processed', 'Split Low Yield']
        values = [regular_processed, split_low_yield]
        colors = ['#4CAF50', '#FF9800']
        
        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            marker_colors=colors,
            textinfo='label+percent+value',
            hovertemplate='<b>%{label}</b><br>Count: %{value}<br>Percentage: %{percent}<extra></extra>'
        )])
        
        fig.update_layout(
            title="Processed Lot Categories",
            showlegend=True,
            height=400
        )
        
        return fig
    
    def create_summary_table(self):
        if not hasattr(self, 'processed_lots') or not hasattr(self, 'in_progress_lots'):
            return None
        
        total_lots = len(self.before_shift_data) if self.before_shift_data is not None else 0
        processed_count = len(self.processed_lots)
        processed_regular_count = len(self.processed_regular_lots) if hasattr(self, 'processed_regular_lots') else 0
        processed_split_count = len(self.processed_split_low_yield_lots) if hasattr(self, 'processed_split_low_yield_lots') else 0
        in_progress_regular_count = len(self.in_progress_regular_lots) if hasattr(self, 'in_progress_regular_lots') else 0
        in_progress_split_count = len(self.in_progress_split_low_yield_lots) if hasattr(self, 'in_progress_split_low_yield_lots') else 0
        
        summary_data = {
            'Metric': [
                'Total Lots (Start of Shift)',
                'Processed Regular Lots',
                'Processed Split Low Yield Lots',
                'In Progress Regular Lots',
                'In Progress Split Low Yield Lots',
                'Processing Rate (%)'
            ],
            'Value': [
                str(total_lots),
                str(processed_regular_count),
                str(processed_split_count),
                str(in_progress_regular_count),
                str(in_progress_split_count),
                f"{(processed_count/total_lots*100):.1f}%" if total_lots > 0 else "0%"
            ]
        }
        
        return pd.DataFrame(summary_data)
    
    def export_data(self):
        if not hasattr(self, 'processed_lots') or not hasattr(self, 'in_progress_lots'):
            st.warning("No analysis data available for export")
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create download buttons for different datasets
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if len(self.processed_lots) > 0:
                processed_csv = pd.DataFrame(self.processed_lots).to_csv(index=False)
                st.download_button(
                    label="Download Processed Lots",
                    data=processed_csv,
                    file_name=f"processed_lots_{timestamp}.csv",
                    mime="text/csv"
                )
        
        with col2:
            if len(self.in_progress_lots) > 0:
                in_progress_csv = pd.DataFrame(self.in_progress_lots).to_csv(index=False)
                st.download_button(
                    label="Download In Progress Lots",
                    data=in_progress_csv,
                    file_name=f"in_progress_lots_{timestamp}.csv",
                    mime="text/csv"
                )
        
        with col3:
            if len(self.split_low_yield_lots) > 0:
                split_csv = pd.DataFrame(self.split_low_yield_lots).to_csv(index=False)
                st.download_button(
                    label="Download Split Low Yield",
                    data=split_csv,
                    file_name=f"split_low_yield_{timestamp}.csv",
                    mime="text/csv"
                )

def main():
    st.set_page_config(
        page_title="Manufacturing Lot Tracking Dashboard",
        page_icon="🏭",
        layout="wide"
    )

    # Initialize session state
    if 'attendance_completed' not in st.session_state:
        st.session_state.attendance_completed = False
    if 'detape_completed' not in st.session_state:
        st.session_state.detape_completed = False
    if 'before_shift_captured' not in st.session_state:
        st.session_state.before_shift_captured = False
    if 'after_shift_captured' not in st.session_state:
        st.session_state.after_shift_captured = False
    if 'analysis_complete' not in st.session_state:
        st.session_state.analysis_complete = False

    # STEP 1: ATTENDANCE CHECK - Must be completed first
    if not st.session_state.attendance_completed:
        attendance_tracker = AttendanceTracker()
        attendance_tracker.show_attendance_form()
        st.info("✅ Complete attendance to continue")
        st.stop()  # Block further execution until attendance is complete

    # STEP 2: DETAPE MONITORING - Must be completed after attendance
    if not st.session_state.detape_completed:
        detape_tracker = DetapeTracker()
        detape_tracker.show_detape_form()
        st.info("✅ Complete detape count to access the dashboard")
        st.stop()  # Block further execution until detape is complete

    # STEP 3: Show the main dashboard after all checks are complete
    st.title("🏭 Manufacturing Lot Tracking Dashboard")

    # Display current shift info and completion status
    col1, col2 = st.columns(2)
    with col1:
        if 'current_shift' in st.session_state:
            st.caption(f"📋 Current Shift: {st.session_state.current_shift}")
    with col2:
        if 'detape_count' in st.session_state:
            st.caption(f"📊 Today's Detape Count: {st.session_state.detape_count}")
    
    # Sidebar for configuration
    with st.sidebar:
        st.header("Configuration")
        
        # Google Sheets URL
        spreadsheet_url = st.text_input(
            "Google Sheets URL",
            value="https://docs.google.com/spreadsheets/d/1XlkxQlIjm29dGzUhm9iRHaL6VuOwRSeJc4mCqR6gxhA/edit",
            help="Enter the URL of your Google Sheets document"
        )
        
        # Google Service Account Credentials Status
        st.subheader("Google Credentials")
        try:
            if "google_service_account" in st.secrets:
                st.success("✅ Credentials loaded from secrets.toml")
            else:
                st.error("❌ Credentials not found in secrets.toml")
        except Exception:
            st.error("❌ Credentials not found in secrets.toml")
    
    # Initialize dashboard
    dashboard = LotTrackingDashboard(spreadsheet_url)
    
    # Instructions
    with st.expander("📋 Instructions", expanded=True):
        st.markdown("""
        **How to use this dashboard:**

        1. **Before Shift**: Click "Capture Before Shift Data" at the start of your shift
        2. **After Shift**: Click "Capture After Shift Data" at the end of your shift
        3. **Analysis**: The system will automatically analyze which lots were processed

        **What gets tracked:**
        - Lots that were processed (disappeared from the sheet)
        - Lots still in progress (remain on the sheet)
        - Special "Split Low Yield" lots (identified by ENGR-SPLIT LOW YIELD in CATEGORY column)
        """)
    
    # Control buttons
    st.header("🎮 Controls")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📥 Capture Before Shift Data", type="primary"):
            with st.spinner("Capturing before shift data..."):
                dashboard.capture_before_shift()
    
    with col2:
        if st.button("📤 Capture After Shift Data", type="primary"):
            if not st.session_state.before_shift_captured:
                st.error("Please capture before shift data first")
            else:
                with st.spinner("Capturing after shift data and analyzing..."):
                    dashboard.capture_after_shift()
    
    with col3:
        if st.button("🔄 Reset Analysis"):
            for key in ['before_shift_captured', 'after_shift_captured', 'analysis_complete']:
                st.session_state[key] = False
            st.success("Analysis reset successfully")
            st.rerun()
    
    # Status indicators
    st.header("📊 Status")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.session_state.before_shift_captured:
            st.success("✅ Before shift data captured")
        else:
            st.info("⏳ Before shift data pending")
    
    with col2:
        if st.session_state.after_shift_captured:
            st.success("✅ After shift data captured")
        else:
            st.info("⏳ After shift data pending")
    
    with col3:
        if st.session_state.analysis_complete:
            st.success("✅ Analysis complete")
        else:
            st.info("⏳ Analysis pending")
    
    # Results section
    if st.session_state.analysis_complete:
        st.header("📈 Results")

        # Display detape count and package codes
        if 'detape_count' in st.session_state:
            st.metric("📊 Detapes Occured Today", st.session_state.detape_count)

            # Display package codes if available
            if 'detape_package_codes' in st.session_state and st.session_state.detape_package_codes:
                st.write("**Package Codes:**")
                # Display as a comma-separated list in white
                package_codes_display = ", ".join(st.session_state.detape_package_codes)
                st.markdown(f"<span style='color: white;'>{package_codes_display}</span>", unsafe_allow_html=True)

            st.markdown("---")

        # Summary table
        summary_df = dashboard.create_summary_table()
        if summary_df is not None:
            col1, col2 = st.columns([1, 2])
            with col1:
                st.subheader("Summary Statistics")
                st.dataframe(summary_df, hide_index=True)
        
        # Charts
        col1, col2 = st.columns(2)
        
        with col1:
            pie_chart = dashboard.create_pie_chart()
            if pie_chart:
                st.plotly_chart(pie_chart, use_container_width=True)
        
        with col2:
            categories_chart = dashboard.create_processed_categories_chart()
            if categories_chart:
                st.plotly_chart(categories_chart, use_container_width=True)

        # Detailed data views
        with st.expander("🔍 View Detailed Data"):
            tab1, tab2, tab3, tab4 = st.tabs([
                "Processed Regular", 
                "Processed Split Low Yield", 
                "In Progress Regular", 
                "In Progress Split Low Yield"
            ])
            
            with tab1:
                if len(dashboard.processed_regular_lots) > 0:
                    # Display metrics in columns
                    col1, col2 = st.columns(2)

                    with col1:
                        count = len(dashboard.processed_regular_lots)
                        st.metric("Processed Regular Lots", f"{count}")

                    with col2:
                        qty_sum = dashboard.safe_qty_sum(dashboard.processed_regular_lots)
                        st.metric("Total QTY", f"{qty_sum:,.0f}")

                    # Sort by OTD STATUS: 5 OVERDUE, 4 EXPEDITE OVERDUE, 3 NEAR DUE
                    df_sorted = dashboard.processed_regular_lots.copy()
                    if 'OTD STATUS' in df_sorted.columns:
                        # Create sort key based on OTD status priority
                        def otd_sort_key(status):
                            status_str = str(status).upper()
                            if '5' in status_str or 'OVERDUE' in status_str and '4' not in status_str and '3' not in status_str:
                                return 1  # 5 OVERDUE first
                            elif '4' in status_str or 'EXPEDITE' in status_str:
                                return 2  # 4 EXPEDITE OVERDUE second
                            elif '3' in status_str or 'NEAR DUE' in status_str:
                                return 3  # 3 NEAR DUE third
                            else:
                                return 4  # Others last

                        df_sorted['_sort_key'] = df_sorted['OTD STATUS'].apply(otd_sort_key)
                        df_sorted = df_sorted.sort_values('_sort_key').drop('_sort_key', axis=1)

                    # Filter to display only specified columns
                    df_filtered = dashboard.filter_display_columns(df_sorted)
                    df_display = df_filtered.astype(str)
                    st.dataframe(df_display, use_container_width=True)
                else:
                    st.info("No processed regular lots found")
            
            with tab2:
                if len(dashboard.processed_split_low_yield_lots) > 0:
                    # Display metrics in columns
                    col1, col2 = st.columns(2)

                    with col1:
                        count = len(dashboard.processed_split_low_yield_lots)
                        st.metric("Processed Split Low Yield Lots", f"{count}")

                    with col2:
                        qty_sum = dashboard.safe_qty_sum(dashboard.processed_split_low_yield_lots)
                        st.metric("Total QTY", f"{qty_sum:,.0f}")

                    # Filter to display only specified columns
                    df_filtered = dashboard.filter_display_columns(dashboard.processed_split_low_yield_lots)
                    df_display = df_filtered.astype(str)
                    st.dataframe(df_display, use_container_width=True)
                else:
                    st.info("No processed split low yield lots found")
            
            with tab3:
                if len(dashboard.in_progress_regular_lots) > 0:
                    # Display metrics in columns
                    col1, col2 = st.columns(2)

                    with col1:
                        count = len(dashboard.in_progress_regular_lots)
                        st.metric("In Progress Regular Lots", f"{count}")

                    with col2:
                        qty_sum = dashboard.safe_qty_sum(dashboard.in_progress_regular_lots)
                        st.metric("Total QTY", f"{qty_sum:,.0f}")

                    # Sort by OTD STATUS: 5 OVERDUE, 4 EXPEDITE OVERDUE, 3 NEAR DUE
                    df_sorted = dashboard.in_progress_regular_lots.copy()
                    if 'OTD STATUS' in df_sorted.columns:
                        # Create sort key based on OTD status priority
                        def otd_sort_key(status):
                            status_str = str(status).upper()
                            if '5' in status_str or 'OVERDUE' in status_str and '4' not in status_str and '3' not in status_str:
                                return 1  # 5 OVERDUE first
                            elif '4' in status_str or 'EXPEDITE' in status_str:
                                return 2  # 4 EXPEDITE OVERDUE second
                            elif '3' in status_str or 'NEAR DUE' in status_str:
                                return 3  # 3 NEAR DUE third
                            else:
                                return 4  # Others last

                        df_sorted['_sort_key'] = df_sorted['OTD STATUS'].apply(otd_sort_key)
                        df_sorted = df_sorted.sort_values('_sort_key').drop('_sort_key', axis=1)

                    # Filter to display only specified columns
                    df_filtered = dashboard.filter_display_columns(df_sorted)
                    df_display = df_filtered.astype(str)
                    st.dataframe(df_display, use_container_width=True)
                else:
                    st.info("No in progress regular lots found")
            
            with tab4:
                if len(dashboard.in_progress_split_low_yield_lots) > 0:
                    # Display metrics in columns
                    col1, col2 = st.columns(2)

                    with col1:
                        count = len(dashboard.in_progress_split_low_yield_lots)
                        st.metric("In Progress Split Low Yield Lots", f"{count}")

                    with col2:
                        qty_sum = dashboard.safe_qty_sum(dashboard.in_progress_split_low_yield_lots)
                        st.metric("Total QTY", f"{qty_sum:,.0f}")

                    # Filter to display only specified columns
                    df_filtered = dashboard.filter_display_columns(dashboard.in_progress_split_low_yield_lots)
                    df_display = df_filtered.astype(str)
                    st.dataframe(df_display, use_container_width=True)
                else:
                    st.info("No in progress split low yield lots found")

if __name__ == "__main__":
    main()