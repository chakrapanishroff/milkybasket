import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import calendar
import hashlib
import openpyxl
import os
from io import BytesIO

# Load environment variables for local development
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not required on Streamlit Cloud

# Try to import groq, but handle if it's not installed
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    Groq = None

# Database configuration
DATABASE_NAME = 'milk_calculation.db'

# GROQ API Configuration - Support both Streamlit Cloud secrets and local .env
try:
    # Try Streamlit Cloud secrets first
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
except:
    # Fallback to environment variable for local development
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Initialize session state
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
if 'username' not in st.session_state:
    st.session_state.username = None
if 'selected_month' not in st.session_state:
    st.session_state.selected_month = datetime.now().month
if 'selected_year' not in st.session_state:
    st.session_state.selected_year = datetime.now().year
if 'base_milk_cost' not in st.session_state:
    st.session_state.base_milk_cost = 104.00

# Initialize Database
def init_database():
    """Initialize SQLite database and create tables if they don't exist"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            base_milk_cost REAL DEFAULT 104.00,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create milk_records table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS milk_records (
            record_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            record_date DATE NOT NULL,
            is_taken INTEGER DEFAULT 1,
            base_cost REAL DEFAULT 104.00,
            additional_cost REAL DEFAULT 0.00,
            total_cost REAL GENERATED ALWAYS AS (
                CASE WHEN is_taken = 1 THEN base_cost + additional_cost ELSE 0 END
            ) STORED,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            UNIQUE(user_id, record_date)
        )
    """)
    
    # Create monthly_summary table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS monthly_summary (
            summary_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            month INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
            year INTEGER NOT NULL CHECK (year BETWEEN 2020 AND 2100),
            total_days INTEGER NOT NULL,
            milk_taken_days INTEGER NOT NULL,
            total_amount REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            UNIQUE(user_id, month, year)
        )
    """)
    
    # Create indexes
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_milk_records_date 
        ON milk_records(record_date)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_milk_records_user_date 
        ON milk_records(user_id, record_date)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_monthly_summary_user 
        ON monthly_summary(user_id, year, month)
    """)
    
    # Insert default demo user if not exists
    cursor.execute("SELECT COUNT(*) FROM users WHERE username = 'demo'")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO users (username, password_hash, base_milk_cost) VALUES ('demo', 'demo', 104.00)")
    
    conn.commit()
    conn.close()

# Database connection
def get_db_connection():
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        return conn
    except Exception as e:
        st.error(f"Database connection error: {e}")
        return None

# Hash password (simple implementation - use proper hashing in production)
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Authenticate user
def authenticate(username, password):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, password_hash FROM users WHERE username = ?", (username,))
            result = cursor.fetchone()
            conn.close()
            
            if result and result['password_hash'] == password:
                return result['user_id']
            return None
        except Exception as e:
            st.error(f"Authentication error: {e}")
            return None
    return None

# Get user details
def get_user_details(user_id):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT username, base_milk_cost FROM users WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            conn.close()
            if result:
                return {
                    'username': result['username'],
                    'base_milk_cost': result['base_milk_cost']
                }
            return None
        except Exception as e:
            st.error(f"Error fetching user details: {e}")
            return None
    return None

# Update user base milk cost
def update_base_milk_cost(user_id, new_cost):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users 
                SET base_milk_cost = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE user_id = ?
            """, (new_cost, user_id))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            st.error(f"Error updating base milk cost: {e}")
            return False
    return False

# Update user password
def update_password(user_id, new_password):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users 
                SET password_hash = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE user_id = ?
            """, (new_password, user_id))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            st.error(f"Error updating password: {e}")
            return False
    return False

# Create new user
def create_user(username, password, base_milk_cost=104.00):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (username, password_hash, base_milk_cost) VALUES (?, ?, ?)", 
                         (username, password, base_milk_cost))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            st.error(f"Error creating user: {e}")
            return False
    return False

