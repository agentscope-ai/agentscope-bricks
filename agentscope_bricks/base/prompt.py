# -*- coding: utf-8 -*-
import re
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union

from jinja2 import Environment, meta
from pydantic import BaseModel

from agentscope_bricks.utils.schemas.oai_llm import (
    AssistantMessage,
    OpenAIMessage,
    SystemMessage,
    ToolMessage,
    UserMessage,
)
from .__base import BaseComponent

DEFAULT_KNOWLEDGE_TEMPLATE = """## 来自 {source} 的内容：

```
{content}
```"""

ArgsT = TypeVar("ArgsT", bound=BaseModel, contravariant=True)
ReturnT = TypeVar(
    "ReturnT",
    bound=Union[List[OpenAIMessage], str],
    covariant=True,
)


class PromptTemplate(BaseComponent, Generic[ArgsT, ReturnT]):
    """Template class for generating prompts from structured data."""

    def __init__(
        self,
        template: Union[
            str,
            List[Dict[str, str]],
        ] = DEFAULT_KNOWLEDGE_TEMPLATE,
        template_format: str = "f-string",
        prefix: str = "",
        postfix: str = "",
    ):
        """Initialize the PromptTemplate.

        Args:
            template: The template for a single prompt or list of message
                      dictionaries.
            template_format: The format of the template ('jinja2',
                             'f-string', or 'interpolation').
            prefix: Prefix for multiple prompts.
            postfix: Postfix for multiple prompts.

        Raises:
            ValueError: If template_format is not supported or template type
                is invalid.
        """
        if template_format not in ["jinja2", "f-string", "interpolation"]:
            raise ValueError(
                "Supported template formats are 'jinja2', "
                "'f-string', and 'interpolation'.",
            )
        self.template_format = template_format
        self.env = Environment() if template_format == "jinja2" else None

        if not isinstance(template, str) and not isinstance(template, list):
            raise ValueError(
                "Template must be either a string or a "
                "list of message dictionaries.",
            )
        self.template = template
        self.prefix = prefix
        self.postfix = postfix

    @classmethod
    def from_template(
        cls,
        template: Union[str, List[Dict[str, str]]],
        template_format: str = "jinja2",
        prefix: str = "",
        postfix: str = "",
    ) -> "PromptTemplate":
        """Create a PromptTemplate instance from a template.

        Args:
            template: The template string or list of message dictionaries.
            template_format: The format of the template ('jinja2',
                            'f-string', or 'interpolation').
            prefix: Prefix for multiple prompts.
            postfix: Postfix for multiple prompts.

        Returns:
            PromptTemplate: A new PromptTemplate instance.
        """
        return cls(template, template_format, prefix, postfix)

    def format_from_context_providers(
        self,
        context_providers: Dict[str, ArgsT],
    ) -> str:
        """Format prompt from context providers.

        This method is only for system prompt with string not for message.

        Args:
            context_providers: Dictionary of context provider information.

        Returns:
            str: Formatted prompt string.
        """
        output = self.prefix
        if context_providers:
            for provider_info in context_providers.values():
                if provider_info:
                    formatted_prompt = self.format_prompt(provider_info)
                    if formatted_prompt is not None:
                        output += "/n/n"
                        output += formatted_prompt

        output += self.postfix
        return output

    def format(self, args: ArgsT) -> Union[List[OpenAIMessage], str]:
        """Format the template with the given arguments, could apply both
        message input and raw prompt input.

        Args:
            args: BaseModel instance containing template variables.

        Returns:
            Union[List[OpenAIMessage], str]: Formatted prompt as string or
            list of messages.
        """
        if isinstance(self.template, str):
            return self.format_prompt(args) or ""
        else:
            return self.format_message(args)

    async def arun(
        self,
        args: ArgsT,
        **kwargs: Any,
    ) -> Union[List[OpenAIMessage], str]:
        """Asynchronously format the template with the given arguments.

        Args:
            args: BaseModel instance containing template variables.
            **kwargs: Additional keyword arguments.

        Returns:
            Union[List[OpenAIMessage], str]: Formatted prompt as string or
            list of messages.
        """
        return self.format(args)

    def format_prompt(self, args: ArgsT) -> Optional[str]:
        """Format a string template with the given arguments.

        Args:
            args: BaseModel instance containing template variables.

        Returns:
            Optional[str]: Formatted prompt string.

        Raises:
            ValueError: If template is not a string.
        """
        if not isinstance(self.template, str):
            raise ValueError(
                "This template is for messages. Use format_message() instead.",
            )
        return self._format_template(self.template, args)

    def format_message(self, args: ArgsT) -> List[OpenAIMessage]:
        """Format a message template with the given arguments.

        Args:
            args: BaseModel instance containing template variables.

        Returns:
            List[OpenAIMessage]: List of formatted prompt messages.

        Raises:
            ValueError: If template is not a list or contains unsupported role.
        """
        if not isinstance(self.template, list):
            raise ValueError(
                "This template is not for messages. Use format() instead.",
            )

        formatted_messages = []
        for msg in self.template:
            role = msg["role"]
            content = self._format_template(msg["content"], args)

            if role == "system":
                formatted_message = SystemMessage(content=content)
            elif role == "user":
                formatted_message = UserMessage(content=content)
            elif role == "assistant":
                formatted_message = AssistantMessage(content=content)
            elif role == "tool":
                formatted_message = ToolMessage(
                    content=content,
                    tool_call_id=msg.get("tool_call_id", ""),
                )
            else:
                raise ValueError(f"Unsupported role: {role}")

            formatted_messages.append(formatted_message)

        return formatted_messages

    def _format_template(
        self,
        template: str,
        model_instance: Union[Dict, BaseModel],
    ) -> Optional[str]:
        """Format a template string with model instance data.

        Args:
            template: Template string to format.
            model_instance: BaseModel instance or dictionary containing
                template variables.

        Returns:
            Optional[str]: Formatted template string.

        Raises:
            ValueError: If template format is unsupported.
        """
        self._validate_template_with_model(template, model_instance.__class__)
        model_dict = (
            model_instance.model_dump()
            if isinstance(model_instance, BaseModel)
            else model_instance
        )
        model_dict = self.process_value_into_str(model_dict)
        if self.template_format == "jinja2":
            template_obj = self.env.from_string(template)
            return template_obj.render(**model_dict)
        elif self.template_format == "f-string":
            return template.format(**model_dict)
        elif self.template_format == "interpolation":
            variables = self._get_interpolation_variables(template)
            rendered_template = template
            for var_name in variables:
                var_value = str(getattr(model_instance, var_name))
                rendered_template = rendered_template.replace(
                    f"${{{var_name}}}",
                    var_value,
                )
            return rendered_template
        else:
            raise ValueError(
                f"Unsupported template format: {self.template_format}",
            )

    @staticmethod
    def process_value_into_str(model_dict: Dict) -> Dict:
        """Process model dictionary values into string format.

        Args:
            model_dict: Dictionary containing model data.

        Returns:
            Dict: Processed dictionary with string values.
        """
        processed_model = {}
        for item in model_dict.keys():
            if isinstance(model_dict[item], str):
                processed_model[item] = model_dict[item]
            if isinstance(model_dict[item], list):
                if len(model_dict[item]) > 0 and isinstance(
                    model_dict[item][0],
                    str,
                ):
                    processed_model[item] += "\n".join(model_dict[item])
            if isinstance(model_dict[item], BaseModel):
                processed_model[item] = model_dict[item].model_dump_json()
            if isinstance(model_dict[item], dict):
                value = ""
                for k, v in model_dict[item].items():
                    value += k + ":" + v + "\n"
                processed_model[item] = value
        return processed_model

    def _validate_template_with_model(
        self,
        template: str,
        model_class: Type[BaseModel],
    ) -> None:
        """Validate that template variables match model fields.

        Args:
            template: Template string to validate.
            model_class: BaseModel class to validate against.

        Raises:
            ValueError: If template variables are not found in model fields.
        """
        if self.template_format == "jinja2":
            template_variables = self._get_jinja2_variables(template)
        elif self.template_format == "f-string":
            template_variables = self._get_fstring_variables(template)
        elif self.template_format == "interpolation":
            template_variables = self._get_interpolation_variables(template)

        model_fields = set(model_class.model_fields.keys())

        missing_fields = template_variables - model_fields
        if missing_fields:
            raise ValueError(
                f"Template variables not found in model: {missing_fields}",
            )

        unused_fields = model_fields - template_variables
        if unused_fields:
            print(
                f"Warning: Model fields not used in template: {unused_fields}",
            )

    def _get_jinja2_variables(self, template: str) -> set:
        """Extract variables from Jinja2 template.

        Args:
            template: Jinja2 template string.

        Returns:
            set: Set of variable names found in the template.
        """
        ast = self.env.parse(template)
        return meta.find_undeclared_variables(ast)

    def _get_fstring_variables(self, template: str) -> set:
        """Extract variables from f-string template.

        Args:
            template: F-string template.

        Returns:
            set: Set of variable names found in the template.
        """
        pattern = r"\{([^}]+)\}"
        return set(re.findall(pattern, template))

    def _get_interpolation_variables(self, template: str) -> set:
        """Extract variables from interpolation template.

        Args:
            template: Interpolation template string.

        Returns:
            set: Set of variable names found in the template.
        """
        pattern = r"\$\{([^}]+)\}"
        return set(re.findall(pattern, template))
