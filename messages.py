import json


def get_instrument_info_msg(instrument_name):
    msg = \
        {
            "jsonrpc": "2.0",
            "method": "public/get_order_book",
            "params": {
                "instrument_name": instrument_name
            }
        }

    return msg


def get_open_orders_msg(instrument_name):
    msg = \
        {
            "jsonrpc": "2.0",
            "method": "private/get_open_orders_by_instrument",
            "params": {
                "instrument_name": instrument_name
            }
        }

    return msg


def get_positions_msg(access_token):
    buy_msg = \
    {
      "jsonrpc" : "2.0",
      "method" : "/private/get_positions",
      "params" : {
        "currency": "BTC",
        "access_token": access_token
      }
    }
    return buy_msg


def get_auth_msg(client_id, client_secret):
    msg = \
        {
            "jsonrpc": "2.0",
            "id": 9929,
            "method": "public/auth",
            "params": {
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret
            }
        }
    return json.dumps(msg)


def subscribe_to_public_channels(request_id, channels):
    msg = {
         "jsonrpc": "2.0",
         "method": "public/subscribe",
         "id": request_id,
         "params": {
             "channels": channels
         }
    }
    return msg


def subscribe_to_private_channels(request_id, access_token, channels):
    msg = {
         "jsonrpc": "2.0",
         "method": "private/subscribe",
         "id": request_id,
         "params": {
             "access_token": access_token,
             "channels": channels
         }
    }
    return msg


