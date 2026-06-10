import psycopg2
from config import Config

class Database:
    """Classe para gerenciamento da conexão com o banco de dados"""
    
    def __init__(self, municipio):
        """
        Inicializa a classe de banco de dados
        
        Args:
            municipio (str): Nome do município para selecionar a base de dados
        """
        self.municipio = municipio
        
    def get_connection(self):
        """
        Retorna uma nova conexão com o banco de dados configurado para o município
        
        Returns:
            psycopg2.extensions.connection: Conexão com o banco de dados
        """
        if self.municipio in Config.DB_CONFIGS:
            return psycopg2.connect(**Config.DB_CONFIGS[self.municipio])
        else:
            raise ValueError(f"Município não reconhecido: {self.municipio}")
