# cognito_auth.py
import logging
import boto3
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class CognitoAuth:
    def __init__(self, user_pool_id, client_id, region):
        self.client = boto3.client('cognito-idp', region_name=region)
        self.user_pool_id = user_pool_id
        self.client_id = client_id

    def sign_in(self, username, password):
        try:
            response = self.client.initiate_auth(
                ClientId=self.client_id,
                AuthFlow='USER_PASSWORD_AUTH',
                AuthParameters={
                    'USERNAME': username,
                    'PASSWORD': password
                }
            )
            return True, response
        except ClientError as e:
            logging.error("Cognito sign in error: %s", e.response['Error']['Message'])
            return False, None

    def sign_up(self, username, password):
        try:
            response = self.client.sign_up(
                ClientId=self.client_id,
                Username=username,
                Password=password,
                UserAttributes=[{'Name': 'email', 'Value': username}]
            )
            return True, response
        except ClientError as e:
            logging.error("Cognito sign up error: %s", e.response['Error']['Message'])
            return False, None
