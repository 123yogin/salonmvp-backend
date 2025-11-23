import hmac
import hashlib
import base64
import boto3
from flask import current_app

def get_secret_hash(username):
    """
    Calculates the Secret Hash required for Cognito API calls 
    when the App Client has a Client Secret.
    """
    client_id = current_app.config.get('COGNITO_APP_CLIENT_ID')
    client_secret = current_app.config.get('COGNITO_CLIENT_SECRET')

    if not client_secret:
        return None

    message = username + client_id
    dig = hmac.new(
        str(client_secret).encode('utf-8'), 
        msg=str(message).encode('utf-8'), 
        digestmod=hashlib.sha256
    ).digest()
    
    return base64.b64encode(dig).decode()

def cognito_client():
    """Returns a boto3 client for Cognito Identity Provider"""
    return boto3.client(
        'cognito-idp',
        region_name=current_app.config.get('COGNITO_REGION')
    )

