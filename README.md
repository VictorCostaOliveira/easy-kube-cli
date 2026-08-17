# Easy Kube Cli

CLI para simplificar operações diárias no Kubernetes (AWS EKS e Azure AKS).

**Comandos:** `kube-cli` (principal) e `ekli` (atalho).

## Instalação rápida

### Pré-requisitos

- Python **3.10+** (recomendado: Python do Homebrew no macOS, linkado a OpenSSL, para evitar avisos do urllib3 com LibreSSL do sistema)
- Linux (Ubuntu) ou macOS

```bash
git clone git@github.com:VictorCostaOliveira/easy-kube-cli.git
cd easy-kube-cli
./install.sh
```

Ou configure o remote em um clone existente:

```bash
git remote add origin git@github.com:VictorCostaOliveira/easy-kube-cli.git
```

### Migrando da versão antiga (jera-cli)

- Copie `~/.jera/config` para `~/.easy-kube-cli/config` (crie o diretório se precisar), ou rode `kube-cli init` de novo.
- Desinstale bins antigos (`jeracli`, `jcli`) se ainda existirem; use `./uninstall.sh` da versão nova para limpar destinos atuais e legados quando fizer sentido.

### macOS: avisos urllib3 / OpenSSL

Se aparecer `NotOpenSSLWarning` do urllib3, use Python **3.10+** instalado via **Homebrew** (build com OpenSSL), não só o `/usr/bin/python3` do sistema. Este projeto fixa **urllib3 menor que 2.x** nas dependências para reduzir esse problema em LibreSSL.

## Uso Básico

### Opção 1: AWS
```bash
# Faça login no AWS SSO
kube-cli login-aws

# Configure o acesso ao cluster EKS
kube-cli init
```

### Opção 2: Azure
```bash
# Faça login no Azure
kube-cli login-azure

# Configure o acesso ao cluster AKS
kube-cli init-azure
```

### 3. Selecionar Namespace
```bash
# Escolha um namespace para trabalhar
kube-cli use production
```

### Alternando entre Clusters
```bash
# Liste todos os clusters configurados
kube-cli clusters

# Alterne para outro cluster (AWS ou Azure)
kube-cli use-cluster

# Alterne explicitamente entre AWS e Azure
kube-cli use-cluster -s

# Escolha um cluster AWS específico
kube-cli use-cluster meu-cluster-aws

# Escolha um cluster Azure específico
kube-cli use-cluster meu-cluster-aks -az -g meu-grupo-recursos
```

### Sessões por aba

Cada aba do terminal é uma sessão própria: cluster, profile AWS e namespace ficam
isolados por aba, então dá para trabalhar em dois clusters ao mesmo tempo — inclusive
em contas diferentes sob o mesmo SSO.

```bash
# aba 1
ekli use-cluster        # conta A -> cluster A
ekli use                # namespace da aba 1

# aba 2 — a aba 1 continua no cluster A
ekli use-cluster        # conta B -> cluster B

ekli status             # cluster, profile e namespace desta aba
eval $(ekli env)        # faz o kubectl digitado à mão seguir esta aba
```

Uma aba nova herda o estado da última sessão usada e passa a ter estado próprio no
primeiro `use-cluster` ou `use`. Trocar de cluster limpa o namespace da aba, porque o
namespace anterior não existe no cluster novo.

A chave da sessão é o TTY da aba. Para uma sessão nomeada, que sobrevive ao fechar a
aba: `export EKLI_SESSION=prod`.

O estado vive em `~/.easy-kube-cli/sessions/<chave>/`, com um `kubeconfig` por sessão —
o `~/.kube/config` global não é mais reescrito nas trocas de cluster.

## Comparação com kubectl

Esta CLI nasceu porque, ao trabalhar entre namespaces, repetir `kubectl` e `-n meu-namespace` o tempo todo fica cansativo. A Easy Kube Cli reduz isso no dia a dia. Comparação com os comandos mais frequentes:

| Funcionalidade               | Easy Kube Cli                   | kubectl                                                    |
|------------------------------|--------------------------------|-----------------------------------------------------------|
| **Seleção de contexto**      | `kube-cli use-cluster`          | `kubectl config use-context <context>`                    |
| **Configuração de cluster AWS** | `kube-cli init`              | `aws eks update-kubeconfig --name <cluster>`              |
| **Configuração de cluster Azure** | `kube-cli init-azure`      | `az aks get-credentials --resource-group <rg> --name <cluster>` |
| **Seleção de namespace**     | `kube-cli use <namespace>`      | `kubectl config set-context --current --namespace=<namespace>` |
| **Listar pods**              | `kube-cli pods`                 | `kubectl get pods`                                         |
| **Ver logs de um pod**       | `kube-cli logs <pod>`           | `kubectl logs <pod>`                                       |
| **Executar shell em um pod** | `kube-cli exec <pod>`           | `kubectl exec -it <pod> -- /bin/sh`                       |
| **Ver detalhes de um pod**   | `kube-cli describe <pod>`       | `kubectl describe pod <pod>`                              |
| **Listar serviços**          | `kube-cli loadbalancer` ou `lb` | `kubectl get svc`                                         |
| **Listar ingresses**         | `kube-cli urls`                 | `kubectl get ingress --all-namespaces`                    |
| **Listar nós**               | `kube-cli nodes`                | `kubectl get nodes`                                       |
| **Ver métricas de nós**      | `kube-cli node-metrics`         | `kubectl top nodes`                                       |
| **Ver volumes persistentes** | `kube-cli pvs`                  | `kubectl get pv`                                          |
| **Ver claims de volumes**    | `kube-cli pvcs`                 | `kubectl get pvc --all-namespaces`                        |

### Principais vantagens

- **Simplicidade**: Comandos mais curtos e intuitivos
- **Interatividade**: Muitos comandos oferecem seleção interativa quando não especificados todos os parâmetros
- **Integração com cloud**: Gerencia automaticamente a autenticação com AWS e Azure
- **Comandos consolidados**: Agrega múltiplas operações kubectl em um único comando
- **Visualização otimizada**: Saída formatada e focada nas informações mais relevantes

### Comandos Principais

#### Listar Pods
```bash
# Lista pods no namespace atual
kube-cli pods
```

#### Ver Logs
```bash
# Ver logs de um pod (interativo)
kube-cli logs
```

#### Executar Shell em um Pod
```bash
# Abrir shell em um pod
kube-cli exec
```

## Comandos Disponíveis

- `login-aws`: Faz login no AWS SSO interativamente
- `login-azure`: Faz login no Azure interativamente
- `init`: Configura AWS SSO e kubectl para cluster EKS
- `init-azure`: Configura kubectl para cluster AKS
- `use-cluster`: Alterna o cluster desta sessão (AWS EKS ou Azure AKS)
- `use`: Define o namespace desta sessão
- `status`: Mostra cluster, profile e namespace desta sessão
- `env`: Exporta a sessão para o shell (`eval $(ekli env)`)
- `pods`: Lista pods
- `logs`: Visualiza logs de pods
- `exec`: Abre shell em pods
- `describe`: Mostra detalhes de pods
- `urls`: Lista URLs de Ingresses
- `loadbalancer`: Lista URLs dos LoadBalancers
- `lb`: Alias para loadbalancer
- `pvs`: Mostra Persistent Volumes
- `pvcs`: Mostra Persistent Volume Claims
- `storage`: Visão consolidada de armazenamento
- `nodes`: Lista nós do cluster
- `node-metrics`: Mostra métricas de utilização dos nós

## Desenvolvimento

### Configuração do Ambiente

1. Clone o repositório
```bash
git clone git@github.com:VictorCostaOliveira/easy-kube-cli.git
cd easy-kube-cli
```

2. Crie um ambiente virtual
```bash
python3 -m venv .venv
source .venv/bin/activate
```

3. Instale as dependências
```bash
pip install -e .
```

### Padrões de Desenvolvimento

#### Branches
- `feature/`: Para novas funcionalidades
- `fix/`: Para correções de bugs
- `improvement/`: Para melhorias em funcionalidades existentes

