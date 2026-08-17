"""Estado por sessão: cada aba do terminal tem seu próprio cluster e namespace.

A chave da sessão é o TTY da aba, então abrir uma aba nova já dá isolamento sem
configurar nada. Uma sessão é um diretório com dois arquivos:

    ~/.easy-kube-cli/sessions/ttys004/
        kubeconfig   <- KUBECONFIG desta aba
        config       <- namespace, current_cluster, current_type, azure_*
"""

import os
import shutil
import yaml

BASE_DIR = os.path.expanduser('~/.easy-kube-cli')
SESSIONS_DIR = os.path.join(BASE_DIR, 'sessions')
LEGACY_STATE = os.path.join(BASE_DIR, 'config')
GLOBAL_KUBECONFIG = os.path.expanduser('~/.kube/config')


def session_key():
    """EKLI_SESSION se definida, senão o TTY da aba, senão 'default'."""
    explicit = os.environ.get('EKLI_SESSION')
    if explicit:
        return explicit.replace(os.sep, '_')

    try:
        return os.path.basename(os.ttyname(0))
    except OSError:
        return 'default'  # sem terminal: pipe, cron, CI


def session_dir():
    """Diretório da sessão. Na primeira vez, semeia da sessão mais recente."""
    path = os.path.join(SESSIONS_DIR, session_key())
    if os.path.isdir(path):
        return path

    source = _newest_session()
    os.makedirs(path, exist_ok=True)

    if source:
        _copy(os.path.join(source, 'kubeconfig'), os.path.join(path, 'kubeconfig'))
        _copy(os.path.join(source, 'config'), os.path.join(path, 'config'))
    else:
        # Primeira sessão da máquina: herda o que já existia global.
        _copy(GLOBAL_KUBECONFIG, os.path.join(path, 'kubeconfig'))
        _copy(LEGACY_STATE, os.path.join(path, 'config'))

    return path


def kubeconfig_path():
    return os.path.join(session_dir(), 'kubeconfig')


def state_path():
    return os.path.join(session_dir(), 'config')


def load_state():
    path = state_path()
    if not os.path.exists(path):
        return {}

    with open(path) as f:
        return yaml.safe_load(f) or {}


def save_state(**values):
    """Grava fazendo merge com o que já existe. Valor None remove a chave."""
    state = load_state()
    for key, value in values.items():
        if value is None:
            state.pop(key, None)
        else:
            state[key] = value

    with open(state_path(), 'w') as f:
        yaml.dump(state, f)

    return state


def aws_profile():
    """Profile da sessão. Cai no do cluster para estado vindo da versão antiga."""
    state = load_state()
    return state.get('aws_profile') or (state.get('current_cluster') or {}).get('profile')


def apply_env():
    """Aponta os kubectl/aws desta invocação para a sessão atual."""
    os.environ['KUBECONFIG'] = kubeconfig_path()

    profile = aws_profile()
    if profile:
        os.environ['AWS_PROFILE'] = profile


def load_kube(context=None):
    """load_kube_config da sessão.

    O config_file vai explícito porque o cliente Python congela o KUBECONFIG no
    import do módulo (kubernetes/config/kube_config.py:48), antes de apply_env().
    """
    from kubernetes import config
    config.load_kube_config(config_file=kubeconfig_path(), context=context)


def _newest_session():
    """Sessão usada mais recentemente, pelo mtime do seu arquivo de estado."""
    if not os.path.isdir(SESSIONS_DIR):
        return None

    dirs = [
        os.path.join(SESSIONS_DIR, name)
        for name in os.listdir(SESSIONS_DIR)
        if os.path.isfile(os.path.join(SESSIONS_DIR, name, 'config'))
    ]
    if not dirs:
        return None

    return max(dirs, key=lambda d: os.path.getmtime(os.path.join(d, 'config')))


def _copy(src, dst):
    if os.path.exists(src):
        shutil.copyfile(src, dst)
