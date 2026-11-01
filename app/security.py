from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import settings
from app.schemas import UserContext

security_scheme = HTTPBearer(auto_error=False)

def create_access_token(
    user_id: UUID,
    tenant_id: UUID,
    roles: List[str],
    clearance: int,
    email: Optional[str] = None,
    expires_delta: Optional[timedelta] = None
) -> str:
    now = datetime.now(timezone.utc)
    if expires_delta is not None:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    
    payload = {
        "sub": str(user_id),
        "user_id": str(user_id),
        "tenant_id": str(tenant_id),
        "roles": roles,
        "clearance": clearance,
        "email": email or "",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp())
    }
    
    encoded_jwt = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> UserContext:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["sub", "user_id", "tenant_id", "roles", "clearance", "iat", "exp"]},
        )
        user_id_str = payload.get("user_id") or payload.get("sub")
        tenant_id_str = payload.get("tenant_id")
        roles = payload["roles"]
        clearance = payload["clearance"]

        if any(type(payload[claim]) is not int for claim in ("iat", "exp")):
            raise ValueError("JWT numeric dates must be integers")
        
        if not user_id_str or not tenant_id_str or payload["sub"] != user_id_str:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token is missing required tenant or user claims",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return UserContext(
            user_id=user_id_str,
            tenant_id=tenant_id_str,
            roles=roles,
            clearance=clearance
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token signature has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except (jwt.InvalidTokenError, ValueError, TypeError, OverflowError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

def get_current_user_context(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)
) -> UserContext:
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token required for authorization",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return decode_access_token(credentials.credentials)
