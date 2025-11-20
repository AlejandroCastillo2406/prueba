"""
Servicio para integración con Stripe
"""
import stripe
from typing import Dict, Any
from uuid import UUID
from loguru import logger

from app.core.config import settings


class StripeService:
    """Servicio para gestionar pagos con Stripe"""
    
    def __init__(self):
        stripe.api_key = settings.STRIPE_SECRET_KEY
    
    def crear_checkout_session(
        self,
        orden_id: UUID,
        cantidad_rfcs: int,
        monto_total: float,
        tenant_email: str = None
    ) -> Dict[str, Any]:
        """
        Crea una sesión de checkout de Stripe
        
        Args:
            orden_id: ID de la orden de pago
            cantidad_rfcs: Número de RFCs a pagar
            monto_total: Monto total en MXN/USD
            tenant_email: Email del tenant (opcional)
            
        Returns:
            Diccionario con session_id y url
        """
        try:
            # Crear sesión de checkout usando producto fijo de Stripe
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price': settings.STRIPE_PRICE_ID,  
                    'quantity': cantidad_rfcs,
                }],
                mode='payment',
                success_url=f'{settings.STRIPE_SUCCESS_URL}?orden_id={orden_id}',
                cancel_url=f'{settings.STRIPE_CANCEL_URL}?orden_id={orden_id}',
                client_reference_id=str(orden_id),
                metadata={
                    'orden_id': str(orden_id),
                    'cantidad_rfcs': cantidad_rfcs,
                    'tipo': 'excedentes'
                },
                customer_email=tenant_email if tenant_email else None,
            )
            
            logger.info(f"Checkout session creada: {session.id} para orden {orden_id}")
            
            return {
                'session_id': session.id,
                'url': session.url,
                'payment_intent': session.payment_intent
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Error creando checkout session: {e}")
            raise Exception(f"Error al crear sesión de pago: {str(e)}")
    
    def obtener_session(self, session_id: str) -> Dict[str, Any]:
        """
        Obtiene información de una sesión de checkout
        
        Args:
            session_id: ID de la sesión
            
        Returns:
            Información de la sesión
        """
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            return {
                'id': session.id,
                'payment_status': session.payment_status,
                'payment_intent': session.payment_intent,
                'customer': session.customer,
                'amount_total': session.amount_total / 100 if session.amount_total else 0,
                'metadata': session.metadata
            }
        except stripe.error.StripeError as e:
            logger.error(f"Error obteniendo session {session_id}: {e}")
            raise Exception(f"Error al obtener información de pago: {str(e)}")
    
    def obtener_payment_intent(self, payment_intent_id: str) -> Dict[str, Any]:
        """
        Obtiene información de un payment intent
        
        Args:
            payment_intent_id: ID del payment intent
            
        Returns:
            Información del payment intent
        """
        try:
            payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            return {
                'id': payment_intent.id,
                'status': payment_intent.status,
                'amount': payment_intent.amount / 100 if payment_intent.amount else 0,
                'currency': payment_intent.currency,
                'customer': payment_intent.customer,
                'metadata': payment_intent.metadata
            }
        except stripe.error.StripeError as e:
            logger.error(f"Error obteniendo payment intent {payment_intent_id}: {e}")
            raise Exception(f"Error al obtener información de pago: {str(e)}")
    
    def verificar_webhook_signature(self, payload: bytes, sig_header: str) -> Any:
        """
        Verifica la firma del webhook de Stripe
        
        Args:
            payload: Cuerpo del request
            sig_header: Header de firma de Stripe
            
        Returns:
            Evento verificado
        """
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
            return event
        except ValueError as e:
            logger.error(f"Payload inválido: {e}")
            raise ValueError("Payload inválido")
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Firma inválida: {e}")
            raise ValueError("Firma inválida")

