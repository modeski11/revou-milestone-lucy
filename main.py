from subgraph.check import check_subgraph
from subgraph.route import clasify_intent
from subgraph.qna import qna_subgraph
from subgraph.general import general_subgraph
from subgraph.create import create_subgraph
from tools.auth import terminate_session, is_session
from langgraph.graph import START, END, StateGraph
from typing_extensions import TypedDict
from typing import List, Optional
from dotenv import load_dotenv
load_dotenv()

class Message(TypedDict):
    role: str
    content: str

class ParentState(TypedDict):
    messages: List[Message]
    answer: Optional[str]
    session_id: Optional[str]
    file_context: Optional[str]

workflow = StateGraph(ParentState)

def check_node(state: ParentState):
    response = check_subgraph.invoke({"messages": state["messages"], "terminate": False})
    return {"answer": response["answer"]}

def qna_node(state: ParentState):
    response = qna_subgraph.invoke({"messages": state["messages"], "file_context": state.get('file_context', None), "terminate": False})
    return {"answer": response["answer"]}

def general_node(state: ParentState):
    response = general_subgraph.invoke({"messages": state["messages"], "file_context": state.get('file_context', None), "terminate": False})
    return {"answer": response["answer"]}

def create_node(state: ParentState):
    response = create_subgraph.invoke({"messages": state["messages"], "session_id": state["session_id"]})
    return {"answer": response["answer"]}

def terminate_node(state:ParentState):
    if is_session(state['session_id']):
        terminate_session(state['session_id'])
        return {"answer": "Proses pembuatan tiket telah dibatalkan. Silahkan jelaskan keluhan anda lebih lanjut agar kami dapat membantu anda dengan segera."}
    else:
        return {"answer": "Baik. Jika ada keluhan lebih lanjut, silahkan jelaskan secara detil agar kami dapat membantu anda dengan segera."}

workflow.add_node("check", check_node)
workflow.add_node("qna", qna_node)
workflow.add_node("general", general_node)
workflow.add_node("create", create_node)
workflow.add_node("terminate", terminate_node)

workflow.add_conditional_edges(
    START,
    clasify_intent, {
        "check": "check",
        "qna": "qna",
        "general": "general",
        "create":"create",
        "terminate":"terminate"
    }
)
workflow.add_edge("check", END)
workflow.add_edge("qna", END)
workflow.add_edge("general", END)
workflow.add_edge("create", END)
workflow.add_edge("terminate", END)

agent = workflow.compile()

