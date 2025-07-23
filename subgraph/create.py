from typing import List, Optional, Dict
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from datetime import datetime, timedelta
from tools.auth import *
from tools.ticket import *
from random import randint
import ast
from dotenv import load_dotenv
GPT_MODEL = os.environ.get('GPT_MODEL')
OPENAI_KEY = os.environ.get('OPENAI_API_KEY')
load_dotenv()
class Message(TypedDict):
    role:str
    content:str

class CreationState(TypedDict):
    messages: List[Message]
    session_id: Optional[str]
    answer:str

def creation_router(state:CreationState):
    """Uses several conditional check to route to the right node for prompting the right data to the user depending on what the process needs"""
    session_id = state['session_id']
    if is_authenticated(session_id):
        return "ticket_enrichment"
    elif not is_session(session_id):
        return "create_session"
    elif not is_authenticating(session_id):
        return "send_authentication"
    elif not is_authenticated(session_id):
        return "check_code"

def create_session(state:CreationState): #Initialize session, goes here if session_id not in session table
    upsert_row = {
        "session_id" : state['session_id']
    }
    truncate_options(state['session_id'])
    initialize_session(upsert_row, str(state['messages'][:-1])) #Initialize and store message before ticket request
    return {"answer": "Baik, sebelum pembuatan tiket, Lucy perlu meng-autentikasi identitas kepegawaian anda melalui email. Mohon masukkan email perusahaan anda."}

def send_authentication(state:CreationState):
    message = state['messages'][-1]['content']
    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', message)
    email = email_match.group(0) if email_match else ""
    whitelist_email = ['@anugrah-argon.com',
    '@dexa-medica.com',
    '@medela-potentia.com',
    '@dexagroup.com',
    '@ferron-pharma.com',
    '@amarthaglobal.com',
    '@equilab-int.com',
    '@ptgue.com',
    '@djembatandua.com',
    '@sarana-titan.com',
    '@goapotik.com',
    '@betapharmacon.com',
    '@assist.id',
    '@fonko-pharma.com',
    '@decametric-medica.com',
    '@gloriousdexa.ph']
    if not any(email.endswith(domain) for domain in whitelist_email):
        return {"answer": "Email yang Anda masukkan tidak valid. Mohon masukkan email perusahaan yang valid."}
    try:
        identity = get_person_email(email)[0]
        upsert_row = {
            "email" : email,
            "auth_key" : f"{randint(0,999999):06d}",
            "expiration" : datetime.now() + timedelta(minutes=5),
            "session_id" : state['session_id']
        }
        update_session_info(state['session_id'], column="caller_id", value=identity['caller_id'])
        update_session_info(state['session_id'], column="org_id", value=identity['org_id'])
        update_session_info(state['session_id'], column='caller_name', value=identity['caller_name'])
        insert_authentication(upsert_row)
        send_authentication_email(upsert_row['email'], upsert_row['auth_key'])
        return {"answer": f"Kode autentikasi telah dikirim ke email {email}. Mohon cek email Anda dan masukkan kode autentikasi yang telah kami kirimkan."}
    except:
        return {"answer": f"Profil anda tidak dapat ditemukan. Mohon periksa kembali email anda"}

def check_code(state:CreationState):
    session_id = state['session_id']
    code = state['messages'][-1]['content']
    if authenticate(session_id, code):
        update_session_info(session_id, column="authenticated", value=True)
        return {"answer": "Autentikasi berhasil, mohon berikan judul dari tiket yang anda inginkan"}
    else:
        return {"answer": "Autentikasi gagal, mohon isi kembali kode autentikasi yang telah kami kirimkan"}

def insert_predicted_description(session_id:str, history:list):
    """Insert predicted description into the session table."""
    content = history[-1]['content']
    llm = ChatOpenAI(model=GPT_MODEL, api_key=OPENAI_KEY)
    try:
        messages = [
            {"role":"system", "content":f"You are an IT Assistant called Lucy that tries to create a brief description about an IT issue using Bahasa Indonesia. Write just the ticket description in sentences while focusing on clarity to help the support team diagnose the problem further with less than 255 characters. Write only the description without mentioning your reasoning. Chat history: {str(history)}"},
            {"role":"user", "content":content}
        ]
        response = llm.invoke(messages).content
        update_session_info(session_id, column="predicted_description", value=response)
    except:
        pass

def insert_predicted_service(session_id:str, history: list, options:dict):
    """Insert predicted service into the session table."""
    content = history[-1]['content']
    llm = ChatOpenAI(model=GPT_MODEL, api_key=OPENAI_KEY)
    try:
        messages = [
            {"role":"system", "content":f"You are an IT Assistant that tries to pick an appropriate service based on the chat history where the user tries to create a ticket based on these options: {options}. Where options is formated as {{'service_id':'service_name'}}, answer using the service_name in options only and nothing else. Chat history: {str(history)}"},
            {"role":"user", "content":content}
        ]
        response = llm.invoke(messages).content
        update_session_info(session_id, column="predicted_service", value=response)
    except:
        pass

