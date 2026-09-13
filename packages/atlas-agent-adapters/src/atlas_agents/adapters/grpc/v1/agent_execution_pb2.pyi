import datetime

from google.protobuf import struct_pb2 as _struct_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ApprovalDecision(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    APPROVAL_DECISION_UNSPECIFIED: _ClassVar[ApprovalDecision]
    APPROVAL_DECISION_APPROVE: _ClassVar[ApprovalDecision]
    APPROVAL_DECISION_REJECT: _ClassVar[ApprovalDecision]
APPROVAL_DECISION_UNSPECIFIED: ApprovalDecision
APPROVAL_DECISION_APPROVE: ApprovalDecision
APPROVAL_DECISION_REJECT: ApprovalDecision

class Attachment(_message.Message):
    __slots__ = ("attachment_id", "name", "media_type", "uri", "metadata")
    ATTACHMENT_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    MEDIA_TYPE_FIELD_NUMBER: _ClassVar[int]
    URI_FIELD_NUMBER: _ClassVar[int]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    attachment_id: str
    name: str
    media_type: str
    uri: str
    metadata: _struct_pb2.Struct
    def __init__(self, attachment_id: _Optional[str] = ..., name: _Optional[str] = ..., media_type: _Optional[str] = ..., uri: _Optional[str] = ..., metadata: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ...) -> None: ...

class AgentInput(_message.Message):
    __slots__ = ("message", "attachments", "metadata")
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    ATTACHMENTS_FIELD_NUMBER: _ClassVar[int]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    message: str
    attachments: _containers.RepeatedCompositeFieldContainer[Attachment]
    metadata: _struct_pb2.Struct
    def __init__(self, message: _Optional[str] = ..., attachments: _Optional[_Iterable[_Union[Attachment, _Mapping]]] = ..., metadata: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ...) -> None: ...

class ExecutionContext(_message.Message):
    __slots__ = ("session_id", "metadata")
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    metadata: _struct_pb2.Struct
    def __init__(self, session_id: _Optional[str] = ..., metadata: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ...) -> None: ...

class RequestedLimits(_message.Message):
    __slots__ = ("max_turns", "max_tool_calls", "max_input_tokens", "max_output_tokens", "max_total_tokens", "timeout_seconds")
    MAX_TURNS_FIELD_NUMBER: _ClassVar[int]
    MAX_TOOL_CALLS_FIELD_NUMBER: _ClassVar[int]
    MAX_INPUT_TOKENS_FIELD_NUMBER: _ClassVar[int]
    MAX_OUTPUT_TOKENS_FIELD_NUMBER: _ClassVar[int]
    MAX_TOTAL_TOKENS_FIELD_NUMBER: _ClassVar[int]
    TIMEOUT_SECONDS_FIELD_NUMBER: _ClassVar[int]
    max_turns: int
    max_tool_calls: int
    max_input_tokens: int
    max_output_tokens: int
    max_total_tokens: int
    timeout_seconds: float
    def __init__(self, max_turns: _Optional[int] = ..., max_tool_calls: _Optional[int] = ..., max_input_tokens: _Optional[int] = ..., max_output_tokens: _Optional[int] = ..., max_total_tokens: _Optional[int] = ..., timeout_seconds: _Optional[float] = ...) -> None: ...

class RequestedBudget(_message.Message):
    __slots__ = ("max_estimated_cost", "currency")
    MAX_ESTIMATED_COST_FIELD_NUMBER: _ClassVar[int]
    CURRENCY_FIELD_NUMBER: _ClassVar[int]
    max_estimated_cost: str
    currency: str
    def __init__(self, max_estimated_cost: _Optional[str] = ..., currency: _Optional[str] = ...) -> None: ...

class ExecuteRequest(_message.Message):
    __slots__ = ("request_id", "agent_id", "input", "context", "requested_limits", "requested_budget", "metadata")
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    AGENT_ID_FIELD_NUMBER: _ClassVar[int]
    INPUT_FIELD_NUMBER: _ClassVar[int]
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    REQUESTED_LIMITS_FIELD_NUMBER: _ClassVar[int]
    REQUESTED_BUDGET_FIELD_NUMBER: _ClassVar[int]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    request_id: str
    agent_id: str
    input: AgentInput
    context: ExecutionContext
    requested_limits: RequestedLimits
    requested_budget: RequestedBudget
    metadata: _struct_pb2.Struct
    def __init__(self, request_id: _Optional[str] = ..., agent_id: _Optional[str] = ..., input: _Optional[_Union[AgentInput, _Mapping]] = ..., context: _Optional[_Union[ExecutionContext, _Mapping]] = ..., requested_limits: _Optional[_Union[RequestedLimits, _Mapping]] = ..., requested_budget: _Optional[_Union[RequestedBudget, _Mapping]] = ..., metadata: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ...) -> None: ...

class ResumeRequest(_message.Message):
    __slots__ = ("request_id", "agent_id", "resume_token", "approval_request_id", "decision", "reason", "decided_at", "metadata")
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    AGENT_ID_FIELD_NUMBER: _ClassVar[int]
    RESUME_TOKEN_FIELD_NUMBER: _ClassVar[int]
    APPROVAL_REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    DECISION_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    DECIDED_AT_FIELD_NUMBER: _ClassVar[int]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    request_id: str
    agent_id: str
    resume_token: str
    approval_request_id: str
    decision: ApprovalDecision
    reason: str
    decided_at: _timestamp_pb2.Timestamp
    metadata: _struct_pb2.Struct
    def __init__(self, request_id: _Optional[str] = ..., agent_id: _Optional[str] = ..., resume_token: _Optional[str] = ..., approval_request_id: _Optional[str] = ..., decision: _Optional[_Union[ApprovalDecision, str]] = ..., reason: _Optional[str] = ..., decided_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., metadata: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ...) -> None: ...

class Error(_message.Message):
    __slots__ = ("code", "message", "retryable", "details")
    CODE_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    RETRYABLE_FIELD_NUMBER: _ClassVar[int]
    DETAILS_FIELD_NUMBER: _ClassVar[int]
    code: str
    message: str
    retryable: bool
    details: _struct_pb2.Struct
    def __init__(self, code: _Optional[str] = ..., message: _Optional[str] = ..., retryable: _Optional[bool] = ..., details: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ...) -> None: ...

class Usage(_message.Message):
    __slots__ = ("input_tokens", "output_tokens", "cached_input_tokens", "reasoning_tokens", "estimated_cost")
    INPUT_TOKENS_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_TOKENS_FIELD_NUMBER: _ClassVar[int]
    CACHED_INPUT_TOKENS_FIELD_NUMBER: _ClassVar[int]
    REASONING_TOKENS_FIELD_NUMBER: _ClassVar[int]
    ESTIMATED_COST_FIELD_NUMBER: _ClassVar[int]
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int
    reasoning_tokens: int
    estimated_cost: str
    def __init__(self, input_tokens: _Optional[int] = ..., output_tokens: _Optional[int] = ..., cached_input_tokens: _Optional[int] = ..., reasoning_tokens: _Optional[int] = ..., estimated_cost: _Optional[str] = ...) -> None: ...

class Citation(_message.Message):
    __slots__ = ("citation_key", "source_id", "document_id", "passage_id", "title", "uri", "page", "section")
    CITATION_KEY_FIELD_NUMBER: _ClassVar[int]
    SOURCE_ID_FIELD_NUMBER: _ClassVar[int]
    DOCUMENT_ID_FIELD_NUMBER: _ClassVar[int]
    PASSAGE_ID_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    URI_FIELD_NUMBER: _ClassVar[int]
    PAGE_FIELD_NUMBER: _ClassVar[int]
    SECTION_FIELD_NUMBER: _ClassVar[int]
    citation_key: str
    source_id: str
    document_id: str
    passage_id: str
    title: str
    uri: str
    page: int
    section: str
    def __init__(self, citation_key: _Optional[str] = ..., source_id: _Optional[str] = ..., document_id: _Optional[str] = ..., passage_id: _Optional[str] = ..., title: _Optional[str] = ..., uri: _Optional[str] = ..., page: _Optional[int] = ..., section: _Optional[str] = ...) -> None: ...

class ApprovalSubject(_message.Message):
    __slots__ = ("tool_call_id", "tool_name", "argument_keys")
    TOOL_CALL_ID_FIELD_NUMBER: _ClassVar[int]
    TOOL_NAME_FIELD_NUMBER: _ClassVar[int]
    ARGUMENT_KEYS_FIELD_NUMBER: _ClassVar[int]
    tool_call_id: str
    tool_name: str
    argument_keys: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, tool_call_id: _Optional[str] = ..., tool_name: _Optional[str] = ..., argument_keys: _Optional[_Iterable[str]] = ...) -> None: ...

