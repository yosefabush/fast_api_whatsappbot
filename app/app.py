import os
import pytz
import uvicorn
import requests
import threading
from typing import List
from Model.models import *
from datetime import datetime
from json import JSONDecodeError
from sqlalchemy.orm import Session
from requests.structures import CaseInsensitiveDict
from DatabaseConnection import SessionLocal, engine
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status

requests.packages.urllib3.disable_warnings()

PORT = os.getenv("PORT", default=443)
TOKEN = os.getenv('TOKEN', default=None)
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", default=None)
PHONE_NUMBER_ID_PROVIDER = os.getenv("NUMBER_ID_PROVIDER", default="104091002619024")
FACEBOOK_API_URL = 'https://graph.facebook.com/v16.0'
WHATS_API_URL = 'https://api.whatsapp.com/v3'
TIMER_FOR_SEARCH_OPEN_SESSION_SEC = 300
MAX_NOT_RESPONDING_TIMEOUT_MINUETS = 5
TIME_PASS_FROM_LAST_SESSION = 2
if None in [TOKEN, VERIFY_TOKEN]:
    raise Exception(f"Error on env var '{TOKEN, VERIFY_TOKEN}' ")
# db = Database()
sender = None
language_support = {"he": "he_IL", "en": "en_US"}

headers = CaseInsensitiveDict()
headers["Accept"] = "application/json"
headers["Authorization"] = f"Bearer {TOKEN}"
session_open = False
conversation = {
    "Greeting": "היי ברוך הבא לבוט של מוזס!\nתודה שפנית אלינו 😊\n"
                "כדי לפתוח קריאה נעבור תהליך זיהוי קצר,"
                " בכל שלב תוכלו לרשום לנו יציאה והמערכת תתחיל את השיחה מחדש"
}
WORKING_HOURS_START_END = (8, 17)
non_working_hours_msg = """שלום, שירות הוואצפ פעיל בימים א'-ה' בשעות 08:00- 17:30. 
ניתן לפתוח קריאה באתר דרך הקישור הבא 
 026430010.co.il
ונחזור אליכם בשעות הפעילות

בברכה,
מוזס מחשבים."""
# Define a list of predefined conversation steps
conversation_steps = ConversationSession.conversation_steps_in_class

# conversation_history = list()
app = FastAPI(debug=False)


# Request Models.
class WebhookRequestData(BaseModel):
    object: str = ""
    entry: List = []


@app.on_event("startup")
def startup():
    print("startup DB create_all")
    Base.metadata.create_all(bind=engine)
    schedule_search_for_inactive_sessions()


@app.on_event("shutdown")
def shutdown():
    print("shutdown DB dispose")
    engine.dispose()


# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/")
def root():
    print("root router 1!")
    return {"Hello": "FastAPI"}


@app.get("/user/{user}", status_code=200)
def get_user(user, response: Response, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.name == user).first()
    if db_user:
        return {"Result": f"Found {db_user.name}"}
    # response.status_code = status.HTTP_204_NO_CONTENT
    return {"Result": f"{user} not Found"}


@app.post("/users/")
# def create_user(user: UserSchema, db: Session = Depends(get_db)):
def create_user(user, db: Session = Depends(get_db)):
    user = User(db=db, name="Alice", password="password", phone="555-1234")
    # user_ = User(db, user)
    existing_user = db.query(User).filter(User.phone == user.phone).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Phone number already registered")
    db.add(user)
    db.commit()
    db.refresh(user)
    return f"'{user}' Created"


@app.get("/all_users")
async def get_users(db=Depends(get_db)):
    # result = db.execute(text("SELECT * FROM users"))
    # rows = result.fetchall()
    result = db.query(User).all()
    return {"Results": result}


