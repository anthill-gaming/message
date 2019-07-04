# For more details about routing, see
# http://www.tornadoweb.org/en/stable/routing.html
from tornado.web import url
from .api.compat.rest import routes as rest_routes
from anthill.framework.utils.urls import include
from anthill.framework.handlers.socketio import socketio_server
from anthill.platform.core.messenger.handlers.transports import socketio
from . import handlers

MESSENGER_NAMESPACE = '/messenger'

socketio_server.register_namespace(handlers.MessengerNamespace(MESSENGER_NAMESPACE))

route_patterns = [
    url(r'^/', include(rest_routes.route_patterns, namespace='api')),  # for compatibility only
    url(r'^/socket.io/$', socketio.MessengerHandler),
]
