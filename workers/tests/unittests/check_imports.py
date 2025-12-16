import ast
import pathlib
import tomllib
import sys

IMPORT_TO_PACKAGE = {
    "google": "protobuf",
    "dateutil": "python_dateutil",
    "grpc": "grpcio",
    "azure.functions": "azure_functions",
    "azurefunctions.extensions.base": "azurefunctions_extensions_base",
}


def normalize_import(import_name):
    return IMPORT_TO_PACKAGE.get(import_name, import_name)


def find_local_modules(src_dir):
    local = set()
    for py in src_dir.rglob("*.py"):
        if py.name == "__init__.py":
            local.add(py.parent.name)
        else:
            local.add(py.stem)
    return local


def find_imports(src_dir):
    imports = set()
    for py in src_dir.rglob("*.py"):
        with open(py, "r", encoding="utf8") as f:
            tree = ast.parse(f.read(), filename=str(py))

        for node in ast.walk(tree):
            # import x.y
            if isinstance(node, ast.Import):
                for n in node.names:
                    if n.name == "azurefunctions.extensions.base":
                        imports.add("azurefunctions.extensions.base")
                    elif n.name == "azure.functions":
                        imports.add("azure.functions")
                    else:
                        imports.add(n.name.split(".")[0])

            # from x import y
            elif isinstance(node, ast.ImportFrom):
                # 🔹 Ignore relative imports
                if node.level > 0:
                    continue

                if node.module:
                    if node.module == "azure.functions":
                        imports.add("azure.functions")
                    elif node.module == "azurefunctions.extensions.base":
                        imports.add("azurefunctions.extensions.base")
                    # Special cases to ignore
                    elif str(src_dir).startswith("workers") and (
                        node.module == "azure.monitor.opentelemetry"
                        or node.module == "opentelemetry"
                        or node.module == "opentelemetry.trace.propagation.tracecontext"
                        or node.module == "Cookie"):
                        pass
                    elif str(src_dir).startswith("runtimes\\v1\\azure_functions_runtime_v1") and (
                        node.module == "google.protobuf.timestamp_pb2"
                        or node.module == "azure.monitor.opentelemetry"
                        or node.module == "opentelemetry"
                        or node.module == "opentelemetry.trace.propagation.tracecontext"
                        or node.module == "Cookie"):
                        pass
                    elif str(src_dir).startswith("runtimes\\v2\\azure_functions_runtime") and (
                        node.module == "google.protobuf.duration_pb2"
                        or node.module == "google.protobuf.timestamp_pb2"
                        or node.module == "azure.monitor.opentelemetry"
                        or node.module == "opentelemetry"
                        or node.module == "opentelemetry.trace.propagation.tracecontext"
                        or node.module == "Cookie"):
                        pass
                    else:
                        imports.add(node.module.split(".")[0])

    return imports


def load_declared_dependencies(pyproject):
    data = tomllib.loads(pyproject.read_text())
    deps = data["project"]["dependencies"]
    # Strip extras/markers, e.g. "protobuf~=4.25.3; python_version < '3.13'"
    normalized = set()
    for d in deps:
        name = d.split(";")[0].strip()       # strip environment marker
        name = name.split("[")[0].strip()    # strip extras
        pkg = name.split("==")[0].split("~=")[0].split(">=")[0].split("<=")[0]
        normalized.add(pkg.lower().replace("-", "_"))
    return normalized


def check_package(pkg_root, package_name):
    pyproject = pkg_root / "pyproject.toml"
    src_dir = pkg_root / package_name

    imports = find_imports(src_dir)
    deps = load_declared_dependencies(pyproject)
    stdlib = set(stdlib_modules())
    local_modules = find_local_modules(src_dir)
    print("Found imports:", imports)
    print("Declared dependencies:", deps)

    missing = []

    for imp in imports:

        normalized = normalize_import(imp)
        if (
            normalized not in deps
            and imp not in stdlib
            and imp not in local_modules
            and imp != package_name
        ):
            missing.append(imp)



    if missing:
        print("Missing required dependencies:")
        for m in missing:
            print("  -", m)
        raise SystemExit(1)


def stdlib_modules():
    # simple version
    import sys
    return set(sys.stdlib_module_names)


def main():
    roots = sys.argv[1]
    package_name = sys.argv[2]

    if not roots:
        print("Usage: python check_imports.py <pkg_dir> [<pkg_dir> ...]")
        sys.exit(2)

    failed = False
    check_package(pathlib.Path(roots), package_name)

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
