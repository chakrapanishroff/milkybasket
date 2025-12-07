import streamlit as st
import pandas as pd
import pyodbc
from datetime import datetime, timedelta
import calendar
import hashlib
from groq import Groq
import os

# Database configuration
DATABASE_NAME = 'MilkCalculationDB'

# GROQ API Configuration
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

# Database connection
def get_db_connection():
    try:
        conn = pyodbc.connect(
            "DRIVER={ODBC Driver 17 for SQL Server};"
            "SERVER=localhost;"
            f"DATABASE={DATABASE_NAME};"
            "UID=sa;"
            "PWD=Admin@1234;"
            "Encrypt=no;"
            "TrustServerCertificate=yes;"
        )
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
            # For demo purposes, allowing simple password. In production, use hash_password(password)
            cursor.execute("SELECT user_id, password_hash FROM users WHERE username = ?", username)
            result = cursor.fetchone()
            conn.close()
            
            if result and result[1] == password:  # In production: hash_password(password)
                return result[0]
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
            cursor.execute("SELECT username FROM users WHERE user_id = ?", user_id)
            result = cursor.fetchone()
            conn.close()
            return result[0] if result else None
        except Exception as e:
            st.error(f"Error fetching user details: {e}")
            return None
    return None

# Update user password
def update_password(user_id, new_password):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            # In production, use hash_password(new_password)
            cursor.execute("UPDATE users SET password_hash = ?, updated_at = GETDATE() WHERE user_id = ?", 
                         new_password, user_id)
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            st.error(f"Error updating password: {e}")
            return False
    return False

# Create new user
def create_user(username, password):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", 
                         username, password)
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
                   total_cost, notes
            FROM milk_records
            WHERE user_id = ? AND MONTH(record_date) = ? AND YEAR(record_date) = ?
            ORDER BY record_date
            """
            df = pd.read_sql(query, conn, params=(user_id, month, year))
            conn.close()
            return df
        except Exception as e:
            st.error(f"Error fetching records: {e}")
            return pd.DataFrame()
    return pd.DataFrame()

# Initialize milk records for a month
def initialize_month_records(user_id, month, year):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            num_days = calendar.monthrange(year, month)[1]
            
            for day in range(1, num_days + 1):
                record_date = datetime(year, month, day).date()
                cursor.execute("""
                    IF NOT EXISTS (SELECT 1 FROM milk_records WHERE user_id = ? AND record_date = ?)
                    INSERT INTO milk_records (user_id, record_date, is_taken, base_cost, additional_cost)
                    VALUES (?, ?, 1, 104.00, 0.00)
                """, user_id, record_date, user_id, record_date)
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            st.error(f"Error initializing records: {e}")
            return False
    return False

# Update milk record
def update_milk_record(record_id, is_taken, additional_cost, notes):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE milk_records 
                SET is_taken = ?, additional_cost = ?, notes = ?, updated_at = GETDATE()
                WHERE record_id = ?
            """, is_taken, additional_cost, notes, record_id)
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
            cursor.execute("EXEC sp_calculate_monthly_summary ?, ?, ?", user_id, month, year)
            conn.commit()
            
            cursor.execute("""
                SELECT total_days, milk_taken_days, total_amount
                FROM monthly_summary
                WHERE user_id = ? AND month = ? AND year = ?
            """, user_id, month, year)
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return {
                    'total_days': result[0],
                    'milk_taken_days': result[1],
                    'total_amount': result[2]
                }
            return None
        except Exception as e:
            st.error(f"Error calculating summary: {e}")
            return None
    return None

# GROQ AI Assistant
def ask_groq_assistant(question, context=""):
    try:
        # Initialize Groq client
        from groq import Client
        client = Client(api_key=GROQ_API_KEY)
        
        system_prompt = f"""You are a helpful assistant for a milk calculation application.
        Context: {context}
        Help users with their questions about milk calculations, records, and monthly summaries.
        Provide clear, concise answers based on the context provided."""
        
        # Create chat completion
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
    except ImportError:
        # Fallback to alternative import
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
            return f"AI Assistant Error: {str(e)}. Please check your GROQ_API_KEY and groq library version."
    except Exception as e:
        return f"AI Assistant Error: {str(e)}. Please try: pip install --upgrade groq"

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

# Registration Page
def registration_page():
    st.title("🥛 User Registration")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        new_username = st.text_input("New Username")
        new_password = st.text_input("New Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")
        
        col_reg, col_back = st.columns(2)
        
        with col_reg:
            if st.button("Register", use_container_width=True):
                if new_username and new_password and confirm_password:
                    if new_password == confirm_password:
                        if create_user(new_username, new_password):
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
        
        if st.button("Logout"):
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
                col1, col2, col3 = st.columns([2, 2, 2])
                
                with col1:
                    is_taken = st.checkbox("Milk Taken", 
                                          value=bool(row['is_taken']), 
                                          key=f"taken_{row['record_id']}")
                
                with col2:
                    additional_cost = st.number_input("Additional Cost (₹)", 
                                                     value=float(row['additional_cost']), 
                                                     min_value=0.0,
                                                     key=f"add_{row['record_id']}")
                
                with col3:
                    notes = st.text_input("Notes", 
                                        value=row['notes'] if pd.notna(row['notes']) else "", 
                                        key=f"notes_{row['record_id']}")
                
                if st.button("Update", key=f"update_{row['record_id']}"):
                    if update_milk_record(row['record_id'], is_taken, additional_cost, notes):
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
    
    # Check if GROQ API key is set
    if not GROQ_API_KEY or GROQ_API_KEY == 'your_groq_api_key_here':
        st.error("⚠️ GROQ API Key not configured!")
        st.info("""
        To use the AI Assistant, you need to:
        1. Get a GROQ API key from https://console.groq.com
        2. Set it as an environment variable: `GROQ_API_KEY=your_key_here`
        3. Or edit the app.py file and replace 'your_groq_api_key_here' with your actual key
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