# Get milk records for a month
def get_milk_records(user_id, month, year):
    conn = get_db_connection()
    if conn:
        try:
            query = """
            SELECT record_id, record_date, is_taken, base_cost, additional_cost, 
                   CASE WHEN is_taken = 1 THEN base_cost + additional_cost ELSE 0 END as total_cost,
                   notes
            FROM milk_records
            WHERE user_id = ? AND strftime('%m', record_date) = ? AND strftime('%Y', record_date) = ?
            ORDER BY record_date
            """
            df = pd.read_sql_query(query, conn, params=(user_id, f"{month:02d}", str(year)))
            conn.close()
            
            # Convert record_date to datetime
            if not df.empty:
                df['record_date'] = pd.to_datetime(df['record_date'])
            
            return df
        except Exception as e:
            st.error(f"Error fetching records: {e}")
            return pd.DataFrame()
    return pd.DataFrame()

# Initialize milk records for a month
def initialize_month_records(user_id, month, year, base_cost=None):
    conn = get_db_connection()
    if conn:
        try:
            # Get user's base milk cost if not provided
            if base_cost is None:
                cursor = conn.cursor()
                cursor.execute("SELECT base_milk_cost FROM users WHERE user_id = ?", (user_id,))
                result = cursor.fetchone()
                base_cost = result['base_milk_cost'] if result else 104.00
            
            cursor = conn.cursor()
            num_days = calendar.monthrange(year, month)[1]
            
            for day in range(1, num_days + 1):
                record_date = datetime(year, month, day).date()
                # Set is_taken to 1 (True) by default - all days checked, user unchecks days they didn't take milk
                cursor.execute("""
                    INSERT OR IGNORE INTO milk_records (user_id, record_date, is_taken, base_cost, additional_cost)
                    VALUES (?, ?, 1, ?, 0.00)
                """, (user_id, record_date, base_cost))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            st.error(f"Error initializing records: {e}")
            return False
    return False

# Update milk record
def update_milk_record(record_id, is_taken, base_cost, additional_cost, notes):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE milk_records 
                SET is_taken = ?, base_cost = ?, additional_cost = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
                WHERE record_id = ?
            """, (1 if is_taken else 0, base_cost, additional_cost, notes, record_id))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            st.error(f"Error updating record: {e}")
            return False
    return False

# Calculate monthly summary
def calculate_monthly_summary(user_id, month, year):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            
            # Calculate statistics from milk_records
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_days,
                    SUM(CASE WHEN is_taken = 1 THEN 1 ELSE 0 END) as milk_taken_days,
                    SUM(CASE WHEN is_taken = 1 THEN base_cost + additional_cost ELSE 0 END) as total_amount
                FROM milk_records
                WHERE user_id = ? 
                    AND strftime('%m', record_date) = ? 
                    AND strftime('%Y', record_date) = ?
            """, (user_id, f"{month:02d}", str(year)))
            
            result = cursor.fetchone()
            
            if result:
                total_days = result['total_days'] or 0
                milk_taken_days = result['milk_taken_days'] or 0
                total_amount = result['total_amount'] or 0
                
                # Upsert into monthly_summary
                cursor.execute("""
                    INSERT INTO monthly_summary (user_id, month, year, total_days, milk_taken_days, total_amount)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(user_id, month, year) 
                    DO UPDATE SET 
                        total_days = excluded.total_days,
                        milk_taken_days = excluded.milk_taken_days,
                        total_amount = excluded.total_amount
                """, (user_id, month, year, total_days, milk_taken_days, total_amount))
                
                conn.commit()
                conn.close()
                
                return {
                    'total_days': total_days,
                    'milk_taken_days': milk_taken_days,
                    'total_amount': total_amount
                }
            
            conn.close()
            return None
        except Exception as e:
            st.error(f"Error calculating summary: {e}")
            return None
    return None

# Generate Excel backup
def generate_excel_backup():
    """Generate Excel file with all database tables"""
    conn = sqlite3.connect(DATABASE_NAME)

    users_df = pd.read_sql_query("SELECT * FROM users", conn)
    milk_df = pd.read_sql_query("SELECT * FROM milk_records", conn)
    summary_df = pd.read_sql_query("SELECT * FROM monthly_summary", conn)

    conn.close()

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        users_df.to_excel(writer, sheet_name="users", index=False)
        milk_df.to_excel(writer, sheet_name="milk_records", index=False)
        summary_df.to_excel(writer, sheet_name="monthly_summary", index=False)

    output.seek(0)
    return output

