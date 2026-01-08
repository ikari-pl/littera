"""
TUI decorators for safe action handling and common patterns.
"""

from functools import wraps
from typing import Any, Callable, TypeVar


T = TypeVar("T")


def safe_action(action_func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator that makes TUI actions safe by checking for required state."""

    @wraps(action_func)
    def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        # Common safety check - ensure state exists
        if hasattr(self, "state") and self.state is None:
            return None

        return action_func(self, *args, **kwargs)

    return wrapper


def require_state(action_func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator that ensures state exists before executing action."""

    @wraps(action_func)
    def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        if not hasattr(self, "state") or self.state is None:
            return None
        return action_func(self, *args, **kwargs)

    return wrapper
