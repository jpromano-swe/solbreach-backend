from mangum import Mangum
from app.main import create_app

app = create_app()
handler = Mangum(app, lifespan="off", api_gateway_base_path=f"/{stage}" if stage else None)