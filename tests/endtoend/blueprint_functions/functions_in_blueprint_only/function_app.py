import azure.functions as func
from blueprint import bp

app = func.FunctionApp()

app.register_functions(bp)
