from rich.console import Console
import subprocess
import time

console = Console()

def profile_authenticated(profile):
    """Diz se ESTE profile tem credencial válida agora."""
    result = subprocess.run(
        ["aws", "sts", "get-caller-identity", "--profile", profile],
        capture_output=True,
        text=True
    )
    return result.returncode == 0

def ensure_profile_session(profile):
    """Garante sessão válida para o profile escolhido, logando se preciso.

    Profiles da mesma sso_session compartilham o token em ~/.aws/sso/cache, então
    trocar de conta normalmente resolve aqui sem abrir o navegador.
    """
    if profile_authenticated(profile):
        return True

    console.print(f"\n🔑 Fazendo login com o profile [bold green]{profile}[/]...", style="bold blue")
    # Sem capture_output: o login precisa do terminal interativo.
    subprocess.run(["aws", "sso", "login", "--profile", profile], check=False)

    if profile_authenticated(profile):
        return True

    console.print(f"❌ Erro ao fazer login com o profile '{profile}'", style="bold red")
    console.print("\n📝 Se o profile ainda não está configurado:", style="bold blue")
    console.print("   aws configure sso", style="bold green")
    return False

def check_azure_cli_installed():
    """Verifica se o Azure CLI está instalado"""
    try:
        result = subprocess.run(["az", "--version"], capture_output=True, text=True)
        return result.returncode == 0
    except Exception:
        return False

def check_azure_session():
    """Verifica se há uma sessão Azure ativa"""
    try:
        result = subprocess.run(
            ["az", "account", "show"],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception:
        return False

def get_azure_subscriptions():
    """Obtém a lista de assinaturas do Azure"""
    try:
        result = subprocess.run(
            ["az", "account", "list", "--query", "[].name", "-o", "tsv"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return result.stdout.strip().split('\n')
        return []
    except Exception:
        return []

def get_azure_current_subscription():
    """Obtém a assinatura atual do Azure"""
    try:
        result = subprocess.run(
            ["az", "account", "show", "--query", "name", "-o", "tsv"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except Exception:
        return None

def get_azure_clusters(subscription=None):
    """Obtém a lista de clusters AKS do Azure"""
    try:
        cmd = ["az", "aks", "list", "--query", "[].name", "-o", "tsv"]
        if subscription:
            cmd.extend(["--subscription", subscription])
            
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return result.stdout.strip().split('\n')
        return []
    except Exception:
        return []

def set_azure_subscription(subscription):
    """Define a assinatura atual do Azure"""
    try:
        result = subprocess.run(
            ["az", "account", "set", "--subscription", subscription],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception:
        return False

def get_aks_credentials(cluster_name, resource_group=None, subscription=None, kubeconfig=None):
    """Obtém as credenciais para um cluster AKS"""
    try:
        cmd = ["az", "aks", "get-credentials", "--name", cluster_name, "--overwrite-existing"]

        if kubeconfig:
            # O default do az é ~/.kube/config literal, então o arquivo vai explícito.
            cmd.extend(["--file", kubeconfig])

        if resource_group:
            cmd.extend(["--resource-group", resource_group])
            
        if subscription:
            cmd.extend(["--subscription", subscription])
            
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def format_age(timestamp):
    """Formata a idade de um recurso baseado em seu timestamp"""
    age = time.time() - timestamp.timestamp()
    if age < 60:  # menos de 1 minuto
        return f"{int(age)}s"
    elif age < 3600:  # menos de 1 hora
        return f"{int(age/60)}m"
    elif age < 86400:  # menos de 1 dia
        return f"{int(age/3600)}h"
    else:
        return f"{int(age/86400)}d"

def get_pod_metrics(namespace):
    """Obtém métricas de uso dos pods em um namespace"""
    try:
        result = subprocess.run(
            ["kubectl", "top", "pods", "-n", namespace],
            capture_output=True,
            text=True,
            check=True
        )
        metrics_lines = result.stdout.strip().split('\n')[1:]  # Pula o cabeçalho
        metrics_dict = {}
        for line in metrics_lines:
            parts = line.split()
            if len(parts) >= 3:
                pod_name = parts[0]
                cpu = parts[1]
                memory = parts[2]
                metrics_dict[pod_name] = {
                    'cpu': cpu,
                    'memory': memory
                }
        return metrics_dict
    except subprocess.CalledProcessError:
        return {}

def parse_resource_value(value, resource_type='cpu'):
    """Converte valores de recursos (CPU/memória) para um formato padrão"""
    if not value:
        return 0
        
    if resource_type == 'cpu':
        if value.endswith('m'):
            return int(value[:-1])
        return int(float(value) * 1000)
    elif resource_type == 'memory':
        if value.endswith('Mi'):
            return int(value[:-2])
        elif value.endswith('Gi'):
            return int(float(value[:-2]) * 1024)
        elif value.endswith('Ki'):
            return int(value[:-2]) / 1024
    return 0 