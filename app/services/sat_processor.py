"""
Servicio para procesamiento del SAT
Descarga, valida y procesa archivos del SAT basado en fechas usando S3 como almacenamiento principal
"""
import os
import csv
import requests
import pandas as pd
import boto3
from pathlib import Path
from datetime import datetime, date
from typing import Optional, Dict, List, Tuple, Any
from sqlalchemy.orm import Session
from loguru import logger
from app.core.timezone import get_mexico_time_naive
from botocore.exceptions import ClientError
from io import StringIO

from app.core.config import settings
from app.models.proveedor import Proveedor
from app.services.athena_service import AthenaService



class SATProcessor:
    """Servicio para procesamiento del SAT usando S3"""
    
    def __init__(self):
        self.list_url = settings.SAT_LIST_URL
        
        # Configurar S3
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        self.s3_bucket = settings.S3_BUCKET_NAME
        self.s3_principal = settings.S3_PRINCIPAL
        self.s3_temp = settings.S3_TEMP
        self.s3_versions_path = settings.S3_VERSIONS_PATH
        
        # Claves S3
        self.current_file_key = f"{self.s3_principal}/sat_list_current.csv"
        self.temp_file_key = f"{self.s3_temp}/sat_list_temp.csv"
    
    def analyze_csv_header_from_s3(self, s3_key: str) -> Optional[Dict]:
        """
        Analiza el encabezado del CSV desde S3 para extraer metadata
        
        Args:
            s3_key: Clave del archivo en S3
            
        Returns:
            Diccionario con metadata del archivo o None si hay error
        """
        try:
            # Descargar solo las primeras líneas del archivo
            response = self.s3_client.get_object(
                Bucket=self.s3_bucket,
                Key=s3_key,
                Range='bytes=0-2048'  # Solo primeros 2KB
            )
            
            # Intentar diferentes codificaciones
            try:
                content = response['Body'].read().decode('latin-1')
            except UnicodeDecodeError:
                try:
                    content = response['Body'].read().decode('utf-8')
                except UnicodeDecodeError:
                    content = response['Body'].read().decode('cp1252')
            
            lines = content.split('\n')[:10]  # Solo primeras 10 líneas
            
            # Buscar fecha en el encabezado
            fecha_archivo = None
            total_registros = None
            
            import re
            
            # Buscar fecha en la primera línea 
            if lines:
                primera_linea = lines[0].strip()
                
                # Buscar cualquier fecha en formato español en la primera línea
                meses_esp = {
                    'enero': '01', 'febrero': '02', 'marzo': '03', 'abril': '04',
                    'mayo': '05', 'junio': '06', 'julio': '07', 'agosto': '08',
                    'septiembre': '09', 'octubre': '10', 'noviembre': '11', 'diciembre': '12'
                }
                
                # Patrón 1: "DD de MES de YYYY" (formato español)
                for mes_esp, mes_num in meses_esp.items():
                    if mes_esp in primera_linea.lower():
                        date_match = re.search(r'(\d{1,2})\s+de\s+' + mes_esp + r'\s+de\s+(\d{4})', primera_linea.lower())
                        if date_match:
                            dia = date_match.group(1).zfill(2)
                            año = date_match.group(2)
                            fecha_archivo = datetime.strptime(f"{año}-{mes_num}-{dia}", '%Y-%m-%d').date()
                            logger.info(f"✅ Fecha encontrada en primera línea: {fecha_archivo}")
                            break
                
                # Patrón 2: "YYYY-MM-DD" (formato ISO)
                if not fecha_archivo:
                    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', primera_linea)
                    if date_match:
                        try:
                            fecha_archivo = datetime.strptime(date_match.group(1), '%Y-%m-%d').date()
                            logger.info(f"✅ Fecha encontrada en primera línea (ISO): {fecha_archivo}")
                        except:
                            pass
                
                # Patrón 3: "DD/MM/YYYY" o "MM/DD/YYYY"
                if not fecha_archivo:
                    date_patterns = [
                        r'(\d{1,2})/(\d{1,2})/(\d{4})',  # DD/MM/YYYY o MM/DD/YYYY
                    ]
                    for pattern in date_patterns:
                        matches = re.findall(pattern, primera_linea)
                        for match in matches:
                            try:
                                # Intentar DD/MM/YYYY primero
                                fecha = datetime.strptime(f"{match[0].zfill(2)}/{match[1].zfill(2)}/{match[2]}", '%d/%m/%Y').date()
                                fecha_archivo = fecha
                                logger.info(f"✅ Fecha encontrada en primera línea (DD/MM/YYYY): {fecha_archivo}")
                                break
                            except:
                                try:
                                    # Intentar MM/DD/YYYY
                                    fecha = datetime.strptime(f"{match[0].zfill(2)}/{match[1].zfill(2)}/{match[2]}", '%m/%d/%Y').date()
                                    fecha_archivo = fecha
                                    logger.info(f"✅ Fecha encontrada en primera línea (MM/DD/YYYY): {fecha_archivo}")
                                    break
                                except:
                                    pass
                        if fecha_archivo:
                            break
                
                # Buscar total de registros en otras líneas si encontramos fecha
                if fecha_archivo:
                    for line in lines[1:]:
                        line = line.strip()
                        if 'total' in line.lower() and 'registros' in line.lower():
                            total_match = re.search(r'(\d+)', line)
                            if total_match:
                                total_registros = int(total_match.group(1))
                                logger.info(f"Total de registros encontrado: {total_registros}")
                                break
            else:
                logger.warning("No hay líneas en el archivo para analizar")
            
            # Si no encontramos fecha en encabezado, usar fecha de modificación de S3
            if not fecha_archivo:
                try:
                    response = self.s3_client.head_object(Bucket=self.s3_bucket, Key=s3_key)
                    last_modified = response['LastModified']
                    fecha_archivo = last_modified.date()
                except:
                    fecha_archivo = datetime.now().date()
            
            return {
                'fecha_archivo': fecha_archivo,
                'total_registros': total_registros,
                'archivo_s3_path': s3_key,
                'fecha_procesamiento': datetime.now(),
                'archivo_local_path': None
            }
            
        except Exception as e:
            logger.error(f"Error analizando encabezado de {s3_key}: {e}")
            return None

    def clean_csv_for_athena(self, s3_key: str) -> Optional[str]:
        """
        Limpia un CSV del SAT eliminando comillas problemáticas y preparándolo para Athena.
        
        Args:
            s3_key: Clave S3 del archivo CSV a limpiar
            
        Returns:
            Contenido del CSV limpio como string, o None si falla
        """
        try:
            logger.info(f"🧹 Limpiando CSV para Athena: {s3_key}")
            
            # Descargar archivo de S3
            response = self.s3_client.get_object(Bucket=self.s3_bucket, Key=s3_key)
            
            # Detectar encoding
            encodings = ['latin-1', 'utf-8', 'cp1252', 'iso-8859-1']
            content_bytes = response['Body'].read()
            
            for encoding in encodings:
                try:
                    content = content_bytes.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                content = content_bytes.decode('latin-1', errors='replace')
            
            # Procesar línea por línea
            lines = content.split('\n')
            cleaned_lines = []
            
            # Saltar las 3 primeras líneas de header
            for line_idx, line in enumerate(lines):
                if line_idx < 3:
                    continue
                
                line = line.strip()
                if not line:
                    continue
                
                # Preprocesar: quitar comillas externas y ;;;;
                if line.startswith('"'):
                    line = line[1:]
                line = line.rstrip(';')
                if line.endswith('"'):
                    line = line[:-1]
                
                # Parsear manualmente respetando comillas dobles escapadas ""
                row = []
                current_value = ""
                in_quotes = False
                i = 0
                
                while i < len(line):
                    char = line[i]
                    
                    if char == '"':
                        if i + 1 < len(line) and line[i + 1] == '"':
                            # Es "", marca inicio/fin de campo entrecomillado
                            i += 2
                            in_quotes = not in_quotes
                            continue
                        else:
                            # Es comilla simple
                            in_quotes = not in_quotes
                            i += 1
                            continue
                    
                    elif char == ',' and not in_quotes:
                        # Coma separadora de columna
                        row.append(current_value.strip())
                        current_value = ""
                        i += 1
                        continue
                    
                    elif char == ',' and in_quotes:
                        # Coma dentro de comillas = eliminarla
                        i += 1
                        continue
                    
                    else:
                        current_value += char
                        i += 1
                
                # Agregar último valor
                if current_value or in_quotes:
                    row.append(current_value.strip())
                
                # Limpiar valores (eliminar comillas residuales)
                cleaned_row = [value.strip().strip('"') for value in row]
                
                # Validar RFC (columna 2 - índice 1)
                if len(cleaned_row) >= 4:
                    rfc = cleaned_row[1].strip() if len(cleaned_row) > 1 else ""
                    if rfc and len(rfc) >= 10:
                        # Asegurar 20 columnas
                        while len(cleaned_row) < 20:
                            cleaned_row.append('')
                        
                        # Escribir línea limpia
                        cleaned_line = ','.join(cleaned_row[:20])
                        cleaned_lines.append(cleaned_line)
            
            logger.success(f"✅ CSV limpiado: {len(cleaned_lines)} líneas procesadas")
            return '\n'.join(cleaned_lines)
            
        except Exception as e:
            logger.error(f"❌ Error limpiando CSV: {e}")
            return None

    def backup_current_file_to_versions(self, new_file_date: date) -> bool:
        """
        Hace backup del archivo actual a la estructura de versiones S3.
        Limpia el CSV antes de moverlo para compatibilidad con Athena.
        
        Args:
            new_file_date: Fecha del nuevo archivo que va a reemplazar al actual
            
        Returns:
            True si el backup fue exitoso, False en caso contrario
        """
        try:
            # Verificar si existe el archivo actual
            try:
                self.s3_client.head_object(Bucket=self.s3_bucket, Key=self.current_file_key)
            except ClientError:
                logger.info("No hay archivo actual para hacer backup")
                return True
            
            # Obtener la fecha del archivo actual (extraer antes de limpiar)
            current_metadata = self.analyze_csv_header_from_s3(self.current_file_key)
            if not current_metadata or not current_metadata.get('fecha_archivo'):
                logger.warning("No se pudo obtener fecha del archivo actual para backup")
                return True
            
            current_date = current_metadata['fecha_archivo']
            
            # Crear estructura de versiones 
            fecha_str = current_date.strftime('%Y-%m-%d')
            fecha_filename = current_date.strftime('%Y%m%d')
            
            backup_key = f"{self.s3_versions_path}/version={fecha_str}/SAT_{fecha_filename}.csv"
            
            logger.info(f"💾 Creando backup limpio: {self.current_file_key} → {backup_key}")
            
            # Limpiar CSV para Athena
            cleaned_content = self.clean_csv_for_athena(self.current_file_key)
            if not cleaned_content:
                logger.error("❌ Error limpiando CSV para Athena")
                return False
            
            # Subir CSV limpio a versiones
            try:
                self.s3_client.put_object(
                    Bucket=self.s3_bucket,
                    Key=backup_key,
                    Body=cleaned_content.encode('utf-8'),
                    ContentType='text/csv'
                )
                logger.success(f"✅ Backup limpio creado exitosamente: {backup_key}")
                
                # Ejecutar MSCK REPAIR TABLE para cargar la nueva partición
                logger.info("🔧 Ejecutando MSCK REPAIR TABLE para cargar nueva partición...")
                if self.repair_athena_partitions():
                    logger.success("✅ Particiones de Athena actualizadas correctamente")
                else:
                    logger.warning("⚠️ Error actualizando particiones de Athena (continuando...)")
                
                return True
            except Exception as e:
                logger.error(f"❌ Error subiendo backup limpio: {e}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error inesperado haciendo backup: {e}")
            return False

    def is_file_date_newer_than_processed(self, file_date: date) -> bool:
        """
        Verifica si la fecha del archivo es más reciente que la última procesada
        
        Args:
            file_date: Fecha del archivo a verificar
            
        Returns:
            True si la fecha es más reciente
        """
        try:
            # Verificar si existe un archivo procesado anteriormente
            try:
                response = self.s3_client.head_object(Bucket=self.s3_bucket, Key=self.current_file_key)
                
                # Analizar la fecha del archivo actual procesado
                current_metadata = self.analyze_csv_header_from_s3(self.current_file_key)
                if current_metadata and current_metadata.get('fecha_archivo'):
                    current_date = current_metadata['fecha_archivo']
                    logger.info(f"📅 Fecha del archivo actual procesado: {current_date}")
                    logger.info(f"📅 Fecha del archivo nuevo: {file_date}")
                    
                    # Comparar fechas
                    is_newer = file_date > current_date
                    logger.info(f"🔍 ¿Es más reciente? {is_newer}")
                    return is_newer
                else:
                    # No se pudo obtener la fecha del archivo actual, asumir que es nuevo
                    logger.warning("No se pudo obtener fecha del archivo actual, asumiendo que es nuevo")
                    return True
                
            except ClientError:
                # No existe archivo procesado anteriormente
                logger.info("No existe archivo procesado anteriormente")
                return True
                
        except Exception as e:
            logger.error(f"Error verificando si fecha es más reciente: {e}")
            return True  # En caso de error, asumir que es nuevo

    def download_csv_to_s3(self) -> bool:
        """
        Descarga el CSV del SAT y lo sube directamente a S3 temp
        
        Returns:
            True si la descarga fue exitosa, False en caso contrario
        """
        try:
            logger.info(f"Descargando CSV del SAT desde {self.list_url}")
            
            response = requests.get(
                self.list_url,
                timeout=60,
                headers={'User-Agent': 'AxFiiS-SAT-API/1.0'}
            )
            response.raise_for_status()
            
            # Subir directamente a S3 temp
            self.s3_client.put_object(
                Bucket=self.s3_bucket,
                Key=self.temp_file_key,
                Body=response.content
            )
            
            logger.success(f"CSV descargado exitosamente a S3: s3://{self.s3_bucket}/{self.temp_file_key}")
            return True
            
        except requests.RequestException as e:
            logger.error(f"Error al descargar CSV del SAT: {e}")
            return False
        except ClientError as e:
            logger.error(f"Error subiendo CSV a S3: {e}")
            return False
        except Exception as e:
            logger.error(f"Error inesperado al descargar CSV: {e}")
            return False
    
    def extract_date_from_s3_header(self, s3_key: str) -> Optional[date]:
        """
        Extrae la fecha del encabezado del CSV del SAT desde S3
        
        Args:
            s3_key: Clave S3 del archivo CSV
            
        Returns:
            Fecha extraída del encabezado o None si hay error
        """
        try:
            logger.info(f"Extrayendo fecha del encabezado desde S3: {s3_key}")
            
            # Descargar solo las primeras líneas del archivo
            response = self.s3_client.get_object(
                Bucket=self.s3_bucket,
                Key=s3_key,
                Range='bytes=0-2048'  # Solo primeros 2KB
            )
            
            content = response['Body'].read().decode('latin-1')
            lines = content.split('\n')[:3]  # Solo primeras 3 líneas
            
            # Buscar fecha en las líneas del encabezado
            import re
            for line in lines:
                # Buscar patrones de fecha comunes en el SAT
                if 'actualiza' in line.lower() or 'fecha' in line.lower():
                    # Patrón para fechas en español: "31 de agosto de 2025"
                    meses_esp = {
                        'enero': '01', 'febrero': '02', 'marzo': '03', 'abril': '04',
                        'mayo': '05', 'junio': '06', 'julio': '07', 'agosto': '08',
                        'septiembre': '09', 'octubre': '10', 'noviembre': '11', 'diciembre': '12'
                    }
                    
                    # Buscar patrón: DD de MES de YYYY
                    pattern_esp = r'(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})'
                    match = re.search(pattern_esp, line.lower())
                    if match:
                        dia = match.group(1).zfill(2)
                        mes_nombre = match.group(2)
                        año = match.group(3)
                        
                        if mes_nombre in meses_esp:
                            mes = meses_esp[mes_nombre]
                            try:
                                return datetime.strptime(f'{año}-{mes}-{dia}', '%Y-%m-%d').date()
                            except ValueError:
                                continue
                    
                    # Buscar otros patrones de fecha
                    date_patterns = [
                        r'(\d{1,2}/\d{1,2}/\d{4})',  # DD/MM/YYYY
                        r'(\d{4}-\d{1,2}-\d{1,2})',  # YYYY-MM-DD
                        r'(\d{1,2}-\d{1,2}-\d{4})',  # DD-MM-YYYY
                    ]
                    
                    for pattern in date_patterns:
                        match = re.search(pattern, line)
                        if match:
                            date_str = match.group(1)
                            try:
                                # Intentar parsear la fecha
                                if '/' in date_str:
                                    return datetime.strptime(date_str, '%d/%m/%Y').date()
                                elif '-' in date_str and len(date_str.split('-')[0]) == 4:
                                    return datetime.strptime(date_str, '%Y-%m-%d').date()
                                elif '-' in date_str:
                                    return datetime.strptime(date_str, '%d-%m-%Y').date()
                            except ValueError:
                                continue
            
            # Si no se encuentra fecha específica, usar fecha actual
            logger.warning("No se encontró fecha en el encabezado, usando fecha actual")
            return datetime.now().date()
            
        except ClientError as e:
            logger.error(f"Error descargando archivo desde S3: {e}")
            return None
        except Exception as e:
            logger.error(f"Error extrayendo fecha del encabezado: {e}")
            return None
    
    
    def move_s3_object(self, source_key: str, dest_key: str) -> bool:
        """
        Mueve un objeto de una ubicación S3 a otra
        
        Args:
            source_key: Clave S3 origen
            dest_key: Clave S3 destino
            
        Returns:
            True si el movimiento fue exitoso, False en caso contrario
        """
        try:
            logger.info(f"Moviendo objeto S3: {source_key} → {dest_key}")
            
            # Copiar objeto a nueva ubicación
            copy_source = {'Bucket': self.s3_bucket, 'Key': source_key}
            self.s3_client.copy_object(
                CopySource=copy_source,
                Bucket=self.s3_bucket,
                Key=dest_key
            )
            
            # Eliminar objeto original
            self.s3_client.delete_object(
                Bucket=self.s3_bucket,
                Key=source_key
            )
            
            logger.success(f"Objeto movido exitosamente: {source_key} → {dest_key}")
            return True
            
        except ClientError as e:
            logger.error(f"Error moviendo objeto S3: {e}")
            return False
        except Exception as e:
            logger.error(f"Error inesperado moviendo objeto S3: {e}")
            return False
    
    def delete_s3_object(self, s3_key: str) -> bool:
        """
        Elimina un objeto de S3
        
        Args:
            s3_key: Clave S3 del objeto a eliminar
            
        Returns:
            True si la eliminación fue exitosa, False en caso contrario
        """
        try:
            logger.info(f"Eliminando objeto S3: {s3_key}")
            
            self.s3_client.delete_object(
                Bucket=self.s3_bucket,
                Key=s3_key
            )
            
            logger.success(f"Objeto eliminado exitosamente: {s3_key}")
            return True
            
        except ClientError as e:
            logger.error(f"Error eliminando objeto S3: {e}")
            return False
        except Exception as e:
            logger.error(f"Error inesperado eliminando objeto S3: {e}")
            return False
    
    
    def process_csv_data_from_s3_optimized(self, db: Session, s3_key: str, file_date: date) -> bool:
        """
        Procesa los datos del CSV desde S3 usando pandas chunks para inserción 
        
        Args:
            db: Sesión de base de datos
            s3_key: Clave S3 del archivo CSV
            file_date: Fecha del archivo
            
        Returns:
            True si el procesamiento fue exitoso, False en caso contrario
        """
        try:
            logger.info(f"Procesando datos del CSV desde S3 : {s3_key}")
            
            # Descargar CSV desde S3 a memoria 
            response = self.s3_client.get_object(Bucket=self.s3_bucket, Key=s3_key)
            content = response['Body'].read().decode('latin-1')
            
            # Limpiar tabla de proveedores 
            logger.info("Limpiando tabla de proveedores...")
            db.query(Proveedor).delete()
            
            # Procesar con pandas chunks para inserción masiva
            chunk_size = 5000  # Procesar en lotes de 5000 registros
            total_processed = 0
            now = get_mexico_time_naive()
            
            # Convertir file_date a datetime para la columna fecha_lista
            file_datetime = datetime.combine(file_date, datetime.min.time())
            
            logger.info(f"Procesando CSV en chunks de {chunk_size} registros...")
            
            # Set global para evitar duplicados entre chunks
            global_seen_rfcs = set()
            
            # Procesar CSV en chunks usando pandas
            for chunk_num, chunk_df in enumerate(pd.read_csv(
                StringIO(content),
                chunksize=chunk_size,
                skiprows=2,  # Saltar encabezados del SAT
                encoding='latin-1',
                dtype=str
            )):
                logger.info(f"Procesando chunk {chunk_num + 1}...")
                
                # Mapear columnas
                chunk_df = self._map_csv_columns(chunk_df)
                
                # Procesar chunk (con set global para evitar duplicados entre chunks)
                chunk_data = self._process_chunk_data(chunk_df, file_datetime, now, global_seen_rfcs)
                
                if chunk_data:
                    # Inserción masiva del chunk
                    db.bulk_insert_mappings(Proveedor, chunk_data)
                    total_processed += len(chunk_data)
                    logger.info(f"✅ Chunk {chunk_num + 1}: {len(chunk_data)} registros insertados")
            
            
            db.commit()
            logger.success(f"Base de datos actualizada exitosamente con {total_processed} registros")
            return True
                    
        except Exception as e:
            logger.error(f"Error procesando datos del CSV: {e}")
            db.rollback()
            return False
    
    def _map_csv_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Mapea las columnas del CSV del SAT"""
        column_mapping = {
            'No': 'numero',
            'RFC': 'rfc',
            'Nombre del Contribuyente': 'nombre_contribuyente',
            'Situación del contribuyente': 'situacion_contribuyente',
            'Número y fecha de oficio global de presunción SAT': 'oficio_presuncion_numero',
            'Publicación página SAT presuntos': 'publicacion_sat_presuntos',
            'Número y fecha de oficio global de presunción DOF': 'oficio_presuncion_dof',
            'Publicación DOF presuntos': 'publicacion_dof_presuntos',
            'Número y fecha de oficio global de contribuyentes que desvirtuaron SAT': 'oficio_desvirtuar_numero',
            'Publicación página SAT desvirtuados': 'publicacion_sat_desvirtuados',
            'Número y fecha de oficio global de contribuyentes que desvirtuaron DOF': 'oficio_desvirtuar_dof',
            'Publicación DOF desvirtuados': 'publicacion_dof_desvirtuados',
            'Número y fecha de oficio global de definitivos SAT': 'oficio_definitivo_numero',
            'Publicación página SAT definitivos': 'publicacion_sat_definitivos',
            'Número y fecha de oficio global de definitivos DOF': 'oficio_definitivo_dof',
            'Publicación DOF definitivos': 'publicacion_dof_definitivos',
            'Número y fecha de oficio global de sentencia favorable SAT': 'oficio_sentencia_numero',
            'Publicación página SAT sentencia favorable': 'publicacion_sat_sentencia',
            'Número y fecha de oficio global de sentencia favorable DOF': 'oficio_sentencia_dof',
            'Publicación DOF sentencia favorable': 'publicacion_dof_sentencia'
        }
        
        df = df.rename(columns=column_mapping)
        df = df.fillna('')
        return df
    
    def _process_chunk_data(self, chunk_df: pd.DataFrame, file_datetime: datetime, now: datetime, global_seen_rfcs: set = None) -> List[Dict]:
        """Procesa un chunk de datos y los convierte al formato de la BD"""
        chunk_data = []
        
        # Usar set global si se proporciona, sino crear uno local
        if global_seen_rfcs is None:
            global_seen_rfcs = set()
        
        for _, row in chunk_df.iterrows():
            rfc = str(row.get('rfc', '')).strip()
            
            # Filtrar RFCs vacíos o información suprimida
            if not rfc or rfc == 'XXXXXXXXXXXX' or rfc == 'nan':
                continue
            
            # Normalizar RFC
            rfc_norm = rfc.upper().strip()
            
            # Eliminar duplicados (usa set global que persiste entre chunks)
            if rfc_norm in global_seen_rfcs:
                continue
            global_seen_rfcs.add(rfc_norm)
            
            # Preparar datos del proveedor
            proveedor_data = {
                'rfc': rfc_norm,
                'nombre_contribuyente': str(row.get('nombre_contribuyente', '')),
                'razon_social': str(row.get('razon_social', '')) or str(row.get('nombre_contribuyente', '')),
                'situacion_contribuyente': str(row.get('situacion_contribuyente', '')),
                'fecha_lista': file_datetime,  # Fecha de la versión del SAT, no la fecha de procesamiento
                'created_at': now,
                'fecha_actualizacion': now,
                # Campos adicionales del SAT
                'oficio_presuncion_numero': str(row.get('oficio_presuncion_numero', '')),
                'publicacion_sat_presuntos': str(row.get('publicacion_sat_presuntos', '')),
                'publicacion_dof_presuntos': str(row.get('publicacion_dof_presuntos', '')),
                'oficio_desvirtuar_numero': str(row.get('oficio_desvirtuar_numero', '')),
                'publicacion_sat_desvirtuados': str(row.get('publicacion_sat_desvirtuados', '')),
                'publicacion_dof_desvirtuados': str(row.get('publicacion_dof_desvirtuados', '')),
                'oficio_definitivo_numero': str(row.get('oficio_definitivo_numero', '')),
                'publicacion_sat_definitivos': str(row.get('publicacion_sat_definitivos', '')),
                'publicacion_dof_definitivos': str(row.get('publicacion_dof_definitivos', '')),
                'oficio_sentencia_numero': str(row.get('oficio_sentencia_numero', '')),
                'publicacion_sat_sentencia': str(row.get('publicacion_sat_sentencia', '')),
                'publicacion_dof_sentencia': str(row.get('publicacion_dof_sentencia', ''))
            }
            
            chunk_data.append(proveedor_data)
        
        return chunk_data
    
    
    def process_sat_update(self, db: Session) -> Dict[str, Any]:
        """
        Función principal: procesa actualización del SAT usando análisis de encabezado S3
        
        Args:
            db: Sesión de base de datos
            
        Returns:
            Diccionario con:
            - success: True si el procesamiento fue exitoso, False en caso contrario
            - nueva_version: True si se detectó una nueva versión, False si ya estaba procesada
            - fecha_version: Fecha de la versión procesada (str en formato YYYY-MM-DD) o None
            - total_registros: Total de registros procesados (opcional)
        """
        try:
            logger.info("🚀 Iniciando procesamiento de actualización del SAT (S3)")
            logger.info("=" * 60)
            
            # 1. Descargar CSV a S3 temp
            if not self.download_csv_to_s3():
                logger.error("❌ Error descargando CSV del SAT a S3")
                return {
                    "success": False,
                    "nueva_version": False,
                    "fecha_version": None,
                    "total_registros": None
                }
            
            # 2. Analizar encabezado del archivo
            logger.info("📅 Analizando encabezado del archivo...")
            file_metadata = self.analyze_csv_header_from_s3(self.temp_file_key)
            if not file_metadata:
                logger.error("❌ Error analizando encabezado del archivo")
                self.delete_s3_object(self.temp_file_key)
                return {
                    "success": False,
                    "nueva_version": False,
                    "fecha_version": None,
                    "total_registros": None
                }
            
            file_date = file_metadata['fecha_archivo']
            logger.info(f"📅 Fecha del archivo descargado: {file_date}")
            total_registros = file_metadata.get('total_registros')
            if total_registros:
                logger.info(f"📊 Total de registros esperados: {total_registros}")
            
            # 3. Verificar si la fecha del archivo es más reciente que la última procesada
            logger.info("🔍 Verificando si la fecha del archivo es más reciente...")
            if not self.is_file_date_newer_than_processed(file_date):
                logger.info(f"📋 Archivo con fecha {file_date} ya fue procesado")
                logger.info("⏹️  Procesamiento omitido")
                self.delete_s3_object(self.temp_file_key)
                return {
                    "success": True,
                    "nueva_version": False,
                    "fecha_version": file_date.strftime('%Y-%m-%d'),
                    "total_registros": total_registros
                }
            
            logger.info("🔄 Archivo nuevo detectado - iniciando procesamiento")
            
            # 4. Hacer backup del archivo actual (si existe)
            logger.info("💾 Haciendo backup del archivo actual...")
            if not self.backup_current_file_to_versions(file_date):
                logger.warning("⚠️  Error haciendo backup, continuando...")
            
            # 5. Mover archivo temporal a Actual_SAT
            logger.info("📁 Moviendo archivo temporal a Actual_SAT...")
            if not self.move_s3_object(self.temp_file_key, self.current_file_key):
                logger.error("❌ Error moviendo archivo temporal a Actual_SAT")
                return {
                    "success": False,
                    "nueva_version": False,
                    "fecha_version": None,
                    "total_registros": None
                }
            
            # 6. Procesar datos y actualizar BD 
            logger.info("🔄 Procesando datos y actualizando base de datos...")
            if not self.process_csv_data_from_s3_optimized(db, self.current_file_key, file_date):
                logger.error("❌ Error procesando datos del CSV")
                return {
                    "success": False,
                    "nueva_version": False,
                    "fecha_version": None,
                    "total_registros": None
                }
            
            logger.success("✅ Procesamiento del SAT completado exitosamente")
            logger.info("=" * 60)
            
            # Retornar información de éxito con nueva versión
            return {
                "success": True,
                "nueva_version": True,
                "fecha_version": file_date.strftime('%Y-%m-%d'),
                "total_registros": total_registros
            }
            
        except Exception as e:
            logger.error(f"❌ Error inesperado en procesamiento: {e}")
            # Limpiar archivo temporal en caso de error
            try:
                self.delete_s3_object(self.temp_file_key)
            except:
                pass
            return {
                "success": False,
                "nueva_version": False,
                "fecha_version": None,
                "total_registros": None
            }
    
    def repair_athena_partitions(self) -> bool:
        """
        Ejecuta MSCK REPAIR TABLE para cargar nuevas particiones en Athena
        
        Returns:
            True si fue exitoso, False en caso contrario
        """
        try:
            athena_service = AthenaService()
            return athena_service.repair_partitions()
        except Exception as e:
            logger.error(f"Error ejecutando MSCK REPAIR TABLE: {e}")
            return False


# Instancia global del procesador
sat_processor = SATProcessor()
