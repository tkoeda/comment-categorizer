from pydantic import BaseModel, Field


class UserCreateModel(BaseModel):
    username: str = Field(..., min_length=3, max_length=30)
    password: str = Field(..., min_length=8, max_length=40)


class OpenAIApiKeyUpdate(BaseModel):
    api_key: str = Field(..., description="Your OpenAI API key")
