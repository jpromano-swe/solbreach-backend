from mangum import Mangum
from app.main import create_app

handler = Mangum(create_app(), lifespan="off")