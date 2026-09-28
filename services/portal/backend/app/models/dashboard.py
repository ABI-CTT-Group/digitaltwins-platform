from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class DashBoardSignInResponse(BaseModel):
    access_token: str
