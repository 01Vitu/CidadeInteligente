# src/devices/temp_sensor.py
import socket
import threading
import time
import uuid
import random
from generated import smart_city_pb2

# --- Configurações ---
DEVICE_ID = f"temp_{uuid.uuid4().hex[:6]}"
DEVICE_TYPE = smart_city_pb2.DeviceType.Value('TEMP_SENSOR')
# A porta UDP para status pode permanecer constante ou ser anunciada pelo Gateway.
# Para simplicidade, vamos mantê-la constante.
GATEWAY_UDP_PORT = 10001
MULTICAST_GROUP = "224.1.1.1"
MULTICAST_PORT = 5007

# A função de envio de status agora precisa receber o IP do Gateway.
def send_status_updates(udp_socket, gateway_ip):
    while True:
        temp = round(random.uniform(22.0, 31.0), 2)
        wrapper_msg = smart_city_pb2.WrapperMessage()
        status = wrapper_msg.status_update
        status.device_id = DEVICE_ID
        status.temperature = temp
        # Usa o IP do Gateway descoberto dinamicamente.
        udp_socket.sendto(wrapper_msg.SerializeToString(), (gateway_ip, GATEWAY_UDP_PORT))
        print(f"Enviado status: Temperatura = {temp:.2f}°C para {gateway_ip}")
        time.sleep(15)

# --- NOVA FUNÇÃO DE DESCOBERTA E CONEXÃO ---
def discover_gateway_and_connect():
    """Escuta e conecta ao Gateway para registro, depois inicia o envio de status UDP."""
    multicast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    multicast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    multicast_socket.bind(("", MULTICAST_PORT))
    group = socket.inet_aton(MULTICAST_GROUP)
    mreq = group + socket.inet_aton("0.0.0.0")
    multicast_socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    
    print(f"Sensor de Temperatura ({DEVICE_ID}) aguardando anúncio do Gateway...")
    
    while True:
        data, address = multicast_socket.recvfrom(1024)
        wrapper_msg = smart_city_pb2.WrapperMessage()
        wrapper_msg.ParseFromString(data)
        
        if wrapper_msg.HasField("gateway_info"):
            gateway_info = wrapper_msg.gateway_info
            discovered_ip = gateway_info.ip_address
            discovered_port = gateway_info.device_tcp_port
            print(f"--> Gateway encontrado em {discovered_ip}:{discovered_port}. Registrando...")

            try:
                tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                tcp_socket.connect((discovered_ip, discovered_port))
                
                register_msg = smart_city_pb2.WrapperMessage()
                info = register_msg.device_info
                info.id = DEVICE_ID
                info.type = DEVICE_TYPE
                tcp_socket.send(register_msg.SerializeToString())
                print("--> SUCESSO: Registrado no Gateway.")
                tcp_socket.close() # Fecha a conexão TCP
                
                # Inicia a thread de envio de status UDP, passando o IP descoberto.
                update_thread = threading.Thread(target=send_status_updates, args=(socket.socket(socket.AF_INET, socket.SOCK_DGRAM), discovered_ip), daemon=True)
                update_thread.start()
                break
            except Exception as e:
                print(f"Falha ao registrar no Gateway: {e}")
                time.sleep(5)

if __name__ == "__main__":
    discover_gateway_and_connect()
    while True:
        time.sleep(3600)