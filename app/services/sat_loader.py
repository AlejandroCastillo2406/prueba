"""
Servicio para cargar datos del SAT desde CSV
"""
import csv
import os
import chardet
import re
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.models.proveedor import Proveedor
from loguru import logger
from datetime import datetime
from app.core.timezone import get_mexico_time_naive, formatear_fecha_es

class SATLoader:
    """
    Servicio para cargar datos del SAT desde archivos CSV
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def _extract_sat_date(self, first_line: str) -> datetime:
        """
        Extrae la fecha de la primera línea del CSV del SAT.
        
        Args:
            first_line: Primera línea del CSV que contiene la información de fecha
            
        Returns:
            Fecha extraída o hora actual de México si no se puede extraer
        """
        try:
            # Buscar patrón de fecha en formato "31 de agosto de 2025"
            date_pattern = r'(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})'
            match = re.search(date_pattern, first_line, re.IGNORECASE)
            
            if match:
                day = int(match.group(1))
                month_name = match.group(2).lower()
                year = int(match.group(3))
                
                # Mapeo de meses en español
                months = {
                    'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4,
                    'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
                    'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
                }
                
                if month_name in months:
                    month = months[month_name]
                    fecha_lista = datetime(year, month, day)
                    logger.info(f"Fecha extraída del SAT: {formatear_fecha_es(fecha_lista)}")
                    return fecha_lista
                    
        except Exception as e:
            logger.warning(f"Error extrayendo fecha del SAT: {e}")
        
        # Si no se puede extraer, usar fecha actual
        logger.warning("No se pudo extraer fecha del SAT, usando fecha actual")
        return get_mexico_time_naive()

    def load_from_csv(self, csv_path: str) -> int:
        """
        Carga datos del SAT desde un archivo CSV.
        
        Args:
            csv_path: Ruta al archivo CSV
            
        Returns:
            Número de registros cargados
        """
        try:
            if not os.path.exists(csv_path):
                raise FileNotFoundError(f"Archivo CSV no encontrado: {csv_path}")
            
            # Detectar codificación del archivo
            with open(csv_path, 'rb') as file:
                raw_data = file.read(10000)  # Leer primeros 10KB
                encoding_result = chardet.detect(raw_data)
                detected_encoding = encoding_result.get('encoding', 'utf-8')
                confidence = encoding_result.get('confidence', 0)
                
                logger.info(f"Codificación detectada: {detected_encoding} (confianza: {confidence:.2f})")
                
                # Si la confianza es baja, probar diferentes codificaciones
                if confidence < 0.7:
                    # Lista de codificaciones a probar en orden de preferencia
                    encodings_to_try = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
                    detected_encoding = 'utf-8'  # Por defecto
                    
                    for enc in encodings_to_try:
                        try:
                            test_data = raw_data.decode(enc)
                            detected_encoding = enc
                            logger.info(f"Usando codificación: {enc}")
                            break
                        except:
                            continue
            
            registros_cargados = 0
            logger.info(f"Iniciando carga con codificación: {detected_encoding}")
            
            existing_rfcs = set()
            try:
                existing_proveedores = self.db.query(Proveedor.rfc).all()
                existing_rfcs = {p.rfc for p in existing_proveedores}
                logger.info(f"Encontrados {len(existing_rfcs)} RFCs existentes")
            except Exception as e:
                logger.warning(f"Error cargando RFCs existentes: {e}")
            
            #  Procesar en lotes 
            batch_size = 1000
            batch_data = []
            
            # Contadores para estadísticas
            duplicados_encontrados = 0
            duplicados_reemplazados = 0
            rfcs_invalidos = 0
            
            with open(csv_path, 'r', encoding=detected_encoding, errors='ignore') as file:
                # Detectar el delimitador
                sample = file.read(1024)
                file.seek(0)
                sniffer = csv.Sniffer()
                delimiter = sniffer.sniff(sample).delimiter
                
                # Leer el archivo CSV
                reader = csv.reader(file, delimiter=delimiter)
                
                # Leer primera línea para extraer fecha del SAT
                first_line = next(reader, None)
                # Convertir lista a string si es necesario
                if isinstance(first_line, list):
                    first_line = ' '.join(str(item) for item in first_line)
                fecha_lista = self._extract_sat_date(first_line) if first_line else get_mexico_time_naive()
                
                # Saltar la segunda línea (información adicional del SAT)
                next(reader, None)
                
                # Leer los headers (línea 3)
                headers = next(reader, None)
                logger.info(f"Headers detectados: {headers[:5] if headers else 'No headers'}")
                
                logger.info("Procesando registros en lotes...")
                # Conjuntos para deduplicar durante esta ejecución
                added_rfcs: set = set()
                added_hashes: set = set()
                
                for i, row in enumerate(reader, 1):
                    try:
                        # Mostrar progreso cada 1000 registros
                        if i % 1000 == 0:
                            logger.info(f"Procesados {i} registros...")
                        
                        if len(row) < 4:
                            continue
                        
                        # Mapeo directo por posición de columna
                        # Columna 0: Número
                        # Columna 1: RFC
                        # Columna 2: Nombre del Contribuyente (RAZÓN SOCIAL)
                        # Columna 3: Situación del contribuyente
                        
                        rfc = row[1].strip().upper() if len(row) > 1 else None
                        razon_social = row[2].strip() if len(row) > 2 else None
                        situacion = row[3].strip() if len(row) > 3 else None
                        
                        # Validar RFC
                        if not rfc or len(rfc) < 10:
                            continue
                        
                        # Eliminar RFCs con XXXXXXXXXXXX
                        if rfc == "XXXXXXXXXXXX" or "XXXXXXXX" in rfc:
                            logger.warning(f"🚫 RFC eliminado (formato inválido): {rfc}")
                            rfcs_invalidos += 1
                            continue
                        
                        # Verificar patrón RFC básico 
                        # RFC Persona Física: 4 letras + 6 dígitos + 3 caracteres = 13 caracteres
                        # RFC Persona Moral: 3 letras + 6 dígitos + 3 caracteres = 12 caracteres
                        # RFC puede contener símbolos como &, -, ', etc. en cualquier parte
                        rfc_valido = False
        
                        if len(rfc) in [12, 13]:
                            # Verificar que empiece con letras
                            if rfc[:3].isalpha() or rfc[:4].isalpha():
                                # Verificar que tenga 6 dígitos en el medio
                                if len(rfc) == 12:  # Persona moral: 3 letras + 6 dígitos + 3 caracteres
                                    if rfc[3:9].isdigit() and rfc[9:].isalnum():
                                        rfc_valido = True
                                elif len(rfc) == 13:  # Persona física: 4 letras + 6 dígitos + 3 caracteres
                                    if rfc[4:10].isdigit() and rfc[10:].isalnum():
                                        rfc_valido = True
        
                        # Si no pasó la validación estricta, verificar patrón más flexible con símbolos
                        if not rfc_valido and len(rfc) in [12, 13]:
                            # Verificar que empiece con letras y tenga 6 dígitos en el medio
                            if len(rfc) == 12:  # Persona moral
                                if (rfc[:3].isalpha() and 
                                    rfc[3:9].isdigit() and 
                                    len(rfc[9:]) >= 2 and 
                                    all(c.isalnum() or c in "&'-" for c in rfc[9:])):
                                    rfc_valido = True
                            elif len(rfc) == 13:  # Persona física
                                if (rfc[:4].isalpha() and 
                                    rfc[4:10].isdigit() and 
                                    len(rfc[10:]) >= 2 and 
                                    all(c.isalnum() or c in "&'-" for c in rfc[10:])):
                                    rfc_valido = True
        
                        if not rfc_valido and len(rfc) in [12, 13]:
                            # Verificar que tenga al menos 3-4 letras al inicio, 6 dígitos consecutivos, y el resto alfanumérico o símbolos permitidos
                            if len(rfc) == 12:  # Persona moral
                                if (rfc[:3].isalpha() and 
                                    rfc[3:9].isdigit() and 
                                    len(rfc[9:]) >= 2 and 
                                    all(c.isalnum() or c in "&'-" for c in rfc[9:])):
                                    rfc_valido = True
                            elif len(rfc) == 13:  # Persona física
                                if (rfc[:4].isalpha() and 
                                    rfc[4:10].isdigit() and 
                                    len(rfc[10:]) >= 2 and 
                                    all(c.isalnum() or c in "&'-" for c in rfc[10:])):
                                    rfc_valido = True
        
                        if not rfc_valido and len(rfc) in [12, 13]:
                            # Verificar que tenga al menos 3-4 letras al inicio, 6 dígitos consecutivos, y el resto alfanumérico o símbolos permitidos
                            if len(rfc) == 12:  # Persona moral
                                if (rfc[:3].isalpha() and 
                                    rfc[3:9].isdigit() and 
                                    len(rfc[9:]) >= 2 and 
                                    all(c.isalnum() or c in "&'-" for c in rfc[9:])):
                                    rfc_valido = True
                            elif len(rfc) == 13:  # Persona física
                                if (rfc[:4].isalpha() and 
                                    rfc[4:10].isdigit() and 
                                    len(rfc[10:]) >= 2 and 
                                    all(c.isalnum() or c in "&'-" for c in rfc[10:])):
                                    rfc_valido = True
        
                        # Validación mega flexible para RFCs con símbolos EN CUALQUIER PARTE (como T&D030616HY7)
                        if not rfc_valido and len(rfc) in [12, 13]:
                            # Buscar 6 dígitos consecutivos en cualquier posición
                            import re
                            digitos_match = re.search(r'\d{6}', rfc)
                            if digitos_match:
                                # Verificar que tenga al menos 1 letra al inicio
                                letras_inicio = sum(1 for c in rfc[:4] if c.isalpha())
                                if letras_inicio >= 1:
                                    # Verificar que todo el RFC contenga solo alfanuméricos y símbolos permitidos
                                    if all(c.isalnum() or c in "&'-" for c in rfc):
                                        rfc_valido = True
                                        logger.info(f"✅ RFC aceptado con símbolos: {rfc}")
        
                        if not rfc_valido:
                            logger.warning(f"🚫 RFC eliminado (patrón inválido): {rfc}")
                            rfcs_invalidos += 1
                            continue
                        
                        # Normalizar RFC
                        rfc_norm = rfc.upper().strip()
                        
                        proveedor_data = {
                            'rfc': rfc_norm,
                            'razon_social': razon_social[:500] if razon_social else f"Proveedor {rfc}",
                            'situacion_contribuyente': situacion[:50] if situacion else "No especificado",
                            'fecha_lista': fecha_lista,  # Usar fecha extraída del SAT
                            'created_at': get_mexico_time_naive(),
                            'fecha_actualizacion': get_mexico_time_naive()
                        }
                        
                        # Verificar duplicados y decidir cuál mantener
                        if rfc_norm in added_rfcs:
                            duplicados_encontrados += 1
                            # Ya existe en esta corrida, verificar si el actual tiene "En cumplimiento"
                            existing_data = next((item for item in batch_data if item['rfc'] == rfc_norm), None)
                            if existing_data:
                                # Si el existente tiene "En cumplimiento", descartarlo
                                if "en cumplimiento" in existing_data['situacion_contribuyente'].lower():
                                    duplicados_reemplazados += 1
                                    old_razon = existing_data['razon_social'][:30]
                                    old_situacion = existing_data['situacion_contribuyente']
                                    batch_data = [item for item in batch_data if item['rfc'] != rfc_norm]
                                    logger.info(f"🔄 RFC duplicado {rfc}: Se reemplaza '{old_razon}...' [{old_situacion}] con '{razon_social[:30] if razon_social else 'Sin nombre'}...' [{situacion if situacion else 'No especificado'}] (descartado por 'En cumplimiento')")
                                # Si el nuevo tiene "En cumplimiento", descartarlo
                                elif situacion and "en cumplimiento" in situacion.lower():
                                    logger.info(f"🔄 RFC duplicado {rfc}: Se mantiene el existente '{existing_data['razon_social'][:30]}...' [{existing_data['situacion_contribuyente']}] (nuevo descartado por 'En cumplimiento')")
                                    continue
                                # Si ninguno tiene "En cumplimiento", mantener el existente
                                else:
                                    logger.info(f"🔄 RFC duplicado {rfc}: Se mantiene el existente '{existing_data['razon_social'][:30]}...' [{existing_data['situacion_contribuyente']}] (sin 'En cumplimiento')")
                                    continue
                        
                        # Verificar si ya existe en BD
                        if rfc_norm in existing_rfcs:
                            duplicados_encontrados += 1
                            logger.info(f"🔄 RFC duplicado {rfc}: Ya existe en BD, se omite")
                            continue

                        batch_data.append(proveedor_data)
                        added_rfcs.add(rfc_norm)
                        registros_cargados += 1
                        
                        # Procesar lote cuando alcance el tamaño
                        if len(batch_data) >= batch_size:
                            self._insert_batch(batch_data)
                            # Actualizar cache con lo insertado para siguientes lotes
                            for item in batch_data:
                                existing_rfcs.add(item['rfc'])
                            batch_data = []
                            logger.info(f"Procesados {i} registros, {registros_cargados} nuevos")
                    
                    except Exception as e:
                        logger.warning(f"Error procesando línea {i}: {e}")
                        continue
                
                # Procesar lote final
                if batch_data:
                    self._insert_batch(batch_data)
                    for item in batch_data:
                        existing_rfcs.add(item['rfc'])
                    logger.info(f"Procesados {i} registros, {registros_cargados} nuevos")
            
            logger.info(f"Carga completada: {registros_cargados} registros nuevos desde {csv_path}")
            logger.info(f"📊 Resumen detallado de procesamiento:")
            logger.info(f"   🔄 RFCs duplicados encontrados: {duplicados_encontrados}")
            logger.info(f"   🔄 RFCs duplicados reemplazados: {duplicados_reemplazados}")
            logger.info(f"   🚫 RFCs con formato inválido eliminados: {rfcs_invalidos}")
            logger.info(f"   ✅ RFCs únicos cargados: {registros_cargados}")
            logger.info(f"   📈 Total procesados: {registros_cargados + duplicados_encontrados + rfcs_invalidos}")
            return registros_cargados
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error cargando datos del SAT: {str(e)}")
            raise
    
    def _insert_batch(self, batch_data: List[Dict[str, Any]]) -> None:
        """Inserta un lote de datos """
        try:
            self.db.bulk_insert_mappings(Proveedor, batch_data)
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error insertando lote: {e}")
            raise
    
    def _map_csv_row_to_dict(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Mapea una fila del CSV a un diccionario"""
        try:
            # Convertir row a lista de valores para procesar por posición
            values = list(row.values())
            
            # Saltar filas de encabezado o vacías
            if len(values) < 3 or not any(v for v in values if v and str(v).strip()):
                return None
                
            # Buscar RFC (patrón: 3-4 letras + 6 dígitos + 3 caracteres)
            rfc = None
            for value in values:
                if value and isinstance(value, str):
                    value = value.strip().upper()
                    # Patrón RFC: AAA010101AAA o AAAA010101AAA
                    if (len(value) >= 10 and value.isalnum() and 
                        not value.startswith('Información') and
                        not value.startswith('Listado') and
                        not value.startswith('No') and
                        not value.isdigit()):
                        # Verificar patrón RFC más específico
                        if (len(value) in [12, 13] and 
                            value[:3].isalpha() and 
                            value[3:9].isdigit() and 
                            value[9:].isalnum()):
                            rfc = value
                            break
            
            if not rfc or rfc == 'XXXXXXXXXXXX':
                return None
                
            # Buscar nombre del contribuyente (generalmente el segundo valor no vacío)
            razon_social = None
            for i, value in enumerate(values):
                if value and isinstance(value, str) and value.strip():
                    value = value.strip()
                    # Si no es el RFC, no es un número, y tiene más de 5 caracteres
                    if (value != rfc and 
                        not value.isdigit() and 
                        not value.startswith('Información') and
                        not value.startswith('Listado') and
                        not value.startswith('No') and
                        len(value) > 5 and
                        not any(word in value.lower() for word in ['definitivo', 'desvirtuado', 'sentencia', 'presunto'])):
                        razon_social = value
                        break
            
            # Buscar situación (buscar palabras clave)
            situacion = None
            for value in values:
                if value and isinstance(value, str) and value.strip():
                    value = value.strip()
                    if any(word in value.lower() for word in ['definitivo', 'desvirtuado', 'sentencia', 'presunto']):
                        situacion = value
                        break
            
            # Si no hay campo de fecha, usar la fecha actual
            fecha_lista = get_mexico_time_naive()
            if 'Fecha' in row and row['Fecha']:
                try:
                    fecha_lista = datetime.strptime(row['Fecha'], '%Y-%m-%d')
                except ValueError:
                    try:
                        fecha_lista = datetime.strptime(row['Fecha'], '%d/%m/%Y')
                    except ValueError:
                        fecha_lista = get_mexico_time_naive()
            
            # RFC en texto plano
            rfc_norm = rfc.upper().strip()
            
            return {
                'rfc': rfc_norm,
                'razon_social': razon_social,
                'situacion_contribuyente': situacion,
                'fecha_lista': fecha_lista,
                'created_at': get_mexico_time_naive(),
                'fecha_actualizacion': get_mexico_time_naive()
            }
        except Exception as e:
            logger.warning(f"Error mapeando fila: {e}")
            return None
    
    def _map_csv_row_to_proveedor(self, row: Dict[str, Any]) -> Proveedor:
        """
        Mapea una fila del CSV a un objeto Proveedor.
        
        Args:
            row: Fila del CSV como diccionario
            
        Returns:
            Objeto Proveedor
        """
        # Mapear campos comunes 
        rfc = row.get('RFC', '').strip().upper()
        razon_social = row.get('Razon Social', '').strip()
        situacion = row.get('Situacion', '').strip()
        
        # Si no hay campo de fecha, usar la fecha actual
        fecha_lista = get_mexico_time_naive()
        if 'Fecha' in row and row['Fecha']:
            try:
                fecha_lista = datetime.strptime(row['Fecha'], '%Y-%m-%d')
            except ValueError:
                try:
                    fecha_lista = datetime.strptime(row['Fecha'], '%d/%m/%Y')
                except ValueError:
                    fecha_lista = get_mexico_time_naive()
        
        return Proveedor(
            rfc=rfc,
            razon_social=razon_social,
            situacion_contribuyente=situacion,
            fecha_lista=fecha_lista
        )
    
    def get_csv_info(self, csv_path: str) -> Dict[str, Any]:
        """
        Obtiene información sobre el archivo CSV.
        
        Args:
            csv_path: Ruta al archivo CSV
            
        Returns:
            Información del archivo
        """
        try:
            if not os.path.exists(csv_path):
                raise FileNotFoundError(f"Archivo CSV no encontrado: {csv_path}")
            
            with open(csv_path, 'r', encoding='utf-8', errors='ignore') as file:
                # Detectar el delimitador
                sample = file.read(1024)
                file.seek(0)
                sniffer = csv.Sniffer()
                delimiter = sniffer.sniff(sample).delimiter
                
                reader = csv.DictReader(file, delimiter=delimiter)
                fieldnames = reader.fieldnames
                
                # Contar líneas
                file.seek(0)
                line_count = sum(1 for line in file) - 1  # -1 para excluir header
            
            return {
                "archivo": csv_path,
                "delimitador": delimiter,
                "campos": fieldnames,
                "total_registros": line_count,
                "tamaño_archivo": os.path.getsize(csv_path)
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo información del CSV: {str(e)}")
            raise
