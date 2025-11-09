"""
Console-based Attendance Tracking System
Standalone version for command-line usage
"""

import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import json


class ConsoleAttendanceTracker:
    """Console-based attendance tracker for PTEO team"""

    MEMBERS_SHEET_URL = "https://docs.google.com/spreadsheets/d/1mTmcjz93wwF_YJUVoKmGPYsFR73KHiyR8l4uUnSyPYk/edit?usp=sharing"
    ATTENDANCE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1G8_xpSug-dOEODdwLI6wgGphbSNc3Y924IyXoIsyZqs/edit?usp=sharing"
    FULL_TEAM_SIZE = 3
    SHIFTS = ["Shift A", "Shift B", "Shift C"]
    CREDENTIALS_FILE = ".streamlit/secrets.toml"

    def __init__(self):
        self.gc = None
        self.members_data = None
        self.connect_to_sheets()

    def connect_to_sheets(self):
        """Connect to Google Sheets using service account credentials"""
        try:
            # Load credentials from secrets.toml
            import toml
            secrets = toml.load(self.CREDENTIALS_FILE)
            credentials_dict = secrets.get("google_service_account")

            if not credentials_dict:
                # Try loading from JSON file
                with open('pteo-report-f6d4e954b590.json', 'r') as f:
                    credentials_dict = json.load(f)

            credentials = Credentials.from_service_account_info(
                credentials_dict,
                scopes=[
                    'https://www.googleapis.com/auth/spreadsheets',
                    'https://www.googleapis.com/auth/drive'
                ]
            )
            self.gc = gspread.authorize(credentials)
            print("✅ Successfully connected to Google Sheets")
            return True
        except Exception as e:
            print(f"❌ Error connecting to Google Sheets: {str(e)}")
            return False

    def load_team_members(self):
        """Load team members from PTEO Members sheet"""
        try:
            spreadsheet = self.gc.open_by_url(self.MEMBERS_SHEET_URL)

            # Try to find the correct worksheet
            try:
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
            print(f"❌ Error loading team members: {str(e)}")
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
            name = (member.get('Name') or member.get('name') or
                    member.get('Member Name') or member.get('member_name'))

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
            print("\n📝 Recording attendance to Google Sheets...")
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
                print(f"  • {member}: {status}")

            # Append records to sheet
            if records:
                attendance_sheet.append_rows(records)
                print(f"\n✅ Attendance recorded successfully for {len(all_members)} members")
                return True

            return False
        except Exception as e:
            print(f"❌ Error recording attendance: {str(e)}")
            return False

    def run(self):
        """Main console interface"""
        print("\n" + "="*60)
        print("   PTEO TEAM ATTENDANCE TRACKING SYSTEM")
        print("="*60)

        today = datetime.now().strftime("%Y-%m-%d")
        print(f"\n📅 Date: {today}")

        # Step 1: Select shift
        print("\n" + "-"*60)
        print("STEP 1: Which shift is working?")
        print("-"*60)
        for i, shift in enumerate(self.SHIFTS, 1):
            print(f"{i}. {shift}")

        while True:
            try:
                choice = int(input("\nEnter shift number (1-3): "))
                if 1 <= choice <= 3:
                    selected_shift = self.SHIFTS[choice - 1]
                    break
                print("Invalid choice. Please enter 1, 2, or 3.")
            except ValueError:
                print("Invalid input. Please enter a number.")

        print(f"\n✅ Selected: {selected_shift}")

        # Load team members
        if not self.members_data:
            self.load_team_members()

        team_members = self.get_team_members_for_shift(selected_shift)

        # Step 2: Get attendance count
        print("\n" + "-"*60)
        print(f"STEP 2: How many team members are present?")
        print("-"*60)
        print(f"Full team size: {self.FULL_TEAM_SIZE}")

        while True:
            try:
                num_present = int(input(f"\nEnter number of present members (0-{self.FULL_TEAM_SIZE}): "))
                if 0 <= num_present <= self.FULL_TEAM_SIZE:
                    break
                print(f"Invalid number. Must be between 0 and {self.FULL_TEAM_SIZE}.")
            except ValueError:
                print("Invalid input. Please enter a number.")

        # Step 3: Get absent members if needed
        absent_members = []
        if num_present < self.FULL_TEAM_SIZE:
            expected_absent = self.FULL_TEAM_SIZE - num_present
            print(f"\n⚠️  Team is not at full capacity ({num_present}/{self.FULL_TEAM_SIZE})")
            print(f"📋 You must specify exactly {expected_absent} absent member(s)")

            print("\n" + "-"*60)
            print("STEP 3: Who is absent in this shift?")
            print("-"*60)

            if team_members:
                print("\nAvailable team members:")
                for i, member in enumerate(team_members, 1):
                    print(f"{i}. {member}")

                print(f"\n⚠️  IMPORTANT: Select exactly {expected_absent} member(s)")
                print(f"Enter {expected_absent} absent member number(s), separated by commas:")

                while True:
                    try:
                        absent_input = input("Absent members: ").strip()

                        if not absent_input:
                            print(f"❌ Error: You must enter {expected_absent} member(s)")
                            continue

                        absent_indices = [int(x.strip()) - 1 for x in absent_input.split(',')]

                        if len(absent_indices) < expected_absent:
                            print(f"❌ Error: Too few members selected. You need {expected_absent - len(absent_indices)} more.")
                            continue
                        elif len(absent_indices) > expected_absent:
                            print(f"❌ Error: Too many members selected. Remove {len(absent_indices) - expected_absent} member(s).")
                            continue

                        if all(0 <= i < len(team_members) for i in absent_indices):
                            absent_members = [team_members[i] for i in absent_indices]
                            print(f"✅ Correctly selected {expected_absent} absent member(s)")
                            break
                        else:
                            print("❌ Invalid member number. Please try again.")
                    except (ValueError, IndexError):
                        print("❌ Invalid input. Please enter numbers separated by commas (e.g., 1,3)")
            else:
                print(f"\n⚠️  Enter exactly {expected_absent} absent member name(s):")
                while len(absent_members) < expected_absent:
                    remaining = expected_absent - len(absent_members)
                    name = input(f"Absent member {len(absent_members) + 1} of {expected_absent}: ").strip()
                    if name:
                        absent_members.append(name)
                        if remaining - 1 > 0:
                            print(f"   ({remaining - 1} more to enter)")
                    else:
                        print("❌ Name cannot be empty. Please try again.")

                print(f"✅ All {expected_absent} absent member(s) entered")

        # Determine present members
        if team_members:
            present_members = [m for m in team_members if m not in absent_members]
        else:
            present_members = [f"Team Member {i+1}" for i in range(num_present)]

        # Confirmation
        print("\n" + "="*60)
        print("ATTENDANCE SUMMARY")
        print("="*60)
        print(f"Shift: {selected_shift}")
        print(f"Date: {today}")
        print(f"Present: {num_present}/{self.FULL_TEAM_SIZE}")

        if present_members:
            print(f"\n✅ Present Members:")
            for member in present_members:
                print(f"   • {member}")

        if absent_members:
            print(f"\n❌ Absent Members:")
            for member in absent_members:
                print(f"   • {member}")

        # Confirm and record
        print("\n" + "-"*60)
        confirm = input("\nRecord this attendance? (yes/no): ").strip().lower()

        if confirm in ['yes', 'y']:
            success = self.record_attendance(
                shift=selected_shift,
                present_members=present_members,
                absent_members=absent_members,
                date=today
            )

            if success:
                print("\n" + "="*60)
                print("   ✅ ATTENDANCE RECORDED SUCCESSFULLY!")
                print("="*60)
                return True
            else:
                print("\n❌ Failed to record attendance.")
                return False
        else:
            print("\n⚠️  Attendance recording cancelled.")
            return False


def main():
    """Main entry point"""
    try:
        tracker = ConsoleAttendanceTracker()
        tracker.run()
    except KeyboardInterrupt:
        print("\n\n⚠️  Operation cancelled by user.")
    except Exception as e:
        print(f"\n❌ An error occurred: {str(e)}")


if __name__ == "__main__":
    main()
