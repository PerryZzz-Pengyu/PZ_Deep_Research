from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

import jwt


class AuthenticationError(Exception):
    def __init__(self, message: str, *, status_code: int = 401) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class RequestIdentity:
    anonymous_id: Optional[str]
    user_id: Optional[str]

    @property
    def is_authenticated(self) -> bool:
        return self.user_id is not None

    @property
    def owner_kwargs(self) -> dict[str, Optional[str]]:
        if self.user_id:
            return {"anonymous_id": None, "user_id": self.user_id}
        return {"anonymous_id": self.anonymous_id, "user_id": None}


class ClerkAuthenticator:
    def __init__(
        self,
        *,
        jwt_key: str = "",
        authorized_parties: tuple[str, ...] = (),
        clock_skew_seconds: int = 5,
    ) -> None:
        self.jwt_key = jwt_key.replace("\\n", "\n").strip()
        self.authorized_parties = tuple(
            origin.rstrip("/") for origin in authorized_parties if origin
        )
        self.clock_skew_seconds = max(0, clock_skew_seconds)

    @property
    def enabled(self) -> bool:
        return bool(self.jwt_key)

    @staticmethod
    def _validate_visitor_id(visitor_id: str | None) -> Optional[str]:
        if not visitor_id:
            return None
        try:
            return str(UUID(visitor_id))
        except ValueError as exc:
            raise AuthenticationError("访客标识无效", status_code=400) from exc

    @staticmethod
    def _bearer_token(authorization: str | None) -> Optional[str]:
        if not authorization:
            return None
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            raise AuthenticationError("登录状态无效，请重新登录")
        return token.strip()

    def authenticate(
        self,
        *,
        authorization: str | None,
        visitor_id: str | None,
    ) -> RequestIdentity:
        anonymous_id = self._validate_visitor_id(visitor_id)
        token = self._bearer_token(authorization)
        if not token:
            if not anonymous_id:
                raise AuthenticationError("缺少访客标识", status_code=400)
            return RequestIdentity(anonymous_id=anonymous_id, user_id=None)
        if not self.enabled:
            raise AuthenticationError("登录服务暂时不可用", status_code=503)

        try:
            claims = jwt.decode(
                token,
                self.jwt_key,
                algorithms=["RS256"],
                options={
                    "require": ["exp", "nbf", "sub"],
                    "verify_aud": False,
                },
                leeway=self.clock_skew_seconds,
            )
        except jwt.PyJWTError as exc:
            raise AuthenticationError("登录状态已失效，请重新登录") from exc

        authorized_party = claims.get("azp")
        if self.authorized_parties:
            if (
                not isinstance(authorized_party, str)
                or authorized_party.rstrip("/") not in self.authorized_parties
            ):
                raise AuthenticationError("登录来源无效，请重新登录")
        if claims.get("sts") == "pending":
            raise AuthenticationError("账号尚未完成注册")

        user_id = claims.get("sub")
        if not isinstance(user_id, str) or not user_id:
            raise AuthenticationError("登录状态缺少用户标识")
        return RequestIdentity(anonymous_id=anonymous_id, user_id=user_id)
