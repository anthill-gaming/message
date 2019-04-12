from anthill.platform.core.messenger.handlers.transports import socketio
from anthill.platform.core.messenger.client.backends import db


class MessengerNamespace(socketio.MessengerNamespace):
    client_class = db.Client
