"""Provider-neutral model request construction for runtime executions."""

from atlas_agents.agents import AgentDefinition, AgentInput
from atlas_agents.models import (
    AudioContent,
    ImageContent,
    MessageContent,
    MessageRole,
    ModelCapability,
    ModelMessage,
    ModelRequest,
    ModelSelectionRequest,
    ModelSelectionResult,
    TextContent,
)
from atlas_agents.runtime.errors import RuntimeInputRejectedError
from atlas_agents.runtime.state import ExecutionState


class ModelRequestBuilder:
    """Build validated single-turn messages, requirements, and model requests."""

    def validate_input(self, input_data: AgentInput) -> None:
        """Reject empty input and attachment types unsupported by this runtime."""
        if not input_data.message.strip() and not input_data.attachments:
            raise RuntimeInputRejectedError(
                code="empty_agent_input",
                message="A execução requer uma mensagem ou attachment suportado.",
            )
        for attachment in input_data.attachments:
            if not attachment.media_type.startswith(("image/", "audio/")):
                raise RuntimeInputRejectedError(
                    code="unsupported_attachment",
                    message=(
                        "O runtime single-turn aceita somente attachments de imagem "
                        "ou áudio."
                    ),
                )

    def build_initial_messages(
        self,
        agent: AgentDefinition,
        input_data: AgentInput,
    ) -> tuple[ModelMessage, ...]:
        """Map instructions and input to ordered system and user messages."""
        self.validate_input(input_data)
        user_content: list[MessageContent] = []
        if input_data.message.strip():
            user_content.append(TextContent(text=input_data.message))
        for attachment in input_data.attachments:
            if attachment.media_type.startswith("image/"):
                user_content.append(
                    ImageContent(
                        uri=attachment.uri,
                        media_type=attachment.media_type,
                    )
                )
            elif attachment.media_type.startswith("audio/"):
                user_content.append(
                    AudioContent(
                        uri=attachment.uri,
                        media_type=attachment.media_type,
                    )
                )

        return (
            ModelMessage(
                role=MessageRole.SYSTEM,
                content=(TextContent(text=agent.instructions),),
            ),
            ModelMessage(role=MessageRole.USER, content=tuple(user_content)),
        )

    def derive_selection_request(
        self,
        input_data: AgentInput,
        requested: ModelSelectionRequest | None = None,
    ) -> ModelSelectionRequest:
        """Merge caller policy with capabilities required by the actual input."""
        self.validate_input(input_data)
        required = {ModelCapability.TEXT_GENERATION}
        for attachment in input_data.attachments:
            if attachment.media_type.startswith("image/"):
                required.add(ModelCapability.VISION)
            elif attachment.media_type.startswith("audio/"):
                required.add(ModelCapability.AUDIO_INPUT)

        if requested is None:
            return ModelSelectionRequest(required_capabilities=frozenset(required))
        return ModelSelectionRequest(
            provider=requested.provider,
            model=requested.model,
            required_capabilities=requested.required_capabilities | required,
            preferred_capabilities=requested.preferred_capabilities,
            minimum_context_window=requested.minimum_context_window,
            minimum_max_output_tokens=requested.minimum_max_output_tokens,
            metadata=requested.metadata,
        )

    def build_request(
        self,
        state: ExecutionState,
        selection: ModelSelectionResult,
    ) -> ModelRequest:
        """Build one vendor-neutral request from selected model and state messages."""
        return ModelRequest(
            model=selection.model,
            messages=state.messages,
        )
