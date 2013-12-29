from twisted.application.service import Service
from twisted.internet import stdio

from autobahn.websocket import connectWS


class CoxswainService(Service):

    def __init__(self, factory):
        self.factory = factory
        self.conn = None

    def startService(self):
        #self.factory(ReveilleCommandProtocol())
        self.conn = connectWS(self.factory)
        self.running = True

    def stopService(self):
        self.factory.stopFactory()
        if self.conn is not None:
            self.conn.disconnect()
        self.running = False
