# Needed to make azure a namespace for package discovery
import typing
from pkgutil import extend_path

__path__: typing.Iterable[str] = extend_path(__path__, __name__)
