from azure.functions_worker.bindings import meta


class Binding(meta.InConverter, meta.OutConverter,
              binding='fooType'):
    pass