#Improve this process accordingly
def ticket_enrichment(state:CreationState):
    try:
        #idea: Enrich step by step tergantung null yang ada didalem state
        session_info = retrieve_session_info(state['session_id'])
        history = state['messages']
        if session_info["title"] is None:
            update_session_info(state['session_id'], column="title", value=state['messages'][-1]['content'])
            insert_predicted_description(state['session_id'], history)
            return {"answer": "Judul tiket telah disimpan, mohon berikan deskripsi dari tiket yang anda inginkan (Mohon berikan deskripsi dengan detil agar Lucy dapat selalu membantu anda)"}
        if session_info["description"] is None:
            update_session_info(state['session_id'], column="description", value=state['messages'][-1]['content'])
            session_info = retrieve_session_info(state['session_id'])
            options = recommend_options(session_info['title'], session_info['description'])
            insert_predicted_service(state['session_id'], history, options)
            store_options(state['session_id'], options)
            return {"answer": "Deskripsi tiket sudah disimpan. Mohon pilih layanan tiket berikut (Jawab hanya dengan salah satu nomor opsi):\n" + "\n".join([f"{num+1}. {name}" for num, (_, name) in enumerate(options.items())])}
        if session_info["service_id"] is None:
            if not state['messages'][-1]['content'].isdigit():
                return {"answer": "Mohon pilih layanan tiket dengan mengirimkan hanya nomor opsi yang sesuai."}
            service_id, service_name = get_service_id(state['session_id'], state['messages'][-1]['content'])
            update_session_info(state['session_id'], column="service_id", value=service_id)
            update_session_info(state['session_id'], column="service_name", value=service_name)
            options = get_subservice(service_id)
            store_options(state['session_id'], options, True)
            return {"answer": "Layanan berhasil terpilih. Mohon pilih subkategori dari layanan tiket berikut (Jawab hanya dengan salah satu nomor opsi):\n" + "\n".join([f"{num+1}. {name}" for num, (_, name) in enumerate(options.items())])}
        if session_info["servicesubcategory_id"] is None:
            if not state['messages'][-1]['content'].isdigit():
                return {"answer": "Mohon pilih subkategori layanan tiket dengan mengirimkan hanya nomor opsi yang sesuai."}
            servicesubcategory_id, servicesubcategory_name = get_service_id(state['session_id'], state['messages'][-1]['content'], True)
            update_session_info(state['session_id'], column="servicesubcategory_id", value=servicesubcategory_id)
            update_session_info(state['session_id'], column="servicesubcategory_name", value=servicesubcategory_name)
            session_info = retrieve_session_info(state['session_id'])
            return {"answer": f"Subkategori tiket telah disimpan. Mohon konfirmasi data tiket:\n- Caller: {session_info['caller_name']}\n- Title: {session_info['title']}\n - Description: {session_info['description']}\n - Service: {session_info['service_name']}\n - Subservice: {session_info['servicesubcategory_name']} \n\n Kirim 'ya' untuk konfirmasi dan kirim 'tidak' untuk membatalkan pembuatan tiket"}
        if(state["messages"][-1]["content"].lower() == "ya"):
            chat_history = '\n'.join([f"{chat['role'].capitalize()}: {chat['content']}" for chat in ast.literal_eval(session_info['chat_history'])])

            ticket_id = create_ticket(get_ticket_type(session_info["servicesubcategory_id"]), session_info["org_id"], session_info["caller_id"], session_info["title"], session_info["description"],"Chat History:\n"+chat_history, session_info["service_id"], session_info["servicesubcategory_id"])
            terminate_session(state['session_id'])
            return {"answer":f"Tiket {ticket_id} sudah dibuat, mohon cek email anda untuk melihat status tiket.\n Sesi telah diakhiri, apakah masih ada hal yang dapat Lucy bantu?"}
        elif(state["messages"][-1]["content"].lower() == "tidak"):
            terminate_session(state['session_id'])
            return {"answer": "Proses pembuatan tiket telah dibatalkan, Apakah masih ada hal yang dapat Lucy bantu?"}
        else:
            return {"answer": "Mohon konfirmasi data tiket dengan mengirimkan hanya 'ya' untuk konfirmasi atau 'tidak' untuk membatalkan pembuatan tiket."}

    except Exception:
        terminate_session(state['session_id'])
        return{"answer": "Proses pembuatan tiket telah gagal, Apakah masih ada hal yang dapat Lucy bantu? Mohon jelaskan keluhan anda lebih lanjut jika ada."}

create_workflow = StateGraph(CreationState)
create_workflow.add_node("create_session", create_session)
create_workflow.add_node("send_authentication", send_authentication)
create_workflow.add_node("check_code", check_code)
create_workflow.add_node("ticket_enrichment", ticket_enrichment)
create_workflow.add_conditional_edges(START, creation_router, {
    "create_session": "create_session",
    "send_authentication": "send_authentication",
    "check_code": "check_code",
    "ticket_enrichment": "ticket_enrichment"
})
create_workflow.add_edge("create_session", END)
create_workflow.add_edge("send_authentication", END)
create_workflow.add_edge("check_code", END)
create_workflow.add_edge("ticket_enrichment", END)

create_subgraph = create_workflow.compile()
