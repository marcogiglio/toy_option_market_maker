from messages import get_auth_msg
import json

file = open('auth.json')
auth = json.load(file)
dev_client_id = auth['dev_client_id']
dev_client_secret = auth['dev_client_secret']

async def get_access_token(websocket):
    authentication_msg = get_auth_msg(dev_client_id, dev_client_secret)
    await websocket.send(authentication_msg)
    response = await websocket.recv()
    response = json.loads(response)
    access_token = response['result']['access_token']
    refresh_token = response['result']['refresh_token']
    expiry = ''
    return access_token
