import click
from rich.console import Console
from rich.table import Table
from kubernetes import client
from ..utils import session
import time

console = Console()

@click.command()
def namespaces():
    """📋 Lista todos os namespaces disponíveis no cluster"""
    try:
        # Carrega a configuração do kubernetes
        session.load_kube()
        v1 = client.CoreV1Api()
        
        # Cria uma tabela rica para exibir os namespaces
        table = Table(title="📋 Namespaces Disponíveis", show_header=True)
        table.add_column("Nome", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Idade", style="yellow")
        
        # Lista os namespaces
        namespaces = v1.list_namespace()
        
        for ns in namespaces.items:
            # Calcula a idade do namespace
            creation_time = ns.metadata.creation_timestamp
            age = time.time() - creation_time.timestamp()
            age_str = ""
            
            if age < 3600:  # menos de 1 hora
                age_str = f"{int(age/60)}m"
            elif age < 86400:  # menos de 1 dia
                age_str = f"{int(age/3600)}h"
            else:
                age_str = f"{int(age/86400)}d"
            
            table.add_row(
                ns.metadata.name,
                ns.status.phase,
                age_str
            )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"❌ Erro ao listar namespaces: {str(e)}", style="bold red")
        return 