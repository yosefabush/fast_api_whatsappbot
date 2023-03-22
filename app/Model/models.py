import re
import json
import datetime
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Boolean, Column, Integer, String, TIMESTAMP

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
    item_id = Column(Integer)
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
        "3": "תודה שפנית אלינו, פרטיך נקלטו במערכת, באיזה נושא נוכל להעניק לך שירות?",
        "4": "אנא הזן קוד מוצר",
        "5": "על מנת לחזור למספר ממנו שלחת את ההודעה הקש 1 אחרת את הקש את המספר הרצוי ",
        "6": "נא רשום בקצרה את תיאור הפנייה",
        "7": "פנייתך התקבלה, נציג טלפוני יחזור אליך בהקדם.",
    }
    MAX_LOGING_ATTEMPTS = 3
    __tablename__ = 'conversation'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(255), unique=False, index=True)
    password = Column(String(255), unique=False, index=True)
    login_attempts = Column(Integer)
    call_flow_location = Column(Integer)
    all_client_products_in_service = Column(String(2000), unique=False)
    start_data = Column(TIMESTAMP(timezone=False), nullable=False, default=datetime.datetime.now())
    # start_data = Column('timestamp', TIMESTAMP(timezone=False), nullable=False, default=datetime.datetime.now())
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
                                             "6": ""
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

    def validation_switch_step(self, db, case, answer):
        try:
            if case == 1:
                print(f"Check if user name '{answer}' valid")
                # user_db = db.query(User).filter(User.name == answer).first()
                # if user_db is None:
                #     print("user name not exist")
                #     return False
                # self.set_convertsion_step(case, answer)
            elif case == 2:
                print(f"Log in with password '{answer}'")
                print(f"Search for user with user name '{self.get_conversation_step_json('1')}' and password '{answer}'")
                # user_db = moses_api.get_product_by_user(self.get_converstion_step('1'), self.password)
                # user_db = db.query(User).filter(User.name == self.get_conversation_step_json('1'),
                #                                 User.password == answer).first()
                client_id = moses_api.login_whatsapp(self.get_conversation_step_json('1'), answer)
                if client_id is None:
                    return False
                # if user_db is None:
                #     print("user not found!")
                #     return False
                # print("User found!")
                self.password = f"{answer};{client_id}"
                db.commit()
            elif case == 3:
                print(f"check if chosen '{answer}' valid")
                # choises = {a.name: a.id for a in db.query(Items).all()}
                # choises = moses_api.get_subjects_by_user_and_password(self.password.split(";")[1])
                # choises = self.get_options_subjects(db)
                # group = list(dict.fromkeys([name["ProductSherotName"].split("-")[0].strip() for name in choises["table"]]))
                # if answer not in group:
                #     return False
                choices = json.loads(self.all_client_products_in_service)
                print(f"subjects {list(choices.keys())}")
                # res = [r for r in choises if answer == r["NumComp"]]
                # distinct_values = dict()
                # for row in choices:
                #     clean_name = row['ProductSherotName'].split("-")[0].strip()
                #     if clean_name not in distinct_values.keys():
                #         distinct_values[clean_name] = [row['NumComp']]
                #         print("new")
                #     else:
                #         distinct_values[clean_name].append(row['NumComp'])
                #         print("else")
                # res = False if answer not in distinct_values.keys() else True
                # if not res:
                #     return False
                # db.commit()
                # res = db.query(Items.id).filter(Items.name == answer).first()
                # if len(res) == 0:
                #     print(f"Item not exist {answer}")
                #     return False
            elif case == 4:
                print(f"Check if product '{answer}' exist")
                choices = json.loads(self.all_client_products_in_service)
                print(f"Products {list(choices.values())}")
                # products = moses_api.get_product_number_by_user(self.user_id, self.password)
                # products = self.get_products(db)
                # if answer not in list(products.values()):
                #     return False
            elif case == 5:
                print(f"Check if phone number '{answer}' is valid")
                if answer != "1":
                    # rule = re.compile(r'(^[+0-9]{1,3})*([0-9]{10,11}$)')
                    rule = re.compile(r'(^\+?(972|0)(\-)?0?(([23489]{1}\d{7})|[5]{1}\d{8})$)')
                    if not rule.search(answer):
                        msg = "המספר שהוקש איננו תקין"
                        print(msg)
                        return False
            elif case == 6:
                print(f"NO NEED TO VALIDATE ISSUE")
            else:
                return False
            return True
        except Exception as ex:
            print(f"step {case} {ex}")
            return False

    def validate_and_set_answer(self, db, step, response):
        step = int(step)
        if self.validation_switch_step(db, step, response):
            # if step == 4:
            #     item_id = db.query(Items.id).filter(Items.name == response).first()
            #     response = item_id[0]
            #     self.set_conversion_step(step, response, db)
            #
            if step == 5:
                if response == "1":
                    # user_id is phone number in conversation
                    self.set_conversion_step(step, self.user_id, db)
                else:
                    self.set_conversion_step(step, response, db)
            else:
                self.set_conversion_step(step, response, db)
            print(f"session object step {self.get_conversation_step_json(str(step))}")
            result = f"{self.conversation_steps_in_class[str(step)]}: {response}"
            return True, result
        else:
            if self.call_flow_location in [2]:
                self.login_attempts += 1
                hint = f"נסיון {self.login_attempts} מתוך {self.MAX_LOGING_ATTEMPTS}"
                result = f"סיסמא שגויה אנא נסה שוב ({hint})"
                db.commit()
                if self.login_attempts == self.MAX_LOGING_ATTEMPTS:
                    print("restart session")
                    # session = db.query(ConversationSession).filter(ConversationSession.id == self.id).first()
                    self.call_flow_location = 0
                    self.login_attempts = 0
                    db.commit()
                    result = "בשל ריבוי ניסיונות החיבור נכשל, על מנת להמשיך שלח הודעה כדי להתחיל הזדהות מחדש"
                else:
                    print(f"login failure number '{self.login_attempts}'")
            elif self.call_flow_location == 1:
                result = "שם משתמש שגוי אנא נסה שוב"
            elif self.call_flow_location == 5:
                result = "מספר הטלפון שהוקש אינו חוקי, אנא נסה שוב"
            else:
                result = f" ערך לא חוקי '{response}' "
            print(f"Not valid response {response} for {self.conversation_steps_in_class[str(step)]}")
            return False, result

    def set_status(self, db, status):
        session = db.query(ConversationSession).filter(ConversationSession.id == self.id).first()
        session.session_active = status
        db.commit()

    def get_options_subjects(self, db):
        # [a.name for a in db.query(Items.name).all()]
        # choices = {a.name: a.id for a in db.query(Items).all()} list(choices.keys())
        choices = moses_api.get_subjects_by_user_and_password(self.password.split(";")[1])
        if choices is None:
            raise Exception("No options found")
        print(f"Allowed values: '{choices}'")
        self.all_client_products_in_service = json.dumps(choices)
        db.commit()
        print("saved to DB!")
        # distinct_values = {row['NumComp']:row['ProductSherotName'].split("-")[0].strip() for row in choices}
        distinct_values = dict()
        for row in choices:
            clean_name = row['ProductSherotName'].split("-")[0].strip()
            if clean_name not in distinct_values.keys():
                distinct_values[clean_name] = [row['NumComp']]
                print("new")
            else:
                distinct_values[clean_name].append(row['NumComp'])
                print("else")
        return list(distinct_values.keys())

    def get_all_client_product_and_save_db_subjects2(self, db):
        choices = moses_api.get_sorted_product_by_user_and_password(self.password.split(";")[1])
        if choices is None:
            raise Exception("No options found")
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


class UserSchema(BaseModel):
    id: int
    name: str
    password: str
    phone: str

    class Config:
        orm_model = True

# class ItemsSchema(BaseModel):
#     id: int
#     name: str
#
#     class Config:
#         orm_model = True
#
#
# class IssuesSchema(BaseModel):
#     id: int
#     user_id: int
#     item_id: int
#     status: bool
#
#     class Config:
#         orm_model = True
#
#
# class ConversationSessionSchema(BaseModel):
#     user_id = int
#     password = str
#     call_flow_location = int
#     issue_to_be_created = str
#     start_data = datetime
#     session_active = bool
#     convers_step_resp = str
#
#     class Config:
#         orm_model = True
