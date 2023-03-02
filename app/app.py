import os
import uvicorn
import requests
from Model.models import *
from json import JSONDecodeError
from sqlalchemy.orm import Session
from requests.structures import CaseInsensitiveDict
from DatabaseConnection import SessionLocal, engine
from fastapi import Depends, FastAPI, HTTPException, Request, Response

requests.packages.urllib3.disable_warnings()

PORT = os.getenv("PORT", default=5000)
TOKEN = os.getenv('TOKEN', default=None)
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", default=None)
PHONE_NUMBER_ID_PROVIDER = os.getenv("NUMBER_ID_PROVIDER", default="104091002619024")
FACEBOOK_API_URL = 'https://graph.facebook.com/v16.0'
WHATS_API_URL = 'https://api.whatsapp.com/v3'
TIMEOUT_FOR_OPEN_SESSION_MINUTES = 1
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

# Define a list of predefined conversation steps
conversation_steps = ConversationSession.conversation_steps_in_class

conversation_history = list()
app = FastAPI(debug=True)


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
    print("root router!")
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
async def handle_message(request: Request, db: Session = Depends(get_db)):
    try:
        if after_working_hourse():
            return """שלום, השירות פעיל בימים א'-ה' בשעות 08:00- 17:30. 
ניתן לפתוח קריאה באתר דרך הקישור הבא 
 026430010.co.il
ונחזור אליכם בשעות הפעילות

בברכה,
מוזס מחשבים.""", 200
        global sender
        payload_as_json = await request.json()
        payload_as_json = payload_as_json['entry'][0]['changes'][0]['value']['messages'][0]
        sender = payload_as_json["from"]
        text = payload_as_json['text']['body']
        message = process_bot_response(db, text)
        return message, 200
    except JSONDecodeError:
        payload_as_json = None
        message = "Received data is not a valid JSON"
    return {"message": message, "received_data_as_json": payload_as_json}


def process_bot_response(db, user_msg: str) -> str:
    log = ""
    global conversation_history
    # conversation_history = db.query(ConversationSession).all()
    print("Loading active conversation...")
    conversation_history = db.query(ConversationSession).filter(ConversationSession.session_active == True).all()
    if user_msg in ["אדמין"]:
        for s in conversation_history:
            if not s.session_active:
                log += f"ID: {s.user_id} Sent message: {s.issue_to_be_created}\n"
        send_response_using_whatsapp_api(log)
        return log
    session = check_if_session_exist(sender)
    if session is None:
        print(f"Hi {sender} You are new!:")
        steps_message = ""
        for key, value in conversation_steps.items():
            steps_message += f"{value} - {key}\n"

        send_response_using_whatsapp_api(conversation["Greeting"])
        print(f"{steps_message}")
        session = ConversationSession(user_id=sender, db=db)
        db.add(session)
        db.commit()
        send_response_using_whatsapp_api(conversation_steps[str(session.call_flow_location)])
        session.increment_call_flow(db)
        return conversation["Greeting"]
    else:
        current_conversation_step = str(session.call_flow_location)
        if current_conversation_step == "8":
            print("Session already end, set end status")
            session.set_status(db, False)
            return "Session already end, set end status"
        print(f"Current step is: {current_conversation_step}")
        is_answer_valid, message_in_error = session.validate_and_set_answer(db, current_conversation_step, user_msg)
        if is_answer_valid:
            if current_conversation_step == "2":
                send_response_using_whatsapp_api("שלום " + session.get_converstion_step("1") + "!")
            if current_conversation_step == "3":
                # choices = ["ב", "א"]
                choices = session.get_chossies(db)
                send_response_using_whatsapp_api(f"{conversation_steps[current_conversation_step]}\n{choices}\n")
            else:
                send_response_using_whatsapp_api(conversation_steps[current_conversation_step])
            session.increment_call_flow(db)
            next_step_conversation_after_increment = str(session.call_flow_location)
            # Check if conversation reach to last step
            if next_step_conversation_after_increment == str(len(conversation_steps) + 1):  # 7
                new_issue = Issues(user_id=session.id, item_id=session.get_converstion_step("3"),
                                   issue_data=session.get_converstion_step(str(int(current_conversation_step) - 1)))
                db.add(new_issue)
                db.commit()
                summary = json.loads(session.convers_step_resp)
                data = {"technicianName": f"{summary['1']}", "kria": f"{summary['6']}", "clientCode": f"{18047}",
                        "id": f"{448}", "password": f"{summary['2']}"}
                if moses_api.create_issue(new_issue):
                    print(f"Issue successfully created! {data}")
                    new_issue.set_issue_status(db, True)
                print("Conversation ends!")
                session.set_status(db, False)
                # print(session.get_all_responses())
                return "Conversation ends!"
            else:
                return conversation_steps[current_conversation_step]
        else:
            print("Try again")
            send_response_using_whatsapp_api(message_in_error)
            fixed_step = str(int(current_conversation_step) - 1)
            if fixed_step == "3":
                # choices = ["ב", "א"]
                choices = session.get_chossies(db)
                return send_response_using_whatsapp_api(f"{conversation_steps[fixed_step]}\n{choices}\n")
            else:
                return send_response_using_whatsapp_api(conversation_steps[fixed_step])


def send_response_using_whatsapp_api(message, phone_number=PHONE_NUMBER_ID_PROVIDER, debug=True):
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


def check_if_session_exist(user_id):
    print(f"Check check_if_session_exist '{user_id}'")
    # search for active session with user_id
    for session in conversation_history:
        if session.user_id == user_id:
            print("SESSION exist!")
            return session
    return None


def after_working_hourse():
    return False


if __name__ == "__main__":
    print("From main")
    uvicorn.run("app:app", host="0.0.0.0", port=os.getenv("PORT", default=5000), log_level="info")
    # uvicorn.run(app, host="0.0.0.0")
    # uvicorn.run(app, host="127.0.0.1", port=int(PORT))
