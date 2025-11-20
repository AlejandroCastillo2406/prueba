"""
Servicio para envío de correos electrónicos usando AWS SES
"""
import boto3
from typing import List, Optional
from io import BytesIO
from botocore.exceptions import ClientError
from loguru import logger

from app.core.config import settings


class EmailService:
    """Servicio para envío de correos electrónicos con AWS SES"""
    
    def __init__(self):
        """Inicializa el cliente SES"""
        self.ses_client = boto3.client(
            'ses',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        self.sender_email = settings.SES_SENDER_EMAIL
    
    def enviar_correo_conciliacion(
        self,
        destinatarios: List[str],
        tenant_nombre: str,
        tipo_conciliacion: str,
        fecha_conciliacion: str,
        rfcs_procesados: int,
        coincidencias: int,
        pdf_buffer: BytesIO,
        historial_id: str
    ) -> bool:
        """
        Envía correo con reporte PDF de conciliación a cada destinatario individualmente.
        Si un destinatario falla, los demás no se afectan.
        
        Args:
            destinatarios: Lista de emails de destinatarios
            tenant_nombre: Nombre del tenant
            tipo_conciliacion: Tipo de conciliación (DOF + SAT, Automatica, etc.)
            fecha_conciliacion: Fecha de la conciliación
            rfcs_procesados: Total de RFCs procesados
            coincidencias: Total de coincidencias
            pdf_buffer: Buffer con el contenido del PDF
            historial_id: ID del historial de conciliación
            
        Returns:
            True si al menos un correo se envió correctamente, False si todos fallaron
        """
        if not destinatarios:
            logger.warning("No hay destinatarios para enviar correo")
            return False
        
        # Preparar nombre del archivo PDF
        fecha_str = fecha_conciliacion.replace("-", "").replace(" ", "_").replace(":", "")[:8]
        filename = f"conciliacion_{tipo_conciliacion.replace(' ', '_')}_{fecha_str}_{historial_id[:8]}.pdf"
        
        # Leer contenido del PDF una sola vez
        pdf_buffer.seek(0)
        attachment = pdf_buffer.read()
        
        # Preparar cuerpo del correo en HTML
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #1a1a1a; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; background-color: #f9f9f9; }}
                .metrics {{ display: flex; justify-content: space-around; margin: 20px 0; }}
                .metric {{ text-align: center; padding: 15px; background-color: white; border-radius: 5px; }}
                .metric-value {{ font-size: 24px; font-weight: bold; color: #1a1a1a; }}
                .metric-label {{ font-size: 12px; color: #666; margin-top: 5px; }}
                .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Reporte de Conciliación</h1>
                </div>
                <div class="content">
                    <p>Estimado/a,</p>
                    <p>Se ha completado una conciliación automática para <strong>{tenant_nombre}</strong>.</p>
                    
                    <div class="metrics">
                        <div class="metric">
                            <div class="metric-value">{rfcs_procesados}</div>
                            <div class="metric-label">RFCs Procesados</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value">{coincidencias}</div>
                            <div class="metric-label">Coincidencias</div>
                        </div>
                    </div>
                    
                    <p><strong>Tipo de Conciliación:</strong> {tipo_conciliacion}</p>
                    <p><strong>Fecha:</strong> {fecha_conciliacion}</p>
                    
                    <p>El reporte completo en PDF se adjunta a este correo.</p>
                    
                    <p>Saludos,<br>Equipo AxFiiS</p>
                </div>
                <div class="footer">
                    <p>Este es un correo automático, por favor no responder.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Preparar cuerpo en texto plano
        text_body = f"""
Reporte de Conciliación

Se ha completado una conciliación automática para {tenant_nombre}.

RFCs Procesados: {rfcs_procesados}
Coincidencias: {coincidencias}
Tipo de Conciliación: {tipo_conciliacion}
Fecha: {fecha_conciliacion}

El reporte completo en PDF se adjunta a este correo.

Saludos,
Equipo AxFiiS
        """
        
        # Enviar correo individual a cada destinatario
        exitosos = 0
        fallidos = 0
        emails_fallidos = []
        
        for destinatario in destinatarios:
            try:
                # Crear mensaje raw para un solo destinatario
                raw_message = self._crear_mensaje_raw(
                    from_email=self.sender_email,
                    to_emails=[destinatario],  # Solo un destinatario
                    subject=f"Reporte de Conciliación - {tenant_nombre}",
                    html_body=html_body,
                    text_body=text_body,
                    attachment=attachment,
                    filename=filename
                )
                
                # Enviar correo usando SES
                response = self.ses_client.send_raw_email(
                    Source=self.sender_email,
                    Destinations=[destinatario],  # Solo un destinatario
                    RawMessage={'Data': raw_message}
                )
                
                exitosos += 1
                logger.success(f"✅ Correo enviado a {destinatario}. MessageId: {response.get('MessageId')}")
                
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                fallidos += 1
                emails_fallidos.append(destinatario)
                logger.error(f"❌ Error enviando correo a {destinatario}: {error_code} - {str(e)}")
                
            except Exception as e:
                fallidos += 1
                emails_fallidos.append(destinatario)
                logger.error(f"❌ Error inesperado enviando correo a {destinatario}: {str(e)}")
        
        # Resumen
        total = len(destinatarios)
        if exitosos > 0:
            logger.success(f"📧 Resumen: {exitosos}/{total} correos enviados exitosamente")
            if fallidos > 0:
                logger.warning(f"⚠️ {fallidos} correos fallaron: {', '.join(emails_fallidos)}")
            return True
        else:
            logger.error(f"❌ Todos los correos fallaron ({fallidos}/{total})")
            return False
    
    def _crear_mensaje_raw(
        self,
        from_email: str,
        to_emails: List[str],
        subject: str,
        html_body: str,
        text_body: str,
        attachment: bytes,
        filename: str
    ) -> bytes:
        """
        Crea un mensaje raw para SES con HTML, texto plano y adjunto
        
        Args:
            from_email: Email del remitente
            to_emails: Lista de emails destinatarios
            subject: Asunto del correo
            html_body: Cuerpo HTML
            text_body: Cuerpo en texto plano
            attachment: Contenido del adjunto (bytes)
            filename: Nombre del archivo adjunto
            
        Returns:
            Mensaje raw en formato bytes
        """
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        from email.mime.application import MIMEApplication
        from email.header import Header
        
        # Crear mensaje multipart
        msg = MIMEMultipart('mixed')
        msg['From'] = from_email
        msg['To'] = ', '.join(to_emails)
        msg['Subject'] = subject
        
        # Crear parte alternativa (HTML + texto)
        msg_alternative = MIMEMultipart('alternative')
        msg.attach(msg_alternative)
        
        # Agregar texto plano
        part_text = MIMEText(text_body, 'plain', 'utf-8')
        msg_alternative.attach(part_text)
        
        # Agregar HTML
        part_html = MIMEText(html_body, 'html', 'utf-8')
        msg_alternative.attach(part_html)
        
        # Agregar adjunto PDF
        part_attachment = MIMEApplication(attachment, 'pdf')
        part_attachment.add_header(
            'Content-Disposition',
            'attachment',
            filename=Header(filename, 'utf-8').encode()
        )
        part_attachment.add_header('Content-Type', 'application/pdf')
        msg.attach(part_attachment)
        
        # Convertir a string y luego a bytes
        return msg.as_string().encode('utf-8')


# Instancia global del servicio de email
email_service = EmailService()

