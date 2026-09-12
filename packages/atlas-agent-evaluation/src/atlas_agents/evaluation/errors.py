"""Typed failures for evaluation configuration and orchestration."""


class EvaluationError(Exception):
    """Base class for expected evaluation framework failures."""


class EvaluationConfigurationError(EvaluationError):
    """Report invalid evaluation configuration."""


class EvaluationDatasetError(EvaluationConfigurationError):
    """Report an invalid dataset contract."""


class DuplicateEvaluationCaseError(EvaluationDatasetError):
    """Report a repeated case identifier."""


class DuplicateExpectationError(EvaluationDatasetError):
    """Report a repeated expectation identifier within one case."""


class EvaluatorRegistryError(EvaluationConfigurationError):
    """Base class for evaluator registry failures."""


class DuplicateEvaluatorError(EvaluatorRegistryError):
    """Report a repeated evaluator identifier."""


class EvaluatorNotRegisteredError(EvaluatorRegistryError):
    """Report an expectation referencing an unknown evaluator."""


class EvaluationProtocolError(EvaluationError):
    """Report an evaluator or observation protocol violation."""


class EvaluationMetricError(EvaluationError):
    """Report an invalid metric, score, threshold, or bound."""


class IncompatibleEvaluationMetricError(EvaluationMetricError):
    """Report conflicting definitions sharing a metric identifier."""


class EvaluationExecutionError(EvaluationError):
    """Report failure to produce an observation for one case."""
