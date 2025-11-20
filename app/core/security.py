"""
Módulo de seguridad - AxFiiS
Funciones de seguridad, JWT, hashing de passwords con bcrypt
"""
import hashlib
import secrets
import re
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from passlib.context import CryptContext
from jose import JWTError, jwt
from app.core.config import settings
from app.core.timezone import get_mexico_time_naive


pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=10 
)


class SecurityUtils:
    """
    Utilidades de seguridad básicas
    """
    
    @staticmethod
    def generate_salt() -> str:
        """
        Genera salt único
        
        Returns:
            Salt de 32 caracteres hexadecimales
        """
        return secrets.token_hex(16)  # 32 caracteres
    
    @staticmethod
    def generate_api_key() -> str:
        """
        Genera API key única para tenant
        
        Returns:
            API key de 64 caracteres hexadecimales
        """
        return secrets.token_hex(32)  # 64 caracteres
    
    @staticmethod
    def generate_password_salt() -> str:
        """
        Genera salt único para password de usuario
        
        Returns:
            Salt de 16 caracteres hexadecimales
        """
        return secrets.token_hex(8)  # 16 caracteres
    
    @staticmethod
    def hash_password_bcrypt(password: str) -> str:
        """
        Genera hash del password usando bcrypt (recomendado para usuarios)
        
        Args:
            password: Password en texto plano
            
        Returns:
            Hash bcrypt (incluye salt automáticamente)
        """
        return pwd_context.hash(password)
    
    @staticmethod
    def verify_password_bcrypt(plain_password: str, hashed_password: str) -> bool:
        """
        Verifica password contra hash bcrypt
        
        Args:
            plain_password: Password en texto plano
            hashed_password: Hash bcrypt almacenado
            
        Returns:
            True si el password coincide
        """
        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    def hash_password(password: str, salt: str) -> str:
        """
        Genera hash del password con salt usando SHA256 (legacy)
        Mantener por compatibilidad con sistema existente
        
        Args:
            password: Password en texto plano
            salt: Salt único
            
        Returns:
            Hash SHA256 de 64 caracteres
        """
        combined = f"{password}{salt}"
        return hashlib.sha256(combined.encode('utf-8')).hexdigest()
    
    @staticmethod
    def verify_password_sha256(plain_password: str, hashed_password: str, salt: str) -> bool:
        """
        Verifica password contra hash SHA256 + salt (legacy)
        
        Args:
            plain_password: Password en texto plano
            hashed_password: Hash almacenado
            salt: Salt usado en el hash
            
        Returns:
            True si el password coincide
        """
        computed_hash = SecurityUtils.hash_password(plain_password, salt)
        return computed_hash == hashed_password
    
    @staticmethod
    def generate_invitation_token(email: str, tenant_id: str) -> str:
        """
        Genera token único para invitaciones
        
        Args:
            email: Email del invitado
            tenant_id: ID del tenant
            
        Returns:
            Token de 64 caracteres
        """
        timestamp = str(int(datetime.utcnow().timestamp()))
        combined = f"{email}{tenant_id}{timestamp}"
        return hashlib.sha256(combined.encode('utf-8')).hexdigest()
    
    @staticmethod
    def hash_session_token(token: str) -> str:
        """
        Genera hash del token de sesión para almacenar en BD
        
        Args:
            token: Token JWT original
            
        Returns:
            Hash SHA256 de 64 caracteres
        """
        return hashlib.sha256(token.encode('utf-8')).hexdigest()
    
    @staticmethod
    def hash_webhook_secret(secret: str) -> str:
        """
        Genera hash del webhook secret para almacenar en BD
        
        Args:
            secret: Webhook secret original
            
        Returns:
            Hash SHA256 de 64 caracteres
        """
        return hashlib.sha256(secret.encode('utf-8')).hexdigest()
    
    @staticmethod
    def validate_password_strength(password: str) -> tuple[bool, str]:
        """
        Valida la fortaleza del password según políticas configuradas
        
        Args:
            password: Password a validar
            
        Returns:
            Tupla (es_válido, mensaje_error)
        """
        if len(password) < settings.MIN_PASSWORD_LENGTH:
            return False, f"El password debe tener al menos {settings.MIN_PASSWORD_LENGTH} caracteres"
        
        if settings.REQUIRE_UPPERCASE and not re.search(r'[A-Z]', password):
            return False, "El password debe contener al menos una mayúscula"
        
        if settings.REQUIRE_LOWERCASE and not re.search(r'[a-z]', password):
            return False, "El password debe contener al menos una minúscula"
        
        if settings.REQUIRE_NUMBERS and not re.search(r'\d', password):
            return False, "El password debe contener al menos un número"
        
        if settings.REQUIRE_SPECIAL_CHARS and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            return False, "El password debe contener al menos un carácter especial"
        
        return True, ""
    
    @staticmethod
    def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """
        Crea un JWT access token
        
        Args:
            data: Datos a incluir en el token (sub, email, tenant_id, etc)
            expires_delta: Tiempo de expiración customizado
            
        Returns:
            Token JWT codificado
        """
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access"
        })
        
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def create_refresh_token(data: Dict[str, Any]) -> str:
        """
        Crea un JWT refresh token
        
        Args:
            data: Datos a incluir en el token (normalmente solo sub)
            
        Returns:
            Token JWT codificado
        """
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh"
        })
        
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def decode_token(token: str) -> Optional[Dict[str, Any]]:
        """
        Decodifica y valida un JWT token
        
        Args:
            token: Token JWT a decodificar
            
        Returns:
            Payload del token o None si es inválido
        """
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            return payload
        except JWTError:
            return None


# Instancia global para compatibilidad
security_utils = SecurityUtils()

# Alias para compatibilidad con código existente
rfc_encryption = security_utils

# Funciones de nivel módulo para facilitar el uso
hash_password = security_utils.hash_password_bcrypt
verify_password = security_utils.verify_password_bcrypt
create_access_token = security_utils.create_access_token
create_refresh_token = security_utils.create_refresh_token
decode_token = security_utils.decode_token
validate_password_strength = security_utils.validate_password_strength