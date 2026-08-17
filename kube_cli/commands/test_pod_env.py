"""Checagem do parse da saída do printenv.

Roda da raiz do repo: python -m kube_cli.commands.test_pod_env
"""

import re

from kube_cli.commands.pods import parse_printenv


def test_pares_simples_ordenados():
    got = parse_printenv('PATH=/usr/bin\nHOME=/root\n')
    assert got == [['HOME', '/root'], ['PATH', '/usr/bin']], got


def test_valor_com_igual_fica_inteiro():
    got = parse_printenv('DB_URL=postgres://u:p@h/db?a=1&b=2\n')
    assert got == [['DB_URL', 'postgres://u:p@h/db?a=1&b=2']], got


def test_valor_vazio():
    assert parse_printenv('SWAP_TOKEN=\n') == [['SWAP_TOKEN', '']]


def test_valor_multilinha_indentado_nao_vira_variavel_nova():
    saida = (
        'LOG_CONFIG={\n'
        '  "level": "debug",\n'
        '  "sink": "stdout=1"\n'
        '}\n'
        'SWAP_HOST=api.local\n'
    )
    got = dict(parse_printenv(saida))

    assert list(got) == ['LOG_CONFIG', 'SWAP_HOST'], f'só duas variáveis: {list(got)}'
    assert got['LOG_CONFIG'].endswith('}')
    assert '"sink": "stdout=1"' in got['LOG_CONFIG'], 'linha indentada com = é continuação'


def test_base64_multilinha_e_um_teto_conhecido():
    # A saída do printenv é ambígua aqui: 'MIIB...=' é indistinguível de uma
    # variável de valor vazio. Documenta o comportamento real em vez de fingir
    # que resolve — o 'printenv | grep' quebra igual.
    saida = (
        'TLS_CERT=-----BEGIN CERTIFICATE-----\n'
        'MIIBIjANBgkqhkiG9w0=\n'
        '-----END CERTIFICATE-----\n'
        'SWAP_HOST=api.local\n'
    )
    nomes = [n for n, _ in parse_printenv(saida)]

    assert 'MIIBIjANBgkqhkiG9w0' in nomes, 'entrada espúria esperada, é o teto conhecido'
    assert 'SWAP_HOST' in nomes, 'as variáveis seguintes continuam íntegras'
    # O filtro por nome, que é o uso real, não é afetado.
    assert parse_printenv(saida, re.compile('^SWAP_')) == [['SWAP_HOST', 'api.local']]


def test_filtro_por_nome():
    saida = 'SWAP_HOST=a\nSWAP_PORT=1\nPATH=/bin\nMY_SWAP_X=z\n'

    ancorado = parse_printenv(saida, re.compile('^SWAP_'))
    assert [n for n, _ in ancorado] == ['SWAP_HOST', 'SWAP_PORT'], ancorado

    solto = parse_printenv(saida, re.compile('SWAP_'))
    assert [n for n, _ in solto] == ['MY_SWAP_X', 'SWAP_HOST', 'SWAP_PORT'], solto

    assert parse_printenv(saida, re.compile('^NAO_EXISTE')) == []


def test_valor_com_markup_do_rich_sai_intacto():
    got = parse_printenv('LOG_FORMAT=[bold]%d[/] %msg\n')
    assert got == [['LOG_FORMAT', '[bold]%d[/] %msg']], got


def test_saida_vazia():
    assert parse_printenv('') == []
    assert parse_printenv('\n') == []


if __name__ == '__main__':
    for name, run in sorted(globals().items()):
        if name.startswith('test_'):
            run()
            print(f'ok  {name}')
    print('\ntodos os checks passaram')
