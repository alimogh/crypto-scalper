import json
import sys
from typing import Callable
from settings import DEBUG, SYMBOL
import time
from binance.client import Client
from binance.enums import SIDE_BUY, SIDE_SELL
from colors import colors, phrases
from binance.websockets import BinanceSocketManager
from twisted.internet import reactor


class Order:
    client: Client
    socket: BinanceSocketManager

    ticketSocketKey: str = None
    userSocketKey: str = None

    latestPrice: float = None
    latestOrder: dict = None
    accountEvent: dict = None

    @staticmethod
    def setClient(client: Client):
        """
        Sets static client for orders, starts socket
        """
        Order.client = client
        Order.socket = BinanceSocketManager(Order.client)
        Order.ticketSocketKey = Order.socket.start_trade_socket(
            SYMBOL, Order.processTradeSocket
        )
        Order.userSocketKey = Order.socket.start_user_socket(Order.processUserSocket)
        Order.socket.start()

        if Order.ticketSocketKey == False or Order.userSocketKey == False:
            print(colors.fail("FAILED") + " to open socket connection")
            exit(1)

    def __init__(
        self,
        symbol: str,
        side: SIDE_BUY or SIDE_SELL,
        price: float = 0,
        quantity: float = 0,
        basePrecision: int = 8,
        quotePrecision: int = 8,
        tickSize: float = 0,
        stepSize: float = 0,
        cancelThreshold: float or None = None,
        cancelled: bool = False,
    ) -> None:
        self.orderId: int = ""
        self.clientOrderId: str = ""
        self.filled: bool = False

        self.symbol = symbol
        self.symbol: str
        self.side = side
        self.cancelThreshold = cancelThreshold

        # self.price = round(price, quotePrecision)
        ticks = 0
        temp = tickSize
        while temp < 1:
            temp = temp * 10
            ticks = ticks + 1
        self.price = round(price, ticks)

        # self.quantity = round(quantity, basePrecision)
        ticks = 0
        temp = stepSize
        while temp < 1:
            temp = temp * 10
            ticks = ticks + 1
        self.quantity = round(quantity, ticks)

        self.basePrecision = basePrecision
        self.quotePrecision = quotePrecision
        self.tickSize = tickSize
        self.cancelled = cancelled

    def __str__(self) -> str:
        return (
            "\n"  # Added newline
            + phrases.cancelled(self.cancelled)
            + phrases.filledOrPlaced(self.filled)
            + phrases.buyOrSell(self.side)
            + "@ "
            + str(self.price)
            + " totaling "
            + str(self.quantity)
            + phrases.thresholdPricedOrNot(self.cancelThreshold)
            + "."
        )

    def fill(self):
        """
        Fill this order
        """
        self.filled = True

    def waitForOrder(self, callback: Callable or None = None) -> dict or False:
        """
        Waits for the order to fill, returns filled order dict
        :param callback function cancels this order
        :returns False if order is cancelled before being fully filled
        """
        # getOrder = Order.getAccountEvent()
        # while (
        #     getOrder == None
        #     or not "X" in getOrder
        #     or not "i" in getOrder
        #     or not getOrder["X"] == "FILLED"
        #     or not int(getOrder["i"]) == self.orderId
        # ):
        #     time.sleep(1)
        #     getOrder = Order.getAccountEvent()
        # print(getOrder)
        # self.fill()
        # return getOrder

        getOrder = Order.client.get_order(symbol=self.symbol, orderId=self.orderId)
        try:
            while not getOrder["status"] == "FILLED":
                if (not callback == None and callback()) or (
                    not self.cancelThreshold == None
                    and Order.getAveragePrice(self.symbol) > self.cancelThreshold
                ):
                    self.cancel()
                    return False
                time.sleep(10)
                getOrder = Order.client.get_order(
                    symbol=self.symbol, orderId=self.orderId
                )
        except:
            raise
        self.fill()
        return getOrder

    def place(self) -> dict or None:
        """
        Place the order
        :returns api response or None if in debug mode
        """
        self.printStatus()
        if self.side == SIDE_BUY:
            if DEBUG:
                pass
            else:
                result = Order.client.order_limit_buy(
                    symbol=self.symbol,
                    quantity=self.quantity,
                    price=self.price,
                )
                self.orderId = result["orderId"]
                self.clientOrderId = result["clientOrderId"]
                return result
        elif self.side == SIDE_SELL:
            if DEBUG:
                pass
            else:
                result = Order.client.order_limit_sell(
                    symbol=self.symbol,
                    quantity=self.quantity,
                    price=self.price,
                )
                self.orderId = result["orderId"]
                self.clientOrderId = result["clientOrderId"]
                return result
        return None

    def printStatus(self) -> None:
        print(self)

    @staticmethod
    def processTradeSocket(message: dict) -> None:
        """
        Processes socket message
        """
        for i in range(len(str(message["p"]))):
            sys.stdout.write("\b")
        sys.stdout.write(str(message["p"]))
        sys.stdout.flush()
        Order.latestPrice = float(message["p"])

    @staticmethod
    def processUserSocket(message: dict) -> None:
        """
        Processes user socket event
        """
        print(message)
        Order.accountEvent = json.loads(message)

    @staticmethod
    def getOpenOrders(symbol: str) -> list:
        """
        Returns open orders
        """
        return list(Order.client.get_open_orders(symbol=symbol))

    @staticmethod
    def getLatestOrderPrice() -> float:
        if Order.latestPrice == None:
            while Order.latestPrice == None:
                return float(
                    Order.client.get_recent_trades(symbol=SYMBOL, limit=1)[0]["price"]
                )
        return Order.latestPrice

    @staticmethod
    def getLatestOrder() -> dict:
        if Order.latestOrder == None:
            return Order.client.get_recent_trades(symbol=SYMBOL, limit=1)[0]
        return Order.latestOrder

    @staticmethod
    def getAccountEvent() -> dict:
        return Order.accountEvent

    @staticmethod
    def stopSocket():
        """
        Stops the socket and reactor
        """
        Order.socket.close()
        reactor.stop()

    @staticmethod
    def cancelOrder(symbol: str, orderId: str) -> dict:
        """
        Cancel an order
        """
        return Order.client.cancel_order(symbol=symbol, orderId=orderId)

    def cancel(self) -> dict:
        """
        Cancel this order
        :returns api response
        """
        self.cancelled = True
        self.printStatus()
        return Order.cancelOrder(self.symbol, self.orderId)

    @staticmethod
    def getAssetBalance(asset: str) -> float:
        return float(Order.client.get_asset_balance(asset=asset)["free"])

    @staticmethod
    def getAveragePrice(asset: str) -> float:
        return float(Order.client.get_avg_price(symbol=asset)["price"])