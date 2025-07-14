import socket
import threading
import time
from generated import smart_city_pb2

# --- Configurações ---
# Define as constantes de rede para o gateway, incluindo IPs e portas
# para comunicação com dispositivos, clientes, e para o multicast.
GATEWAY_IP = "192.168.1.7"
DEVICE_TCP_PORT = 10000  # Porta para Dispositivos
CLIENT_TCP_PORT = 10003  # Nova porta para Clientes
UDP_PORT = 10001
MULTICAST_GROUP = "224.1.1.1"
MULTICAST_PORT = 5007

# --- Estado do Gateway ---
# Dicionários para armazenar o estado e os sockets dos dispositivos conectados.
devices = {}  # Armazena informações e status de cada dispositivo.
device_tcp_sockets = {}  # Armazena os objetos de socket para comunicação TCP com cada dispositivo.
lock = threading.Lock()  # Um lock para garantir que o acesso aos dicionários seja seguro em ambiente com múltiplas threads.

def handle_device_connection(conn):
    """
    Lida com a conexão inicial de um novo dispositivo.
    
    Esta função é executada em uma thread para cada dispositivo que se conecta.
    Ela recebe uma mensagem de identificação, a decodifica com Protocol Buffers,
    e registra o dispositivo nos dicionários globais.
    """
    try:
        # Recebe os dados de identificação do dispositivo.
        data = conn.recv(1024)
        if not data:
            conn.close()
            return

        # Decodifica a mensagem usando o wrapper do Protocol Buffers.
        wrapper_msg = smart_city_pb2.WrapperMessage()
        wrapper_msg.ParseFromString(data)

        # Verifica se a mensagem contém informações de um dispositivo.
        if wrapper_msg.HasField("device_info"):
            info = wrapper_msg.device_info
            # Usa o lock para adicionar o dispositivo aos dicionários de forma segura.
            with lock:
                devices[info.id] = {'info': info, 'status': None}
                device_tcp_sockets[info.id] = conn
            device_type_name = smart_city_pb2.DeviceType.Name(info.type)
            print(f"--> SUCESSO: Dispositivo {info.id} ({device_type_name}) conectado na porta de dispositivos.")
        else:
            print("[ERRO] Conexão na porta de dispositivos não se identificou como um dispositivo.")
            conn.close()
    except Exception as e:
        print(f"[ERRO] Durante registro de dispositivo: {e}")
        conn.close()


def handle_client_connection(conn):
    """
    Lida com a conexão e os pedidos de um cliente de controle.

    Executada em uma thread para cada cliente, esta função entra em um loop para
    receber e processar requisições do cliente, como listar dispositivos ou
    encaminhar comandos para os dispositivos específicos.
    """
    print(f"[TCP-CLIENT] Cliente conectado de {conn.getpeername()}.")
    try:
        while True:
            data = conn.recv(1024)
            if not data:
                break  # Cliente desconectou

            wrapper_msg = smart_city_pb2.WrapperMessage()
            wrapper_msg.ParseFromString(data)
            
            # Se for um pedido para listar os dispositivos...
            if wrapper_msg.HasField("list_request"):
                print("[GATEWAY] Recebido pedido de listagem do cliente.")
                response_msg = smart_city_pb2.WrapperMessage()
                list_response = response_msg.list_response
                # Com o lock ativado, cria uma lista com as informações dos dispositivos registrados.
                with lock:
                    for device_id, device_data in devices.items():
                        device_info = list_response.devices.add()
                        device_info.id = device_id
                        device_info.type = device_data['info'].type
                # Envia a resposta para o cliente.
                conn.send(response_msg.SerializeToString())
                print("[GATEWAY] Resposta da lista enviada.")

            # Se for um comando para um dispositivo...
            elif wrapper_msg.HasField("command"):
                cmd = wrapper_msg.command
                print(f"[GATEWAY] Recebido comando para {cmd.device_id}.")
                # Encontra o socket do dispositivo alvo.
                target_socket = device_tcp_sockets.get(cmd.device_id)
                if target_socket:
                    # Encaminha a mensagem de comando para o dispositivo.
                    target_socket.send(wrapper_msg.SerializeToString())
                else:
                    print(f"[ERRO] Dispositivo {cmd.device_id} não encontrado.")

    except Exception as e:
        print(f"Erro com cliente {conn.getpeername()}: {e}")
    finally:
        print(f"[TCP-CLIENT] Cliente {conn.getpeername()} desconectado.")
        conn.close()


