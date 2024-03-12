from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_core.runnables import RunnableParallel, RunnablePassthrough, RunnableBranch
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain.globals import set_debug
from langchain.agents import tool
from langchain import hub

from sqlalchemy.orm import Session
from db import SessionLocal, Appointment
import datetime

set_debug(True)

model = ChatOpenAI(temperature=0)

class Appointment_create(BaseModel):
    overlap: bool = Field(description="Does the new appointment overlap with existing appointments")
    date: str = Field(description="Date of the appointment in YYYY-MM-DD")
    start: str = Field(description="Start time of the appointment in HH:MM")
    end: str = Field(description="End of the appointment in HH:MM")
    description: str = Field(description="Description of the appointment")
    
class Appointment_adjust(BaseModel):
    overlap: bool = Field(description="Does the new appointment time overlap with existing appointments")
    id: int = Field(description="Id of the appointment you want to adjust.")
    date: str = Field(description="Date of the appointment in YYYY-MM-DD")
    start: str = Field(description="Start time of the appointment in HH:MM")
    end: str = Field(description="End of the appointment in HH:MM")
    description: str = Field(description="Description of the appointment")


create_appointment_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """Today's Date is: {today_date}\nYou're a helpful assistant.\
            \n\nGiven the existing appointments: {tool_response}.\nTurn the following user input into a json request to create an appointment on the user's calendar.\
            \n\nYOUR RESPONSE MUST BE A JSON OBJECT THAT FOLLOWS THIS FORMAT:\n{format_instructions}.""",
        ),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
    ]
)

adjust_appointment_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """Today's Date is: {today_date}\nYou're a helpful assistant.\
            \n\nGiven the existing appointments: {tool_response}.\nTurn the following user input into a json request to adjust an appointment on the user's calendar.\
            \n\nYOUR RESPONSE MUST BE A JSON OBJECT THAT FOLLOWS THIS FORMAT:\n{format_instructions}.""",
        ),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
    ]
)

prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """Today's Date is: {today_date}\n\nGiven the user input, classify it as either being for `create_appointment`, `modify_appointmment`, `return_appointment`, or `other`. You're a helpful assistant.
            \nDo not respond with more than one word.""",
        ),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
    ]
)

final_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """Today's Date is: {today_date}\n\nYou're a helpful and reliable assistant.\n\nIf provided, use the response from a calendar tool to provide a response to the human input: {tool_response}.""",
        ),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
    ]
)

    
@tool
def create_appointment(overlap: bool, date: str, start: str, end: str, description: str) -> str:
    """Creates an appointment in the user's calendar on the specified date, starting and ending at the specified start and end respectively. The input date should always be of this format: %B %d, %Y"""
    try:
        db = SessionLocal()
        if overlap==True:
            return "Unable to create appointment as the appointment overlaps with an existing appointment"

        new_appointment = Appointment(date=date, start=start, end=end, description=description)
        db.add(new_appointment)
        db.commit()
        return f"Appointment Created at {date} {start}"
    except Exception as e:
        print(e)
        return "Unable to create an appointment"
    finally:
        db.close()

@tool
def adjust_appointment(overlap: bool, id: int, date: str, start: str, end: str, description: str) -> str:
    """Given an appointment id, it adjusts the appointment to the given date, and start and end. The input date should always be of this format: %B %d, %Y"""
    try:
        db = SessionLocal()
        appointment = db.query(Appointment).filter(Appointment.id==id).first()
        if appointment is None:
            return "Appointment not found"
        if overlap==True:
            return "Unable to adjust appointment as new date and time overlaps with an existing appointment"
        appointment.date = date
        appointment.start = start
        appointment.end = end
        appointment.description = description
        db.commit()
        return f"Appointment has been modified"
    except Exception as e:
        print(e)
        return "Unable to modify appointment"

@tool
def return_all_appointment() -> list:
    """Return all appointments in the user's calendar."""
    try:
        db = SessionLocal()
        appointments = db.query(Appointment).all()
        appointments_list = [{"id": appointment.id, "date": appointment.id, "start": appointment.start, "end": appointment.end, "description": appointment.description} for appointment in appointments]
        if appointments_list == []:
            return ["You do not have any appointments"]
        return appointments_list
    except:
        return ["Unable to retrieve appointments"]
    finally:
        db.close()


return_appointment_chain = RunnableParallel({}) | return_all_appointment

create_parser = JsonOutputParser(pydantic_object=Appointment_create)
create_appointment_chain = (
    {"tool_response": return_appointment_chain, "input": lambda x: x["input"], "chat_history":lambda x: x["chat_history"]}
    | RunnableParallel(tool_response=lambda x: x['tool_response'], input=lambda x: x["input"], chat_history=lambda x: x["chat_history"], today_date=lambda x: datetime.date.today().strftime("%B %d, %Y"))
    | create_appointment_prompt.partial(format_instructions=create_parser.get_format_instructions()) 
    | model
    | create_parser
    | create_appointment
)

adjust_parser = JsonOutputParser(pydantic_object=Appointment_adjust)
adjust_appointment_chain = (
    {"tool_response": return_appointment_chain, "input": lambda x: x["input"], "chat_history":lambda x: x["chat_history"]}
    | RunnableParallel(tool_response=lambda x: x['tool_response'], input=lambda x: x["input"], chat_history=lambda x: x["chat_history"], today_date=lambda x: datetime.date.today().strftime("%B %d, %Y"))
    | adjust_appointment_prompt.partial(format_instructions=adjust_parser.get_format_instructions()) 
    | model
    | adjust_parser
    | adjust_appointment
)

branch1 = RunnableBranch(
    (lambda x: "create_appointment" in x["topic"].lower(), {"tool_response": create_appointment_chain, "input": lambda x: x["input"], "chat_history": lambda x: x["chat_history"]}),
    (lambda x: "modify_appointment" in x["topic"].lower(), {"tool_response": adjust_appointment_chain, "input": lambda x: x["input"], "chat_history": lambda x: x["chat_history"]}),
    (lambda x: "return_appointment" in x["topic"].lower(), {"tool_response": return_appointment_chain, "input": lambda x: x["input"], "chat_history": lambda x: x["chat_history"]}),
    # (lambda x: "delete_appointment" in x["topic"].lower(), create_appointment_chain),
    RunnablePassthrough.assign(tool_response=lambda x: "None"),
)

final_chain = final_prompt.partial(today_date=datetime.date.today().strftime("%B %d, %Y")) | model | StrOutputParser()

chain = prompt.partial(today_date=datetime.date.today().strftime("%B %d, %Y")) | model | StrOutputParser()

full_chain = {"topic": chain, "input": lambda x: x["input"], "chat_history": lambda x: x["chat_history"]} | branch1 | final_chain
