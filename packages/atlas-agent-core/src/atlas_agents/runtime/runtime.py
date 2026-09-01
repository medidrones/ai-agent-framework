"""Single-turn agent runtime orchestrating one complete model invocation."""

import asyncio
from collections.abc import Mapping
from uuid import uuid4

from atlas_agents.agents import (
    AgentContext,
    AgentDefinition,
    AgentErrorInfo,
    AgentInput,
    AgentResult,
    ExecutionStatus,
)
from atlas_agents.events import AgentEventFactory, AgentEventType
from atlas_agents.exceptions import (
    ModelProviderError,
    ModelProviderRegistryError,
    ModelSelectionError,
)
from atlas_agents.models import (
    FinishReason,
    MessageRole,
    ModelExecutionContext,
    ModelMessage,
    ModelProviderRegistry,
    ModelResponse,
    ModelSelectionRequest,
    TextContent,
)
from atlas_agents.runtime.error_mapping import (
    model_provider_error_to_agent_error,
    model_selection_error_to_agent_error,
    registry_error_to_agent_error,
)
from atlas_agents.runtime.errors import RuntimeInputRejectedError
from atlas_agents.runtime.model_request import ModelRequestBuilder
from atlas_agents.runtime.state import ExecutionState


class AgentRuntime:
    """Own the provider-agnostic execution loop for one model turn."""

    def __init__(
        self,
        *,
        model_registry: ModelProviderRegistry,
        request_builder: ModelRequestBuilder | None = None,
    ) -> None:
        """Initialize the runtime with explicit replaceable dependencies."""
        self._model_registry = model_registry
        self._request_builder = (
            request_builder if request_builder is not None else ModelRequestBuilder()
        )

    async def run(
        self,
        *,
        agent: AgentDefinition,
        input_data: AgentInput,
        context: AgentContext,
        model_selection: ModelSelectionRequest | None = None,
    ) -> AgentResult[object]:
        """Execute exactly one model generation and return a terminal result."""
        state = ExecutionState(
            execution_id=context.execution_id,
            agent=agent,
            input_data=input_data,
            context=context,
        )
        factory = AgentEventFactory(context.execution_id)
        self._record(state, factory, AgentEventType.EXECUTION_CREATED)

        validating_transition = state.transition_to(ExecutionStatus.VALIDATING_INPUT)
        self._record(state, factory, AgentEventType.EXECUTION_STARTED)
        state.record_event(factory.from_transition(validating_transition))
        self._record(state, factory, AgentEventType.INPUT_VALIDATION_STARTED)
        try:
            self._request_builder.validate_input(input_data)
        except RuntimeInputRejectedError as error:
            self._record(
                state,
                factory,
                AgentEventType.INPUT_VALIDATION_COMPLETED,
                {"outcome": "rejected", "code": error.code},
            )
            self._reject(state, factory, code=error.code, reason=str(error))
            return state.to_result()
        self._record(
            state,
            factory,
            AgentEventType.INPUT_VALIDATION_COMPLETED,
            {"outcome": "accepted"},
        )

        self._transition(state, factory, ExecutionStatus.LOADING_CONTEXT)
        self._record(state, factory, AgentEventType.CONTEXT_LOADING_STARTED)
        messages = self._request_builder.build_initial_messages(agent, input_data)
        for message in messages:
            state.add_message(message)
        selection_request = self._request_builder.derive_selection_request(
            input_data,
            model_selection,
        )
        try:
            selection = await self._model_registry.select(selection_request)
            state.set_model_selection(selection)
            provider = self._model_registry.get(selection.provider_name)
        except ModelProviderError as error:
            self._fail_preparation(
                state,
                factory,
                model_provider_error_to_agent_error(error),
            )
            return state.to_result()
        except ModelSelectionError as error:
            self._fail_preparation(
                state,
                factory,
                model_selection_error_to_agent_error(error),
            )
            return state.to_result()
        except ModelProviderRegistryError as error:
            self._fail_preparation(
                state,
                factory,
                registry_error_to_agent_error(error),
            )
            return state.to_result()
        except Exception:
            self._fail_preparation(state, factory, self._runtime_error())
            return state.to_result()

        self._record(
            state,
            factory,
            AgentEventType.CONTEXT_LOADING_COMPLETED,
            {"outcome": "completed"},
        )

        self._transition(state, factory, ExecutionStatus.RUNNING)
        request = self._request_builder.build_request(state, selection)
        model_context = ModelExecutionContext(
            execution_id=state.execution_id,
            agent_id=agent.agent_id,
            request_id=str(uuid4()),
        )
        self._record(
            state,
            factory,
            AgentEventType.MODEL_EXECUTION_STARTED,
            {"provider": selection.provider_name, "model": selection.model},
        )
        state.increment_turn()
        try:
            response = await provider.generate(request, model_context)
        except asyncio.CancelledError:
            self._record(
                state,
                factory,
                AgentEventType.MODEL_EXECUTION_COMPLETED,
                {"outcome": "cancelled"},
            )
            self._cancel(
                state,
                factory,
                reason="A chamada ao modelo foi cancelada pelo consumidor.",
            )
            raise
        except ModelProviderError as error:
            self._record(
                state,
                factory,
                AgentEventType.MODEL_EXECUTION_COMPLETED,
                {"outcome": "failed"},
            )
            self._fail(state, factory, model_provider_error_to_agent_error(error))
            return state.to_result()
        except Exception:
            self._record(
                state,
                factory,
                AgentEventType.MODEL_EXECUTION_COMPLETED,
                {"outcome": "failed"},
            )
            self._fail(state, factory, self._runtime_error())
            return state.to_result()

        self._record(
            state,
            factory,
            AgentEventType.MODEL_EXECUTION_COMPLETED,
            {
                "outcome": "completed",
                "finish_reason": response.finish_reason.value,
            },
        )
        state.add_model_usage(response.usage)
        state.add_message(
            ModelMessage(role=MessageRole.ASSISTANT, content=response.content)
        )
        self._transition(state, factory, ExecutionStatus.VALIDATING_OUTPUT)
        self._record(state, factory, AgentEventType.OUTPUT_VALIDATION_STARTED)
        return self._finish_response(state, factory, response)

    def _finish_response(
        self,
        state: ExecutionState,
        factory: AgentEventFactory,
        response: ModelResponse,
    ) -> AgentResult[object]:
        if response.finish_reason in {FinishReason.STOP, FinishReason.LENGTH}:
            output = "".join(
                part.text for part in response.content if isinstance(part, TextContent)
            )
            if not output:
                return self._failed_output(
                    state,
                    factory,
                    code="model_empty_text_response",
                    message="O modelo não retornou conteúdo textual utilizável.",
                )
            self._record(
                state,
                factory,
                AgentEventType.OUTPUT_VALIDATION_COMPLETED,
                {
                    "outcome": "accepted",
                    "partial": response.finish_reason is FinishReason.LENGTH,
                },
            )
            state.complete(output)
            state.record_event(factory.from_transition(state.transitions[-1]))
            self._record(state, factory, AgentEventType.EXECUTION_COMPLETED)
            return state.to_result()

        if response.finish_reason is FinishReason.CONTENT_FILTER:
            self._record(
                state,
                factory,
                AgentEventType.OUTPUT_VALIDATION_COMPLETED,
                {"outcome": "rejected", "code": "model_content_filtered"},
            )
            self._reject(
                state,
                factory,
                code="model_content_filtered",
                reason="O provider bloqueou o conteúdo da resposta.",
            )
            return state.to_result()

        if response.finish_reason is FinishReason.CANCELLED:
            self._record(
                state,
                factory,
                AgentEventType.OUTPUT_VALIDATION_COMPLETED,
                {"outcome": "cancelled", "code": "model_response_cancelled"},
            )
            self._cancel(
                state,
                factory,
                reason="O provider retornou uma resposta cancelada.",
            )
            return state.to_result()

        error_facts = {
            FinishReason.TOOL_CALL: (
                "unsupported_tool_call",
                "Chamadas de ferramentas não são suportadas pelo runtime single-turn.",
            ),
            FinishReason.ERROR: (
                "model_error_finish_reason",
                "O provider encerrou a resposta com erro.",
            ),
            FinishReason.UNKNOWN: (
                "model_unknown_finish_reason",
                "O provider retornou um motivo de término desconhecido.",
            ),
        }
        code, message = error_facts[response.finish_reason]
        return self._failed_output(state, factory, code=code, message=message)

    def _failed_output(
        self,
        state: ExecutionState,
        factory: AgentEventFactory,
        *,
        code: str,
        message: str,
    ) -> AgentResult[object]:
        self._record(
            state,
            factory,
            AgentEventType.OUTPUT_VALIDATION_COMPLETED,
            {"outcome": "failed", "code": code},
        )
        self._fail(state, factory, AgentErrorInfo(code=code, message=message))
        return state.to_result()

    def _record(
        self,
        state: ExecutionState,
        factory: AgentEventFactory,
        event_type: AgentEventType,
        data: Mapping[str, object] | None = None,
    ) -> None:
        del self
        state.record_event(factory.create(event_type, data=data))

    @staticmethod
    def _transition(
        state: ExecutionState,
        factory: AgentEventFactory,
        status: ExecutionStatus,
        *,
        reason: str | None = None,
    ) -> None:
        transition = state.transition_to(status, reason=reason)
        state.record_event(factory.from_transition(transition))

    def _fail(
        self,
        state: ExecutionState,
        factory: AgentEventFactory,
        error: AgentErrorInfo,
    ) -> None:
        state.fail(error)
        state.record_event(factory.from_transition(state.transitions[-1]))
        self._record(
            state,
            factory,
            AgentEventType.EXECUTION_FAILED,
            {"code": error.code},
        )

    def _fail_preparation(
        self,
        state: ExecutionState,
        factory: AgentEventFactory,
        error: AgentErrorInfo,
    ) -> None:
        self._record(
            state,
            factory,
            AgentEventType.CONTEXT_LOADING_COMPLETED,
            {"outcome": "failed", "code": error.code},
        )
        self._fail(state, factory, error)

    def _reject(
        self,
        state: ExecutionState,
        factory: AgentEventFactory,
        *,
        code: str,
        reason: str,
    ) -> None:
        self._transition(
            state,
            factory,
            ExecutionStatus.REJECTED,
            reason=reason,
        )
        self._record(
            state,
            factory,
            AgentEventType.EXECUTION_REJECTED,
            {"code": code, "reason": reason},
        )

    def _cancel(
        self,
        state: ExecutionState,
        factory: AgentEventFactory,
        *,
        reason: str,
    ) -> None:
        state.cancel(reason=reason)
        state.record_event(factory.from_transition(state.transitions[-1]))
        self._record(
            state,
            factory,
            AgentEventType.EXECUTION_CANCELLED,
            {"reason": reason},
        )

    @staticmethod
    def _runtime_error() -> AgentErrorInfo:
        return AgentErrorInfo(
            code="runtime_error",
            message="A execução falhou devido a um erro interno inesperado.",
        )
