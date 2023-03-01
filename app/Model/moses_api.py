import json
import requests
import xml.etree.ElementTree as ET

END_POINT = "https://026430010.co.il/MosesTechWebService/Service1.asmx"


def create_issue(data):
    return True
    url = END_POINT + f"/InsertNewCall"
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    response = requests.post(url, data=data, headers=headers)
    if response.ok:
        return True
    return False


def get_product_by_user(user_name, password):
    res = {'table': [{'NumComp': '200401', 'ProductSherotName': 'מחשב - ELISHA-PC'}, {'NumComp': '501384', 'ProductSherotName': 'מחשב - אלישע'}]}
    return list(dict.fromkeys([name["ProductSherotName"].split("-")[0].strip() for name in res["table"]]))
    new_url = END_POINT + f"/AllDataAndCLientId?name={user_name}&password&{password}"
    data = requests.get(new_url, verify=False)

    url = END_POINT + F"/GetClientProductsInService?clientId={data.client_id}&Id={data.user_id}&password&{password}"
    response = requests.get(url, verify=False)
    if response.ok:
        root = ET.fromstring(response.content)
        data = json.loads(root.text)
        distinct_values = set()
        for k in data["table"]:
            for ke, va in k.items():
                clean = va.split('-')[0]
                distinct_values.add(clean)
                print(va.split('-')[0])
        return distinct_values
    return None


def get_product_number_by_user(user_name, password):
    res = {'table': [{'NumComp': '200401', 'ProductSherotName': 'מחשב - ELISHA-PC'}, {'NumComp': '501384', 'ProductSherotName': 'מחשב - אלישע'}]}
    return list(dict.fromkeys([name["NumComp"].split("-")[0].strip() for name in res["table"]]))
    new_url = END_POINT + f"/AllDataAndCLientId?name={user_name}&password&{password}"
    data = requests.get(new_url, verify=False)

    url = END_POINT + F"/GetClientProductsInService?clientId={data.client_id}&Id={data.user_id}&password&{password}"
    response = requests.get(url, verify=False)
    if response.ok:
        root = ET.fromstring(response.content)
        data = json.loads(root.text)
        distinct_values = set()
        for k in data["table"]:
            for ke, va in k.items():
                clean = va.split('-')[1]
                distinct_values.add(clean)
                print(va.split('-')[1])
        return distinct_values
    return None
# Todo: #
#  1) add ProductServiceId to Insert new
#  2) add new end point to get all necessary data (client_id)

