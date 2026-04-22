#!/bin/bash

# Cores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}🚀 Instalando Easy Kube Cli...${NC}\n"

# Verifica se está rodando como sudo no Linux, mas não no macOS
if [[ "$OSTYPE" == "linux-gnu"* ]] && [ "$EUID" -ne 0 ]; then 
    echo -e "${YELLOW}⚠️  Executando com sudo para instalação global...${NC}"
    sudo "$0" "$@"
    exit $?
fi

# Define os diretórios com base no sistema operacional
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS - instala no diretório do usuário
    INSTALL_DIR="$HOME/.easy-kube-cli"
    WRAPPER_SCRIPT="$HOME/.local/bin/kube-cli"
    ALIAS_SCRIPT="$HOME/.local/bin/ek-cli"
    
    # Garante que o diretório .local/bin existe e está no PATH
    mkdir -p "$HOME/.local/bin"
    
    # Adiciona ao PATH se não estiver
    if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
        echo -e "${YELLOW}📝 Adicionando $HOME/.local/bin ao PATH...${NC}"
        if [[ -f "$HOME/.zshrc" ]]; then
            echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.zshrc"
            echo -e "${YELLOW}✅ Adicionado ao .zshrc. Execute 'source ~/.zshrc' após a instalação.${NC}"
        fi
        if [[ -f "$HOME/.bash_profile" ]]; then
            echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bash_profile"
            echo -e "${YELLOW}✅ Adicionado ao .bash_profile. Execute 'source ~/.bash_profile' após a instalação.${NC}"
        fi
    fi
else
    # Linux - instala globalmente
    INSTALL_DIR="/opt/easy-kube-cli"
    WRAPPER_SCRIPT="/usr/local/bin/kube-cli"
    ALIAS_SCRIPT="/usr/local/bin/ek-cli"
fi

# Verifica se estamos em um sistema Debian/Ubuntu
if [[ "$OSTYPE" == "linux-gnu"* ]] && [ -f /etc/os-release ]; then
    source /etc/os-release
    if [[ "$ID" == "ubuntu" || "$ID" == "debian" || "$ID_LIKE" == *"ubuntu"* || "$ID_LIKE" == *"debian"* ]]; then
        echo -e "${YELLOW}📦 Sistema baseado em Debian/Ubuntu detectado. Verificando pacotes necessários...${NC}"
        
        # Verifica a versão do Python
        if command -v python3 &> /dev/null; then
            PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
            echo -e "${YELLOW}📦 Versão do Python detectada: ${PYTHON_VERSION}${NC}"
            
            # Verifica se o pacote venv específico está instalado
            VENV_PACKAGE="python${PYTHON_VERSION}-venv"
            if ! dpkg -s "$VENV_PACKAGE" &> /dev/null; then
                echo -e "${YELLOW}⚠️ Pacote ${VENV_PACKAGE} não encontrado. Instalando...${NC}"
                apt-get update
                apt-get install -y python3-venv "$VENV_PACKAGE" || {
                    echo -e "${YELLOW}⚠️ Não foi possível instalar ${VENV_PACKAGE} diretamente.${NC}"
                    
                    # Tenta instalar pacotes específicos para versões comuns
                    if [[ "$PYTHON_VERSION" == "3.8" ]]; then
                        echo -e "${YELLOW}📦 Instalando python3.8-venv...${NC}"
                        apt-get install -y python3.8-venv python3.8-dev
                    fi
                }
            else
                echo -e "${GREEN}✅ Pacote ${VENV_PACKAGE} já está instalado.${NC}"
            fi
        fi
    fi
fi

# Função para instalar Python e pip no Ubuntu
install_python_ubuntu() {
    echo -e "${YELLOW}📦 Instalando Python 3.10+ no Ubuntu...${NC}"
    
    # Adiciona repositório para versões mais recentes do Python
    apt-get update
    apt-get install -y software-properties-common
    add-apt-repository -y ppa:deadsnakes/ppa
    apt-get update
    
    # Instala Python 3.10 e pip apenas se não estiverem instalados
    if ! dpkg -s python3.10 &> /dev/null; then
        apt-get install -y python3.10 python3.10-venv python3.10-dev
        
        # Define Python 3.10 como padrão
        update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1
        update-alternatives --set python3 /usr/bin/python3.10
    else
        echo -e "${GREEN}✅ Python 3.10 já está instalado.${NC}"
    fi
    
    # Instala pacotes de desenvolvimento e pip
    apt-get install -y python3-pip python3-dev python3-setuptools python3-wheel
    
    # Garante que o pacote venv esteja instalado para a versão do Python em uso
    PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    echo -e "${YELLOW}📦 Instalando python${PYTHON_VERSION}-venv...${NC}"
    apt-get install -y python3-venv "python${PYTHON_VERSION}-venv" || apt-get install -y python3-venv
    
    echo -e "${GREEN}✅ Pacotes de desenvolvimento Python instalados.${NC}"
}

