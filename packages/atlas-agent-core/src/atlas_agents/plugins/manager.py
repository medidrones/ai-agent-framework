"""Explicit plugin orchestration with preflight and per-plugin rollback."""

import asyncio
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass
from importlib.metadata import version as distribution_version
from typing import Any, Protocol

from pydantic import JsonValue

from atlas_agents.guardrails import GuardrailRegistry
from atlas_agents.models import ModelProviderRegistry
from atlas_agents.plugins._models import non_empty
from atlas_agents.plugins.contract import Plugin
from atlas_agents.plugins.contributions import (
    CONTRIBUTION_TYPES,
    EvaluatorContribution,
    GuardrailContribution,
    ModelProviderContribution,
    PluginContributionDescriptor,
    PluginContributionValue,
    ToolContribution,
)
from atlas_agents.plugins.discovery import (
    PluginDiscovery,
    PluginEntryPoint,
    PluginLoader,
)
from atlas_agents.plugins.errors import (
    PluginActivationError,
    PluginAlreadyActiveError,
    PluginContributionConflictError,
    PluginDeactivationError,
    PluginProtocolError,
    PluginRegistrationError,
    PluginRollbackError,
)
from atlas_agents.plugins.manifest import (
    PluginCapability,
    PluginCompatibilityChecker,
    PluginContext,
)
from atlas_agents.plugins.registry import PluginRegistry
from atlas_agents.plugins.results import PluginActivationResult
from atlas_agents.tools import ToolRegistry


class EvaluatorRegistryLike(Protocol):
    """Describe the evaluator registry operations needed by plugin management."""

    def register(self, evaluator: Any) -> None:  # noqa: ANN401
        """Register one evaluator extension."""
        ...

    def unregister(self, evaluator_id: str) -> Any:  # noqa: ANN401
        """Remove one evaluator extension."""
        ...

    def try_get(self, evaluator_id: str) -> Any | None:  # noqa: ANN401
        """Resolve one evaluator extension without raising."""
        ...


@dataclass(frozen=True, slots=True)
class _ActivePluginRecord:
    context: PluginContext
    descriptors: tuple[PluginContributionDescriptor, ...]
    contributions: tuple[PluginContributionValue, ...]
    registered: tuple[PluginContributionValue, ...]


