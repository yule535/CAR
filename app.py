import streamlit as st

st.set_page_config(page_title="CAR", layout="wide")

dashboard = st.Page("pages/Dashboard.py", title="Dashboard", icon="📊", default=True)
momentum_scanner = st.Page("pages/Momentum_Scanner.py", title="Momentum Scanner", icon="🚀")

pg = st.navigation([dashboard, momentum_scanner])
pg.run()
