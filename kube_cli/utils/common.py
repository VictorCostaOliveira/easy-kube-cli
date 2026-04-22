import yaml
import os

def load_namespace():
    """Carrega o namespace salvo na configuração"""
    config_path = os.path.expanduser('~/.easy-kube-cli/config')
    if os.path.exists(config_path):
        with open(config_path) as f:
            config_data = yaml.safe_load(f) or {}
            return config_data.get('namespace')
    return None 

def save_environment_variable(key, value):
    """Define uma variável de ambiente e mostra como configurá-la no shell"""
    # Define no processo atual (para uso interno do CLI)
    os.environ[key] = value
    
    # Importa console aqui para evitar dependência circular
    from rich.console import Console
    console = Console()
    
    # Mostra a instrução para o usuário
    console.print(f"\n💡 Para usar a variável {key} no seu terminal, execute:", style="bold blue")
    console.print(f"export {key}={value}", style="bold green")
    console.print(f"\nOu adicione esta linha ao seu ~/.bashrc ou ~/.zshrc para torná-la permanente.", style="dim") 