#### Commits
Use o padrão de commits semânticos:
- `feat:` Nova funcionalidade
- `fix:` Correção de bug
- `docs:` Alterações na documentação
- `style:` Formatação de código
- `refactor:` Refatoração
- `test:` Adição/modificação de testes
- `chore:` Tarefas de manutenção

### Exemplo de Commit
```bash
git commit -m "feat: adiciona opção de filtro por status nos pods"
```

### Pull Request
1. Crie uma branch para sua alteração
2. Faça suas modificações
3. Teste localmente
4. Crie um Pull Request com descrição clara

## Suporte

Em caso de dúvidas, entre em contato com a equipe de desenvolvimento.

## Licença

[Informações sobre a licença]

## Exemplos de Uso

### Cenário 1: Investigando um Pod com Problema
```bash
# Liste todos os pods
kube-cli pods

# Veja os logs de um pod específico
kube-cli logs meu-pod-nome

# Obtenha detalhes completos do pod
kube-cli describe meu-pod-nome
```

### Cenário 2: Acessando um Container
```bash
# Abra um shell interativo em um pod
kube-cli exec meu-pod-nome

# Execute um comando específico em um pod
kube-cli exec meu-pod-nome -- ls /app
```

### Cenário 3: Gerenciando Namespaces
```bash
# Liste todos os namespaces disponíveis
kube-cli namespaces

# Mude para um namespace específico
kube-cli use production

# Veja os pods no namespace atual
kube-cli pods
```

### Cenário 4: Verificando URLs de Ingress
```bash
# Liste URLs de Ingress em todos os namespaces
kube-cli urls

# Liste URLs de Ingress em um namespace específico
kube-cli urls -n staging

# Liste URLs dos LoadBalancers
kube-cli lb
```

### Cenário 5: Análise de Recursos
```bash
# Veja métricas de todos os pods
kube-cli pod-metrics

# Veja métricas de pods em um namespace específico
kube-cli pod-metrics production

# Veja métricas dos nós do cluster
kube-cli node-metrics

# Veja métricas de um nó específico
kube-cli node-metrics nome-do-no
```

### Cenário 6: Visualizando Nós do Cluster
```bash
# Liste todos os nós do cluster
kube-cli nodes

# Veja detalhes de um nó específico
kube-cli describe node meu-node-nome
```

### Cenário 7: Gerenciando Armazenamento
```bash
# Listar todos os Persistent Volumes do cluster
kube-cli pvs

# Ver informações detalhadas dos PVs
kube-cli pvs -d

# Listar Persistent Volume Claims em todos os namespaces
kube-cli pvcs

# Listar PVCs em um namespace específico
kube-cli pvcs -n production

# Selecionar um namespace interativamente
kube-cli pvcs -s

# Ver visão consolidada de armazenamento
kube-cli storage

# Ver visão detalhada com filtro por namespace
kube-cli storage -n production -d
```

### Cenário 8: Deletando Pods
```bash
# Deleta um pod específico
kube-cli delete meu-pod

# Deleta múltiplos pods
kube-cli delete pod1 pod2

# Força a deleção de um pod
kube-cli delete meu-pod --force

# Deleta todos os pods do namespace atual
kube-cli delete --all

# Força a deleção de todos os pods
kube-cli delete --all --force
```

### Cenário 9: Trabalhando com Múltiplos Clusters
```bash
# AWS EKS
kube-cli login-aws
kube-cli init

# Azure AKS
kube-cli login-azure
kube-cli init-azure

# Alternar entre os clusters configurados
kube-cli use-cluster

# Alternar explicitamente entre AWS e Azure
kube-cli use-cluster -s

# Forçar o uso de Azure
kube-cli use-cluster -az

# Forçar o uso de AWS
kube-cli use-cluster --aws

# Especificar um cluster Azure com seu grupo de recursos
kube-cli use-cluster meu-cluster-aks -az -g meu-grupo-recursos
```

### Dicas Adicionais
- Use `kube-cli --help` para ver todos os comandos disponíveis
- Adicione `-h` ou `--help` após qualquer comando para ver opções específicas
  ```bash
  kube-cli pods --help
  kube-cli logs --help
  kube-cli use-cluster --help
  ```