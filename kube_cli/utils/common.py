from . import session


def load_namespace():
    """Namespace da sessão atual (a aba do terminal)."""
    return session.load_state().get('namespace')
