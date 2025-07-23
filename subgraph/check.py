from typing import List, Optional, Dict
from typing_extensions import TypedDict
from langgraph.graph import START, END, StateGraph
from tools.ticket import get_ticket
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import re
import os

load_dotenv()

OPENAI_KEY = os.environ.get('OPENAI_API_KEY')
GPT_MODEL = os.environ.get('GPT_MODEL')

class Message(TypedDict):
    role:str
    content:str

class TicketState(TypedDict):
    messages: List[Message]
    ticket_status: List[dict]
    ticket_id: List[str]
    terminate: bool
    answer:str

def early_stop(state:TicketState):
    if state['terminate']:
        return 'end'
    else:
        return 'continue'

def extract_ticket(state: TicketState):
    try:
        pattern = r"([RrCcPpIi]-\d{6})(?!\d)"
        text = state['messages'][-1]['content']
        result = re.findall(pattern,text)
        if result:
            return {"ticket_id":re.findall(pattern,text)}
        else:
            return {"terminate":True, "answer": "Mohon kesediaan Anda untuk memberikan kode tiket agar kami dapat membantu memeriksa status tiket tersebut. Biasanya kode tiket dimulai dengan satu huruf, diikuti tanda hubung, dan enam digit (misalnya R-123456)."}
    except:
        return {"terminate":True, "answer": "Mohon kesediaan Anda untuk memberikan kode tiket agar kami dapat membantu memeriksa status tiket tersebut. Biasanya kode tiket dimulai dengan satu huruf, diikuti tanda hubung, dan enam digit (misalnya R-123456)."}

def get_status(state: TicketState):
    try:
        tickets = state['ticket_id']
        response = []
        for ticket in tickets:
            try:
                response.append(get_ticket(ticket))
            except:
                response.append({"ticket_id":ticket,"status":"Tiket tidak dapat ditemukan"})
        return {"ticket_status":response}
    except:
        return {"terminate":True, "answer": "Tiket tidak dapat ditemukan, mohon periksa kembali kode tiket yang Anda masukkan atau cek email anda jika ada informasi seperti perubahan tiket dan lainnya."}

def generate_response(state:TicketState):    
    llm = ChatOpenAI(model=GPT_MODEL, api_key=OPENAI_KEY)
    try:
        ticket_status = state['ticket_status']
        response = '\n\n'.join([f"Informasi tiket {status['ticket_id']}:\n" + '\n'.join([f"**{info.replace('_', ' ').capitalize()}**: {status[info]}" for info in status if info != 'ticket_id']) for status in ticket_status])
        return {"answer":response}
    except:
        return {"terminate":True, "answer": "Terjadi galat. Mohon coba lagi"}

check_ticket_workflow = StateGraph(TicketState)

check_ticket_workflow.add_node('extract',extract_ticket)
check_ticket_workflow.add_node('check', get_status)
check_ticket_workflow.add_node('respond', generate_response)

check_ticket_workflow.add_edge(START, 'extract')
check_ticket_workflow.add_conditional_edges('extract',
                                            early_stop, 
                                            {
                                                "continue":'check',
                                                "end": END
                                            })
check_ticket_workflow.add_conditional_edges('check',
                                            early_stop, 
                                            {
                                                "continue":'respond',
                                                "end": END
                                            })
check_ticket_workflow.add_edge('respond',END)

check_subgraph = check_ticket_workflow.compile()