@app.post("/webhook")
async def handle_message_with_request_scheme(data: WebhookRequestData, db: Session = Depends(get_db)):
    try:
        print("handle_message webhook")
        global sender
        message = "ok"
        if data.object == "whatsapp_business_account":
            for entry in data.entry:
                messaging_events = [event for event in entry.get("changes", []) if
                                    event.get("field", None) == "messages"]
                print(f"total events: '{len(messaging_events)}'")
                for event in messaging_events:
                    type = event['value']['messages'][0].get('type', None)
                    if type is None:
                        print("None type")
                        return Response(content="None type found", status_code=status.HTTP_400_BAD_REQUEST)
                    if type == "text":
                        print("text")
                        text = event['value']['messages'][0]['text']['body']
                        sender = event['value']['messages'][0]['from']
                        message = process_bot_response(db, text)
                    elif type == "button":
                        print("Button")
                        text = event['value']['messages'][0]['button']['text']
                        sender = event['value']['messages'][0]['from']
                        message = process_bot_response(db, text, button_selected=True)
                    elif type == "interactive":
                        print("interactive")
                        if event['value']['messages'][0]['interactive']["type"] == "button_reply":
                            text = event['value']['messages'][0]['interactive']['button_reply']["title"]
                        elif event['value']['messages'][0]['interactive']["type"] == "list_reply":
                            text = event['value']['messages'][0]['interactive']['list_reply']['title']
                        else:
                            raise Exception("unknown type {event['value']['messages'][0]['interactive']}")
                        sender = event['value']['messages'][0]['from']
                        message = process_bot_response(db, text, button_selected=True)
                        res = f"Json: '{event['value']['messages'][0]}'"
                        print(res)
                    else:
                        print(f"Type '{type}' is not valid")
                        message = f"Json: '{event['value']['messages'][0]}'"
                        print(message)
                    return Response(content=message)
        else:
            print(data.object)
        return Response(content=message)
    except JSONDecodeError:
        message = "Received data is not a valid JSON (JSONDecodeError)"
    except Exception as ex:
        print(f"Exception: '{ex}'")
        message = str(ex)
    return Response(content=message)


@app.get("/webhook")
async def verify(request: Request):
    """
    On webhook verification VERIFY_TOKEN has to match the token at the
    configuration and send back "hub.challenge" as success.
    """
    print("verify token")
    if request.query_params.get("hub.mode") == "subscribe" and request.query_params.get("hub.challenge"):
        if not request.query_params.get("hub.verify_token") == os.environ["VERIFY_TOKEN"]:
            return Response(content="Verification token mismatch", status_code=403)
        return Response(content=request.query_params["hub.challenge"])

    return Response(content="Required arguments haven't passed.", status_code=400)


def check_for_timeout(db, sender):
    return True
    session = db.query(ConversationSession).filter(ConversationSession.user_id == sender,
                                                   ConversationSession.session_active == False).order_by(
        ConversationSession.start_data.desc()).first()
    if session is None:
        return True
    diff_time = datetime.datetime.now() - session.start_data
    seconds_in_day = 24 * 60 * 60
    minutes, second = divmod(diff_time.days * seconds_in_day + diff_time.seconds, 60)
    if TIME_PASS_FROM_LAST_SESSION > minutes:
        return False
    return True


