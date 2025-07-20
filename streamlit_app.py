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

class LotTrackingDashboard:
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
        
    def connect_to_sheet(self):
        try:
            if 'google_credentials' in st.session_state:
                credentials_dict = st.session_state.google_credentials
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
            else:
                st.error("Please contact our engineers")
                return False
        except Exception as e:
            st.error("Please contact our engineers")
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
            st.error("Please contact our engineers")
            return None
    
    def capture_before_shift(self):
        data = self.read_sheet_data()
        if data is not None:
            self.before_shift_data = data.copy()
            st.session_state.before_shift_data = data.copy()
            st.session_state.before_shift_captured = True
            unique_lots = data['LOT NUMBER'].nunique() if 'LOT NUMBER' in data.columns else len(data)
            st.success(f"Before shift data captured: {unique_lots} unique lots")
            return True
        return False
    
    def capture_after_shift(self):
        data = self.read_sheet_data()
        if data is not None:
            self.after_shift_data = data.copy()
            st.session_state.after_shift_data = data.copy()
            st.session_state.after_shift_captured = True
            unique_lots = data['LOT NUMBER'].nunique() if 'LOT NUMBER' in data.columns else len(data)
            st.success(f"After shift data captured: {unique_lots} unique lots")
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
            st.warning("Please contact our engineers")
            return
        
        # Identify processed lots (lots that disappeared)
        if 'LOT NUMBER' not in self.before_shift_data.columns or 'LOT NUMBER' not in self.after_shift_data.columns:
            st.error("Please contact our engineers")
            return
            
        before_lot_numbers = set(self.before_shift_data['LOT NUMBER'].dropna())
        after_lot_numbers = set(self.after_shift_data['LOT NUMBER'].dropna())
        
        processed_lot_numbers = before_lot_numbers - after_lot_numbers
        in_progress_lot_numbers = before_lot_numbers.intersection(after_lot_numbers)
        
        self.processed_lots = self.before_shift_data[self.before_shift_data['LOT NUMBER'].isin(processed_lot_numbers)]
        self.in_progress_lots = self.before_shift_data[self.before_shift_data['LOT NUMBER'].isin(in_progress_lot_numbers)]
        
        # Debug output
        st.info(f"Analysis: {len(processed_lot_numbers)} processed, {len(in_progress_lot_numbers)} in progress")
        
        # Separate processed lots into regular and split low yield
        if len(self.processed_lots) > 0 and 'CATEGORY' in self.processed_lots.columns:
            processed_split_mask = self.processed_lots['CATEGORY'].str.contains(
                'ENGR-SPLIT LOW YIELD', 
                case=False, 
                na=False
            )
            self.processed_split_low_yield_lots = self.processed_lots[processed_split_mask]
            self.processed_regular_lots = self.processed_lots[~processed_split_mask]
            st.info(f"Processed: {len(self.processed_regular_lots)} regular, {len(self.processed_split_low_yield_lots)} split low yield")
        else:
            self.processed_split_low_yield_lots = pd.DataFrame()
            self.processed_regular_lots = self.processed_lots.copy() if len(self.processed_lots) > 0 else pd.DataFrame()
        
        # Separate in-progress lots into regular and split low yield
        if len(self.in_progress_lots) > 0 and 'CATEGORY' in self.in_progress_lots.columns:
            in_progress_split_mask = self.in_progress_lots['CATEGORY'].str.contains(
                'ENGR-SPLIT LOW YIELD', 
                case=False, 
                na=False
            )
            self.in_progress_split_low_yield_lots = self.in_progress_lots[in_progress_split_mask]
            self.in_progress_regular_lots = self.in_progress_lots[~in_progress_split_mask]
            st.info(f"In Progress: {len(self.in_progress_regular_lots)} regular, {len(self.in_progress_split_low_yield_lots)} split low yield")
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
            st.warning("Please contact our engineers")
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
    
    st.title("🏭 Manufacturing Lot Tracking Dashboard")
    
    # Initialize session state
    if 'before_shift_captured' not in st.session_state:
        st.session_state.before_shift_captured = False
    if 'after_shift_captured' not in st.session_state:
        st.session_state.after_shift_captured = False
    if 'analysis_complete' not in st.session_state:
        st.session_state.analysis_complete = False
    
    # Sidebar for configuration
    with st.sidebar:
        st.header("Configuration")
        
        # Google Sheets URL
        spreadsheet_url = st.text_input(
            "Google Sheets URL",
            value="https://docs.google.com/spreadsheets/d/1XlkxQlIjm29dGzUhm9iRHaL6VuOwRSeJc4mCqR6gxhA/edit",
            help="Enter the URL of your Google Sheets document"
        )
        
        # Auto-load hardcoded service account credentials
        if 'google_credentials' not in st.session_state:
            credentials_dict = {
                "type": "service_account",
                "project_id": "meta-imagery-466510-f7",
                "private_key_id": "026a9927f285a61537bd4c365d1bdb094451dbea",
                "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQCednjArM6KiQTx\nCgchekPEGjNgnvrw92IruM7mDv1oiRbTZ+KHwg4QpFoNOi41sKAMnpREhZ7DKLqE\naA79Slz0gnPX9LeH1S7nkrb2XtCiAfkxlM70U0oV2DO/w1N4JfltajH6y8vFtki8\n7jW8OPK4umTrHqSbSZTI9zppoWEmEx1eYk9NWZxJzibcjCisJUmRAZzd4UxqyKLN\njvYFnk5U87LxfO/piABDZLAK7VQKalQifjix1JuhBitjEJeMeTZIat92Y22Iuokk\nDuZM+DHMFp5bmDc7Jzhx6ntyPnc1BqrBpjy3UVb+TslQNgVRKAoDvwod19tkxZbv\n1rsfZ2uVAgMBAAECggEADPY6YuJPw7+4/oF4O1oNrH8LKFJgyvClYFet3t4nhtM9\n4X2MJ1gtf9l9vzq82Gnx8Y5QKPm4FpUgip+baEcaqup30Nik4ZDD1S/oVOdFEBdy\nu4ZFVnFwrDBC7WLsEzYh/Lv0yiO875d9RC0FCrgqzIb8pcncI5Klf7nPVqAbevpw\n0MPGD/BqyeCYKRoIvjmKj7upUv+meV/gD9OhGSvPJuLvm71wTIOB6EfuBl3Djj84\nb9EST9x+BENC3Kz2sMyZUv+6dsxdsf8dbIeAkv6UDM32Iv0KTszjYMEFKgmnX/ar\nYvLcf37uyvvnto0A9nZPgMCyUid7qUk3n+o3AR0GWQKBgQDRo8ibBwOzCIm7npMm\n+46ajyvpahdcElIgYn4ZOlxNNXUKGsHM0o4ohuewCiCnP2S2oyWP9rBvr/J7B16E\nD8C39b4xhGWSE0ikPIJHpmvKg7I47TppbfcAmueeBmixy/d1+yAruus1/ssnGonV\nGcX2KqSU1cmuCte+dEdSVAegvQKBgQDBgW8afrwSMLzjyfrH6xkiobG9NeBWRsDR\nia3oIh2ixk8btDC4AKXk4P4Q27deRa2bWMKh1W107ypXq0x8GtJxL499xYpQxjgB\n7q4gY0dockjF5crA7Wa+yY+sSn/ICAIXvz3BskZ6TZJI7DpOHL82YixTpUH2uyzN\nYqblgGj/uQKBgEzgc/Mt2lRwIBoWZ74W58+UCzVYe2J/MXDAzZ8wwKJrpRTkhQc4\ne3svJY1v2VObsrIrF944R7FdY11scWOaZ0DOtEVyWND9k1ju+5OM2uBz9QpdLFt3\nQOoO5DsV/JSeyIuSYNTIgfLWEeewGrVz8x13u8z8rS3OuhkUiQcO25E9AoGADhiF\npWJyBMk0GUvPTtzbWeB5eBUCoIZK6XikCHLjwcW8YYJAwkaZzxBssYGv29gri1Nt\n6igH7yq05On/ilLR3ZjfVQQczUGDNvDSEl3pB7y7fF7+5ArnHyLDqoNKx6F9tYki\n0IdSBvq7m0BKBwKlEysXm4hAQ97ippt3GOS/wVECgYEAqczLPnyokGzpARLFplvp\nOvpNeKueMjb5tkie82v9ClgyKvn2iThSTEF1PzEfnzyoNkvDcnyBWQLlWMWIu+L9\nT+soASPMjLflZAEB9AKSJxDKLNio8Yx0/9guN12/7wl+NxtaGMa/WB1trybAzjEj\n5950L0Cf9jVy5PCrwTVtTEo=\n-----END PRIVATE KEY-----\n",
                "client_email": "test-200@meta-imagery-466510-f7.iam.gserviceaccount.com",
                "client_id": "113913956273250298443",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/test-200%40meta-imagery-466510-f7.iam.gserviceaccount.com",
                "universe_domain": "googleapis.com"
            }
            st.session_state.google_credentials = credentials_dict
    
    # Main dashboard
    if 'google_credentials' not in st.session_state:
        st.warning("Please contact our engineers")
        st.info("""
        **Setup Instructions:**
        1. Go to Google Cloud Console
        2. Enable Google Sheets API
        3. Create a service account
        4. Download the JSON credentials file
        5. Upload it using the sidebar
        """)
        return
    
    # Initialize dashboard
    dashboard = LotTrackingDashboard(spreadsheet_url)
    
    # Instructions
    with st.expander("📋 Instructions", expanded=True):
        st.markdown("""
        **How to use this dashboard:**
        
        1. **Before Shift**: Click "Capture Before Shift Data" at the start of your shift
        2. **After Shift**: Click "Capture After Shift Data" at the end of your shift  
        3. **Analysis**: The system will automatically analyze which lots were processed
        4. **Export**: Download the results as CSV files
        
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
                st.error("Please contact our engineers")
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
        
        # Data export
        st.header("💾 Export Data")
        dashboard.export_data()
        
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
                    
                    df_display = dashboard.processed_regular_lots.astype(str)
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
                    
                    df_display = dashboard.processed_split_low_yield_lots.astype(str)
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
                    
                    df_display = dashboard.in_progress_regular_lots.astype(str)
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
                    
                    df_display = dashboard.in_progress_split_low_yield_lots.astype(str)
                    st.dataframe(df_display, use_container_width=True)
                else:
                    st.info("No in progress split low yield lots found")

if __name__ == "__main__":
    main()