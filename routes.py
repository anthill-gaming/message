# For more details about routing, see
# http://www.tornadoweb.org/en/stable/routing.html
from tornado.web import url
from message import handlers
from anthill.framework.handlers.socketio import socketio_server
from anthill.platform.core.messenger.handlers.transports import socketio

MESSENGER_NAMESPACE = '/messenger'

socketio_server.register_namespace(handlers.MessengerNamespace(MESSENGER_NAMESPACE))

route_patterns = [
    url(r'^/socket.io/$', socketio.MessengerHandler),
]
