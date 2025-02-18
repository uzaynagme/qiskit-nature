# This code is part of Qiskit.
#
# (C) Copyright IBM 2021.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Contains the Deprecation message methods."""

from abc import abstractmethod
import warnings
import functools
from typing import NamedTuple, Optional, Callable, Dict, Set
from enum import Enum, EnumMeta


class DeprecatedEnum(Enum):
    """
    Shows deprecate message whenever member is accessed
    """

    def __new__(cls, value, *args):
        member = object.__new__(cls)
        member._value_ = value
        member._args = args
        member._show_deprecate = member.deprecate
        return member

    @abstractmethod
    def deprecate(self):
        """show deprecate message"""
        pass


class DeprecatedEnumMeta(EnumMeta):
    """
    Shows deprecate message whenever member is accessed
    """

    def __getattribute__(cls, name):
        obj = super().__getattribute__(name)
        if isinstance(obj, DeprecatedEnum) and obj._show_deprecate:
            obj._show_deprecate()
        return obj

    def __getitem__(cls, name):
        member = super().__getitem__(name)
        if member._show_deprecate:
            member._show_deprecate()
        return member

    # pylint: disable=redefined-builtin
    def __call__(cls, value, names=None, *, module=None, qualname=None, type=None, start=1):
        obj = super().__call__(
            value, names, module=module, qualname=qualname, type=type, start=start
        )
        if isinstance(obj, DeprecatedEnum) and obj._show_deprecate:
            obj._show_deprecate()
        return obj


class DeprecatedType(Enum):
    """ " Deprecation Types"""

    PACKAGE = "package"
    ENUM = "enum"
    CLASS = "class"
    METHOD = "method"
    FUNCTION = "function"
    ARGUMENT = "argument"
    PROPERTY = "property"


class _DeprecatedObject(NamedTuple):
    version: str
    old_type: DeprecatedType
    old_name: str
    new_type: DeprecatedType
    new_name: str
    additional_msg: str


_DEPRECATED_OBJECTS: Set[_DeprecatedObject] = set()


def warn_deprecated(
    version: str,
    old_type: DeprecatedType,
    old_name: str,
    new_type: Optional[DeprecatedType] = None,
    new_name: Optional[str] = None,
    additional_msg: Optional[str] = None,
    stack_level: int = 2,
) -> None:
    """Emits deprecation warning the first time only
    Args:
        version: Version to be used
        old_type: Old type to be used
        old_name: Old name to be used
        new_type: New type to be used
        new_name: New name to be used
        additional_msg: any additional message
        stack_level: stack level
    """
    # skip if it was already added
    obj = _DeprecatedObject(version, old_type, old_name, new_type, new_name, additional_msg)
    if obj in _DEPRECATED_OBJECTS:
        return

    _DEPRECATED_OBJECTS.add(obj)

    msg = (
        f"The {old_name} {old_type.value} is deprecated as of version {version} "
        "and will be removed no sooner than 3 months after the release"
    )
    if new_type is not None and new_name:
        msg += f". Instead use the {new_name} {new_type.value}"
    if additional_msg:
        msg += f" {additional_msg}"
    msg += "."

    warnings.warn(msg, DeprecationWarning, stacklevel=stack_level + 1)


def warn_deprecated_same_type_name(
    version: str,
    new_type: DeprecatedType,
    new_name: str,
    additional_msg: Optional[str] = None,
    stack_level: int = 2,
) -> None:
    """Emits deprecation warning the first time only
       Used when the type and name remained the same.
    Args:
        version: Version to be used
        new_type: new type to be used
        new_name: new name to be used
        additional_msg: any additional message
        stack_level: stack level
    """
    warn_deprecated(
        version, new_type, new_name, new_type, new_name, additional_msg, stack_level + 1
    )


def _rename_kwargs(version, func_name, kwargs, kwarg_map, additional_msg, stack_level):
    for old_arg, new_arg in kwarg_map.items():
        if old_arg in kwargs:
            if new_arg in kwargs:
                raise TypeError(
                    "{} received both {} and {} (deprecated).".format(func_name, new_arg, old_arg)
                )

            msg = (
                f"{func_name}: the {old_arg} {DeprecatedType.ARGUMENT.value} is deprecated "
                f"as of version {version} and will be removed no sooner "
                "than 3 months after the release. Instead use the "
                f"{new_arg} {DeprecatedType.ARGUMENT.value}"
            )
            if additional_msg:
                msg += f" {additional_msg}"
            msg += "."
            warnings.warn(msg, DeprecationWarning, stacklevel=stack_level)
            kwargs[new_arg] = kwargs.pop(old_arg)


def deprecate_arguments(
    version: str,
    kwarg_map: Dict[str, str],
    additional_msg: Optional[str] = None,
    stack_level: int = 3,
) -> Callable:
    """Decorator to alias deprecated argument names and warn upon use.
    Args:
        version: Version to be used
        kwarg_map: Args dictionary with old, new arguments
        additional_msg: any additional message
        stack_level: stack level

    Returns:
        The decorated function
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if kwargs:
                _rename_kwargs(
                    version, func.__name__, kwargs, kwarg_map, additional_msg, stack_level
                )
            return func(*args, **kwargs)

        return wrapper

    return decorator


def deprecate_method(
    version: str,
    new_type: DeprecatedType,
    new_name: str,
    additional_msg: Optional[str] = None,
    stack_level: int = 2,
) -> Callable:
    """Decorator that prints deprecated message for an instance method
    Args:
        version: Version to be used
        new_type: New type to be used
        new_name: New name to be used
        additional_msg: any additional message
        stack_level: stack level

    Returns:
        The decorated method
    """

    def decorator(method):
        msg = (
            f"The {method.__name__} {DeprecatedType.METHOD.value} is deprecated "
            f"as of version {version} and will be removed no sooner "
            "than 3 months after the release. Instead use the "
            f"{new_name} {new_type.value}"
        )
        if additional_msg:
            msg += f" {additional_msg}"
        msg += "."

        @functools.wraps(method)
        def wrapper(self, *method_args, **method_kwargs):
            # warn only once
            if not wrapper._warned:
                warnings.warn(msg, DeprecationWarning, stacklevel=stack_level)
                wrapper._warned = True
            return method(self, *method_args, **method_kwargs)

        wrapper._warned = False
        return wrapper

    return decorator


def deprecate_function(
    version: str,
    new_type: DeprecatedType,
    new_name: str,
    additional_msg: Optional[str] = None,
    stack_level: int = 2,
) -> Callable:
    """Decorator that prints deprecated message for a function
    Args:
        version: Version to be used
        new_type: New type to be used
        new_name: New name to be used
        additional_msg: any additional message
        stack_level: stack level

    Returns:
        The decorated function
    """

    def decorator(func):
        msg = (
            f"The {func.__name__} {DeprecatedType.FUNCTION.value} is deprecated "
            f"as of version {version} and will be removed no sooner "
            "than 3 months after the release. Instead use the "
            f"{new_name} {new_type.value}"
        )
        if additional_msg:
            msg += f" {additional_msg}"
        msg += "."

        @functools.wraps(func)
        def wrapper(*method_args, **method_kwargs):
            # warn only once
            if not wrapper._warned:
                warnings.warn(msg, DeprecationWarning, stacklevel=stack_level)
                wrapper._warned = True
            return func(*method_args, **method_kwargs)

        wrapper._warned = False
        return wrapper

    return decorator
