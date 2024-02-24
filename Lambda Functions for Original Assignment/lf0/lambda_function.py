import json
import boto3
from datetime import datetime

def lambda_handler(event, context):
    lexClient = boto3.client('lex-runtime')
    lexResponse = lexClient.post_text(
        botName='SuggestRes',
        botAlias='Food',
        userId='id',
        inputText=event['messages'][0]['unstructured']['text']
    )

    response = {
        "statusCode": 200,
        # 'headers': {
        #     'Access-Control-Allow-Origin': 'http://lambdawebsitehw1.s3-website-us-east-1.amazonaws.com',
        #     'Access-Control-Allow-Methods': 'OPTIONS, POST, GET',
        #     'Access-Control-Allow-Headers': 'Content-Type'
        # },
        "messages": [
            {
                "type": "unstructured",
                "unstructured": {
                    "id": 1,
                    "text": lexResponse['message'],
                    'timestamp': datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                    
                }
                
            }
        ]
    }

    return response