def process_bot_response(db, user_msg: str, button_selected=False) -> str:
    if after_working_hours():
        print("after_working_hours")
        send_response_using_whatsapp_api(non_working_hours_msg)
        return non_working_hours_msg
    log = ""
    if user_msg in ["אדמין", "servercheck"]:
        created_issues_history = db.query(Issues).filter(Issues.issue_sent_status == True).all()
        for issue in created_issues_history:
            log += f"Conversation ID: {issue.conversation_id} Sent message: {issue.issue_data}\n"
        send_response_using_whatsapp_api(log)
        return log
    if user_msg.lower() in ["reset"]:
        conversation_history = db.query(ConversationSession).filter(ConversationSession.session_active == True).all()
        for session in conversation_history:
            # session.set_status(db, False)
            session.session_active = False
            db.commit()
        print("All conversation were reset")
        return "All conversation were reset"
    next_step_conversation_after_increment = ""
    session = check_if_session_exist(db, sender)
    if session is None or session.call_flow_location == 0:
        if not check_for_timeout(db, sender):
            print(f"Please wait '{TIME_PASS_FROM_LAST_SESSION}' min")
            send_response_using_whatsapp_api(
                f"""אנא המתן אנא המתן '{TIME_PASS_FROM_LAST_SESSION}' דקות לפני הפנייה הבאה""", sender)
            return f"""אנא המתן אנא המתן '{TIME_PASS_FROM_LAST_SESSION}' דקות לפני הפנייה הבאה"""
        print(f"Hi {sender} You are new!:")
        steps_message = ""
        for key, value in conversation_steps.items():
            steps_message += f"{value} - {key}\n"
        print(f"{steps_message}")

        send_response_using_whatsapp_api(conversation["Greeting"])
        # Handling session after restart dou to max login attempts
        if session is None:
            session = ConversationSession(user_id=sender, db=db)
            db.add(session)
            db.commit()
        session.increment_call_flow(db)
        send_response_using_whatsapp_api(conversation_steps[str(session.call_flow_location)])
        return conversation_steps[str(session.call_flow_location)]
    else:
        if user_msg.lower() in ["יציאה"]:
            # session.set_status(db, False)
            session.session_active = False
            db.commit()
            print("Your session end")
            send_response_using_whatsapp_api("השיחה הסתיימה, על מנת לחדש את השיחה אנא שלח הודעה")
            return "השיחה הסתיימה, על מנת לחדש את השיחה אנא שלח הודעה"
        current_conversation_step = str(session.call_flow_location)
        print(f"Current step is: {current_conversation_step}")
        is_answer_valid, message_in_error = session.validate_and_set_answer(db, current_conversation_step, user_msg,button_selected)
        if is_answer_valid:
            if not button_selected:
                session.increment_call_flow(db)
                next_step_conversation_after_increment = str(session.call_flow_location)
            if current_conversation_step == "2":
                send_response_using_whatsapp_api("שלום " + session.get_conversation_step_json("1") + "!")
                # show buttons for step 4
                subject_groups = session.get_all_client_product_and_save_db_subjects2(db)
                return send_interactive_response(conversation_steps[next_step_conversation_after_increment],
                                                 subject_groups)
            elif current_conversation_step in ["3", "4"]:
                if button_selected:
                    print(f"drop menu: {user_msg}")
                    session.increment_call_flow(db)
                    next_step_conversation_after_increment = str(session.call_flow_location)
                if current_conversation_step == "3":
                    # show buttons for step 4
                    products = session.get_products(db, user_msg)
                    if products:
                        products_2 = list()
                        for s in products:
                            for k, v in s.items():
                                products_2.append(k)
                        return send_interactive_response(conversation_steps[next_step_conversation_after_increment],
                                                         products_2)
                    else:
                        print("product return empty")
                        send_response_using_whatsapp_api(conversation_steps[next_step_conversation_after_increment])
                        return conversation_steps[next_step_conversation_after_increment]
                    # return "Choose product..."
                else:
                    send_response_using_whatsapp_api(conversation_steps[next_step_conversation_after_increment])
                    return conversation_steps[next_step_conversation_after_increment]
            else:
                send_response_using_whatsapp_api(conversation_steps[next_step_conversation_after_increment])
                # regarding last step
                if next_step_conversation_after_increment != str(len(conversation_steps)):
                    return conversation_steps[next_step_conversation_after_increment]
            # Check if conversation reach to last step
            if next_step_conversation_after_increment == str(len(conversation_steps)):  # 7
                new_issue = Issues(conversation_id=session.id,
                                   item_id=session.get_conversation_step_json("4"),
                                   issue_data=session.get_conversation_step_json(str(int(current_conversation_step)))
                                   )
                db.add(new_issue)
                db.commit()
                print(f"Issue successfully created! {new_issue}")
                summary = json.loads(session.convers_step_resp)
                client_id = session.password.split(";")[1]
                data = {"technicianName": f"{summary['5'].replace('972', '0')}-{summary['1']}",
                        "kria": f"{summary['6']}\nהמספר המקורי: {session.user_id}",
                        "clientCode": f"{client_id}"}
                if len(data["technicianName"]) > 20:
                    print("Set technicianName only phone number without name")
                    data = {"technicianName": f"{summary['5']}",
                            "kria": f"{summary['6']}\nהמספר המקורי: {session.user_id}",
                            "clientCode": f"{client_id}"}
                if moses_api.create_kria(data):
                    print(f"Kria successfully created! {data}")
                    new_issue.set_issue_status(db, True)
                else:
                    print(f"Failed to create Kria {data}")
                print("Conversation ends!")
                # session.set_status(db, False)
                session.session_active = False
                db.commit()
                return "Conversation ends!"
            else:
                raise Exception("Unknown step after check for end conversation")
        else:
            print("Try again")
            send_response_using_whatsapp_api(message_in_error)
            return conversation_steps[current_conversation_step]


def send_response_using_whatsapp_api(message, debug=False, _specific_sendr=None):
    """Send a message using the WhatsApp Business API."""
    try:
        print(f"Sending message: '{message}' ")
        url = f"{FACEBOOK_API_URL}/{PHONE_NUMBER_ID_PROVIDER}/messages"

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": f"{sender if _specific_sendr is None else _specific_sendr}",
            "type": "text",
            "text": {
                "preview_url": False,
                "body": f"{message}"
            }
        }

        if debug:
            print(f"Payload '{payload}' ")
            print(f"Headers '{headers}' ")
            print(f"URL '{url}' ")
        response = requests.post(url, json=payload, headers=headers)
        if not response.ok:
            raise Exception(f"Error on sending message, json: {payload}")
        print(f"Message sent successfully to :'{sender if _specific_sendr is None else _specific_sendr}'!")
        return f"Message sent successfully to :'{sender if _specific_sendr is None else _specific_sendr}'!"
    except Exception as EX:
        print(f"Error send whatsapp : '{EX}'")
        raise EX


