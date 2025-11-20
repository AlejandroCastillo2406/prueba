"""
Configuración de la aplicación
Carga todas las variables de entorno y las expone de forma segura
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List
from functools import lru_cache


class Settings(BaseSettings):
    """Configuración de la aplicación usando Pydantic Settings"""
    
    # Aplicación
    APP_NAME: str = Field(..., env="APP_NAME")
    APP_VERSION: str = Field(..., env="APP_VERSION")
    DEBUG: bool = Field(..., env="DEBUG")
    ENVIRONMENT: str = Field(..., env="ENVIRONMENT")
    
    # Servidor
    HOST: str = Field(..., env="HOST")
    PORT: int = Field(..., env="PORT")
    
    # Base de datos
    DATABASE_URL: str = Field(..., env="DATABASE_URL")
    
    # Seguridad
    SECRET_KEY: str = Field(..., env="SECRET_KEY")
    ALGORITHM: str = Field(..., env="ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(..., env="ACCESS_TOKEN_EXPIRE_MINUTES")
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, env="REFRESH_TOKEN_EXPIRE_DAYS")
    
    # Password Policy
    MIN_PASSWORD_LENGTH: int = Field(default=8, env="MIN_PASSWORD_LENGTH")
    REQUIRE_UPPERCASE: bool = Field(default=True, env="REQUIRE_UPPERCASE")
    REQUIRE_LOWERCASE: bool = Field(default=True, env="REQUIRE_LOWERCASE")
    REQUIRE_NUMBERS: bool = Field(default=True, env="REQUIRE_NUMBERS")
    REQUIRE_SPECIAL_CHARS: bool = Field(default=True, env="REQUIRE_SPECIAL_CHARS")
    
    # Rate Limiting
    MAX_LOGIN_ATTEMPTS: int = Field(default=5, env="MAX_LOGIN_ATTEMPTS")
    LOGIN_LOCKOUT_MINUTES: int = Field(default=15, env="LOGIN_LOCKOUT_MINUTES")
    
    # SAT
    SAT_LIST_URL: str = Field(..., env="SAT_LIST_URL")
    
    # DOF
    DOF_URL: str = Field(..., env="DOF_URL")

    # Logs
    LOG_LEVEL: str = Field(..., env="LOG_LEVEL")
    LOG_FILE: str = Field(..., env="LOG_FILE")
    
    # CORS
    CORS_ORIGINS: str = Field(..., env="CORS_ORIGINS")
    
    # S3 Storage
    AWS_ACCESS_KEY_ID: str = Field(..., env="AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY: str = Field(..., env="AWS_SECRET_ACCESS_KEY")
    AWS_REGION: str = Field(..., env="AWS_REGION")
    S3_BUCKET_NAME: str = Field(..., env="S3_BUCKET_NAME")
    S3_PRINCIPAL: str = Field(..., env="S3_PRINCIPAL")
    S3_TEMP: str = Field(..., env="S3_TEMP")
    S3_VERSIONS_PATH: str = Field(..., env="S3_VERSIONS_PATH")
    
    # Athena
    ATHENA_DATABASE: str = Field(..., env="ATHENA_DATABASE")
    ATHENA_TABLE: str = Field(..., env="ATHENA_TABLE")
    ATHENA_OUTPUT_LOCATION: str = Field(..., env="ATHENA_OUTPUT_LOCATION")
    ATHENA_WORKGROUP: str = Field(..., env="ATHENA_WORKGROUP")
    
    # Stripe
    STRIPE_SECRET_KEY: str = Field(..., env="STRIPE_SECRET_KEY")
    STRIPE_PUBLISHABLE_KEY: str = Field(..., env="STRIPE_PUBLISHABLE_KEY")
    STRIPE_WEBHOOK_SECRET: str = Field(..., env="STRIPE_WEBHOOK_SECRET")
    STRIPE_SUCCESS_URL: str = Field(..., env="STRIPE_SUCCESS_URL")
    STRIPE_CANCEL_URL: str = Field(..., env="STRIPE_CANCEL_URL")
    STRIPE_PRICE_ID: str = Field(..., env="STRIPE_PRICE_ID") 
    
    # SQS
    SQS_QUEUE_URL: str = Field(..., env="SQS_QUEUE_URL")
    
    # Internal API Key 
    INTERNAL_API_KEY: str = Field(..., env="INTERNAL_API_KEY")
    
    # AWS SES (Email)
    SES_SENDER_EMAIL: str = Field(..., env="SES_SENDER_EMAIL", description="Email verificado en SES para enviar correos") 
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Convierte el string de orígenes CORS en una lista"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignorar variables de entorno adicionales que no estén definidas


@lru_cache()
def get_settings() -> Settings:
    """
    Usar esta función en lugar de instanciar Settings directamente
    """
    return Settings()

# Instancia global de configuración
settings = get_settings()