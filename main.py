import websockets
import asyncio
from logger import global_logger
import json
from messages import get_positions_msg, get_instrument_info_msg, subscribe_to_public_channels,\
    subscribe_to_private_channels
from authentication import get_access_token
from datetime import datetime as dt


class Response:

    def __init__(self, data):
        self.__dict__ = json.loads(data)

    def __str__(self):
        return_str = ''
        for (key, value) in self.__dict__.items():
            return_str += '\n{} : {}'.format(key, value)
        return return_str


async def send(request_id, messages, msg, ws):
    msg['id'] = request_id
    messages[str(request_id)] = msg
    await ws.send(json.dumps(msg))
    return messages


async def main():
    messages = dict()
    open_orders = dict()
    positions_dict = dict()
    books = dict()
    underlying_price = dict()
    trades = []
    realized_volatility = None
    start = dt.now().timestamp()

    async with websockets.connect('wss://test.deribit.com/ws/api/v2', max_queue=1000) as websocket:
        access_token = await get_access_token(websocket)
        pending_order_msg_queue = []
        option_contracts = []
        msg = {
            "method": "public/get_instruments",
            "params": {
                "currency": "BTC",
                "kind": "option",
                "expired": False
            },
            "jsonrpc": "2.0",
            "id": 1
        }

        await websocket.send(json.dumps(msg))
        response = json.loads(await websocket.recv())

        for option in response['result']:
            if option["instrument_name"].startswith('BTC-26MAR21') and option["instrument_name"].endswith('-C'):
                strike = option["instrument_name"][12:]
                strike = int(strike[:-2])
                if strike > 40000:
                    option_contracts.append(option["instrument_name"])

        # Subscribe to channels
        public_channels = []
        private_channels = []
        request_id = 1

        for instrument_name in option_contracts:

            public_channels.append('book.' + instrument_name + '.none.1.100ms')
            private_channels.append('user.changes.' + instrument_name + '.raw')
            msg = get_instrument_info_msg(instrument_name)
            messages = await send(request_id, messages, msg, websocket)
            request_id += 1
        private_channels.append('user.changes.BTC-26MAR21.raw')

        # Portfolio
        msg = get_positions_msg(access_token)
        messages = await send(request_id, messages, msg, websocket)
        request_id += 1

        # Subscribe Private Channels
        msg = subscribe_to_private_channels(request_id, access_token, private_channels)
        messages = await send(request_id, messages, msg, websocket)
        request_id += 1

        # Subscribe Public Channels
        msg = subscribe_to_public_channels(request_id, public_channels)
        messages = await send(request_id, messages, msg, websocket)
        request_id += 1

        # Subscribe to Volatility Index
        msg = subscribe_to_public_channels(request_id, ['deribit_volatility_index.btc_usd'])
        messages = await send(request_id, messages, msg, websocket)
        request_id += 1

        # subscribe to price feed of underlying
        msg = subscribe_to_public_channels(request_id, ['ticker.BTC-26MAR21.100ms'])
        messages = await send(request_id, messages, msg, websocket)
        request_id += 1

        while websocket.open:
            async for message in websocket:
                response = Response(message)

                # Recover message using the request_id, so that you see the method originating the request
                if hasattr(response, 'error'):
                    global_logger.error('{}'.format(response.error))
                    if response.error['code'] == 10028:
                        await asyncio.sleep(1)
                    elif response.error['code'] == 10003:
                        # Order overlap, pass
                        pass
                    elif response.error['code'] == 10009:
                        # Not enough funds, send messages to Telegram
                        if hasattr(response, 'id'):
                            msg = messages[str(response.id)]
                            global_logger.error('Request that generated the error: {}'.format(msg))
                        raise Exception
                if hasattr(response, 'id'):
                    msg = messages[str(response.id)]
                    del messages[str(response.id)]

                    if msg['method'] == '/private/get_positions':
                        positions = response.result
                        for position in positions:
                            instrument_name = position['instrument_name']
                            positions_dict[instrument_name] = position
                    elif msg['method'] == 'private/get_open_orders_by_instrument':
                        orders = response.result
                        for order in orders:
                            order_id = order['order_id']
                            # Replace with changed orders
                            open_orders[order_id] = order
                        global_logger.info('Open orders method'.format(open_orders))
                    elif msg['method'] == 'public/get_order_book':
                        instrument_info = response.result

                        if instrument_info['mark_iv'] < 160 and not open_orders.items():
                            buy_price = instrument_info['mark_price']*0.9
                            sell_price = instrument_info['mark_price']*1.1

                            if instrument_info['asks'] and instrument_info['bids']:
                                best_asks_price = instrument_info['asks'][0][0]
                                best_bids_price = instrument_info['bids'][0][0]
                                sell_price = min(best_asks_price, sell_price)
                                buy_price = max(best_bids_price, buy_price)

                            buy_msg = {
                                "jsonrpc": "2.0",
                                "method": "private/buy",
                                "params": {
                                    "instrument_name": instrument_info['instrument_name'],
                                    "amount": 0.1,
                                    "price": buy_price,
                                    "type": 'limit',
                                    "access_token": access_token
                                }
                            }

                            sell_msg = {
                                "jsonrpc": "2.0",
                                "method": "private/sell",
                                "params": {
                                    "instrument_name": instrument_info['instrument_name'],
                                    "amount": 0.1,
                                    "price": sell_price,
                                    "type": 'limit',
                                    "access_token": access_token
                                }
                            }

                            pending_order_msg_queue.append(buy_msg)
                            pending_order_msg_queue.append(sell_msg)
                    elif msg['method'] in ['private/buy', 'private/sell']:

                        # Filled?
                        if response.result['trades']:
                            global_logger.debug('Response to msg {}'.format(response.result))
                        # msg = get_positions_msg(access_token)
                        # messages = await send(request_id, messages, msg, websocket)
                        # request_id += 1

                if hasattr(response, 'params'):
                    if response.params['channel'] == 'deribit_volatility_index.btc_usd':
                        realized_volatility = response.params['data']['volatility']
                        global_logger.debug('Volatility: {}'.format(response.params['data']['volatility']))
                    if response.params['channel'].startswith('ticker.'):
                        instrument_name = response.params['data']['instrument_name']
                        underlying_price[instrument_name] = response.params['data']['mark_price']
                        global_logger.debug('Mark Price of Instrument {}: {}'.format(instrument_name, response.params['data']['mark_price']))
                    if response.params['channel'] in public_channels:
                        data = response.params['data']
                        global_logger.debug('Book data: {}'.format(data))
                        instrument_name = data['instrument_name']
                        books[instrument_name] = data
                    if response.params['channel'] in private_channels:
                        global_logger.debug('User changes: {}'.format(response.params['data']))

                        orders_changes = response.params['data']['orders']
                        trades_changes = response.params['data']['trades']
                        positions_changes = response.params['data']['positions']

                        for trade in trades_changes:
                            trades.append(trade)
                            global_logger.warning('{} : {} : {} : {}'.format(trade['instrument_name'], trade['direction'], trade['amount'], trade['price']))

                        for order in orders_changes:
                            order_id = order['order_id']
                            # Replace with changed orders
                            open_orders[order_id] = order

                        for position in positions_changes:
                            instrument_name = position['instrument_name']
                            if position['size'] != 0:
                                positions_dict[instrument_name] = position

asyncio.get_event_loop().run_until_complete(main())


