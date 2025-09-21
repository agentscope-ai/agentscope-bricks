# -*- coding: utf-8 -*-
import asyncio
from duckduckgo_search import DDGS
from enum import Enum
from langchain_community.retrievers import ArxivRetriever
from tavily import AsyncTavilyClient
from typing import Any, Dict, List


class SearchAPI(Enum):
    """Enumeration of available searches APIs."""

    ARXIV = "arxiv"
    MODELSTUDIO = "modelstudio"
    DUCKDUCKGO = "duckduckgo"
    TAVILY = "tavily"


def deduplicate_and_format_sources(
    search_response: List,
    max_tokens_per_source: int,
    include_raw_content: bool = True,
) -> str:
    """
    Takes a list of searches responses and formats them into a readable string.
    Limits the raw_content to approximately max_tokens_per_source tokens.

    Args:
        search_response (List): List of search response dicts,
        each containing:
            - query: str
            - results: List of dicts with fields:
                - title: str
                - url: str
                - content: str
                - score: float
                - raw_content: str|None
        max_tokens_per_source (int): Maximum number of tokens per source.
        include_raw_content (bool): Whether to include raw content.
            Defaults to True.

    Returns:
        str: Formatted string with deduplicated sources
    """
    # Collect all results
    sources_list = []
    for response in search_response:
        sources_list.extend(response["results"])

    # Deduplicate by URL
    unique_sources = {source["url"]: source for source in sources_list}

    # Format output
    formatted_text = "Content from sources:\n"
    for i, source in enumerate(unique_sources.values(), 1):
        formatted_text += f"{'=' * 80}\n"  # Clear section separator
        formatted_text += f"Source: {source['title']}\n"
        formatted_text += f"{'-' * 80}\n"  # Subsection separator
        formatted_text += f"URL: {source['url']}\n===\n"
        formatted_text += (
            f"Most relevant content from source: {source['content']}\n===\n"
        )
        if include_raw_content:
            # Using rough estimate of 4 characters per token
            char_limit = max_tokens_per_source * 4
            # Handle None raw_content
            raw_content = source.get("raw_content", "")
            if raw_content is None:
                raw_content = ""
                print(
                    f"Warning: No raw_content found "
                    f"for source {source['url']}",
                )
            if len(raw_content) > char_limit:
                raw_content = raw_content[:char_limit] + "... [truncated]"
            formatted_text += f"Full source content limited to {max_tokens_per_source} tokens: {raw_content}\n\n"  # noqa E501
        formatted_text += f"{'=' * 80}\n\n"  # End section separator

    return formatted_text.strip()


async def tavily_search_async(search_queries: List[str]) -> List[dict]:
    """
    Performs concurrent web searches using the Tavily API.

    Args:
        search_queries (List[str]): List of searches queries to process

    Returns:
            List[dict]: List of searches responses from Tavily API, one per
            query. Each response has format:
                {
                    'query': str, # The original searches query
                    'follow_up_questions': None,
                    'answer': None,
                    'images': list,
                    'results': [                     # List of searches results
                        {
                            'title': str,            # Title of the webpage
                            'url': str,              # URL of the result
                            'content': str,          # Summary/snippet of
                                                        content
                            'score': float,          # Relevance score
                            'raw_content': str|None  # Full page content if
                                                        available
                        },
                        ...
                    ]
                }
    """
    tavily_async_client = AsyncTavilyClient()
    search_tasks = []
    for query in search_queries:
        search_tasks.append(
            tavily_async_client.search(
                query,
                max_results=5,
                include_raw_content=True,
                topic="general",
            ),
        )

    # Execute all searches concurrently
    search_docs = await asyncio.gather(*search_tasks)

    return search_docs


