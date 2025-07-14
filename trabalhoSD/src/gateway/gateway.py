import socket
import threading
import time
from generated import smart_city_pb2

# --- NOVA FUNÇÃO para detectar o IP local ---
def get_local_ip():
    """
    Descobre o endereço IP local da máquina na rede.

    Cria uma conexão UDP temporária para um destino externo (não envia dados)
    para que o sistema operacional informe qual é o endereço IP da interface
    de rede preferencial.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Conecta-se a um servidor conhecido na internet, como o DNS do Google.
        # Isso não envia dados, apenas força o SO a escolher uma rota e um IP.
        s.connect(('8.8.8.8', 1))
        IP = s.getsockname()[0]
    except Exception:
        # Se a máquina não estiver conectada à internet, usa o localhost como fallback.
        IP = '127.0.0.1'
    finally:
        # Fecha o socket temporário.
        s.close()
    return IP

# --- Configurações ---
# A variável GATEWAY_IP agora é preenchida dinamicamente pela função get_local_ip().
GATEWAY_IP = get_local_ip()
DEVICE_TCP_PORT = 10000  # Porta para Dispositivos se conectarem via TCP.
CLIENT_TCP_PORT = 10003  # Porta para Clientes se conectarem via TCP.
UDP_PORT = 10001         # Porta para receber status de sensores via UDP.
MULTICAST_GROUP = "224.1.1.1" # Endereço do grupo multicast para descoberta.
MULTICAST_PORT = 5007         # Porta para a comunicação multicast.

# --- Estado do Gateway ---
# Dicionários globais para armazenar o estado do sistema.
devices = {}              # Armazena informações e o último status de cada dispositivo.
device_tcp_sockets = {}   # Armazena os objetos de socket TCP ativos para cada dispositivo.
lock = threading.Lock()   # Um "cadeado" (lock) para garantir acesso seguro aos dicionários por múltiplas threads.

def discover_devices_periodically():
    """
    Anuncia a presença e as informações de conexão do Gateway na rede
    periodicamente via multicast.
    """
    # Cria um socket UDP para a comunicação multicast.
    multicast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    # Define o Time-To-Live (TTL) do pacote, permitindo que ele passe por roteadores se necessário.
    multicast_socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    # Associa o socket à interface de rede do IP do gateway.
    multicast_socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(GATEWAY_IP))
    
    # Constrói a mensagem estruturada com as informações de conexão do Gateway.
    # Esta mensagem será o "cartão de visita" do Gateway na rede.
    wrapper_msg = smart_city_pb2.WrapperMessage()
    info = wrapper_msg.gateway_info
    info.ip_address = GATEWAY_IP
    info.device_tcp_port = DEVICE_TCP_PORT
    info.client_tcp_port = CLIENT_TCP_PORT
    
    # Serializa a mensagem para um formato de bytes para ser enviada pela rede.
    message = wrapper_msg.SerializeToString()
    
    # Loop infinito para enviar o anúncio a cada 10 segundos.
    while True:
        print(f"[DISCOVERY] Anunciando presença do Gateway ({GATEWAY_IP}) na rede...")
        multicast_socket.sendto(message, (MULTICAST_GROUP, MULTICAST_PORT))
        time.sleep(10)

def handle_device_connection(conn):
    """
    Lida com a conexão inicial de um novo dispositivo. Executada em uma thread.
    """
    try:
        # Recebe a mensagem de registro do dispositivo.
        data = conn.recv(1024)
        if not data:
            conn.close()
            return

        # Decodifica a mensagem usando Protocol Buffers.
        wrapper_msg = smart_city_pb2.WrapperMessage()
        wrapper_msg.ParseFromString(data)

        # Se for uma mensagem de identificação, registra o dispositivo.
        if wrapper_msg.HasField("device_info"):
            info = wrapper_msg.device_info
            # Usa o lock para garantir que a escrita nos dicionários seja segura.
            with lock:
                devices[info.id] = {'info': info, 'status': None}
                device_tcp_sockets[info.id] = conn
            device_type_name = smart_city_pb2.DeviceType.Name(info.type)
            print(f"--> SUCESSO: Dispositivo {info.id} ({device_type_name}) conectado.")
        else:
            # Se a mensagem não for de identificação, fecha a conexão.
            print("[ERRO] Conexão na porta de dispositivos não se identificou.")
            conn.close()
    except Exception as e:
        print(f"[ERRO] Durante registro de dispositivo: {e}")
        conn.close()


def handle_client_connection(conn):
    """
    Lida com a conexão e os pedidos de um cliente. Executada em uma thread.
    """
    print(f"[TCP-CLIENT] Cliente conectado de {conn.getpeername()}.")
    try:
        # Loop para processar múltiplos pedidos do mesmo cliente.
        while True:
            data = conn.recv(1024)
            if not data:
                break # Cliente desconectou

            wrapper_msg = smart_city_pb2.WrapperMessage()
            wrapper_msg.ParseFromString(data)
            
            # Se a requisição for para listar dispositivos...
            if wrapper_msg.HasField("list_request"):
                print("[GATEWAY] Recebido pedido de listagem do cliente.")
                response_msg = smart_city_pb2.WrapperMessage()
                list_response = response_msg.list_response
                # Acessa a lista de dispositivos de forma segura.
                with lock:
                    for device_id, device_data in devices.items():
                        device_info = list_response.devices.add()
                        device_info.id = device_id
                        device_info.type = device_data['info'].type
                # Envia a resposta para o cliente.
                conn.send(response_msg.SerializeToString())
                print("[GATEWAY] Resposta da lista enviada.")

            # Se a requisição for um comando...
            elif wrapper_msg.HasField("command"):
                cmd = wrapper_msg.command
                print(f"[GATEWAY] Recebido comando para {cmd.device_id}.")
                # Encontra o socket do dispositivo alvo para encaminhar o comando.
                target_socket = device_tcp_sockets.get(cmd.device_id)
                if target_socket:
                    target_socket.send(wrapper_msg.SerializeToString())
                else:
                    print(f"[ERRO] Dispositivo {cmd.device_id} não encontrado.")

    except Exception as e:
        print(f"Erro com cliente {conn.getpeername()}: {e}")
    finally:
        # Garante que a conexão seja fechada ao final.
        print(f"[TCP-CLIENT] Cliente {conn.getpeername()} desconectado.")
        conn.close()


def device_tcp_server():
    """Cria um servidor TCP que escuta APENAS por conexões de dispositivos."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((GATEWAY_IP, DEVICE_TCP_PORT))
    server_socket.listen(5)
    print(f"[TCP-DEVICE] Gateway ouvindo por Dispositivos na porta {DEVICE_TCP_PORT}")
    while True:
        conn, addr = server_socket.accept()
        # Cria uma nova thread para cada dispositivo que se conecta.
        threading.Thread(target=handle_device_connection, args=(conn,), daemon=True).start()

