"""Map versioned protobuf messages to transport-neutral application DTOs."""

from __future__ import annotations

import json
from datetime import UTC
from decimal import Decimal
from typing import Literal, cast

from google.protobuf import json_format, struct_pb2, timestamp_pb2
from pydantic import JsonValue, ValidationError

from atlas_agents.adapters.errors import InvalidExternalRequestError
from atlas_agents.adapters.grpc.v1 import agent_execution_pb2 as pb
from atlas_agents.adapters.models import (
    ExecuteAgentRequest,
    ExecuteAgentResponse,
    ExecutionStreamItem,
    ExternalAgentInput,
    ExternalAttachment,
    ExternalExecutionContext,
    RequestedExecutionBudget,
    RequestedExecutionLimits,
    ResumeExecutionRequest,
    TransportPrincipal,
)


def _mapping(value: struct_pb2.Struct) -> dict[str, JsonValue]:
    return cast(
        "dict[str, JsonValue]",
        json_format.MessageToDict(value, preserving_proto_field_name=True),
    )


def _struct(value: dict[str, JsonValue]) -> struct_pb2.Struct:
    message = struct_pb2.Struct()
    json_format.ParseDict(value, message)
    return message


def _value(value: JsonValue | None) -> struct_pb2.Value:
    message = struct_pb2.Value()
    json_format.Parse(json.dumps(value, ensure_ascii=False), message)
    return message


def execute_from_proto(
    value: pb.ExecuteRequest,
    *,
    principal: TransportPrincipal,
    idempotency_key: str | None = None,
    transport_timeout: float | None = None,
) -> ExecuteAgentRequest:
    """Validate and map a protobuf execution request."""
    try:
        limits = None
        if value.HasField("requested_limits") or transport_timeout is not None:
            current = value.requested_limits
            requested_timeout = (
                current.timeout_seconds if current.HasField("timeout_seconds") else None
            )
            timeout = requested_timeout
            if transport_timeout is not None:
                timeout = (
                    transport_timeout
                    if timeout is None
                    else min(timeout, transport_timeout)
                )
            limits = RequestedExecutionLimits(
                max_turns=current.max_turns if current.HasField("max_turns") else None,
                max_tool_calls=(
                    current.max_tool_calls
                    if current.HasField("max_tool_calls")
                    else None
                ),
                max_input_tokens=(
                    current.max_input_tokens
                    if current.HasField("max_input_tokens")
                    else None
                ),
                max_output_tokens=(
                    current.max_output_tokens
                    if current.HasField("max_output_tokens")
                    else None
                ),
                max_total_tokens=(
                    current.max_total_tokens
                    if current.HasField("max_total_tokens")
                    else None
                ),
                timeout_seconds=timeout,
            )
        budget = None
        if value.HasField("requested_budget"):
            current_budget = value.requested_budget
            budget = RequestedExecutionBudget(
                max_estimated_cost=(
                    Decimal(current_budget.max_estimated_cost)
                    if current_budget.HasField("max_estimated_cost")
                    else None
                ),
                currency=(
                    current_budget.currency
                    if current_budget.HasField("currency")
                    else None
                ),
            )
        return ExecuteAgentRequest(
            request_id=value.request_id,
            agent_id=value.agent_id,
            input=ExternalAgentInput(
                message=value.input.message,
                attachments=tuple(
                    ExternalAttachment(
                        attachment_id=item.attachment_id,
                        name=item.name,
                        media_type=item.media_type,
                        uri=item.uri,
                        metadata=_mapping(item.metadata),
                    )
                    for item in value.input.attachments
                ),
                metadata=_mapping(value.input.metadata),
            ),
            context=ExternalExecutionContext(
                session_id=(
                    value.context.session_id
                    if value.context.HasField("session_id")
                    else None
                ),
                metadata=_mapping(value.context.metadata),
            ),
            requested_limits=limits,
            requested_budget=budget,
            metadata=_mapping(value.metadata),
            principal=principal,
            idempotency_key=idempotency_key,
        )
    except (ValidationError, ValueError):
        raise InvalidExternalRequestError("A requisição gRPC é inválida.") from None


