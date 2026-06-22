import os
import json

class ConfigMeta(type):
    @property
    def DB_CONFIGS(cls):
        return cls.load_db_configs()

class Config(metaclass=ConfigMeta):
    """Configurações do sistema"""
    CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'db_configs.json')
    
    @classmethod
    def load_db_configs(cls):
        if not os.path.exists(cls.CONFIG_PATH):
            # Fallback/Default config
            defaults = {
                'Viradouro': {
                    "host": "dpg-d7jn378sfn5c738s2veg-a.virginia-postgres.render.com",
                    "port": "5432",
                    "dbname": "somos_educa_26_vd",
                    "user": "somos_educa_26_rp_user",
                    "password": "mPaPHRDIeuGiHxV3sNKnXH3N1BlmF4Ry",
                    "sslmode": "require"
                },
                'Rio Pardo': {
                    "host": "dpg-d7jn378sfn5c738s2veg-a.virginia-postgres.render.com",
                    "port": "5432",
                    "dbname": "somos_educa_26_rp",
                    "user": "somos_educa_26_rp_user",
                    "password": "mPaPHRDIeuGiHxV3sNKnXH3N1BlmF4Ry",
                    "sslmode": "require"
                }
            }
            cls.save_db_configs(defaults)
            return defaults
        try:
            with open(cls.CONFIG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Erro ao carregar db_configs.json: {e}")
            return {}

    @classmethod
    def save_db_configs(cls, configs):
        try:
            with open(cls.CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(configs, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Erro ao salvar db_configs.json: {e}")