async def arxiv_search_async(
    search_queries: List[str],
    load_max_docs: int = 5,
    get_full_documents: bool = True,
    load_all_available_meta: bool = True,
) -> List[dict]:
    """
    Performs concurrent searches on arXiv using the ArxivRetriever.

    Args:
        search_queries (List[str]): List of searches queries or article IDs
        load_max_docs (int, optional): Maximum number of documents to return
        per query. Default is 5.
        get_full_documents (bool, optional): Whether to fetch full text of
         documents. Default is True.
        load_all_available_meta (bool, optional): Whether to load all
        available metadata. Default is True.

    Returns:
        List[dict]: List of searches responses from arXiv, one per query.
        Each response has format:
        {
            'query': str,                    # The original searches query
            'follow_up_questions': None,
            'answer': None,
            'images': [],
            'results': [                     # List of searches results
                {
                    'title': str,            # Title of the paper
                    'url': str,              # URL (Entry ID) of the paper
                    'content': str,          # Formatted summary with metadata
                    'score': float,          # Relevance score (approximated)
                    'raw_content': str|None  # Full paper content if available
                },
                ...
            ]
        }
    """

    async def process_single_query(query: str) -> dict:
        """Process a single arXiv searches query.

        Args:
            query (str): The searches query to process.

        Returns:
            dict: The searches response for the query.
        """
        try:
            # Create retriever for each query
            retriever = ArxivRetriever(
                load_max_docs=load_max_docs,
                get_full_documents=get_full_documents,
                load_all_available_meta=load_all_available_meta,
            )

            # Run the synchronous retriever in a thread pool
            loop = asyncio.get_event_loop()
            docs = await loop.run_in_executor(
                None,
                lambda: retriever.invoke(query),
            )

            results = []
            # Assign decreasing scores based on the order
            base_score = 1.0
            score_decrement = 1.0 / (len(docs) + 1) if docs else 0

            for i, doc in enumerate(docs):
                # Extract metadata
                metadata = doc.metadata

                # Use entry_id as the URL (this is the actual arxiv link)
                url = metadata.get("entry_id", "")

                # Format content with all useful metadata
                content_parts = []

                # Primary information
                if "Summary" in metadata:
                    content_parts.append(f"Summary: {metadata['Summary']}")

                if "Authors" in metadata:
                    content_parts.append(f"Authors: {metadata['Authors']}")

                # Add publication information
                published = metadata.get("Published")
                published_str = (
                    published.isoformat()
                    if hasattr(published, "isoformat")
                    else str(published) if published else ""
                )
                if published_str:
                    content_parts.append(f"Published: {published_str}")

                # Add additional metadata if available
                if "primary_category" in metadata:
                    content_parts.append(
                        f"Primary Category: {metadata['primary_category']}",
                    )

                if "categories" in metadata and metadata["categories"]:
                    content_parts.append(
                        f"Categories: {', '.join(metadata['categories'])}",
                    )

                if "comment" in metadata and metadata["comment"]:
                    content_parts.append(f"Comment: {metadata['comment']}")

                if "journal_ref" in metadata and metadata["journal_ref"]:
                    content_parts.append(
                        f"Journal Reference: {metadata['journal_ref']}",
                    )

                if "doi" in metadata and metadata["doi"]:
                    content_parts.append(f"DOI: {metadata['doi']}")

                # Get PDF link if available in the links
                pdf_link = ""
                if "links" in metadata and metadata["links"]:
                    for link in metadata["links"]:
                        if "pdf" in link:
                            pdf_link = link
                            content_parts.append(f"PDF: {pdf_link}")
                            break

                # Join all content parts with newlines
                content = "\n".join(content_parts)

                result = {
                    "title": metadata.get("Title", ""),
                    "url": url,  # Using entry_id as the URL
                    "content": content,
                    "score": base_score - (i * score_decrement),
                    "raw_content": (
                        doc.page_content if get_full_documents else None
                    ),
                }
                results.append(result)

            return {
                "query": query,
                "follow_up_questions": None,
                "answer": None,
                "images": [],
                "results": results,
            }
        except Exception as e:
            # Handle exceptions gracefully
            print(f"Error processing arXiv query '{query}': {str(e)}")
            return {
                "query": query,
                "follow_up_questions": None,
                "answer": None,
                "images": [],
                "results": [],
                "error": str(e),
            }

    # Process queries sequentially with delay to respect arXiv
    # rate limit (1 request per 3 seconds)
    search_docs = []
    for i, query in enumerate(search_queries):
        try:
            # Add delay between requests (3 seconds per ArXiv's rate limit)
            if i > 0:  # Don't delay the first request
                await asyncio.sleep(3.0)

            result = await process_single_query(query)
            search_docs.append(result)
        except Exception as e:
            # Handle exceptions gracefully
            print(f"Error processing arXiv query '{query}': {str(e)}")
            search_docs.append(
                {
                    "query": query,
                    "follow_up_questions": None,
                    "answer": None,
                    "images": [],
                    "results": [],
                    "error": str(e),
                },
            )

            # Add additional delay if we hit a rate limit error
            if "429" in str(e) or "Too Many Requests" in str(e):
                print("ArXiv rate limit exceeded. Adding additional delay...")
                await asyncio.sleep(
                    5.0,
                )  # Add a longer delay if we hit a rate limit

    return search_docs


