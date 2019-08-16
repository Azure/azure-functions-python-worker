# Needed to make azure a namespace for package discovery
from pkgutil import extend_path
import typing
__path__: typing.Iterable[str] = extend_path(__path__, __name__)
