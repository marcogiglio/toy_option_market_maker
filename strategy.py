from copy import deepcopy
from optionprice import Option
import numpy as np
from datetime import datetime as dt
from logger import global_logger


def edit_order_msg(access_token, order_id, amount, price):
    msg = \
    {
      "jsonrpc": "2.0",
      "method": "private/edit",
      "params": {
        "access_token": access_token,
        "order_id": order_id,
        "amount": amount,
        "price": price
      }
    }

    return msg


# Turn on and off delta hedging
def produce_strategy(positions_dict, access_token, instrument_info, open_orders, dynamic_hedging=False):

    # mimic top option
    # check my open orders
    pending_order_msg_queue = []

    # Make Dynamic Hedging Optional
    # Focus on accumulating bid - ask spread 

    if open_orders:
        # compare my orders with best bid and best ask
        ins_n = instrument_info['instrument_name']
        sell_order = next(filter(lambda o: o['direction'] == 'sell' and o['instrument_name'] == ins_n, open_orders.values()), None)
        buy_order = next(filter(lambda o: o['direction'] == 'buy' and o['instrument_name'] == ins_n, open_orders.values()), None)

        # 2) do not place orders on instruments with zero bids or zero asks
        # Fix logic
        if sell_order:
            # Lonely order
            if instrument_info['asks'][0][0] == sell_order['price'] and \
               instrument_info['asks'][0][1] == sell_order['amount']:
                price = sell_order['price'] + 0.0005
                edit_msg = edit_order_msg(access_token,
                               sell_order['order_id'],
                               sell_order['amount'],
                               price)
                pending_order_msg_queue.append(edit_msg)

            if instrument_info['asks'][0] != sell_order['price']:
                pending_order_msg_queue.append(edit_order_msg(access_token,
                                                              sell_order['order_id'],
                                                              sell_order['amount'],
                                                              instrument_info['best_ask_price']))
        # Fix logic
        if buy_order:
            if instrument_info['bids'][0][0] == buy_order['price'] and \
               instrument_info['bids'][0][1] == buy_order['amount']:
                price = buy_order['price'] - 0.0005
                edit_msg = edit_order_msg(access_token,
                               buy_order['order_id'],
                               buy_order['amount'],
                               price)
                pending_order_msg_queue.append(edit_msg)

            if instrument_info['bids'][0] != buy_order['price']:
                pending_order_msg_queue.append(edit_order_msg(access_token,
                                                           buy_order['order_id'],
                                                           buy_order['amount'],
                                                           instrument_info['best_bid_price']))
        #
    else:
        # No open orders, create new orders and place on new orders queue

        buy_msg = {
            "jsonrpc": "2.0",
            "method": "private/buy",
            "params": {
                "instrument_name": instrument_info['instrument_name'],
                "amount": 0.1,
                "price": instrument_info['best_bid_price'],
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
                "price": instrument_info['best_ask_price'],
                "type": 'limit',
                "access_token": access_token
            }
        }
        pending_order_msg_queue.append(buy_msg)
        pending_order_msg_queue.append(sell_msg)

    if dynamic_hedging:
        # Delta Hedging (Static?)
        # get portfolio delta
        # When prices changes, the delta changes due to gamma.

        # Remove pending_edits with no changes with respect to open orders
        iterator_copy = deepcopy(pending_order_msg_queue)
        for new_order in iterator_copy:
            # Remove pending_orders_with_no_change
            try:
                order_id = new_order['params']['order_id']
                old_open_order = open_orders[order_id]
                if old_open_order['amount'] == new_order['params']['amount'] and old_open_order['price'] == new_order['params']['price']:
                    pending_order_msg_queue.remove(new_order)
            except KeyError:
                pass

        underlying_price = instrument_info['underlying_price']
        for (i, order) in open_orders.items():
            if instrument_info['underlying_index'] == order['instrument_name']:
                return pending_order_msg_queue

        for (i, position) in positions_dict.items():
            print('Position delta', position['delta'], position['instrument_name'], position['size'], position['direction'])
        total_delta = sum([position['delta'] for (i, position) in positions_dict.items()])
        if total_delta > 0.05:
            # compute hedge required
            position_size = round(total_delta*underlying_price)
            position_size -= position_size % 10

            sell_msg = {
                "jsonrpc": "2.0",
                "method": "private/sell",
                "params": {
                    "instrument_name": instrument_info['underlying_index'],
                    "amount": position_size,
                    "type": 'market',
                    "access_token": access_token
                }
            }
            pending_order_msg_queue.append(sell_msg)
        elif total_delta < -0.05:
            position_size = round(-total_delta*underlying_price)
            position_size -= position_size % 10

            buy_msg = {
                "jsonrpc": "2.0",
                "method": "private/buy",
                "params": {
                    "instrument_name": instrument_info['underlying_index'],
                    "amount": position_size,
                    "type": 'market',
                    "access_token": access_token
                }
            }
            pending_order_msg_queue.append(buy_msg)

    return pending_order_msg_queue


