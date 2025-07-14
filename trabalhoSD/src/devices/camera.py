# src/devices/camera.py
import socket
import threading
import time
import uuid
from generated import smart_city_pb2

# --- Configurações ---
# Define um ID e tipo únicos para o dispositivo.
DEVICE_ID = f"cam_{uuid.uuid4().hex[:6]}"
DEVICE_TYPE = smart_city_pb2.DeviceType.Value('CAMERA')
# Constantes para a comunicação multicast de descoberta.
MULTICAST_GROUP = "224.1.1.1"
MULTICAST_PORT = 5007

# --- Estado do Dispositivo ---
# Variáveis que armazenam o estado atual da câmera.
is_on = False
resolution = "HD" # Estado inicial da resolução.

def listen_for_commands(tcp_socket):
    """
    Escuta por comandos do Gateway na conexão TCP persistente.

    Esta função roda em uma thread dedicada após a conexão ser estabelecida.
    Ela processa os comandos recebidos para alterar o estado da câmera.
    """
    global is_on, resolution
    try:
        # Loop infinito para continuar recebendo comandos.
        while True:
            # Fica bloqueado aqui, aguardando dados do Gateway.
            data = tcp_socket.recv(1024)
            if not data:
                print("Conexão com o Gateway perdida.")
                break
                
            # Decodifica a mensagem recebida com Protocol Buffers.
            wrapper_msg = smart_city_pb2.WrapperMessage()
            wrapper_msg.ParseFromString(data)
            
            # Verifica se a mensagem é um comando e se é para este dispositivo.
            if wrapper_msg.HasField("command"):
                cmd = wrapper_msg.command
                if cmd.device_id == DEVICE_ID:
                    # Lida com o comando 'toggle' para ligar/desligar.
                    if cmd.HasField("toggle"):
                        is_on = not is_on
                        print(f"--> Comando 'toggle' recebido! Câmera agora está {'LIGADA' if is_on else 'DESLIGADA'}.")
                    
                    # Lida com o comando 'new_config' para alterar outras configurações.
                    if cmd.HasField("new_config"):
                        # Tenta processar a string de configuração (ex: "resolution:FullHD").
                        try:
                            # Divide a string em chave e valor.
                            key, value = cmd.new_config.split(':')
                            if key.lower() == "resolution":
                                resolution = value
                                print(f"--> Comando 'config' recebido! Resolução alterada para {resolution}.")
                            else:
                                print(f"Configuração desconhecida: {key}")
                        except ValueError:
                            # Erro caso a string não esteja no formato esperado.
                            print(f"Formato de configuração inválido recebido: {cmd.new_config}")

    except ConnectionResetError:
        print("Conexão com o Gateway foi resetada.")
    except Exception as e:
        print(f"Erro ao receber comando: {e}")
    finally:
        # Garante que o socket seja fechado ao final.
        tcp_socket.close()

def discover_gateway_and_connect():
    """
    Escuta por anúncios do Gateway na rede para se registrar e, em seguida,
    mantém a conexão para receber comandos.
    """
    # Configura o socket para escutar por mensagens multicast.
    multicast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    multicast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    multicast_socket.bind(("", MULTICAST_PORT))
    group = socket.inet_aton(MULTICAST_GROUP)
    mreq = group + socket.inet_aton("0.0.0.0")
    multicast_socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    
    print(f"Câmera ({DEVICE_ID}) aguardando anúncio do Gateway...")
    
    # Loop de descoberta.
    while True:
        data, address = multicast_socket.recvfrom(1024)
        wrapper_msg = smart_city_pb2.WrapperMessage()
        wrapper_msg.ParseFromString(data)
        
        # Se receber um anúncio válido do Gateway...
        if wrapper_msg.HasField("gateway_info"):
            gateway_info = wrapper_msg.gateway_info
            discovered_ip = gateway_info.ip_address
            # Um atuador se conecta à porta de dispositivos.
            discovered_port = gateway_info.device_tcp_port
            print(f"--> Gateway encontrado em {discovered_ip}:{discovered_port}. Conectando...")
            
            try:
                # Inicia a CONEXÃO TCP PERSISTENTE para o registro e recebimento de comandos.
                tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                tcp_socket.connect((discovered_ip, discovered_port))
                
                # Envia sua mensagem de identificação.
                register_msg = smart_city_pb2.WrapperMessage()
                info = register_msg.device_info
                info.id = DEVICE_ID
                info.type = DEVICE_TYPE
                tcp_socket.send(register_msg.SerializeToString())
                
                print(f"--> SUCESSO: Registrado no Gateway. Aguardando comandos.")
                
                # Inicia a thread que ficará escutando por comandos.
                command_thread = threading.Thread(target=listen_for_commands, args=(tcp_socket,), daemon=True)
                command_thread.start()
                # Sai do loop de descoberta após o sucesso.
                break
            except Exception as e:
                # Se falhar, aguarda para tentar novamente no próximo anúncio.
                print(f"Falha ao conectar no Gateway descoberto: {e}")
                time.sleep(5)

# Ponto de entrada do script.
if __name__ == "__main__":
    discover_gateway_and_connect()
    # Mantém a thread principal viva indefinidamente.
    while True:
        time.sleep(3600)
