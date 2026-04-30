import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)

DB_PATH = os.environ.get("DB_PATH", os.path.join(PROJECT_ROOT, "finance.db"))
BANKS_DIR = os.path.join(PROJECT_ROOT, "banks")
RULES_TEMPLATE_DIR = os.path.join(PROJECT_ROOT, "rules", "templates")
SAMPLE_DATA_DIR = os.path.join(PROJECT_ROOT, "sample_data")
DEMO_MODE = os.environ.get("DEMO_MODE", "false").lower() == "true"