async def duckduckgo_search(search_queries: List[str]) -> List[dict]:
    """Perform searches using DuckDuckGo

    Args:
        search_queries (List[str]): List of searches queries to process

    Returns:
        List[dict]: List of searches results
    """

    async def process_single_query(query: str) -> dict:
        """Process a single DuckDuckGo searches query.

        Args:
            query (str): The searches query to process.

        Returns:
            dict: The searches response for the query.
        """
        # Execute synchronous searches in the event loop's thread pool
        loop = asyncio.get_event_loop()

        def perform_search() -> dict:
            """Perform the actual DuckDuckGo searches.

            Returns:
                dict: The formatted searches results.
            """
            results = []
            with DDGS() as ddgs:
                ddg_results = list(ddgs.text(query, max_results=5))

                # Format results
                for i, result in enumerate(ddg_results):
                    results.append(
                        {
                            "title": result.get("title", ""),
                            "url": result.get("link", ""),
                            "content": result.get("body", ""),
                            "score": 1.0
                            - (i * 0.1),  # Simple scoring mechanism
                            "raw_content": result.get("body", ""),
                        },
                    )
            return {
                "query": query,
                "follow_up_questions": None,
                "answer": None,
                "images": [],
                "results": results,
            }

        return await loop.run_in_executor(None, perform_search)

    # Execute all queries concurrently
    tasks = [process_single_query(query) for query in search_queries]
    search_docs = await asyncio.gather(*tasks)

    return search_docs


async def select_and_execute_search(
    search_api: SearchAPI,
    query_list: list[str],
    params_to_pass: Dict[str, Any],
) -> str:
    """Select and execute the appropriate searches API.

    Args:
        search_api (SearchAPI): Name of the searches API to use
        query_list (list[str]): List of searches queries to execute
        params_to_pass (Dict[str, Any]): Parameters to pass to the searches API

    Returns:
        str: Formatted string containing searches results

    Raises:
        ValueError: If an unsupported searches API is specified
    """
    if search_api == SearchAPI.TAVILY:
        search_results = await tavily_search_async(
            query_list,
            **params_to_pass,
        )
        return deduplicate_and_format_sources(
            search_results,
            max_tokens_per_source=4000,
            include_raw_content=False,
        )
    elif search_api == "arxiv":
        search_results = await arxiv_search_async(query_list, **params_to_pass)
        return deduplicate_and_format_sources(
            search_results,
            max_tokens_per_source=4000,
        )
    elif search_api == "duckduckgo":
        search_results = await duckduckgo_search(query_list)
        return deduplicate_and_format_sources(
            search_results,
            max_tokens_per_source=4000,
        )
    else:
        raise ValueError(f"Unsupported searches API: {search_api}")
