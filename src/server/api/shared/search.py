"""
Shared search business logic (v1 + v2).
"""

from typing import Optional

from ...models.response import APIResponse, SearchResponse
from ...services.search_service import SearchService
from ...utils.converters import search_result_to_response


def do_search(
    service: SearchService,
    query: str,
    user_id: Optional[str],
    agent_id: Optional[str],
    run_id: Optional[str],
    filters: Optional[dict],
    limit: int,
):
    results = service.search_memories(
        query=query,
        user_id=user_id,
        agent_id=agent_id,
        run_id=run_id,
        filters=filters,
        limit=limit,
    )
    search_results = [
        search_result_to_response(r) for r in results.get("results", [])
    ]
    response_data = SearchResponse(
        results=search_results,
        total=len(search_results),
        query=query,
    )
    return APIResponse(
        success=True,
        data=response_data.model_dump(mode='json'),
        message="Search completed successfully",
    )
