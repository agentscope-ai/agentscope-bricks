# -*- coding: utf-8 -*-
import json
import types
import inspect
from inspect import Parameter, signature
from typing import (
    Any,
    Callable,
    Dict,
    Literal,
    Type,
    TypedDict,
    Union,
    get_type_hints,
)

from pydantic import BaseModel, create_model

from agentscope_runtime.engine.schemas.agent_schemas import (
    FunctionParameters,
    FunctionTool,
)


def schema_type_to_typing(schema_property: Dict[str, Any]) -> Any:
    """Convert a JSON schema property to a Python typing annotation.

    Args:
        schema_property: Dictionary containing JSON schema property definition.

    Returns:
        Any: Python typing annotation corresponding to the schema type.
    """
    schema_type = schema_property.get("type", "any")

    if schema_type == "string":
        if "enum" in schema_property:
            return Literal[tuple(schema_property["enum"])]
        return str
    elif schema_type == "integer":
        return int
    elif schema_type == "number":
        return float
    elif schema_type == "boolean":
        return bool
    elif schema_type == "array":
        items_schema = schema_property.get("items", {})
        item_type = schema_type_to_typing(items_schema)
        return list(item_type)
    elif schema_type == "object":
        if "properties" in schema_property:
            # Create a TypedDict for the object
            properties = {}
            for prop_name, prop_schema in schema_property[
                "properties"
            ].items():
                properties[prop_name] = schema_type_to_typing(prop_schema)
            class_name = schema_property.get(
                "title",
                "CustomTypedDict",
            )  # Use types.new_class() instead of type()
            namespace = {"__annotations__": properties}
            return types.new_class(
                class_name,
                (TypedDict,),
                {},
                lambda ns: ns.update(namespace),
            )
        else:
            return Dict[str, Any]
    else:  # "any" or unknown types
        return Any


