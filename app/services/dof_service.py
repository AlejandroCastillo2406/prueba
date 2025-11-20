"""
Servicio para scraping y procesamiento del DOF (Diario Oficial de la Federación)
Artículos relacionados con el artículo 69-B del Código Fiscal de la Federación
"""
import requests
from bs4 import BeautifulSoup
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from loguru import logger
import re
import PyPDF2
import io

from app.models.dof_articulo import DOFArticulo
from app.models.dof_contribuyente import DOFContribuyente
from app.core.config import settings


class DOFService:
    """Servicio para extraer y procesar artículos del DOF"""
    
    def __init__(self):
        self.base_url = settings.DOF_URL
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    def procesar_dof_fecha(self, db: Session, fecha: Optional[date] = None) -> Dict[str, Any]:
        """
        Procesa el DOF de una fecha específica buscando artículos 69-B
        Extrae la fecha real de publicación del HTML del DOF
        
        IMPORTANTE: Si detecta una versión diferente (fecha diferente) del DOF,
        vacía las tablas dof_articulos y dof_contribuyentes antes de procesar.
        
        Args:
            db: Sesión de base de datos
            fecha: Fecha a procesar (por defecto hoy)
            
        Returns:
            Diccionario con resultados del procesamiento
        """
        try:
            if fecha is None:
                fecha = date.today()
            
            # Formatear fecha para URL (dd-mm-yyyy)
            fecha_str = fecha.strftime("%d-%m-%Y")
            url = f"{self.base_url}/welcome/{fecha_str}"
            
            logger.info(f"Descargando DOF desde URL: {url}")
            
            # Obtener página principal
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            # Parsear HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extraer fecha real de publicación del DOF desde la página
            fecha_publicacion_real = self._extraer_fecha_publicacion_dof(soup, fecha)
            
            # Usar la fecha real extraída del DOF
            if fecha_publicacion_real != fecha:
                logger.info(f"Fecha en URL: {fecha}, Fecha real de publicación DOF: {fecha_publicacion_real}")
                fecha_procesar = fecha_publicacion_real
            else:
                fecha_procesar = fecha
            
            # VERIFICAR SI HAY UNA VERSIÓN DIFERENTE DEL DOF EN LA BD
            # Si hay artículos con fechas diferentes, vaciar las tablas
            # Normalizar fecha_procesar a date
            if isinstance(fecha_procesar, datetime):
                fecha_procesar_date = fecha_procesar.date()
            else:
                fecha_procesar_date = fecha_procesar
            
            # Obtener la fecha más reciente de los artículos existentes
            articulo_mas_reciente = db.query(DOFArticulo).order_by(DOFArticulo.fecha_publicacion.desc()).first()
            
            if articulo_mas_reciente:
                fecha_existente = articulo_mas_reciente.fecha_publicacion.date()
                
                # Si la fecha del DOF a procesar es diferente a la existente, vaciar tablas
                if fecha_existente != fecha_procesar_date:
                    logger.warning(f"⚠️ DETECTADA VERSIÓN DIFERENTE DEL DOF")
                    logger.warning(f"   Fecha existente en BD: {fecha_existente}")
                    logger.warning(f"   Fecha nueva a procesar: {fecha_procesar_date}")
                    logger.warning(f"   Vaciando tablas dof_articulos y dof_contribuyentes...")
                    
                    # Vaciar tabla de contribuyentes primero (por la FK)
                    contribuyentes_eliminados = db.query(DOFContribuyente).delete()
                    logger.info(f"   Eliminados {contribuyentes_eliminados} contribuyentes del DOF")
                    
                    # Vaciar tabla de artículos
                    articulos_eliminados = db.query(DOFArticulo).delete()
                    logger.info(f"   Eliminados {articulos_eliminados} artículos del DOF")
                    
                    # Commit para confirmar la eliminación
                    db.commit()
                    logger.info(f"✅ Tablas DOF vaciadas. Procesando nueva versión...")
                else:
                    logger.info(f"✅ Fecha del DOF coincide con la existente ({fecha_procesar_date}). No se vacían las tablas.")
            else:
                logger.info(f"ℹ️ No hay artículos previos en la BD. Procesando primera versión del DOF.")
            
            # Buscar artículos relacionados con 69-B usando la fecha real
            articulos_69b = self._encontrar_articulos_69b(soup, fecha_procesar)
            
            logger.info(f"Encontrados {len(articulos_69b)} artículos relacionados con 69-B")
            
            # Procesar cada artículo
            articulos_nuevos = 0
            articulos_existentes = 0
            articulos_procesados = 0
            errores = []
            
            for articulo_data in articulos_69b:
                try:
                    # Verificar si ya existe
                    existe = db.query(DOFArticulo).filter(
                        DOFArticulo.numero_oficio == articulo_data['numero_oficio'],
                        DOFArticulo.fecha_publicacion == articulo_data['fecha_publicacion']
                    ).first()
                    
                    if existe:
                        # Si ya existe y está procesado, contar como procesado
                        if existe.procesado == 1:
                            logger.info(f"Artículo {articulo_data['numero_oficio']} ya existe y fue procesado anteriormente")
                            articulos_procesados += 1
                        else:
                            logger.info(f"Artículo {articulo_data['numero_oficio']} ya existe pero no está procesado (estado: {existe.procesado})")
                            articulos_existentes += 1
                        continue
                    
                    # Crear registro del artículo
                    nuevo_articulo = DOFArticulo(
                        numero_oficio=articulo_data['numero_oficio'],
                        fecha_publicacion=articulo_data['fecha_publicacion'],
                        titulo=articulo_data['titulo'],
                        tipo_lista=articulo_data['tipo_lista'],
                        url_pdf=articulo_data.get('url_pdf'),
                        procesado=0  # Pendiente de procesamiento
                    )
                    
                    db.add(nuevo_articulo)
                    db.flush()  # Para obtener el ID
                    
                    articulos_nuevos += 1
                    
                    # Intentar procesar el PDF si está disponible
                    if articulo_data.get('url_pdf'):
                        try:
                            self._procesar_pdf_articulo(db, nuevo_articulo, articulo_data['url_pdf'])
                            articulos_procesados += 1
                        except Exception as e:
                            logger.error(f"Error procesando PDF {articulo_data['url_pdf']}: {str(e)}")
                            nuevo_articulo.procesado = 2  # Error
                            nuevo_articulo.error_mensaje = str(e)
                            errores.append({
                                'oficio': articulo_data['numero_oficio'],
                                'error': str(e)
                            })
                    
                except Exception as e:
                    logger.error(f"Error procesando artículo {articulo_data.get('numero_oficio', 'desconocido')}: {str(e)}")
                    errores.append({
                        'oficio': articulo_data.get('numero_oficio', 'desconocido'),
                        'error': str(e)
                    })
            
            db.commit()
            
            # Usar la fecha real de publicación para el resultado 
            fecha_resultado = fecha_procesar.strftime("%d-%m-%Y")
            
            resultado = {
                'fecha': fecha_resultado,
                'articulos_encontrados': len(articulos_69b),
                'articulos_nuevos': articulos_nuevos,
                'articulos_existentes': articulos_existentes,
                'articulos_procesados': articulos_procesados,
                'errores': errores
            }
            
            logger.info(f"Procesamiento completado: {resultado}")
            return resultado
            
        except Exception as e:
            logger.error(f"Error en procesar_dof_fecha: {str(e)}")
            db.rollback()
            raise
    
    
    def _extraer_fecha_publicacion_dof(self, soup: BeautifulSoup, fecha_fallback: date) -> date:
        """
        Extrae la fecha real de publicación del DOF desde el HTML de la página principal
        ANTES de abrir cualquier artículo.
        
        El DOF muestra la fecha en el encabezado/título de la página principal
        
        Args:
            soup: BeautifulSoup object con el HTML de la página principal
            fecha_fallback: Fecha a usar si no se puede extraer la fecha real
            
        Returns:
            Fecha real de publicación del DOF
        """
        try:
            meses_es = {
                'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4,
                'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
                'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
            }
            
            # PRIORIDAD 1: Buscar en el título de la página (tag <title>)
            title_tag = soup.find('title')
            if title_tag:
                texto_title = title_tag.get_text()
                logger.debug(f"Buscando fecha en <title>: {texto_title[:100]}")
                for mes_es, mes_num in meses_es.items():
                    patrones = [
                        rf'del\s+(\d{{1,2}})\s+de\s+{mes_es}\s+de\s+(\d{{4}})',
                        rf'(\d{{1,2}})\s+de\s+{mes_es}\s+de\s+(\d{{4}})',
                        rf'(\d{{1,2}})\s+de\s+{mes_es}\s+de\s+(\d{{4}})'
                    ]
                    for patron in patrones:
                        match = re.search(patron, texto_title, re.IGNORECASE)
                        if match:
                            dia = int(match.group(1))
                            año = int(match.group(2))
                            try:
                                fecha_encontrada = date(año, mes_num, dia)
                                logger.info(f"✅ Fecha de publicación DOF extraída del <title>: {fecha_encontrada}")
                                return fecha_encontrada
                            except ValueError:
                                continue
            
            # PRIORIDAD 2: Buscar en encabezados principales (h1, h2) - normalmente están en el header
            for tag in ['h1', 'h2']:
                titulos = soup.find_all(tag, limit=5)  # Solo los primeros 5
                for titulo in titulos:
                    texto_titulo = titulo.get_text(strip=True)
                    if not texto_titulo or len(texto_titulo) > 200:  # Evitar textos muy largos
                        continue
                    
                    logger.debug(f"Buscando fecha en <{tag}>: {texto_titulo[:80]}")
                    
                    # Buscar patrón: "del DD de MES de YYYY" o "DD de MES de YYYY"
                    for mes_es, mes_num in meses_es.items():
                        patrones = [
                            rf'del\s+(\d{{1,2}})\s+de\s+{mes_es}\s+de\s+(\d{{4}})',
                            rf'(\d{{1,2}})\s+de\s+{mes_es}\s+de\s+(\d{{4}})'
                        ]
                        for patron in patrones:
                            match = re.search(patron, texto_titulo, re.IGNORECASE)
                            if match:
                                dia = int(match.group(1))
                                año = int(match.group(2))
                                try:
                                    fecha_encontrada = date(año, mes_num, dia)
                                    logger.info(f"✅ Fecha de publicación DOF extraída del <{tag}>: {fecha_encontrada}")
                                    return fecha_encontrada
                                except ValueError:
                                    continue
            
            # PRIORIDAD 3: Buscar en elementos del header/encabezado (header, nav, div con clases específicas)
            # Solo buscar en los primeros elementos, no en todo el contenido
            elementos_header = []
            
            # Buscar tag <header>
            header_tag = soup.find('header')
            if header_tag:
                elementos_header.append(header_tag)
            
            # Buscar divs con clases que indiquen encabezado
            divs_header = soup.find_all('div', class_=lambda x: x and any(
                palabra in str(x).lower() 
                for palabra in ['header', 'cabecera', 'encabezado', 'title', 'fecha', 'edicion', 'matutina', 'vespertina']
            ), limit=10)
            elementos_header.extend(divs_header)
            
            # Buscar en elementos del header
            for elem in elementos_header:
                texto_elem = elem.get_text(strip=True)
                if not texto_elem or len(texto_elem) > 300:  # Limitar tamaño
                    continue
                
                logger.debug(f"Buscando fecha en header: {texto_elem[:80]}")
                
                for mes_es, mes_num in meses_es.items():
                    patron = rf'(\d{{1,2}})\s+de\s+{mes_es}\s+de\s+(\d{{4}})'
                    match = re.search(patron, texto_elem, re.IGNORECASE)
                    if match:
                        dia = int(match.group(1))
                        año = int(match.group(2))
                        try:
                            fecha_encontrada = date(año, mes_num, dia)
                            logger.info(f"✅ Fecha de publicación DOF extraída del header: {fecha_encontrada}")
                            return fecha_encontrada
                        except ValueError:
                            continue
            
            # PRIORIDAD 4: Buscar en los primeros 3000 caracteres del texto (donde normalmente está la fecha de publicación)
            # Esto evita capturar fechas mencionadas en el contenido de los artículos
            texto_completo = soup.get_text()
            texto_inicial = texto_completo[:3000]  # Solo los primeros caracteres
            
            logger.debug(f"Buscando fecha en los primeros 3000 caracteres del texto...")
            
            fechas_encontradas = []
            for mes_es, mes_num in meses_es.items():
                patron = rf'(\d{{1,2}})\s+de\s+{mes_es}\s+de\s+(\d{{4}})'
                matches = re.findall(patron, texto_inicial, re.IGNORECASE)
                for match in matches:
                    dia = int(match[0])
                    año = int(match[1])
                    try:
                        fecha_candidata = date(año, mes_num, dia)
                        fechas_encontradas.append(fecha_candidata)
                    except ValueError:
                        continue
            
            if fechas_encontradas:
                # Usar la primera fecha encontrada en el texto inicial (más probable que sea la fecha de publicación)
                fecha_encontrada = fechas_encontradas[0]
                logger.info(f"✅ Fecha de publicación DOF extraída del texto inicial: {fecha_encontrada}")
                return fecha_encontrada
            
            # Si no se encuentra, usar la fecha de fallback
            logger.warning(f"⚠️ No se pudo extraer fecha del HTML del DOF, usando fecha de fallback: {fecha_fallback}")
            return fecha_fallback
            
        except Exception as e:
            logger.warning(f"Error extrayendo fecha de publicación DOF: {str(e)}")
            import traceback
            logger.debug(traceback.format_exc())
            return fecha_fallback
    
    def _encontrar_articulos_69b(self, soup: BeautifulSoup, fecha: date) -> List[Dict[str, Any]]:
        """
        Busca artículos relacionados con el artículo 69-B en el HTML del DOF
        
        Args:
            soup: BeautifulSoup object con el HTML
            fecha: Fecha de publicación
            
        Returns:
            Lista de artículos encontrados
        """
        articulos = []
        
        # Buscar todos los links que mencionen "69-B"
        links = soup.find_all('a', href=True)
        
        for link in links:
            texto = link.get_text(strip=True)
            
            # Verificar si el texto menciona 69-B
            if '69-B' in texto or '69 - B' in texto.upper():
                # Extraer número de oficio
                match_oficio = re.search(r'(\d{3}-\d{2}-\d{4}-\d+)', texto)
                
                if match_oficio:
                    numero_oficio = match_oficio.group(1)
                    
                    # Determinar tipo de lista
                    tipo_lista = self._determinar_tipo_lista(texto)
                    
                    # Obtener URL del PDF
                    href = link.get('href', '')
                    url_pdf = None
                    if href:
                        if href.startswith('http'):
                            url_pdf = href
                        elif href.startswith('/'):
                            url_pdf = f"{self.base_url}{href}"
                    
                    articulo = {
                        'numero_oficio': numero_oficio,
                        'fecha_publicacion': datetime.combine(fecha, datetime.min.time()),
                        'titulo': texto,
                        'tipo_lista': tipo_lista,
                        'url_pdf': url_pdf
                    }
                    
                    articulos.append(articulo)
                    logger.info(f"Encontrado artículo: {numero_oficio} - {tipo_lista}")
        
        return articulos
    
    def _determinar_tipo_lista(self, texto: str) -> str:
        """Determina el tipo de lista según el texto del título"""
        texto_lower = texto.lower()
        
        if 'sentencia favorable' in texto_lower or 'sentencia' in texto_lower:
            return 'sentencia_favorable'
        elif 'definitivo' in texto_lower:
            return 'definitivo'
        elif 'desvirtu' in texto_lower:
            return 'desvirtuado'
        elif 'presun' in texto_lower:
            return 'presuncion'
        else:
            return 'otro'
    
    def _procesar_pdf_articulo(self, db: Session, articulo: DOFArticulo, url_pdf: str) -> None:
        """
        Descarga y procesa el contenido del DOF para extraer contribuyentes
        El DOF usa páginas HTML con iframes que contienen tablas HTML
        
        Args:
            db: Sesión de base de datos
            articulo: Registro del artículo en BD
            url_pdf: URL del artículo (puede ser HTML con iframe)
        """
        try:
            logger.info(f"Descargando contenido: {url_pdf}")
            
            # Descargar contenido principal
            response = requests.get(url_pdf, headers=self.headers, timeout=60)
            response.raise_for_status()
            
            # Verificar si es HTML (que es lo esperado)
            content_type = response.headers.get('content-type', '').lower()
            
            if 'text/html' not in content_type:
                logger.warning(f"Content-Type inesperado: {content_type}")
            
            # Parsear HTML principal
            soup_principal = BeautifulSoup(response.content, 'html.parser')
            
            # Buscar iframe
            iframe = soup_principal.find('iframe')
            if not iframe:
                raise ValueError("No se encontró iframe en la página principal")
            
            # Obtener URL del iframe
            iframe_src = iframe.get('src', '').strip()
            if not iframe_src:
                raise ValueError("El iframe no tiene atributo src")
            
            # Convertir a URL absoluta si es relativa
            from urllib.parse import urlparse, urljoin
            if iframe_src.startswith('http'):
                url_iframe = iframe_src
            elif iframe_src.startswith('//'):
                parsed = urlparse(url_pdf)
                url_iframe = f"{parsed.scheme}:{iframe_src}"
            elif iframe_src.startswith('/'):
                parsed = urlparse(url_pdf)
                url_iframe = f"{parsed.scheme}://{parsed.netloc}{iframe_src}"
            else:
                url_iframe = urljoin(url_pdf, iframe_src)
            
            logger.info(f"Descargando contenido del iframe: {url_iframe}")
            
            # Descargar contenido del iframe
            response_iframe = requests.get(url_iframe, headers=self.headers, timeout=60)
            response_iframe.raise_for_status()
            
            # Parsear HTML del iframe
            soup_iframe = BeautifulSoup(response_iframe.content, 'html.parser')
            
            # Extraer contribuyentes de las tablas HTML
            contribuyentes = self._extraer_contribuyentes_de_tablas_html(soup_iframe, articulo.tipo_lista)
            
            if not contribuyentes:
                raise ValueError("No se encontraron contribuyentes en las tablas HTML")
            
            # Guardar contribuyentes en la BD
            for contrib in contribuyentes:
                nuevo_contrib = DOFContribuyente(
                    dof_articulo_id=articulo.id,
                    rfc=contrib['rfc'],
                    razon_social=contrib['razon_social'],
                    situacion_contribuyente=contrib['situacion']
                )
                db.add(nuevo_contrib)
            
            # Actualizar artículo
            articulo.total_rfcs = len(contribuyentes)
            articulo.procesado = 1  # Procesado exitosamente
            
            db.flush()
            
            logger.info(f"Extraídos {len(contribuyentes)} contribuyentes de las tablas HTML")
            
        except Exception as e:
            logger.error(f"Error procesando artículo: {str(e)}")
            articulo.procesado = 2  # Error
            articulo.error_mensaje = str(e)
            raise
    
    def _extraer_url_pdf_de_html(self, html_content: bytes, base_url: str) -> Optional[str]:
        """
        Extrae la URL del PDF desde un HTML que contiene un iframe
        El DOF usa URLs como: https://sidof.segob.gob.mx/notas/XXXXX
        que contienen un iframe con el PDF real
        
        Args:
            html_content: Contenido HTML
            base_url: URL base para resolver URLs relativas
            
        Returns:
            URL del PDF o None si no se encuentra
        """
        try:
            from urllib.parse import urlparse, urljoin
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Buscar iframe (prioridad 1)
            iframes = soup.find_all('iframe')
            for iframe in iframes:
                src = iframe.get('src', '').strip()
                if src:
                    # Limpiar src de espacios y caracteres especiales
                    src = src.replace('\\', '').strip('"\'')
                    
                    # Convertir a URL absoluta
                    if src.startswith('http'):
                        logger.info(f"Encontrado iframe con URL absoluta: {src}")
                        return src
                    elif src.startswith('//'):
                        # URL protocol-relative
                        parsed = urlparse(base_url)
                        return f"{parsed.scheme}:{src}"
                    elif src.startswith('/'):
                        # URL absoluta relativa al dominio
                        parsed = urlparse(base_url)
                        return f"{parsed.scheme}://{parsed.netloc}{src}"
                    else:
                        # URL relativa
                        return urljoin(base_url, src)
            
            # Buscar object/embed tags (prioridad 2)
            for tag_name in ['object', 'embed']:
                tags = soup.find_all(tag_name)
                for tag in tags:
                    data = tag.get('data', '') or tag.get('src', '')
                    if data and (data.endswith('.pdf') or 'pdf' in data.lower()):
                        if data.startswith('http'):
                            return data
                        else:
                            return urljoin(base_url, data)
            
            # Buscar links a PDF (prioridad 3)
            links = soup.find_all('a', href=True)
            for link in links:
                href = link.get('href', '').strip()
                if href and (href.endswith('.pdf') or 'pdf' in href.lower() or '/pdf/' in href):
                    if href.startswith('http'):
                        logger.info(f"Encontrado link PDF: {href}")
                        return href
                    else:
                        full_url = urljoin(base_url, href)
                        logger.info(f"Encontrado link PDF relativo: {full_url}")
                        return full_url
            
            # Buscar en atributos data-* (prioridad 4)
            for tag in soup.find_all(True):
                for attr_name, attr_value in tag.attrs.items():
                    if isinstance(attr_value, str) and ('pdf' in attr_value.lower() or '.pdf' in attr_value):
                        if attr_value.startswith('http'):
                            return attr_value
                        elif attr_value.startswith('/'):
                            parsed = urlparse(base_url)
                            return f"{parsed.scheme}://{parsed.netloc}{attr_value}"
            
            # Buscar en scripts JavaScript (prioridad 5)
            scripts = soup.find_all('script')
            for script in scripts:
                script_content = script.string or ''
                # Buscar URLs de PDF en JavaScript (más flexible)
                patterns = [
                    r'["\']([^"\']*\.pdf[^"\']*)["\']',
                    r'src\s*[:=]\s*["\']([^"\']+)["\']',
                    r'url\s*[:=]\s*["\']([^"\']+\.pdf[^"\']*)["\']',
                    r'["\']([^"\']*\/pdf\/[^"\']*)["\']'
                ]
                
                for pattern in patterns:
                    matches = re.findall(pattern, script_content, re.IGNORECASE)
                    for match in matches:
                        if 'pdf' in match.lower() or match.endswith('.pdf'):
                            if match.startswith('http'):
                                return match
                            elif match.startswith('/'):
                                parsed = urlparse(base_url)
                                return f"{parsed.scheme}://{parsed.netloc}{match}"
                            else:
                                return urljoin(base_url, match)
            
            # Si no se encuentra, intentar construir URL basada en el patrón del DOF
            # El DOF puede usar URLs como: /documentos/XXXXX.pdf o /notas/XXXXX/documento.pdf
            logger.warning(f"No se encontró PDF en HTML, intentando construir URL...")
            parsed = urlparse(base_url)
            nota_id = base_url.split('/')[-1]
            
            # Intentar diferentes patrones comunes del DOF
            posibles_urls = [
                f"{parsed.scheme}://{parsed.netloc}/documentos/{nota_id}.pdf",
                f"{parsed.scheme}://{parsed.netloc}/notas/{nota_id}/documento.pdf",
                f"{parsed.scheme}://{parsed.netloc}/pdf/{nota_id}.pdf",
                f"{parsed.scheme}://{parsed.netloc}/notas/{nota_id}.pdf",
            ]
            
            # Probar las URLs posibles
            for url_candidata in posibles_urls:
                try:
                    test_response = requests.head(url_candidata, headers=self.headers, timeout=5)
                    if test_response.status_code == 200:
                        content_type = test_response.headers.get('content-type', '').lower()
                        if 'pdf' in content_type:
                            logger.info(f"URL de PDF encontrada por prueba: {url_candidata}")
                            return url_candidata
                except:
                    continue
            
            return None
            
        except Exception as e:
            logger.error(f"Error extrayendo URL de PDF del HTML: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def _extraer_contribuyentes_de_tablas_html(self, soup: BeautifulSoup, tipo_lista: str) -> List[Dict[str, str]]:
        """
        Extrae RFCs y razones sociales de las tablas HTML dentro del iframe
        Agrupa todas las tablas del mismo apartado y las procesa juntas
        Si no encuentra apartados, solo toma la última tabla
        
        Args:
            soup: BeautifulSoup object con el HTML del iframe
            tipo_lista: Tipo de lista (para determinar la situación)
            
        Returns:
            Lista de contribuyentes extraídos
        """
        contribuyentes = []
        
        # Mapear tipo de lista a situación
        situacion_map = {
            'presuncion': 'Presunto',
            'desvirtuado': 'Desvirtuado',
            'definitivo': 'Definitivo',
            'sentencia_favorable': 'Sentencia favorable'
        }
        situacion = situacion_map.get(tipo_lista, 'Otro')
        
        # Buscar todas las tablas en el HTML
        tablas = soup.find_all('table')
        
        if not tablas:
            logger.warning("No se encontraron tablas en el HTML del iframe")
            return contribuyentes
        
        logger.info(f"Encontradas {len(tablas)} tablas en el HTML")
        
        # Buscar apartados en el HTML
        apartados_encontrados = []
        texto_completo = soup.get_text()
        
        # Buscar "Apartado A", "Apartado B", etc.
        patron_apartado = re.compile(r'Apartado\s+([A-Z])', re.IGNORECASE)
        matches = patron_apartado.findall(texto_completo)
        
        if matches:
            apartados_encontrados = [m.upper() for m in matches]
            logger.info(f"Encontrados apartados: {apartados_encontrados}")
        
        # Si hay apartados, agrupar todas las tablas del último apartado
        if apartados_encontrados:
            ultimo_apartado = apartados_encontrados[-1]
            logger.info(f"Usando último apartado encontrado: {ultimo_apartado}")
            
            # Agrupar todas las tablas que pertenecen al último apartado
            tablas_apartado = []
            current_apartado = None
            
            # Buscar el apartado antes de cada tabla
            for tabla in tablas:
                # Buscar apartado más cercano antes de esta tabla
                apartado_encontrado = self._find_apartado_for_table(tabla, soup)
                
                if apartado_encontrado:
                    current_apartado = apartado_encontrado['letra']
                
                # Si la tabla pertenece al último apartado, agregarla
                if current_apartado == ultimo_apartado:
                    tablas_apartado.append(tabla)
            
            # Si no se encontraron tablas específicas del apartado, buscar todas después del último apartado
            if not tablas_apartado:
                logger.warning(f"No se encontraron tablas específicas para el apartado {ultimo_apartado}, buscando todas las tablas después del último apartado")
                # Buscar todas las tablas después del último apartado
                encontrado_ultimo_apartado = False
                for tabla in tablas:
                    apartado_tabla = self._find_apartado_for_table(tabla, soup)
                    if apartado_tabla and apartado_tabla['letra'] == ultimo_apartado:
                        encontrado_ultimo_apartado = True
                    if encontrado_ultimo_apartado:
                        # Agregar todas las tablas después del último apartado hasta encontrar otro apartado
                        apartado_siguiente = self._find_apartado_for_table(tabla, soup)
                        if apartado_siguiente and apartado_siguiente['letra'] != ultimo_apartado:
                            break
                        tablas_apartado.append(tabla)
                
                # Si aún no hay tablas, usar todas
                if not tablas_apartado:
                    logger.warning("No se pudieron encontrar tablas del último apartado, usando todas las tablas")
                    tablas_apartado = tablas
        else:
            # Si no hay apartados, usar solo la última tabla
            logger.info("No se encontraron apartados, usando solo la última tabla")
            tablas_apartado = [tablas[-1]] if tablas else []
        
        # Extraer contribuyentes de todas las tablas del apartado (procesarlas juntas)
        logger.info(f"Procesando {len(tablas_apartado)} tabla(s) del apartado")
        
        for tabla_idx, tabla in enumerate(tablas_apartado):
            try:
                contribuyentes_tabla = self._extraer_rfcs_de_tabla(tabla, situacion)
                
                # Agregar contribuyentes únicos (evitar duplicados por RFC)
                for contrib in contribuyentes_tabla:
                    if not any(c['rfc'] == contrib['rfc'] for c in contribuyentes):
                        contribuyentes.append(contrib)
                
                logger.info(f"Tabla {tabla_idx + 1}: Extraídos {len(contribuyentes_tabla)} contribuyentes")
                        
            except Exception as e:
                logger.error(f"Error extrayendo datos de tabla {tabla_idx + 1}: {str(e)}")
                continue
        
        logger.info(f"Total extraídos: {len(contribuyentes)} contribuyentes de {len(tablas_apartado)} tabla(s)")
        return contribuyentes
    
    def _find_apartado_for_table(self, table, soup: BeautifulSoup) -> Optional[Dict[str, str]]:
        """
        Encuentra el apartado al que pertenece una tabla.
        Busca el apartado más cercano ANTES de esta tabla.
        
        Args:
            table: Elemento de tabla HTML
            soup: BeautifulSoup object del documento completo
            
        Returns:
            Diccionario con 'letra' (A, B, C, etc.) y 'text' (texto completo del apartado), o None
        """
        # Buscar el apartado más cercano ANTES de esta tabla
        prev_elements = table.find_all_previous(['h1', 'h2', 'h3', 'h4', 'h5', 'p', 'div', 'strong', 'b'], limit=300)
        
        # Prioridad 1: Buscar "Apartado A", "Apartado B", etc. (el más cercano)
        for elem in prev_elements:
            text = elem.get_text(strip=True)
            if not text:
                continue
            
            # Buscar "Apartado A", "Apartado B", etc.
            apartado_match = re.search(r'Apartado\s+([A-Z])', text, re.IGNORECASE)
            if apartado_match:
                apartado_letra = apartado_match.group(1).upper()
                # Limpiar texto del apartado
                apartado_text = re.sub(r'\s+', ' ', text).strip()
                return {
                    'letra': apartado_letra,
                    'text': apartado_text
                }
        
        # No se encontró apartado
        return None
    
    def _extraer_rfcs_de_tabla(self, tabla, situacion: str) -> List[Dict[str, str]]:
        """
        Extrae RFCs y razones sociales de una tabla HTML específica
        Basado en el script de referencia que busca RFCs y razones sociales en las celdas
        
        Args:
            tabla: BeautifulSoup table object
            situacion: Situación del contribuyente
            
        Returns:
            Lista de contribuyentes extraídos de la tabla
        """
        contribuyentes = []
        
        try:
            # Buscar todas las filas (tr) en la tabla
            filas = tabla.find_all('tr')
            
            for fila in filas:
                # Buscar todas las celdas (td o th) en la fila
                celdas = fila.find_all(['td', 'th'])
                
                if len(celdas) < 1:
                    continue
                
                # Extraer texto de todas las celdas
                valores = []
                for celda in celdas:
                    texto = celda.get_text(separator=' ', strip=True)
                    # Limpiar espacios múltiples
                    texto = re.sub(r'\s+', ' ', texto).strip()
                    if texto:
                        valores.append(texto)
                
                if not valores:
                    continue
                
                # Buscar RFC en los valores
                rfc = None
                razon_social = None
                
                for i, valor in enumerate(valores):
                    texto = str(valor).strip().upper()
                    if not texto:
                        continue
                    
                    # Buscar RFC (patrón: 12-13 caracteres alfanuméricos)
                    # Formato: AAA######AAA o AAAA######AAA
                    if re.match(r'^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{2,3}$', texto):
                        rfc = texto.strip()
                        # Buscar razón social en las siguientes celdas o en la misma celda después del RFC
                        # La razón social puede estar en la misma celda después del RFC o en las siguientes
                        for j in range(i + 1, min(i + 3, len(valores))):
                            texto_razon = valores[j].strip()
                            if (texto_razon and 
                                len(texto_razon) > 5 and 
                                not re.match(r'^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{2,3}$', texto_razon.upper()) and
                                'APARTADO' not in texto_razon.upper() and
                                'RFC' not in texto_razon.upper() and
                                'INFORMACIÓN' not in texto_razon.upper() and
                                'LISTADO' not in texto_razon.upper() and
                                'NO' not in texto_razon.upper()[:2]):
                                razon_social = texto_razon
                                break
                        
                        # Si no se encontró en las siguientes celdas, buscar en la misma celda
                        if not razon_social:
                            # Extraer texto después del RFC en la misma celda
                            texto_completo = valor
                            match_rfc = re.search(r'([A-ZÑ&]{3,4}\d{6}[A-Z0-9]{2,3})', texto_completo, re.IGNORECASE)
                            if match_rfc:
                                texto_restante = texto_completo.replace(match_rfc.group(1), '').strip()
                                if texto_restante and len(texto_restante) > 5:
                                    razon_social = texto_restante
                        
                        break
                
                # Si encontramos RFC, agregar contribuyente
                if rfc:
                    # Si no encontramos razón social, usar vacío
                    if not razon_social:
                        # Buscar cualquier texto que no sea RFC en las celdas
                        for valor in valores:
                            texto_razon = str(valor).strip()
                            if (texto_razon and 
                                len(texto_razon) > 5 and 
                                not re.match(r'^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{2,3}$', texto_razon.upper()) and
                                texto_razon.upper() != rfc and
                                'APARTADO' not in texto_razon.upper() and
                                'RFC' not in texto_razon.upper() and
                                'INFORMACIÓN' not in texto_razon.upper() and
                                'LISTADO' not in texto_razon.upper()):
                                razon_social = texto_razon
                                break
                    
                    # Limpiar razón social
                    if razon_social:
                        razon_social_limpia = re.sub(r'\s+', ' ', razon_social).strip()
                        # Limitar longitud
                        razon_social_limpia = razon_social_limpia[:500]
                    else:
                        razon_social_limpia = ''
                    
                    # Agregar contribuyente (aunque no tenga razón social)
                    contribuyentes.append({
                        'rfc': rfc,
                        'razon_social': razon_social_limpia,
                        'situacion': situacion
                    })
                    logger.debug(f"Extraído: RFC={rfc}, Razón Social={razon_social_limpia or 'N/A'}")
        
        except Exception as e:
            logger.error(f"Error extrayendo RFCs de tabla: {str(e)}")
            import traceback
            logger.debug(traceback.format_exc())
        
        return contribuyentes

