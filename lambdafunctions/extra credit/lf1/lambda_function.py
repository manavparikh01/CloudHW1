import json
import boto3
import random
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

def lambda_handler(event, context):
    # Initialize SES client
    
    #sqs = boto3.client("sqs")
   # dynamodb = boto3.resource("dynamodb")
    queue_url = "https://sqs.us-east-1.amazonaws.com/533267188080/suggestdiningqueue"

    # Security Credentials and OpenSearch configuration
    region  = "us-east-1"
    access_key  = "AKIAXYKJTRFYPMCPHQAJ"
    secret_key     = "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"
    host = "search-datahw1-ryccisgow2q4bkppx3varihlum.aos.us-east-1.on.aws"
    service = "es"

    #awsauth = AWS4Auth(access_key, secret_key, region, service)
    
    sqs = boto3.client (
                            service_name            = "sqs",
                            aws_access_key_id       = access_key,
                            aws_secret_access_key   = secret_key  ,
                            region_name             = region,
                        )
    auth = ('Assignment1','Assignment1*')   
    
    dynamodb = boto3.client(
    service_name='dynamodb',
    aws_access_key_id=access_key,
    aws_secret_access_key=secret_key,
    region_name=region)


    # Create OpenSearch client
    openSearch = OpenSearch(
        hosts=  [ {'host': host, 'port': 443}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection
    )

    # Receive a message from SQS
    resp = sqs.receive_message(
        QueueUrl=queue_url,
        MaxNumberOfMessages=1,
        VisibilityTimeout=0,
        WaitTimeSeconds=0
    )

    if 'Messages' not in resp:
        return {'statusCode': 200, 'body': 'No messages in the queue'}

    message = resp['Messages'][0]
    receipt_handle = message['ReceiptHandle']
    message_body = json.loads(message['Body'])

    # Extract details from the message body
    cuisine = message_body['Cuisine']
    email = message_body['Email']
    people = message_body['People']
    day = message_body['Date']
    time = message_body['DiningTime']


    # Search OpenSearch for restaurants matching the cuisine
    result = openSearch.search(
        index="restaurants",
        body={"query": 
                    {"match": 
                         {"cuisine_type": cuisine}
                    }
              }
    )
    
    # Extract restaurant IDs from the search result
    restaurant_ids = [hit['_source']['id'] for hit in result['hits']['hits']]
     # Initialize variables
    chosen_restaurant_ids = []
    attempts = 0

    # Keep trying until we have 3 valid restaurant IDs or have attempted a reasonable number of times
    while len(chosen_restaurant_ids) < 3 and attempts < len(restaurant_ids):
        selected_id = random.choice(restaurant_ids)
        attempts += 1

        try:
            response = dynamodb.get_item(
                TableName='yelp_restaurants',
                Key={'id': {'S': selected_id}}
            )
            restaurant_info = response.get('Item', None)
            if restaurant_info:
                chosen_restaurant_ids.append(selected_id)
                # Remove the selected ID from the list to avoid re-selecting it
                restaurant_ids.remove(selected_id)
        except Exception as e:
            print(f"An error occurred: {e}")

    # Construct the email body with restaurant suggestions
    email_body = f"Hello! Here are my {cuisine} restaurant suggestions for {people} people, for {day} at {time}:\n"
    state_dynamo = ""

    for idx, restaurant_id in enumerate(chosen_restaurant_ids):
        response = dynamodb.get_item(
            TableName='yelp_restaurants',
            Key={'id': {'S': restaurant_id}}
        )
        restaurant_info = response['Item']
        state_dynamo += f"{idx + 1}. {restaurant_info['name']['S']}, located at {restaurant_info['address']['S']}. It has {restaurant_info['review_count']['N']} reviews with an average rating of {restaurant_info['rating']['N']}\n"
        email_body += f"{idx + 1}. {restaurant_info['name']['S']}, located at {restaurant_info['address']['S']}. It has {restaurant_info['review_count']['N']} reviews with an average rating of {restaurant_info['rating']['N']}\n"
        
    email_body += "Enjoy your meal!"
    dynamodb_state = boto3.resource('dynamodb', region_name=region, aws_access_key_id=access_key, aws_secret_access_key=secret_key)
    
    ## extra credit part - add email to state_manager table
    table_name = 'state_manager'
    table = dynamodb_state.Table(table_name)
    sample_data = {"email": email, "cuisine_type": cuisine, "email_body": state_dynamo}
    table.put_item(Item=sample_data)
    

    

        
    ses =  boto3.client (
                            service_name            = "ses",
                            aws_access_key_id       = access_key,
                            aws_secret_access_key   = secret_key  ,
                            region_name             = region,
                        )


    # Format the email content
    email_subject = "Restaurant Suggestion"
 

    # Send the email via SES
    ses.send_email(
        Source='mm13575@nyu.edu',
        Destination={'ToAddresses': [email]},  
        Message={
            'Subject': {'Data': email_subject},
            'Body': {'Text': {'Data': email_body}}
        }
    )

    # Delete the message from the SQS queue
    sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt_handle)

    return {'statusCode': 200, 'body': 'Email sent successfully!'}
