# Manufacturing Lot Tracking Dashboard

A Streamlit application for tracking manufacturing lots using Google Sheets integration.

## Features

- **Shift-based Tracking**: Capture lot states before and after work shifts
- **Automated Analysis**: Identifies processed vs in-progress lots
- **Special Categories**: Tracks "split low yield" lots based on comment patterns
- **Interactive Dashboard**: Real-time data visualization with Plotly charts
- **Data Export**: Download analysis results as CSV files
- **Google Sheets Integration**: Direct connection to your manufacturing data

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Google Sheets Authentication

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable the Google Sheets API and Google Drive API
4. Create a service account:
   - Go to IAM & Admin > Service Accounts
   - Click "Create Service Account"
   - Fill in the details and create
5. Generate credentials:
   - Click on the created service account
   - Go to "Keys" tab
   - Click "Add Key" > "Create new key"
   - Choose JSON format and download
6. Share your Google Sheet with the service account email

### 3. Run the Application

```bash
streamlit run streamlit_app.py
```

## Usage

1. **Upload Credentials**: Use the sidebar to upload your Google service account JSON file
2. **Set Sheet URL**: Enter your Google Sheets URL in the sidebar
3. **Capture Before Shift**: Click to capture initial lot state
4. **Capture After Shift**: Click to capture final state and trigger analysis
5. **View Results**: Explore charts, tables, and export data

## Google Sheets Format

Your Google Sheets should contain:
- **OTD STATUS** column: Non-blank values indicate active lots
- **COMMENTS** column: Used to identify "split low yield" lots (containing "TBE-BMPQ-L/YIELD")

## Analysis Logic

- **Processed Lots**: Lots that disappeared between before/after captures
- **In-Progress Lots**: Lots that remain in both captures
- **Split Low Yield**: Processed lots with specific comment pattern

## Export Options

- Processed lots CSV
- In-progress lots CSV  
- Split low yield lots CSV
- Summary statistics