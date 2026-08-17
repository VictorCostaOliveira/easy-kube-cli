"""Checagem do estado por sessão.

Roda da raiz do repo: python -m kube_cli.utils.test_session

Rodar o arquivo direto não funciona: isso põe kube_cli/utils/ no início do
sys.path e o kubernetes.py daqui passa a sombrear o pacote kubernetes.
"""

import importlib
import os
import tempfile

from kube_cli.utils import session as session_module


def fresh_home(home):
    """Recarrega o módulo com um HOME temporário — as constantes são de import."""
    os.environ['HOME'] = home
    return importlib.reload(session_module)


def use(session, key):
    os.environ['EKLI_SESSION'] = key
    return session


def test_session_key_prefers_env():
    with tempfile.TemporaryDirectory() as home:
        session = fresh_home(home)

        os.environ['EKLI_SESSION'] = 'prod'
        assert session.session_key() == 'prod'

        os.environ['EKLI_SESSION'] = 'a/b'
        assert session.session_key() == 'a_b', 'chave não pode virar subdiretório'

        del os.environ['EKLI_SESSION']
        assert session.session_key(), 'sem EKLI_SESSION cai no TTY ou em default'


def test_save_state_merges_and_none_removes():
    with tempfile.TemporaryDirectory() as home:
        session = use(fresh_home(home), 'merge')

        session.save_state(namespace='payments', current_type='aws')
        session.save_state(namespace='billing')

        state = session.load_state()
        assert state['namespace'] == 'billing'
        assert state['current_type'] == 'aws', 'save_state faz merge, não sobrescreve'

        session.save_state(namespace=None)
        assert 'namespace' not in session.load_state()


def test_sessions_are_isolated():
    with tempfile.TemporaryDirectory() as home:
        session = fresh_home(home)

        use(session, 'aba-a').save_state(namespace='payments')
        use(session, 'aba-b').save_state(namespace='billing')

        assert use(session, 'aba-a').load_state()['namespace'] == 'payments'
        assert use(session, 'aba-b').load_state()['namespace'] == 'billing'
        assert session.kubeconfig_path() != os.path.join(
            session.SESSIONS_DIR, 'aba-a', 'kubeconfig'
        )


def test_new_session_seeds_from_newest():
    with tempfile.TemporaryDirectory() as home:
        session = fresh_home(home)

        use(session, 'antiga').save_state(namespace='velho')
        old_state = session.state_path()

        use(session, 'recente').save_state(namespace='novo')
        with open(session.kubeconfig_path(), 'w') as f:
            f.write('kubeconfig da recente')

        # mtimes explícitos: 'recente' é a mais nova, sem depender de sleep.
        os.utime(old_state, (1_000, 1_000))
        os.utime(session.state_path(), (2_000, 2_000))

        nova = use(session, 'nova-aba')
        assert nova.load_state()['namespace'] == 'novo', 'herda da sessão mais recente'
        with open(nova.kubeconfig_path()) as f:
            assert f.read() == 'kubeconfig da recente'

        # E divergir na nova aba não toca a origem.
        nova.save_state(namespace='proprio')
        assert use(session, 'recente').load_state()['namespace'] == 'novo'


def test_first_session_seeds_from_legacy_global():
    with tempfile.TemporaryDirectory() as home:
        session = fresh_home(home)

        os.makedirs(session.BASE_DIR, exist_ok=True)
        with open(session.LEGACY_STATE, 'w') as f:
            f.write('namespace: legado\n')
        os.makedirs(os.path.dirname(session.GLOBAL_KUBECONFIG), exist_ok=True)
        with open(session.GLOBAL_KUBECONFIG, 'w') as f:
            f.write('kubeconfig global')

        primeira = use(session, 'primeira')
        assert primeira.load_state()['namespace'] == 'legado'
        with open(primeira.kubeconfig_path()) as f:
            assert f.read() == 'kubeconfig global'


def test_apply_env_points_at_session():
    with tempfile.TemporaryDirectory() as home:
        session = use(fresh_home(home), 'env')

        session.save_state(aws_profile='conta-b')
        session.apply_env()

        assert os.environ['KUBECONFIG'] == session.kubeconfig_path()
        assert os.environ['AWS_PROFILE'] == 'conta-b'


def test_aws_profile_falls_back_to_cluster():
    with tempfile.TemporaryDirectory() as home:
        session = use(fresh_home(home), 'migrada')

        # Estado vindo da versão antiga: profile só dentro de current_cluster.
        session.save_state(current_cluster={'name': 'eks', 'profile': 'conta-a'})
        assert session.aws_profile() == 'conta-a'

        session.save_state(aws_profile='conta-b')
        assert session.aws_profile() == 'conta-b', 'aws_profile explícito tem precedência'


if __name__ == '__main__':
    real_home = os.environ.get('HOME')
    try:
        for name, run in sorted(globals().items()):
            if name.startswith('test_'):
                run()
                print(f'ok  {name}')
    finally:
        os.environ.pop('EKLI_SESSION', None)
        if real_home:
            os.environ['HOME'] = real_home
    print('\ntodos os checks passaram')
