import click
from rich.console import Console
from rich.table import Table
from kubernetes import client
from ..utils import session
from ..utils.kubernetes import format_age, parse_resource_value
import inquirer
import subprocess

console = Console()

@click.command()
def nodes():
    """Lista todos os nós do cluster com informações detalhadas."""
    try:
        session.load_kube()
        v1 = client.CoreV1Api()
        
        console.print("\n🔄 Obtendo informações dos nós...", style="yellow")
        
        nodes = v1.list_node()
        
        table = Table(title="📊 Nós do Cluster", show_header=True)
        table.add_column("Nome", style="cyan")
        table.add_column("Status", justify="center")
        table.add_column("Roles", style="blue")
        table.add_column("Versão", style="magenta")
        table.add_column("CPU", justify="right")
        table.add_column("Memória", justify="right")
        table.add_column("Idade", justify="right")
        
        for node in nodes.items:
            # Nome do nó
            name = node.metadata.name
            
            # Status
            status = "Ready"
            status_style = "green"
            for condition in node.status.conditions:
                if condition.type == "Ready":
                    if condition.status != "True":
                        status = "NotReady"
                        status_style = "red"
                    break
            
            # Roles
            roles = []
            for label, value in node.metadata.labels.items():
                if label.startswith("node-role.kubernetes.io/"):
                    role = label.split("/")[1]
                    roles.append(role)
            roles = ", ".join(roles) if roles else "worker"
            
            # Versão do Kubernetes
            version = node.status.node_info.kubelet_version
            
            # Recursos
            allocatable_cpu = node.status.allocatable.get('cpu', '0')
            allocatable_memory = node.status.allocatable.get('memory', '0')
            
            # Converte memória para GB
            memory_bytes = parse_resource_value(allocatable_memory, 'memory')
            memory_gb = round(memory_bytes / 1024, 1)  # Converte Mi para Gi
            
            # Idade
            age = format_age(node.metadata.creation_timestamp)
            
            table.add_row(
                name,
                f"[{status_style}]{status}[/{status_style}]",
                roles,
                version,
                f"{allocatable_cpu} cores",
                f"{memory_gb}Gi",
                age
            )
        
        console.print()
        console.print(table)
        console.print()
        
    except Exception as e:
        console.print(f"❌ Erro ao listar nós: {str(e)}", style="bold red")

@click.command()
@click.argument('node_name', required=False)
def describe_node(node_name=None):
    """Mostra informações detalhadas de um nó."""
    try:
        session.load_kube()
        v1 = client.CoreV1Api()
        
        # Lista todos os nós
        nodes = v1.list_node()
        node_names = [node.metadata.name for node in nodes.items]
        
        if not node_names:
            console.print("❌ Nenhum nó encontrado no cluster.", style="bold red")
            return
        
        selected_node = node_name
        
        # Se não foi fornecido um nó, mostra a lista interativa
        if not selected_node:
            questions = [
                inquirer.List('node',
                             message="Selecione um nó para ver detalhes",
                             choices=node_names,
                             )
            ]
            answers = inquirer.prompt(questions)
            
            if answers:
                selected_node = answers['node']
            else:
                return
        
        # Verifica se o nó existe
        if selected_node not in node_names:
            console.print(f"❌ Nó '{selected_node}' não encontrado.", style="bold red")
            return
        
        # Obtém os detalhes do nó
        node = next(node for node in nodes.items if node.metadata.name == selected_node)
        
        # Cria a tabela de informações gerais
        table = Table(title=f"📊 Detalhes do Nó: [bold cyan]{selected_node}[/]", show_header=True)
        table.add_column("Campo", style="blue")
        table.add_column("Valor")
        
        # Informações básicas
        table.add_row("Nome", node.metadata.name)
        table.add_row("UID", str(node.metadata.uid))
        table.add_row("Criado em", format_age(node.metadata.creation_timestamp))
        
        # Roles
        roles = []
        for label, value in node.metadata.labels.items():
            if label.startswith("node-role.kubernetes.io/"):
                role = label.split("/")[1]
                roles.append(role)
        table.add_row("Roles", ", ".join(roles) if roles else "worker")
        
        # Informações do sistema
        table.add_row("Arquitetura", node.status.node_info.architecture)
        table.add_row("Container Runtime", node.status.node_info.container_runtime_version)
        table.add_row("Kernel Version", node.status.node_info.kernel_version)
        table.add_row("OS Image", node.status.node_info.os_image)
        table.add_row("Kubelet Version", node.status.node_info.kubelet_version)
        
        # Status
        status = "Ready"
        status_style = "green"
        for condition in node.status.conditions:
            if condition.type == "Ready":
                if condition.status != "True":
                    status = "NotReady"
                    status_style = "red"
                break
        table.add_row("Status", f"[{status_style}]{status}[/{status_style}]")
        
        # Recursos
        allocatable_cpu = node.status.allocatable.get('cpu', '0')
        allocatable_memory = node.status.allocatable.get('memory', '0')
        memory_gb = round(parse_resource_value(allocatable_memory, 'memory') / 1024, 1)
        
        table.add_row("CPU Alocável", f"{allocatable_cpu} cores")
        table.add_row("Memória Alocável", f"{memory_gb}Gi")
        
        console.print()
        console.print(table)
        
        # Tabela de condições
        conditions_table = Table(title="\n🔄 Condições", show_header=True)
        conditions_table.add_column("Tipo", style="cyan")
        conditions_table.add_column("Status", style="yellow")
        conditions_table.add_column("Última Transição", style="blue")
        conditions_table.add_column("Mensagem")
        
        for condition in node.status.conditions:
            status_style = "green" if condition.status == "True" else "red"
            conditions_table.add_row(
                condition.type,
                f"[{status_style}]{condition.status}[/{status_style}]",
                format_age(condition.last_transition_time),
                condition.message or "N/A"
            )
        
        console.print()
        console.print(conditions_table)
        
        # Eventos relacionados ao nó
        events = v1.list_event_for_all_namespaces(
            field_selector=f'involvedObject.name={selected_node},involvedObject.kind=Node'
        )
        
        if events.items:
            events_table = Table(title="\n📝 Eventos Recentes", show_header=True)
            events_table.add_column("Tipo", style="cyan")
            events_table.add_column("Razão", style="yellow")
            events_table.add_column("Idade", style="blue")
            events_table.add_column("Mensagem")
            
            for event in events.items:
                events_table.add_row(
                    event.type,
                    event.reason,
                    format_age(event.first_timestamp),
                    event.message
                )
            
            console.print()
            console.print(events_table)
        
        console.print()
        
    except Exception as e:
        console.print(f"❌ Erro ao descrever nó: {str(e)}", style="bold red")

