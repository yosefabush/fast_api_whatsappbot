import os
import time
import pytz
import pickle
import uvicorn
import requests
import threading
from pathlib import Path
from Model.models import *
from datetime import datetime
from json import JSONDecodeError
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi import Limiter, _rate_limit_exceeded_handler
from requests.structures import CaseInsensitiveDict
from DatabaseConnection import SessionLocal, engine
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status

requests.packages.urllib3.disable_warnings()

PORT = os.getenv("PORT", default=8000)
TOKEN = os.getenv('TOKEN', default=None)
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", default=None)
PHONE_NUMBER_ID_PROVIDER = os.getenv("NUMBER_ID_PROVIDER", default="104091002619024")
FACEBOOK_API_URL = 'https://graph.facebook.com/v16.0'
WHATS_API_URL = 'https://api.whatsapp.com/v3'
TIMER_FOR_SEARCH_OPEN_SESSION_MINUTES = 1
MAX_NOT_RESPONDING_TIMEOUT_MINUETS = 8
TIME_PASS_FROM_LAST_SESSION = 2
MINIMUM_SUSPENDED_TIME_SECONDS = 60
EXCEEDED_REQUEST_REQUEST_LIMIT = 5
if None in [TOKEN, VERIFY_TOKEN]:
    raise Exception(f"Error on env var '{TOKEN, VERIFY_TOKEN}' ")

sender = None
language_support = {"he": "he_IL", "en": "en_US"}