def open_strategy(positions_dict, access_token, underlying_price, realized_volatility):
    pending_order_msg_queue = []
    return pending_order_msg_queue


# If I get a position in one direction, shift bid-ask spread by one tick
def mimic_strategy(positions_dict, access_token, books, mark_prices, open_orders, underlying_price):
    tick = 0.0005
    pending_order_msg_queue = []
    delta = 0
    for (instrument_name, books_data) in books.items():
        try:
            position = positions_dict[instrument_name]
        # It should be one element array
            if position['size'] != 0:
                # I am long a call, so I need to reduce the ask
                if position['direction'] == 'buy':
                    delta = - max(abs(position['size']*10), 1)*tick
                else:
                    delta = tick * max(abs(position['size']*10), 1)
        except KeyError:
            pass
        open_orders_instrument = list(filter(lambda order: order['instrument_name'] == instrument_name, open_orders.values()))
        mark_price = next(filter(lambda price: price['instrument_name'] == instrument_name, mark_prices), None)
        sell_price = 0
        buy_price = 0
        best_bids_price = 0
        best_asks_price = 1000

        strike = instrument_name[12:]
        strike = int(strike[:-2])

        # Get realized volatility estimate to start?
        iv_high = 1.05
        option_high = Option(european=True,
                             kind='call',
                             s0=underlying_price,
                             k=int(strike),
                             sigma=iv_high,
                             r=0.00,
                             start=str(dt.today().date()),
                             end='2021-03-26')
        iv_low = 0.85
        option_low = Option(european=True,
                             kind='call',
                             s0=underlying_price,
                             k=int(strike),
                             sigma=iv_low,
                             r=0.00,
                             start=str(dt.today().date()),
                             end='2021-03-26')



        price_high = option_high.getPrice()
        price_low = option_low.getPrice()
        sigma_price = (price_high - price_low)/2
        price = price_high - sigma_price
        btc_price = price/underlying_price
        btc_price_low = round(btc_price * 0.95, 4)
        buy_price = round(btc_price_low - btc_price_low % tick + delta, 4)
        btc_price_high = round(btc_price * 1.05, 4)
        sell_price = round(btc_price_high - btc_price_high % tick + delta, 4)

        # Kalman Filter
        #sigma_e = sigma_price*(0.1/traded_size - 1)
        #k = np.pow(sigma_price, 2) / (np.pow(sigma_price, 2) + np.pow(sigma_e, 2))
        #price_new = price + k *(traded_price - price)




        if books_data['asks']:
            best_asks_price = books_data['asks'][0][0]
        if books_data['bids']:
            best_bids_price = books_data['bids'][0][0]

        if best_bids_price >= btc_price_low:
            best_bids_price = 0
        if best_asks_price <= btc_price_high:
            best_asks_price = 10000

        sell_price = min(best_asks_price, sell_price)
        buy_price = max(best_bids_price, buy_price)

        open_buy = next(filter(lambda o: o['direction'] == 'buy', open_orders_instrument), None)
        open_sell = next(filter(lambda o: o['direction'] == 'sell', open_orders_instrument), None)

        if sell_price:
            if open_sell:
                edit_msg = edit_order_msg(access_token,
                                  open_sell['order_id'],
                                  0.1,
                                  sell_price)
                pending_order_msg_queue.append(edit_msg)
            else:
                sell_msg = {
                    "jsonrpc": "2.0",
                    "method": "private/sell",
                    "params": {
                        "instrument_name": instrument_name,
                        "amount": 0.1,
                        "price": sell_price,
                        "type": 'limit',
                        "access_token": access_token
                    }
                }
                pending_order_msg_queue.append(sell_msg)

        if buy_price:
            if open_buy:
                edit_msg = edit_order_msg(access_token,
                                          open_buy['order_id'],
                                          0.1,
                                          buy_price)

                pending_order_msg_queue.append(edit_msg)
            else:
                buy_msg = {
                    "jsonrpc": "2.0",
                    "method": "private/buy",
                    "params": {
                        "instrument_name": instrument_name,
                        "amount": 0.1,
                        "price": buy_price,
                        "type": 'limit',
                        "access_token": access_token
                    }
                }
                pending_order_msg_queue.append(buy_msg)

    return pending_order_msg_queue


def delta_hedging(access_token, underlying_name, underlying_price, delta):
    position_size = round(abs(delta) * underlying_price)
    position_size -= position_size % 10
    position_size = max(10000, position_size)

    if delta > 0:
        msg = {
            "jsonrpc": "2.0",
            "method": "private/sell",
            "params": {
                "instrument_name": underlying_name,
                "amount": position_size,
                "type": 'market',
                "access_token": access_token
            }
        }
    else:
        msg = {
            "jsonrpc": "2.0",
            "method": "private/buy",
            "params": {
                "instrument_name": underlying_name,
                "amount": position_size,
                "type": 'market',
                "access_token": access_token
            }
        }

    return msg
