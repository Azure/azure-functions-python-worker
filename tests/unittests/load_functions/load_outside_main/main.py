# This function app is to ensure the code outside main() function
# should only get loaded once in __init__.py

import azure.functions as func


def main(req: func.HttpRequest):
    if req.params['from'] == 'init':
        # Ensure the module can still be loaded from package.__init__
        from ..stub_http_trigger.__init__ import main  # NoQA
        from __app__.stub_http_trigger.__init__ import main  # NoQA

    elif req.params['from'] == 'package':
        # Ensure the module can still be loaded from package
        from ..stub_http_trigger import main
        from __app__.stub_http_trigger import main  # NoQA

    # Ensure submodules can also be imported
    from ..stub_http_trigger.stub_tools import FOO  # NoQA
    from __app__.stub_http_trigger.stub_tools import FOO  # NoQA

    return 'OK'