headers = CaseInsensitiveDict()
headers["Accept"] = "application/json"
headers["Authorization"] = f"Bearer {TOKEN}"
session_open = False
conversation = {
    "Greeting": "היי ברוך הבא לבוט של מוזס!\nתודה שפנית אלינו 😊\n"
                "כדי לפתוח קריאת שירות עלינו לבצע הליך זיהוי קצר,"
                " בכל שלב תוכלו לרשום 'יציאה' והמערכת תתחיל את השיחה מחדש"
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

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(debug=False)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Create a new scheduler
scheduler = BackgroundScheduler()

# origins = [
#     "https://wa.mosesnet.net",
#     "https://localhost",
#     f"http://localhost:{PORT}"
# ]
#
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=origins,
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# Create a dictionary to store the request count and timestamp for each user
user_requests = dict()


def save_file_as_pickle(data, filename, path=os.path.join(os.getcwd(), "dict")):
    Path(path).mkdir(parents=True, exist_ok=True)
    file_path = os.path.join(path, str(filename + ".pickle"))
    # save dictionary to pickle file
    with open(file_path, "wb") as file:
        pickle.dump(data, file, pickle.HIGHEST_PROTOCOL)


def load_pickle(filename, path=os.path.join(os.getcwd(), "dict")):
    global user_requests
    file_path = os.path.join(path, str(filename + ".pickle"))
    try:
        # load a pickle file
        with open(file_path, "rb") as file:
            user_requests = pickle.load(file)
        print(f"pickle {user_requests}")
    except:
        print("Error loading load_pickle")
        pass


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    global user_requests
    print("~" * 100)
    print(f"Received request: {request.method} {request.url}")

    async def set_body(req: Request):
        receive_ = await req._receive()

        async def receive():
            return receive_

        request._receive = receive

    start_time = time.time()
    await set_body(request)
    try:
        data = await request.json()
        if data['object'] == "whatsapp_business_account":
            entry = data['entry'][0]
            messaging_events = [msg for msg in entry.get("changes", []) if msg.get("field", None) == "messages"]
            event = messaging_events[0]
            user_id = event['value']['messages'][0]['from']
            # print(user_id)
            if user_id in user_requests:
                # Get the request count and timestamp for the user
                count, timestamp = user_requests[user_id]

                # Calculate the elapsed time since the last request
                elapsed_time = time.time() - timestamp

                # If the elapsed time is greater than 60 seconds, reset the count and timestamp
                if elapsed_time > MINIMUM_SUSPENDED_TIME_SECONDS:
                    count = 0
                    timestamp = time.time()

                # If the user has exceeded the request limit (5 requests), raise an HTTPException
                if count >= EXCEEDED_REQUEST_REQUEST_LIMIT:
                    response = await suspend_session_after_too_meny_request(user_id)
                    return Response(content=response, status_code=status.HTTP_429_TOO_MANY_REQUESTS)

                # Increment the request count and update the dictionary
                count += 1
                user_requests[user_id] = (count, timestamp)
            else:
                # If the user is not in the dictionary, add a new entry with a count of 1 and the current timestamp
                user_requests[user_id] = (1, time.time())
            print(f'********** user_requests {user_requests} **********')
            print("~" * 100)
            response = await call_next(request)
            process_time = time.time() - start_time
            response.headers["X-Process-Time"] = str(process_time)
            return response
        else:
            print("invalid object")
            return Response(content="invalid object (from middleware)")
    except:
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response


@app.on_event("startup")
def startup():
    print("startup DB create_all..")
    Base.metadata.create_all(bind=engine)
    print(f"starting scheduler..")
    # Add your function to the scheduler to run every x minutes
    scheduler.add_job(check_for_afk_sessions, 'interval', minutes=TIMER_FOR_SEARCH_OPEN_SESSION_MINUTES)
    scheduler.start()
    print(f"loading user_requests from file..")
    load_pickle("user_requests")
    # schedule_search_for_inactive_sessions()


@app.on_event("shutdown")
def shutdown():
    print("shutdown DB dispose..")
    engine.dispose()
    print("shutdown scheduler..")
    scheduler.shutdown()
    print("Write active users to file..")
    save_file_as_pickle(user_requests, "user_requests")


# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_for_afk_sessions():
    db_connection = next(get_db())
    results = db_connection.query(ConversationSession).filter(ConversationSession.session_active == True).all()
    print(f"Active sessions: '{len(results)}' (interval: '{TIMER_FOR_SEARCH_OPEN_SESSION_MINUTES}' minutes)")
    for open_session in results:
        now = datetime.now()
        diff = now - open_session.start_data
        min = diff.total_seconds() / 60
        print(f"session opened: '{min}' ago")
        if min < MAX_NOT_RESPONDING_TIMEOUT_MINUETS:
            print(f"session id: '{open_session.id}' remains '{MAX_NOT_RESPONDING_TIMEOUT_MINUETS - min}' minutes")
            return
        try:
            # print(f"end session phone: '{open_session.user_id}' id {open_session.id}")
            open_session.session_active = False
            db_connection.commit()
            db_connection.refresh(open_session)
            send_response_using_whatsapp_api(
                f"השיחה הופסקה עקב חוסר מענה, על מנת להתחיל שיחה חדשה אנא שלח הודעה",
                _specific_sendr=open_session.user_id)
            print("session closed!")
        except Exception as er:
            print(er)
            continue


async def suspend_session_after_too_meny_request(user):
    try:
        print("Suspending session")
        msg = f"השיחה הופסקה עקב שימוש מגונה, על מנת להתחיל שיחה חדשה אנא שלח הודעה"
        db_connection = next(get_db())
        result = db_connection.query(ConversationSession).filter(ConversationSession.user_id == user,
                                                                 ConversationSession.session_active == True).first()
        if result is None:
            msg = f"הנך מושעה אין באפשרותך לשלוח הודעות, אנא המתן מספר דקות"
            send_response_using_whatsapp_api(msg, _specific_sendr=user)
            return msg
        result.session_active = False
        db_connection.commit()
        db_connection.refresh(result)
        send_response_using_whatsapp_api(msg, _specific_sendr=result.user_id)
        print("too meny request!, session closed!")
        return msg
    except Exception as er:
        print(er)


def schedule_search_for_inactive_sessions():
    print(f"Searching for sessions over {MAX_NOT_RESPONDING_TIMEOUT_MINUETS} minutes...")
    threading.Timer(TIMER_FOR_SEARCH_OPEN_SESSION_MINUTES, schedule_search_for_inactive_sessions).start()
    check_for_afk_sessions()


@app.get("/")
@limiter.limit('5/minute')
async def root(request: Request):
    print("root router 1!")
    return {"Hello": "FastAPI"}


@app.get("/user/{user}", status_code=200)
def get_user(user, response: Response, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.name == user).first()
    if db_user:
        return {"Result": f"Found {db_user.name}"}
    # response.status_code = status.HTTP_204_NO_CONTENT
    return {"Result": f"{user} not Found"}


@app.get("/get_all_created_issues/{user}")
def get_conversations(user, db: Session = Depends(get_db)):
    results = list()
    if user.lower() not in ["admin", "servercheck"]:
        raise HTTPException(status_code=400, detail="Only admin can get all created issues")
    created_issues_history = db.query(Issues).filter(Issues.issue_sent_status == True).all()
    for issue in created_issues_history:
        results.append({"ID": issue.conversation_id, "Message": issue.issue_data})
    return JSONResponse(content={"sessions": results})


@app.get("/reset/{user}")
def reset_all_sessions(user, db: Session = Depends(get_db)):
    if user.lower() not in ["admin"]:
        raise HTTPException(status_code=400, detail="Only admin can reset all sessions")
    conversation_history = db.query(ConversationSession).filter(ConversationSession.session_active == True).all()
    for session in conversation_history:
        # session.set_status(db, False)
        session.session_active = False
        db.commit()
    print("All conversation were reset")
    return "All conversation were reset"
    # user = User(db=db, name="Alice", password="password", phone="555-1234")
    # # user_ = User(db, user)
    # existing_user = db.query(User).filter(User.phone == user.phone).first()
    # if existing_user:
    #     raise HTTPException(status_code=400, detail="Phone number already registered")
    # db.add(user)
    # db.commit()
    # db.refresh(user)
    # return f"'{user}' Created"


@app.get("/all_users")
async def get_users(db=Depends(get_db)):
    # result = db.execute(text("SELECT * FROM users"))
    # rows = result.fetchall()
    result = db.query(User).all()
    return {"Results": result}


@app.post("/webhook")
@limiter.limit('100/minute')
async def handle_message_with_request_scheme(request: Request, data: WebhookRequestData, db: Session = Depends(get_db)):
    try:
        # print("handle_message webhook")
        global sender
        message = "ok"
        if data.object == "whatsapp_business_account":
            for entry in data.entry:
                messaging_events = [msg for msg in entry.get("changes", []) if msg.get("field", None) == "messages"]
                # print(f"total events: '{len(messaging_events)}'")
                for event in messaging_events:
                    if event['value'].get('messages', None) is None:
                        print(f"event is not a messages")
                        return Response(content="Event is not a messages")
                    type = event['value']['messages'][0].get('type', None)
                    if type is None:
                        print("None type")
                        return Response(content="None type found")
                        # return Response(content="None type found", status_code=status.HTTP_400_BAD_REQUEST)
                    if type == "text":
                        # print("text")
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
                        # res = f"Json: '{event['value']['messages'][0]}'"
                        # print(res)
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
    """
    Check if last session of the user was at least x minutes old
    return True if yes, False otherwise
    """
    # return False
    print("Checking for timeout to prevent abuse of issues creation..")
    session = db.query(ConversationSession).filter(ConversationSession.user_id == sender,
                                                   ConversationSession.session_active == False).order_by(
        ConversationSession.start_data.desc()).first()
    if session is None:
        return False
    now = datetime.now()
    diff = now - session.start_data
    minutes = diff.total_seconds() / 60
    if TIME_PASS_FROM_LAST_SESSION > minutes:
        return True
    return False


def process_bot_response(db, user_msg: str, button_selected=False) -> str:
    if after_working_hours():
        print("after working hours")
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
    next_step_after_increment = ""
    session = check_if_session_exist(db, sender)
    if session is None or session.call_flow_location == 0:
        # Todo: should enable this in the future
        # if check_for_timeout(db, sender):
        #     print(f"Please wait '{TIME_PASS_FROM_LAST_SESSION}' min")
        #     send_response_using_whatsapp_api(
        #         f"""אנא המתן אנא המתן '{TIME_PASS_FROM_LAST_SESSION}' דקות לפני הפנייה הבאה""", sender)
        #     return f"""אנא המתן אנא המתן '{TIME_PASS_FROM_LAST_SESSION}' דקות לפני הפנייה הבאה"""
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
        is_answer_valid, message_in_error = session.validate_and_set_answer(db, current_conversation_step, user_msg,
                                                                            button_selected)
        if is_answer_valid:
            if not button_selected:
                session.increment_call_flow(db)
                next_step_after_increment = str(session.call_flow_location)
            if current_conversation_step == "2":
                # send_response_using_whatsapp_api(f"שלום '{session.get_conversation_step_json('2')}' !")
                subject_groups = session.get_all_client_product_and_save_db_subjects(db)
                message = f"שלום '{session.get_conversation_step_json('2')}' !\n{conversation_steps[next_step_after_increment]}"
                # show buttons for step 3
                return send_interactive_response(message, subject_groups)
            elif current_conversation_step in ["3", "4", "5"]:
                if button_selected:
                    print(f"selected button: '{user_msg}'")
                    session.increment_call_flow(db)
                    next_step_after_increment = str(session.call_flow_location)
                if current_conversation_step == "3":
                    # show buttons for step 4
                    products = session.get_products(db, user_msg)
                    if products:
                        products_2 = list()
                        for s in products:
                            for k, v in s.items():
                                products_2.append(k)
                        return send_interactive_response(conversation_steps[next_step_after_increment],
                                                         products_2)
                    else:
                        print("product return empty")
                        return send_interactive_response(conversation_steps[next_step_after_increment],
                                                         ["חזור למספר שלי"])
                        # send_response_using_whatsapp_api(conversation_steps[next_step_after_increment])
                        # return conversation_steps[next_step_after_increment]
                    # return "Choose product..."
                elif current_conversation_step == "4":
                    return send_interactive_response(conversation_steps[next_step_after_increment],
                                                     ["חזור למספר שלי"])
                else:
                    send_response_using_whatsapp_api(conversation_steps[next_step_after_increment])
                    return conversation_steps[next_step_after_increment]
            else:
                send_response_using_whatsapp_api(conversation_steps[next_step_after_increment])
                # check if is last step
                if next_step_after_increment != str(len(conversation_steps)):
                    return conversation_steps[next_step_after_increment]
            # Check if conversation reach to last step
            if next_step_after_increment == str(len(conversation_steps)):  # 8
                summary = json.loads(session.convers_step_resp)
                client_id = session.password.split(";")[1]
                _phone_number_with_0 = summary['5'].replace('972', '0')
                kria_header = f"מספר מדבקה: {summary['4']}" if summary[
                    '4'].isdigit() else f"שים לב למוצר אין מדבקה: {summary['4']}"
                keria_body = summary['7']
                kria_footer = f"המספר ממנו נפתחה הקריאה: {session.user_id.replace('972', '0')}"
                data = {"technicianName": f"{_phone_number_with_0} {summary['6']}",
                        # product name and phone
                        "kria": f"{keria_body}\n{kria_header}\n{kria_footer}",
                        # issue details and orig phone number
                        "clientCode": f"{client_id}"}  # client code
                if len(data["technicianName"]) > 20:
                    print("technicianName is Over 20 character! Set technicianName only phone number without name")
                    data["technicianName"] = f"{summary['5']}"
                new_issue = Issues(conversation_id=session.id,
                                   item_id=session.get_conversation_step_json("4"),
                                   issue_data=data["kria"]
                                   )
                db.add(new_issue)
                # db.commit()
                print(f"Issue successfully created! {new_issue}")
                if moses_api.create_kria(data):
                    print(f"Kria successfully created! {data}")
                    # new_issue.set_issue_status(db, True)
                    new_issue.issue_sent_status = True
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
            print("Invalid response try again")
            if current_conversation_step == "2":
                session.session_active = False
                db.commit()
                print("Your session end")
                send_response_using_whatsapp_api(message_in_error)
                return message_in_error
            send_response_using_whatsapp_api(message_in_error)
            return conversation_steps[current_conversation_step]


def trigger_bot_response_after_wrong_auth():
    """Trigger bot response after wrong auth."""
    print(f"Trigger bot response after wrong auth")
    json_data = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "8856996819413533",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "16505553333",
                                "phone_number_id": "27681414235104944"
                            },
                            "contacts": [
                                {
                                    "profile": {
                                        "name": "Kerry Fisher"
                                    },
                                    "wa_id": "16315551234"
                                }
                            ],
                            "messages": [
                                {
                                    "from": f"{sender}",
                                    "id": "wamid.ABGGFlCGg0cvAgo-sJQh43L5Pe4W",
                                    "timestamp": "1603059201",
                                    "text": {
                                        "body": "retry login"
                                    },
                                    "type": "text"
                                }
                            ]
                        },
                        "field": "messages"
                    }
                ]
            }
        ]
    }
    headers = {'Content-type': 'application/json', 'Accept': 'application/json'}
    res = requests.post(f'http://localhost:{PORT}/webhook', json=json.dumps(json_data), headers=headers)
    print(res)


