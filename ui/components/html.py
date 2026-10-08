"""Small helper for rendering HTML safely inside Streamlit markdown."""
import streamlit as st


def compact(html: str) -> str:
    """Remove indentation/newlines so Streamlit never treats the HTML as a code block."""
    return " ".join(line.strip() for line in html.strip().splitlines())


def render(html: str) -> None:
    st.markdown(compact(html), unsafe_allow_html=True)