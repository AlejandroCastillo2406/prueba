"""
Servicio para manejo de mensajes SQS
"""
import json
import boto3
from typing import Dict, Any, Optional
from datetime import datetime
from loguru import logger
from botocore.exceptions import ClientError

from app.core.config import settings
from app.core.timezone import get_mexico_time_naive


class SQSService:
    """Servicio para publicar mensajes a SQS"""
    
    def __init__(self):
        """Inicializa el cliente SQS"""
        self.sqs_client = boto3.client(
            'sqs',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        self.queue_url = settings.SQS_QUEUE_URL
    
    def publish_nueva_version_sat(self, fecha_version: str, total_registros: Optional[int] = None) -> bool:
        """
        Publica un mensaje a SQS cuando se detecta una nueva versión del SAT
        
        Args:
            fecha_version: Fecha de la nueva versión del SAT (formato YYYY-MM-DD)
            total_registros: Total de registros procesados (opcional)
            
        Returns:
            True si el mensaje se publicó correctamente, False en caso contrario
        """
        try:
            logger.info(f"📤 Publicando mensaje a SQS para nueva versión SAT: {fecha_version}")
            
            # Crear mensaje
            message_body = {
                "tipo": "nueva_version_sat",
                "fecha_version": fecha_version,
                "timestamp": get_mexico_time_naive().isoformat(),
                "total_registros": total_registros,
                "accion": "ejecutar_conciliacion"
            }
            
            # Publicar mensaje a SQS
            response = self.sqs_client.send_message(
                QueueUrl=self.queue_url,
                MessageBody=json.dumps(message_body, ensure_ascii=False),
                MessageAttributes={
                    'TipoEvento': {
                        'StringValue': 'nueva_version_sat',
                        'DataType': 'String'
                    },
                    'FechaVersion': {
                        'StringValue': fecha_version,
                        'DataType': 'String'
                    }
                }
            )
            
            logger.success(f"✅ Mensaje publicado exitosamente a SQS. MessageId: {response.get('MessageId')}")
            return True
            
        except ClientError as e:
            logger.error(f"❌ Error de AWS al publicar mensaje a SQS: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Error inesperado al publicar mensaje a SQS: {e}")
            return False
    
    def publish_message(self, message_body: Dict[str, Any], message_attributes: Optional[Dict[str, Any]] = None) -> bool:
        """
        Publica un mensaje genérico a SQS
        
        Args:
            message_body: Cuerpo del mensaje (diccionario que se serializará a JSON)
            message_attributes: Atributos del mensaje (opcional)
            
        Returns:
            True si el mensaje se publicó correctamente, False en caso contrario
        """
        try:
            logger.info(f" Publicando mensaje genérico a SQS")
            
            # Serializar mensaje
            message_body_json = json.dumps(message_body, ensure_ascii=False, default=str)
            
            # Preparar atributos
            sqs_attributes = {}
            if message_attributes:
                for key, value in message_attributes.items():
                    if isinstance(value, str):
                        sqs_attributes[key] = {
                            'StringValue': value,
                            'DataType': 'String'
                        }
                    elif isinstance(value, (int, float)):
                        sqs_attributes[key] = {
                            'StringValue': str(value),
                            'DataType': 'Number'
                        }
            
            # Publicar mensaje
            response = self.sqs_client.send_message(
                QueueUrl=self.queue_url,
                MessageBody=message_body_json,
                MessageAttributes=sqs_attributes if sqs_attributes else None
            )
            
            logger.success(f"✅ Mensaje publicado exitosamente. MessageId: {response.get('MessageId')}")
            return True
            
        except ClientError as e:
            logger.error(f"❌ Error de AWS al publicar mensaje a SQS: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Error inesperado al publicar mensaje a SQS: {e}")
            return False


# Instancia global del servicio SQS
sqs_service = SQSService()

