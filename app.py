# ===== Import Libraries =====
import pandas as pd
import streamlit as st
import psycopg2
from datetime import datetime
from io import BytesIO
import plotly.graph_objects as go

# ===== Set Page =====
st.set_page_config(page_title="Dashboard", page_icon=":bar_chart:", layout="wide")

# ===== Connect & Fetch Database =====
connection = psycopg2.connect(host="43.218.52.114",
                              database="postgres",
                              user="data-analyst",
                              password="lEyeo8Ah0k0BE30",
                              port=5432)

# ===== Streamlit Date Input Widgets =====
st.write("# Shipping Performance Report")

# Input pasangan tanggal
dates = []
for i in range(1, 5):
    start_date_input = st.date_input(f"Start Date {i}", value=None)
    end_date_input = st.date_input(f"End Date {i}", value=None)
    dates.append((start_date_input, end_date_input))


# Validasi input
def validate_inputs(dates):
    errors = []

    # Check for empty inputs
    filled_dates = [d for d in dates if d[0] and d[1]]  # Only include fully filled date pairs
    if len(filled_dates) < 1:
        errors.append("At least one start date and end date pair must be provided.")

    # Check for start date > end date
    for start, end in filled_dates:
        if start > end:
            errors.append(f"Start date {start} cannot be greater than end date {end}.")

    # Check for duplicate date ranges
    date_ranges = [(start, end) for start, end in filled_dates]
    if len(date_ranges) != len(set(date_ranges)):
        errors.append("Duplicate date ranges detected.")

    # Check sequential order of dates
    for i in range(len(filled_dates) - 1):
        if filled_dates[i][0] >= filled_dates[i + 1][0]:
            errors.append(f"Start date {filled_dates[i][0]} should be less than start date {filled_dates[i + 1][0]}.")
        if filled_dates[i][1] >= filled_dates[i + 1][1]:
            errors.append(f"End date {filled_dates[i][1]} should be less than end date {filled_dates[i + 1][1]}.")

    return errors, filled_dates


# Tombol Submit
if st.button('Submit'):
    errors, filled_dates = validate_inputs(dates)

    if errors:
        for error in errors:
            st.error(error)
    else:
        results = []
        gmv_final_statuses = []
        date_labels = []

        for start_date_input, end_date_input in filled_dates:
            if start_date_input and end_date_input:  # Process only filled date pairs
                # Konversi date ke datetime agar bisa mendapatkan Unix Time
                start_date = int(datetime.combine(start_date_input, datetime.min.time()).timestamp())
                end_date = int(datetime.combine(end_date_input, datetime.min.time()).timestamp())

                # Query SQL gabungan dengan input parameter dari variabel Python
                query = f"""
                SELECT
                    COALESCE(SUM(CASE WHEN so.status IN (500, 702, 703) THEN so.gmv_shipment END), 0) AS gmv_final_status,
                    -- Mengambil GMV EOM (25 Agustus 2024 - 25 September 2024)
                    (SELECT COALESCE(SUM(gmv_shipment), 0)
                     FROM shipment_orders
                     WHERE created_at >= {start_date}
                       AND created_at <= {end_date}) AS gmv_eom,
                    COUNT(CASE WHEN so.status >= 300 AND so.status < 500 THEN 1 END) AS order_qty,

                    -- R Transacting User: Pengguna yang sudah pernah bertransaksi sebelum rentang waktu
                    COUNT(DISTINCT(CASE WHEN EXISTS (
                        SELECT 1 FROM shipment_orders so3
                        WHERE so3.created_by = so.created_by
                          AND so3.created_at < {start_date}
                    ) THEN so.created_by END)) AS r_trx_user,

                    -- N Transacting User: Pengguna baru yang pertama kali bertransaksi dalam rentang waktu
                    COUNT(DISTINCT(CASE WHEN NOT EXISTS (
                        SELECT 1 FROM shipment_orders so2
                        WHERE so2.created_by = so.created_by
                          AND so2.created_at < {start_date}
                    ) THEN so.created_by END)) AS n_trx_user,

                    (SELECT COUNT(DISTINCT ul.user_id)
                     FROM user_logs ul
                     WHERE ul.created_at >= {start_date}
                       AND ul.created_at <= {end_date}) AS active_user,
                    COUNT(DISTINCT so.created_by) AS trx_user,
                    AVG(so.transaction_value) AS aov,
                    CASE
                        WHEN COUNT(CASE WHEN so.status IN (500, 703) THEN 1 END) = 0
                        THEN 0
                        ELSE (COUNT(CASE WHEN so.status = 702 THEN 1 END)::NUMERIC /
                              COUNT(CASE WHEN so.status IN (500, 703) THEN 1 END)::NUMERIC)
                    END AS cod_rts
                FROM shipment_orders so
                WHERE so.created_at >= {start_date} AND so.created_at <= {end_date};
                """

                # Menjalankan query dan menyimpan hasilnya
                cur = connection.cursor()
                cur.execute(query)
                rows = cur.fetchall()

                # Menyimpan hasil dalam list
                results.append(rows[0])
                gmv_final_statuses.append(rows[0][0])
                date_labels.append(f"{start_date_input.strftime('%Y-%m-%d')} sd {end_date_input.strftime('%Y-%m-%d')}")

        # Store results and dates in session state
        st.session_state.results = results
        st.session_state.dates = filled_dates
        st.session_state.gmv_final_statuses = gmv_final_statuses
        st.session_state.date_labels = date_labels

