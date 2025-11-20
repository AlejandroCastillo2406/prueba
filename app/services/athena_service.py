"""
Servicio para consultas históricas usando AWS Athena
"""
import boto3
import time
from typing import List, Dict, Optional, Any
from loguru import logger
from app.interfaces.athena_service_interface import IAthenaService
from app.core.config import settings


class AthenaService(IAthenaService):
    """Servicio para ejecutar queries en AWS Athena - Solo funcionalidades esenciales"""
    
    def __init__(self):
        """Inicializa el cliente de Athena"""
        self.athena_client = boto3.client(
            'athena',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        self.database = settings.ATHENA_DATABASE
        self.table = settings.ATHENA_TABLE
        self.output_location = settings.ATHENA_OUTPUT_LOCATION
    
    def execute_query(self, query: str) -> List[Dict[str, Any]]:
        """
        Ejecuta una query en Athena y retorna los resultados
        
        Args:
            query: Query SQL a ejecutar
            
        Returns:
            Lista de diccionarios con los resultados
        """
        try:
            logger.info(f"Ejecutando query en Athena: {query[:100]}...")
            
            # Ejecutar query
            response = self.athena_client.start_query_execution(
                QueryString=query,
                QueryExecutionContext={'Database': self.database},
                ResultConfiguration={'OutputLocation': self.output_location}
            )
            
            query_execution_id = response['QueryExecutionId']
            logger.info(f"Query execution ID: {query_execution_id}")
            
            # Esperar a que termine
            while True:
                response = self.athena_client.get_query_execution(
                    QueryExecutionId=query_execution_id
                )
                status = response['QueryExecution']['Status']['State']
                
                if status in ['SUCCEEDED']:
                    break
                elif status in ['FAILED', 'CANCELLED']:
                    error_reason = response['QueryExecution']['Status'].get('StateChangeReason', 'Unknown error')
                    raise Exception(f"Query failed: {error_reason}")
                
                time.sleep(2)
            
            # Obtener resultados
            results = self.athena_client.get_query_results(
                QueryExecutionId=query_execution_id
            )
            
            logger.debug(f"Resultados obtenidos: {len(results.get('ResultSet', {}).get('Rows', []))} filas")
            
            # Procesar resultados
            rows = results['ResultSet']['Rows']
            if len(rows) <= 1:  # Solo headers o vacío
                logger.info("No hay datos en los resultados")
                return []
            
            # Obtener columnas del metadata
            column_info = results['ResultSet']['ResultSetMetadata']['ColumnInfo']
            columns = [col['Name'] for col in column_info]
            logger.debug(f"Columnas detectadas: {columns}")
            
            # Procesar datos
            data = []
            for row_idx, row in enumerate(rows[1:], 1):  # Saltar header
                row_data = {}
                for i, cell in enumerate(row['Data']):
                    if i < len(columns):
                        column_name = columns[i]
                        # Manejar diferentes tipos de datos
                        if 'VarCharValue' in cell:
                            value = cell['VarCharValue']
                        elif 'BigIntValue' in cell:
                            value = str(cell['BigIntValue'])
                        elif 'LongValue' in cell:
                            value = str(cell['LongValue'])
                        else:
                            value = ''
                        row_data[column_name] = value
                data.append(row_data)
                logger.debug(f"Fila {row_idx} procesada: {row_data}")
            
            logger.info(f"Query ejecutada exitosamente. {len(data)} resultados obtenidos")
            return data
            
        except Exception as e:
            logger.error(f"Error ejecutando query en Athena: {e}")
            raise
    
    def get_historial_rfc(self, rfc: str) -> List[Dict[str, Any]]:
        """
        Obtiene el historial completo de un RFC
        
        Args:
            rfc: RFC a consultar
            
        Returns:
            Lista con el historial del RFC
        """
        query = f"""
        SELECT 
            rfc,
            nombre_contribuyente,
            situacion_contribuyente,
            version
        FROM {self.database}.{self.table}
        WHERE rfc = '{rfc.upper().strip()}'
        ORDER BY version ASC
        """
        
        return self.execute_query(query)
    
    def repair_partitions(self) -> bool:
        """
        Repara las particiones de la tabla
        
        Returns:
            True si se ejecutó correctamente
        """
        try:
            query = f"MSCK REPAIR TABLE {self.database}.{self.table}"
            self.execute_query(query)
            logger.info("Particiones reparadas exitosamente")
            return True
        except Exception as e:
            logger.error(f"Error reparando particiones: {e}")
            return False