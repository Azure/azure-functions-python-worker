import azure.functions as func
from flask import Flask, request

flask_app = Flask(__name__)


@flask_app.get("/get_query_param")
def get_query_param():
    name = request.args.get("name")
    if name is None:
        name = "world"
    return f"hello {name}"


@flask_app.post("/post_str")
def post_str():
    return f"hello {request.data.decode()}"


@flask_app.post("/post_json_return_json_response")
def post_json_return_json_response():
    return request.get_json()


@flask_app.get("/get_path_param/<id>")
def get_path_param(id):
    return f"hello {id}"


@flask_app.get("/raise_http_exception")
def raise_http_exception():
    return {"detail": "Item not found"}, 404


app = func.WsgiFunctionApp(app=flask_app.wsgi_app,
                           http_auth_level=func.AuthLevel.ANONYMOUS)