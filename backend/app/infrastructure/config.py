from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    env: str = "dev"
    aws_profile: str = "dev"
    aws_region: str = "ap-northeast-1"
    
    dsql_endpoint: str
    dynamo_table: str

    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()
