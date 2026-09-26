"""FastAPI dependencies shared by the SaaS routes."""

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from engine.service import Engine

from .accounts import CurrentUser, ensure_user
from .auth import InvalidToken, TokenVerifier
from .payments import PaymentProvider

_bearer = HTTPBearer(auto_error=False)


def current_user(request: Request, creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> CurrentUser:
    if creds is None:
        raise HTTPException(401, "Please log in.", headers={"WWW-Authenticate": "Bearer"})
    verifier: TokenVerifier = request.app.state.verifier
    try:
        principal = verifier.verify(creds.credentials)
    except InvalidToken:
        raise HTTPException(401, "Your session has expired — please log in again.",
                            headers={"WWW-Authenticate": "Bearer"})
    return ensure_user(principal)


def engine(request: Request) -> Engine:
    return request.app.state.engine


def payment_provider(request: Request) -> PaymentProvider:
    return request.app.state.payments