# Jika hasil sudah disimpan di session state, tampilkan tabel, chart, dan tombol unduh
if st.session_state.get('results'):
    results = st.session_state.results
    dates = st.session_state.dates
    gmv_final_statuses = st.session_state.gmv_final_statuses
    date_labels = st.session_state.date_labels

    # Menggabungkan hasil dalam DataFrame
    columns = ['GMV (Final Status)', 'GMV EOM', 'Orders Qty', 'R Transacting User',
               'N Transacting User', 'AU (Aktive User)', 'TU (Trx User)', 'AOV', 'COD RTS%']
    df = pd.DataFrame(results, columns=columns)

    # Menampilkan DataFrame hasil query
    df.insert(0, 'Performance',
              [f"{start_date_input} sd {end_date_input}" for start_date_input, end_date_input in dates])
    df = df.transpose()
    df.columns = df.iloc[0]
    df = df.iloc[1:]
    st.dataframe(df, use_container_width=True)

    # Convert DataFrame to Excel
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=True)
    processed_data = output.getvalue()

    # Format file name with start date of first period and end date of last period
    start_date_str = dates[0][0].strftime('%Y-%m-%d')
    end_date_str = dates[-1][1].strftime('%Y-%m-%d')
    file_name = f"shipping_report_{start_date_str}_{end_date_str}.xlsx"

    # Tombol Download
    st.download_button(label='Download as Excel',
                       data=processed_data,
                       file_name=file_name,
                       mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    # Create line chart using Plotly
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=date_labels, y=gmv_final_statuses,
        mode='lines+markers',
        line=dict(color='royalblue', width=4),
        marker=dict(size=10),
        text=date_labels,
        hoverinfo='text+y'
    ))

    # Update layout for aesthetics
    fig.update_layout(
        title='GMV Final Status Over Time',
        xaxis_title='Period',
        yaxis_title='GMV Final Status',
        hovermode='x unified',
        template='plotly_white',
        xaxis=dict(tickmode='linear'),
        yaxis=dict(tickformat='.2f'),
        title_x=0.5,
        margin=dict(l=0, r=0, t=50, b=0),
        height=400
    )

    # Display the chart
    st.plotly_chart(fig, use_container_width=True)

    # Download button for the chart as PNG
    st.download_button(
        label="Download chart as PNG",
        data=fig.to_image(format="png"),
        file_name="gmv_final_status_chart.png",
        mime="image/png"
    )