# Coloca no PATH um python3 do Homebrew com versão >= 3.10 (Apple Silicon ou Intel).
macos_prepend_homebrew_python() {
    if ! command -v brew &> /dev/null; then
        return 1
    fi
    # shellcheck disable=SC1090
    if [[ -x /opt/homebrew/bin/brew ]]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    elif [[ -x /usr/local/bin/brew ]]; then
        eval "$(/usr/local/bin/brew shellenv)"
    fi
    local formula prefix bin
    for formula in python@3.13 python@3.12 python@3.11 python@3.10 python; do
        prefix="$(brew --prefix "$formula" 2>/dev/null)" || continue
        bin="${prefix}/bin"
        if [[ -x "${bin}/python3" ]] && "${bin}/python3" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
            export PATH="${bin}:${PATH}"
            return 0
        fi
    done
    return 1
}

# Função para instalar Python e pip no macOS
install_python_macos() {
    echo -e "${YELLOW}📦 Instalando Python 3.10+ no macOS via Homebrew...${NC}"
    
    # Verifica se o Homebrew está instalado
    if ! command -v brew &> /dev/null; then
        echo -e "${YELLOW}🍺 Instalando Homebrew...${NC}"
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        if [[ -x /opt/homebrew/bin/brew ]]; then
            eval "$(/opt/homebrew/bin/brew shellenv)"
        elif [[ -x /usr/local/bin/brew ]]; then
            eval "$(/usr/local/bin/brew shellenv)"
        fi
    fi
    
    # Instala Python 3.10 apenas se não estiver instalado
    if ! brew list python@3.10 &> /dev/null; then
        brew install python@3.10
    else
        echo -e "${GREEN}✅ Python 3.10 (formula python@3.10) já está instalado via Homebrew.${NC}"
    fi
    
    local py10_bin
    py10_bin="$(brew --prefix python@3.10 2>/dev/null)/bin"
    if [[ -d "$py10_bin" ]]; then
        export PATH="${py10_bin}:${PATH}"
        # Sugere PATH permanente (caminho real do prefix, funciona em Intel e Apple Silicon)
        if [[ -f "$HOME/.zshrc" ]] && ! grep -q 'easy-kube-cli: python@3.10' "$HOME/.zshrc" 2>/dev/null; then
            echo "# easy-kube-cli: python@3.10 (Homebrew)" >> "$HOME/.zshrc"
            echo "export PATH=\"${py10_bin}:\$PATH\"" >> "$HOME/.zshrc"
            echo -e "${YELLOW}✅ PATH do Python Homebrew adicionado ao .zshrc. Rode: source ~/.zshrc${NC}"
        fi
        if [[ -f "$HOME/.bash_profile" ]] && ! grep -q 'easy-kube-cli: python@3.10' "$HOME/.bash_profile" 2>/dev/null; then
            echo "# easy-kube-cli: python@3.10 (Homebrew)" >> "$HOME/.bash_profile"
            echo "export PATH=\"${py10_bin}:\$PATH\"" >> "$HOME/.bash_profile"
            echo -e "${YELLOW}✅ PATH do Python Homebrew adicionado ao .bash_profile.${NC}"
        fi
    fi
    
    # Instala pacotes de desenvolvimento
    brew install python-setuptools python-wheel 2>/dev/null || true
    
    echo -e "${GREEN}✅ Pacotes de desenvolvimento Python instalados.${NC}"
}

