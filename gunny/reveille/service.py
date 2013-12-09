from twisted.application import internet
from twisted.application.service import Service
from twisted.internet import reactor

from autobahn.websocket import connectWS


class ControlService(Service):
    pass


class PlayerService(Service):

    def __init__(self, factory):
        self.factory = factory
        self.conn = None

    def startService(self):
        self.factory.startFactory()
        self.conn = connectWS(self.factory)
        self.running = 1

    def stopService(self):
        self.factory.stopFactory()
        if self.conn is not None:
            self.conn.disconnect()
        self.running = 0
