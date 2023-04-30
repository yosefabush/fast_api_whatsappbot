import re
import json
from typing import List
from datetime import datetime
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Boolean, Column, Integer, String, Text, DateTime

from Model import moses_api

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=False, index=True)
    password = Column(String(255), unique=False, index=True)
    phone = Column(String(255), unique=True, index=True)

    def __init__(self, db: Session, **kwargs):
        self.db = db
        super().__init__(**kwargs)

    @classmethod
    def log_in_user(self, user, password):
        return self.db.query(self).filter(self.name == user, self.password == password).first()


class Items(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, index=True)


class Issues(Base):
    __tablename__ = "issues"
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(String(255), unique=False, index=True)
    item_id = Column(Text)
    issue_data = Column(String(255), unique=False)
    issue_sent_status = Column(Boolean, default=False)

    def set_issue_status(self, db, status):
        session = db.query(Issues).filter(Issues.id == self.id).first()
        session.issue_sent_status = status
        db.commit()
        # self.session_active = status


class ConversationSession(Base):
    conversation_steps_in_class = {
        "1": "אנא הזן שם משתמש",
        "2": "אנא הזן סיסמא",
        "3": "תודה שפנית אלינו פרטיך נקלטו במערכת,\nבאיזה נושא נוכל להעניק לך שירות?\n(לפתיחת קריאה ללא נושא רשום 'אחר')",
        "4": "אנא בחר קוד מוצר",
        "5": "אם ברצונך לחזור למספר אחר אנא הקש את המספר לחזרה",
        "6": "מה שם פותח הקריאה?",
        "7": "נא רשום בקצרה את תיאור הפנייה",
        "8": """תודה רבה על פנייתך, הקריאה הוכנסה למערכת ותטופל בהקדם האפשרי.
אנא הישאר זמין  📶 📞
כדי לפתוח בשיחה חדשה ניתן לשלוח הודעה נוספת
תודה ולהתראות""",
    }
    MAX_LOGING_ATTEMPTS = 3
    __tablename__ = 'conversation'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(255), unique=False, index=True)
    password = Column(String(255), unique=False, index=True)
    login_attempts = Column(Integer)
    call_flow_location = Column(Integer)
    all_client_products_in_service = Column(LONGTEXT)
    start_data = Column(DateTime, nullable=False, default=datetime.now)
    session_active = Column(Boolean, default=True)
    convers_step_resp = Column(String(1500), unique=False)

    def __init__(self, user_id, db: Session):
        self.user_id = user_id
        self.login_attempts = 0
        self.call_flow_location = 0
        self.all_client_products_in_service = None
        # self.start_data = None
        self.session_active = True
        self.convers_step_resp = json.dumps({"1": "",
                                             "2": "",
                                             "3": "",
                                             "4": "",
                                             "5": "",
                                             "6": "",
                                             "7": ""
                                             })
        # self.db = db

    def increment_call_flow(self, db):
        session = db.query(ConversationSession).filter(ConversationSession.id == self.id).first()
        session.call_flow_location += 1
        db.commit()
        print(f"call flow inc to: '{self.call_flow_location}'")

    def get_conversation_session_id(self):
        return self.user_id

    def get_user_id(self):
        return self.user_id

    def get_call_flow_location(self):
        sees = self.db.query(ConversationSession).filter(ConversationSession.id == self.id).first()
        if sees is None:
            raise Exception(f"Could not find user {self.id}, {self.user_id}")
        return sees.call_flow_location

    # def all_validation(self, db, step, answer):
    #     match step:
    #         case 1:
    #             print(f"Check if user name '{answer}' valid")
    #         case 2:
    #             print(f"Log in with password '{answer}'")
    #             print(
    #                 f"Search for user with user name '{self.get_conversation_step_json('1')}' and password '{answer}'")
    #             # user_db = moses_api.get_product_by_user(self.get_converstion_step('1'), self.password)
    #             user_db = db.query(User).filter(User.name == self.get_conversation_step_json('1'),
    #                                             User.password == answer).first()
    #             if user_db is None:
    #                 print("user not found!")
    #                 return False
    #             print("User found!")
    #             self.password = answer
    #             db.commit()
    #         case 3:
    #             print(f"check if chosen '{answer}' valid")
    #             # choises = {a.name: a.id for a in db.query(Items).all()}
    #             choises = moses_api.get_product_by_user(self.user_id, self.password)
    #             if answer not in choises:
    #                 return False
    #             res = db.query(Items.id).filter(Items.name == answer).first()
    #             if len(res) == 0:
    #                 print(f"Item not exist {answer}")
    #                 return False
    #         case 4:
    #             print(f"Check if product '{answer}' exist")
    #             if answer not in moses_api.get_product_number_by_user(self.user_id, self.password):
    #                 return False
    #         case 5:
    #             print(f"Check if phone number '{answer}' is valid")
    #             if answer != "1":
    #                 # rule = re.compile(r'(^[+0-9]{1,3})*([0-9]{10,11}$)')
    #                 rule = re.compile(r'(^\+?(972|0)(\-)?0?(([23489]{1}\d{7})|[5]{1}\d{8})$)')
    #                 if not rule.search(answer):
    #                     msg = "המספר שהוקש איננו תקין"
    #                     print(msg)
    #                     return False
    #         case 6:
    #             print(f"NO NEED TO VALIDATE ISSUE")
    #     return True

    def validation_switch_step(self, db, case, answer, select_by_button):
        try:
            if case == 1:
                print(f"Check if user name '{answer}' valid")
            elif case == 2:
                print(f"Log in user name '{self.get_conversation_step_json('1')}' password '{answer}'")
                client_data = moses_api.login_whatsapp(self.get_conversation_step_json('1'), answer)
                if client_data is None:
                    return False
                client_name = client_data.get('clientName', None)
                if client_name is None:
                    print(f"No clientName!")
                    self.password = f"{answer};{client_data['UserId']};{None}"
                else:
                    print(f"clientName found! {client_name}")
                    self.password = f"{answer};{client_data['UserId']};{client_data['clientName']}"
                db.commit()
            elif case == 3:
                print(f"check if chosen '{answer}' valid")
                choices = json.loads(self.all_client_products_in_service)
                print(f"subjects {list(choices.keys())}")
                if answer == "אחר":
                    print("found אחר")
                    return True
                if not select_by_button:
                    return False
            elif case == 4:
                print(f"Check if product '{answer}' exist")
                if not select_by_button:
                    return False
                choices = json.loads(self.all_client_products_in_service)
                res = choices.get(self.get_conversation_step_json("3"), None)
                found = False
                for d in res:
                    an = d.get(answer, None)
                    if an is not None:
                        # print(an[0])
                        found = True
                        break
                return found
            elif case == 5:
                print(f"Check if phone number '{answer}' is valid")
                if answer != "חזור למספר זה":
                    rule = re.compile(r'(^\+?(972|0)(\-)?0?(([23489]{1}\d{7})|[5]{1}\d{8})$)')
                    if not rule.search(answer):
                        msg = "המספר שהוקש איננו תקין"
                        print(msg)
                        return False
            elif case == 6:
                print(f"Opening issue name {answer}")
            elif case == 7:
                print(f"NO NEED TO VALIDATE ISSUE")
            else:
                return False
            return True
        except Exception as ex:
            print(f"step {case} {ex}")
            return False

    def validate_and_set_answer(self, db, step, response, is_button_selected):
        step = int(step)
        if self.validation_switch_step(db, step, response, is_button_selected):
            if step == 2:
                client = self.password.split(';')[-1]
                if client != 'None':
                    self.set_conversion_step(step, client, db)
                else:
                    print(f"Save login name")
                    self.set_conversion_step(step, response, db)
            elif step == 3 and response == "אחר":
                self.set_conversion_step(step, "None", db)
                self.set_conversion_step(4, "None", db)
                self.call_flow_location = 4
                db.commit()
            elif step == 4:
                choices = json.loads(self.all_client_products_in_service)
                res = choices.get(self.get_conversation_step_json("3"), None)
                for d in res:
                    an = d.get(response, None)
                    if an is not None:
                        print(an[0])
                        self.set_conversion_step(step, an[0], db)
                        break
            elif step == 5:
                # if response == "1":
                if response == "חזור למספר זה":
                    # user_id is phone number in conversation
                    self.set_conversion_step(step, self.user_id, db)
                else:
                    # new phone number
                    self.set_conversion_step(step, response, db)
            else:
                self.set_conversion_step(step, response, db)
            print(f"session object step {self.get_conversation_step_json(str(step))}")
            result = f"{self.conversation_steps_in_class[str(step)]}: {response}"
            return True, result
        else:
            if self.call_flow_location == 1:
                result = "שם משתמש שגוי אנא נסה שוב"
            elif self.call_flow_location == 2:
                # self.login_attempts += 1
                # hint = f"נסיון {self.login_attempts} מתוך {self.MAX_LOGING_ATTEMPTS}"
                # result = f"שם משתמש או סיסמא שגויים\n אנא נסה שוב ({hint})"
                # # self.call_flow_location = 1
                # db.commit()
                # if self.login_attempts == self.MAX_LOGING_ATTEMPTS:
                #     print("restart session")
                #     # session = db.query(ConversationSession).filter(ConversationSession.id == self.id).first()
                #     self.call_flow_location = 0
                #     self.login_attempts = 0
                #     db.commit()
                #     result = "בשל ריבוי ניסיונות החיבור נכשל, על מנת להמשיך שלח הודעה כדי להתחיל הזדהות מחדש"
                # else:
                #     print(f"login failure number '{self.login_attempts}'")
                result = f"לא ניתן להמשיך את הליך ההזדהות, שם משתמש או סיסמא שגויים.\nהשיחה הסתיימה, על מנת לחדש את השיחה אנא שלח הודעה"
            elif self.call_flow_location in [3, 4]:
                result = "אנא בחר פריטים מהרשימה"
            elif self.call_flow_location == 5:
                result = "מספר הטלפון שהוקש אינו חוקי, אנא נסה שוב"
            else:
                result = f" ערך לא חוקי '{response}' "
            print(f"Not valid response {response} for step {step}")
            return False, result

    def set_status(self, db, status):
        session = db.query(ConversationSession).filter(ConversationSession.id == self.id).first()
        session.session_active = status
        db.commit()

    def get_all_client_product_and_save_db_subjects(self, db):
        choices = moses_api.get_sorted_product_by_user_and_password(self.password.split(";")[1])
        if choices is None:
            raise Exception("get_all_client_product error (check user password and client Id)")
        print(f"Allowed values: '{choices}'")
        self.all_client_products_in_service = json.dumps(choices)
        db.commit()
        print("saved to DB!")
        return list(choices.keys())

    def get_products(self, db, msg):
        choices = json.loads(self.all_client_products_in_service)
        distinct_values = choices.get(msg, None)
        return distinct_values

    def get_all_responses(self):
        return self.convers_step_resp

    def set_conversion_step(self, step, value, db):
        print(f"set_conversion_step {step} value {value} ")
        temp = json.loads(self.convers_step_resp)
        temp[str(step)] = value
        self.convers_step_resp = json.dumps(temp)
        db.commit()

    def get_conversation_step_json(self, step):
        return json.loads(self.convers_step_resp)[step]


# Request Models.
class WebhookRequestData(BaseModel):
    object: str = ""
    entry: List = []
