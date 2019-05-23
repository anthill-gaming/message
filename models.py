# For more details, see
# http://docs.sqlalchemy.org/en/latest/orm/tutorial.html#declare-a-mapping
from anthill.framework.db import db
from anthill.framework.utils import timezone
from anthill.platform.api.internal import InternalAPIMixin
from anthill.platform.auth import RemoteUser
from anthill.framework.utils.translation import translate_lazy as _
from anthill.framework.utils.asynchronous import as_future
from anthill.framework.utils.functional import SimpleLazyObject
from sqlalchemy_utils.types import ChoiceType, URLType
from functools import partial
import re
import six


def _lazy_re_compile(regex, flags=0):
    """Lazily compile a regex with flags."""
    def _compile():
        # Compile the regex if it was not passed pre-compiled.
        if isinstance(regex, six.string_types):
            return re.compile(regex, flags)
        else:
            assert not flags, "flags must be empty if regex is passed pre-compiled"
            return regex
    return SimpleLazyObject(_compile)


class UrlRegex:
    ul = '\u00a1-\uffff'  # unicode letters range (must be a unicode string, not a raw string)

    # IP patterns
    ipv4_re = r'(?:25[0-5]|2[0-4]\d|[0-1]?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|[0-1]?\d?\d)){3}'
    ipv6_re = r'\[[0-9a-f:\.]+\]'  # (simple regex, validated later)

    # Host patterns
    hostname_re = r'[a-z' + ul + r'0-9](?:[a-z' + ul + r'0-9-]{0,61}[a-z' + ul + r'0-9])?'
    # Max length for domain name labels is 63 characters per RFC 1034 sec. 3.1
    domain_re = r'(?:\.(?!-)[a-z' + ul + r'0-9-]{1,63}(?<!-))*'
    tld_re = (
        r'\.'  # dot
        r'(?!-)'  # can't start with a dash
        r'(?:[a-z' + ul + '-]{2,63}'  # domain label
        r'|xn--[a-z0-9]{1,59})'  # or punycode label
        r'(?<!-)'  # can't end with a dash
        r'\.?'  # may have a trailing dot
    )
    host_re = '(' + hostname_re + domain_re + tld_re + '|localhost)'

    build_regex = (
        r'(?:[a-z0-9\.\-\+]*)://'  # scheme
        r'(?:\S+(?::\S*)?@)?'  # user:pass authentication
        r'(?:' + ipv4_re + '|' + ipv6_re + '|' + host_re + ')'
        r'(?::\d{2,5})?'  # port
        r'(?:[/?#][^\s]*)?'  # resource path
    )

    url = _lazy_re_compile(r'^' + build_regex + r'\Z', re.IGNORECASE)
    urls = _lazy_re_compile(r'(?:' + build_regex + r')+', re.IGNORECASE)


url_regex = UrlRegex()


MESSAGE_STATUSES = (
    ('new', _('New')),
    ('read', _('Read')),
)


class MessageStatus(InternalAPIMixin, db.Model):
    __tablename__ = 'message_statuses'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    value = db.Column(ChoiceType(MESSAGE_STATUSES), default='new')
    updated = db.Column(db.DateTime, onupdate=timezone.now)
    message_id = db.Column(
        db.Integer, db.ForeignKey('messages.id', ondelete='CASCADE'))
    receiver_id = db.Column(db.Integer)

    @property
    def request_user(self):
        return partial(self.internal_request, 'login', 'get_user')

    async def get_receiver(self) -> RemoteUser:
        data = await self.request_user(user_id=self.receiver_id)
        return RemoteUser(**data)


class MessageReaction(InternalAPIMixin, db.Model):
    __tablename__ = 'message_reactions'
    __table_args__ = (
        db.UniqueConstraint('message_id', 'user_id', 'value'),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    value = db.Column(db.String(32))
    message_id = db.Column(db.Integer, db.ForeignKey('messages.id', ondelete='CASCADE'))
    user_id = db.Column(db.Integer)

    @property
    def request_user(self):
        return partial(self.internal_request, 'login', 'get_user')

    async def get_user(self) -> RemoteUser:
        data = await self.request_user(user_id=self.user_id)
        return RemoteUser(**data)


class Message(InternalAPIMixin, db.Model):
    __tablename__ = 'messages'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    sender_id = db.Column(db.Integer, nullable=False)
    group_id = db.Column(db.Integer, nullable=False)
    created = db.Column(db.DateTime, default=timezone.now)
    updated = db.Column(db.DateTime, onupdate=timezone.now)
    active = db.Column(db.Boolean, nullable=False, default=True)
    draft = db.Column(db.Boolean, nullable=False, default=False)
    statuses = db.relationship('MessageStatus', backref='message', lazy='dynamic')
    reactions = db.relationship('MessageReaction', backref='message', lazy='dynamic')
    discriminator = db.Column(db.String)

    __mapper_args__ = {
        'polymorphic_on': discriminator,
        'polymorphic_identity': 'message',
    }

    @property
    def request_user(self):
        return partial(self.internal_request, 'login', 'get_user')

    async def get_sender(self) -> RemoteUser:
        data = await self.request_user(user_id=self.sender_id)
        return RemoteUser(**data)

    @classmethod
    @as_future
    def outgoing_messages(cls, sender_id, **kwargs):
        return cls.query.filter_by(active=True, sender_id=sender_id, **kwargs)

    @classmethod
    @as_future
    def incoming_messages(cls, receiver_id, **kwargs):
        return cls.query.filter_by(active=True, **kwargs).join(MessageStatus) \
            .filter(MessageStatus.receiver_id == receiver_id)

    @classmethod
    async def draft_messages(cls, sender_id, **kwargs):
        return await cls.outgoing_messages(sender_id).filter_by(draft=True, **kwargs)

    @classmethod
    @as_future
    def new_messages(cls, receiver_id, **kwargs):
        return cls.query.filter_by(active=True, **kwargs).join(MessageStatus) \
            .filter(MessageStatus.receiver_id == receiver_id, MessageStatus.value == 'new')

    @as_future
    def add_reaction(self, user_id, value):
        # TODO: message_id = self.id
        pass


class TextMessage(Message):
    __tablename__ = 'text_messages'

    id = db.Column(db.Integer, db.ForeignKey('messages.id'), primary_key=True)
    content_type = db.Column(db.String(128), nullable=False, default='text/plain')
    value = db.Column(db.Text, nullable=False)

    __mapper_args__ = {
        'polymorphic_identity': 'text_message',
    }


class FileMessage(Message):
    __tablename__ = 'file_messages'

    id = db.Column(db.Integer, db.ForeignKey('messages.id'), primary_key=True)
    content_type = db.Column(db.String(128), nullable=False)
    value = db.Column(URLType, nullable=False)

    __mapper_args__ = {
        'polymorphic_identity': 'file_message',
    }


class URLMessage(Message):
    __tablename__ = 'url_messages'

    id = db.Column(db.Integer, db.ForeignKey('messages.id'), primary_key=True)
    content_type = db.Column(db.String(128), nullable=False)
    value = db.Column(URLType, nullable=False)

    __mapper_args__ = {
        'polymorphic_identity': 'url_message',
    }
