import logging
from dataclasses import dataclass, field
from typing import List

logger = logging.getLogger(__name__)
VALID_SORT_ORDERS = {"asc", "desc"}
__all__ = ["QuerySettings", "prompt_for_query_settings"]


@dataclass(frozen=True)
class QuerySettings:
    endpoint: str
    fields: List[str] = field(default_factory=list)
    release_sort: str = "asc"
    limit: int = 10
    offset: int = 0

    def validate(self) -> None:
        """
        Validate the query settings.
        """
        if not self.endpoint:
            raise ValueError("Endpoint cannot be empty.")
        if not self.fields:
            raise ValueError("At least one field is required.")
        if any(not field.strip() for field in self.fields):
            raise ValueError("Fields cannot contain empty values.")
        if self.limit <= 0:
            raise ValueError("Limit must be positive.")
        if self.offset < 0:
            raise ValueError("Offset cannot be negative.")
        if self.release_sort not in VALID_SORT_ORDERS:
            raise ValueError("Release sort must be one of: asc, desc.")


def prompt_non_empty(message: str) -> str:
    """
    Prompt the user for a non-empty string value.
    :param:
        message: The prompt message to display to the user.
    :return:
        The non-empty string input from the user.
    """
    value = input(message).strip()
    if not value:
        raise ValueError("Value cannot be empty.")
    return value


def prompt_positive_int(message: str) -> int:
    """
    Prompt the user for a positive integer value.
    :param:
        message: The prompt message to display to the user.
    :return:
        The positive integer input from the user.
    """
    value = int(input(message).strip())
    if value <= 0:
        raise ValueError("Value must be positive.")
    return value


def prompt_non_negative_int(message: str) -> int:
    """
    Prompt the user for a non-negative integer value.
    :param:
        message: The prompt message to display to the user.
    :return:
        The non-negative integer input from the user.
    """
    value = int(input(message).strip())
    if value < 0:
        raise ValueError("Value cannot be negative.")
    return value


def prompt_release_sort(message: str = "Sort release date asc/desc (default asc): ") -> str:
    """
    Prompt the user for the release sort order.
    :param:
        message: The prompt message to display to the user.
    :return:
        The sort order input from the user, defaulting to 'asc' if invalid or empty.
    """
    value = input(message).strip().lower()
    if not value:
        return "asc"
    if value not in VALID_SORT_ORDERS:
        logger.warning("Invalid sort order; defaulting to asc.")
        return "asc"
    return value


def _collect_fields(count: int) -> List[str]:
    """
    Collect a list of fields from user input.
    :param:
        count: The number of fields to collect.
    :return:
        A list of field names input by the user.
    """
    fields: List[str] = []
    for index in range(count):
        fields.append(prompt_non_empty(f"Enter field #{index + 1}: "))
    return fields


def prompt_for_query_settings() -> QuerySettings:
    """
    Prompt the user for query settings and return a QuerySettings object.
    :return:
        A QuerySettings object populated with user input.
    """
    while True:
        try:
            endpoint = prompt_non_empty("Enter the endpoint you wish to gather data from: ").lower()
            field_count = prompt_positive_int("Please enter the number of fields you wish to use: ")
            fields = _collect_fields(field_count)
            release_sort = prompt_release_sort()
            limit = prompt_positive_int("How many inputs do you wish to gather: ")
            offset = prompt_non_negative_int(
                "Is there any entries you wish to skip? type 0 if you do not want to skip: "
            )

            settings = QuerySettings(
                endpoint=endpoint,
                fields=fields,
                release_sort=release_sort,
                limit=limit,
                offset=offset,
            )
            settings.validate()
            return settings
        except ValueError as exc:
            logger.error("Invalid input: %s. Please try again.", exc)