def device_tcp_server():
    """Cria e mantém um servidor TCP que escuta por conexões de dispositivos."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((GATEWAY_IP, DEVICE_TCP_PORT))
    server_socket.listen(5)
    print(f"[TCP-DEVICE] Gateway ouvindo por Dispositivos na porta {DEVICE_TCP_PORT}")
    while True:
        conn, addr = server_socket.accept()
        # Para cada nova conexão, uma nova thread é criada para lidar com o registro.
        threading.Thread(target=handle_device_connection, args=(conn,), daemon=True).start()

def client_tcp_server():
    """Cria e mantém um servidor TCP que escuta por conexões de clientes."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((GATEWAY_IP, CLIENT_TCP_PORT))
    server_socket.listen(5)
    print(f"[TCP-CLIENT] Gateway ouvindo por Clientes na porta {CLIENT_TCP_PORT}")
    while True:
        conn, addr = server_socket.accept()
        # Para cada nova conexão, uma nova thread é criada para lidar com as requisições.
        threading.Thread(target=handle_client_connection, args=(conn,), daemon=True).start()

def listen_for_udp_data():
    """Cria um socket UDP para receber dados de status enviados pelos sensores."""
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.bind(("", UDP_PORT))
    print(f"[UDP] Gateway ouvindo por dados de sensores na porta {UDP_PORT}")
    while True:
        data, addr = udp_socket.recvfrom(1024)
        wrapper_msg = smart_city_pb2.WrapperMessage()
        wrapper_msg.ParseFromString(data)
        if wrapper_msg.HasField("status_update"):
            status = wrapper_msg.status_update
            # Com o lock, atualiza o status do dispositivo correspondente.
            with lock:
                if status.device_id in devices:
                    devices[status.device_id]['status'] = status
                    if status.HasField("temperature"):
                        print(f"[UDP] Status recebido de {status.device_id}: Temperatura {status.temperature:.2f}°C")

def discover_devices_periodically():
    """
    Inicia e mantém o processo de descoberta de dispositivos na rede.

    Esta função cria um socket UDP configurado para multicast. Em um loop infinito,
    ela transmite uma mensagem de descoberta ('GATEWAY_DISCOVERY') para um grupo
    multicast específico a cada 10 segundos. Isso permite que novos dispositivos
    na rede se identifiquem para o gateway. As opções do socket (TTL e interface)
    garantem que as mensagens de descoberta sejam roteadas corretamente.
    """
    # Cria um socket UDP para a comunicação multicast.
    multicast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    # Define o Time-To-Live (TTL) do pacote multicast.
    multicast_socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    # Especifica a interface de rede a ser usada para enviar os pacotes multicast.
    multicast_socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(GATEWAY_IP))
    message = b"GATEWAY_DISCOVERY"
    while True:
        print(f"[DISCOVERY] Enviando sinal de descoberta...")
        multicast_socket.sendto(message, (MULTICAST_GROUP, MULTICAST_PORT))
        # Pausa de 10 segundos antes de enviar o próximo sinal.
        time.sleep(10)


# Bloco principal que inicializa o gateway.
if __name__ == "__main__":
    print(f"--- Gateway iniciando com IP fixo: {GATEWAY_IP} ---")
    
    # Inicia as funções de background em threads separadas para que não bloqueiem a execução.
    # Elas rodam em modo 'daemon', o que significa que serão encerradas quando o programa principal terminar.
    threading.Thread(target=discover_devices_periodically, daemon=True).start()
    threading.Thread(target=listen_for_udp_data, daemon=True).start()
    threading.Thread(target=device_tcp_server, daemon=True).start()
    
    # Inicia o servidor para clientes na thread principal.
    # Isso mantém o programa principal vivo, escutando por conexões de clientes.
    client_tcp_server()
