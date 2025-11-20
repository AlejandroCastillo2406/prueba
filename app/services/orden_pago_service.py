"""
Servicio para procesamiento de órdenes de pago de excedentes
"""
from typing import Dict, Any, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from loguru import logger

from app.repositories.orden_pago_repository import OrdenPagoRepository
from app.factories.service_factory import service_factory


class OrdenPagoService:
    """Servicio para gestionar órdenes de pago de excedentes"""
    
    def __init__(self):
        self.orden_repository = OrdenPagoRepository()
    
    def procesar_pago_exitoso(
        self,
        session: Session,
        checkout_session_id: str,
        payment_intent_id: Optional[str] = None,
        customer_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Procesa un pago exitoso (checkout.session.completed)
        
        Args:
            session: Sesión de base de datos
            checkout_session_id: ID de la sesión de checkout de Stripe
            payment_intent_id: ID del payment intent (opcional)
            customer_id: ID del customer en Stripe (opcional)
            
        Returns:
            Diccionario con resultado del procesamiento
        """
        try:
            # Obtener orden por checkout session ID
            orden = self.orden_repository.obtener_por_stripe_checkout(
                session, checkout_session_id
            )
            
            if not orden:
                logger.warning(f"Orden no encontrada para checkout session {checkout_session_id}")
                return {
                    "success": False,
                    "message": "orden_no_encontrada"
                }
            
            # Marcar como pagada
            self.orden_repository.marcar_como_pagada(session, orden.id)
            
            # Actualizar info de Stripe
            self.orden_repository.actualizar_stripe_info(
                session=session,
                orden_id=orden.id,
                checkout_session_id=checkout_session_id,
                payment_intent_id=payment_intent_id,
                customer_id=customer_id
            )
            
            session.commit()
            
            logger.info(f"Orden {orden.id} marcada como pagada")
            
            # Ejecutar conciliación de los RFCs pagados
            try:
                conciliacion_service = service_factory.create_conciliacion_service()
                
                # Crear conciliación para los RFCs pagados
                historial_id = conciliacion_service.conciliar_rfcs_especificos(
                    session=session,
                    tenant_id=orden.tenant_id,
                    rfcs=orden.rfcs,
                    tipo_conciliacion="Excedentes - Pago"
                )
                
                # Marcar orden como conciliada
                self.orden_repository.marcar_como_conciliada(session, orden.id, historial_id)
                session.commit()
                
                logger.info(f"Conciliación automática completada para orden {orden.id} - historial {historial_id}")
                
                return {
                    "success": True,
                    "orden_id": str(orden.id),
                    "historial_id": str(historial_id),
                    "message": "Pago procesado y conciliación completada"
                }
                
            except Exception as e:
                logger.error(f"Error en conciliación automática: {e}")
                # No fallar el procesamiento si la conciliación falla
                # La orden ya está marcada como pagada
                return {
                    "success": True,
                    "orden_id": str(orden.id),
                    "warning": "Pago procesado pero conciliación falló",
                    "error": str(e)
                }
            
        except Exception as e:
            logger.error(f"Error procesando pago exitoso: {e}")
            session.rollback()
            raise
    
    def procesar_pago_fallido(
        self,
        session: Session,
        payment_intent_id: str
    ) -> Dict[str, Any]:
        """
        Procesa un pago fallido (payment_intent.payment_failed)
        
        Args:
            session: Sesión de base de datos
            payment_intent_id: ID del payment intent de Stripe
            
        Returns:
            Diccionario con resultado del procesamiento
        """
        try:
            orden = self.orden_repository.obtener_por_payment_intent(
                session, payment_intent_id
            )
            
            if orden:
                orden.estado = "fallido"
                session.commit()
                logger.info(f"Orden {orden.id} marcada como fallida")
                return {
                    "success": True,
                    "orden_id": str(orden.id),
                    "message": "Orden marcada como fallida"
                }
            else:
                logger.warning(f"Orden no encontrada para payment intent {payment_intent_id}")
                return {
                    "success": False,
                    "message": "orden_no_encontrada"
                }
            
        except Exception as e:
            logger.error(f"Error procesando pago fallido: {e}")
            session.rollback()
            raise

