# src/devices/temp_sensor.py
# VERSÃO CORRETA E FINAL
import socket
import threading
import time
import uuid
import random
from generated import smart_city_pb2

# --- Configurações ---
DEVICE_ID = f"temp_{uuid.uuid4().hex[:6]}"
DEVICE_TYPE = smart_city_pb2.DeviceType.Value('TEMP_SENSOR')
GATEWAY_IP = "192.168.1.7"
GATEWAY_TCP_PORT = 10000
GATEWAY_UDP_PORT = 10001
MULTICAST_GROUP = "224.1.1.1"
MULTICAST_PORT = 5007

def send_status_updates(udp_socket):
    while True:
        temp = round(random.uniform(22.0, 31.0), 2)
        wrapper_msg = smart_city_pb2.WrapperMessage()
        status = wrapper_msg.status_update
        status.device_id = DEVICE_ID
        status.temperature = temp
        udp_socket.sendto(wrapper_msg.SerializeToString(), (GATEWAY_IP, GATEWAY_UDP_PORT))
        print(f"Enviado status: Temperatura = {temp:.2f}°C")
        time.sleep(15)

def listen_for_discovery():
    multicast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    multicast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    multicast_socket.bind(("", MULTICAST_PORT))
    group = socket.inet_aton(MULTICAST_GROUP)
    mreq = group + socket.inet_aton("0.0.0.0")
    multicast_socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    print(f"Sensor de Temperatura ({DEVICE_ID}) aguardando descoberta...")
    while True:
        data, address = multicast_socket.recvfrom(1024)
        if data == b"GATEWAY_DISCOVERY":
            print("--> Descoberta recebida. Registrando e iniciando envio de dados.")
            try:
                tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                tcp_socket.connect((GATEWAY_IP, GATEWAY_TCP_PORT))
                wrapper_msg = smart_city_pb2.WrapperMessage()
                info = wrapper_msg.device_info
                info.id = DEVICE_ID
                info.type = DEVICE_TYPE
                tcp_socket.send(wrapper_msg.SerializeToString())
                print("--> SUCESSO: Registrado no Gateway.")
                tcp_socket.close()
                update_thread = threading.Thread(target=send_status_updates, args=(socket.socket(socket.AF_INET, socket.SOCK_DGRAM),), daemon=True)
                update_thread.start()
            except Exception as e: print(f"Falha ao registrar via TCP: {e}")
            break

if __name__ == "__main__":
    listen_for_discovery()
    while True: time.sleep(3600)
