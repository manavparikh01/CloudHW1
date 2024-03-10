import json
import re
from datetime import datetime
import boto3
import logging

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# Initialize the SQS client
sqs = boto3.client('sqs')


cities = ['manhattan', 'brooklyn', 'queens', 'staten island', 'bronx']
cuisine_list = ['indian', 'thai', 'mediterranean', 'chinese', 'italian','japanese']

def lambda_handler(event, context):
    region = "us-east-1"
    access_key = "access_key"
    secret_key = "secret_key"
    dynamodb_state = boto3.resource('dynamodb', region_name=region, aws_access_key_id=access_key, aws_secret_access_key=secret_key)

    table_name = 'state_manager'
    logger.debug('event={}'.format(event))
    slots = event.get('currentIntent', {}).get('slots', {})

    location = try_ex(lambda: slots['Location'])
    cuisine = try_ex(lambda: slots['Cuisine'])
    people = try_ex(lambda: slots['People'])
    dining_time = try_ex(lambda: slots['DiningTime'])
    email = try_ex(lambda: slots['Email'])
    date = try_ex(lambda: slots['Date'])

    intent_name = event.get('currentIntent', {}).get('name')
    #session_attributes = event.get('sessionAttributes', {})
    session_attributes = event.get("sessionAttributes") or {}
    confirmation_status = event.get('currentIntent', {}).get('confirmationStatus', 'None')

    if intent_name == "GreetingIntent":
        return build_response("Hey, what can I help you with?")
        
    elif intent_name == "ThankYouIntent":
        return build_response("Welcome. Hope I was able to assist you!")
        
    elif intent_name == "DiningSuggestionsIntent":
        if 'email' in session_attributes :
            if confirmation_status == 'Confirmed':
            # User confirmed to use previous recommendations
                send_email_with_previous_recommendation(session_attributes['email'])
                return build_response("Your previous dining recommendations have been sent to your email.")
            else:
                return handle_dining_suggestions_intent(location, cuisine, people, dining_time, email, date, slots, session_attributes)
                
  
        elif email and isvalid_email(email):
                # Check if email exists in DynamoDB for  previous recommendation
                table = dynamodb_state.Table(table_name)
                response = table.get_item(Key={'email': email})
                if 'Item' in response:
                    return ask_for_previous_recommendation(email,session_attributes, slots)
                else:
                    # No previous recommendation, proceed with normal flow
                    return handle_dining_suggestions_intent(location, cuisine, people, dining_time, email, date, slots, session_attributes)
        else:
                # If email hasn't been asked yet, ask for it
            return elicit_slot(session_attributes, "DiningSuggestionsIntent", slots, 'Email', "Enter your email to start.")
        

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
    
    send_to_sqs(location, cuisine, people, dining_time, email, date)

    # Construct the confirmation response to the user
    confirmation_response = "Thank you. Your dining suggestions request has been received. "
    if cuisine and people and date:
        confirmation_response += f"You will be notified over email once we have the list of {cuisine} restaurant suggestions for {people} people on {date}."

    # Return the confirmation response
    return build_response(confirmation_response)


def ask_for_previous_recommendation(email, session_attributes, slots):
    # Save the email in session attributes to use after user's response
    session_attributes['email'] = email

    # Prompt the user to ask if they want to use the previous recommendation
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'ConfirmIntent',
            'intentName': 'DiningSuggestionsIntent',
            'slots': slots,
            'message': {'contentType': 'PlainText', 'content': 'Would you like to use your previous dining suggestions?'}
        }
    }

def send_email_with_previous_recommendation(email):
    table_name = 'state_manager'
    region  = "us-east-1"
    access_key  = "acess_key"
    secret_key     = "secret_key"
    # Initialize DynamoDB
    dynamodb_state = boto3.resource(
        'dynamodb',
        region_name=region,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key
    )
    table = dynamodb_state.Table(table_name)

    # Retrieve the previous recommendation from DynamoDB
    response = table.get_item(Key={'email': email})
    if 'Item' in response:
        item = response['Item']
        cuisine_type = item.get('cuisine_type', 'No cuisine type found')
        email_body = item.get('email_body', 'No recommendation found')
    else:
        email_body = 'No previous recommendation found for this email.'
        cuisine_type = 'N/A'

    # Initialize SES
    ses = boto3.client(
        'ses',
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region
    )

    # Format the email content
    email_subject = f"Your Previous {cuisine_type} Restaurant Recommendation"

    # Send the email via SES
    ses.send_email(
        Source= 'mm13575@nyu.edu',
        Destination= {'ToAddresses': [email]},
        Message={
            'Subject': {'Data': email_subject},
            'Body': {'Text': {'Data': email_body}}
        }
    )

# Helper functions for validation
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
    r = {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'ElicitSlot',
            'intentName': intent_name,
            'slots': slots,
            'slotToElicit': slot_to_elicit,
            'message': {'contentType': 'PlainText', 'content': message_content}
        }
    }
    logger.debug(r)
    return r

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
        'dialogAction': {
            'type': 'Close',  
            'fulfillmentState': 'Fulfilled', 
            'message': {
                'contentType': 'PlainText',
                'content': message_content
            },
        },
        'sessionAttributes': {} 
    }


    
def send_to_sqs(location, cuisine, people, dining_time, email, date):
    
    # Construct the message body with the relevant data

    regionName  = "us-east-1"
    access_key  = "access_key"
    api_key     = "acess_key"
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
        # Send the message to the SQS queue
        response = sqs.send_message(
            QueueUrl = sqs_url,
            DelaySeconds = 10,
            MessageBody=message_body
        )
        print(f"Message sent to SQS with ID: {response['MessageId']}")
    except Exception as e:
        # Log the error and re-raise it
        print(f"Error sending message to SQS: {str(e)}")
        raise
    
