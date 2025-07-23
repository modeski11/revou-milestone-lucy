from sqlalchemy import create_engine, Table, Column, String, DateTime, MetaData, select, and_, Boolean, inspect
from sqlalchemy.orm import sessionmaker
from email.message import EmailMessage
from dotenv import load_dotenv
import smtplib
from datetime import datetime
from pymilvus import MilvusClient
import openai
import os
import re
load_dotenv()

MAIL_SERVER = os.environ.get('MAIL_SERVER') 
DATABASE_URI = os.environ.get('DEV_DATABASE_URI')
OPENAI_KEY = os.environ.get('OPENAI_API_KEY')
MILVUS_URI = os.environ.get('DEV_MILVUS_URI')

# Database configuration

# SQLAlchemy setup
engine = create_engine(DATABASE_URI, pool_pre_ping=True)
Session = sessionmaker(bind=engine)
metadata = MetaData()

# Define the authentication table
authentication_table = Table(
    'auth', metadata,
    Column('auth_id', String, primary_key=True),
    Column('email', String),
    Column('auth_key', String),
    Column('expiration', DateTime),
    Column('session_id', String),
    Column('is_active', Boolean)
)

session_table  = Table(
    'session', metadata,
    Column('session_no', String, primary_key=True),
    Column('session_id', String),
    Column('ticket_class', String),
    Column('caller_id', String),
    Column('caller_name', String),
    Column('org_id', String),
    Column('title', String),
    Column('description', String),
    Column('service_id', String),
    Column('service_name', String),
    Column('servicesubcategory_id', String),
    Column('servicesubcategory_name', String),
    Column('predicted_description', String),
    Column('predicted_service', String),
    Column('chat_history', String),
    Column('terminate', Boolean),
    Column('authenticated', Boolean)
)

option_table = Table(
    'options', metadata,
    Column('option_id', String, primary_key=True),
    Column('session_id', String),
    Column('option_no', String),
    Column('service_id', String),
    Column('service_name', String),
    Column('subservice_flag', Boolean)
)

openai.api_key = OPENAI_KEY

def insert_authentication(up_row):
    """Insert authentication details into the database."""
    session = Session()
    try:
        insert_stmt = authentication_table.insert().values(
            email=up_row['email'],
            auth_key=up_row['auth_key'],
            expiration=up_row['expiration'],
            session_id=up_row['session_id'],
            is_active=True
        )
        session.execute(insert_stmt)
        session.commit()
    finally:
        session.close()

def initialize_session(up_row, history):
    """Insert session details into the database."""
    session=Session()
    try:
        insert_stmt = session_table.insert().values(
            session_id = up_row['session_id'],
            chat_history = history,
            terminate = False,
            authenticated = False
        )
        session.execute(insert_stmt)
        session.commit()
    finally:
        session.close()

#def update ticket information

def send_authentication_email(email:str, code:str):
    """Send authentication email to the user."""
    msg = EmailMessage()
    msg['Subject'] = "Lucy Bot Authentication Code"
    msg['From'] = 'noreply-lucy@dexagroup.com'
    msg['To'] = email
    msg.set_content(f"Do not reply to this email.\n\nYour authentication code is: {code}.\n Ignore this email if you did not request for it.")

    server = smtplib.SMTP(host=MAIL_SERVER)
    server.send_message(msg)
    server.quit()

def authenticate(session_id:str, code:str) -> bool:
    """Verify email and code authentication."""
    session = Session()
    try:
        select_stmt = select(authentication_table).where(
            and_(
                authentication_table.c.auth_key == code,
                authentication_table.c.expiration > datetime.now(),
                authentication_table.c.session_id == session_id
            )
        ).where(authentication_table.c.is_active==True)
        result = session.execute(select_stmt).fetchone()
        if result is not None:
            update_stmt = authentication_table.update().where(
                and_(
                    authentication_table.c.auth_id == result.auth_id,
                    authentication_table.c.email == result.email
                )
            ).where(
                authentication_table.c.is_active == result.is_active
            ).values(is_active=False)
            session.execute(update_stmt)
            session.commit()
        return result is not None
    finally:
        session.close()

def is_session(session_id:str) -> bool:
    """check if sesssion_id exists in the session table."""
    session = Session()
    try:
        select_stmt = select(session_table.c.session_id).where(
            and_(
                session_table.c.session_id == session_id, 
                session_table.c.terminate == False
            )
        )
        result = session.execute(select_stmt).fetchone()
        return result is not None
    finally:
        session.close()

def is_authenticating(session_id: str) -> bool:
    """Check if session_id exists in the auth table."""
    session = Session()
    try:
        select_stmt = select(authentication_table.c.session_id).where(
            and_(
                authentication_table.c.session_id == session_id,
                authentication_table.c.expiration > datetime.now()
            )
        ).where(
            authentication_table.c.is_active == True
        )
        result = session.execute(select_stmt).fetchone()
        return result is not None
    finally:
        session.close()