# Mantém o comando "describe" para compatibilidade com versões anteriores
@click.command(name="describe")
@click.argument('node_name', required=False)
def describe(node_name=None):
    """Alias para describe-node. Mostra informações detalhadas de um nó."""
    return describe_node(node_name)

@click.command(name="node-metrics")
@click.argument('node_name', required=False)
def node_metrics(node_name=None):
    """Mostra métricas de utilização de CPU e memória por nó com os top 5 pods que mais consomem recursos."""
    try:
        session.load_kube()
        v1 = client.CoreV1Api()
        
        console.print("\n🔄 Obtendo informações de utilização dos nós...", style="yellow")
        
        # Obter lista de nós
        nodes_list = v1.list_node()
        nodes_info = {}
        
        # Se um nó específico for fornecido, filtra a lista
        if node_name:
            nodes_list.items = [n for n in nodes_list.items if n.metadata.name == node_name]
            if not nodes_list.items:
                console.print(f"❌ Nó '{node_name}' não encontrado.", style="bold red")
                return
        
        # Obtém informações de métricas dos nós
        try:
            result = subprocess.run(
                ["kubectl", "top", "nodes"],
                capture_output=True,
                text=True,
                check=True
            )
            metrics_lines = result.stdout.strip().split('\n')[1:]  # Pula o cabeçalho
            
            for line in metrics_lines:
                parts = line.split()
                if len(parts) >= 5:
                    node_name = parts[0]
                    cpu_usage = parts[1]
                    cpu_percent = parts[2]
                    memory_usage = parts[3]
                    memory_percent = parts[4]
                    
                    nodes_info[node_name] = {
                        'cpu_usage': cpu_usage,
                        'cpu_percent': cpu_percent,
                        'memory_usage': memory_usage,
                        'memory_percent': memory_percent,
                        'top_pods': [],
                        'total_cpu_request': 0,
                        'total_cpu_limit': 0,
                        'total_pods_cpu_usage': 0,
                        'total_pods_memory_usage': 0
                    }
        except subprocess.CalledProcessError as e:
            console.print(f"❌ Erro ao obter métricas de nós: {e}", style="bold red")
            return
        
        # Obtém todos os pods em todos os namespaces
        all_pods = v1.list_pod_for_all_namespaces(watch=False)
        
        # Agrupa pods por nó
        pods_by_node = {}
        for pod in all_pods.items:
            node = pod.spec.node_name
            if node not in pods_by_node:
                pods_by_node[node] = []
            pods_by_node[node].append(pod)
        
        # Para cada nó, obtém os top 5 pods que mais consomem CPU
        for node_name, pods in pods_by_node.items():
            if node_name not in nodes_info:
                continue
                
            # Lista de todos os pods com seus namespaces
            pods_with_namespaces = [(pod.metadata.namespace, pod.metadata.name, pod) for pod in pods]
            
            # Obter métricas de todos os pods por namespace
            pod_metrics_by_namespace = {}
            namespaces = set([ns for ns, _, _ in pods_with_namespaces])
            
            for namespace in namespaces:
                try:
                    result = subprocess.run(
                        ["kubectl", "top", "pods", "-n", namespace],
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    metrics_lines = result.stdout.strip().split('\n')[1:]  # Pula o cabeçalho
                    
                    for line in metrics_lines:
                        parts = line.split()
                        if len(parts) >= 3:
                            pod_name = parts[0]
                            cpu = parts[1]
                            memory = parts[2]
                            
                            # Remove o sufixo 'm' e converte para inteiro
                            cpu_value = int(cpu.replace('m', ''))
                            # Remove o sufixo 'Mi' e converte para inteiro
                            memory_value = int(memory.replace('Mi', ''))
                            
                            pod_metrics_by_namespace[(namespace, pod_name)] = {
                                'cpu': cpu,
                                'cpu_value': cpu_value,
                                'memory': memory,
                                'memory_value': memory_value
                            }
                except subprocess.CalledProcessError:
                    continue
            
            # Filtra apenas os pods que estão no nó atual e obtém limites de CPU
            pod_metrics = []
            total_cpu_request = 0
            total_cpu_limit = 0
            total_pods_cpu_usage = 0
            total_pods_memory_usage = 0
            
            for ns_pod_obj in pods_with_namespaces:
                ns, pod_name, pod_obj = ns_pod_obj
                ns_pod = (ns, pod_name)
                
                if ns_pod in pod_metrics_by_namespace:
                    metrics = pod_metrics_by_namespace[ns_pod]
                    
                    # Obtém limites de CPU do pod
                    cpu_request = 0
                    cpu_limit = 0
                    
                    if pod_obj.spec.containers:
                        for container in pod_obj.spec.containers:
                            if container.resources:
                                if container.resources.requests and 'cpu' in container.resources.requests:
                                    cpu_request += parse_resource_value(container.resources.requests.get('cpu', '0'), 'cpu')
                                if container.resources.limits and 'cpu' in container.resources.limits:
                                    cpu_limit += parse_resource_value(container.resources.limits.get('cpu', '0'), 'cpu')
                    
                    # Acumula os totais
                    total_cpu_request += cpu_request
                    total_cpu_limit += cpu_limit
                    total_pods_cpu_usage += metrics['cpu_value']
                    total_pods_memory_usage += metrics['memory_value']
                    
                    pod_metrics.append({
                        'namespace': ns,
                        'name': pod_name,
                        'cpu': metrics['cpu'],
                        'cpu_value': metrics['cpu_value'],
                        'cpu_request': cpu_request,
                        'cpu_limit': cpu_limit,
                        'memory': metrics['memory'],
                        'memory_value': metrics['memory_value']
                    })
            
            # Ordena por uso de CPU (do maior para o menor)
            pod_metrics.sort(key=lambda x: x['cpu_value'], reverse=True)
            
            # Armazena os top 5 pods e totais
            nodes_info[node_name]['top_pods'] = pod_metrics[:5]
            nodes_info[node_name]['total_cpu_request'] = total_cpu_request
            nodes_info[node_name]['total_cpu_limit'] = total_cpu_limit
            nodes_info[node_name]['total_pods_cpu_usage'] = total_pods_cpu_usage
            nodes_info[node_name]['total_pods_memory_usage'] = total_pods_memory_usage
        
        # Cria tabela principal para nós
        nodes_table = Table(title="📊 Métricas de Utilização dos Nós", show_header=True)
        nodes_table.add_column("Nome", style="cyan")
        nodes_table.add_column("Status", justify="center")
        nodes_table.add_column("CPU Alocável", justify="right", style="blue")
        nodes_table.add_column("CPU Req", justify="right", style="blue")
        nodes_table.add_column("CPU Uso", justify="right", style="green")
        nodes_table.add_column("CPU %", justify="right", style="yellow")
        nodes_table.add_column("Mem Alocável", justify="right", style="blue")
        nodes_table.add_column("Mem Uso", justify="right", style="green")
        nodes_table.add_column("Mem %", justify="right", style="yellow")
        
        # Exibe as informações para cada nó
        for i, node in enumerate(nodes_list.items):
            name = node.metadata.name
            
            if name not in nodes_info:
                continue
            
            node_metrics = nodes_info[name]
            
            # Obtém recursos alocáveis do nó
            allocatable_cpu = node.status.allocatable.get('cpu', '0')
            allocatable_memory = node.status.allocatable.get('memory', '0')
            memory_gb = round(parse_resource_value(allocatable_memory, 'memory') / 1024, 1)
            
            # Status do nó
            status = "Ready" if any(c.type == 'Ready' and c.status == 'True' for c in node.status.conditions) else "NotReady"
            status_style = "green" if status == "Ready" else "red"
            
            # Prepara informações de CPU solicitada
            total_cpu_request_m = node_metrics['total_cpu_request']
            cpu_request_percent = "N/A"
            
            # Converte allocatable_cpu para milicores para comparação
            allocatable_cpu_m = parse_resource_value(allocatable_cpu, 'cpu')
            
            if allocatable_cpu_m > 0:
                request_percent = (total_cpu_request_m / allocatable_cpu_m) * 100
                request_color = "yellow"
                
                if request_percent > 100:
                    request_color = "red bold"
                
                cpu_request_percent = f"({request_percent:.1f}%)"
            
            nodes_table.add_row(
                name,
                f"[{status_style}]{status}[/{status_style}]",
                f"{allocatable_cpu} cores",
                f"{total_cpu_request_m}m {cpu_request_percent}",
                f"{node_metrics['cpu_usage']} ({node_metrics['total_pods_cpu_usage']}m)",
                node_metrics['cpu_percent'],
                f"{memory_gb}Gi",
                f"{node_metrics['memory_usage']} ({node_metrics['total_pods_memory_usage']}Mi)",
                node_metrics['memory_percent']
            )
        
        console.print()
        console.print(nodes_table)
        console.print()
        
        # Agora exibe os top 5 pods de cada nó
        for node in nodes_list.items:
            name = node.metadata.name
            
            if name not in nodes_info or not nodes_info[name]['top_pods']:
                continue
            
            console.print(f"[bold cyan]Top 5 Pods por Consumo de CPU no Nó: {name}[/]")
            
            # Adiciona informações de CPU e memória total
            node_metrics = nodes_info[name]
            allocatable_cpu = node.status.allocatable.get('cpu', '0')
            allocatable_cpu_m = parse_resource_value(allocatable_cpu, 'cpu')
            
            console.print(f"Total CPU: {node_metrics['total_pods_cpu_usage']}m de {allocatable_cpu_m}m alocáveis ({node_metrics['cpu_percent']})")
            console.print(f"CPU Solicitado: {node_metrics['total_cpu_request']}m ({(node_metrics['total_cpu_request'] / allocatable_cpu_m * 100):.1f}% do total alocável)")
            console.print(f"Total Memória: {node_metrics['total_pods_memory_usage']}Mi {node_metrics['memory_percent']}")
            console.print()
            
            pods_table = Table(show_header=True)
            pods_table.add_column("Rank", style="dim", width=4)
            pods_table.add_column("Namespace", style="magenta")
            pods_table.add_column("Pod", style="cyan")
            pods_table.add_column("CPU Req", justify="right", style="blue")
            pods_table.add_column("CPU Lim", justify="right", style="blue")
            pods_table.add_column("CPU Uso", justify="right", style="green")
            pods_table.add_column("CPU %", justify="right", style="yellow")
            pods_table.add_column("Memória", justify="right", style="blue")
            
            for idx, pod in enumerate(nodes_info[name]['top_pods'], 1):
                # Calcula porcentagem do uso em relação ao request
                cpu_percent = "N/A"
                if pod['cpu_request'] > 0:
                    cpu_percent_value = (pod['cpu_value'] / pod['cpu_request']) * 100
                    cpu_color = "yellow"
                    
                    if cpu_percent_value > 100:
                        cpu_color = "red bold"
                    
                    cpu_percent = f"[{cpu_color}]{cpu_percent_value:.1f}%[/{cpu_color}]"
                
                pods_table.add_row(
                    str(idx),
                    pod['namespace'],
                    pod['name'],
                    f"{pod['cpu_request']}m" if pod['cpu_request'] > 0 else "0m",
                    f"{pod['cpu_limit']}m" if pod['cpu_limit'] > 0 else "∞",
                    pod['cpu'],
                    cpu_percent,
                    pod['memory']
                )
            
            console.print(pods_table)
            console.print()
        
    except Exception as e:
        console.print(f"❌ Erro ao obter métricas dos nós: {str(e)}", style="bold red") 