def function_schema_to_typing(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a function call schema to Python typing annotations with
    default values.

    Args:
        schema: Dictionary containing function schema definition.

    Returns:
        Dict[str, Any]: Dictionary mapping parameter names to (type,
                    default_value) tuples.  Format: {'key_name': (type,
                    default_value)} or { 'key_name': (type, ...)} if no
                    default.
    """
    annotations = {}

    parameters = schema
    if parameters.get("type") != "object":
        return {}
    properties = parameters.get("properties", {})
    required = parameters.get("required", [])

    for param_name, param_schema in properties.items():
        param_type = schema_type_to_typing(param_schema)
        # Check if parameter has a default value specified in schema
        if "default" in param_schema:
            default_value = param_schema["default"]
        # If not required, use None as default
        elif param_name not in required:
            default_value = None
        # If required, use ... to indicate no default value
        else:
            default_value = ...
        annotations[param_name] = (param_type, default_value)

    # Add return type if available
    if "returns" in schema:
        returns_schema = schema["returns"]
        returns_type = schema_type_to_typing(returns_schema)
        annotations["return"] = (
            returns_type,
            ...,
        )  # Return type doesn't have a default value
    return annotations


def function_tool(
    _func: Callable = None,
    *,
    name_override: str = None,
    description_override: str = None,
    schema_override: FunctionParameters = None,
) -> Callable:
    """Decorator to convert any function to a Component-like functionality,
    after applying this decorator to a function, the function will act as a
    component, and could be called during function call loop

    Args:
        _func: The function to decorate (when used without parentheses).
        name_override: Override name for the function schema.
        description_override: Override description for the function schema.
        schema_override: Override schema for function parameters.

    Returns:
        Callable: Decorated function with added functionality.
    """

    def decorator(func: Callable) -> Callable:
        """Inner decorator function.

        Adds:
        - function_schema: A schema representation of the function.
        - arun: An asynchronous version of the function.
        - verify_args: A method to validate function arguments.

        Args:
            func: The function to decorate.

        Returns:
            Callable: The decorated function with added methods.
        """

        # Generate Pydantic model for argument validation
        func_annotations = get_type_hints(func)
        sig = signature(func)
        fields = {}

        if schema_override is None:
            for name, param in sig.parameters.items():
                if name == "return":
                    continue
                typ = func_annotations.get(name, Any)
                if param.default is Parameter.empty:
                    # Required parameter
                    fields[name] = (typ, ...)
                else:
                    # Optional parameter, set default value
                    fields[name] = (typ, param.default)
        else:
            fields = function_schema_to_typing(schema_override.model_dump())
        args_model: Type[BaseModel] = create_model(
            f"{func.__name__}Args",
            **fields,
        )

        def generate_function_schema(
            schema: Union[Dict, FunctionParameters] = None,
        ) -> FunctionTool:
            """Generate function schema for the decorated function.

            Args:
                schema: Optional schema override.

            Returns:
                FunctionTool: Function schema representation.
            """
            properties = {}
            required = []
            for name, field in args_model.model_fields.items():
                properties[name] = {
                    "type": (
                        field.annotation.__name__
                        if hasattr(field.annotation, "__name__")
                        else str(field.annotation)
                    ),
                }
                if field.is_required():
                    required.append(name)

            if schema is None:
                parameters = FunctionParameters(
                    type="object",
                    properties=properties,
                    required=required,
                )
            else:
                parameters = schema

            return FunctionTool(
                name=(
                    name_override
                    if name_override is not None
                    else func.__name__
                ),
                description=description_override or (func.__doc__ or ""),
                parameters=parameters,
            )

        def run(*args: Any, **kwargs: Any) -> Any:
            """Synchronous wrapper for the decorated function.

            Args:
                *args: Positional arguments.
                **kwargs: Keyword arguments.

            Returns:
                Any: Result of the function execution.
            """
            # Validate arguments
            if args:
                validated_args = verify_args(args[0])
            else:
                validated_args = verify_args(kwargs)
            # Call the original function with validated arguments
            return func(**validated_args)

        async def arun(*args: Any, **kwargs: Any) -> Any:
            """Asynchronous wrapper for the decorated function.

            Args:
                *args: Positional arguments.
                **kwargs: Keyword arguments.

            Returns:
                Any: Result of the function execution.
            """
            # Call the original function with validated arguments
            if args:
                validated_args = verify_args(args[0])
            else:
                validated_args = verify_args(kwargs)
            # Call the original function with validated arguments
            if inspect.iscoroutinefunction(func):
                return await func(**validated_args)
            else:
                return func(**validated_args)

        def verify_args(args: Dict[str, Any]) -> Dict[str, Any]:
            """Validate function arguments against the schema.

            Args:
                args: Arguments to validate (can be string, dict,
                or BaseModel).

            Returns:
                Dict[str, Any]: Validated argument dictionary.

            Raises:
                ValueError: If arguments are invalid or JSON format is
                incorrect.
            """
            try:
                if isinstance(args, str):
                    args_dict = json.loads(args)
                elif isinstance(args, BaseModel):
                    args_dict = args.model_dump()
                else:
                    args_dict = args

                validated_args = args_model(**args_dict)
                return validated_args.model_dump(exclude_none=True)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON format: {e}")
            except Exception as e:
                raise ValueError(f"Invalid arguments: {e}")

        # Return a new function object that wraps the original function
        wrapper = func  # Use run as the main entry point
        wrapper.arun = arun
        wrapper.run = run
        wrapper.verify_args = verify_args
        wrapper.function_schema = generate_function_schema(schema_override)

        return wrapper

    if _func is None:
        # If called with arguments, return the decorator
        return decorator
    else:
        # If called without arguments, apply directly
        return decorator(_func)


def tool_function_factory(
    schema: Union[FunctionTool, Dict],
    actual_func: Callable,
    **factory_kwargs: Any,
) -> Callable:
    """Create a tool function based on the given schema.

    Args:
        schema: The schema definition of the tool (dict or FunctionTool).
        actual_func: The actual function to execute.
        **factory_kwargs: Additional keyword arguments for the factory.

    Returns:
        Callable: The function generated according to the schema.
    """
    if isinstance(schema, Dict):
        schema = FunctionTool(**schema)
    tool_name = schema.name
    tool_description = schema.description
    input_schema = schema.parameters
    if isinstance(input_schema, FunctionParameters):
        input_schema = input_schema.model_dump()
    required_properties = input_schema.get("required", [])

    async def generated_tool(**kwargs: Any) -> Any:
        """Generate a function by schema.

        Args:
            **kwargs: Keyword arguments for the tool function.

        Returns:
            Any: Result of the actual function execution.

        Raises:
            ValueError: If required properties are missing.
        """
        # Validate required parameters
        for prop in required_properties:
            if prop not in kwargs:
                raise ValueError(f"Missing required property: {prop}")
        extra_kwargs = factory_kwargs.copy()

        # Call the original function with validated arguments
        if inspect.iscoroutinefunction(actual_func):
            return await actual_func(
                tool_name=tool_name,
                tool_params=kwargs,
                **extra_kwargs,
            )
        else:
            return actual_func(
                tool_name=tool_name,
                tool_params=kwargs,
                **extra_kwargs,
            )

    # Generate function docstring
    generated_tool.__doc__ = f"{tool_description}"
    generated_tool.__name__ = tool_name

    return function_tool(
        generated_tool,
        schema_override=FunctionParameters(**input_schema),
    )
