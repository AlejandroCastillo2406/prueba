"""
Maneja todas las operaciones de cifrado y hashing del sistema
"""
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import secrets
import hashlib
from app.interfaces.encryption_service_interface import IEncryptionService
from app.models.tenant import Tenant
from app.models.usuario import Usuario
from app.models.proveedor import Proveedor
from app.core.timezone import get_mexico_time_naive


class EncryptionService(IEncryptionService):
    """
    Servicio centralizado para operaciones de cifrado
    """
    
    def __init__(self):
        """
        Servicio centralizado para operaciones de cifrado
        """
        pass
    
    
    def create_tenant(self, session: Session, rfc: str, nombre_comercial: str, razon_social: str) -> Tenant:
        """
        Crea un nuevo tenant con cifrado automático
        
        Args:
            session: Sesión de base de datos
            rfc: RFC de la empresa
            nombre_comercial: Nombre comercial
            razon_social: Razón social
            
        Returns:
            Tenant creado
        """
        tenant_data = {
            "rfc": rfc.upper().strip(),
            "nombre_comercial": nombre_comercial,
            "razon_social": razon_social,
            "api_key": secrets.token_hex(32),  # 64 caracteres hexadecimales
            "plan_tipo": "starter",
            "rfcs_limite": 500,
            "usuarios_limite": 1
        }
        
        tenant = Tenant(**tenant_data)
        session.add(tenant)
        session.commit()
        session.refresh(tenant)
        
        return tenant
    
    
    def get_tenant_by_api_key(self, session: Session, api_key: str) -> Optional[Tenant]:
        """
        Obtiene un tenant por su API key
        
        Args:
            session: Sesión de base de datos
            api_key: API key del tenant
            
        Returns:
            Tenant si existe, None si no
        """
        return session.query(Tenant).filter(
            Tenant.api_key == api_key,
            Tenant.activo == True
        ).first()
    
    
    def authenticate_user(self, email: str, password: str, tenant_id: str) -> Optional[Usuario]:
        """
        Autentica un usuario
        
        Args:
            email: Email del usuario
            password: Password en texto plano
            tenant_id: ID del tenant
            
        Returns:
            Usuario si la autenticación es exitosa, None si no
        """
        usuario = self.db.query(Usuario).filter(
            Usuario.email == email.lower().strip(),
            Usuario.tenant_id == tenant_id,
            Usuario.activo == True,
            Usuario.estado == "active"
        ).first()
        
        if not usuario:
            return None
        
        # Verificar password
        password_hash = hashlib.sha256(f"{password}{usuario.password_salt}".encode()).hexdigest()
        if password_hash != usuario.password_hash:
            return None
        
        return usuario
    
    def get_user_by_email(self, email: str, tenant_id: str) -> Optional[Usuario]:
        """
        Obtiene un usuario por email y tenant
        
        Args:
            email: Email del usuario
            tenant_id: ID del tenant
            
        Returns:
            Usuario si existe, None si no
        """
        return self.db.query(Usuario).filter(
            Usuario.email == email.lower().strip(),
            Usuario.tenant_id == tenant_id,
            Usuario.activo == True
        ).first()
    
# Instancia global del servicio
encryption_service = EncryptionService()
