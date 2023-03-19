import os
import uvicorn
import requests
from typing import List
from Model.models import *
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
    "Greeting": "ברוך הבא לבוט של מוזס!"
}
non_working_hours_msg = """שלום, השירות פעיל בימים א'-ה' בשעות 08:00- 17:30. 
ניתן לפתוח קריאה באתר דרך הקישור הבא 
 026430010.co.il
ונחזור אליכם בשעות הפעילות

בברכה,
מוזס מחשבים."""
# Define a list of predefined conversation steps
conversation_steps = ConversationSession.conversation_steps_in_class

# conversation_history = list()
app = FastAPI(debug=True)


# Request Models.
class WebhookRequestData(BaseModel):
    object: str = ""
    entry: List = []


@app.on_event("startup")
def startup():
    print("startup DB create_all")
    Base.metadata.create_all(bind=engine)


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


@app.post("/webhook_old")
async def handle_message(request: Request, db: Session = Depends(get_db)):
    try:
        print("handle_message")
        global sender
        message = None
        payload_as_json = None
        payload_as_json = await request.json()
        payload_as_json = payload_as_json['entry'][0]['changes'][0]['value']['messages'][0]
        sender = payload_as_json["from"]
        text = payload_as_json['text']['body']
        if after_working_hours():
            print("after_working_hours")
            send_response_using_whatsapp_api(non_working_hours_msg)
            return Response(content=non_working_hours_msg)
            # return non_working_hours_msg, 200
        message = process_bot_response(db, text)
        return Response(content=message)
    except JSONDecodeError:
        message = "Received data is not a valid JSON"
    return Response(content=message)


@app.post("/webhook")
async def handle_message_with_request_scheme(data: WebhookRequestData, db: Session = Depends(get_db)):
    try:
        print("handle_message_with_request_scheme")
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
                    else:
                        print(f"Type {type} is not valid")
                        message = f"Json '{event['value']['messages'][0]}'"
                    return Response(content=message)
        else:
            print(data.object)
        return Response(content=message)
    except JSONDecodeError:
        message = "Received data is not a valid JSON"
    except Exception as ex:
        print(f"Exception: '{ex}'")
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
    log = ""
    if user_msg in ["אדמין"]:
        created_issues_history = db.query(Issues).filter(Issues.issue_sent_status == True).all()
        for issue in created_issues_history:
            log += f"Conversation ID: {issue.conversation_id} Sent message: {issue.issue_data}\n"
        send_response_using_whatsapp_api(log)
        return log
    if user_msg.lower() in ["reset"]:
        conversation_history = db.query(ConversationSession).filter(ConversationSession.session_active == True).all()
        for session in conversation_history:
            session.set_status(db, False)
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
        if session is None:
            session = ConversationSession(user_id=sender, db=db)
            db.add(session)
            db.commit()
        session.increment_call_flow(db)
        send_response_using_whatsapp_api(conversation_steps[str(session.call_flow_location)])
        return conversation["Greeting"]
    else:
        current_conversation_step = str(session.call_flow_location)
        print(f"Current step is: {current_conversation_step}")
        is_answer_valid, message_in_error = session.validate_and_set_answer(db, current_conversation_step, user_msg)
        if is_answer_valid:
            if not button_selected:
                session.increment_call_flow(db)
                next_step_conversation_after_increment = str(session.call_flow_location)
            if current_conversation_step == "2":
                send_response_using_whatsapp_api("שלום " + session.get_conversation_step_json("1") + "!")
                # send_response_using_whatsapp_api(conversation_steps[next_step_conversation_after_increment])
                # regarding step 3
                choices = session.get_chooses(db)
                send_interactive_response(conversation_steps[next_step_conversation_after_increment], choices)
                return "Choose..."
            elif current_conversation_step == "3":
                if button_selected:
                    print(f"drop menu: {user_msg}")
                    session.increment_call_flow(db)
                    next_step_conversation_after_increment = str(session.call_flow_location)
                    send_response_using_whatsapp_api(conversation_steps[next_step_conversation_after_increment])
            else:
                send_response_using_whatsapp_api(conversation_steps[next_step_conversation_after_increment])
            # Check if conversation reach to last step
            if next_step_conversation_after_increment == str(len(conversation_steps)):  # 7
                new_issue = Issues(conversation_id=session.id,
                                   item_id=session.get_conversation_step_json("3"),
                                   issue_data=session.get_conversation_step_json(str(int(current_conversation_step)))
                                   )
                db.add(new_issue)
                db.commit()
                summary = json.loads(session.convers_step_resp)
                data = {"technicianName": f"{summary['5']}", "kria": f"{summary['6']}", "clientCode": f"{18047}"}
                # data = {"technicianName": f"{summary['5']}", "kria": f"{new_issue.issue_data}", "clientCode": f"{18047}"}
                if moses_api.create_kria(data):
                    print(f"Issue successfully created! {data}")
                    new_issue.set_issue_status(db, True)
                else:
                    print(f"Failed to create Kria")
                print("Conversation ends!")
                session.set_status(db, False)
                return "Conversation ends!"
            else:
                return conversation_steps[current_conversation_step]
        else:
            print("Try again")
            send_response_using_whatsapp_api(message_in_error)
            return conversation_steps[current_conversation_step]


def send_response_using_whatsapp_api(message, debug=True):
    """Send a message using the WhatsApp Business API."""
    try:
        print(f"Sending message: '{message}' ")
        url = f"{FACEBOOK_API_URL}/{PHONE_NUMBER_ID_PROVIDER}/messages"

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": f"{sender}",
            "type": "text",
            "text": {
                "preview_url": False,
                "body": f"{message}"
            }
        }

        pay = {
            "messaging_product": "whatsapp",
            "to": f"{sender}",
            "type": "template",
            "template": {
                "name": "hello_world",
                "language": {
                    "code": "en_US"
                }
            }
        }
        if debug:
            print(f"Payload '{payload}' ")
            print(f"Headers '{headers}' ")
            print(f"URL '{url}' ")
        response = requests.post(url, json=payload, headers=headers, verify=False)
        if not response.ok:
            return f"Failed send message, response: '{response}'"
        print(f"Message sent successfully to :'{sender}'!")
        return f"Message sent successfully to :'{sender}'!"
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
        response = requests.post(url, json=payload, headers=headers, verify=False)
        if not response.ok:
            return f"Failed send message, response: '{response}'"
        print(f"Message sent successfully to :'{sender}'!")
        return f"Interactive sent successfully to :'{sender}'!"
    except Exception as EX:
        print(f"Error send whatsapp : '{EX}'")
        raise EX


def check_if_session_exist(db, user_id):
    # print("Loading active conversation...")
    # conversation_history = db.query(ConversationSession).filter(ConversationSession.session_active == True).all()
    # print(f"Check check_if_session_exist '{user_id}'")
    # # search for active session with user_id
    # for session in conversation_history:
    #     if session.user_id == user_id:
    #         print("SESSION exist!")
    #         return session
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
    return False


if __name__ == "__main__":
    print("From main")
    # uvicorn.run(app,
    #             host="0.0.0.0",
    #             port=int(PORT),
    #             ssl_keyfile=r"C:\Certificate\key.pem",
    #             ssl_certfile=r"C:\Certificate\cert.pem",
    #             log_level="info")

    uvicorn.run(app,
                host="0.0.0.0",
                port=int(PORT),
                log_level="info")
