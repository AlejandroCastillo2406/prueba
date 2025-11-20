"""
Servicio para procesar archivos CSV y Excel con RFCs
"""
import csv
import io
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime
import pandas as pd
from loguru import logger


class FileProcessorService:
    """Servicio para procesar archivos CSV y Excel con validación de template"""
    
    # Template exacto requerido 
    REQUIRED_COLUMNS = {"RFC", "Razón Social", "Fecha Inicio", "Fecha Baja"}
    
    def process_file(self, file_content: bytes, filename: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Procesa un archivo CSV o Excel y extrae los RFCs con sus datos
        
        Args:
            file_content: Contenido del archivo en bytes
            filename: Nombre del archivo
            
        Returns:
            Tupla con (lista de datos extraídos, metadatos)
            
        Raises:
            ValueError: Si el archivo no tiene el template correcto
        """
        try:
            # Detectar tipo de archivo
            if filename.lower().endswith('.csv'):
                return self._process_csv(file_content)
            elif filename.lower().endswith(('.xlsx', '.xls')):
                return self._process_excel(file_content)
            else:
                raise ValueError("Formato de archivo no soportado. Solo se aceptan CSV y Excel (.xlsx, .xls)")
                
        except Exception as e:
            logger.error(f"Error procesando archivo {filename}: {e}")
            raise
    
    def _process_csv(self, file_content: bytes) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Procesa archivo CSV"""
        try:
            # Intentar diferentes encodings
            for encoding in ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']:
                try:
                    content_str = file_content.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise ValueError("No se pudo decodificar el archivo CSV. Verifica el encoding.")
            
            # Leer CSV
            csv_file = io.StringIO(content_str)
            reader = csv.DictReader(csv_file)
            
            # Validar columnas
            if not reader.fieldnames:
                raise ValueError("El archivo CSV está vacío o no tiene encabezados")
            
            # Normalizar nombres de columnas (quitar espacios extra)
            columnas = {col.strip() for col in reader.fieldnames}
            
            # Validar template exacto
            if columnas != self.REQUIRED_COLUMNS:
                self._raise_template_error(columnas)
            
            # Extraer datos
            datos = []
            filas_procesadas = 0
            rfcs_validos = 0
            
            for row in reader:
                filas_procesadas += 1
                
                # Extraer y limpiar datos
                rfc = row.get('RFC', '').strip().upper()
                razon_social = row.get('Razón Social', '').strip()
                fecha_inicio_str = row.get('Fecha Inicio', '').strip()
                fecha_baja_str = row.get('Fecha Baja', '').strip()
                
                # Validar RFC (12 o 13 caracteres alfanuméricos)
                if not rfc or len(rfc) not in [12, 13] or not rfc.isalnum():
                    continue
                
                # Parsear fechas
                fecha_inicio = self._parse_fecha(fecha_inicio_str) if fecha_inicio_str else None
                fecha_baja = self._parse_fecha(fecha_baja_str) if fecha_baja_str else None
                
                datos.append({
                    'rfc': rfc,
                    'razon_social': razon_social or None,
                    'fecha_inicio': fecha_inicio,
                    'fecha_baja': fecha_baja
                })
                rfcs_validos += 1
            
            metadatos = {
                'total_filas': filas_procesadas,
                'rfcs_validos': rfcs_validos,
                'tipo_archivo': 'CSV'
            }
            
            return datos, metadatos
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error procesando CSV: {e}")
            raise ValueError(f"Error procesando archivo CSV: {str(e)}")
    
    def _process_excel(self, file_content: bytes) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Procesa archivo Excel"""
        try:
            # Leer Excel
            df = pd.read_excel(io.BytesIO(file_content), sheet_name=0)
            
            if df.empty:
                raise ValueError("El archivo Excel está vacío")
            
            # Normalizar nombres de columnas (quitar espacios extra)
            df.columns = df.columns.str.strip()
            columnas = set(df.columns)
            
            # Validar template exacto
            if columnas != self.REQUIRED_COLUMNS:
                self._raise_template_error(columnas)
            
            # Extraer datos
            datos = []
            rfcs_validos = 0
            
            for _, row in df.iterrows():
                # Extraer y limpiar datos
                rfc = str(row.get('RFC', '')).strip().upper()
                razon_social = str(row.get('Razón Social', '')).strip()
                fecha_inicio = row.get('Fecha Inicio')
                fecha_baja = row.get('Fecha Baja')
                
                # Validar RFC
                if not rfc or len(rfc) not in [12, 13] or not rfc.replace(' ', '').isalnum():
                    continue
                
                rfc = rfc.replace(' ', '')  # Eliminar espacios
                
                # Convertir fechas de pandas a datetime
                fecha_inicio_dt = self._convert_pandas_date(fecha_inicio)
                fecha_baja_dt = self._convert_pandas_date(fecha_baja)
                
                datos.append({
                    'rfc': rfc,
                    'razon_social': razon_social if razon_social != 'nan' else None,
                    'fecha_inicio': fecha_inicio_dt,
                    'fecha_baja': fecha_baja_dt
                })
                rfcs_validos += 1
            
            metadatos = {
                'total_filas': len(df),
                'rfcs_validos': rfcs_validos,
                'tipo_archivo': 'Excel'
            }
            
            return datos, metadatos
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error procesando Excel: {e}")
            raise ValueError(f"Error procesando archivo Excel: {str(e)}")
    
    def _raise_template_error(self, columnas_encontradas: set):
        """Lanza error de template inválido con detalles"""
        columnas_faltantes = self.REQUIRED_COLUMNS - columnas_encontradas
        columnas_extra = columnas_encontradas - self.REQUIRED_COLUMNS
        
        error_msg = "Template inválido. "
        
        if columnas_faltantes:
            error_msg += f"Faltan columnas: {', '.join(columnas_faltantes)}. "
        
        if columnas_extra:
            error_msg += f"Columnas no reconocidas: {', '.join(columnas_extra)}. "
        
        error_msg += f"El archivo debe tener exactamente estas columnas: {', '.join(sorted(self.REQUIRED_COLUMNS))}"
        
        raise ValueError(error_msg)
    
    def _parse_fecha(self, fecha_str: str) -> Optional[datetime]:
        """
        Parsea una fecha desde string probando diferentes formatos
        """
        if not fecha_str or fecha_str.lower() in ['nan', 'null', 'none', '']:
            return None
        
        # Formatos comunes
        formatos = [
            '%Y-%m-%d',           # 2025-01-15
            '%d/%m/%Y',           # 15/01/2025
            '%d-%m-%Y',           # 15-01-2025
            '%Y/%m/%d',           # 2025/01/15
            '%d/%m/%y',           # 15/01/25
            '%d-%m-%y',           # 15-01-25
            '%Y-%m-%d %H:%M:%S',  # 2025-01-15 10:30:00
            '%d/%m/%Y %H:%M:%S',  # 15/01/2025 10:30:00
        ]
        
        for formato in formatos:
            try:
                return datetime.strptime(fecha_str, formato)
            except ValueError:
                continue
        
        # Si no se pudo parsear, retornar None
        logger.warning(f"No se pudo parsear fecha: {fecha_str}")
        return None
    
    def _convert_pandas_date(self, fecha) -> Optional[datetime]:
        """Convierte fecha de pandas a datetime"""
        if pd.isna(fecha):
            return None
        
        if isinstance(fecha, datetime):
            return fecha
        
        if isinstance(fecha, str):
            return self._parse_fecha(fecha)
        
        # Intentar convertir con pandas
        try:
            return pd.to_datetime(fecha).to_pydatetime()
        except:
            return None

