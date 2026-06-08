"""Generic accumulator-pipeline validation framework.

Provides a small, side-effect-free validation pipeline:

- :class:`ValidationError` — immutable record of a single validation failure.
- :class:`ValidationResult` — immutable collection of all failures from a
  validation run; empty means valid.
- :data:`Validator` — type alias for a pure validator function.
- :func:`validate_all` — runs every validator in sequence and accumulates
  results into a :class:`ValidationResult`.

All validators always run regardless of prior failures (no short-circuit),
so the caller receives the complete set of errors in one pass.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class ValidationError:
    """Immutable record of a single validation failure.

    Attributes:
        validator: The validator function that produced this error.
        message: Human-readable description of the validation failure.
    """

    validator: Callable[..., ValidationError | None]
    message: str

    def __str__(self) -> str:
        """Return a human-readable string combining the validator name and message."""
        return f"{self.validator.__name__}: {self.message}"


@dataclass(frozen=True)
class ValidationResult:
    """Immutable collection of all validation failures from a single run.

    An empty :attr:`errors` tuple means the input was valid.

    Attributes:
        errors: All failures produced by the validator pipeline. Empty when valid.
    """

    errors: tuple[ValidationError, ...]

    @property
    def is_valid(self) -> bool:
        """Return True when no validation errors were recorded."""
        return len(self.errors) == 0


type Validator[T] = Callable[[T], ValidationError | None]
"""A pure validator function over an input of type ``T``.

Returns a :class:`ValidationError` if the input violates the rule,
or ``None`` if the input passes.

Each validator is responsible only for detecting a single violation; it has
no knowledge of the :class:`ValidationResult` accumulator or other validators
in the pipeline.
"""


def validate_all[T](input: T, validators: list[Validator[T]]) -> ValidationResult:
    """Run every validator over ``input`` and return the accumulated result.

    All validators always run regardless of prior failures — no short-circuit.

    Args:
        input: The value to validate.
        validators: Ordered list of validators to apply.

    Returns:
        A :class:`ValidationResult` containing all failures, or an empty
        result if every validator passed.
    """
    errors: Final[tuple[ValidationError, ...]] = tuple(error for v in validators if (error := v(input)) is not None)
    return ValidationResult(errors=errors)
