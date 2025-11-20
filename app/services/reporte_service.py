"""
Servicio para generar reportes PDF y CSV de conciliaciones
"""
from typing import Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from io import BytesIO
from datetime import datetime
from loguru import logger

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT


from app.models.conciliacion_historial import ConciliacionHistorial
from app.models.conciliacion_detalle import ConciliacionDetalle
from app.core.timezone import formatear_fecha_es


class ReporteService:
    """Servicio para generar reportes de conciliación"""
    
    def obtener_datos_reporte(self, session: Session, tenant_id: UUID, historial_id: UUID) -> Dict[str, Any]:
        """
        Obtiene todos los datos necesarios para generar el reporte
        
        Args:
            session: Sesión de base de datos
            tenant_id: ID del tenant
            historial_id: ID del historial de conciliación
            
        Returns:
            Diccionario con todos los datos del reporte
        """
        try:
            # Obtener historial
            historial = session.query(ConciliacionHistorial).filter(
                ConciliacionHistorial.id == historial_id,
                ConciliacionHistorial.tenant_id == tenant_id
            ).first()
            
            if not historial:
                raise ValueError(f"Conciliación {historial_id} no encontrada para tenant {tenant_id}")
            
            # Obtener detalles
            detalles = session.query(ConciliacionDetalle).filter(
                ConciliacionDetalle.conciliacion_id == historial_id
            ).order_by(ConciliacionDetalle.rfc.asc()).all()
            
            # Formatear fecha
            fecha_formateada = formatear_fecha_es(historial.fecha_conciliacion)
            
            # Formatear duración
            duracion_min = historial.duracion_ms / 60000.0 if historial.duracion_ms else 0
            duracion_str = f"{duracion_min:.1f} min" if duracion_min >= 1.0 else f"{historial.duracion_ms / 1000.0:.1f} seg"
            
            return {
                "historial": {
                    "id": str(historial.id),
                    "fecha_conciliacion": historial.fecha_conciliacion,
                    "fecha_formateada": fecha_formateada,
                    "tipo_conciliacion": historial.tipo_conciliacion,
                    "version_sat": historial.version_sat,
                    "rfcs_procesados": historial.rfcs_procesados,
                    "coincidencias": historial.coincidencias,
                    "sin_coincidencias": historial.rfcs_procesados - historial.coincidencias,
                    "duracion_ms": historial.duracion_ms,
                    "duracion_str": duracion_str,
                    "estado": historial.estado
                },
                "detalles": [
                    {
                        "rfc": detalle.rfc,
                        "estado": detalle.estado
                    }
                    for detalle in detalles
                ]
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo datos para reporte: {e}")
            raise
    
    def generar_pdf(self, datos: Dict[str, Any]) -> BytesIO:
        """
        Genera un PDF con el reporte de conciliación
        
        Args:
            datos: Datos del reporte obtenidos de obtener_datos_reporte
            
        Returns:
            BytesIO con el contenido del PDF
        """
        try:

            
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.75*inch, bottomMargin=0.75*inch)
            story = []
            
            styles = getSampleStyleSheet()
            
            # Título principal
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=18,
                textColor=colors.HexColor('#1a1a1a'),
                spaceAfter=12,
                alignment=TA_LEFT
            )
            
            historial = datos["historial"]
            detalles = datos["detalles"]
            
            # Título
            story.append(Paragraph(historial["tipo_conciliacion"], title_style))
            
            # Fecha y versión SAT
            fecha_style = ParagraphStyle(
                'Fecha',
                parent=styles['Normal'],
                fontSize=10,
                textColor=colors.HexColor('#666666'),
                spaceAfter=20
            )
            fecha_text = f"{historial['fecha_formateada']} · Versión SAT: {historial['version_sat']}"
            story.append(Paragraph(fecha_text, fecha_style))
            story.append(Spacer(1, 0.3*inch))
            
            # Métricas principales
            metrics_data = [
                [
                    Paragraph("<b>RFCs procesados</b>", styles['Normal']),
                    Paragraph("<b>Coincidencias</b>", styles['Normal']),
                    Paragraph("<b>Sin coincidencias</b>", styles['Normal']),
                    Paragraph("<b>Duración</b>", styles['Normal'])
                ],
                [
                    Paragraph(str(historial["rfcs_procesados"]), styles['Heading2']),
                    Paragraph(str(historial["coincidencias"]), styles['Heading2']),
                    Paragraph(str(historial["sin_coincidencias"]), styles['Heading2']),
                    Paragraph(historial["duracion_str"], styles['Heading2'])
                ]
            ]
            
            metrics_table = Table(metrics_data, colWidths=[1.5*inch, 1.5*inch, 1.5*inch, 1.5*inch])
            metrics_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f5f5f5')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('FONTSIZE', (0, 1), (-1, 1), 14),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('TOPPADDING', (0, 1), (-1, 1), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e0e0e0')),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            
            story.append(metrics_table)
            story.append(Spacer(1, 0.4*inch))
            
            # Resultados destacados (solo coincidencias)
            coincidencias = [d for d in detalles if d["estado"] != "No encontrado"]
            
            if coincidencias:
                story.append(Paragraph("<b>Resultados destacados</b>", styles['Heading2']))
                story.append(Spacer(1, 0.2*inch))
                
                # Tabla de resultados
                resultados_data = [
                    [Paragraph("<b>RFC</b>", styles['Normal']),
                     Paragraph("<b>Estado SAT</b>", styles['Normal']),
                     Paragraph("<b>Resultado</b>", styles['Normal'])]
                ]
                
                for detalle in coincidencias:
                    estado_color = self._obtener_color_estado(detalle["estado"])
                    resultado = "Coincidencia" if detalle["estado"] != "No encontrado" else "Sin coincidencia"
                    
                    # Si es "Desvirtuado" o similar, mostrar "Regularizado"
                    if "desvirtuado" in detalle["estado"].lower() or "sentencia" in detalle["estado"].lower():
                        resultado = "Regularizado"
                    
                    resultados_data.append([
                        Paragraph(detalle["rfc"], styles['Normal']),
                        Paragraph(f'<font color="{estado_color}">{detalle["estado"]}</font>', styles['Normal']),
                        Paragraph(resultado, styles['Normal'])
                    ])
                
                resultados_table = Table(resultados_data, colWidths=[2*inch, 2.5*inch, 2*inch])
                resultados_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f5f5f5')),
                    ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                    ('TOPPADDING', (0, 0), (-1, -1), 8),
                    ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e0e0e0')),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ]))
                
                story.append(resultados_table)
                story.append(Spacer(1, 0.3*inch))
            
            # Resumen técnico
            story.append(Paragraph("<b>Resumen técnico</b>", styles['Heading2']))
            story.append(Spacer(1, 0.2*inch))
            
            resumen_text = f"""
            execution_id: {historial['id']}<br/>
            status: {historial['estado']}<br/>
            processed: {historial['rfcs_procesados']}<br/>
            matched: {historial['coincidencias']}
            """
            
            resumen_style = ParagraphStyle(
                'Resumen',
                parent=styles['Normal'],
                fontSize=9,
                fontName='Courier',
                textColor=colors.HexColor('#333333'),
                backColor=colors.HexColor('#f9f9f9'),
                leftIndent=12,
                rightIndent=12,
                spaceBefore=8,
                spaceAfter=8,
                borderPadding=8
            )
            
            story.append(Paragraph(resumen_text, resumen_style))
            
            # Construir PDF
            doc.build(story)
            buffer.seek(0)
            
            return buffer
            
        except Exception as e:
            logger.error(f"Error generando PDF: {e}")
            raise
    
    def generar_csv(self, datos: Dict[str, Any]) -> BytesIO:
        """
        Genera un CSV con el reporte de conciliación
        
        Args:
            datos: Datos del reporte obtenidos de obtener_datos_reporte
            
        Returns:
            BytesIO con el contenido del CSV
        """
        try:
            import csv
            import io
            
            # Crear buffer de texto en memoria
            text_buffer = io.StringIO()
            writer = csv.writer(text_buffer)
            
            historial = datos["historial"]
            detalles = datos["detalles"]
            
            # Encabezado
            writer.writerow([f"Reporte de Conciliación - {historial['tipo_conciliacion']}"])
            writer.writerow([f"Fecha: {historial['fecha_formateada']}"])
            writer.writerow([f"Versión SAT: {historial['version_sat']}"])
            writer.writerow([])
            
            # Métricas
            writer.writerow(["Métricas"])
            writer.writerow(["RFCs procesados", historial["rfcs_procesados"]])
            writer.writerow(["Coincidencias", historial["coincidencias"]])
            writer.writerow(["Sin coincidencias", historial["sin_coincidencias"]])
            writer.writerow(["Duración", historial["duracion_str"]])
            writer.writerow([])
            
            # Resultados
            writer.writerow(["RFC", "Estado SAT", "Resultado"])
            for detalle in detalles:
                resultado = "Coincidencia" if detalle["estado"] != "No encontrado" else "Sin coincidencia"
                if "desvirtuado" in detalle["estado"].lower() or "sentencia" in detalle["estado"].lower():
                    resultado = "Regularizado"
                writer.writerow([detalle["rfc"], detalle["estado"], resultado])
            
            writer.writerow([])
            writer.writerow(["Resumen técnico"])
            writer.writerow(["execution_id", historial["id"]])
            writer.writerow(["status", historial["estado"]])
            writer.writerow(["processed", historial["rfcs_procesados"]])
            writer.writerow(["matched", historial["coincidencias"]])
            
            # Obtener el contenido como string
            csv_content = text_buffer.getvalue()
            text_buffer.close()
            
            # Crear buffer de bytes con BOM UTF-8 para Excel
            buffer = BytesIO()
            buffer.write('\ufeff'.encode('utf-8-sig'))  # BOM para Excel
            buffer.write(csv_content.encode('utf-8-sig'))
            
            # Volver al inicio del buffer
            buffer.seek(0)
            return buffer
            
        except Exception as e:
            logger.error(f"Error generando CSV: {e}")
            raise
    
    def _obtener_color_estado(self, estado: str) -> str:
        """
        Obtiene el color hexadecimal según el estado del RFC
        
        Args:
            estado: Estado del RFC en el SAT
            
        Returns:
            Color hexadecimal como string
        """
        estado_lower = estado.lower()
        if "definitivo" in estado_lower:
            return "#dc3545"  # Rojo
        elif "presunto" in estado_lower:
            return "#fd7e14"  # Naranja
        elif "desvirtuado" in estado_lower or "sentencia" in estado_lower:
            return "#28a745"  # Verde
        else:
            return "#6c757d"  # Gris

