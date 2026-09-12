import streamlit as st


def apply_voolkia_style():
    st.markdown(
        """
        <style>
            :root {
                --voolkia-orange: #ff7000;
                --voolkia-orange-2: #ff9100;
                --voolkia-gray: #ededed;
                --voolkia-dark: #240300;
            }

            .stApp { background: #ffffff; }
            h1, h2, h3 { color: #240300; }

            div.stButton > button[kind="primary"],
            div.stDownloadButton > button[kind="primary"] {
                background-color: #ff7000;
                border-color: #ff7000;
                color: white;
                font-weight: 700;
            }

            div.stButton > button[kind="primary"]:hover,
            div.stDownloadButton > button[kind="primary"]:hover {
                background-color: #ff9100;
                border-color: #ff9100;
            }

            [data-testid="stSidebar"] { background-color: #ededed; }

            [data-testid="stMetric"] {
                background: #f8f8f8;
                border: 1px solid #ededed;
                border-radius: 14px;
                padding: 14px;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )
