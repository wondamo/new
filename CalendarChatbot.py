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
import datetime

model = ChatOpenAI(temperature=0)

class Appointment(BaseModel):
    overlap: bool = Field(description="Does the appointment overlap with existing appointments")
    date: str = Field(description="Date of the appointment")
    start: str = Field(description="Start time of the appointment")
    end: str = Field(description="End of the appointment")
    description: str = Field(description="Description of the appointment")
    
class Appointment_adjust(BaseModel):
    overlap: bool = Field(description="Does the appointment overlap with existing appointments")
    appointment_id: int = Field(description="Id of the appointment you want to adjust.")
    date: str = Field(description="Date of the appointment")
    start: str = Field(description="Start time of the appointment")
    end: str = Field(description="End of the appointment")
    description: str = Field(description="Description of the appointment")


create_appointment_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """Today's Date is: {today_date}\nYou're a helpful assistant.\
            \n\nGiven the existing appointments: {tool_response}.\nTurn the following user input into a json request to create an appointment on the user's calendar.\
            \n\nThe request should be in this format:\n{format_instructions}.\n\nYOUR RESPONSE MUST BE A JSON OBJECT""",
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
            \n\nThe request should be in this format:\n{format_instructions}.\n\nYOUR RESPONSE MUST BE A JSON OBJECT""",
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

appointments = [
    {1: {'date_time': 'March 10, 2024, 9:00 AM - 10:00 AM', 'description': 'Project Brainstorm'}},
    {2: {'date_time': 'March 17, 2024, 11:00 AM - 12:00 PM', 'description': 'Dentist Appointment'}},
    {3: {'date_time': 'April 03, 2024, 1:30 PM - 2:30 PM', 'description': 'Lunch with Sarah'}},
    {4: {'date_time': 'March 28, 2024, 3:00 PM - 4:30 PM', 'description': 'Weekly Team Status Meeting'}},
    {5: {'date_time': 'April 12, 2024, 6:00 PM - 7:00 PM', 'description': 'Yoga Class'}},
    {6: {'date_time': 'March 31, 2024, 7:30 PM - 8:30 PM', 'description': 'Book Club Discussion'}},
    {7: {'date_time': 'May 07, 2024, 9:00 PM - 10:00 PM', 'description': 'Experiment with new recipe'}},
    {8: {'date_time': 'May 11, 2024, 10:30 PM', 'description': 'Call Mom!'}},
    {9: {'date_time': 'April 21, 2024, All Day Event', 'description': "Ben's Birthday"}}
]
    
@tool
def create_appointment(overlap: bool, date: str, start: str, end: str, description: str) -> str:
    """Creates an appointment in the user's calendar on the specified date, starting and ending at the specified start and end respectively. The input date should always be of this format: %B %d, %Y"""
    try:
        if overlap==True:
            return "Unable to create appointment as the appointment overlaps with an existing appointment"
        id = len(appointments) + 1
        appointments.append({id: {"date_time": f"{date}, {start} - {end}", "description": description}})
        return f"Appointment Created at {date} {start}"
    except Exception as e:
        return "Unable to create an appointment"

@tool
def adjust_appointment(overlap: bool, appointment_id: int, date: str, start: str, end: str, description: str) -> str:
    """Given an appointment id, it adjusts the appointment to the given date, and start and end. The input date should always be of this format: %B %d, %Y"""
    try:
        if overlap==True:
            return "Unable to adjust appointment as new date and time overlaps with an existing appointment"
        for i in appointments:
            if i.get(appointment_id, False):
                i[appointment_id] = {"date_time": f"{date}, {start} - {end}", "description": description}
                return f"Appointment has been modified"
        return "Appointment not found"
    except Exception as e:
        print(e)
        return "Unable to modify appointment"

@tool
def return_all_appointment() -> list:
    """Return all appointments in the user's calendar."""
    try:
        return appointments
    except:
        return ["Unable to retrieve appointments"]


return_appointment_chain = RunnableParallel({}) | return_all_appointment

create_parshttps://github.com/wondamo/new.giter = JsonOutputParser(pydantic_object=Appointment)
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