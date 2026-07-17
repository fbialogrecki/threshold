from threshold.users.v1 import user_pb2 as _user_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Event(_message.Message):
    __slots__ = ("id", "title", "starts_at", "city", "organizer")
    ID_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    STARTS_AT_FIELD_NUMBER: _ClassVar[int]
    CITY_FIELD_NUMBER: _ClassVar[int]
    ORGANIZER_FIELD_NUMBER: _ClassVar[int]
    id: str
    title: str
    starts_at: str
    city: str
    organizer: _user_pb2.User
    def __init__(self, id: _Optional[str] = ..., title: _Optional[str] = ..., starts_at: _Optional[str] = ..., city: _Optional[str] = ..., organizer: _Optional[_Union[_user_pb2.User, _Mapping]] = ...) -> None: ...

class GetEventRequest(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class GetEventResponse(_message.Message):
    __slots__ = ("event",)
    EVENT_FIELD_NUMBER: _ClassVar[int]
    event: Event
    def __init__(self, event: _Optional[_Union[Event, _Mapping]] = ...) -> None: ...