# Função para verificar e instalar Python
check_python() {
    # macOS: o /usr/bin/python3 costuma ser 3.9 — prioriza Homebrew 3.10+ antes de validar
    if [[ "$OSTYPE" == "darwin"* ]]; then
        if ! macos_prepend_homebrew_python; then
            echo -e "${YELLOW}⚠️  Nenhum Python 3.10+ do Homebrew encontrado no PATH. Tentando instalar...${NC}"
            install_python_macos
            macos_prepend_homebrew_python || true
        fi
    fi

    # Verifica se Python 3.10+ está instalado
    if ! command -v python3 &> /dev/null; then
        echo -e "${YELLOW}⚠️  Python 3 não encontrado. Instalando...${NC}"
        
        if [[ "$OSTYPE" == "linux-gnu"* ]]; then
            # Linux (Ubuntu)
            install_python_ubuntu
            
        elif [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS
            install_python_macos
            macos_prepend_homebrew_python || true
            
        else
            echo -e "${RED}❌ Sistema operacional não suportado para instalação automática do Python.${NC}"
            echo -e "${YELLOW}Por favor, instale manualmente o Python 3.10+.${NC}"
            exit 1
        fi
    fi
    
    # Verifica a versão do Python de forma mais robusta
    PYTHON_MAJOR=$(python3 -c 'import sys; print(sys.version_info.major)')
    PYTHON_MINOR=$(python3 -c 'import sys; print(sys.version_info.minor)')
    
    # Verifica se a versão é maior ou igual a 3.10
    if [[ $PYTHON_MAJOR -lt 3 ]] || [[ $PYTHON_MAJOR -eq 3 && $PYTHON_MINOR -lt 10 ]]; then
        if [[ "$OSTYPE" == "darwin"* ]]; then
            echo -e "${YELLOW}⚠️  python3 atual é ${PYTHON_MAJOR}.${PYTHON_MINOR}. Instalando Python 3.10 via Homebrew...${NC}"
            install_python_macos
            macos_prepend_homebrew_python || true
            PYTHON_MAJOR=$(python3 -c 'import sys; print(sys.version_info.major)')
            PYTHON_MINOR=$(python3 -c 'import sys; print(sys.version_info.minor)')
        fi
    fi

    if [[ $PYTHON_MAJOR -lt 3 ]] || [[ $PYTHON_MAJOR -eq 3 && $PYTHON_MINOR -lt 10 ]]; then
        echo -e "${RED}❌ Python ${PYTHON_MAJOR}.${PYTHON_MINOR} não é suportado. Instale Python 3.10+.${NC}"
        if [[ "$OSTYPE" == "darwin"* ]]; then
            echo -e "${YELLOW}No macOS: brew install python@3.10 e garanta que o binário do Homebrew venha antes do /usr/bin no PATH (brew shellenv).${NC}"
        fi
        exit 1
    fi
    
    echo -e "${GREEN}✅ Python ${PYTHON_MAJOR}.${PYTHON_MINOR} verificado com sucesso!${NC}"
    
    # Verifica se o pacote venv está disponível para a versão do Python em uso
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Para sistemas baseados em Debian/Ubuntu
        PYTHON_VERSION="${PYTHON_MAJOR}.${PYTHON_MINOR}"
        VENV_PACKAGE="python${PYTHON_VERSION}-venv"
        
        echo -e "${YELLOW}📦 Verificando pacote ${VENV_PACKAGE}...${NC}"
        
        if ! dpkg -s python3-venv &> /dev/null || ! dpkg -s "$VENV_PACKAGE" &> /dev/null 2>&1; then
            echo -e "${YELLOW}⚠️ Instalando pacotes necessários para ambientes virtuais...${NC}"
            apt-get update
            apt-get install -y python3-venv
            
            # Tenta instalar o pacote específico para a versão do Python
            if [[ "$PYTHON_VERSION" == "3.8" ]]; then
                apt-get install -y python3.8-venv
            elif [[ "$PYTHON_VERSION" == "3.9" ]]; then
                apt-get install -y python3.9-venv
            elif [[ "$PYTHON_VERSION" == "3.10" ]]; then
                apt-get install -y python3.10-venv
            else
                apt-get install -y "$VENV_PACKAGE" || true
            fi
        else
            echo -e "${GREEN}✅ Pacote ${VENV_PACKAGE} já está instalado.${NC}"
        fi
    fi
}

# Garante pacotes de sistema para criar venv (não roda pip no Python do sistema — PEP 668 / externally-managed).
check_pip() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        apt-get install -y python3-venv python3-full 2>/dev/null || apt-get install -y python3-venv
        echo -e "${GREEN}✅ Ambiente Debian/Ubuntu pronto para venv (sem pip global).${NC}"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        echo -e "${GREEN}✅ macOS: pip será usado apenas dentro do .venv após python3 -m venv.${NC}"
    fi
}

