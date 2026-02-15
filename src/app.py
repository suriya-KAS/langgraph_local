import streamlit as st
import os
import sys
import requests
from datetime import datetime
# Add project root to path for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
from utils.logger_config import get_logger

# Initialize logger
logger = get_logger(__name__)

# Backend API configuration (new backend)
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8502")
SEND_MESSAGE_URL = f"{API_BASE_URL}/api/chat/message"
HEALTH_URL = f"{API_BASE_URL}/health"

# Default payload configuration (can be overridden via env)
DEFAULT_USER_ID = os.getenv("DEFAULT_USER_ID", "48")
DEFAULT_USERNAME = os.getenv("DEFAULT_USERNAME", "Aditi Toys")
DEFAULT_LOGIN_LOCATION = os.getenv("DEFAULT_LOGIN_LOCATION", "India")
DEFAULT_MARKETPLACES = os.getenv("DEFAULT_MARKETPLACES", "amazon").split(",")
DEFAULT_WALLET_BALANCE = float(os.getenv("DEFAULT_WALLET_BALANCE", "1000.0"))
DEFAULT_APP_VERSION = os.getenv("DEFAULT_APP_VERSION", "1.0.0")

# Page configuration
st.set_page_config(
    page_title="MySellerCentral Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for WhatsApp-style chat
st.markdown("""
<style>
    /* Hide default Streamlit chat components */
    .stChatMessage {
        background-color: transparent !important;
        padding: 0 !important;
    }
    
    /* Chat container */
    .chat-container {
        display: flex;
        flex-direction: column;
        gap: 12px;
        padding: 20px 10px;
        max-width: 1200px;
        margin: 0 auto;
    }
    
    /* Message wrapper - controls alignment */
    .message-wrapper {
        display: flex;
        width: 100%;
        margin-bottom: 8px;
    }
    
    .message-wrapper.user {
        justify-content: flex-end;
    }
    
    .message-wrapper.assistant {
        justify-content: flex-start;
    }
    
    /* Message bubble */
    .message-bubble {
        max-width: 65%;
        padding: 12px 16px;
        border-radius: 12px;
        word-wrap: break-word;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
        position: relative;
        animation: slideIn 0.3s ease-out;
    }
    
    @keyframes slideIn {
        from {
            opacity: 0;
            transform: translateY(10px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    /* User message bubble - right side */
    .message-bubble.user {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-bottom-right-radius: 4px;
        margin-left: auto;
    }
    
    /* Assistant message bubble - left side */
    .message-bubble.assistant {
        background-color: #2d2d2d;
        color: #e0e0e0;
        border-bottom-left-radius: 4px;
        margin-right: auto;
        border: 1px solid #3d3d3d;
    }
    
    /* Avatar styling */
    .message-avatar {
        width: 36px;
        height: 36px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 20px;
        flex-shrink: 0;
        margin: 0 8px;
    }
    
    .message-wrapper.user .message-avatar {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        order: 2;
    }
    
    .message-wrapper.assistant .message-avatar {
        background-color: #2d2d2d;
        border: 2px solid #667eea;
        order: 1;
    }
    
    .message-wrapper.user .message-content {
        order: 1;
    }
    
    .message-wrapper.assistant .message-content {
        order: 2;
    }
    
    .message-content {
        display: flex;
        flex-direction: column;
        max-width: 65%;
    }
    
    /* Markdown styling in bubbles */
    .message-bubble strong {
        font-weight: 700;
    }
    
    .message-bubble.user strong {
        color: #fff;
    }
    
    .message-bubble.assistant strong {
        color: #667eea;
    }
    
    .message-bubble em {
        font-style: italic;
        opacity: 0.9;
    }
    
    .message-bubble code {
        background-color: rgba(255, 255, 255, 0.1);
        padding: 2px 6px;
        border-radius: 4px;
        font-family: 'Courier New', monospace;
        font-size: 0.9em;
    }
    
    .message-bubble.user code {
        background-color: rgba(255, 255, 255, 0.2);
        color: #fff;
    }
    
    .message-bubble.assistant code {
        background-color: rgba(102, 126, 234, 0.2);
        color: #8fa9ff;
    }
    
    .message-bubble pre {
        background-color: #1a1a1a;
        border: 1px solid #3d3d3d;
        border-radius: 6px;
        padding: 12px;
        overflow-x: auto;
        margin: 8px 0;
    }
    
    .message-bubble pre code {
        background-color: transparent;
        padding: 0;
    }
    
    .message-bubble a {
        color: inherit;
        text-decoration: underline;
        opacity: 0.9;
    }
    
    .message-bubble a:hover {
        opacity: 1;
    }
    
    /* Welcome message styling */
    .welcome-container {
        display: flex;
        justify-content: center;
        align-items: center;
        min-height: 60vh;
        text-align: center;
    }
    
    .welcome-message {
        font-size: 2.5rem;
        font-weight: 600;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 1rem;
        animation: fadeIn 1s ease-in;
    }
    
    .welcome-subtitle {
        font-size: 1.2rem;
        color: #666;
        margin-top: 0.5rem;
        animation: fadeIn 1.5s ease-in;
    }
    
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    /* Sidebar styling */
    .sidebar-content {
        padding: 1rem 0;
    }
    
    .sidebar-header {
        font-size: 1.5rem;
        font-weight: 600;
        margin-bottom: 1rem;
        color: #667eea;
    }
    
    /* Chat input styling */
    .stChatInput {
        border-radius: 10px;
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Spinner styling */
    .stSpinner > div {
        border-top-color: #667eea !important;
    }
    
    /* Tables in messages */
    .message-bubble table {
        border-collapse: collapse;
        width: 100%;
        margin: 8px 0;
        font-size: 0.9em;
    }
    
    .message-bubble table th {
        background-color: rgba(102, 126, 234, 0.3);
        padding: 8px;
        text-align: left;
        font-weight: 600;
        border-bottom: 2px solid rgba(102, 126, 234, 0.5);
    }
    
    .message-bubble table td {
        padding: 6px 8px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    .message-bubble.user table th {
        background-color: rgba(255, 255, 255, 0.2);
        border-bottom-color: rgba(255, 255, 255, 0.3);
    }
    
    /* Lists in messages */
    .message-bubble ul,
    .message-bubble ol {
        margin: 8px 0;
        padding-left: 24px;
    }
    
    .message-bubble li {
        margin: 4px 0;
    }
    
    /* Headers in messages */
    .message-bubble h1,
    .message-bubble h2,
    .message-bubble h3 {
        margin-top: 12px;
        margin-bottom: 8px;
    }
    
    .message-bubble.user h1,
    .message-bubble.user h2,
    .message-bubble.user h3 {
        color: #fff;
    }
    
    .message-bubble.assistant h1,
    .message-bubble.assistant h2,
    .message-bubble.assistant h3 {
        color: #667eea;
    }
    
    /* Blockquotes */
    .message-bubble blockquote {
        border-left: 3px solid rgba(255, 255, 255, 0.3);
        padding-left: 12px;
        margin: 8px 0;
        font-style: italic;
        opacity: 0.9;
    }
    
    /* Testing header */
    .testing-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 12px 20px;
        border-radius: 8px;
        margin-bottom: 20px;
        font-size: 0.9rem;
        box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
    }
    
    .testing-header strong {
        color: #fff;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state for chat history + conversation
if "messages" not in st.session_state:
    st.session_state.messages = []
    logger.info("Initialized Streamlit session state for messages")
if "conversation_id" not in st.session_state:
    # Start a new conversation for every new Streamlit session (new user visit)
    st.session_state.conversation_id = "new"
if "user_id" not in st.session_state:
    st.session_state.user_id = DEFAULT_USER_ID
if "username" not in st.session_state:
    st.session_state.username = DEFAULT_USERNAME
if "login_location" not in st.session_state:
    st.session_state.login_location = DEFAULT_LOGIN_LOCATION
if "marketplaces_registered" not in st.session_state:
    st.session_state.marketplaces_registered = [m.strip() for m in DEFAULT_MARKETPLACES if m.strip()]
if "wallet_balance" not in st.session_state:
    st.session_state.wallet_balance = DEFAULT_WALLET_BALANCE


def check_api_health() -> bool:
    try:
        r = requests.get(HEALTH_URL, timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def build_default_payload(message: str, language: str) -> dict:
    """Build default request payload for the new backend."""
    login_location = st.session_state.login_location
    country = "IN" if login_location == "India" else "US"

    return {
        "message": message,
        # "new" triggers backend to create conversation (see routes.py)
        "conversationId": st.session_state.conversation_id or "new",
        "messageType": "text",
        "context": {
            "userId": st.session_state.user_id,
            "username": st.session_state.username,
            "loginLocation": login_location,
            "marketplaces_registered": st.session_state.marketplaces_registered,
            "wallet_balance": st.session_state.wallet_balance,
            "previousIntent": None,
            "clientInfo": {
                "device": "desktop",
                "appVersion": DEFAULT_APP_VERSION,
                "timezone": "UTC",
                "platform": "web",
                "userAgent": "Streamlit",
                "country": country,
            },
            "metadata": {},
        },
        "language": language,
    }


def send_message_to_backend(message: str, language: str) -> dict:
    payload = build_default_payload(message=message, language=language)
    logger.debug(
        "Sending message to backend. conversation_id=%s user_id=%s",
        payload.get("conversationId"),
        st.session_state.user_id,
    )
    r = requests.post(SEND_MESSAGE_URL, json=payload, timeout=60)
    r.raise_for_status()
    return r.json()

# Sidebar for settings
with st.sidebar:
    st.markdown('<div class="sidebar-content">', unsafe_allow_html=True)
    
    # Logo/Header
    st.markdown('<p class="sidebar-header">⚙️ Settings</p>', unsafe_allow_html=True)
    
    # Language selector with emoji
    language = st.selectbox(
        "🌐 Language", 
        ["English", "Spanish", "Hindi", "French", "German"], 
        index=0
    )
    
    st.divider()
    
    # About section
    st.markdown("### 📚 About")
    st.info(
        """
        **MySellerCentral Assistant** helps you with:
        
        ✅ Platform features  
        ✅ AI agents & pricing  
        ✅ Marketplace integrations  
        ✅ Workflow automation  
        
        Ask me anything!
        """
    )
    
    st.divider()

    # Backend status
    if check_api_health():
        st.success("🟢 Backend Connected")
    else:
        st.error("🔴 Backend Offline")

    st.divider()
    
    # Footer
    st.markdown(
        """
        <div style='text-align: center; color: #888; font-size: 0.8rem; margin-top: 2rem;'>
        Powered by AWS Bedrock & LangChain<br>
        © 2024 MySellerCentral
        </div>
        """, 
        unsafe_allow_html=True
    )
    
    st.markdown('</div>', unsafe_allow_html=True)

# Static testing header
st.markdown(f"""
    <div class="testing-header">
        <strong>TESTING PURPOSE:</strong> Client id {st.session_state.user_id}, name: {st.session_state.username.lower()}, list of registered marketplaces: {', '.join(st.session_state.marketplaces_registered)} (added only amazon to test analytics engine)
    </div>
""", unsafe_allow_html=True)

# Main chat area
# Show welcome message if no messages yet
if len(st.session_state.messages) == 0:
    st.markdown("""
        <div class="welcome-container">
            <div>
                <div class="welcome-message">
                    👋 Hello Suriya, Whatsup?
                </div>
                <div class="welcome-subtitle">
                    How can I help you today with MySellerCentral?
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    # Suggestion chips
    st.markdown("### 💬 Get started with these questions:")
    col1, col2, col3 = st.columns(3)
    
    suggestions = [
        ("🤖 AI Agents", "What AI agents are available?"),
        ("💰 Pricing", "Show me pricing plans"),
        ("🛒 Marketplaces", "Which marketplaces do you support?")
    ]
    
    for col, (label, question) in zip([col1, col2, col3], suggestions):
        with col:
            if st.button(label, key=f"suggestion_{label}", use_container_width=True):
                logger.info(f"User clicked suggestion: {label} - {question}")
                st.session_state.messages.append({"role": "user", "content": question})
                st.rerun()
else:
    # Display chat history with WhatsApp-style bubbles
    st.markdown('<div class="chat-container">', unsafe_allow_html=True)
    
    for i, message in enumerate(st.session_state.messages):
        role = message["role"]
        content = message["content"]
        avatar = "🧑‍💼" if role == "user" else "🤖"
        
        # Create WhatsApp-style message bubble
        st.markdown(f"""
            <div class="message-wrapper {role}">
                <div class="message-avatar">{avatar}</div>
                <div class="message-content">
                    <div class="message-bubble {role}">
                        {content}
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

# Chat input at the bottom
if prompt := st.chat_input("Ask about MySellerCentral features, pricing, AI agents...", key="chat_input"):
    # Add user message to chat
    logger.info(f"User sent message: {prompt[:100]}...")
    st.session_state.messages.append(
        {"role": "user", "content": prompt, "timestamp": datetime.now().isoformat()}
    )
    
    # Rerun to show user message immediately
    st.rerun()

# Handle bot response after rerun
if len(st.session_state.messages) > 0 and st.session_state.messages[-1]["role"] == "user":
    last_user_message = st.session_state.messages[-1]["content"]
    logger.info(f"Processing bot response for user message: {last_user_message[:100]}...")
    
    # Create a placeholder for the bot response
    with st.spinner("🔍 Searching knowledge base..."):
        try:
            api_response = send_message_to_backend(last_user_message, language=language)

            if not api_response.get("success"):
                err = api_response.get("error", {}) or {}
                response_text = err.get("message") or "Unknown error"
                wallet_balance = err.get("walletBalance")
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": f"❌ {response_text}",
                        "walletBalance": wallet_balance,
                    }
                )
                st.rerun()

            data = api_response.get("data") or {}
            response_text = data.get("reply") or ""

            # Persist conversationId and wallet balance from backend
            if data.get("conversationId"):
                st.session_state.conversation_id = data["conversationId"]
            if data.get("walletBalance") is not None:
                st.session_state.wallet_balance = data["walletBalance"]

            logger.info(
                "Bot response generated successfully - intent: %s conversation_id: %s",
                data.get("intent", "unknown"),
                st.session_state.conversation_id,
            )

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": response_text,
                    "walletBalance": data.get("walletBalance"),
                    "components": data.get("components"),
                }
            )
            st.rerun()
        except Exception as e:
            logger.error(f"Error generating bot response: {e}", exc_info=True)
            error_message = f"❌ An error occurred: {str(e)}"
            st.session_state.messages.append({"role": "assistant", "content": error_message})
            st.rerun()