# GROQ AI Assistant
def ask_groq_assistant(question, context=""):
    if not GROQ_AVAILABLE:
        return """
        ⚠️ **AI Assistant Unavailable**
        
        The GROQ library is not installed. To enable the AI Assistant:
        
        1. Add `groq` to your requirements.txt file
        2. Get a GROQ API key from https://console.groq.com
        3. Add it to Streamlit Cloud Secrets (Settings > Secrets):
           ```
           GROQ_API_KEY = "your_key_here"
           ```
        4. Redeploy the application
        """
    
    if not GROQ_API_KEY:
        return """
        ⚠️ **GROQ API Key Not Configured**
        
        To use the AI Assistant:
        
        **For Streamlit Cloud:**
        1. Get a GROQ API key from https://console.groq.com
        2. Go to App Settings > Secrets
        3. Add: `GROQ_API_KEY = "your_key_here"`
        
        **For Local Development:**
        1. Create a `.env` file
        2. Add: `GROQ_API_KEY=your_key_here`
        """
    
    try:
        client = Groq(api_key=GROQ_API_KEY)
        
        system_prompt = f"""You are a helpful assistant for a milk calculation application.
        Context: {context}
        Help users with their questions about milk calculations, records, and monthly summaries.
        Provide clear, concise answers based on the context provided."""
        
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ],
            temperature=0.7,
            max_tokens=1024
        )
        
        return response.choices[0].message.content
    except Exception as e:
        return f"AI Assistant Error: {str(e)}\n\nPlease verify your GROQ_API_KEY is correctly configured."

# Login Page
def login_page():
    st.title("🥛 Milk Calculation App")
    st.subheader("Login")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")
        
        col_login, col_register = st.columns(2)
        
        with col_login:
            if st.button("Login", use_container_width=True):
                if username and password:
                    user_id = authenticate(username, password)
                    if user_id:
                        st.session_state.logged_in = True
                        st.session_state.user_id = user_id
                        st.session_state.username = username
                        
                        # Load user's base milk cost
                        user_details = get_user_details(user_id)
                        if user_details:
                            st.session_state.base_milk_cost = user_details['base_milk_cost']
                        
                        st.success("Login successful!")
                        st.rerun()
                    else:
                        st.error("Invalid username or password")
                else:
                    st.warning("Please enter username and password")
        
        with col_register:
            if st.button("Register New User", use_container_width=True):
                st.session_state.show_register = True
                st.rerun()
        
        st.info("💡 Demo Login: Username: **demo** | Password: **demo**")

# Registration Page
def registration_page():
    st.title("🥛 User Registration")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        new_username = st.text_input("New Username")
        new_password = st.text_input("New Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")
        base_milk_cost = st.number_input("Daily Milk Cost (₹)", min_value=0.0, value=104.0, step=1.0)
        
        col_reg, col_back = st.columns(2)
        
        with col_reg:
            if st.button("Register", use_container_width=True):
                if new_username and new_password and confirm_password:
                    if new_password == confirm_password:
                        if create_user(new_username, new_password, base_milk_cost):
                            st.success("User registered successfully! Please login.")
                            st.session_state.show_register = False
                            st.rerun()
                    else:
                        st.error("Passwords do not match")
                else:
                    st.warning("Please fill all fields")
        
        with col_back:
            if st.button("Back to Login", use_container_width=True):
                st.session_state.show_register = False
                st.rerun()

