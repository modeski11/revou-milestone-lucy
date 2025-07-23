import json
import requests
import os
from dotenv import load_dotenv
load_dotenv()
ITOP_USER = os.environ.get('ITOP_USER')
ITOP_PWD = os.environ.get('ITOP_PWD')
ITOP_URL = os.environ.get('DEV_ITOP_URL')

def get_waiting_approver_id(request_id:str):
    json_data = {
        "operation": "core/get", 
        "class": "ApprovalScheme", 
        "key": f"SELECT ApprovalScheme WHERE obj_key = '{request_id[2:]}'",
        "output_fields": "steps"
    }
    encoded_data = json.dumps(json_data)
    response = requests.post(ITOP_URL, verify=False, data = {'auth_user': ITOP_USER, 'auth_pwd':ITOP_PWD, 'json_data' :encoded_data})
    steps = list(response.json()['objects'].values())[0]['fields']['steps'].split('"') # di parse sesuai hasil array steps yang di output
    largest_index = [i for i,x in enumerate(steps) if x == 'ongoing']
    return steps[max(largest_index)+10]

def get_person_identity(person_id):
    json_data = {
        "operation":"core/get",
        "class":"Person",
        "key": f"SELECT Person WHERE id = {str(person_id)}",
        "output_fields": "friendlyname"
    }
    encoded_data = json.dumps(json_data)
    response = requests.post(ITOP_URL,timeout=10, data = {'auth_user': ITOP_USER, 'auth_pwd':ITOP_PWD, 'json_data': encoded_data}, verify=False)

    if (len(response.json()['objects'])):
        return list(response.json()['objects'].values())[0]['fields']['friendlyname']
    else:
        raise ValueError('Person Not Found')
    
def get_ticket(ticket_id:str):
    if(ticket_id[0] == 'R' or ticket_id[0] == 'r'):
        json_data = {
            "operation": "core/get", 
            "class": "UserRequest", 
            "key": f"SELECT UserRequest WHERE friendlyname LIKE '%{ticket_id}%'", 
            "output_fields": "friendlyname, finalclass, caller_id_friendlyname, agent_id_friendlyname,title, description, service_id_friendlyname, servicesubcategory_id_friendlyname, public_log, status, solution, pending_reason, start_date"
        }
    elif(ticket_id[0] == 'I' or ticket_id[0] == 'i'):
        json_data = {
            "operation" : "core/get",
            "class" : "Incident",
            "key": f"SELECT Incident WHERE friendlyname LIKE '%{ticket_id}%'",
            "output_fields": "friendlyname, finalclass, caller_id_friendlyname, agent_id_friendlyname,title, service_id_friendlyname, servicesubcategory_id_friendlyname, public_log, status, solution, pending_reason, start_date"
        }
    elif(ticket_id[0] == 'P' or ticket_id[0] == 'p'):
        json_data = {
            "operation" : "core/get",
            "class" : "Problem",
            "key": f"SELECT Problem WHERE friendlyname LIKE '%{ticket_id}%'",
            "output_fields" : "friendlyname, finalclass, caller_id_friendlyname, agent_id_friendlyname, title, service_id_friendlyname, servicesubcategory_id_friendlyname, status, start_date"
        }
    elif(ticket_id[0] == 'C' or ticket_id[0] == 'c'):
        json_data = {
            "operation" : "core/get",
            "class" : "Change",
            "key": f"SELECT Change WHERE friendlyname LIKE '%{ticket_id}%'",
            "output_fields" : "friendlyname, finalclass, caller_id_friendlyname, agent_id_friendlyname,title, status, start_date"
        }
    else:
        raise ValueError(f'{ticket_id} is not a valid ticket ID')
    encoded_data = json.dumps(json_data)
    response = requests.post(ITOP_URL, verify=False, data = {'auth_user': ITOP_USER, 'auth_pwd' : ITOP_PWD, 'json_data': encoded_data})
    if (response.json()['objects'] != None):
        ticket_info = list(response.json()['objects'].values())[0]['fields']
        result = {
            "ticket_id": ticket_info.get('friendlyname', ticket_id),
            "user_caller": ticket_info.get('caller_id_friendlyname', ""),
            "title": ticket_info.get('title', ""),
            "service": ticket_info.get('service_id_friendlyname', "").capitalize(),
            "service_subcategory": ticket_info.get('servicesubcategory_id_friendlyname', "").capitalize(),
            "agent": ticket_info.get('agent_id_friendlyname', ""),
            "status": ticket_info.get('status', "Unknown").capitalize(),
            "solution": ticket_info.get('solution', ""),
            "pending_reason": ticket_info.get('pending_reason', ""),
            "date_created": ticket_info.get('start_date', "")
        }
        if('WAIT' in result['status'].upper()):
            try:
                result['waiting_approval_from'] = get_person_identity(get_waiting_approver_id(ticket_id))
            except:
                result['waiting_approval_from'] = "Unknown due to error"
        elif 'REJECT' in result['status'].upper():
            try:
                reject_msg = [[x['user_login'],x['message']] for x in list(response.json()['objects'].values())[0]['fields']['public_log']['entries'] if 'reject' in x['user_login'].lower()][0]
                result['rejected_by'] = reject_msg[0]
                result['rejected_reason'] = reject_msg[1]
            except:
                result['rejected_reason'] = 'Unknown'
        #Result preprocess
        result = {k: v for k, v in result.items() if not (isinstance(v, str) and v.strip() == '')}
        if result["status"].lower() == "new":
            result["status"] = "Waiting for agent assignment"
        return result
    else:
        raise ValueError(f'{ticket_id} ticket is not found')

