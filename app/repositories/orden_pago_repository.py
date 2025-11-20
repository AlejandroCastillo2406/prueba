"""
Repositorio para órdenes de pago de excedentes
"""
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from loguru import logger
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import array

from app.models.orden_pago_excedente import OrdenPagoExcedente
from app.repositories.base_repository import BaseRepository


class OrdenPagoRepository(BaseRepository):
    """Repositorio para gestión de órdenes de pago"""
    
    def __init__(self):
        super().__init__(OrdenPagoExcedente)
    
    def crear_orden(
        self,
        session: Session,
        tenant_id: UUID,
        rfcs: List[str],
        monto_total: float,
        precio_unitario: float
    ) -> OrdenPagoExcedente:
        """Crea una nueva orden de pago"""
        try:
            orden = OrdenPagoExcedente(
                tenant_id=tenant_id,
                rfcs=rfcs,
                cantidad_rfcs=len(rfcs),
                monto_total=monto_total,
                precio_unitario=precio_unitario,
                estado="pendiente"
            )
            session.add(orden)
            session.flush()
            return orden
        except Exception as e:
            logger.error(f"Error creando orden de pago: {e}")
            raise
    
    def obtener_por_id(
        self,
        session: Session,
        orden_id: UUID,
        tenant_id: UUID = None
    ) -> Optional[OrdenPagoExcedente]:
        """Obtiene una orden por ID (opcionalmente filtrando por tenant)"""
        try:
            query = session.query(OrdenPagoExcedente).filter(
                OrdenPagoExcedente.id == orden_id
            )
            if tenant_id:
                query = query.filter(OrdenPagoExcedente.tenant_id == tenant_id)
            return query.first()
        except Exception as e:
            logger.error(f"Error obteniendo orden {orden_id}: {e}")
            return None
    
    def obtener_por_stripe_checkout(
        self,
        session: Session,
        checkout_session_id: str
    ) -> Optional[OrdenPagoExcedente]:
        """Obtiene una orden por su checkout session ID de Stripe"""
        try:
            return session.query(OrdenPagoExcedente).filter(
                OrdenPagoExcedente.stripe_checkout_session_id == checkout_session_id
            ).first()
        except Exception as e:
            logger.error(f"Error obteniendo orden por checkout {checkout_session_id}: {e}")
            return None
    
    def obtener_por_payment_intent(
        self,
        session: Session,
        payment_intent_id: str
    ) -> Optional[OrdenPagoExcedente]:
        """Obtiene una orden por su payment intent ID de Stripe"""
        try:
            return session.query(OrdenPagoExcedente).filter(
                OrdenPagoExcedente.stripe_payment_intent_id == payment_intent_id
            ).first()
        except Exception as e:
            logger.error(f"Error obteniendo orden por payment intent {payment_intent_id}: {e}")
            return None
    
    def actualizar_stripe_info(
        self,
        session: Session,
        orden_id: UUID,
        checkout_session_id: str = None,
        payment_intent_id: str = None,
        customer_id: str = None
    ) -> bool:
        """Actualiza información de Stripe en una orden"""
        try:
            orden = session.query(OrdenPagoExcedente).filter(
                OrdenPagoExcedente.id == orden_id
            ).first()
            
            if not orden:
                return False
            
            if checkout_session_id:
                orden.stripe_checkout_session_id = checkout_session_id
            if payment_intent_id:
                orden.stripe_payment_intent_id = payment_intent_id
            if customer_id:
                orden.stripe_customer_id = customer_id
            
            session.flush()
            return True
        except Exception as e:
            logger.error(f"Error actualizando info de Stripe: {e}")
            return False
    
    def marcar_como_pagada(
        self,
        session: Session,
        orden_id: UUID
    ) -> bool:
        """Marca una orden como pagada"""
        try:
            orden = session.query(OrdenPagoExcedente).filter(
                OrdenPagoExcedente.id == orden_id
            ).first()
            
            if not orden:
                return False
            
            orden.estado = "pagado"
            orden.pagado_at = datetime.utcnow()
            session.flush()
            return True
        except Exception as e:
            logger.error(f"Error marcando orden {orden_id} como pagada: {e}")
            return False
    
    def marcar_como_conciliada(
        self,
        session: Session,
        orden_id: UUID,
        conciliacion_id: UUID
    ) -> bool:
        """Marca una orden como conciliada"""
        try:
            orden = session.query(OrdenPagoExcedente).filter(
                OrdenPagoExcedente.id == orden_id
            ).first()
            
            if not orden:
                return False
            
            orden.conciliado = True
            orden.conciliacion_id = conciliacion_id
            session.flush()
            return True
        except Exception as e:
            logger.error(f"Error marcando orden {orden_id} como conciliada: {e}")
            return False
    
    def obtener_rfcs_pagados(
        self,
        session: Session,
        tenant_id: UUID
    ) -> set:
        """
        Obtiene set de RFCs que ya han sido pagados 
        Retorna un set para búsqueda O(1) en lugar de lista
        """
        try:
            
            # Obtener RFCs pagados
            rfcs_pagados = session.query(
                func.unnest(OrdenPagoExcedente.rfcs)
            ).filter(
                and_(
                    OrdenPagoExcedente.tenant_id == tenant_id,
                    OrdenPagoExcedente.estado == "pagado"
                )
            ).distinct().all()
            
            # Convertir a set para búsqueda O(1)
            return {rfc[0] for rfc in rfcs_pagados}
        except Exception as e:
            logger.error(f"Error obteniendo RFCs pagados: {e}")
            return set()
    
    def obtener_ordenes_pendientes_conciliar(
        self,
        session: Session,
        tenant_id: UUID = None
    ) -> List[OrdenPagoExcedente]:
        """Obtiene órdenes pagadas pero no conciliadas"""
        try:
            query = session.query(OrdenPagoExcedente).filter(
                and_(
                    OrdenPagoExcedente.estado == "pagado",
                    OrdenPagoExcedente.conciliado == False
                )
            )
            
            if tenant_id:
                query = query.filter(OrdenPagoExcedente.tenant_id == tenant_id)
            
            return query.all()
        except Exception as e:
            logger.error(f"Error obteniendo órdenes pendientes de conciliar: {e}")
            return []

