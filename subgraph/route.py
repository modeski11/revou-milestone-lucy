from langchain_openai import ChatOpenAI
import os
from dotenv import load_dotenv
from tools.auth import terminate_session
load_dotenv()
OPENAI_KEY = os.environ.get('OPENAI_API_KEY')
GPT_MODEL  = os.environ.get('GPT_MODEL')
def clasify_intent(input): #bisa diimprove dari segi prompting untuk fleksibilitas
    """
    Uses an LLM to classify user intent with greater accuracy
    """
    history = input['messages']
    if sum(1 for msg in history if msg['role'] == 'assistant') <= 1:
        terminate_session(input['session_id'])
    content = input['messages'][-1]['content']
    file_description = input['file_context']
    llm = ChatOpenAI(model=GPT_MODEL, api_key=OPENAI_KEY)
    
    prompt = f"""
        Classify the user message into one of the following categories:

        - **check_status:** The user wants to check the status of an existing ticket. A valid ticket ID follows the format: a letter (e.g., R or I) followed by a dash and six digits (e.g., R-123456). Only route to "check_status" if the intention to want to check ticket is very clear or if user only sends a ticket id (EX: Mau cek tiket dong).
        - **question:** The user is asking for information or help with an IT-related issue.
        - **create_ticket:** The user agrees to create a ticket **only when the assistant suggests it.** Do not use this category if the user explicitly asks to create a ticket.
        - Correct example: {{Assistant: "Would you like to create a ticket?", User: "Yes"}} -> "create_ticket"
        - **general_response:** General conversation, greetings, or any other non-IT support interactions. This also includes responses that might be answered using the chat history.
        - **terminate:** The user wants to end the current process or explicitly refuses a suggestion from the assistant.
        - Example: {{Assistant: "Would you like to create a ticket?", User: "No"}} -> "terminate"

        ⚠️ Important Rules:
        - Only route to "check_status" if a valid ticket ID is present in the message or if user inquires explicitly that they want to check ticket status (EX: Mau cek tiket dong).
        - Only route to "create_ticket" if the assistant suggests ticket creation and the user agrees.
        - Never stop choosing "create_ticket" if user is in the middle of ticket creation process, only route to anywhere else when it is confirmed that ticket has been made
        - Only route to "terminate" if the user clearly indicates they refuse a ticket creation prompt.

        Chat history: "{str(history)}"  
        User message: "{content}"  
        File Uploaded Description: "{file_description}"

        - respond only with the predefined categories and nothing else, no need to state your reasoning

        Intent category:
    """
    response = llm.invoke(prompt)
    
    # Extract the intent from the response
    intent = response.content.strip().lower()
    
    # Map to valid intents and provide a fallback
    intent_mapping = {
        "check_status": "check",
        "question": "qna", 
        "create_ticket": "create",
        "general_response": "general",
        "terminate":"terminate"
    }
    print(intent)
    if intent != 'create_ticket' and sum(1 for msg in history if msg['role'] == 'assistant') > 6:
        intent = 'terminate'
    return intent_mapping.get(intent,"general")