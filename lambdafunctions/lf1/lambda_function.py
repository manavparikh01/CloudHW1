import json
import re
from datetime import datetime
import boto3

# Initialize the SQS client
sqs = boto3.client('sqs')


cities = ['manhattan', 'brooklyn', 'queens', 'staten island', 'bronx']
cuisine_list = ['indian', 'thai', 'mediterranean', 'chinese', 'italian','japanese']

def lambda_handler(event, context):
    slots = event['currentIntent']['slots']

 
    location = try_ex(lambda: slots['Location'])
    cuisine = try_ex(lambda: slots['Cuisine'])
    people = try_ex(lambda: slots['People'])
    dining_time = try_ex(lambda: slots['DiningTime'])
    email = try_ex(lambda: slots['Email'])
    date = try_ex(lambda: slots['Date'])

    intent_name = event['currentIntent']['name']
    if intent_name == "GreetingIntent":
        return build_response("Hey, what can I help you with?")
        
    elif intent_name == "ThankYouIntent":
        return build_response("Welcome. Hope I was able to assist you!")
        
    elif intent_name == "DiningSuggestionsIntent":
        return handle_dining_suggestions_intent(location, cuisine, people, dining_time, email, date, slots, event['sessionAttributes'])
        
    elif intent_name == "fallback": 
        return build_response("I'm sorry, I didn't understand that. Can you please rephrase your question or request?")


def handle_dining_suggestions_intent(location, cuisine, people, dining_time, email, date, slots, session_attributes):
    if location is None or (location.lower() not in cities):
        return elicit_slot(session_attributes, "DiningSuggestionsIntent", slots, 'Location', "What city or city area are you looking to dine in?" if location is None else "Please choose from the following cities: Manhattan, Brooklyn, Bronx, Queens, and Staten Island.")

    if cuisine is None or (cuisine.lower() not in cuisine_list):
        return elicit_slot(session_attributes, "DiningSuggestionsIntent", slots, 'Cuisine', "What cuisine would you like to try?" if cuisine is None else "Please choose from the following cuisines: Indian, Thai, Mediterranean, Chinese, Japanese or Italian.")

    if people is None or not isvalid_people(people):
        return elicit_slot(session_attributes, "DiningSuggestionsIntent", slots, 'People', "Ok, how many people are in your party?" if people is None else "Please enter a number of people between 1 and 20.")
    
    if date is None or not isvalid_date(date):
        return elicit_slot(session_attributes, "DiningSuggestionsIntent", slots, 'Date', "For what date would you like the suggestions? (YYYY-MM-DD) " if date is None else "Please enter a valid date ")

    if dining_time is None or not isvalid_time(dining_time):
        return elicit_slot(session_attributes, "DiningSuggestionsIntent", slots, 'DiningTime', "What time would you like your reservation to be at? (HH:MM)" if dining_time is None else "Please enter a valid time in the format HH:MM.")
    
    if email is None or not isvalid_email(email):
        return elicit_slot(session_attributes, "DiningSuggestionsIntent", slots, 'Email', "Great. Lastly, I need your email so I can send you my suggestions." if email is None else "Please enter a valid email address.")
    
    send_to_sqs(location, cuisine, people, dining_time, email, date)

    confirmation_response =confirmation_response = f"Thank you. Your dining suggestions request has been received. You will be notified over email once we have the list of {cuisine} restaurant suggestions for {people} people on {date}."
    return build_response(confirmation_response)


def isvalid_people(people):
    try:
        num_people = int(people)
        return 1 <= num_people <= 20
    except ValueError:
        return False

def isvalid_time(time_str):
    try:
        datetime.strptime(time_str, '%H:%M')
        return True
    except ValueError:
        return False

def isvalid_date(date_str):
    try:
        input_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        current_date = datetime.now().date()
        return input_date >= current_date
    except ValueError:
        return False

def isvalid_email(email):
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(pattern, email) 


def try_ex(func):
    try:
        return func()
    except KeyError:
        return None

def elicit_slot(session_attributes, intent_name, slots, slot_to_elicit, message_content):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'ElicitSlot',
            'intentName': intent_name,
            'slots': slots,
            'slotToElicit': slot_to_elicit,
            'message': {'contentType': 'PlainText', 'content': message_content}
        }
    }

def delegate(session_attributes, slots):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'Delegate',
            'slots': slots
        }
    }
def build_response(message_content):
    return {
        "dialogAction": {
            "type": "Close",
            "fulfillmentState": "Fulfilled",
            "message": {
                "contentType": "PlainText",
                "content": message_content
            }
        }
    }

    
def send_to_sqs(location, cuisine, people, dining_time, email, date):
    

    regionName  = "us-east-1"
    access_key  = "access_key"
    api_key     = "api_key"
    sqs_url = "https://sqs.us-east-1.amazonaws.com/533267188080/suggestdiningqueue"

    sqs = boto3.client (
                            service_name            = "sqs",
                            aws_access_key_id       = access_key,
                            aws_secret_access_key   = api_key,
                            region_name             = regionName,
                        )
    print("Message being sent to the SQS Queue...")

    message_body = json.dumps({
        'Location': location,
        'Cuisine': cuisine,
        'People': people,
        'DiningTime': dining_time,
        'Email': email,
        'Date': date
    })

    try:
        response = sqs.send_message(
            QueueUrl = sqs_url,
            DelaySeconds = 10,
            MessageBody=message_body
        )
        print(f"Message sent to SQS with ID: {response['MessageId']}")
    except Exception as e:
        print(f"Error sending message to SQS: {str(e)}")
        raise
    
    