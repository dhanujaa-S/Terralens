import streamlit as st
from modules.auth import authenticate, create_default_admin
from ui.styles import inject_styles
from ui.components import role_badge


def render_login_page() -> None:
    """Render the centered Terra Lens login screen and handle authentication."""
    inject_styles()

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(
            "<h1 style='text-align:center;color:#1B2A4A;font-size:3.2rem;"
            "font-weight:800;margin-bottom:0;margin-top:1.5rem;'>🌍 Terra Lens</h1>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p style='text-align:center;color:#4A5568;font-size:1.2rem;"
            "margin-top:0.4rem;'>Intelligent Land Record Digitization & "
            "Validation Platform</p>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p style='text-align:center;color:#718096;font-size:1rem;"
            "letter-spacing:0.04em;font-weight:600;'>"
            "AI-POWERED LAND INTELLIGENCE</p>",
            unsafe_allow_html=True,
        )

        st.divider()

        with st.container():
            st.markdown("### Sign In to Continue")
            username = st.text_input(
                "Username", placeholder="Enter your username", key="login_username"
            )
            password = st.text_input(
                "Password", type="password", placeholder="Enter your password",
                key="login_password",
            )
            login_btn = st.button(
                "🔐 Sign In", use_container_width=True, type="primary", key="login_btn"
            )
            st.caption(
                "Demo accounts: admin/admin123  |  verifier1/verify123  |  "
                "uploader1/upload123  |  viewer1/view123"
            )

            if login_btn:
                if not username or not password:
                    st.error("Please enter both username and password.")
                    return

                user = authenticate(username, password)
                if user is None:
                    st.error("❌ Invalid username or password. Please try again.")
                    return

                st.session_state["user"] = user
                st.session_state["user_id"] = user["id"]
                st.session_state["role"] = user["role"]
                st.session_state["logged_in"] = True
                st.session_state["just_logged_in"] = True
                st.rerun()

        st.info(
            "🔒 This system is for authorized personnel only. "
            "All actions are logged for audit."
        )

    st.markdown(
        "<div style='text-align:center;color:#718096;font-size:12.5px;"
        "margin-top:2rem;'>© 2026 Terra Lens — "
        "AI-Powered Land Intelligence</div>",
        unsafe_allow_html=True,
    )