def send_interactive_response(message, chooses):
    try:
        print(f"Sending interactive message: '{chooses}' ")
        url = f"{FACEBOOK_API_URL}/{PHONE_NUMBER_ID_PROVIDER}/messages"
        buttons = [{
            "type": "reply",
            "reply": {
                "id": i,
                "title": msg
            }} for i, msg in enumerate(chooses)]

        if False:
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": f"{sender}",
                "type": "interactive",
                "interactive": {
                    "type": "button",
                    "body": {
                        "text": f"{message}"
                    },
                    "action": {
                        "buttons": json.dumps(buttons)
                    }
                }
            }
        else:
            if len(chooses) > 10:
                print("More then 10, use only 10 first!!")
                buttons = [{
                    "id": i,
                    "title": msg,
                    "description": "",
                } for i, msg in enumerate(chooses[:10])]
            else:
                buttons = [{
                    "id": i,
                    "title": msg,
                    "description": "",
                } for i, msg in enumerate(chooses)]
            print("Multiple options")
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": f"{sender}",
                "type": "interactive",
                "interactive": {
                    "type": "list",
                    "body": {
                        "text": f"{message}"
                    },
                    "action": {
                        "button": "לחץ לבחירה",
                        "sections": [
                            {
                                "title": "בחר פריט מהרשימה",
                                "rows": json.dumps(buttons)
                            }]
                    }
                }
            }
            # Todo: Fix right to left on body for list
        response = requests.post(url, json=payload, headers=headers, verify=False)
        if not response.ok:
            return f"Failed send message, response: '{response}'"
        print(f"Message sent successfully to :'{sender}'!")
        # return f"Interactive sent successfully to :'{sender}'!"
        return f"{message}\n{chooses}"
    except Exception as EX:
        print(f"Error send whatsapp : '{EX}'")
        raise EX


def check_if_session_exist(db, user_id):
    session = db.query(ConversationSession).filter(ConversationSession.user_id == user_id,
                                                   ConversationSession.session_active == True).all()
    if len(session) > 1:
        print("more then one SESSION exist!")
        print(f"There is more then one active call for {user_id}, returning last one")
        return session[-1]
    if len(session) == 1:
        print("SESSION exist!")
        return session[0]
    return None


def after_working_hours():
    # Get Day Number from weekday
    # Todo: remove False
    return False
    week_num = datetime.today().weekday()

    if week_num > 5:
        print("Today is a Weekend")
        return True
    else:
        # 5 Sat, 6 Sun
        print("Today is a Weekend")

    current_time = datetime.now(pytz.timezone('Israel'))
    if current_time.hour > WORKING_HOURS_START_END[1] or current_time.hour < WORKING_HOURS_START_END[0]:
        print("Now is NOT working hours")
        return True
    else:
        # 5 Sat, 6 Sun
        print("Now is working hours")

    return False


def check_for_afk_sessions(db):
    results = db.query(ConversationSession).filter(ConversationSession.session_active == True).all()
    print(f"Active session found: '{results}'")
    for open_session in results:
        now = datetime.now()
        diff_time = now - open_session.start_data
        seconds_in_day = 24 * 60 * 60
        minutes, second = divmod(diff_time.days * seconds_in_day + diff_time.seconds, 60)
        if minutes > MAX_NOT_RESPONDING_TIMEOUT_MINUETS:
            try:
                print(f"end session phone: '{open_session.user_id}' id {open_session.id}")
                send_response_using_whatsapp_api("השיחה הופסקה עקב חוסר מענה, על מנת להתחיל שיחה חדשה אנא שלח הודעה",
                                                 _specific_sendr=open_session.user_id)
                open_session.session_active = False
                db.commit()
                print("session Delete!")
            except Exception as er:
                print(er)


def schedule_search_for_inactive_sessions():
    print("Search for opening session..")
    db_conn = next(get_db())
    threading.Timer(TIMER_FOR_SEARCH_OPEN_SESSION_SEC, schedule_search_for_inactive_sessions).start()
    check_for_afk_sessions(db_conn)


if __name__ == "__main__":
    print("From main")
    uvicorn.run(app,
                host="0.0.0.0",
                port=int(PORT),
                log_level="info")
