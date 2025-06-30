# src/gateway/gateway.py
# VERSÃO FINAL COM PORTAS SEPARADAS
import socket
import threading
import time
from generated import smart_city_pb2

# --- Configurações ---
GATEWAY_IP = "192.168.1.7"
DEVICE_TCP_PORT = 10000  # Porta para Dispositivos
CLIENT_TCP_PORT = 10003  # Nova porta para Clientes
UDP_PORT = 10001
MULTICAST_GROUP = "224.1.1.1"
MULTICAST_PORT = 5007

# --- Estado do Gateway ---
devices = {}
device_tcp_sockets = {}
lock = threading.Lock()

def handle_device_connection(conn):
    """Lida exclusivamente com a conexão de um dispositivo."""
    try:
        data = conn.recv(1024)
        if not data:
            conn.close()
            return

        wrapper_msg = smart_city_pb2.WrapperMessage()
        wrapper_msg.ParseFromString(data)

        if wrapper_msg.HasField("device_info"):
            info = wrapper_msg.device_info
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
    """Lida exclusivamente com a conexão e os pedidos de um cliente."""
    print(f"[TCP-CLIENT] Cliente conectado de {conn.getpeername()}.")
    try:
        while True:
            data = conn.recv(1024)
            if not data:
                break # Cliente desconectou

            wrapper_msg = smart_city_pb2.WrapperMessage()
            wrapper_msg.ParseFromString(data)
            
            if wrapper_msg.HasField("list_request"):
                print("[GATEWAY] Recebido pedido de listagem do cliente.")
                response_msg = smart_city_pb2.WrapperMessage()
                list_response = response_msg.list_response
                with lock:
                    for device_id, device_data in devices.items():
                        device_info = list_response.devices.add()
                        device_info.id = device_id
                        device_info.type = device_data['info'].type
                conn.send(response_msg.SerializeToString())
                print("[GATEWAY] Resposta da lista enviada.")

            elif wrapper_msg.HasField("command"):
                cmd = wrapper_msg.command
                print(f"[GATEWAY] Recebido comando para {cmd.device_id}.")
                target_socket = device_tcp_sockets.get(cmd.device_id)
                if target_socket:
                    target_socket.send(wrapper_msg.SerializeToString())
                else:
                    print(f"[ERRO] Dispositivo {cmd.device_id} não encontrado.")

    except Exception as e:
        print(f"Erro com cliente {conn.getpeername()}: {e}")
    finally:
        print(f"[TCP-CLIENT] Cliente {conn.getpeername()} desconectado.")
        conn.close()


def device_tcp_server():
    """Servidor TCP que escuta APENAS por dispositivos."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((GATEWAY_IP, DEVICE_TCP_PORT))
    server_socket.listen(5)
    print(f"[TCP-DEVICE] Gateway ouvindo por Dispositivos na porta {DEVICE_TCP_PORT}")
    while True:
        conn, addr = server_socket.accept()
        # Uma thread para cada dispositivo que se conecta
        threading.Thread(target=handle_device_connection, args=(conn,), daemon=True).start()

def client_tcp_server():
    """Servidor TCP que escuta APENAS por clientes."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((GATEWAY_IP, CLIENT_TCP_PORT))
    server_socket.listen(5)
    print(f"[TCP-CLIENT] Gateway ouvindo por Clientes na porta {CLIENT_TCP_PORT}")
    while True:
        conn, addr = server_socket.accept()
        # Uma thread para cada cliente que se conecta
        threading.Thread(target=handle_client_connection, args=(conn,), daemon=True).start()

def listen_for_udp_data():
    # ... (sem alterações aqui)
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.bind(("", UDP_PORT))
    print(f"[UDP] Gateway ouvindo por dados de sensores na porta {UDP_PORT}")
    while True:
        data, addr = udp_socket.recvfrom(1024)
        wrapper_msg = smart_city_pb2.WrapperMessage(); wrapper_msg.ParseFromString(data)
        if wrapper_msg.HasField("status_update"):
            status = wrapper_msg.status_update
            with lock:
                if status.device_id in devices:
                    devices[status.device_id]['status'] = status
                    if status.HasField("temperature"):
                        print(f"[UDP] Status recebido de {status.device_id}: Temperatura {status.temperature:.2f}°C")

def discover_devices_periodically():
    # ... (sem alterações aqui)
    multicast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    multicast_socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    multicast_socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(GATEWAY_IP))
    message = b"GATEWAY_DISCOVERY"
    while True:
        print(f"[DISCOVERY] Enviando sinal de descoberta...")
        multicast_socket.sendto(message, (MULTICAST_GROUP, MULTICAST_PORT))
        time.sleep(10)


if __name__ == "__main__":
    print(f"--- Gateway iniciando com IP fixo: {GATEWAY_IP} ---")
    
    threading.Thread(target=discover_devices_periodically, daemon=True).start()
    threading.Thread(target=listen_for_udp_data, daemon=True).start()
    
    # Inicia o servidor para DISPOSITIVOS
    threading.Thread(target=device_tcp_server, daemon=True).start()
    
    # Inicia o servidor para CLIENTES
    # A thread principal pode cuidar disso para não terminar o programa
    client_tcp_server()