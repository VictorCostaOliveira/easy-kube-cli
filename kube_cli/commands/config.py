import click
from rich.console import Console
from rich.table import Table
import subprocess
import json
import shlex
import inquirer
from kubernetes import client
from ..utils.kubernetes import (
    ensure_profile_session,
    check_azure_cli_installed,
    check_azure_session,
    get_azure_subscriptions,
    get_azure_current_subscription,
    set_azure_subscription,
    get_aks_credentials,
)
from ..utils import session

console = Console()

NEW_PROFILE = "+ Adicionar novo profile"


# ---------------------------------------------------------------- AWS: helpers

def check_aws_cli():
    """Confirma que o AWS CLI existe, com instruções de instalação se não."""
    try:
        if subprocess.run(["aws", "--version"], capture_output=True, text=True).returncode == 0:
            return True
    except Exception:
        pass

    console.print("\n❌ AWS CLI não está instalado!", style="bold red")
    console.print("\n📝 Para instalar o AWS CLI:", style="bold yellow")
    console.print("1. Linux/MacOS:", style="dim")
    console.print("   https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html")
    console.print("\n2. Windows:", style="dim")
    console.print("   https://aws.amazon.com/cli/")
    return False


def list_aws_profiles():
    result = subprocess.run(
        ["aws", "configure", "list-profiles"],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        return []

    return [p for p in result.stdout.strip().split('\n') if p]


def print_sso_hints():
    console.print("   - SSO start URL: https://yourdomain.awsapps.com.br/start", style="dim white")
    console.print("   - SSO Region: us-east-1", style="dim white")
    console.print("   - CLI default client Region: us-east-1", style="dim white")
    console.print("   - CLI default output format: json", style="dim white")
    console.print("   - CLI profile name: nome-do-seu-perfil", style="dim white")


def configure_new_profile(before):
    """Roda `aws configure sso` e devolve o profile escolhido depois."""
    console.print("\n📝 Iniciando configuração AWS SSO. Siga os passos abaixo:", style="bold blue")
    print_sso_hints()
    console.print("\n🔧 Executando configuração AWS SSO interativa...", style="bold blue")

    try:
        subprocess.run(["aws", "configure", "sso"], check=True)
    except subprocess.CalledProcessError:
        console.print("❌ Erro ao configurar o profile AWS SSO.", style="bold red")
        return None

    profiles = list_aws_profiles()
    if not profiles:
        console.print("\n⚠️ Configuração AWS SSO não completada corretamente.", style="bold yellow")
        return None

    added = [p for p in profiles if p not in before]
    if added:
        console.print(f"\n✅ Novo(s) profile(s) configurado(s): {', '.join(added)}", style="bold green")
    else:
        console.print("\n⚠️ Não foi possível detectar novos profiles, mas a configuração pode ter sido realizada.", style="bold yellow")

    answers = inquirer.prompt([
        inquirer.List('profile', message="Selecione o profile para usar", choices=profiles)
    ])
    return answers['profile'] if answers else None


def select_profile(current=None, message="Selecione o profile AWS para usar"):
    """Menu de profiles, com o atual marcado e a opção de criar um novo."""
    profiles = list_aws_profiles()
    if not profiles:
        console.print("\n📝 Nenhum profile AWS encontrado. Vamos configurar o primeiro.", style="bold blue")
        return configure_new_profile([])

    # Listas paralelas: o rótulo com " (atual)" nunca volta como valor.
    choices = [f"{p} (atual)" if p == current else p for p in profiles]
    choices.append(NEW_PROFILE)

    answers = inquirer.prompt([inquirer.List('profile', message=message, choices=choices)])
    if not answers:
        return None

    chosen = answers['profile']
    if chosen == NEW_PROFILE:
        return configure_new_profile(profiles)

    return profiles[choices.index(chosen)]


def explain_aws_error(message, profile, cluster=None):
    """Traduz o erro da AWS na ação que resolve."""
    if "ResourceNotFoundException" in message:
        console.print(f"\n⚠️ Cluster '{cluster}' não encontrado na conta com o profile '{profile}'.", style="bold yellow")
        console.print("\n📝 Verifique se o nome do cluster está correto e se o profile tem acesso a ele.", style="bold blue")
    elif "AccessDeniedException" in message or "UnauthorizedException" in message:
        console.print("\n⚠️ O profile não tem permissão para esta operação no EKS.", style="bold yellow")
        console.print(f"\n📝 Tente logar novamente com o profile '{profile}':", style="bold blue")
        console.print(f"   aws sso login --profile {profile}", style="bold green")
    elif "ExpiredToken" in message:
        console.print("\n⚠️ Token de acesso AWS expirado.", style="bold yellow")
        console.print("\n📝 Renove sua sessão:", style="bold blue")
        console.print(f"   aws sso login --profile {profile}", style="bold green")
    else:
        console.print(f"\nErro detalhado: {message}", style="dim red")


def prompt_cluster_name():
    """Saída de emergência quando a listagem falha: digitar o nome à mão."""
    if click.prompt("Deseja informar o nome do cluster manualmente? [s/N]", default="n").lower() != "s":
        return None

    return click.prompt("Digite o nome do cluster")


def select_eks_cluster(profile, region, current=None):
    console.print(f"🔍 Listando clusters EKS disponíveis com profile '{profile}'...", style="bold blue")

    result = subprocess.run(
        ["aws", "eks", "list-clusters", "--region", region, "--profile", profile],
        capture_output=True,
        text=True,
        check=False
    )

    if result.returncode != 0:
        console.print("❌ Erro ao listar clusters EKS:", style="bold red")
        explain_aws_error(result.stderr.strip(), profile)
        console.print("\n📝 Se você conhece o nome do cluster, pode fornecê-lo diretamente:", style="bold blue")
        console.print(f"   ekli use-cluster nome-do-cluster -p {profile}", style="bold green")
        return prompt_cluster_name()

    try:
        available = json.loads(result.stdout).get("clusters", [])
    except json.JSONDecodeError:
        console.print("❌ Erro ao processar a resposta da AWS.", style="bold red")
        console.print(f"Resposta recebida: {result.stdout}", style="dim")
        return prompt_cluster_name()

    if not available:
        console.print(f"❌ Nenhum cluster EKS encontrado na conta com profile '{profile}'.", style="bold red")
        return prompt_cluster_name()

    choices = [f"{c} (atual)" if c == current else c for c in available]
    answers = inquirer.prompt([
        inquirer.List('cluster', message="Selecione um cluster EKS para usar", choices=choices)
    ])
    if not answers:
        return None

    return available[choices.index(answers['cluster'])]


def switch_cluster_aws(cluster_name=None, region=None, profile=None):
    """Aponta a sessão atual para um cluster EKS. Serve init e use-cluster."""
    if not check_aws_cli():
        return

    state = session.load_state()
    current = state.get('current_cluster') or {}
    region = region or current.get('region') or 'us-east-1'

    profile = profile or select_profile(current=current.get('profile'))
    if not profile:
        return

    if not ensure_profile_session(profile):
        return

    if cluster_name is None:
        cluster_name = select_eks_cluster(profile, region, current=current.get('name'))

    if not cluster_name:
        console.print("❌ Nome do cluster não informado.", style="bold red")
        return

    console.print(f"🔄 Atualizando kubeconfig para o cluster '{cluster_name}'...", style="bold blue")
    update = subprocess.run([
        "aws", "eks", "update-kubeconfig",
        "--name", cluster_name,
        "--region", region,
        "--profile", profile,
        # Explícito: escreve no kubeconfig desta sessão, nunca no global.
        "--kubeconfig", session.kubeconfig_path()
    ], capture_output=True, text=True, check=False)

    if update.returncode != 0:
        console.print("❌ Erro ao atualizar kubeconfig:", style="bold red")
        explain_aws_error(update.stderr.strip(), profile, cluster_name)
        return

    # Identidade é name+profile+region: o mesmo nome de cluster existe em duas contas.
    changed = (current.get('name'), current.get('profile'), current.get('region')) != (cluster_name, profile, region)
    session.save_state(
        current_cluster={'name': cluster_name, 'region': region, 'profile': profile},
        current_type='aws',
        aws_profile=profile,
        # Namespace do cluster anterior não existe no novo.
        namespace=None if changed else state.get('namespace'),
    )

    console.print(f"✅ Cluster alterado para: [bold green]{cluster_name}[/] com profile [bold green]{profile}[/]", style="bold")
    smoke_test_cluster()
    list_configured_clusters()


# -------------------------------------------------------------- Azure: helpers

def check_azure_cli():
    """Confirma que o Azure CLI existe, com instruções de instalação se não."""
    if check_azure_cli_installed():
        return True

    console.print("\n❌ Azure CLI não está instalado!", style="bold red")
    console.print("\n📝 Para instalar o Azure CLI:", style="bold yellow")
    console.print("1. Linux/MacOS:", style="dim")
    console.print("   curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash", style="bold green")
    console.print("\n2. Windows:", style="dim")
    console.print("   https://docs.microsoft.com/pt-br/cli/azure/install-azure-cli-windows", style="bold green")
    return False


def select_aks_cluster(current=None, current_group=None):
    """Menu de clusters AKS. Devolve (nome, grupo de recursos)."""
    result = subprocess.run(
        ["az", "aks", "list", "--query", "[].{name:name, resourceGroup:resourceGroup}", "-o", "json"],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        console.print(f"❌ Erro ao listar clusters AKS: {result.stderr}", style="bold red")
        return None, None

    clusters = json.loads(result.stdout)
    if not clusters:
        console.print("❌ Não foram encontrados clusters AKS nesta assinatura.", style="bold red")
        return None, None

    # Listas paralelas: dispensa reparsear o rótulo para achar nome e grupo.
    choices = []
    for c in clusters:
        label = f"{c['name']} (Grupo: {c['resourceGroup']})"
        is_current = c['name'] == current and c['resourceGroup'] == current_group
        choices.append(f"{label} (atual)" if is_current else label)

    answers = inquirer.prompt([
        inquirer.List('cluster', message="Selecione o cluster AKS", choices=choices)
    ])
    if not answers:
        return None, None

    chosen = clusters[choices.index(answers['cluster'])]
    return chosen['name'], chosen['resourceGroup']


def switch_cluster_azure(cluster_name=None, resource_group=None, subscription=None):
    """Aponta a sessão atual para um cluster AKS. Serve init-azure e use-cluster."""
    if not check_azure_cli():
        return

    if not check_azure_session():
        console.print("\n⚠️  Você não tem uma sessão Azure ativa!", style="bold yellow")
        console.print("\n📝 Use o comando 'ekli login-azure' para fazer login primeiro.", style="bold blue")
        return

    state = session.load_state()
    current_subscription = get_azure_current_subscription()
    selected_subscription = subscription or current_subscription

    if subscription and subscription != current_subscription:
        console.print(f"\n🔄 Mudando para a assinatura [bold blue]{selected_subscription}[/]...", style="bold blue")
        if not set_azure_subscription(selected_subscription):
            console.print("❌ Erro ao alterar a assinatura.", style="bold red")
            return

    if not cluster_name:
        cluster_name, resource_group = select_aks_cluster(
            current=state.get('azure_cluster'),
            current_group=state.get('azure_resource_group')
        )

    if not cluster_name:
        return

    if not resource_group:
        console.print("❌ Grupo de recursos não informado para o cluster Azure.", style="bold red")
        console.print("📝 Você precisa fornecer o grupo de recursos para clusters AKS:", style="bold blue")
        console.print(f"  ekli use-cluster {cluster_name} -az -g NOME_DO_GRUPO", style="bold green")
        return

    console.print(f"\n🔄 Configurando kubectl para o cluster [bold green]{cluster_name}[/]...", style="bold blue")
    success, _, stderr = get_aks_credentials(
        cluster_name,
        resource_group=resource_group,
        subscription=selected_subscription,
        kubeconfig=session.kubeconfig_path()
    )

    if not success:
        console.print(f"❌ Erro ao configurar o cluster: {stderr}", style="bold red")
        return

    # Mesmo nome de cluster pode existir em dois grupos de recursos.
    changed = (state.get('azure_cluster'), state.get('azure_resource_group')) != (cluster_name, resource_group)
    session.save_state(
        azure_cluster=cluster_name,
        azure_resource_group=resource_group,
        azure_subscription=selected_subscription,
        current_type='azure',
        namespace=None if changed else state.get('namespace'),
    )

    console.print(f"✅ Cluster alterado para: [bold green]{cluster_name}[/] (Azure AKS)", style="bold")
    console.print("📊 Detalhes:", style="bold blue")
    console.print(f"   Cluster: {cluster_name}", style="dim")
    console.print(f"   Grupo de recursos: {resource_group}", style="dim")
    console.print(f"   Assinatura: {selected_subscription}", style="dim")

    smoke_test_cluster()
    list_configured_clusters()


# ------------------------------------------------------------ kubectl: helpers

def current_context():
    result = subprocess.run(
        ["kubectl", "config", "current-context"],
        capture_output=True,
        text=True
    )
    return result.stdout.strip() if result.returncode == 0 else None


def smoke_test_cluster():
    """Confirma que o cluster recém-configurado responde."""
    result = subprocess.run(
        ["kubectl", "get", "nodes", "--request-timeout=5s"],
        capture_output=True,
        text=True,
        check=False
    )

    if result.returncode == 0:
        console.print("\n✅ Conexão com o cluster estabelecida com sucesso!", style="bold green")
        return

    console.print("\n⚠️ A configuração foi atualizada, mas não foi possível conectar ao cluster.", style="bold yellow")
    console.print("📝 Isso pode ocorrer por:", style="bold blue")
    console.print("  • Problemas de conectividade de rede", style="dim white")
    console.print("  • Problemas de autenticação", style="dim white")
    console.print("  • Configurações adicionais podem ser necessárias", style="dim white")
    console.print("\nTente usar o seguinte comando para verificar a conexão:", style="bold blue")
    console.print("  kubectl get nodes", style="bold green")


def list_configured_clusters():
    """Lista os contextos do kubeconfig desta sessão."""
    try:
        result = subprocess.run(
            ["kubectl", "config", "get-contexts"],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            console.print("❌ Erro ao listar contextos do kubectl.", style="bold red")
            return

        context_now = current_context()

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Nome do Contexto")
        table.add_column("Cluster")
        table.add_column("Usuário")
        table.add_column("Status")

        for line in result.stdout.strip().split('\n')[1:]:
            parts = line.strip().split()
            if len(parts) < 3:
                continue

            # A linha do contexto atual começa com '*', deslocando as colunas.
            if '*' in parts[0]:
                parts = parts[1:]

            table.add_row(
                parts[0],
                parts[1],
                parts[2] if len(parts) > 2 else "N/A",
                "[bold green]ATUAL[/]" if parts[0] == context_now else ""
            )

        console.print("\n📋 Clusters configurados nesta sessão:", style="bold blue")
        console.print(table)
        console.print("\nDica: Use 'ekli use-cluster' para alternar entre clusters.", style="dim")

    except Exception as e:
        console.print(f"❌ Erro ao listar clusters configurados: {str(e)}", style="bold red")


# ------------------------------------------------------------------- comandos

@click.command()
@click.option('--cluster', '-c', help='Nome do cluster EKS para inicializar')
@click.option('--region', '-r', help='Região AWS onde o cluster está localizado')
@click.option('--profile', '-p', help='Profile AWS para usar')
def init(cluster=None, region=None, profile=None):
    """Configura o kubectl desta sessão para um cluster EKS."""
    switch_cluster_aws(cluster_name=cluster, region=region, profile=profile)


@click.command(name="init-azure")
@click.option('--cluster', '-c', help='Nome do cluster AKS para inicializar')
@click.option('--resource-group', '-g', help='Grupo de recursos do cluster AKS')
@click.option('--subscription', '-s', help='Assinatura Azure para usar')
def init_azure(cluster=None, resource_group=None, subscription=None):
    """Configura o kubectl desta sessão para um cluster AKS."""
    switch_cluster_azure(
        cluster_name=cluster,
        resource_group=resource_group,
        subscription=subscription
    )


@click.command(name="use-cluster")
@click.argument('cluster_name', required=False)
@click.option('--region', '-r', help='Região AWS onde o cluster está localizado')
@click.option('--profile', '-p', help='Profile AWS para usar')
@click.option('--azure', '-az', is_flag=True, help='Indica que o cluster está no Azure')
@click.option('--aws', is_flag=True, help='Indica que o cluster está na AWS')
@click.option('--switch', '-s', is_flag=True, help='Alterna entre AWS e Azure')
@click.option('--resource-group', '-g', help='Grupo de recursos do cluster AKS (apenas para Azure)')
@click.option('--subscription', '--sub', help='Assinatura Azure para usar (apenas para Azure)')
def use_cluster(cluster_name=None, region=None, profile=None, azure=False, aws=False,
                switch=False, resource_group=None, subscription=None):
    """Alterna o cluster desta sessão, sem afetar as outras abas."""
    if aws and azure:
        console.print("❌ Não é possível usar as flags --aws e --azure ao mesmo tempo.", style="bold red")
        return

    current_type = session.load_state().get('current_type', 'aws')

    if switch:
        is_azure = current_type != 'azure'
        console.print(f"\n🔄 Alternando para {'Azure AKS' if is_azure else 'AWS EKS'}...", style="bold blue")
    elif aws:
        is_azure = False
    elif azure:
        is_azure = True
    else:
        is_azure = current_type == 'azure'

    if is_azure:
        switch_cluster_azure(cluster_name, resource_group, subscription)
    else:
        switch_cluster_aws(cluster_name, region, profile)


@click.command()
@click.argument('namespace', required=False)
def use(namespace=None):
    """Seleciona o namespace desta sessão."""
    try:
        session.load_kube()
        v1 = client.CoreV1Api()
        available = sorted(ns.metadata.name for ns in v1.list_namespace().items)

        if not available:
            console.print("❌ Nenhum namespace encontrado no cluster.", style="bold red")
            return

        selected = namespace
        if not selected:
            answers = inquirer.prompt([
                inquirer.List('namespace', message="Selecione o namespace para usar", choices=available)
            ])
            if not answers:
                return
            selected = answers['namespace']

        if selected not in available:
            console.print(f"❌ Namespace '{selected}' não encontrado!", style="bold red")
            return

        session.save_state(namespace=selected)
        console.print(f"✅ Namespace alterado para: [bold green]{selected}[/]", style="bold")
    except Exception as e:
        console.print(f"❌ Erro ao alterar namespace: {str(e)}", style="bold red")


@click.command(name="clusters")
def clusters():
    """Lista os clusters configurados nesta sessão."""
    list_configured_clusters()


@click.command(name="status")
def status():
    """Mostra cluster, profile e namespace desta sessão (aba)."""
    state = session.load_state()
    cluster = state.get('current_cluster') or {}

    table = Table(show_header=False, box=None)
    table.add_column(style="bold blue")
    table.add_column()

    table.add_row("Sessão", session.session_key())

    if state.get('current_type') == 'azure':
        table.add_row("Plataforma", "Azure AKS")
        table.add_row("Cluster", state.get('azure_cluster') or "—")
        table.add_row("Grupo de recursos", state.get('azure_resource_group') or "—")
        table.add_row("Assinatura", state.get('azure_subscription') or "—")
    else:
        table.add_row("Plataforma", "AWS EKS")
        table.add_row("Cluster", cluster.get('name') or "—")
        table.add_row("Região", cluster.get('region') or "—")
        # O profile do cluster, não o do login: é ele que o exec do contexto usa.
        table.add_row("Profile", cluster.get('profile') or state.get('aws_profile') or "—")

    table.add_row("Contexto", current_context() or "—")
    table.add_row("Namespace", state.get('namespace') or "—")
    table.add_row("Kubeconfig", session.kubeconfig_path())

    console.print()
    console.print(table)

    # login-aws guarda o profile, mas quem manda na autenticação do cluster é o
    # AWS_PROFILE pinado no exec do contexto pelo update-kubeconfig.
    login_profile = state.get('aws_profile')
    cluster_profile = cluster.get('profile')
    if login_profile and cluster_profile and login_profile != cluster_profile:
        console.print(f"\n⚠️  O login desta sessão é [bold]{login_profile}[/], mas este cluster autentica como [bold]{cluster_profile}[/].", style="bold yellow")
        console.print(f"   Rode 'ekli use-cluster' para trocar para um cluster de {login_profile}.", style="dim")

    console.print("\nDica: 'eval $(ekli env)' faz o kubectl desta aba seguir esta sessão.", style="dim")


@click.command(name="env")
def env():
    """Exporta a sessão desta aba para o shell: eval $(ekli env)"""
    click.echo(f"export KUBECONFIG={shlex.quote(session.kubeconfig_path())}")

    profile = session.aws_profile()
    if profile:
        click.echo(f"export AWS_PROFILE={shlex.quote(profile)}")


@click.command(name="login-aws")
def login_aws():
    """Faz login no AWS SSO de forma interativa."""
    if not check_aws_cli():
        return

    state = session.load_state()
    current = state.get('aws_profile') or (state.get('current_cluster') or {}).get('profile')

    profile = select_profile(current=current, message="Selecione o profile para login")
    if not profile:
        return

    if not ensure_profile_session(profile):
        return

    session.save_state(aws_profile=profile)
    console.print("\n✅ Login realizado com sucesso!", style="bold green")
    console.print(f"🔧 Profile [bold green]{profile}[/] guardado nesta sessão.", style="bold cyan")
    console.print("\n📋 Agora use 'ekli use-cluster' para escolher o cluster.", style="bold blue")


@click.command(name="login-azure")
def login_azure():
    """Faz login no Azure CLI de forma interativa."""
    if not check_azure_cli():
        return

    if not check_azure_session():
        console.print("\n🔑 Iniciando login no Azure...", style="bold blue")
        console.print("Um navegador será aberto para você fazer login.", style="dim white")
        subprocess.run(["az", "login"], check=False)

        if not check_azure_session():
            console.print("\n❌ Falha ao fazer login no Azure.", style="bold red")
            return

        console.print("\n✅ Login realizado com sucesso!", style="bold green")

    current = get_azure_current_subscription()
    console.print(f"🔹 Assinatura atual: [bold blue]{current}[/]", style="dim")

    subscriptions = get_azure_subscriptions()
    if len(subscriptions) <= 1:
        console.print("\n📋 Agora use 'ekli init-azure' para configurar seu cluster AKS.", style="bold blue")
        return

    keep = "Continuar com a assinatura atual"
    answers = inquirer.prompt([
        inquirer.List('subscription',
                      message="Deseja mudar a assinatura?",
                      choices=[keep] + subscriptions,
                      default=keep)
    ])

    if answers and answers['subscription'] != keep:
        chosen = answers['subscription']
        console.print(f"\n🔄 Mudando para a assinatura [bold blue]{chosen}[/]...", style="bold blue")
        if set_azure_subscription(chosen):
            console.print("✅ Assinatura alterada com sucesso!", style="bold green")
        else:
            console.print("❌ Erro ao alterar a assinatura.", style="bold red")
            return

    console.print("\n📋 Agora use 'ekli init-azure' para configurar seu cluster AKS.", style="bold blue")
