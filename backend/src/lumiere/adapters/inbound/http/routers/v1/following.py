from datetime import UTC, datetime

from fastapi import APIRouter, Request, Response

from lumiere.adapters.inbound.http.context import (
    COOKIE_NAME,
    check_origin,
    quota_ip_key,
)
from lumiere.adapters.inbound.http.deps import HttpServices
from lumiere.adapters.inbound.http.schemas.following import (
    FollowingResponse,
    FollowPersonRequest,
)
from lumiere.domain.following import FollowingSnapshot, PersonIdentity


def following_router(services: HttpServices) -> APIRouter:
    router = APIRouter()

    @router.get('/api/v1/following', operation_id='listFollowing', response_model=FollowingResponse, responses={500: {'description': 'Following failed'}})
    async def list_following(request: Request, response: Response) -> FollowingSnapshot:
        context = await services.guests.resolve(request.cookies.get(COOKIE_NAME), quota_ip_key(request, services), datetime.now(UTC))
        result = await services.list_following.execute(context)
        response.headers['Cache-Control'] = 'no-store'
        return result

    @router.post('/api/v1/following', operation_id='followPerson', response_model=FollowingResponse, responses={500: {'description': 'Following failed'}})
    async def follow_person(body: FollowPersonRequest, request: Request, response: Response) -> FollowingSnapshot:
        check_origin(request, services)
        context = await services.guests.resolve(request.cookies.get(COOKIE_NAME), quota_ip_key(request, services), datetime.now(UTC))
        result = await services.follow_person.execute(PersonIdentity(body.provider, body.provider_id), context)
        response.headers['Cache-Control'] = 'no-store'
        return result

    @router.delete('/api/v1/following', operation_id='unfollowPerson', status_code=204, response_class=Response, responses={500: {'description': 'Following failed'}})
    async def unfollow_person(body: FollowPersonRequest, request: Request) -> Response:
        check_origin(request, services)
        context = await services.guests.resolve(request.cookies.get(COOKIE_NAME), quota_ip_key(request, services), datetime.now(UTC))
        await services.unfollow_person.execute(PersonIdentity(body.provider, body.provider_id), context)
        return Response(status_code=204, headers={'Cache-Control': 'no-store'})

    return router
