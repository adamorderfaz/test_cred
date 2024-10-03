import streamlit as st
import snowflake.connector

# Display a message to indicate the app is running
st.title("Snowflake Connection Test")

# Test if secrets are accessible
try:
    # Access secrets using st.secrets
    user = st.secrets["snowflake"]["user"]
    password = st.secrets["snowflake"]["password"]
    account = st.secrets["snowflake"]["account"]
    warehouse = st.secrets["snowflake"]["warehouse"]
    database = st.secrets["snowflake"]["database"]
    schema = st.secrets["snowflake"]["schema"]

    st.success("Secrets loaded successfully!")

    # Establish connection to Snowflake
    conn = snowflake.connector.connect(
        user=user,
        password=password,
        account=account,
        warehouse=warehouse,
        database=database,
        schema=schema
    )
    
    # Execute a simple query to test the connection
    cur = conn.cursor()
    cur.execute("SELECT CURRENT_USER(), CURRENT_ACCOUNT(), CURRENT_DATABASE();")
    data = cur.fetchone()
    
    # Display the result of the query
    st.write("Connection successful! Here is the result:")
    st.write(data)

except Exception as e:
    st.error(f"Error: {e}")