# Main Application
def main_app():
    st.title(f"🥛 Milk Calculation - Welcome {st.session_state.username}!")
    
    # Sidebar
    with st.sidebar:
        st.header("Navigation")
        
        page = st.radio("Select Page", ["Monthly Records", "User Settings", "AI Assistant"])
        
        st.divider()
        
        # Excel Export Section
        st.subheader("📥 Data Export")
        
        try:
            excel_file = generate_excel_backup()
            st.download_button(
                label="📥 Download Excel Backup",
                data=excel_file,
                file_name=f"milk_database_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key="download_excel"
            )
        except Exception as e:
            st.error(f"❌ Error generating Excel: {str(e)}")
        
        st.divider()
        
        if st.button("Logout", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.user_id = None
            st.session_state.username = None
            st.rerun()
    
    if page == "Monthly Records":
        monthly_records_page()
    elif page == "User Settings":
        user_settings_page()
    elif page == "AI Assistant":
        ai_assistant_page()

# Monthly Records Page
def monthly_records_page():
    st.header("Monthly Milk Records")
    
    # Display current base milk cost
    user_details = get_user_details(st.session_state.user_id)
    if user_details:
        current_cost = user_details['base_milk_cost']
        st.info(f"💰 Your current daily milk cost: ₹{current_cost:.2f}")
    
    # Month and Year selection
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        months = list(calendar.month_name)[1:]
        selected_month_name = st.selectbox("Select Month", months, 
                                          index=st.session_state.selected_month - 1)
        st.session_state.selected_month = months.index(selected_month_name) + 1
    
    with col2:
        st.session_state.selected_year = st.number_input("Select Year", 
                                                         min_value=2020, 
                                                         max_value=2030, 
                                                         value=st.session_state.selected_year)
    
    with col3:
        if st.button("Initialize Month", use_container_width=True):
            if initialize_month_records(st.session_state.user_id, 
                                       st.session_state.selected_month, 
                                       st.session_state.selected_year):
                st.success("Month initialized!")
                st.rerun()
    
    # Fetch records
    df = get_milk_records(st.session_state.user_id, 
                         st.session_state.selected_month, 
                         st.session_state.selected_year)
    
    if not df.empty:
        st.subheader("Daily Records")
        
        # Display records in an editable format
        for idx, row in df.iterrows():
            with st.expander(f"📅 {row['record_date'].strftime('%d %B %Y')} - ₹{row['total_cost']:.2f}"):
                col1, col2, col3, col4 = st.columns([2, 2, 2, 2])
                
                with col1:
                    is_taken = st.checkbox("Milk Taken", 
                                          value=bool(row['is_taken']), 
                                          key=f"taken_{row['record_id']}")
                
                with col2:
                    base_cost = st.number_input("Base Cost (₹)", 
                                               value=float(row['base_cost']), 
                                               min_value=0.0,
                                               step=1.0,
                                               key=f"base_{row['record_id']}")
                
                with col3:
                    additional_cost = st.number_input("Additional Cost (₹)", 
                                                     value=float(row['additional_cost']), 
                                                     min_value=0.0,
                                                     step=1.0,
                                                     key=f"add_{row['record_id']}")
                
                with col4:
                    notes = st.text_input("Notes", 
                                        value=row['notes'] if pd.notna(row['notes']) else "", 
                                        key=f"notes_{row['record_id']}")
                
                if st.button("Update", key=f"update_{row['record_id']}"):
                    if update_milk_record(row['record_id'], is_taken, base_cost, additional_cost, notes):
                        st.success("Record updated!")
                        st.rerun()
        
        # Calculate and display summary
        st.subheader("Monthly Summary")
        summary = calculate_monthly_summary(st.session_state.user_id, 
                                           st.session_state.selected_month, 
                                           st.session_state.selected_year)
        
        if summary:
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Days", summary['total_days'])
            col2.metric("Milk Taken Days", summary['milk_taken_days'])
            col3.metric("Total Amount", f"₹{summary['total_amount']:.2f}")
            
            st.info(f"💰 **Amount to pay to milk vendor: ₹{summary['total_amount']:.2f}**")
    else:
        st.info("No records found. Click 'Initialize Month' to create records for this month.")

# User Settings Page
def user_settings_page():
    st.header("User Settings")
    
    # Update Default Milk Cost
    st.subheader("Update Default Milk Cost")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        user_details = get_user_details(st.session_state.user_id)
        current_cost = user_details['base_milk_cost'] if user_details else 104.00
        
        st.info(f"Current daily milk cost: ₹{current_cost:.2f}")
        
        new_milk_cost = st.number_input("New Daily Milk Cost (₹)", 
                                        min_value=0.0, 
                                        value=float(current_cost), 
                                        step=1.0)
        
        if st.button("Update Milk Cost", use_container_width=True):
            if update_base_milk_cost(st.session_state.user_id, new_milk_cost):
                st.session_state.base_milk_cost = new_milk_cost
                st.success(f"Milk cost updated to ₹{new_milk_cost:.2f}!")
                st.info("Note: This will apply to newly initialized months. Existing records remain unchanged.")
            else:
                st.error("Failed to update milk cost")
    
    st.divider()
    
    # Change Password
    st.subheader("Change Password")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        current_password = st.text_input("Current Password", type="password")
        new_password = st.text_input("New Password", type="password")
        confirm_new_password = st.text_input("Confirm New Password", type="password")
        
        if st.button("Update Password", use_container_width=True):
            if current_password and new_password and confirm_new_password:
                # Verify current password
                if authenticate(st.session_state.username, current_password):
                    if new_password == confirm_new_password:
                        if update_password(st.session_state.user_id, new_password):
                            st.success("Password updated successfully!")
                    else:
                        st.error("New passwords do not match")
                else:
                    st.error("Current password is incorrect")
            else:
                st.warning("Please fill all fields")

# AI Assistant Page
def ai_assistant_page():
    st.header("🤖 AI Assistant")
    
    # Check if GROQ is available
    if not GROQ_AVAILABLE:
        st.error("⚠️ GROQ library not installed!")
        st.info("""
        To use the AI Assistant:
        1. Add `groq` to your requirements.txt file
        2. Get a GROQ API key from https://console.groq.com
        3. Add it to Streamlit Cloud Secrets or local .env file
        4. Redeploy the application
        """)
        return
    
    # Check if GROQ API key is set
    if not GROQ_API_KEY:
        st.error("⚠️ GROQ API Key not configured!")
        st.info("""
        **For Streamlit Cloud:**
        1. Go to App Settings > Secrets
        2. Add: `GROQ_API_KEY = "your_key_here"`
        
        **For Local Development:**
        1. Create a `.env` file
        2. Add: `GROQ_API_KEY=your_key_here`
        """)
        return
    
    st.write("Ask questions about your milk records, calculations, or get help with the app!")
    
    # Get context
    summary = calculate_monthly_summary(st.session_state.user_id, 
                                       st.session_state.selected_month, 
                                       st.session_state.selected_year)
    
    context = f"""
    Current Month: {calendar.month_name[st.session_state.selected_month]} {st.session_state.selected_year}
    """
    if summary:
        context += f"""
    Total Days: {summary['total_days']}
    Milk Taken Days: {summary['milk_taken_days']}
    Total Amount: ₹{summary['total_amount']:.2f}
    """
    
    question = st.text_area("Your Question:", height=100, placeholder="E.g., How much do I need to pay this month?")
    
    if st.button("Ask AI Assistant", type="primary"):
        if question:
            with st.spinner("🤔 Thinking..."):
                response = ask_groq_assistant(question, context)
                st.subheader("Assistant's Response:")
                st.markdown(response)
        else:
            st.warning("Please enter a question")
    
    # Sample questions
    st.subheader("💡 Sample Questions:")
    sample_questions = [
        "How much do I need to pay this month?",
        "How many days did I take milk this month?",
        "What is the average daily cost?",
        "Can you explain how the calculation works?"
    ]
    
    cols = st.columns(2)
    for idx, sq in enumerate(sample_questions):
        with cols[idx % 2]:
            if st.button(sq, key=f"sample_{idx}", use_container_width=True):
                with st.spinner("🤔 Thinking..."):
                    response = ask_groq_assistant(sq, context)
                    st.subheader("Assistant's Response:")
                    st.markdown(response)

# Main Application Flow
def main():
    st.set_page_config(page_title="Milk Calculation App", page_icon="🥛", layout="wide")
    
    # Initialize database
    init_database()
    
    # Initialize show_register state
    if 'show_register' not in st.session_state:
        st.session_state.show_register = False
    
    if not st.session_state.logged_in:
        if st.session_state.show_register:
            registration_page()
        else:
            login_page()
    else:
        main_app()

if __name__ == "__main__":
    main()
