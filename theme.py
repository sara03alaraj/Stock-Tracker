import streamlit as st

def load_theme():
    """Injects custom CSS for the Light Theme Stock Market Updates."""
    
    custom_css = """
    <style>
        /* Import Fonts */
        @import url('https://fonts.googleapis.com/css2?family=Jost:wght@300;400;500;600&family=Bodoni+Moda:wght@400;700&family=Amiri&family=JetBrains+Mono&display=swap');

        /* Global Font Settings */
        html, body, [class*="css"] {
            font-family: 'Jost', sans-serif;
            color: #0f172a;
        }
        
        /* Headers and Logos */
        h1, h2, h3 {
            font-family: 'Bodoni Moda', serif !important;
            color: #004475 !important;
        }

        /* Glassmorphism Header */
        header[data-testid="stHeader"] {
            background-color: rgba(255, 255, 255, 0.85) !important;
            backdrop-filter: blur(12px) !important;
            border-bottom: 1px solid rgba(15, 23, 42, 0.15);
        }

        /* Main App Background Gradient */
        .stApp {
            background: linear-gradient(180deg, #ddf0ff 0%, #eef2f8 100%);
        }

        /* Inputs & Select Boxes */
        div[data-baseweb="input"] > div, 
        div[data-baseweb="select"] > div {
            background-color: rgba(248, 250, 252, 0.7) !important;
            border: 1px solid rgba(15, 23, 42, 0.15) !important;
            border-radius: 8px;
            color: #0f172a;
        }
        
        /* Input Focus Ring */
        div[data-baseweb="input"] > div:focus-within, 
        div[data-baseweb="select"] > div:focus-within {
            border-color: #2563eb !important;
            box-shadow: 0 0 0 1px #2563eb !important;
        }

        /* All Standard Streamlit Buttons AND Download Buttons (Forces ALL to #004475) */
        div.stButton > button, 
        div.stButton > button[kind="primary"], 
        div.stButton > button[kind="secondary"],
        div[data-testid="stDownloadButton"] > button {
            background-color: #004475 !important;
            border: 1px solid #004475 !important;
            border-radius: 8px !important;
            color: #ffffff !important; 
            backdrop-filter: blur(4px) !important;
            transition: all 0.3s ease !important;
        }
        
        /* Target inner text of buttons to ensure it stays white */
        div.stButton > button *, 
        div.stButton > button[kind="primary"] *, 
        div.stButton > button[kind="secondary"] *,
        div[data-testid="stDownloadButton"] > button * {
            color: #ffffff !important; 
        }
        
        /* Button Hover effect (Slightly darker blue so it feels interactive) */
        div.stButton > button:hover, 
        div.stButton > button[kind="primary"]:hover, 
        div.stButton > button[kind="secondary"]:hover,
        div[data-testid="stDownloadButton"] > button:hover {
            background-color: #003355 !important;
            border-color: #003355 !important;
            color: #ffffff !important;
        }
        div.stButton > button:hover *, 
        div.stButton > button[kind="primary"]:hover *, 
        div.stButton > button[kind="secondary"]:hover *,
        div[data-testid="stDownloadButton"] > button:hover * {
            color: #ffffff !important;
        }

        /* Info/Success/Warning/Error Panels (Alerts like Last Sync) */
        div[data-testid="stAlert"] {
            background-color: rgba(248, 250, 252, 0.7) !important;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(15, 23, 42, 0.15);
            border-radius: 12px;
            color: #0f172a;
        }
        
        /* General Text Adjustments */
        .stMarkdown, p, div[data-testid="stText"] {
            color: #475569 !important;
        }
        
        /* Code Blocks */
        code {
            font-family: 'JetBrains Mono', monospace !important;
            color: #1e40af !important;
            background-color: rgba(241, 245, 249, 0.9) !important;
        }
    </style>
    """
    st.markdown(custom_css, unsafe_allow_html=True)