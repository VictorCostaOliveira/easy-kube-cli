#!/bin/bash

# Cores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}🗑️  Desinstalando Easy Kube Cli...${NC}\n"

# Verifica se está rodando como sudo no Linux, mas não no macOS
if [[ "$OSTYPE" == "linux-gnu"* ]] && [ "$EUID" -ne 0 ]; then 
    echo -e "${YELLOW}⚠️  Executando com sudo para desinstalação...${NC}"
    sudo "$0" "$@"
    exit $?
fi

# Define os diretórios com base no sistema operacional
if [[ "$OSTYPE" == "darwin"* ]]; then
    INSTALL_DIR="$HOME/.easy-kube-cli"
    WRAPPER_SCRIPT="$HOME/.local/bin/kube-cli"
    EKCLI_LINK="$HOME/.local/bin/ek-cli"
else
    INSTALL_DIR="/opt/easy-kube-cli"
    WRAPPER_SCRIPT="/usr/local/bin/kube-cli"
    EKCLI_LINK="/usr/local/bin/ek-cli"
fi

# Remove o comando principal
if [ -f "$WRAPPER_SCRIPT" ]; then
    echo -e "${YELLOW}🗑️  Removendo comando kube-cli...${NC}"
    rm -f "$WRAPPER_SCRIPT"
fi

# Remove o link simbólico ek-cli
if [ -L "$EKCLI_LINK" ] || [ -f "$EKCLI_LINK" ]; then
    echo -e "${YELLOW}🗑️  Removendo link simbólico ek-cli...${NC}"
    rm -f "$EKCLI_LINK"
fi

# Binários legados (jera-cli)
for legacy in "$HOME/.local/bin/jeracli" "$HOME/.local/bin/jcli" /usr/local/bin/jeracli /usr/local/bin/jcli; do
    if [ -L "$legacy" ] || [ -f "$legacy" ]; then
        echo -e "${YELLOW}🗑️  Removendo legado: ${legacy}${NC}"
        rm -f "$legacy"
    fi
done

# Remove o diretório de instalação
if [ -d "$INSTALL_DIR" ]; then
    echo -e "${YELLOW}🗑️  Removendo diretório de instalação...${NC}"
    rm -rf "$INSTALL_DIR"
fi

# Remove instalações legadas em disco
for legacy_dir in "$HOME/.jera-cli" /opt/jera-cli; do
    if [ -d "$legacy_dir" ]; then
        echo -e "${YELLOW}🗑️  Removendo diretório legado: ${legacy_dir}${NC}"
        rm -rf "$legacy_dir"
    fi
done

# Remove configurações locais (diretório de estado da CLI)
echo -e "${YELLOW}🗑️  Removendo configurações locais...${NC}"
if [ -n "${SUDO_USER:-}" ] && command -v getent &>/dev/null; then
    USER_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)
    rm -rf "${USER_HOME}/.easy-kube-cli"
    rm -rf "${USER_HOME}/.jera"
else
    rm -rf "${HOME}/.easy-kube-cli"
    rm -rf "${HOME}/.jera"
fi

echo -e "\n${GREEN}✅ Easy Kube Cli desinstalada com sucesso!${NC}"
