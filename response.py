from logger import global_logger
import json


class Response:

    def __init__(self, data):
        self.__dict__ = json.loads(data)


async def send_and_receive(ws, msg):
    try:
        await ws.send(msg)
        resp = await ws.recv()
        response = Response(resp)
        if hasattr(response, 'error'):
            error = response.error
            # If error is too many request, wait before retry
            global_logger.error(error)
            return None
        elif hasattr(response, 'result'):
            return response.result
        elif hasattr(response, 'subscription'):
            return response

    except json.JSONDecodeError as err:
        global_logger.error(err)


async def receive(ws):
    try:
        resp = await ws.recv()
        response = Response(resp)
        if hasattr(response, 'error'):
            error = response.error
            # If error is too many request, wait before retry
            global_logger.error(error)
            return None
        elif hasattr(response, 'result'):
            return response.result
        elif hasattr(response, 'params'):
            return response.params

    except json.JSONDecodeError as err:
        global_logger.error(err)
