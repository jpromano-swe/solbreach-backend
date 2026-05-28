from mangum import Mangum
from app.main import create_app

app = create_app()
handler = Mangum(create_app(), lifespan="off", api_gateaway_base_path="/main")