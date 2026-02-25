import streamlit as st
import hashlib
import hmac

def _hash_password(pw: str, salt: str) -> str:
    return hashlib.sha256((salt + pw).encode("utf-8")).hexdigest()

def _verify(pw: str, expected_hash: str, salt: str) -> bool:
    got = _hash_password(pw, salt)
    return hmac.compare_digest(got, expected_hash)

def require_login() -> dict:
    if "auth_user" in st.session_state:
        return st.session_state["auth_user"]

    st.title("Sign in")
    st.caption("Internal tool. Ask admin to add your account in Streamlit secrets.")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    submit = st.button("Login")

    if submit:
        cfg = st.secrets.get("auth", {})
        salt = cfg.get("salt", "change-me")
        users = cfg.get("users", {})
        if username not in users:
            st.error("Invalid username or password.")
            st.stop()

        expected = users[username]
        if _verify(password, expected, salt):
            st.session_state["auth_user"] = {"username": username}
            st.success("Logged in.")
            st.rerun()
        else:
            st.error("Invalid username or password.")
            st.stop()

    st.stop()

def logout_button():
    if st.button("Logout"):
        st.session_state.pop("auth_user", None)
        st.rerun()
