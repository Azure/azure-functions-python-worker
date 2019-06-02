from azure.functions import meta


class Binding(meta.InConverter, meta.OutConverter,
              binding='fooType'):
    pass
