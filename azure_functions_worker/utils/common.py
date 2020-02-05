import os


def is_true_like(setting: str):
    if setting is None:
        return False

    return setting.lower().strip() in ['1', 'true', 't', 'yes', 'y']


def is_envvar_true(env_key: str):
    if os.getenv(env_key) is None:
        return False

    return is_true_like(os.environ[env_key])
