import streamlit as st

from auth import verify_user

st.set_page_config(page_title="CAR", layout="wide")


def login_form() -> None:
    st.title("🔒 Sign in")
    with st.form("login"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in")

    if submitted:
        if verify_user(username, password):
            st.session_state.authenticated = True
            st.session_state.username = username
            st.rerun()
        else:
            st.error("Invalid username or password.")


if not st.session_state.get("authenticated"):
    login_form()
    st.stop()

with st.sidebar:
    st.caption(f"Signed in as **{st.session_state.username}**")
    if st.button("Log out"):
        st.session_state.clear()
        st.rerun()

dashboard = st.Page("views/Dashboard.py", title="Dashboard", icon="📊", default=True)
momentum_scanner = st.Page("views/Momentum_Scanner.py", title="Momentum Scanner", icon="🚀")

pg = st.navigation([dashboard, momentum_scanner])
pg.run()
