import streamlit as st
from main import agent
from pydantic import BaseModel
from typing import List, Optional
from typing_extensions import TypedDict
import uuid
import datetime
from tools.describer import describe_image
from PIL import Image
import io

class MessageModel(BaseModel):
    role: str
    content: str

class ParentStateModel(BaseModel):
    messages: List[MessageModel]
    answer: Optional[str] = None
    session_id: Optional[str] = None
    file_context: Optional[str] = None

class ChatSession(BaseModel):
    session_id: str
    title: str
    messages: List[dict]
    created_at: datetime.datetime
    last_updated: datetime.datetime

# Initialize session state for chat sessions
if 'chat_sessions' not in st.session_state:
    st.session_state['chat_sessions'] = {}

if 'current_session_id' not in st.session_state:
    # Create initial session
    initial_session_id = str(uuid.uuid4())
    st.session_state['current_session_id'] = initial_session_id
    st.session_state['chat_sessions'][initial_session_id] = {
        'session_id': initial_session_id,
        'title': 'Chat Baru',
        'messages': [{'role': 'assistant', 'content': 'Halo, saya Lucy. Bagaimana saya bisa membantu Anda hari ini?'}],
        'created_at': datetime.datetime.now(),
        'last_updated': datetime.datetime.now()
    }

def create_new_chat():
    """Create a new chat session"""
    new_session_id = str(uuid.uuid4())
    st.session_state['chat_sessions'][new_session_id] = {
        'session_id': new_session_id,
        'title': 'Chat Baru',
        'messages': [{'role': 'assistant', 'content': 'Halo, saya Lucy. Bagaimana saya bisa membantu Anda hari ini?'}],
        'created_at': datetime.datetime.now(),
        'last_updated': datetime.datetime.now()
    }
    st.session_state['current_session_id'] = new_session_id
    st.rerun()

def switch_chat(session_id):
    """Switch to a different chat session"""
    st.session_state['current_session_id'] = session_id
    st.rerun()

def delete_chat(session_id):
    """Delete a chat session"""
    if len(st.session_state['chat_sessions']) > 1:  # Keep at least one session
        del st.session_state['chat_sessions'][session_id]
        # If we deleted the current session, switch to another one
        if st.session_state['current_session_id'] == session_id:
            st.session_state['current_session_id'] = list(st.session_state['chat_sessions'].keys())[0]
        st.rerun()

def update_chat_title(session_id, new_title):
    """Update the title of a chat session"""
    if session_id in st.session_state['chat_sessions']:
        st.session_state['chat_sessions'][session_id]['title'] = new_title
        st.session_state['chat_sessions'][session_id]['last_updated'] = datetime.datetime.now()

def get_chat_preview(messages):
    """Get a preview of the chat for display in sidebar"""
    if len(messages) > 1:  # Skip initial assistant message
        first_user_message = next((msg['content'] for msg in messages if msg['role'] == 'user'), None)
        if first_user_message:
            return first_user_message[:50] + "..." if len(first_user_message) > 50 else first_user_message
    return "Chat Baru"

# Sidebar for chat history
with st.sidebar:
    st.title("💬 Riwayat Chat")
    
    # New chat button
    if st.button("➕ Chat Baru", use_container_width=True, type="primary"):
        create_new_chat()
    
    st.divider()
    
    # Display chat sessions
    current_session_id = st.session_state['current_session_id']
    
    # Sort sessions by last updated (most recent first)
    sorted_sessions = sorted(
        st.session_state['chat_sessions'].items(),
        key=lambda x: x[1]['last_updated'],
        reverse=True
    )
    
    for session_id, session_data in sorted_sessions:
        is_current = session_id == current_session_id
        
        # Create container for each chat item
        chat_container = st.container()
        
        with chat_container:
            col1, col2 = st.columns([4, 1])
            
            with col1:
                # Chat preview/title
                chat_preview = get_chat_preview(session_data['messages'])
                
                if is_current:
                    st.markdown(f"🟢 **{chat_preview}**")
                else:
                    if st.button(
                        chat_preview,
                        key=f"switch_{session_id}",
                        use_container_width=True,
                        help=f"Dibuat: {session_data['created_at'].strftime('%d/%m/%Y %H:%M')}"
                    ):
                        switch_chat(session_id)
            
            with col2:
                # Delete button (only show if more than one session)
                if len(st.session_state['chat_sessions']) > 1:
                    if st.button("🗑️", key=f"delete_{session_id}", help="Hapus chat"):
                        delete_chat(session_id)

st.title("🤖 Lucy - AI Assistant")

current_session = st.session_state['chat_sessions'][current_session_id]

# Display chat history
for message in current_session['messages']:
    with st.chat_message(message['role']):
        # Display text content
        if message.get('content'):
            st.write(message['content'])
        
        # Display image if present
        if message.get('image'):
            try:
                # Convert bytes back to image for display
                image = Image.open(io.BytesIO(message['image']))
                st.image(image, caption="Uploaded Image", width=300)
            except Exception as e:
                st.error(f"Could not display image: {str(e)}")

input_box = st.chat_input("Ketik pesan...", key="chat_input", accept_file=True, file_type=["jpg", "jpeg", "png"])

if input_box:
    text_input = input_box.get('text', None)
    file_context = None
    uploaded_image_bytes = None
    
    # Handle file upload
    if input_box.get('files', None):
        file_input = input_box.get('files', None)[0]
        uploaded_image_bytes = file_input.getvalue()  # Store the image bytes
        file_context = describe_image(uploaded_image_bytes)
    
    # Create user message with image data if present
    user_message = {
        'role': 'user', 
        'content': text_input,
        'image': uploaded_image_bytes if uploaded_image_bytes else None
    }
    
    current_session['messages'].append(user_message)
    current_session['last_updated'] = datetime.datetime.now()
    
    # Update chat title if it's a new chat
    if current_session['title'] == 'Chat Baru' and len(current_session['messages']) >= 2:
        new_title = text_input[:30] + "..." if len(text_input) > 30 else text_input
        current_session['title'] = new_title
    
    # Display user message
    with st.chat_message("user"):
        if text_input:
            st.write(text_input)
        
        # Display the uploaded image
        if uploaded_image_bytes:
            try:
                image = Image.open(io.BytesIO(uploaded_image_bytes))
                st.image(image, caption="Uploaded Image", width=300)
            except Exception as e:
                st.error(f"Could not display image: {str(e)}")
    
    # Prepare state for agent
    state = ParentStateModel(
        messages=[MessageModel(role=msg['role'], content=msg['content']) for msg in current_session['messages']],
        session_id=current_session_id,
        file_context=file_context
    )
    
    # Get agent response
    try:
        result = {"role": "assistant", "content": agent.invoke(state.model_dump()).get('answer', None)}
    except Exception as e:
        result = {"role": "assistant", "content": "Maaf, saya tidak dapat memproses permintaan Anda."}
    
    current_session['messages'].append(result)
    current_session['last_updated'] = datetime.datetime.now()
    
    # Display assistant response
    with st.chat_message("assistant"):
        st.write(result.get('content'))
    
    st.session_state['chat_sessions'][current_session_id] = current_session