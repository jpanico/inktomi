"""Roam Research asset fetching via the Local API.

Public symbols:

- :class:`FetchRoamAsset` — stateless utility class that fetches a Roam asset
  (image or file) by its Cloud Firestore URL via the Local API's ``file.get``
  action.
"""

from datetime import datetime
from typing import Literal, Self, final
from pydantic import Base64Bytes, BaseModel, ConfigDict, Field, validate_call
import logging

from inktomi.roam_local_api import ApiEndpoint, Request as LocalApiRequest, Response as LocalApiResponse, invoke_action
from inktomi.roam_asset import RoamAsset
from inktomi.roam_primitives import MediaType, Url

logger = logging.getLogger(__name__)


@final
class FetchRoamAsset:
    """Stateless utility class for fetching Roam assets from the Roam Research Local API.

    Executes a ``file.get`` action via the Local API, which proxies
    ``roamAlphaAPI.file.get`` through the Roam Desktop app's local HTTP server.
    The decoded asset is returned as a :class:`~inktomi.roam_asset.RoamAsset`.

    Delegates HTTP transport to :func:`~inktomi.roam_local_api.invoke_action`,
    which handles header construction and error raising.
    """

    def __init__(self) -> None:
        """Prevent instantiation of this stateless utility class."""
        raise TypeError("FetchRoamAsset is a stateless utility class and cannot be instantiated")

    class Request:
        """Namespace for ``file.get`` request types."""

        class Payload(LocalApiRequest.Payload):
            """``file.get`` specialisation of :class:`roam_local_api.Request.Payload`.

            Inherits ``action: str`` and ``args: list[object]`` from the parent.
            Instances must be constructed via :meth:`with_url`, which sets
            ``action`` to ``"file.get"`` and wraps the Cloud Firestore URL in a
            single :class:`Arg`.

            Once created, instances cannot be modified (frozen).
            """

            model_config = ConfigDict(frozen=True)

            class Arg(BaseModel):
                """A single positional argument in a ``file.get`` request.

                Attributes:
                    url: Cloud Firestore URL of the asset to fetch.
                    format: Encoding format for the response; always ``'base64'``.
                """

                model_config = ConfigDict(frozen=True)

                url: Url
                format: Literal["base64"] = Field(default="base64")

            @classmethod
            def with_url(cls, url: Url) -> Self:
                """Construct a ``file.get`` payload for the given Cloud Firestore URL.

                Args:
                    url: Cloud Firestore URL of the asset to fetch.

                Returns:
                    A frozen :class:`Payload` with ``action`` set to ``"file.get"``
                    and ``args`` containing a single :class:`Arg` for ``url``.
                """
                return cls(action="file.get", args=[cls.Arg(url=url)])

    class Response:
        """Namespace for ``file.get`` response types."""

        class Payload(BaseModel):
            """Parsed ``file.get`` response payload."""

            model_config = ConfigDict(frozen=True)

            success: bool
            result: Result

            class Result(BaseModel):
                """Decoded asset data returned by the ``file.get`` action."""

                model_config = ConfigDict(frozen=True)

                file_name: str = Field(alias="filename")
                media_type: MediaType = Field(alias="mimetype")
                content: Base64Bytes = Field(alias="base64")

    @staticmethod
    @validate_call
    def fetch(firebase_url: Url, api_endpoint: ApiEndpoint) -> RoamAsset:
        """Fetch an asset from Cloud Firestore via the Roam Research Local API.

        Builds a ``file.get`` request payload and delegates the HTTP call to
        :func:`~inktomi.roam_local_api.invoke_action`. The Roam Desktop app must be
        running and the user must be logged into the graph at the time this method is
        called.

        Args:
            firebase_url: The Cloud Firestore URL of the asset, as it appears in the
                Roam graph's Markdown.
            api_endpoint: The API endpoint (URL + bearer token) for the target Roam graph.

        Returns:
            An immutable :class:`~inktomi.roam_asset.RoamAsset` with the decoded
            binary contents, file name, media type, and a ``last_modified``
            timestamp of now.

        Raises:
            ValidationError: If any parameter is ``None`` or invalid.
            requests.exceptions.ConnectionError: If the Local API is unreachable.
            requests.exceptions.HTTPError: If the Local API returns a non-200 status.
        """
        logger.debug("api_endpoint: %s, firebase_url: %s", api_endpoint, firebase_url)

        request_payload: FetchRoamAsset.Request.Payload = FetchRoamAsset.Request.Payload.with_url(firebase_url)
        local_api_response_payload: LocalApiResponse.Payload = invoke_action(request_payload, api_endpoint)
        logger.debug("local_api_response_payload: %s", local_api_response_payload)
        fetch_asset_response_payload: FetchRoamAsset.Response.Payload = FetchRoamAsset.Response.Payload.model_validate(
            local_api_response_payload.model_dump(mode="json")
        )
        logger.debug("fetch_asset_response_payload: %s", fetch_asset_response_payload)

        result: FetchRoamAsset.Response.Payload.Result = fetch_asset_response_payload.result
        return RoamAsset(
            file_name=result.file_name,
            last_modified=datetime.now(),
            media_type=result.media_type,
            contents=result.content,
        )