def resume_from_proto(
    value: pb.ResumeRequest,
    *,
    principal: TransportPrincipal,
    idempotency_key: str | None = None,
) -> ResumeExecutionRequest:
    """Validate and map a protobuf resume request conservatively."""
    decisions = {
        pb.APPROVAL_DECISION_APPROVE: "approve",
        pb.APPROVAL_DECISION_REJECT: "reject",
    }
    decision = cast(
        "Literal['approve', 'reject'] | None", decisions.get(value.decision)
    )
    if decision is None:
        raise InvalidExternalRequestError("A decisão de aprovação é inválida.")
    try:
        return ResumeExecutionRequest(
            request_id=value.request_id,
            agent_id=value.agent_id,
            resume_token=value.resume_token,
            approval_request_id=value.approval_request_id,
            decision=decision,
            reason=value.reason if value.HasField("reason") else None,
            decided_at=value.decided_at.ToDatetime(tzinfo=UTC),
            metadata=_mapping(value.metadata),
            principal=principal,
            idempotency_key=idempotency_key,
        )
    except (ValidationError, ValueError):
        raise InvalidExternalRequestError(
            "A requisição gRPC de retomada é inválida."
        ) from None


def response_to_proto(value: ExecuteAgentResponse) -> pb.ExecuteResponse:
    """Map one application outcome to the versioned protobuf contract."""
    message = pb.ExecuteResponse(
        request_id=value.request_id,
        execution_id=value.execution_id,
        status=value.status.value,
        output=_value(value.output),
        metadata=_struct(value.metadata),
    )
    if value.error is not None:
        message.error.CopyFrom(
            pb.Error(
                code=value.error.code,
                message=value.error.message,
                retryable=value.error.retryable,
                details=_struct(value.error.details),
            )
        )
    if value.usage is not None:
        usage = pb.Usage(
            input_tokens=value.usage.input_tokens,
            output_tokens=value.usage.output_tokens,
            cached_input_tokens=value.usage.cached_input_tokens,
            reasoning_tokens=value.usage.reasoning_tokens,
        )
        if value.usage.estimated_cost is not None:
            usage.estimated_cost = str(value.usage.estimated_cost)
        message.usage.CopyFrom(usage)
    for item in value.citations:
        citation = message.citations.add(
            citation_key=item.citation_key,
            source_id=item.source_id,
            document_id=item.document_id,
            passage_id=item.passage_id,
        )
        if item.title is not None:
            citation.title = item.title
        if item.uri is not None:
            citation.uri = item.uri
        if item.page is not None:
            citation.page = item.page
        if item.section is not None:
            citation.section = item.section
    if value.suspension is not None:
        suspension = value.suspension
        approval = suspension.approval_request
        requested_at = timestamp_pb2.Timestamp()
        requested_at.FromDatetime(approval.requested_at)
        approval_message = pb.ApprovalRequest(
            approval_request_id=approval.approval_request_id,
            execution_id=approval.execution_id,
            agent_id=approval.agent_id,
            kind=approval.kind,
            summary=approval.summary,
            reason=approval.reason,
            requested_at=requested_at,
            subject=pb.ApprovalSubject(
                tool_call_id=approval.subject.tool_call_id,
                tool_name=approval.subject.tool_name,
                argument_keys=approval.subject.argument_keys,
            ),
        )
        if approval.expires_at is not None:
            approval_message.expires_at.FromDatetime(approval.expires_at)
        created_at = timestamp_pb2.Timestamp()
        created_at.FromDatetime(suspension.created_at)
        message.suspension.CopyFrom(
            pb.Suspension(
                execution_id=suspension.execution_id,
                approval_request=approval_message,
                resume_token=suspension.resume_token,
                checkpoint_version=suspension.checkpoint_version,
                created_at=created_at,
            )
        )
    return message


def stream_to_proto(value: ExecutionStreamItem) -> pb.StreamItem:
    """Map one ordered application stream item without buffering."""
    return pb.StreamItem(
        type=value.type,
        sequence=value.sequence,
        execution_id=value.execution_id,
        data=_struct(value.data),
    )
