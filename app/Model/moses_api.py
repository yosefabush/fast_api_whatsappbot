import json
import base64
import requests
import xml.etree.ElementTree as ET

END_POINT = "https://026430010.co.il/MosesTechWebService/Service1.asmx"
# encode code
PERFIX_USER_ID = 'NDQ4'
PERFIX_PASSWORD = 'NDU2Nzg5'

base64_bytes = PERFIX_USER_ID.encode('ascii')
message_bytes = base64.b64decode(base64_bytes)
PERFIX_USER_ID = int(message_bytes.decode('ascii'))

base64_bytes = PERFIX_PASSWORD.encode('ascii')
message_bytes = base64.b64decode(base64_bytes)
PERFIX_PASSWORD = int(message_bytes.decode('ascii'))


def create_kria(data):
    data["id"] = PERFIX_USER_ID
    data["password"] = PERFIX_PASSWORD
    return True
    url = END_POINT + f"/InsertNewCall"
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    response = requests.post(url, data=data, headers=headers)
    if response.ok:
        return True
    return False


def get_subjects_by_user_and_password(client_id):
    print("GetClientProductsInService")
    res = {'table': [{'NumComp': '200401', 'ProductSherotName': 'מחשב - ELISHA-PC'},
                     {'NumComp': '501384', 'ProductSherotName': 'מחשב - אלישע'}]}
    # return list(dict.fromkeys([name["ProductSherotName"].split("-")[0].strip() for name in res["table"]]))
    # return {row['NumComp']:row['ProductSherotName'] for row in res["table"]}
    url = END_POINT + F"/GetClientProductsInService?clientId={client_id}&Id={PERFIX_USER_ID}&password={PERFIX_PASSWORD}"
    response = requests.get(url, verify=False)
    if response.ok:
        root = ET.fromstring(response.content)
        data = json.loads(root.text)
        return data["table"]
        # return data
        # distinct_values = set()
        # for k in data["table"]:
        #     for ke, va in k.items():
        #         clean = va.split('-')[0]
        #         distinct_values.add(clean)
        #         print(va.split('-')[0])
        # return data["table"], distinct_values
    return None


def get_sorted_product_by_user_and_password(client_id):
    res = {'table': [{'NumComp': '200401', 'ProductSherotName': 'מחשב - ELISHA-PC'},
                     {'NumComp': '501384', 'ProductSherotName': 'מחשב - אלישע'}]}
    # data = {"clientId": client_id, "id": PERFIX_USER_ID, "password": PERFIX_PASSWORD}
    # url = END_POINT + f"/GetClientProductsInServiceForWhatsapp"
    # headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    # response = requests.post(url, data=data, headers=headers)
    url = END_POINT + F"/GetClientProductsInServiceForWhatsapp?clientId={client_id}&Id={PERFIX_USER_ID}&password={PERFIX_PASSWORD}"
    response = requests.get(url, verify=False)
    if response.ok:
        root = ET.fromstring(response.content)
        data = json.loads(root.text)
        # return data["table"]
        distinct_product_values = dict()
        for row in data["table"]:
            if row['ProductSherotName'] not in distinct_product_values.keys():
                # distinct_product_values[row['ProductSherotName']] = [row['NumComp']]
                # distinct_product_values[row['ProductSherotName']] = [{f"{row['NumComp']}-{row['Description']}":[row['NumComp']]}]
                if row["NumComp"] != "":
                    distinct_product_values[row['ProductSherotName']] = [
                        {f"{row['NumComp']}-{row['Description']}": [row['NumComp']]}]
                else:
                    distinct_product_values[row['ProductSherotName']] = [
                        {f"{row['Description']}": [row['Description']]}]
                print("new product")
            else:
                # distinct_product_values[row['ProductSherotName']].append(row['NumComp'])
                # distinct_product_values[row['ProductSherotName']].append({f"{row['NumComp']}-{row['Description']}":[row['NumComp']]})
                if row["NumComp"] != "":
                    distinct_product_values[row['ProductSherotName']].append(
                        {f"{row['NumComp']}-{row['Description']}": [row['NumComp']]})
                else:
                    distinct_product_values[row['ProductSherotName']].append(
                        {f"{row['Description']}": [row['Description']]})
                print("exist product")
        return distinct_product_values
    return None


def login_whatsapp(user, password):
    data = {"username": user, "password": password}
    url = END_POINT + f"/LoginWhatsapp"
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    response = requests.post(url, data=data, headers=headers)
    if response.ok:
        root = ET.fromstring(response.content)
        data = json.loads(root.text)
        return data
    return False

# Todo: #
#  1) add ProductServiceId to Insert new
#  2) add new end point to get all necessary data (client_id)