def get_person_email(email):
    json_data = {
    "operation": "core/get",
    "class": "Person",
    "key": f"SELECT Person WHERE email = '{str(email)}' OR wdemail = '{str(email)}'"
    }
    encoded_data =json.dumps(json_data)
    response = requests.post(ITOP_URL, verify=False, data = {'auth_user': ITOP_USER, 'auth_pwd' : ITOP_PWD, 'json_data': encoded_data})
    return [{"caller_id": value['key'], "email": value['fields']['email'], "org_id": value['fields']['org_id'], "caller_name":value['fields']['first_name']+" "+value['fields']['name']}for _, value in response.json()['objects'].items()]

def get_contract(org_id):
    json_data = {
        "operation": "core/get",
        "class": "CustomerContract",
        "key": f"SELECT CustomerContract WHERE org_id = {org_id}",
        "output_fields":"id, org_id"
    }
    encoded_data = json.dumps(json_data)
    response = requests.post(ITOP_URL, verify=False, data = {'auth_user': ITOP_USER, 'auth_pwd' : ITOP_PWD, 'json_data': encoded_data})
    return [i['fields'] for i in response.json()['objects'].values()][0]

def get_service_contract(contract_id):
    json_data = {
        "operation": "core/get",
        "class": "lnkCustomerContractToService",
        "key": f"SELECT lnkCustomerContractToService WHERE customercontract_id = '{contract_id}'",
        "output_fields":"service_id"
    }
    encoded_data = json.dumps(json_data)
    response = requests.post(ITOP_URL, verify=False, data = {'auth_user': ITOP_USER, 'auth_pwd' : ITOP_PWD, 'json_data': encoded_data})
    return [i['service_id'] for i in [i['fields'] for i in response.json()['objects'].values()]]

def get_service(org_id):
    contract = get_contract(org_id)
    services = get_service_contract(contract['id'])
    json_data = {
        "operation":"core/get",
        "class":"Service",
        "key":f"SELECT Service WHERE status != 'obsolete'",
        "output_fields": "id, friendlyname"
    }
    encoded_data = json.dumps(json_data)
    response = requests.post(ITOP_URL, verify=False, data = {'auth_user': ITOP_USER, 'auth_pwd' : ITOP_PWD, 'json_data': encoded_data})
    service_status = [i['fields'] for i in response.json()['objects'].values()]
    return [service for service in service_status if service['id'] in services]

def get_subservice(service_id):
    json_data = {
        "operation":"core/get",
        "class":"ServiceSubcategory",
        "key":f"SELECT ServiceSubcategory WHERE service_id = '{service_id}' AND status != 'obsolete'",
        "output_fields":"id, name, description"
    }
    encoded_data = json.dumps(json_data)
    response = requests.post(ITOP_URL, verify=False, data = {'auth_user': ITOP_USER, 'auth_pwd' : ITOP_PWD, 'json_data': encoded_data})
    return {i['fields']['id']:i['fields']['name'] for i in response.json()['objects'].values()}

def create_ticket(ticket_class, org_id, caller_id, title, description, history_log, service_id, service_subcategory_id):
    json_data = {
        "operation": "core/create",
        "class": ticket_class,
        "fields": {
            "org_id": org_id,
            "caller_id": caller_id,
            "title": title,
            "description": description,
            "private_log": history_log,
            "service_id": service_id,
            "servicesubcategory_id": service_subcategory_id,
            "urgency": "3",
            "impact": "3",
            "origin": "mobile"
        },
        "comment": "Created by Lucy",
        "output_fields": "id, friendlyname"
    }
    encoded_data = json.dumps(json_data)
    response = requests.post(ITOP_URL, verify=False, data = {'auth_user': ITOP_USER, 'auth_pwd' : ITOP_PWD, 'json_data': encoded_data})
    return list(response.json()['objects'].values())[0]['fields']['friendlyname']

def get_ticket_type(subservice_id:str):
    json_data = {
        "operation":"core/get",
        "class":"ServiceSubcategory",
        "key":f"SELECT ServiceSubcategory WHERE id = '{subservice_id}' AND status != 'obsolete'",
        "output_fields":"id, request_type"
    }
    encoded_data = json.dumps(json_data)
    response = requests.post(ITOP_URL, verify=False, data = {'auth_user': ITOP_USER, 'auth_pwd' : ITOP_PWD, 'json_data': encoded_data})
    type = [value['fields']['request_type'] for _, value in response.json()['objects'].items()][0]
    return "UserRequest" if type == "service_request" else "Incident"