# Função para verificar e instalar pacotes necessários para o ambiente virtual
install_venv_packages() {
    echo -e "${YELLOW}📦 Verificando pacotes necessários para ambientes virtuais...${NC}"
    
    # Detecta a versão do Python
    PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    echo -e "${YELLOW}📦 Versão do Python detectada: ${PYTHON_VERSION}${NC}"
    
    # Instala o pacote python3-venv genérico
    apt-get update
    apt-get install -y python3-venv python3-dev
    
    # Tenta instalar o pacote específico para a versão do Python
    VENV_PACKAGE="python${PYTHON_VERSION}-venv"
    echo -e "${YELLOW}📦 Tentando instalar ${VENV_PACKAGE}...${NC}"
    
    # Tenta instalar o pacote específico
    apt-get install -y "$VENV_PACKAGE" || {
        echo -e "${YELLOW}⚠️ Não foi possível instalar ${VENV_PACKAGE} diretamente.${NC}"
        echo -e "${YELLOW}⚠️ Tentando alternativas...${NC}"
        
        # Tenta instalar pacotes específicos para versões comuns
        if [[ "$PYTHON_VERSION" == "3.8" ]]; then
            apt-get install -y python3.8-venv python3.8-dev
        elif [[ "$PYTHON_VERSION" == "3.9" ]]; then
            apt-get install -y python3.9-venv python3.9-dev
        elif [[ "$PYTHON_VERSION" == "3.10" ]]; then
            apt-get install -y python3.10-venv python3.10-dev
        elif [[ "$PYTHON_VERSION" == "3.11" ]]; then
            apt-get install -y python3.11-venv python3.11-dev
        fi
    }
    
    # Instala virtualenv como alternativa
    apt-get install -y python3-virtualenv
    
    echo -e "${GREEN}✅ Pacotes para ambiente virtual instalados.${NC}"
}