def send_response_using_whatsapp_api(message, debug=False, _specific_sendr=None):
    """Send a message using the WhatsApp Business API."""
    # Todo: handle exceptions, after sending message failure, call get incremented should not be incremented
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


def send_interactive_response(message, chooses, debug=False):
    try:
        print(f"Sending interactive message: '{chooses}' ")
        url = f"{FACEBOOK_API_URL}/{PHONE_NUMBER_ID_PROVIDER}/messages"
        buttons = [{
            "type": "reply",
            "reply": {
                "id": i,
                "title": msg
            }} for i, msg in enumerate(chooses)]

        if len(chooses) == 1:
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
        if debug:
            print(f"Payload '{payload}' ")
            print(f"Headers '{headers}' ")
            print(f"URL '{url}' ")
        response = requests.post(url, json=payload, headers=headers, verify=False)
        if not response.ok:
            return f"Failed send interactive message, response: '{response}'"
        print(f"Interactive message sent successfully to :'{sender}'!")
        # return f"Interactive sent successfully to :'{sender}'!"
        return f"{message}\n{chooses}"
    except Exception as EX:
        print(f"Error send interactive whatsapp : '{EX}'")
        raise EX


def check_if_session_exist(db, user_id):
    session = db.query(ConversationSession).filter(ConversationSession.user_id == user_id,
                                                   ConversationSession.session_active == True).all()
    if len(session) > 1:
        print(f"There is more then one active call for {user_id}, returning last one")
        return session[-1]
    if len(session) == 1:
        # print("SESSION exist!")
        return session[0]
    return None


def after_working_hours():
    # Get Day Number from weekday
    # weekday: Sunday is 6
    #          Monday is 0
    #          tuesday  is 1
    #          wednesday is 2
    #          thursday is 3
    #          friday is 4
    #          saturday is 5
    # Todo: remove False
    # return False
    week_num = datetime.today().weekday()

    if week_num in [4, 5]:
        # print("Today is a Weekend")
        return True
    else:
        pass
        # print(f"Today is weekday {week_num}")

    current_time = datetime.now(pytz.timezone('Israel'))
    if current_time.hour > WORKING_HOURS_START_END[1] or current_time.hour < WORKING_HOURS_START_END[0]:
        # print("Now is NOT working hours")
        return True
    else:
        pass
        # print("Now is working hours")

    return False


if __name__ == "__main__":
    print("From main")
    uvicorn.run(app,
                host="0.0.0.0",
                port=int(PORT),
                log_level="info")
