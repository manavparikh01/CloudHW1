import json

def lambda_handler(event, context):
    # TODO implement
    inner_message = {
        'type': 'unstructured',
        'unstructured': {
            'id': 'temp',
            'text': 'I’m still under development. Please come back later.',
            'timestamp': '12/03/2024'
        }
    }

    response = {
        'statusCode': 200,
        'messages': [inner_message]
    }

    return response