# Verifica se o AWS CLI está instalado
check_aws_cli() {
    if ! command -v aws &> /dev/null; then
        echo -e "${YELLOW}⚠️  AWS CLI não encontrado. Instalando...${NC}"
        
        # Detecta o sistema operacional
        if [[ "$OSTYPE" == "linux-gnu"* ]]; then
            # Linux
            echo -e "${YELLOW}📦 Baixando AWS CLI para Linux...${NC}"
            curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
            apt-get update && apt-get install -y unzip
            unzip awscliv2.zip
            ./aws/install
            rm -rf aws awscliv2.zip
            
        elif [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS
            echo -e "${YELLOW}📦 Instalando AWS CLI via Homebrew...${NC}"
            brew install awscli
            
        else
            echo -e "${RED}❌ Sistema operacional não suportado para instalação automática do AWS CLI.${NC}"
            echo -e "${YELLOW}Por favor, instale manualmente:${NC}"
            echo -e "Windows: https://aws.amazon.com/cli/"
            echo -e "Linux/MacOS: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
            exit 1
        fi
        
        # Verifica se a instalação foi bem sucedida
        if command -v aws &> /dev/null; then
            echo -e "${GREEN}✅ AWS CLI instalado com sucesso!${NC}"
        else
            echo -e "${RED}❌ Falha ao instalar AWS CLI.${NC}"
            exit 1
        fi
    else
        echo -e "${GREEN}✅ AWS CLI já está instalado.${NC}"
    fi
}

# Verifica se o kubectl está instalado
check_kubectl() {
    if ! command -v kubectl &> /dev/null; then
        echo -e "${YELLOW}⚠️  kubectl não encontrado. Instalando...${NC}"
        
        # Detecta o sistema operacional
        if [[ "$OSTYPE" == "linux-gnu"* ]]; then
            # Linux
            echo -e "${YELLOW}📦 Baixando kubectl para Linux...${NC}"
            curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
            install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
            rm -f kubectl
            
        elif [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS
            echo -e "${YELLOW}📦 Instalando kubectl via Homebrew...${NC}"
            brew install kubectl
            
        else
            echo -e "${RED}❌ Sistema operacional não suportado para instalação automática do kubectl.${NC}"
            echo -e "${YELLOW}Por favor, instale manualmente seguindo:${NC}"
            echo -e "https://kubernetes.io/docs/tasks/tools/install-kubectl/"
            exit 1
        fi
        
        # Verifica se a instalação foi bem sucedida
        if command -v kubectl &> /dev/null; then
            echo -e "${GREEN}✅ kubectl instalado com sucesso!${NC}"
        else
            echo -e "${RED}❌ Falha ao instalar kubectl.${NC}"
            exit 1
        fi
    else
        echo -e "${GREEN}✅ kubectl já está instalado.${NC}"
    fi
}

# Chama as funções de verificação e instalação
check_python
check_pip

# Verifica e instala pacotes necessários para o ambiente virtual
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    install_venv_packages
fi

# Verifica e instala o AWS CLI se necessário
check_aws_cli

# Verifica e instala o kubectl se necessário
check_kubectl

# Remove o comando global
if [ -f "$WRAPPER_SCRIPT" ]; then
    echo -e "${YELLOW}🔄 Removendo instalação anterior...${NC}"
    rm -f "$WRAPPER_SCRIPT"
    rm -f "$ALIAS_SCRIPT"
fi

# Remove o diretório de instalação
if [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR"
fi

# Cria diretório de instalação
echo -e "${YELLOW}📁 Criando diretório de instalação...${NC}"
mkdir -p "$INSTALL_DIR"
cp -r . "$INSTALL_DIR"

# Cria o diretório para binários no macOS se ainda não existir
if [[ "$OSTYPE" == "darwin"* ]]; then
    mkdir -p "$(dirname "$WRAPPER_SCRIPT")"
fi

# Vai para o diretório de instalação
cd "$INSTALL_DIR"

# Verifica se o pacote venv está instalado (somente no Linux)
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    if ! dpkg -s python3-venv &> /dev/null; then
        echo -e "${YELLOW}⚠️ Pacote python3-venv não encontrado. Instalando...${NC}"
        apt-get install -y python3-venv
        
        # Tenta instalar o pacote específico para a versão do Python em uso
        PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        echo -e "${YELLOW}📦 Detectada versão Python ${PYTHON_VERSION}. Instalando python${PYTHON_VERSION}-venv...${NC}"
        
        # Tenta instalar o pacote específico para a versão do Python
        if [[ "$PYTHON_VERSION" == "3.8" ]]; then
            apt-get install -y python3.8-venv
        elif [[ "$PYTHON_VERSION" == "3.9" ]]; then
            apt-get install -y python3.9-venv
        elif [[ "$PYTHON_VERSION" == "3.10" ]]; then
            apt-get install -y python3.10-venv
        else
            apt-get install -y "python${PYTHON_VERSION}-venv" || true
        fi
    fi
fi

# Cria ambiente virtual no diretório de instalação
echo -e "${YELLOW}🔧 Criando ambiente virtual com Python $(python3 --version)...${NC}"

if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS — python3 -m venv não usa pip global (evita PEP 668)
    python3 -m venv .venv || {
        echo -e "${RED}❌ Falha ao criar ambiente virtual no macOS.${NC}"
        echo -e "${YELLOW}⚠️ Tentando virtualenv (último recurso; pode usar --user no Homebrew)...${NC}"
        PIP_BREAK_SYSTEM_PACKAGES=1 python3 -m pip install --user virtualenv 2>/dev/null || true
        python3 -m virtualenv .venv || {
            echo -e "${RED}❌ Todas as tentativas de criar o ambiente virtual falharam.${NC}"
            echo -e "${YELLOW}⚠️ Verifique se o Python está instalado corretamente no seu sistema.${NC}"
            exit 1
        }
    }
else
    # Linux - tenta diferentes métodos
    python3 -m venv .venv || {
        echo -e "${RED}❌ Falha ao criar ambiente virtual com python3 -m venv.${NC}"
        echo -e "${YELLOW}⚠️ Tentando método alternativo...${NC}"
        
        # Tenta usar o módulo virtualenv como alternativa
        apt-get install -y python3-virtualenv
        python3 -m virtualenv .venv || {
            echo -e "${RED}❌ Falha ao criar ambiente virtual com virtualenv.${NC}"
            echo -e "${YELLOW}⚠️ Tentando método com --without-pip...${NC}"
            
            # Tenta criar sem pip
            python3 -m venv --without-pip .venv || {
                echo -e "${RED}❌ Todas as tentativas de criar o ambiente virtual falharam.${NC}"
                
                # Verifica a versão do Python para sugerir o pacote correto
                PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
                
                echo -e "${YELLOW}Por favor, execute manualmente:${NC}"
                echo -e "${GREEN}sudo apt update${NC}"
                echo -e "${GREEN}sudo apt install -y python3-venv python${PYTHON_VERSION}-venv${NC}"
                
                # Mensagem específica para Python 3.8
                if [[ "$PYTHON_VERSION" == "3.8" ]]; then
                    echo -e "${GREEN}sudo apt install -y python3.8-venv python3.8-dev${NC}"
                fi
                
                echo -e "${YELLOW}E tente novamente.${NC}"
                
                # Oferece a opção de continuar sem ambiente virtual
                echo -e "${YELLOW}Deseja continuar a instalação sem ambiente virtual? (s/N)${NC}"
                read -r response
                if [[ "$response" =~ ^([sS][iI]|[sS])$ ]]; then
                    echo -e "${YELLOW}⚠️ Continuando sem ambiente virtual. A instalação pode não funcionar corretamente.${NC}"
                    mkdir -p .venv/bin
                    echo "#!/bin/bash" > .venv/bin/activate
                    echo "# Ambiente virtual simulado" >> .venv/bin/activate
                    chmod +x .venv/bin/activate
                else
                    echo -e "${RED}❌ Instalação abortada.${NC}"
                    exit 1
                fi
            }
            
            # Se criou sem pip, instala pip manualmente
            if [ -f ".venv/bin/python3" ]; then
                echo -e "${YELLOW}📦 Instalando pip no ambiente virtual...${NC}"
                curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
                .venv/bin/python3 get-pip.py
                rm get-pip.py
            fi
        }
    }
fi

# Verifica se o ambiente virtual foi criado com sucesso
if [ ! -f ".venv/bin/activate" ]; then
    echo -e "${RED}❌ Não foi possível criar o ambiente virtual. Abortando instalação.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Ambiente virtual criado com sucesso!${NC}"

# Ativa o ambiente virtual e instala dependências
echo -e "${YELLOW}🔧 Ativando ambiente virtual...${NC}"
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate || {
        echo -e "${RED}❌ Falha ao ativar o ambiente virtual.${NC}"
        echo -e "${YELLOW}⚠️ Tentando método alternativo...${NC}"
        
        # Tenta ativar usando o caminho completo
        source "$INSTALL_DIR/.venv/bin/activate" || {
            echo -e "${RED}❌ Não foi possível ativar o ambiente virtual.${NC}"
            echo -e "${YELLOW}⚠️ Continuando sem ambiente virtual ativado. A instalação pode falhar.${NC}"
            
            # Define variáveis de ambiente manualmente para simular ambiente virtual
            export VIRTUAL_ENV="$INSTALL_DIR/.venv"
            export PATH="$INSTALL_DIR/.venv/bin:$PATH"
        }
    }
else
    echo -e "${RED}❌ Arquivo de ativação do ambiente virtual não encontrado.${NC}"
    echo -e "${YELLOW}⚠️ Tentando criar manualmente...${NC}"
    
    mkdir -p .venv/bin
    echo "#!/bin/bash" > .venv/bin/activate
    echo "export VIRTUAL_ENV=\"$INSTALL_DIR/.venv\"" >> .venv/bin/activate
    echo "export PATH=\"\$VIRTUAL_ENV/bin:\$PATH\"" >> .venv/bin/activate
    chmod +x .venv/bin/activate
    
    source .venv/bin/activate || {
        echo -e "${RED}❌ Não foi possível ativar o ambiente virtual criado manualmente.${NC}"
        echo -e "${YELLOW}⚠️ Continuando sem ambiente virtual ativado. A instalação pode falhar.${NC}"
        
        # Define variáveis de ambiente manualmente
        export VIRTUAL_ENV="$INSTALL_DIR/.venv"
        export PATH="$INSTALL_DIR/.venv/bin:$PATH"
    }
fi

# Verifica se o ambiente virtual está ativo
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo -e "${YELLOW}⚠️ Ambiente virtual não foi ativado corretamente.${NC}"
    echo -e "${YELLOW}⚠️ Continuando sem ambiente virtual. A instalação pode falhar.${NC}"
    
    # Define variáveis de ambiente manualmente
    export VIRTUAL_ENV="$INSTALL_DIR/.venv"
    export PATH="$INSTALL_DIR/.venv/bin:$PATH"
else
    echo -e "${GREEN}✅ Ambiente virtual ativado com sucesso!${NC}"
fi

# Sempre usa o Python do venv (nunca pip no sistema — PEP 668 / externally-managed)
VENV_PY="${INSTALL_DIR}/.venv/bin/python"
if [[ ! -x "$VENV_PY" ]]; then
    echo -e "${RED}❌ Interpretador do venv não encontrado: ${VENV_PY}${NC}"
    exit 1
fi

# Atualiza pip e setuptools dentro do venv
echo -e "${YELLOW}📦 Atualizando pip/setuptools/wheel no ambiente virtual...${NC}"
"$VENV_PY" -m pip install --upgrade pip setuptools wheel || {
    echo -e "${YELLOW}⚠️ Tentando instalar get-pip.py dentro do venv...${NC}"
    curl -fsS https://bootstrap.pypa.io/get-pip.py -o get-pip.py
    "$VENV_PY" get-pip.py
    rm -f get-pip.py
    "$VENV_PY" -m pip install --upgrade pip setuptools wheel
}

echo -e "${YELLOW}📦 Instalando dependências no venv...${NC}"
"$VENV_PY" -m pip install --use-pep517 -e . || {
    echo -e "${YELLOW}⚠️ Tentando instalar sem --use-pep517...${NC}"
    "$VENV_PY" -m pip install -e . || {
        echo -e "${RED}❌ Falha ao instalar dependências no venv.${NC}"
        exit 1
    }
}

# Cria o wrapper script
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    cat > "$WRAPPER_SCRIPT" << EOF
#!/bin/bash
INSTALL_DIR="$INSTALL_DIR"
VENV="\$INSTALL_DIR/.venv"

# Ativa o ambiente virtual e executa o comando
source "\$VENV/bin/activate"
python3 -m kube_cli "\$@"
EOF
else
    # Linux
    cat > "$WRAPPER_SCRIPT" << 'EOF'
#!/bin/bash
INSTALL_DIR="/opt/easy-kube-cli"
VENV="$INSTALL_DIR/.venv"

# Ativa o ambiente virtual e executa o comando
source "$VENV/bin/activate"
python3 -m kube_cli "$@"
EOF
fi

# Link simbólico para o atalho ek-cli (mesmo wrapper que kube-cli)
ln -s "$WRAPPER_SCRIPT" "$ALIAS_SCRIPT"

# Torna o wrapper executável
chmod +x "$WRAPPER_SCRIPT"

# Ajusta as permissões
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    chown -R $(logname):$(logname) "$INSTALL_DIR"
    chown $(logname):$(logname) "$WRAPPER_SCRIPT"
    chown -h $(logname):$(logname) "$ALIAS_SCRIPT"
fi

echo -e "\n${GREEN}✅ Easy Kube Cli instalada com sucesso!${NC}"
echo -e "${YELLOW}Os comandos ${GREEN}kube-cli${YELLOW} e ${GREEN}ek-cli${YELLOW} agora estão disponíveis.${NC}"

if [[ "$OSTYPE" == "darwin"* ]]; then
    echo -e "\n${YELLOW}⚠️ Para usar os comandos, certifique-se de que $HOME/.local/bin está no seu PATH:${NC}"
    echo -e "${GREEN}source ~/.zshrc${NC} ${YELLOW}ou${NC} ${GREEN}source ~/.bash_profile${NC}"
fi

echo -e "\n${YELLOW}Para verificar a instalação:${NC}"
echo -e "${GREEN}kube-cli --version${NC}"
echo -e "${GREEN}ek-cli --version${NC}"

# Verifica se o AWS CLI precisa ser configurado
if ! aws configure list &> /dev/null; then
    echo -e "\n${YELLOW}⚠️  AWS CLI ainda não está configurado.${NC}"
    echo -e "${YELLOW}Execute o comando abaixo para configurar:${NC}"
    echo -e "${GREEN}aws configure sso${NC}"
    echo -e "\nDicas de configuração:"
    echo -e "- SSO start URL: https://yourdomain.awsapps.com.br/start"
    echo -e "- SSO Region: us-east-1"
    echo -e "- CLI default client Region: us-east-1"
    echo -e "- CLI default output format: json"
fi 