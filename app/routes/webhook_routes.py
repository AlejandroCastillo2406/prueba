"""
Rutas para webhooks externos (Stripe, etc.)
"""
from fastapi import APIRouter, Request, HTTPException, status, Depends
from sqlalchemy.orm import Session
from loguru import logger

from app.core.database import get_db
from app.services.stripe_service import StripeService
from app.services.orden_pago_service import OrdenPagoService


router = APIRouter()


@router.post(
    "/stripe",
    summary="Webhook de Stripe",
    description="Recibe notificaciones de eventos de Stripe (pagos completados, etc.)"
)
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Webhook para procesar eventos de Stripe.
    
    **Eventos manejados:**
    - `checkout.session.completed`: Pago exitoso
    - `payment_intent.succeeded`: Confirmación de pago
    - `payment_intent.payment_failed`: Pago fallido
    
    **Flujo:**
    1. Verifica firma del webhook
    2. Procesa evento según tipo
    3. Actualiza orden en BD
    4. Ejecuta conciliación de RFCs pagados
    """
    try:
        # Obtener payload y firma
        payload = await request.body()
        sig_header = request.headers.get('stripe-signature')
        
        if not sig_header:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Falta header stripe-signature"
            )
        
        # Verificar firma y obtener evento
        stripe_service = StripeService()
        try:
            event = stripe_service.verificar_webhook_signature(payload, sig_header)
        except ValueError as e:
            logger.warning(f"Webhook con firma inválida: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        
        logger.info(f"Webhook recibido: {event['type']}")
        
        # Procesar según tipo de evento usando servicio
        orden_service = OrdenPagoService()
        
        if event['type'] == 'checkout.session.completed':
            # Pago completado exitosamente
            session_data = event['data']['object']
            
            resultado = orden_service.procesar_pago_exitoso(
                session=db,
                checkout_session_id=session_data['id'],
                payment_intent_id=session_data.get('payment_intent'),
                customer_id=session_data.get('customer')
            )
            
            if resultado['success']:
                return {"status": "success", "orden_id": resultado.get('orden_id')}
            else:
                return {"status": resultado['message']}
        
        elif event['type'] == 'payment_intent.payment_failed':
            # Pago fallido
            payment_intent = event['data']['object']
            
            resultado = orden_service.procesar_pago_fallido(
                session=db,
                payment_intent_id=payment_intent['id']
            )
            
            if resultado['success']:
                return {"status": "payment_failed", "orden_id": resultado.get('orden_id')}
            else:
                return {"status": resultado['message']}
        
        else:
            # Otros eventos (ignorar)
            logger.info(f"Evento {event['type']} ignorado")
            return {"status": "ignored"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error procesando webhook de Stripe: {e}")
        db.rollback()
        # No fallar el webhook, Stripe reintentará
        return {"status": "error", "message": str(e)}