class ApprovalRequest(_message.Message):
    __slots__ = ("approval_request_id", "execution_id", "agent_id", "kind", "summary", "reason", "requested_at", "expires_at", "subject")
    APPROVAL_REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    EXECUTION_ID_FIELD_NUMBER: _ClassVar[int]
    AGENT_ID_FIELD_NUMBER: _ClassVar[int]
    KIND_FIELD_NUMBER: _ClassVar[int]
    SUMMARY_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    REQUESTED_AT_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    SUBJECT_FIELD_NUMBER: _ClassVar[int]
    approval_request_id: str
    execution_id: str
    agent_id: str
    kind: str
    summary: str
    reason: str
    requested_at: _timestamp_pb2.Timestamp
    expires_at: _timestamp_pb2.Timestamp
    subject: ApprovalSubject
    def __init__(self, approval_request_id: _Optional[str] = ..., execution_id: _Optional[str] = ..., agent_id: _Optional[str] = ..., kind: _Optional[str] = ..., summary: _Optional[str] = ..., reason: _Optional[str] = ..., requested_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., expires_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., subject: _Optional[_Union[ApprovalSubject, _Mapping]] = ...) -> None: ...

class Suspension(_message.Message):
    __slots__ = ("execution_id", "approval_request", "resume_token", "checkpoint_version", "created_at")
    EXECUTION_ID_FIELD_NUMBER: _ClassVar[int]
    APPROVAL_REQUEST_FIELD_NUMBER: _ClassVar[int]
    RESUME_TOKEN_FIELD_NUMBER: _ClassVar[int]
    CHECKPOINT_VERSION_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    execution_id: str
    approval_request: ApprovalRequest
    resume_token: str
    checkpoint_version: int
    created_at: _timestamp_pb2.Timestamp
    def __init__(self, execution_id: _Optional[str] = ..., approval_request: _Optional[_Union[ApprovalRequest, _Mapping]] = ..., resume_token: _Optional[str] = ..., checkpoint_version: _Optional[int] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class ExecuteResponse(_message.Message):
    __slots__ = ("request_id", "execution_id", "status", "output", "error", "usage", "citations", "suspension", "metadata")
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    EXECUTION_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    USAGE_FIELD_NUMBER: _ClassVar[int]
    CITATIONS_FIELD_NUMBER: _ClassVar[int]
    SUSPENSION_FIELD_NUMBER: _ClassVar[int]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    request_id: str
    execution_id: str
    status: str
    output: _struct_pb2.Value
    error: Error
    usage: Usage
    citations: _containers.RepeatedCompositeFieldContainer[Citation]
    suspension: Suspension
    metadata: _struct_pb2.Struct
    def __init__(self, request_id: _Optional[str] = ..., execution_id: _Optional[str] = ..., status: _Optional[str] = ..., output: _Optional[_Union[_struct_pb2.Value, _Mapping]] = ..., error: _Optional[_Union[Error, _Mapping]] = ..., usage: _Optional[_Union[Usage, _Mapping]] = ..., citations: _Optional[_Iterable[_Union[Citation, _Mapping]]] = ..., suspension: _Optional[_Union[Suspension, _Mapping]] = ..., metadata: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ...) -> None: ...

class StreamItem(_message.Message):
    __slots__ = ("type", "sequence", "execution_id", "data")
    TYPE_FIELD_NUMBER: _ClassVar[int]
    SEQUENCE_FIELD_NUMBER: _ClassVar[int]
    EXECUTION_ID_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    type: str
    sequence: int
    execution_id: str
    data: _struct_pb2.Struct
    def __init__(self, type: _Optional[str] = ..., sequence: _Optional[int] = ..., execution_id: _Optional[str] = ..., data: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ...) -> None: ...
