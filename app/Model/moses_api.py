import json
import base64
import requests
import unicodedata
import xml.etree.ElementTree as ET

END_POINT = "https://026430010.co.il/MosesTechWebService/Service1.asmx"
# encode code
# PERFIX_USER_ID = 'MTQ='
# PERFIX_USER_ID = '682'
PERFIX_USER_ID = 'NDQ4'
PERFIX_PASSWORD = 'NDU2Nzg5'

base64_bytes = PERFIX_USER_ID.encode('ascii')
message_bytes = base64.b64decode(base64_bytes)
PERFIX_USER_ID = int(message_bytes.decode('ascii'))

base64_bytes = PERFIX_PASSWORD.encode('ascii')
message_bytes = base64.b64decode(base64_bytes)
PERFIX_PASSWORD = int(message_bytes.decode('ascii'))


def create_kria(data):
    print("creating kria...")
    data["id"] = PERFIX_USER_ID
    data["password"] = PERFIX_PASSWORD
    return True
    url = END_POINT + f"/InsertNewCall"
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    print(f"json '{data}' ")
    print(url)
    response = requests.post(url, data=data, headers=headers)
    if response.ok:
        print(f"kria created! '{response}'")
        return True
    return False


def get_sorted_product_by_user_and_password(client_id):
    print("get_sorted_products.. using perfix_user_id, and perfix_password")
    url = END_POINT + f"/GetClientProductsInServiceForWhatsapp?clientId={client_id}&Id={PERFIX_USER_ID}&password={PERFIX_PASSWORD}"
    print(url)
    response = requests.get(url, verify=False)
    if response.ok:
        root = ET.fromstring(response.content)
        # data = json.loads(root.text)
        try:
            data = json.loads(root.text)
            # return data["table"]
            # Group all products by: {category name: [value_number or value_string]}
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
                    # print("new product")
                else:
                    # distinct_product_values[row['ProductSherotName']].append(row['NumComp'])
                    # distinct_product_values[row['ProductSherotName']].append({f"{row['NumComp']}-{row['Description']}":[row['NumComp']]})
                    if row["NumComp"] != "":
                        distinct_product_values[row['ProductSherotName']].append(
                            {f"{row['NumComp']}-{row['Description']}": [row['NumComp']]})
                    else:
                        distinct_product_values[row['ProductSherotName']].append(
                            {f"{row['Description']}": [row['Description']]})
                    # print("exist product")
            # Rename english product name to hebrew name (only Routers)
            for key, value in distinct_product_values.items():
                _language = "en" if 'HEBREW' not in unicodedata.name(key.strip()[0]) else "he"
                if _language == "en" and key == "Routers":
                    distinct_product_values['ראוטרים'] = distinct_product_values['Routers']
                    del distinct_product_values['Routers']
                    break
            return distinct_product_values
        except Exception as ex:
            print(f"get_sorted_product Exception {ex,root.text}")
            return None
    return None


def login_whatsapp(user, password):
    print("LoginWhatsapp..")
    data = {"username": user, "password": password}
    url = END_POINT + f"/LoginWhatsapp"
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    print(f"json '{data}' ")
    print(url)
    response = requests.post(url, data=data, headers=headers)
    if response.ok:
        root = ET.fromstring(response.content)
        try:
            data = json.loads(root.text)
            print(f"client id {data}")
            return data
        except Exception as ex:
            print(f"login_whatsapp Exception {ex}")
            return None
    return None
