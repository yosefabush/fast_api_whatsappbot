import json
import base64
import requests
import unicodedata
import xml.etree.ElementTree as ET

END_POINT = "https://026430010.co.il/MosesTechWebService/Service1.asmx"
# encode code
PERFIX_USER_ID = 'Njgy'
# PERFIX_USER_ID = 'NDQ4'
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
    # return True
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
            data = json.loads(root.text, strict=False)
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
                    distinct_product_values['ראוטרים ואינטרנט'] = distinct_product_values['Routers']
                    del distinct_product_values['Routers']
                    break

            #fix_value_over_max_length(distinct_product_values)
            #fix_key_over_max_length(distinct_product_values)
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
            error = data['table'][0].get('error', '')
            if len(error) == 0:
                print(f"LoginWhatsapp data: {data['table']}")
                return data["table"][0]
            #else:
                #error.process_bot_response()
        except Exception as ex:
            print(f"login_whatsapp Exception {ex}")
        return None


def fix_value_over_max_length(distinct_product_values):
    for key, item in distinct_product_values.items():
        for row in item:
            for insideKey, value in row.items():
                for index, trimValue in enumerate(value):
                    if len(trimValue) > 16:
                        print("Value were changed")
                        temp_dict = dict()
                        temp_dict[insideKey] = trimValue[:16]
                        distinct_product_values[key][index] = temp_dict


def fix_key_over_max_length(distinct_product_values):
    temp_dict = dict()
    for key, item in distinct_product_values.items():
        for index, row in enumerate(item):
            for insideKey, value in row.items():
                if len(insideKey) > 16:
                    print("Key were changed")
                    #distinct_product_values[key][index][insideKey[:16]] = row.pop(insideKey)
                    temp_dict[insideKey[:16]]=value
    keys_to_change = list(temp_dict.keys())

    # Update the dictionary keys
    for old_key in keys_to_change:
        for key, item in distinct_product_values.items():
            for index, row in enumerate(item):
                if old_key in row.keys():
                    new_key = temp_dict[old_key]
                    distinct_product_values[new_key] = distinct_product_values.pop(old_key)
    print(temp_dict)