class PluginManager:
    """Coordinate explicit plugin loading, activation, and deactivation."""

    def __init__(
        self,
        *,
        plugin_registry: PluginRegistry | None = None,
        plugin_discovery: PluginDiscovery | None = None,
        plugin_loader: PluginLoader | None = None,
        compatibility_checker: PluginCompatibilityChecker | None = None,
        atlas_version: str | None = None,
        model_provider_registry: ModelProviderRegistry | None = None,
        tool_registry: ToolRegistry | None = None,
        guardrail_registry: GuardrailRegistry | None = None,
        evaluator_registry: EvaluatorRegistryLike | None = None,
    ) -> None:
        """Initialize with explicit, instance-local collaborators."""
        self._plugin_registry = plugin_registry or PluginRegistry()
        self._discovery = plugin_discovery or PluginDiscovery()
        self._loader = plugin_loader or PluginLoader()
        self._compatibility = compatibility_checker or PluginCompatibilityChecker()
        self._atlas_version = atlas_version or distribution_version("atlas-agent-core")
        self._model_providers = model_provider_registry
        self._tools = tool_registry
        self._guardrails = guardrail_registry
        self._evaluators = evaluator_registry
        self._active: dict[str, _ActivePluginRecord] = {}

    @property
    def registry(self) -> PluginRegistry:
        """Return the explicitly owned plugin registry."""
        return self._plugin_registry

    def discover(self) -> tuple[PluginEntryPoint, ...]:
        """Discover descriptors only; this never loads or activates plugin code."""
        return self._discovery.discover()

    def load(self, entry_point: PluginEntryPoint) -> Plugin:
        """Explicitly load one discovered plugin without registering contributions."""
        return self._loader.load(entry_point)

    def register_plugin(self, plugin: Plugin) -> None:
        """Register one trusted plugin instance without activating it."""
        self._plugin_registry.register(plugin)

    async def activate(
        self,
        plugin_id: str,
        *,
        configuration: Mapping[str, JsonValue] | None = None,
    ) -> PluginActivationResult:
        """Validate, preflight, activate, and atomically register one plugin."""
        plugin = self._plugin_registry.get(plugin_id)
        if plugin_id in self._active:
            raise PluginAlreadyActiveError(
                f"O plugin '{plugin_id}' já está ativo.", plugin_id=plugin_id
            )

        manifest = self._plugin_registry.manifest(plugin_id)
        self._compatibility.validate(manifest, self._atlas_version)
        context = PluginContext.create(
            atlas_version=self._atlas_version,
            configuration=configuration,
        )
        descriptors = self._describe(plugin_id, plugin, context)
        self._validate_descriptors(plugin_id, manifest.capabilities, descriptors)
        self._preflight_conflicts(plugin_id, descriptors)

        try:
            contributions = await plugin.activate(context)
        except asyncio.CancelledError:
            await self._cleanup_preserving_cancellation(plugin, context)
            raise
        except Exception as exc:
            await self._cleanup_best_effort(plugin, context)
            raise PluginActivationError(
                f"A ativação do plugin '{plugin_id}' falhou ({type(exc).__name__}).",
                plugin_id=plugin_id,
            ) from exc

        try:
            validated = self._validate_contributions(
                plugin_id,
                manifest.capabilities,
                descriptors,
                contributions,
            )
        except Exception:
            await self._cleanup_best_effort(plugin, context)
            raise

        registered: list[PluginContributionValue] = []
        try:
            for contribution in validated:
                if self._is_managed(contribution.capability):
                    self._register(contribution)
                    registered.append(contribution)
        except Exception as exc:
            rollback_failures = self._rollback(tuple(registered))
            await self._cleanup_best_effort(plugin, context)
            if rollback_failures:
                raise PluginRollbackError(
                    f"O rollback do plugin '{plugin_id}' ficou incompleto "
                    f"({len(rollback_failures)} falha(s)).",
                    plugin_id=plugin_id,
                ) from exc
            raise PluginRegistrationError(
                f"O registro das contribuições do plugin '{plugin_id}' falhou "
                f"({type(exc).__name__}); as alterações foram revertidas.",
                plugin_id=plugin_id,
            ) from exc

        record = _ActivePluginRecord(
            context=context,
            descriptors=descriptors,
            contributions=validated,
            registered=tuple(registered),
        )
        self._active[plugin_id] = record
        self._plugin_registry.mark_active(plugin_id, descriptors)
        registered_ids = {
            (item.capability, non_empty(item.identifier, field_name="identifier"))
            for item in registered
        }
        registered_descriptors = tuple(
            item for item in descriptors if item.identity in registered_ids
        )
        unmanaged_descriptors = tuple(
            item for item in descriptors if item.identity not in registered_ids
        )
        return PluginActivationResult(
            plugin_id=plugin_id,
            activated=True,
            contributions=descriptors,
            registered_contributions=registered_descriptors,
            unregistered_contributions=unmanaged_descriptors,
        )

    async def deactivate(self, plugin_id: str) -> None:
        """Unregister contributions in reverse order, then release resources."""
        plugin = self._plugin_registry.get(plugin_id)
        record = self._active.get(plugin_id)
        if record is None:
            from atlas_agents.plugins.errors import PluginNotActiveError

            raise PluginNotActiveError(
                f"O plugin '{plugin_id}' não está ativo.", plugin_id=plugin_id
            )

        failures: list[Exception] = []
        for contribution in reversed(record.registered):
            try:
                self._unregister(contribution)
            except Exception as exc:
                failures.append(exc)
        self._active.pop(plugin_id, None)
        self._plugin_registry.mark_inactive(plugin_id)
        try:
            await plugin.deactivate(record.context)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            failures.append(exc)
        if failures:
            raise PluginDeactivationError(
                f"A desativação do plugin '{plugin_id}' terminou com "
                f"{len(failures)} falha(s) ({type(failures[0]).__name__}).",
                plugin_id=plugin_id,
            ) from failures[0]

    def get_contributions(self, plugin_id: str) -> tuple[PluginContributionValue, ...]:
        """Return active implementations for explicit host composition."""
        self._plugin_registry.get(plugin_id)
        record = self._active.get(plugin_id)
        if record is None:
            from atlas_agents.plugins.errors import PluginNotActiveError

            raise PluginNotActiveError(
                f"O plugin '{plugin_id}' não está ativo.", plugin_id=plugin_id
            )
        return record.contributions

    @staticmethod
    def _describe(
        plugin_id: str, plugin: Plugin, context: PluginContext
    ) -> tuple[PluginContributionDescriptor, ...]:
        try:
            descriptors = plugin.describe(context)
        except Exception as exc:
            raise PluginActivationError(
                f"A descrição do plugin '{plugin_id}' falhou ({type(exc).__name__}).",
                plugin_id=plugin_id,
            ) from exc
        if not isinstance(descriptors, tuple) or not all(
            isinstance(item, PluginContributionDescriptor) for item in descriptors
        ):
            raise PluginProtocolError(
                f"O plugin '{plugin_id}' retornou descritores inválidos.",
                plugin_id=plugin_id,
            )
        return descriptors

    @staticmethod
    def _validate_descriptors(
        plugin_id: str,
        capabilities: tuple[PluginCapability, ...],
        descriptors: tuple[PluginContributionDescriptor, ...],
    ) -> None:
        identities: set[tuple[PluginCapability, str]] = set()
        declared = set(capabilities)
        for descriptor in descriptors:
            if descriptor.capability not in declared:
                raise PluginProtocolError(
                    f"O plugin '{plugin_id}' descreveu a capability não declarada "
                    f"'{descriptor.capability.value}'.",
                    plugin_id=plugin_id,
                )
            if descriptor.identity in identities:
                raise PluginProtocolError(
                    f"O plugin '{plugin_id}' descreveu a contribuição duplicada "
                    f"'{descriptor.identifier}'.",
                    plugin_id=plugin_id,
                )
            identities.add(descriptor.identity)

    def _preflight_conflicts(
        self,
        plugin_id: str,
        descriptors: tuple[PluginContributionDescriptor, ...],
    ) -> None:
        for descriptor in descriptors:
            existing = self._try_get(descriptor.capability, descriptor.identifier)
            if existing is not None:
                raise PluginContributionConflictError(
                    plugin_id,
                    descriptor.capability.value,
                    descriptor.identifier,
                )

    @staticmethod
    def _validate_contributions(
        plugin_id: str,
        capabilities: tuple[PluginCapability, ...],
        descriptors: tuple[PluginContributionDescriptor, ...],
        contributions: object,
    ) -> tuple[PluginContributionValue, ...]:
        if not isinstance(contributions, tuple) or not all(
            isinstance(item, CONTRIBUTION_TYPES) for item in contributions
        ):
            raise PluginProtocolError(
                f"O plugin '{plugin_id}' retornou contribuições inválidas.",
                plugin_id=plugin_id,
            )
        typed = contributions
        identities: list[tuple[PluginCapability, str]] = []
        try:
            for contribution in typed:
                identifier = non_empty(contribution.identifier, field_name="identifier")
                if contribution.capability not in capabilities:
                    raise PluginProtocolError(
                        f"O plugin '{plugin_id}' retornou a capability não declarada "
                        f"'{contribution.capability.value}'.",
                        plugin_id=plugin_id,
                    )
                identities.append((contribution.capability, identifier))
        except PluginProtocolError:
            raise
        except Exception as exc:
            raise PluginProtocolError(
                f"O plugin '{plugin_id}' retornou uma contribuição inválida.",
                plugin_id=plugin_id,
            ) from exc
        expected = [item.identity for item in descriptors]
        if len(set(identities)) != len(identities) or set(identities) != set(expected):
            raise PluginProtocolError(
                f"As contribuições ativadas por '{plugin_id}' não correspondem "
                "aos descritores aprovados.",
                plugin_id=plugin_id,
            )
        return typed

    def _is_managed(self, capability: PluginCapability) -> bool:
        return (
            (
                capability is PluginCapability.MODEL_PROVIDER
                and self._model_providers is not None
            )
            or (capability is PluginCapability.TOOL and self._tools is not None)
            or (
                capability is PluginCapability.GUARDRAIL
                and self._guardrails is not None
            )
            or (
                capability is PluginCapability.EVALUATOR
                and self._evaluators is not None
            )
        )

    def _try_get(self, capability: PluginCapability, identifier: str) -> object | None:
        if capability is PluginCapability.MODEL_PROVIDER and self._model_providers:
            return self._model_providers.try_get(identifier)
        if capability is PluginCapability.TOOL and self._tools:
            return self._tools.try_get(identifier)
        if capability is PluginCapability.GUARDRAIL and self._guardrails:
            return self._guardrails.try_get(identifier)
        if capability is PluginCapability.EVALUATOR and self._evaluators:
            return self._evaluators.try_get(identifier)
        return None

    def _register(self, contribution: PluginContributionValue) -> None:
        if isinstance(contribution, ModelProviderContribution):
            registry = self._model_providers
            if registry is None:
                raise RuntimeError("Registry de providers ausente após preflight")
            registry.register(contribution.provider)
        elif isinstance(contribution, ToolContribution):
            registry_tools = self._tools
            if registry_tools is None:
                raise RuntimeError("Registry de ferramentas ausente após preflight")
            registry_tools.register(contribution.tool)
        elif isinstance(contribution, GuardrailContribution):
            registry_guardrails = self._guardrails
            if registry_guardrails is None:
                raise RuntimeError("Registry de guardrails ausente após preflight")
            registry_guardrails.register(contribution.guardrail)
        elif isinstance(contribution, EvaluatorContribution):
            registry_evaluators = self._evaluators
            if registry_evaluators is None:
                raise RuntimeError("Registry de evaluators ausente após preflight")
            registry_evaluators.register(contribution.evaluator)

    def _unregister(self, contribution: PluginContributionValue) -> None:
        if isinstance(contribution, ModelProviderContribution):
            registry = self._model_providers
            if registry is None:
                raise RuntimeError("Registry de providers ausente durante remoção")
            registry.unregister(contribution.identifier)
        elif isinstance(contribution, ToolContribution):
            registry_tools = self._tools
            if registry_tools is None:
                raise RuntimeError("Registry de ferramentas ausente durante remoção")
            registry_tools.unregister(contribution.identifier)
        elif isinstance(contribution, GuardrailContribution):
            registry_guardrails = self._guardrails
            if registry_guardrails is None:
                raise RuntimeError("Registry de guardrails ausente durante remoção")
            registry_guardrails.unregister(contribution.identifier)
        elif isinstance(contribution, EvaluatorContribution):
            registry_evaluators = self._evaluators
            if registry_evaluators is None:
                raise RuntimeError("Registry de evaluators ausente durante remoção")
            registry_evaluators.unregister(contribution.identifier)

    def _rollback(
        self, registered: tuple[PluginContributionValue, ...]
    ) -> tuple[Exception, ...]:
        failures: list[Exception] = []
        for contribution in reversed(registered):
            try:
                self._unregister(contribution)
            except Exception as exc:
                failures.append(exc)
        return tuple(failures)

    @staticmethod
    async def _cleanup_best_effort(plugin: Plugin, context: PluginContext) -> None:
        with suppress(Exception):
            await plugin.deactivate(context)

    @staticmethod
    async def _cleanup_preserving_cancellation(
        plugin: Plugin, context: PluginContext
    ) -> None:
        with suppress(Exception, asyncio.CancelledError):
            await plugin.deactivate(context)
