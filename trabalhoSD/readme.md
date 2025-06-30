# Sistema de Cidade Inteligente Distribuído

![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)
![Status](https://img.shields.io/badge/status-concluído-green.svg)


Simulação de um sistema distribuído de Cidade Inteligente usando Python, Sockets (TCP/UDP/Multicast) e Protocol Buffers.

## Visão Geral

Este projeto implementa um sistema distribuído que simula o funcionamento de uma cidade inteligente. Ele é composto por três partes principais:

* **Gateway Central:** Atua como o cérebro do sistema, gerenciando o estado dos dispositivos, roteando comandos e coletando dados.
* **Dispositivos Inteligentes:** Processos independentes que simulam sensores (como um sensor de temperatura) e atuadores (como um poste de luz que pode ser ligado/desligado).
* **Cliente:** Uma interface de linha de comando (CLI) que permite a um usuário monitorar e controlar os dispositivos conectados através do Gateway.

## Arquitetura do Sistema

O sistema utiliza diferentes protocolos para diferentes tarefas, com o Gateway agindo como o intermediário principal.

```
      Cliente (Controle)
           | (TCP - Porta 10003)
           V
      +-----------------+
      |     Gateway     |<---- (UDP - Porta 10001) ---- Sensor
      +-----------------+
           | (TCP - Porta 10000)
           V
      Atuador (Poste)

(Descoberta inicial via UDP Multicast - Porta 5007)
```

## Tecnologias Utilizadas

* **Linguagem:** Python 3
* **Comunicação em Rede:** Biblioteca nativa `socket` do Python.
    * **TCP:** Para comunicação confiável e orientada à conexão (registro de dispositivos, envio de comandos).
    * **UDP:** Para envio rápido e sem conexão de dados de sensores.
    * **UDP Multicast:** Para a descoberta inicial de dispositivos na rede.
* **Concorrência:** Biblioteca `threading` para permitir que o Gateway lide com múltiplas tarefas e conexões simultaneamente.
* **Serialização de Dados:** [Google Protocol Buffers (Protobuf)](https://developers.google.com/protocol-buffers) para garantir uma comunicação eficiente, rápida e com um formato de mensagem bem definido.

## Estrutura do Projeto

```
cidade_inteligente/
├── protos/
│   └── smart_city.proto      # Definição de todas as mensagens
├── generated/
│   └── smart_city_pb2.py     # Código Python gerado pelo compilador Protobuf
├── src/
│   ├── gateway/
│   │   └── gateway.py        # Lógica do Gateway Central
│   ├── devices/
│   │   ├── lamp_post.py      # Lógica do Atuador (Poste de Luz)
│   │   └── temp_sensor.py    # Lógica do Sensor de Temperatura
│   └── client/
│       └── client.py         # Lógica do Cliente de linha de comando
└── requirements.txt            # Dependências do projeto
```

## Instalação e Configuração

**1. Clone o Repositório:**
```bash
git clone [https://github.com/seu-usuario/seu-repositorio.git](https://github.com/seu-usuario/seu-repositorio.git)
cd seu-repositorio
```

**2. Crie um Ambiente Virtual (Recomendado):**
```bash
python -m venv venv
source venv/bin/activate  # No Linux/macOS
# ou
venv\Scripts\activate   # No Windows
```

**3. Instale as Dependências:**
```bash
pip install -r requirements.txt
```

**4. Compile o Protocol Buffers:**
Este passo gera o código Python a partir da definição das mensagens.
```bash
python -m grpc_tools.protoc -I=protos --python_out=generated protos/smart_city.proto
```

**5. Configure o Endereço de IP (Passo Crucial):**
O código está configurado com um IP fixo (`192.168.1.7`). Você **precisa** alterar este valor para o endereço IP da máquina que rodará o Gateway na sua rede local.

* **Como descobrir seu IP local:**
    * **Windows:** Abra o `cmd` e digite `ipconfig`. Procure pelo "Endereço IPv4".
    * **Linux/macOS:** Abra o terminal e digite `ifconfig` ou `ip a`.

* **Arquivos para alterar:**
    * `src/gateway/gateway.py`
    * `src/devices/lamp_post.py`
    * `src/devices/temp_sensor.py`
    * `src/client/client.py`

    Em cada um desses arquivos, encontre a linha `GATEWAY_IP = "192.168.1.7"` e substitua o IP pelo seu.

## Como Executar

Para executar o sistema, você precisará de **4 terminais** abertos, todos na pasta raiz do projeto. Execute os comandos na seguinte ordem:

**1. Terminal 1 - Inicie o Gateway:**
```bash
python -m src.gateway.gateway
```

**2. Terminal 2 - Inicie o Poste de Luz (Atuador):**
```bash
python -m src.devices.lamp_post
```

**3. Terminal 3 - Inicie o Sensor de Temperatura:**
```bash
python -m src.devices.temp_sensor
```

**4. Terminal 4 - Inicie o Cliente:**
```bash
python -m src.client.client
```

Agora você pode usar o menu no Terminal 4 para listar os dispositivos e enviar comandos.
