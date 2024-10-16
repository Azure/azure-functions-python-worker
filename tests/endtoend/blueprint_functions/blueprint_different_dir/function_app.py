import azure.functions as func
from blueprint_directory.blueprint import bp

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

app.register_functions(bp)