def client_tcp_server():
    """Cria um servidor TCP que escuta APENAS por conexões de clientes."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((GATEWAY_IP, CLIENT_TCP_PORT))
    server_socket.listen(5)
    print(f"[TCP-CLIENT] Gateway ouvindo por Clientes na porta {CLIENT_TCP_PORT}")
    while True:
        conn, addr = server_socket.accept()
        # Cria uma nova thread para cada cliente que se conecta.
        threading.Thread(target=handle_client_connection, args=(conn,), daemon=True).start()

def listen_for_udp_data():
    """Cria um socket UDP para receber dados de status enviados pelos sensores."""
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # O bind em "" (ou "0.0.0.0") permite aceitar pacotes de qualquer interface de rede.
    udp_socket.bind(("", UDP_PORT))
    print(f"[UDP] Gateway ouvindo por dados de sensores na porta {UDP_PORT}")
    while True:
        data, addr = udp_socket.recvfrom(1024)
        wrapper_msg = smart_city_pb2.WrapperMessage(); wrapper_msg.ParseFromString(data)
        if wrapper_msg.HasField("status_update"):
            status = wrapper_msg.status_update
            # Usa o lock para atualizar o status do dispositivo de forma segura.
            with lock:
                if status.device_id in devices:
                    devices[status.device_id]['status'] = status
                    # Imprime o status recebido para fins de log.
                    if status.HasField("temperature"):
                        print(f"[UDP] Status recebido de {status.device_id}: Temperatura {status.temperature:.2f}°C")
                    elif status.HasField("state_info"):
                         print(f"[UDP] Status recebido de {status.device_id}: {status.state_info}")


if __name__ == "__main__":
    # Ponto de entrada do programa.
    print(f"--- Gateway iniciando com IP dinâmico: {GATEWAY_IP} ---")
    
    # Inicia as funções principais em threads separadas para que rodem em paralelo.
    # 'daemon=True' garante que as threads sejam encerradas quando o programa principal terminar.
    threading.Thread(target=discover_devices_periodically, daemon=True).start()
    threading.Thread(target=listen_for_udp_data, daemon=True).start()
    threading.Thread(target=device_tcp_server, daemon=True).start()
    
    # Executa o servidor de clientes na thread principal.
    # Isso impede que o programa termine, mantendo todos os outros processos em daemon rodando.
    client_tcp_server()