def is_authenticated(session_id: str) -> bool:
    """Check if session_id is authenticated.""" 
    session = Session()
    try:
        select_stmt = select(session_table.c.authenticated).where(
            and_(
                session_table.c.session_id == session_id,
                session_table.c.authenticated == True    
            )
        ).where(
            session_table.c.terminate == False
        )
        result = session.execute(select_stmt).fetchone()
        return result is not None
    finally:
        session.close()

def retrieve_session_info(session_id: str):
    """Retrieve session information from the session table."""
    session = Session()
    try:
        select_stmt = select(session_table).where(
            and_(
                session_table.c.session_id == session_id,
                session_table.c.terminate == False
            )
        )
        result = session.execute(select_stmt).fetchone()
        columns = session_table.c.keys()
        return dict(zip(columns, result))
    finally:
        session.close()

def update_session_info(session_id:str, column:str, value:str):
    """Update session information in the session table."""
    session = Session()
    try:
        update_stmt = session_table.update().where(
            and_(
                session_table.c.session_id == session_id,
                session_table.c.terminate == False
            )
        ).values({column: value})
        session.execute(update_stmt)
        session.commit()
    finally:
        session.close()

def terminate_session(session_id:str):
    """Terminate a session in the session table."""
    session = Session()
    try:
        update_stmt = session_table.update().where(
            session_table.c.session_id == session_id
        ).values(terminate=True)
        session.execute(update_stmt)
        session.commit()
    finally:
        session.close()

def recommend_options(title:str, description:str):
    """Recommend options to the user based on the message."""
    def clean_string(s):
        s = re.sub(r'\s+', ' ', s)
        s = re.sub(r'[^\w\s]', '', s)
        return s.strip()
    message = f"title:{title} description:{clean_string(description)}"
    response = openai.embeddings.create(
        model='text-embedding-ada-002',
        input=clean_string(message)
    )
    query_vector= response.data[0].embedding
    client = MilvusClient(
        uri = MILVUS_URI,
        db_name = "milvus_ds"
    )
    res = client.search(
        collection_name="LucyDB",
        anns_field="VECTOR",
        data = [query_vector],
        limit=50,
        output_fields = ["service_id","service_name"]
    )
    result = [hit['entity'] for hits in res for hit in hits]
    options = {result['service_id']:result['service_name'] for result in result}
    return {id: options[id] for id in list(options.keys())[:5]}

def store_options(session_id:str, options:dict, subservice_flag:bool=False):
    session = Session()
    try:
        for index, (service_id, service) in enumerate(options.items(), start=1):
            insert_stmt = option_table.insert().values(
            session_id = session_id,
            option_no = str(index),
            service_id = service_id,
            service_name = service,
            subservice_flag = subservice_flag
            )
            session.execute(insert_stmt)
        session.commit()
    finally:
        session.close()

def retrieve_options(session_id:str, subservice_flag:bool=False):
    session = Session()
    try:
        select_stmt = select(option_table.c.option_no, option_table.c.service_name).where(
            and_(
                option_table.c.session_id == session_id,
                option_table.c.subservice_flag == subservice_flag
            )
        )
        result = session.execute(select_stmt).fetchall()
        return [{'option_no': row.option_no, 'service_name': row.service_name} for row in result]
    finally:
        session.close()

def get_service_id(session_id:str, option_no:str, subservice_flag:bool=False):
    session = Session()
    try:
        select_stmt = select(option_table.c.service_id, option_table.c.service_name).where(
            option_table.c.session_id == session_id
        ).where(
            option_table.c.subservice_flag == subservice_flag
        ).where(
            option_table.c.option_no == option_no
        )
        result = session.execute(select_stmt).fetchone()
        try:
            return result.service_id, result.service_name
        except:
            return None
    finally:
        session.close()

def terminate_session(session_id: str):
    """Terminate a session in the session table if it exists and is not already terminated."""
    session = Session()
    try:
        select_stmt = select(session_table.c.session_id).where(
            and_(
                session_table.c.session_id == session_id,
                session_table.c.terminate == False
            )
        )
        result = session.execute(select_stmt).fetchone()
        if result:
            update_stmt = session_table.update().where(
                and_(
                    session_table.c.session_id == session_id,
                    session_table.c.terminate == False
                )
            ).values(terminate=True)
            session.execute(update_stmt)
            session.commit()
    finally:
        session.close()

def truncate_options(session_id:str):
    """Truncate options for a specific session."""
    session = Session()
    try:
        delete_stmt = option_table.delete().where(
            option_table.c.session_id == session_id
        )
        session.execute(delete_stmt)
        session.commit()
    finally:
        session.close()